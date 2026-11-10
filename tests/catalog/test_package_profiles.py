#!/usr/bin/env python3
"""Signed package capacity profile tests (standard / large-source-v1).

Covers the explicit profile contract exactly as the App consumer contract
pins it (APP-CONSUMER-CONTRACT.json):
  * absent (or explicit "standard") keeps the original standard bounds and
    renders old standard objects byte-identical;
  * large-source-v1 admits bounded complete source kits (2048 files /
    64 MiB archive, 2 MiB per file unchanged);
  * unknown profiles fail closed everywhere (package gates, archive gates,
    registry rows, catalog bindings) — never a silent fallback;
  * native rejection, path/NFC/case collision, symlink and zip safety gates
    stay fully active under the large profile;
  * the registry author field packageProfile carries the selection into the
    separate same-Y signed capability feeds (catalog-large-source-v1.json),
    NEVER into the standard feeds (old strict readers reject unknown package
    keys before minimumAppVersion checks);
  * a capability feed is a complete replacement/superset of the standard
    full feed: every standard entry id present, standard rows byte-identical,
    only large entries carry package.profile;
  * transport capacity derives from the verified bound entry, never a URL;
  * upstream-update candidate gates read the trusted entry's profile.

Host-level only: no network, no production secrets, nothing executed.
Run: python3 -m unittest discover tests/catalog
"""
import base64
import copy
import hashlib
import io
import json
import pathlib
import sys
import tempfile
import unittest
import zipfile

HERE = pathlib.Path(__file__).resolve()
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import automatic_transport as at  # noqa: E402
import build_catalog  # noqa: E402
import build_packages  # noqa: E402
import catalog_views  # noqa: E402
import hubcore  # noqa: E402
import make_fixture  # noqa: E402
import upstream_updates  # noqa: E402

LARGE = "large-source-v1"
STANDARD = "standard"
MiB = 1024 * 1024

TEST_SEED = hashlib.sha256(
    b"floe-skill-hub package-profile ephemeral TEST key -- NOT production").digest()


def _key(seed):
    Ed25519PrivateKey, _, serialization, _ = hubcore._load_ed25519()
    key = Ed25519PrivateKey.from_private_bytes(seed)
    public = key.public_key().public_bytes(serialization.Encoding.Raw,
                                           serialization.PublicFormat.Raw)
    return key, base64.b64encode(public).decode()


TEST_KEY, TEST_PUB = _key(TEST_SEED)
TRUST = {hubcore.PRODUCTION_KEY_ID: TEST_PUB}


def kit_files(skill_id="large-kit", file_count=0, file_size=1, total_pad=0):
    """A valid package file set with `file_count` extra asset files."""
    files = {
        "SKILL.md": (b"---\nname: " + skill_id.encode() + b"\ndescription: d\n---\n\nbody\n"),
        "floe.json": hubcore.encoded({
            "schemaVersion": 1, "id": skill_id, "version": "1.0.0",
            "capabilities": [], "tools": [], "platforms": ["ios"],
            "scriptRuntime": "none", "pythonPackages": []}),
        "references/NOTICE.md": b"notice\n",
    }
    for index in range(file_count):
        files[f"assets/a{index:04d}.bin"] = b"\0" * file_size
    # distribute the pad in <=1 MiB chunks so no single file trips 2 MiB
    chunk = 0
    while total_pad > 0:
        step = min(total_pad, MiB)
        files[f"assets/pad{chunk:04d}.bin"] = b"\0" * step
        total_pad -= step
        chunk += 1
    return files


def _runtime():
    return {"scriptRuntime": "none", "capabilities": [], "tools": [],
            "installPlatforms": ["ios"], "pythonPackagesPlan": [],
            "execution": {"os": None, "arch": "n/a", "evidence": "unproven"}}


def _status(**overrides):
    status = {"sourcePinned": True, "licenseChecked": True, "adaptation": "frozen",
              "packaged": True, "reviewed": False, "qualified": False,
              "published": False, "executionVerified": False}
    status.update(overrides)
    return status


def registry_entry(id_, plan, **overrides):
    entry = {
        "id": id_, "planNumber": plan, "kind": "optional", "source": "A",
        "name": {"en": id_, "zh-Hans": id_},
        "description": {"en": "t", "zh-Hans": "t"},
        "category": hubcore.CATEGORIES[0], "tags": ["test", "fixture"],
        "deepAdaptation": False,
        "upstream": {"repository": "https://github.com/someone/something",
                     "commit": "a" * 40, "path": "skills/" + id_,
                     "skillManifestPath": "skills/" + id_ + "/SKILL.md",
                     "retrievedAt": "2026-11-10",
                     "licenseStatus": "pending-per-item-audit",
                     "licenseEvidencePath": "", "repositoryLicense": "MIT",
                     "licenseNote": {"en": "n", "zh-Hans": "n"}},
        "firstParty": None, "plannedRuntime": _runtime(),
        "versionTarget": "1.0.0", "minimumAppVersion": None,
        "status": _status(), "notes": {"en": "", "zh-Hans": ""},
    }
    entry.update(overrides)
    return entry


