import copy
import json
import pathlib
import sys
import unittest
sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hubcore

class NativeIOSAdmission(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / "sources/floe-ios-automation/floe.json").read_bytes())

    def parse(self, value):
        return hubcore.parse_manifest(hubcore.encoded(value))

    def test_current_native_declaration_accepted(self):
        self.assertEqual(self.parse(self.manifest), self.manifest)

    def test_device_and_configuration_mutations_refused(self):
        mutations = []
        for key, value in [("id", "other-skill"), ("platforms", ["macos"]),
                           ("schemaVersion", True), ("scriptRuntime", "remote"),
                           ("tools", ["ios.bridge.control"]),
                           ("pythonPackages", [{"spec": "anything==1.0.0"}])]:
            mutations.append((key, value, None))
        for value in [["credentials"], ["browser.observe", "browser.interact", "credentials"],
                      self.manifest["capabilities"] + ["execution.remote"],
                      self.manifest["capabilities"] + ["workspace.write"]]:
            mutations.append(("capabilities", value, None))
        for key, value in [("key", "other"), ("kind", "secret"),
                           ("connectionKind", "ssh"), ("valueType", "url"),
                           ("required", False), ("required", 1),
                           ("sensitive", True), ("sensitive", 0),
                           ("title", {"en": "Only English"}),
                           ("title", {"en": "x" * 121, "zh-Hans": "标题"}),
                           ("description", {"en": "bad\ntext", "zh-Hans": "说明"})]:
            mutations.append((key, value, "field"))
        for key, value, where in mutations:
            with self.subTest(key=key, value=value):
                v=copy.deepcopy(self.manifest)
                target=v["configuration"]["fields"][0] if where else v
                target[key]=value
                with self.assertRaises((hubcore.HubError, TypeError, KeyError)):
                    self.parse(v)

    def test_secret_or_environment_injection_refused(self):
        for key, value in [("environment", []), ("token", "not-a-real-token"),
                           ("fields", self.manifest["configuration"]["fields"] * 2)]:
            with self.subTest(key=key):
                v=copy.deepcopy(self.manifest);v["configuration"][key]=value
                with self.assertRaises(hubcore.HubError): self.parse(v)
        v=copy.deepcopy(self.manifest);v["configuration"]["fields"][0]["value"]="placeholder"
        with self.assertRaises(hubcore.HubError): self.parse(v)
        v=copy.deepcopy(self.manifest);v.pop("configuration")
        with self.assertRaises(hubcore.HubError): self.parse(v)

    def test_existing_manifests_are_unchanged(self):
        base=ROOT / "sources"
        count=0
        for p in base.glob("*/floe.json"):
            original=json.loads(p.read_bytes())
            self.assertEqual(self.parse(original), original)
            count+=1
        self.assertGreaterEqual(count, 68)

    def test_static_review_and_registry_json_schemas(self):
        import jsonschema
        registry=json.loads((ROOT / "catalog/skills.json").read_bytes())
        for name, data in [("registry", registry)]:
            schema=json.loads((ROOT / f"schema/{name}.schema.json").read_bytes())
            jsonschema.validate(data, schema)
        schema=json.loads((ROOT / "schema/review.schema.json").read_bytes())
        for p in (ROOT / "reviews").glob("*/*.review.json"):
            jsonschema.validate(json.loads(p.read_bytes()),schema)

if __name__ == "__main__":
    unittest.main(verbosity=2)
