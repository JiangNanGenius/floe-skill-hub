"""Known OAuth declaration admission; no runtime or publication claim."""
import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hubcore


class OAuthConfigurationAdmission(unittest.TestCase):
    def candidate(self, skill_id="floe-google-auth"):
        value = json.loads((ROOT / "sources/floe-ios-automation/floe.json").read_bytes())
        value["id"] = skill_id
        value["capabilities"] = ["credentials", "network"]
        field = value["configuration"]["fields"][0]
        field["key"] = "connection"
        field["connectionKind"] = "oauth.external"
        field["title"] = {"en": "Account", "zh-Hans": "账号"}
        field["description"] = {"en": "Connect your account.", "zh-Hans": "连接你的账号。"}
        return value

    def parse(self, value):
        return hubcore.parse_manifest(hubcore.encoded(value))

    def test_only_two_known_provider_declarations(self):
        for skill_id in ("floe-google-auth", "floe-microsoft-auth"):
            value = self.candidate(skill_id)
            self.assertEqual(self.parse(value), value)
        with self.assertRaises(hubcore.HubError):
            self.parse(self.candidate("third-party-auth"))

    def test_authority_and_connection_injections_refused(self):
        base = self.candidate()
        mutations = []
        for key, value in (("tools", ["oauth.token"]), ("platforms", ["linux"]),
                           ("capabilities", ["credentials", "network", "device.interact"]),
                           ("capabilities", ["network"]), ("scriptRuntime", "python")):
            v = copy.deepcopy(base)
            v[key] = value
            mutations.append(v)
        for key, value in (("key", "bridge"), ("connectionKind", "ios.bridge.local"),
                           ("required", 1), ("sensitive", True), ("kind", "secret"),
                           ("value", "not-a-real-token"), ("authorizationURL", "https://example.invalid"),
                           ("title", {"en": "Account"})):
            v = copy.deepcopy(base)
            v["configuration"]["fields"][0][key] = value
            mutations.append(v)
        v = copy.deepcopy(base)
        v.pop("configuration")
        mutations.append(v)
        for value in mutations:
            with self.subTest(value=value), self.assertRaises(hubcore.HubError):
                self.parse(value)


if __name__ == "__main__":
    unittest.main()