def registry_with(entries):
    return {
        "schemaVersion": hubcore.REGISTRY_SCHEMA_VERSION, "registry": "candidate",
        "publisher": "JiangNanGenius",
        "hub": {"repository": "JiangNanGenius/floe-skill-hub",
                "channelRoots": {"ios": ".", "android": "android"}},
        "categories": [{"id": c, "name": {"en": c, "zh-Hans": c}}
                       for c in hubcore.CATEGORIES],
        "notes": {"en": "fixture", "zh-Hans": "fixture"},
        "skills": entries,
    }


class TestProfileBounds(unittest.TestCase):
    def test_absent_means_standard(self):
        self.assertIs(hubcore.package_profile_bounds(None),
                      hubcore.PACKAGE_PROFILES[STANDARD])
        self.assertIs(hubcore.package_profile_bounds(STANDARD),
                      hubcore.PACKAGE_PROFILES[STANDARD])

    def test_large_source_v1_capacity(self):
        bounds = hubcore.package_profile_bounds(LARGE)
        self.assertEqual(bounds["maxFiles"], 2048)
        self.assertEqual(bounds["maxTotalBytes"], 64 * MiB)
        self.assertEqual(bounds["maxFileBytes"], 2 * MiB)

    def test_standard_capacity_unchanged(self):
        bounds = hubcore.package_profile_bounds(STANDARD)
        self.assertEqual(bounds, {"maxFiles": 128, "maxTotalBytes": 8 * MiB,
                                  "maxFileBytes": 2 * MiB})
        self.assertEqual(hubcore.MAX_PACKAGE_FILES, 128)
        self.assertEqual(hubcore.MAX_TOTAL_BYTES, 8 * MiB)
        self.assertEqual(hubcore.MAX_FILE_BYTES, 2 * MiB)

    def test_unknown_profile_fails_closed(self):
        for bad in ("huge-v1", "", 1, True, ["large-source-v1"]):
            with self.assertRaises(hubcore.HubError, msg=repr(bad)):
                hubcore.package_profile_bounds(bad)

    def test_ceiling_is_largest_profile(self):
        self.assertEqual(hubcore.MAX_PROFILE_TOTAL_BYTES, 64 * MiB)


class TestPackageGateProfiles(unittest.TestCase):
    def test_standard_default_file_count_unchanged(self):
        hubcore.validate_package_files(kit_files(file_count=125))  # 128 total
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_package_files(kit_files(file_count=126))  # 129

    def test_explicit_standard_matches_default(self):
        hubcore.validate_package_files(kit_files(file_count=125), profile=STANDARD)
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_package_files(kit_files(file_count=126), profile=STANDARD)

    def test_standard_total_bytes_unchanged(self):
        used = sum(len(d) for d in kit_files().values())
        pad = 8 * MiB - used
        hubcore.validate_package_files(kit_files(total_pad=pad))
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_package_files(kit_files(total_pad=pad + 1))

    def test_large_accepts_beyond_standard_total(self):
        files = kit_files(file_count=8, file_size=MiB)  # ~8 MiB + manifest bytes
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_package_files(files)
        hubcore.validate_package_files(files, profile=LARGE)

    def test_large_file_count_boundary(self):
        hubcore.validate_package_files(kit_files(file_count=2045), profile=LARGE)  # 2048
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_package_files(kit_files(file_count=2046), profile=LARGE)

    def test_large_total_boundary(self):
        used = sum(len(d) for d in kit_files().values())
        pad = 64 * MiB - used
        hubcore.validate_package_files(kit_files(total_pad=pad), profile=LARGE)
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_package_files(kit_files(total_pad=pad + 1), profile=LARGE)

    def test_per_file_two_mib_enforced_under_large(self):
        hubcore.validate_package_files(kit_files(file_count=1, file_size=2 * MiB),
                                       profile=LARGE)
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_package_files(kit_files(file_count=1, file_size=2 * MiB + 1),
                                           profile=LARGE)

    def test_unknown_profile_refused_at_package_gate(self):
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_package_files(kit_files(), profile="huge-v1")

    def test_native_rejection_stays_active_under_large(self):
        files = kit_files()
        files["assets/payload.so"] = b"\x7fELF" + b"\0" * 32
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_package_files(files, profile=LARGE)

    def test_nfc_case_collision_stays_active_under_large(self):
        files = kit_files()
        files["assets/Readme.TXT"] = b"x"
        files["assets/readme.txt"] = b"y"
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_package_files(files, profile=LARGE)


