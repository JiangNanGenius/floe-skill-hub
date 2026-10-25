#!/usr/bin/env python3
"""Behaviour tests for the canonical primitives, package gates, envelopes and
the signed review join. Host-level only: no network, no production secrets,
nothing executed from packages. Run: python3 -m unittest discover tests/catalog"""
import pathlib
import stat
import sys
import tempfile
import unittest
import zipfile
import io

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "scripts"))
import hubcore

FIXTURES = HERE.parents[0] / "fixtures"

GOLDEN_FILES = {
    "SKILL.md": b"---\nname: golden\ndescription: d\n---\n\nbody\n",
    "floe.json": hubcore.encoded({"schemaVersion": 1, "id": "golden", "version": "1.0.0",
                                  "capabilities": [], "tools": [], "platforms": ["ios"],
                                  "scriptRuntime": "none", "pythonPackages": []}),
    "references/NOTICE.md": b"n\n",
}
GOLDEN_CONTENT_DIGEST = "10a8732592ba018a326a357565109f13014adfa5a4e4e2fb5db1a51d33367430"
GOLDEN_ZIP_SHA = "24aed3b106d9c48bbead6a37fb5b1f22151cc641f7e62a7083d97f432326c410"
GOLDEN_ZIP_SIZE = 511


def valid_files(**overrides):
    files = dict(GOLDEN_FILES)
    files.update(overrides)
    return files


class TestCanonicalPrimitives(unittest.TestCase):
    def test_content_digest_golden(self):
        self.assertEqual(hubcore.content_digest(GOLDEN_FILES), GOLDEN_CONTENT_DIGEST)

    def test_zip_bytes_golden(self):
        data = hubcore.make_zip(GOLDEN_FILES)
        self.assertEqual(hubcore.sha256_hex(data), GOLDEN_ZIP_SHA)
        self.assertEqual(len(data), GOLDEN_ZIP_SIZE)

    def test_zip_construction_matches_legacy(self):
        data = hubcore.make_zip(GOLDEN_FILES)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for info in archive.infolist():
                self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
                self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
                self.assertEqual(info.create_system, 3)
                self.assertEqual(info.external_attr, 0o100644 << 16)
            self.assertEqual(archive.namelist(), sorted(archive.namelist()))

    def test_canonical_encoding_shape(self):
        self.assertEqual(hubcore.encoded({"b": 1, "a": {"z": [1, 2], "y": None}}),
                         b'{"a":{"y":null,"z":[1,2]},"b":1}')

    def test_rebuild_is_deterministic(self):
        self.assertEqual(hubcore.make_zip(GOLDEN_FILES), hubcore.make_zip(GOLDEN_FILES))


