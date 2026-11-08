"""Actual read-only artifact/fixture bindings plus isolated mutation tests.

The temporary descriptor uses a test-only floor, never a publication offer.
No binary is executed and no authorization/provider account is contacted.
"""
import copy
import json
import os
import pathlib
import shutil
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hubcore
import runtime_dependency as runtime


class OrtieRuntimeBinding(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get("FLOE_TEST_SCRATCH"))
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        shutil.copytree(ROOT / "engines/ortie", self.root / "engines/ortie")
        version = "2.3.0+floe.1.0.0"
        artifact = runtime.expected_artifact_path(version, runtime.KNOWN_TARGET["triple"], runtime.ORTIE_COMPONENT_ID)
        binary = (self.root / artifact).read_bytes()
        self.descriptor = {
            "schemaVersion": 1, "componentID": runtime.ORTIE_COMPONENT_ID,
            "componentVersion": version, "minimumAppVersion": "0.0.0",
            "target": dict(runtime.KNOWN_TARGET),
            "artifact": {"path": artifact, "size": len(binary), "sha256": hubcore.sha256_hex(binary)},
            "oauthContract": {"version": 1, "sha256": hubcore.sha256_hex((self.root / runtime.ORTIE_CONTRACT_REL).read_bytes())},
        }
        self.freeze()

    def freeze(self):
        self.blob = hubcore.encoded(self.descriptor)
        (self.root / runtime.ORTIE_DESCRIPTOR_REL).write_bytes(self.blob)

    def contract(self):
        return json.loads((self.root / runtime.ORTIE_CONTRACT_REL).read_bytes())

    def update_contract(self, value):
        data = hubcore.encoded(value)
        (self.root / runtime.ORTIE_CONTRACT_REL).write_bytes(data)
        self.descriptor["oauthContract"]["sha256"] = hubcore.sha256_hex(data)
        self.freeze()

    def update_distribution(self, value):
        data = hubcore.encoded(value)
        (self.root / runtime.ORTIE_DISTRIBUTION_REL).write_bytes(data)
        contract = self.contract()
        contract["distribution"].update(size=len(data), sha256=hubcore.sha256_hex(data))
        self.update_contract(contract)

    def bind(self):
        return runtime.bind_package_descriptor(self.blob, self.root)

    def test_real_candidate_and_full_fresh_publication(self):
        self.assertEqual(self.bind(), self.descriptor)
        outputs = runtime.publication_files(self.blob, self.root)
        self.assertEqual(len(outputs), 408)
        self.assertNotIn(runtime.FROZEN_DESCRIPTOR_REL, outputs)
        fresh = self.root / "published"
        for rel, data in outputs.items():
            path = fresh / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        shutil.rmtree(self.root / "engines")
        self.assertEqual(runtime.bind_package_descriptor(self.blob, fresh), self.descriptor)

    def test_existing_impeccable_real_binding_unchanged(self):
        raw = (ROOT / runtime.FROZEN_DESCRIPTOR_REL).read_bytes()
        descriptor = runtime.bind_package_descriptor(raw, ROOT)
        outputs = runtime.publication_files(raw, ROOT)
        self.assertEqual(set(outputs), {runtime.FROZEN_DESCRIPTOR_REL, descriptor["artifact"]["path"]})

    def test_component_path_and_contract_confusion_refused(self):
        variants = []
        for key, value in (("componentID", "unknown"), ("schemaVersion", True)):
            d = copy.deepcopy(self.descriptor); d[key] = value; variants.append(d)
        d = copy.deepcopy(self.descriptor)
        d["captureContract"] = d.pop("oauthContract"); variants.append(d)
        d = copy.deepcopy(self.descriptor)
        d["artifact"]["path"] = runtime.expected_artifact_path(d["componentVersion"], d["target"]["triple"])
        variants.append(d)
        d = copy.deepcopy(self.descriptor); d["oauthContract"]["version"] = True; variants.append(d)
        for value in variants:
            with self.subTest(value=value), self.assertRaises(hubcore.HubError):
                runtime.parse_descriptor(hubcore.encoded(value))

    def test_descriptor_and_artifact_tampering_refused(self):
        with self.assertRaises(hubcore.HubError):
            runtime.parse_descriptor(self.blob + b"\n")
        path = self.root / self.descriptor["artifact"]["path"]
        path.write_bytes(path.read_bytes()[:-1] + b"x")
        with self.assertRaises(hubcore.HubError): self.bind()

    def test_missing_and_symlink_notice_refused(self):
        manifest = json.loads((self.root / runtime.ORTIE_DISTRIBUTION_REL).read_bytes())
        path = self.root / manifest["files"][0]["path"]
        data = path.read_bytes(); path.unlink()
        with self.assertRaises(hubcore.HubError): self.bind()
        outside = self.root / "notice-copy"; outside.write_bytes(data)
        path.symlink_to(outside)
        with self.assertRaises(hubcore.HubError): self.bind()

    def test_distribution_cannot_omit_pinned_mpl_source(self):
        value = json.loads((self.root / runtime.ORTIE_DISTRIBUTION_REL).read_bytes())
        value["files"] = [x for x in value["files"] if not x["path"].endswith(".crate")]
        self.update_distribution(value)
        with self.assertRaisesRegex(hubcore.HubError, "MPL source"): self.bind()

    def test_distribution_traversal_and_duplicate_refused(self):
        original = json.loads((self.root / runtime.ORTIE_DISTRIBUTION_REL).read_bytes())
        for mode in ("traversal", "duplicate"):
            value = copy.deepcopy(original)
            if mode == "traversal": value["files"][0]["path"] = "engines/ortie/notices/../outside"
            else: value["files"].insert(1, copy.deepcopy(value["files"][0]))
            self.update_distribution(value)
            with self.subTest(mode=mode), self.assertRaises(hubcore.HubError): self.bind()

    def test_transport_and_unknown_contract_fields_refused(self):
        original = self.contract()
        for value in (dict(original, url="https://example.invalid"), copy.deepcopy(original)):
            if "url" not in value: value["transport"]["externalLoopback"] = 1
            self.update_contract(value)
            with self.assertRaises(hubcore.HubError): self.bind()

    def test_full_handshake_schema_pin_refused_even_if_rehashed(self):
        path = self.root / runtime.ORTIE_HANDSHAKE_REL
        value = json.loads(path.read_bytes())
        value["toolsList"]["tools"][0]["inputSchema"]["additionalProperties"] = True
        data = hubcore.encoded(value); path.write_bytes(data)
        contract = self.contract()
        contract["handshake"].update(size=len(data), sha256=hubcore.sha256_hex(data))
        self.update_contract(contract)
        with self.assertRaisesRegex(hubcore.HubError, "full MCP handshake"): self.bind()


if __name__ == "__main__": unittest.main()