class TestArchiveGateProfiles(unittest.TestCase):
    def test_large_archive_roundtrip(self):
        files = kit_files(file_count=8, file_size=MiB)
        data = hubcore.make_zip(files)
        unpacked = hubcore.check_archive_bytes(data, profile=LARGE)
        self.assertEqual(unpacked, files)

    def test_standard_archive_refuses_large_kit(self):
        data = hubcore.make_zip(kit_files(file_count=8, file_size=MiB))
        with self.assertRaises(hubcore.HubError):
            hubcore.check_archive_bytes(data)

    def test_unknown_profile_refused_at_archive_gate(self):
        data = hubcore.make_zip(kit_files())
        with self.assertRaises(hubcore.HubError):
            hubcore.check_archive_bytes(data, profile="huge-v1")

    def test_archive_byte_boundary_mechanics(self):
        # A tiny injected profile proves the archive-level compressed bound is
        # parameterized by the declared profile (not hardcoded to 8 MiB).
        tiny = {"maxFiles": 2048, "maxTotalBytes": 1024, "maxFileBytes": 2 * MiB}
        saved = hubcore.PACKAGE_PROFILES.get("tiny-test-v1")
        hubcore.PACKAGE_PROFILES["tiny-test-v1"] = tiny
        try:
            data = hubcore.make_zip(kit_files(file_count=2, file_size=400))
            self.assertGreater(len(data), 1024)
            with self.assertRaises(hubcore.HubError):
                hubcore.check_archive_bytes(data, profile="tiny-test-v1")
            accepted = hubcore.check_archive_bytes(
                hubcore.make_zip(kit_files()), profile="tiny-test-v1")
            self.assertIn("SKILL.md", accepted)
        finally:
            if saved is None:
                del hubcore.PACKAGE_PROFILES["tiny-test-v1"]
            else:
                hubcore.PACKAGE_PROFILES["tiny-test-v1"] = saved

    def test_symlink_refused_under_large(self):
        buf = io.BytesIO()
        files = kit_files()
        with zipfile.ZipFile(buf, "w") as archive:
            for rel, data in sorted(files.items()):
                info = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data)
            info = zipfile.ZipInfo("assets/link", date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o120000 << 16
            archive.writestr(info, b"target")
        with self.assertRaises(hubcore.HubError):
            hubcore.check_archive_bytes(buf.getvalue(), profile=LARGE)

    def test_directory_entry_refused_under_large(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            archive.writestr(zipfile.ZipInfo("assets/"), b"")
        with self.assertRaises(hubcore.HubError):
            hubcore.check_archive_bytes(buf.getvalue(), profile=LARGE)

    @staticmethod
    def _deflated_zip(total_declared_mib, per_file_mib=2):
        """Highly-compressible valid kit: declared total >> compressed bytes."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
            for rel, data in sorted(kit_files().items()):
                archive.writestr(rel, data)
            index = 0
            remaining = total_declared_mib * MiB
            while remaining > 0:
                step = min(remaining, per_file_mib * MiB)
                archive.writestr(f"assets/z{index:03d}.bin", b"\0" * step)
                remaining -= step
                index += 1
        return buf.getvalue()

    def test_declared_running_total_bound(self):
        # declared 80 MiB total (compressed tiny): refused under the large
        # profile's 64 MiB bound before any payload allocation matters
        data = self._deflated_zip(80)
        self.assertLess(len(data), MiB)
        with self.assertRaises(hubcore.HubError):
            hubcore.check_archive_bytes(data, require_notice=False, profile=LARGE)
        # declared 10 MiB total refused under the standard bound
        data = self._deflated_zip(10)
        with self.assertRaises(hubcore.HubError):
            hubcore.check_archive_bytes(data, require_notice=False)
        hubcore.check_archive_bytes(data, require_notice=False, profile=LARGE)

    def test_central_directory_count_bound(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
            for index in range(2049):
                archive.writestr(f"assets/c{index:04d}.bin", b"")
        data = buf.getvalue()
        self.assertLess(len(data), MiB)
        with self.assertRaises(hubcore.HubError):
            hubcore.check_archive_bytes(data, require_notice=False, profile=LARGE)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
            for index in range(128 + 1):
                archive.writestr(f"assets/c{index:04d}.bin", b"")
        with self.assertRaises(hubcore.HubError):
            hubcore.check_archive_bytes(buf.getvalue(), require_notice=False)


class TestRegistryProfileField(unittest.TestCase):
    def test_absent_and_declared_profiles_validate(self):
        entries = [registry_entry("profile-a", 1),
                   registry_entry("profile-b", 2, packageProfile=LARGE)]
        hubcore.validate_registry(registry_with(entries), expect_counts=(2, 0, 2, 0))

    def test_explicit_standard_profile_validates(self):
        entries = [registry_entry("profile-a", 1, packageProfile=STANDARD)]
        hubcore.validate_registry(registry_with(entries), expect_counts=(1, 0, 1, 0))

    def test_unknown_profile_refused(self):
        entries = [registry_entry("profile-a", 1, packageProfile="huge-v1")]
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_registry(registry_with(entries), expect_counts=(1, 0, 1, 0))

    def test_non_string_profile_refused(self):
        entries = [registry_entry("profile-a", 1, packageProfile=1)]
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_registry(registry_with(entries), expect_counts=(1, 0, 1, 0))

    def test_present_null_profile_refused(self):
        # strict key-presence string decode: only MISSING means standard
        entries = [registry_entry("profile-a", 1, packageProfile=None)]
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_registry(registry_with(entries), expect_counts=(1, 0, 1, 0))
        entries = [registry_entry("profile-a", 1)]
        hubcore.validate_registry(registry_with(entries), expect_counts=(1, 0, 1, 0))

    def test_unknown_sibling_field_still_refused(self):
        entries = [registry_entry("profile-a", 1, packageProfileExtra=True)]
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_registry(registry_with(entries), expect_counts=(1, 0, 1, 0))

    def test_missing_required_field_still_refused(self):
        entry = registry_entry("profile-a", 1)
        del entry["notes"]
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_registry(registry_with([entry]), expect_counts=(1, 0, 1, 0))


class TestBindingAndCatalogProfile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="floe-profile-test-")
        self.root = pathlib.Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def _stage(self, skill_id, files, profile=None):
        entry = registry_entry(
            skill_id, 1, minimumAppVersion="1.7.0",
            status=_status(packaged=True),
            **({"packageProfile": profile} if profile is not None else {}))
        for rel, data in files.items():
            target = self.root / "sources" / skill_id / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        return entry

    def _bind(self, entry, files, emit_profile=False):
        data = hubcore.make_zip(files)
        rel = hubcore.package_path_for(entry["id"], entry["versionTarget"], "ios")
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        bindings, manifest, _ = build_catalog.bind_package(
            entry, self.root, emit_profile=emit_profile)
        return bindings["ios"], data

    def _fixture_feed(self, entry, binding, capability=False):
        catalog_entry = hubcore.catalog_entry(entry, package=binding)
        feed = hubcore.build_catalog(registry_with([entry]), "ios", "fixture",
                                     [catalog_entry], None)
        return feed

    def test_absent_profile_renders_old_binding_bytes(self):
        files = kit_files("plain-kit")
        entry = self._stage("plain-kit", files)
        binding, _ = self._bind(entry, files)
        self.assertEqual(set(binding),
                         {"path", "size", "sha256", "contentDigest", "containsScripts"})
        binding2, _ = self._bind(entry, files, emit_profile=True)
        self.assertEqual(binding, binding2)  # standard rows never carry profile

    def test_explicit_standard_never_emitted(self):
        files = kit_files("plain-kit")
        entry = self._stage("plain-kit", files, profile=STANDARD)
        binding, _ = self._bind(entry, files, emit_profile=True)
        self.assertNotIn("profile", binding)

    def test_large_profile_rendered_only_for_capability(self):
        files = kit_files("large-kit", file_count=8, file_size=MiB)
        entry = self._stage("large-kit", files, profile=LARGE)
        standard_binding, data = self._bind(entry, files)
        self.assertNotIn("profile", standard_binding)
        capability_binding, _ = self._bind(entry, files, emit_profile=True)
        self.assertEqual(capability_binding["profile"], LARGE)
        self.assertEqual(capability_binding["size"], len(data))

    def test_standard_feed_rejects_profile_key(self):
        files = kit_files("plain-kit")
        entry = self._stage("plain-kit", files)
        binding, _ = self._bind(entry, files)
        binding = dict(binding, profile=LARGE)
        feed = self._fixture_feed(entry, binding)
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_catalog(feed, channel="ios", allow_fixture=True)

    def test_capability_feed_accepts_profile_and_boundaries(self):
        files = kit_files("large-kit", file_count=8, file_size=MiB)
        entry = self._stage("large-kit", files, profile=LARGE)
        binding, _ = self._bind(entry, files, emit_profile=True)
        feed = self._fixture_feed(entry, binding)
        hubcore.validate_catalog(feed, channel="ios", allow_fixture=True,
                                 capability=True)
        over = dict(binding, size=hubcore.MAX_PROFILE_TOTAL_BYTES + 1)
        feed_over = self._fixture_feed(entry, over)
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_catalog(feed_over, channel="ios", allow_fixture=True,
                                     capability=True)

    def test_capability_feed_rejects_unknown_profile(self):
        files = kit_files("plain-kit")
        entry = self._stage("plain-kit", files)
        binding, _ = self._bind(entry, files)
        binding = dict(binding, profile="huge-v1")
        feed = self._fixture_feed(entry, binding)
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_catalog(feed, channel="ios", allow_fixture=True,
                                     capability=True)

    def test_capability_feed_rejects_present_null_profile(self):
        # strict key-presence string decode: only MISSING means standard
        files = kit_files("plain-kit")
        entry = self._stage("plain-kit", files)
        binding, _ = self._bind(entry, files)
        binding = dict(binding, profile=None)
        feed = self._fixture_feed(entry, binding)
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_catalog(feed, channel="ios", allow_fixture=True,
                                     capability=True)
        feed = self._fixture_feed(entry, {k: v for k, v in binding.items()
                                          if k != "profile"})
        hubcore.validate_catalog(feed, channel="ios", allow_fixture=True,
                                 capability=True)

    def test_capability_projection_rules(self):
        files = kit_files("plain-kit")
        entry = self._stage("plain-kit", files)
        binding, _ = self._bind(entry, files)
        row = hubcore.catalog_entry(entry, package=binding)
        standard_full = hubcore.build_catalog(registry_with([entry]), "ios", "fixture",
                                              [row], None)
        # identical feed validates as its own superset
        self.assertTrue(hubcore.validate_capability_projection(standard_full,
                                                               standard_full))
        large_entry = self._stage("large-kit", kit_files("large-kit"), profile=LARGE)
        large_row = hubcore.catalog_entry(large_entry, package=None)
        # a capability feed missing a standard id fails
        missing = hubcore.build_catalog(registry_with([large_entry]), "ios", "fixture",
                                        [large_row], None)
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_capability_projection(missing, standard_full)
        # a drifted standard row fails
        capability = hubcore.build_catalog(registry_with([entry, large_entry]),
                                           "ios", "fixture", [row, large_row], None)
        drifted = json.loads(hubcore.encoded(capability))
        drifted["entries"][0] = dict(drifted["entries"][0], planNumber=99)
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_capability_projection(drifted, standard_full)
        # channel mismatch fails
        foreign = hubcore.build_catalog(registry_with([entry]), "android", "fixture",
                                        [hubcore.catalog_entry(
                                            dict(entry, plannedRuntime=dict(
                                                entry["plannedRuntime"],
                                                installPlatforms=["android"])),
                                            package=dict(binding, path="android/"
                                                         + binding["path"]))], None)
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_capability_projection(foreign, standard_full)

    def test_committed_fixture_feed_bytes_unchanged(self):
        fixture = json.loads(
            (ROOT / "tests" / "catalog" / "fixtures" / "catalog.json").read_bytes())
        hubcore.validate_catalog(fixture, channel="ios", allow_fixture=True)
        for entry in fixture["entries"]:
            if entry["package"] is not None:
                self.assertNotIn("profile", entry["package"])


class TestBuildPackagesProfile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="floe-profile-build-")
        self.root = pathlib.Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def _stage(self, skill_id, files):
        for rel, data in files.items():
            target = self.root / "sources" / skill_id / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)

    def test_large_staged_source_builds_with_profile(self):
        files = kit_files("large-kit", file_count=8, file_size=MiB)
        self._stage("large-kit", files)
        entry = registry_entry("large-kit", 1, packageProfile=LARGE)
        written = build_packages.build_one("large-kit", entry, check=False, root=self.root)
        self.assertTrue(written)
        archive = self.root / written[0]
        unpacked = hubcore.check_archive_bytes(archive.read_bytes(), profile=LARGE)
        self.assertEqual(unpacked, files)

    def test_same_staged_source_refused_without_profile(self):
        files = kit_files("large-kit", file_count=8, file_size=MiB)
        self._stage("large-kit", files)
        entry = registry_entry("large-kit", 1)
        with self.assertRaises(hubcore.HubError):
            build_packages.build_one("large-kit", entry, check=True, root=self.root)


class TestOldBytesUnchanged(unittest.TestCase):
    def test_committed_fixtures_still_rebuild_byte_identical(self):
        outputs = make_fixture.build_outputs()
        make_fixture.verify(outputs)
        for name, data in outputs.items():
            committed = ROOT / "tests" / "catalog" / "fixtures" / name
            self.assertEqual(committed.read_bytes(), data, name)

    def test_golden_digests_unchanged(self):
        # Published golden constants from test_package_gates.py: the profile
        # work must not perturb the canonical bytes.
        golden_content_digest = ("10a8732592ba018a326a357565109f13014adfa5a4e4e2fb5"
                                 "db1a51d33367430")
        golden_zip_sha = ("24aed3b106d9c48bbead6a37fb5b1f22151cc641f7e62a7083"
                          "d97f432326c410")
        files = {
            "SKILL.md": b"---\nname: golden\ndescription: d\n---\n\nbody\n",
            "floe.json": hubcore.encoded({"schemaVersion": 1, "id": "golden",
                                          "version": "1.0.0", "capabilities": [],
                                          "tools": [], "platforms": ["ios"],
                                          "scriptRuntime": "none", "pythonPackages": []}),
            "references/NOTICE.md": b"n\n",
        }
        self.assertEqual(hubcore.content_digest(files), golden_content_digest)
        self.assertEqual(hubcore.sha256_hex(hubcore.make_zip(files)), golden_zip_sha)


class TestRelayCapacityDerivation(unittest.TestCase):
    """Transport capacity derives from the verified bound entry only.

    Large-source entries travel ONLY in the same-Y signed capability feeds
    (declared atomically for both channels); the standard feeds stay
    profile-free.
    """

    X_COMMIT = "b" * 40
    B_COMMIT = "c" * 40
    POLICY = "d" * 64

    def _feed_entry(self, id_, channel="ios", plan=1, size=4, profile=None,
                    qualified=False):
        package = {
            "path": hubcore.package_path_for(id_, "1.0.0", channel),
            "size": size, "sha256": hashlib.sha256(b"zip-" + id_.encode()).hexdigest(),
            "contentDigest": hashlib.sha256(b"cd-" + id_.encode()).hexdigest(),
            "containsScripts": False,
        }
        if profile is not None:
            package["profile"] = profile
        return {
            "id": id_, "planNumber": plan, "kind": "optional", "source": "A",
            "name": {"en": id_, "zh-Hans": id_},
            "description": {"en": "t", "zh-Hans": "t"},
            "category": hubcore.CATEGORIES[0], "tags": ["test", "fixture"],
            "deepAdaptation": False, "upstream": None, "firstParty": None,
            "runtime": {"scriptRuntime": "none", "capabilities": [], "tools": [],
                        "installPlatforms": [channel], "pythonPackagesPlan": [],
                        "execution": {"os": None, "arch": "n/a", "evidence": "unproven"}},
            "version": "1.0.0", "minimumAppVersion": "1.7.0",
            "status": {"sourcePinned": True, "licenseChecked": True,
                       "adaptation": "frozen", "packaged": True,
                       "reviewed": False, "qualified": qualified,
                       "published": True, "executionVerified": False},
            "notes": {"en": "", "zh-Hans": ""},
            "package": package, "review": None, "installOffer": "none",
        }

    def _production_feed(self, channel, entries):
        rows = sorted(entries, key=lambda e: e["planNumber"])
        feed = hubcore.build_catalog({}, channel, "production", rows, self.X_COMMIT)
        return hubcore.encoded(feed)

    def _sign(self, payload):
        return hubcore.sign_envelope(payload, TEST_KEY, hubcore.PRODUCTION_KEY_ID)

    def build_capability_relay(self, mutate_capability=None,
                               declare_capability=True):
        """Complete publication relay: standard 4 views + both capability feeds."""
        files = {}
        feeds = {}
        ios_standard = [self._feed_entry("alpha-guide", "ios", plan=1),
                        self._feed_entry("gamma-guide", "ios", plan=3)]
        android_standard = [self._feed_entry("beta-guide", "android", plan=2)]
        large_size = 60_000_000  # beyond standard 8 MiB, within 64 MiB
        ios_large = self._feed_entry("alpha-large", "ios", plan=4, size=large_size,
                                     profile=LARGE)
        for view in catalog_views.VIEWS:
            channel = catalog_views.channel_for(view)
            entries = ios_standard if channel == "ios" else android_standard
            body = self._production_feed(channel, entries)
            feeds[catalog_views.FEED_PATHS[view][0]] = body
        # capability feeds: superset of the FULL views at the same Y
        ios_capability = self._production_feed("ios", ios_standard + [ios_large])
        android_capability = self._production_feed("android", android_standard)
        if mutate_capability is not None:
            doc = json.loads(ios_capability)
            mutate_capability(doc)
            ios_capability = hubcore.encoded(doc)
        feeds[catalog_views.FEED_PATHS["ios-large-source-v1"][0]] = ios_capability
        feeds[catalog_views.FEED_PATHS["android-large-source-v1"][0]] = android_capability
        for rel, body in feeds.items():
            files[rel] = body
            files[rel[: -len(".json")] + ".sig"] = self._sign(body)
        package_outputs = [{
            "path": ios_large["package"]["path"],
            "sha256": ios_large["package"]["sha256"],
            "size": ios_large["package"]["size"],
        }]
        declared = sorted(feeds) if declare_capability else sorted(
            rel for rel in feeds if "large-source" not in rel)
        receipt = {"schemaVersion": 1, "mode": "catalog",
                   "hubRepository": "JiangNanGenius/floe-skill-hub",
                   "sourceCommit": self.X_COMMIT,
                   "keyID": hubcore.PRODUCTION_KEY_ID,
                   "signedFeeds": declared,
                   "outputs": ([{"path": rel, "sha256": hubcore.sha256_hex(data),
                                  "size": len(data)}
                                 for rel, data in sorted(files.items())]
                               + package_outputs)}
        receipt_bytes = hubcore.encoded(receipt)
        files[at.RELAY_RECEIPT_REL] = receipt_bytes
        files[at.RELAY_RECEIPT_SIG_REL] = self._sign(receipt_bytes)
        request = at.build_request("catalog", self.X_COMMIT, self.B_COMMIT,
                                   self.POLICY)[1]
        return files, request

    def test_capability_relay_validates(self):
        files, request = self.build_capability_relay()
        verdict = at.validate_signed_relay(files, request, TRUST)
        self.assertEqual(verdict["status"], "relay-ok")
        large_refs = [r for r in verdict["packageReferences"]
                      if r["id"] == "alpha-large"]
        self.assertEqual(len(large_refs), 1)
        self.assertEqual(large_refs[0]["size"], 60_000_000)
        self.assertIn("ios-large-source-v1", verdict["feeds"])
        self.assertIn("android-large-source-v1", verdict["feeds"])

    def test_standard_feed_with_profile_refused(self):
        files, request = self.build_capability_relay()

        def poison(feed):
            feed["entries"][0]["package"]["profile"] = LARGE
        # poison the ios FULL feed directly
        for view in ("ios-full",):
            rel = catalog_views.FEED_PATHS[view][0]
            doc = json.loads(files[rel])
            poison(doc)
            files[rel] = hubcore.encoded(doc)
            files[rel[: -len(".json")] + ".sig"] = self._sign(files[rel])
        with self.assertRaises(at.TransportError):
            at.validate_signed_relay(files, request, TRUST)

    def test_capability_missing_standard_id_refused(self):
        def drop_row(feed):
            feed["entries"] = [e for e in feed["entries"]
                               if e["id"] != "gamma-guide"]
            # keep counts consistent so only the projection rule can fire
            feed["counts"]["total"] = len(feed["entries"])
        files, request = self.build_capability_relay(mutate_capability=drop_row)
        with self.assertRaises(at.TransportError):
            at.validate_signed_relay(files, request, TRUST)

    def test_capability_not_atomic_refused(self):
        files, request = self.build_capability_relay(declare_capability=False)
        with self.assertRaises(at.TransportError):
            at.validate_signed_relay(files, request, TRUST)

    def test_receipt_output_shape_bound(self):
        receipt = {"outputs": [
            {"path": "packages/x/1.0.0/x.zip", "sha256": "a" * 64,
             "size": hubcore.MAX_PROFILE_TOTAL_BYTES + 1},
        ]}
        with self.assertRaises(at.TransportError):
            at._receipt_outputs(receipt)
        ok = at._receipt_outputs({"outputs": [
            {"path": "packages/x/1.0.0/x.zip", "sha256": "a" * 64,
             "size": hubcore.MAX_PROFILE_TOTAL_BYTES}]})
        self.assertIn("packages/x/1.0.0/x.zip", ok)
        with self.assertRaises(at.TransportError):
            at._receipt_outputs({"outputs": [
                {"path": "catalog.json", "sha256": "a" * 64,
                 "size": hubcore.MAX_TOTAL_BYTES + 1}]})


class TestCapabilityFeedBuild(unittest.TestCase):
    """build_catalog emits same-Y capability feeds; standard feeds stay clean."""

    def setUp(self):
        self.registry = json.loads((ROOT / "catalog/skills.json").read_bytes())
        self.registry["skills"] = [row for row in self.registry["skills"]
                                   if row["planNumber"] <= 43]

    def _build(self):
        hubcore.validate_registry(self.registry)
        return build_catalog.build(self.registry, "preview", "a" * 40,
                                   ROOT, ROOT, build_catalog.load_trust(ROOT))

    def _add_large_row(self):
        row = next(r for r in self.registry["skills"] if r["id"] == "meetings")
        row["packageProfile"] = LARGE
        return row

    def test_no_large_rows_means_no_capability_feeds(self):
        out = self._build()
        self.assertEqual(sorted(out), [
            "android/catalog-full.json", "android/catalog.json",
            "catalog-full.json", "catalog.json"])
        for prefix in ("", "android/"):
            feed = json.loads(out[prefix + "catalog-full.json"])
            for entry in feed["entries"]:
                if entry["package"] is not None:
                    self.assertNotIn("profile", entry["package"])

    def test_large_row_excluded_from_standard_feeds(self):
        self._add_large_row()
        out = self._build()
        self.assertEqual(set(out), {
            "android/catalog-large-source-v1.json",
            "android/catalog-full.json", "android/catalog.json",
            "catalog-large-source-v1.json", "catalog-full.json", "catalog.json"})
        for prefix in ("", "android/"):
            standard = json.loads(out[prefix + "catalog-full.json"])
            self.assertNotIn("meetings", {e["id"] for e in standard["entries"]})
            for entry in standard["entries"]:
                if entry["package"] is not None:
                    self.assertNotIn("profile", entry["package"])

    def test_capability_feed_is_exact_superset(self):
        self._add_large_row()
        out = self._build()
        for prefix in ("", "android/"):
            standard_full = json.loads(out[prefix + "catalog-full.json"])
            capability = json.loads(out[prefix + "catalog-large-source-v1.json"])
            hubcore.validate_catalog(capability, channel=standard_full["channel"],
                                     capability=True)
            hubcore.validate_capability_projection(capability, standard_full)
            by_id = {e["id"]: e for e in capability["entries"]}
            # the large row installs on both channels: it appears in BOTH
            # capability feeds and in neither standard feed
            large_row = by_id.get("meetings")
            self.assertIsNotNone(large_row)
            self.assertEqual(large_row["package"]["profile"], LARGE)
            for entry in capability["entries"]:
                if entry["id"] != "meetings" and entry["package"] is not None:
                    self.assertNotIn("profile", entry["package"])


class TestUpstreamProfilePropagation(unittest.TestCase):
    """Trusted-entry profile drives the update candidate gates."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="floe-profile-upstream-")
        self.root = pathlib.Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_standard_default_unchanged(self):
        candidate = kit_files("some-skill", file_count=8, file_size=MiB)
        entry = registry_entry("some-skill", 1)
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_package_files(dict(candidate), require_notice=True,
                                           profile=entry.get("packageProfile"))

    def test_opted_large_update_allowed(self):
        candidate = kit_files("some-skill", file_count=8, file_size=MiB)
        entry = registry_entry("some-skill", 1, packageProfile=LARGE)
        hubcore.validate_package_files(dict(candidate), require_notice=True,
                                       profile=entry.get("packageProfile"))

    def test_unknown_profile_rejected(self):
        candidate = kit_files("some-skill")
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_package_files(dict(candidate), require_notice=True,
                                           profile="huge-v1")

    def test_published_digests_reader_uses_profile(self):
        files = kit_files("large-kit", file_count=8, file_size=MiB)
        data = hubcore.make_zip(files)
        archive = self.root / "packages" / "large-kit" / "1.0.0" / "large-kit.zip"
        archive.parent.mkdir(parents=True)
        archive.write_bytes(data)
        self.assertEqual(upstream_updates._published_digests(self.root, "large-kit"),
                         set())
        digests = upstream_updates._published_digests(self.root, "large-kit",
                                                      profile=LARGE)
        self.assertEqual(digests, {hubcore.content_digest(files)})


class TestScanSideStaging(unittest.TestCase):
    """Scan-side package staging uses the trusted-entry-derived capacity."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="floe-profile-staging-")
        self.root = pathlib.Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        import automatic_publication as ap
        self.ap = ap

    def test_capacity_derives_only_from_validated_entry(self):
        cap = self.ap._package_write_capacity
        self.assertEqual(cap("packages/abc/1.0.0/abc.zip", {}), 8 * MiB)
        self.assertEqual(cap("packages/abc/1.0.0/abc.zip", {"abc": LARGE}), 64 * MiB)
        self.assertEqual(cap("android/packages/abc/2.0.0/abc.zip", {"abc": LARGE}),
                         64 * MiB)
        # non-package members keep the standard payload ceiling
        self.assertEqual(cap("catalog/skills.json", {"abc": LARGE}), 8 * MiB)
        self.assertEqual(cap("reviews/abc/1.0.0.review.json", {"abc": LARGE}),
                         8 * MiB)
        # an unrelated id never inherits capacity
        self.assertEqual(cap("packages/other/1.0.0/other.zip", {"abc": LARGE}),
                         8 * MiB)

    def test_capacity_unknown_profile_fails_closed(self):
        with self.assertRaises(hubcore.HubError):
            self.ap._package_write_capacity("packages/abc/1.0.0/abc.zip",
                                            {"abc": "huge-v1"})

    def test_write_payload_file_member_bound(self):
        out = self.root / "out"
        self.ap.write_payload_file(out, "catalog/skills.json", b"x" * (8 * MiB),
                                   max_bytes=8 * MiB)
        with self.assertRaises(self.ap.PublicationError):
            self.ap.write_payload_file(out, "catalog/skills.json",
                                       b"x" * (8 * MiB + 1), max_bytes=8 * MiB)
        # a large package write succeeds only with the derived large capacity
        self.ap.write_payload_file(out, "packages/abc/1.0.0/abc.zip",
                                   b"x" * (30 * MiB), max_bytes=64 * MiB)
        with self.assertRaises(self.ap.PublicationError):
            self.ap.write_payload_file(out, "packages/abc/1.0.0/abc.zip",
                                       b"x" * (64 * MiB + 1), max_bytes=64 * MiB)

    def test_default_payload_ceiling_unchanged(self):
        out = self.root / "out"
        self.ap.write_payload_file(out, "catalog/skills.json", b"x" * (8 * MiB))
        with self.assertRaises(self.ap.PublicationError):
            self.ap.write_payload_file(out, "catalog/skills.json",
                                       b"x" * (8 * MiB + 1))


if __name__ == "__main__":
    unittest.main()