class TestPackageGates(unittest.TestCase):
    def test_valid_guide_package(self):
        manifest, frontmatter = hubcore.validate_package_files(GOLDEN_FILES)
        self.assertEqual(manifest["id"], "golden")

    def test_missing_skill_md(self):
        files = dict(GOLDEN_FILES)
        del files["SKILL.md"]
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_package_files(files)

    def test_missing_notice_for_upstream_source(self):
        files = dict(GOLDEN_FILES)
        del files["references/NOTICE.md"]
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_package_files(files, require_notice=True)
        hubcore.validate_package_files(files, require_notice=False)  # first-party OK

    def test_unknown_manifest_field_rejected(self):
        bad = hubcore.encoded({"schemaVersion": 1, "id": "golden", "version": "1.0.0",
                               "capabilities": [], "tools": [], "platforms": ["ios"],
                               "scriptRuntime": "none", "pythonPackages": [],
                               "trustMe": True})
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_package_files(valid_files(**{"floe.json": bad}))

    def test_unknown_capability_rejected(self):
        bad = hubcore.encoded({"schemaVersion": 1, "id": "golden", "version": "1.0.0",
                               "capabilities": ["everything.please"], "tools": [],
                               "platforms": ["ios"], "scriptRuntime": "none",
                               "pythonPackages": []})
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_package_files(valid_files(**{"floe.json": bad}))

    def test_id_mismatch_rejected(self):
        bad = hubcore.encoded({"schemaVersion": 1, "id": "other", "version": "1.0.0",
                               "capabilities": [], "tools": [], "platforms": ["ios"],
                               "scriptRuntime": "none", "pythonPackages": []})
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_package_files(valid_files(**{"floe.json": bad}))

    def test_android_platform_never_enters_manifest(self):
        # store channels are feeds; floe.json platforms stay the native enum
        bad = hubcore.encoded({"schemaVersion": 1, "id": "golden", "version": "1.0.0",
                               "capabilities": [], "tools": [], "platforms": ["android"],
                               "scriptRuntime": "none", "pythonPackages": []})
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_package_files(valid_files(**{"floe.json": bad}))

    def test_unsafe_paths_rejected(self):
        for name in ("/abs/file.txt", "../escape.txt", "references/../../x",
                     "references/x\\y", ".hidden/file.txt", "references/" + "n" * 600,
                     "scripts/run.js/../../b.py"):
            files = dict(GOLDEN_FILES)
            files[name] = b"x"
            with self.subTest(name=name):
                with self.assertRaises(hubcore.HubError):
                    hubcore.validate_package_files(files)

    def test_nfc_case_duplicate_rejected(self):
        files = dict(GOLDEN_FILES)
        files["references/caf\u00e9.txt"] = b"a"      # precomposed
        files["references/cafe\u0301.txt"] = b"b"     # decomposed
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_package_files(files)

    def test_native_payload_extensions_rejected(self):
        for name in ("assets/lib.so", "assets/x.dylib", "assets/x.wasm", "assets/x.a",
                     "assets/x.o", "agents/Foo.framework/Info.plist"):
            with self.subTest(name=name):
                with self.assertRaises(hubcore.HubError):
                    hubcore.validate_package_files(valid_files(**{name: b"payload"}))

    def test_native_magic_rejected(self):
        for magic in (b"\x7fELF\x02\x01\x01", b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe",
                      b"\x00asm\x01\x00\x00\x00"):
            with self.subTest(magic=magic):
                with self.assertRaises(hubcore.HubError):
                    hubcore.validate_package_files(valid_files(
                        **{"assets/blob.dat": magic + b"\x00" * 8}))

    def test_size_and_count_limits(self):
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_package_files(valid_files(**{"assets/big.bin": b"x" * (2_097_153)}))
        many = valid_files(**{f"references/f{i}.md": b"x" for i in range(130)})
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_package_files(many)

    def test_scripts_runtime_matrix(self):
        remote = hubcore.encoded({"schemaVersion": 1, "id": "golden", "version": "1.0.0",
                                  "capabilities": ["execution.remote"],
                                  "tools": ["exec.shell"], "platforms": ["ios"],
                                  "scriptRuntime": "remote", "pythonPackages": []})
        ok = valid_files(**{"floe.json": remote, "scripts/run.py": b"print(1)\n"})
        del ok["references/NOTICE.md"]
        hubcore.validate_package_files(ok, require_notice=False)
        with self.assertRaises(hubcore.HubError):  # runtime none + scripts
            hubcore.validate_package_files(valid_files(**{"scripts/run.py": b"x"}),
                                           require_notice=False)
        with self.assertRaises(hubcore.HubError):  # remote + disallowed extension
            hubcore.validate_package_files(valid_files(**{"floe.json": remote,
                                                          "scripts/run.txt": b"x"}),
                                           require_notice=False)
        stranded = hubcore.encoded({"schemaVersion": 1, "id": "golden", "version": "1.0.0",
                                    "capabilities": ["execution.remote"],
                                    "tools": ["exec.shell"], "platforms": ["ios"],
                                    "scriptRuntime": "remote", "pythonPackages": []})
        with self.assertRaises(hubcore.HubError):  # runtime declared, scripts empty
            hubcore.validate_package_files(valid_files(**{"floe.json": stranded}),
                                           require_notice=False)

    def test_dependency_specs_must_be_exact(self):
        remote = {"schemaVersion": 1, "id": "golden", "version": "1.0.0",
                  "capabilities": ["execution.remote"], "tools": ["exec.shell"],
                  "platforms": ["ios"], "scriptRuntime": "remote",
                  "pythonPackages": [{"spec": "pandas>=2.0", "purpose": "p",
                                      "capabilities": ["data.read"]}]}
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_package_files(valid_files(**{"floe.json": hubcore.encoded(remote),
                                                          "scripts/a.py": b"x"}),
                                           require_notice=False)
        remote["pythonPackages"] = [{"spec": "pandas==2.2.3", "purpose": "p",
                                     "capabilities": ["data.read"]}]
        hubcore.validate_package_files(valid_files(**{"floe.json": hubcore.encoded(remote),
                                                      "scripts/a.py": b"x"}),
                                       require_notice=False)

    def test_archive_rejects_symlink_and_directory_entries(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            info = zipfile.ZipInfo("references/evil")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, "/etc/passwd")
            info2 = zipfile.ZipInfo("references/")
            info2.external_attr = (stat.S_IFDIR | 0o755) << 16
            archive.writestr(info2, b"")
        with self.assertRaises(hubcore.HubError):
            hubcore.check_archive_bytes(buffer.getvalue())


class TestEnvelopes(unittest.TestCase):
    def setUp(self):
        self.keys = {hubcore.FIXTURE_KEY_ID: hubcore.fixture_public_b64()}

    def test_round_trip_and_tamper(self):
        payload = hubcore.encoded({"x": 1})
        envelope = hubcore.sign_envelope(payload, hubcore.fixture_private_key(),
                                        hubcore.FIXTURE_KEY_ID)
        self.assertEqual(hubcore.verify_envelope(payload, envelope, self.keys),
                         hubcore.FIXTURE_KEY_ID)
        with self.assertRaises(hubcore.HubError):
            hubcore.verify_envelope(payload + b" ", envelope, self.keys)

    def test_unknown_key_and_shape(self):
        payload = hubcore.encoded({"x": 1})
        envelope = hubcore.sign_envelope(payload, hubcore.fixture_private_key(),
                                        hubcore.FIXTURE_KEY_ID)
        with self.assertRaises(hubcore.HubError):
            hubcore.verify_envelope(payload, envelope, {"other-key": self.keys[hubcore.FIXTURE_KEY_ID]})
        bad = hubcore.encoded({"keyID": hubcore.FIXTURE_KEY_ID,
                               "signature": base64_of(envelope), "extra": 1})
        with self.assertRaises(hubcore.HubError):
            hubcore.verify_envelope(payload, bad, self.keys)

    def test_fixture_identity_is_never_the_production_id(self):
        self.assertNotEqual(hubcore.FIXTURE_KEY_ID, hubcore.PRODUCTION_KEY_ID)
        self.assertTrue(hubcore.FIXTURE_KEY_ID.startswith("fixture-only"))


def base64_of(envelope_bytes):
    import json
    return json.loads(envelope_bytes)["signature"]


class TestReviewJoin(unittest.TestCase):
    """The signed review must vouch for the ACTUAL per-build package/manifest."""

    def setUp(self):
        self.record = json_load(FIXTURES / "reviews" / "fixture-reviewed" / "1.0.0.review.json")
        archive = (FIXTURES / "packages" / "fixture-reviewed" / "1.0.0" /
                   "fixture-reviewed.zip").read_bytes()
        self.files = hubcore.check_archive_bytes(archive)
        self.manifest, _ = hubcore.validate_package_files(self.files)
        self.binding = {"path": "packages/fixture-reviewed/1.0.0/fixture-reviewed.zip",
                        "size": len(archive), "sha256": hubcore.sha256_hex(archive),
                        "contentDigest": hubcore.content_digest(self.files),
                        "containsScripts": True}

    def test_true_join_passes(self):
        hubcore.join_review(self.record, self.manifest, self.binding, "fixture-reviewed")

    def _mutate(self, field, value):
        import copy
        record = copy.deepcopy(self.record)
        record[field] = value
        with self.assertRaises(hubcore.HubError):
            hubcore.join_review(record, self.manifest, self.binding, "fixture-reviewed")

    def test_content_digest_drift(self):
        self._mutate("contentDigest", "0" * 64)

    def test_package_sha_drift(self):
        self._mutate("packageSha256", "0" * 64)

    def test_omitted_reviewed_tool(self):
        self._mutate("reviewedTools", [])

    def test_extra_reviewed_permission(self):
        self._mutate("reviewedCapabilities",
                     self.record["reviewedCapabilities"] + ["credentials"])

    def test_new_unreviewed_dependency(self):
        self._mutate("reviewedPythonPackages",
                     self.record["reviewedPythonPackages"] +
                     [{"spec": "numpy==1.26.4", "purpose": "p",
                       "capabilities": ["data.read"]}])

    def test_rejected_decision_cannot_bind(self):
        self._mutate("decision", "reject")

    def test_identity_drift(self):
        self._mutate("version", "1.0.1")

    def test_signature_alone_is_not_the_join(self):
        # a perfectly signed record for different bytes must still fail the join
        other = dict(self.files)
        other["scripts/extra.py"] = b"print(2)\n"
        other_binding = {"path": self.binding["path"], "size": 1,
                        "sha256": hubcore.sha256_hex(hubcore.make_zip(other)),
                        "contentDigest": hubcore.content_digest(other),
                        "containsScripts": True}
        with self.assertRaises(hubcore.HubError):
            hubcore.join_review(self.record, self.manifest, other_binding, "x")


def json_load(path):
    import json
    return json.loads(path.read_bytes())
