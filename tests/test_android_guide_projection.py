#!/usr/bin/env python3
"""Focused contract tests for the Android portable-guide floor projection
in scripts/build_catalog.py (job-771d6808af6d4aea, finalized under Root's
integration decision in job-f3a69ac4223e425f, both 2026-10-28).

These tests pin the SERVER-side projection contract exactly as Root decided:

  * the projection encodes "no SDK-specific content floor" as the VALID
    string sentinel "0.0.0" — never null: the unchanged hubcore.validate_catalog
    clause "packaged entries require minimumAppVersion" and the published
    schema must accept the FINAL projected bytes as-is, with no validator,
    schema or native-client change;
  * only an id inside the frozen ANDROID_PORTABLE_GUIDE_IDS literal set may
    ever project, and only when the ACTUAL bound frozen package manifest and
    review prove portable instruction-only content (linux declared, script
    runtime "none", no tools, no pythonPackages, capabilities inside
    {workspace.read, workspace.write}, static-content-reviewed with the empty
    unproven execution claim);
  * an entry already carrying the sentinel is never re-projected (the helper
    returns None over its own output);
  * the iOS feed entry always keeps the registry floor;
  * pre-Linux payloads (an ios-only manifest — every currently published
    package) keep the floor on BOTH channels, and the full current B release
    feeds rebuild byte-identical with this code (frozen git archive of the
    audited X=2d131b2e..., compared against the 3e145cd6 published bytes);
  * scripted shapes, non-empty tools/pythonPackages, non-basic capabilities,
    unknown ids and missing package/review bindings refuse the waiver and
    retain the floor; a guest/claimed execution review or a wrong review
    stage fails the UNCHANGED bind/join gates closed — the release itself
    refuses, no partial waiver is ever emitted;
  * the projection helper is pure: it never mutates the validated feed and is
    deterministic over the same frozen bytes.

Fixtures are coherent synthetic payloads derived from the REAL immutable-B
registry row shapes (the "copywriting" guide row), signed with an ephemeral
per-run isolated key — never the fixture identity, never a trust root, never
production material. Production data is touched READ-ONLY.

Run (PYTHONDONTWRITEBYTECODE / sys.dont_write_bytecode keeps the tree clean):
    python3 tests/test_android_guide_projection.py
"""
import base64
import copy
import datetime
import json
import pathlib
import subprocess
import sys
import tarfile
import tempfile
import unittest

sys.dont_write_bytecode = True

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "scripts"))

import build_catalog  # noqa: E402
import hubcore  # noqa: E402

X_COMMIT = "2d131b2e7c4263647624e44cb19e0cf0151c3c58"
BASE_COMMIT = "3e145cd6cb04b4c36476c3e59a7495e7fad80c64"
GUIDE_ID = "copywriting"
GUIDE_FLOOR = "1.7.59"
NEW_VERSION = "1.0.1"
TEST_KEY_ID = "projection-test-only-2026-10"  # ephemeral; not fixture, not trust
GUIDE_EXECUTION = {"os": None, "arch": "n/a", "evidence": "unproven"}
SENTINEL = build_catalog.ANDROID_PORTABLE_GUIDE_CONTENT_FLOOR  # "0.0.0"
CATALOG_SCHEMA = REPO / "schema" / "catalog.schema.json"


def _today():
    return datetime.date.today().isoformat()


def _base_entry(root_id):
    """A real immutable-B registry row (read-only) shaped honestly."""
    registry = json.loads((REPO / "catalog" / "skills.json").read_bytes())
    for row in registry["skills"]:
        if row["id"] == root_id:
            return copy.deepcopy(row)
    raise AssertionError(f"registry row {root_id} missing from the checked-in registry")


def rel_review_path(entry_id, version):
    return f"reviews/{entry_id}/{version}.review.json"


def make_manifest_bytes(entry_id, version, platforms, capabilities=(), tools=(),
                        python_packages=(), script_runtime="none"):
    return hubcore.encoded({
        "schemaVersion": 1,
        "id": entry_id,
        "version": version,
        "capabilities": list(capabilities),
        "tools": list(tools),
        "platforms": list(platforms),
        "scriptRuntime": script_runtime,
        "pythonPackages": list(python_packages),
    })


def make_package_files(entry_id, manifest_bytes, scripts=False):
    files = {
        "SKILL.md": (f"---\nname: {entry_id}\ndescription: projection fixture guide\n---\n\n"
                     "Portable instruction-only fixture body.\n").encode("utf-8"),
        "floe.json": manifest_bytes,
        "references/LICENSE.txt": b"Fixture-only license notice text (not upstream material).\n",
    }
    if scripts:
        files["scripts/tool.js"] = b"// fixture-only inert script\n"
    return files


def make_record_bytes(entry_id, version, package_bytes, stage="static-content-reviewed",
                      execution=None):
    files = hubcore.check_archive_bytes(package_bytes)
    manifest, _ = hubcore.validate_package_files(files)
    return hubcore.encoded({
        "schemaVersion": hubcore.REVIEW_SCHEMA_VERSION,
        "id": entry_id,
        "version": version,
        "contentDigest": hubcore.content_digest(files),
        "packageSha256": hubcore.sha256_hex(package_bytes),
        "reviewedCapabilities": list(manifest["capabilities"]),
        "reviewedTools": list(manifest["tools"]),
        "reviewedPythonPackages": list(manifest["pythonPackages"]),
        "execution": execution if execution is not None else dict(GUIDE_EXECUTION),
        "reviewStage": stage,
        "reviewedAt": _today(),
        "reviewer": "projection-contract-test (ephemeral)",
        "decision": "approve",
        "notes": {"en": "Fixture review.", "zh-Hans": "夹具审查。"},
    })


class Snapshot:
    """Ephemeral X-style frozen input tree (packages + reviews), one per test."""

    def __init__(self):
        self.dir = tempfile.TemporaryDirectory(prefix="floe-android-projection-")
        self.root = pathlib.Path(self.dir.name)

    def close(self):
        self.dir.cleanup()

    def write_package(self, entry_id, version, channel, files):
        rel = hubcore.package_path_for(entry_id, version, channel)
        data = hubcore.make_zip(files)
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return rel, data

    def write_review(self, entry_id, version, record_bytes):
        path = self.root / rel_review_path(entry_id, version)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(record_bytes)
        path.with_suffix(path.suffix + ".sig").write_bytes(
            hubcore.sign_envelope(record_bytes, self.private_key, TEST_KEY_ID))


class ProjectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        cls.private_key = Ed25519PrivateKey.generate()
        raw = cls.private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        cls.public_keys = {TEST_KEY_ID: base64.b64encode(raw).decode()}

    def setUp(self):
        self.snapshots = []

    def tearDown(self):
        for snapshot in self.snapshots:
            snapshot.close()

    def _snapshot(self):
        snap = Snapshot()
        snap.private_key = self.private_key
        self.snapshots.append(snap)
        return snap

    def _guide_entry(self, capabilities=("workspace.read", "workspace.write"),
                     tools=(), python_packages=(), script_runtime="none",
                     root_id=GUIDE_ID, version=NEW_VERSION):
        entry = _base_entry(root_id)
        entry["versionTarget"] = version
        entry["minimumAppVersion"] = GUIDE_FLOOR
        entry["plannedRuntime"] = dict(
            entry["plannedRuntime"],
            capabilities=list(capabilities),
            tools=list(tools),
            pythonPackagesPlan=[p["spec"] for p in python_packages],
            scriptRuntime=script_runtime,
            installPlatforms=["ios", "android"],
        )
        if script_runtime != "none":
            entry["plannedRuntime"]["execution"] = {
                "os": "linux", "arch": "x86_64", "evidence": "unproven"}
        entry["status"] = dict(entry["status"], packaged=True, reviewed=True,
                               qualified=True, published=False, adaptation="frozen")
        return entry, version

    def _stage(self, snap, entry, version, platforms, capabilities=(), tools=(),
               python_packages=(), script_runtime="none", scripts=False,
               stage="static-content-reviewed", execution=None):
        manifest_bytes = make_manifest_bytes(
            entry["id"], version, platforms, capabilities, tools, python_packages,
            script_runtime)
        files = make_package_files(entry["id"], manifest_bytes, scripts=scripts)
        _rel, package_bytes = snap.write_package(entry["id"], version, "ios", files)
        snap.write_package(entry["id"], version, "android", files)
        snap.write_review(entry["id"], version, make_record_bytes(
            entry["id"], version, package_bytes, stage=stage, execution=execution))
        return package_bytes

    def _build(self, snap, entry, mode="release"):
        return build_catalog.build({"skills": [entry]}, mode, X_COMMIT,
                                   snap.root, snap.root, self.public_keys)

    @staticmethod
    def _feed(out, channel):
        name = "catalog.json" if channel == "ios" else "android/catalog.json"
        return json.loads(out[name])

    @staticmethod
    def _row(feed, entry_id):
        for row in feed["entries"]:
            if row["id"] == entry_id:
                return row
        raise AssertionError(f"{entry_id} missing from feed")

    @staticmethod
    def _assert_unchanged_schema(feed_doc):
        """Validate a feed doc against the EXISTING published schema file.

        Uses jsonschema only if it is already installed on the host — no
        dependency is installed here; when it is unavailable the caller
        still proves the unchanged hubcore.validate_catalog path.
        """
        try:
            import jsonschema
        except ImportError:
            return False
        schema = json.loads(CATALOG_SCHEMA.read_bytes())
        jsonschema.Draft202012Validator(schema).validate(feed_doc)
        return True

    # ------------------------------------------------------------------
    # identity of the frozen set (trusted tooling == immutable B facts)
    # ------------------------------------------------------------------

    def test_frozen_set_is_exactly_the_28_optional_none_rows(self):
        registry = json.loads((REPO / "catalog" / "skills.json").read_bytes())
        none_ids = {e["id"] for e in registry["skills"]
                    if e["kind"] == "optional"
                    and e["plannedRuntime"]["scriptRuntime"] == "none"}
        scripted = {e["id"] for e in registry["skills"]
                    if e["kind"] == "optional"
                    and e["plannedRuntime"]["scriptRuntime"] != "none"}
        builtins = {e["id"] for e in registry["skills"] if e["kind"] == "builtin"}
        self.assertEqual(len(build_catalog.ANDROID_PORTABLE_GUIDE_IDS), 28)
        self.assertEqual(build_catalog.ANDROID_PORTABLE_GUIDE_IDS, none_ids)
        self.assertEqual(len(scripted), 11)
        self.assertEqual(len(builtins), 4)
        self.assertEqual(len(none_ids | scripted | builtins), 43)
        self.assertFalse(build_catalog.ANDROID_PORTABLE_GUIDE_IDS
                         & (scripted | builtins | set(hubcore.RESERVED_BUILTIN_IDS)))
        self.assertEqual(build_catalog.ANDROID_PORTABLE_GUIDE_CAPABILITY_CEILING,
                         frozenset({"workspace.read", "workspace.write"}))

    def test_predicate_matrix_over_every_frozen_id(self):
        """The pure predicate alone decides; each flipped predicate refuses."""
        ok_manifest = json.loads(make_manifest_bytes(
            GUIDE_ID, NEW_VERSION, ["ios", "linux"], ["workspace.read"]))
        record = json.loads(hubcore.encoded({
            "schemaVersion": 1, "id": GUIDE_ID, "version": NEW_VERSION,
            "contentDigest": "0" * 64, "packageSha256": "1" * 64,
            "reviewedCapabilities": ["workspace.read"], "reviewedTools": [],
            "reviewedPythonPackages": [], "execution": dict(GUIDE_EXECUTION),
            "reviewStage": "static-content-reviewed", "reviewedAt": _today(),
            "reviewer": "shape-only-probe", "decision": "approve",
            "notes": {"en": "x", "zh-Hans": "x"}}))
        self.assertTrue(build_catalog.android_portable_guide_eligible(ok_manifest, record))
        for entry_id in sorted(build_catalog.ANDROID_PORTABLE_GUIDE_IDS):
            manifest = json.loads(hubcore.encoded(dict(ok_manifest, id=entry_id)))
            probe = json.loads(hubcore.encoded(dict(record, id=entry_id)))
            self.assertTrue(build_catalog.android_portable_guide_eligible(manifest, probe),
                            entry_id)
        refusals = {
            "ios-only manifest": dict(ok_manifest, platforms=["ios"]),
            "script runtime": dict(ok_manifest, scriptRuntime="javascriptcore"),
            "nonempty tools": dict(ok_manifest, tools=["data.search"]),
            "pythonPackages": dict(ok_manifest, scriptRuntime="remote",
                                   tools=["exec.shell"],
                                   capabilities=["execution.remote", "workspace.read"],
                                   pythonPackages=[{"spec": "requests==2.32.3",
                                                    "purpose": "x",
                                                    "capabilities": ["net.fetch"]}]),
            "workspace.delete cap": dict(ok_manifest,
                                         capabilities=["workspace.read",
                                                       "workspace.delete"]),
            "network cap": dict(ok_manifest, capabilities=["network"]),
            "browser.observe cap": dict(ok_manifest, capabilities=["browser.observe"]),
        }
        for label, manifest in refusals.items():
            with self.subTest(label):
                self.assertFalse(
                    build_catalog.android_portable_guide_eligible(manifest, record))
        for label, mutated in {
            # decision/reject and byte joins are enforced upstream by the
            # UNCHANGED bind_review/join_review gates; this predicate adds
            # the stage and execution-shape refusals:
            "guest stage": dict(record, reviewStage="guest-execution-qualified",
                                execution={"os": "linux", "arch": "aarch64",
                                           "evidence": "guest-verified"}),
            "claimed execution": dict(record, execution={"os": "linux",
                                                         "arch": "x86_64",
                                                         "evidence": "unproven"}),
        }.items():
            with self.subTest(label):
                self.assertFalse(
                    build_catalog.android_portable_guide_eligible(ok_manifest, mutated))

    # ------------------------------------------------------------------
    # positive projection through the real feed build
    # ------------------------------------------------------------------

    def test_linux_declared_guide_projects_android_and_keeps_ios_floor(self):
        entry, version = self._guide_entry()
        snap = self._snapshot()
        self._stage(snap, entry, version, ["ios", "linux"],
                    capabilities=("workspace.read", "workspace.write"))
        out = self._build(snap, entry)
        ios_row = self._row(self._feed(out, "ios"), GUIDE_ID)
        android_row = self._row(self._feed(out, "android"), GUIDE_ID)
        self.assertEqual(ios_row["minimumAppVersion"], GUIDE_FLOOR)
        self.assertEqual(android_row["minimumAppVersion"], SENTINEL)
        # THE POINT OF THE SENTINEL: the FINAL projected bytes — not a
        # floor-restored copy — pass the FULL unchanged hubcore.validate_catalog
        # (its "packaged entries require minimumAppVersion" clause intact) and
        # the EXISTING published schema, with no validator/schema relaxation.
        projected = json.loads(out["android/catalog.json"])
        hubcore.validate_catalog(projected, channel="android")
        # the EXISTING unchanged schema (jsonschema when already available):
        self._assert_unchanged_schema(projected)
        # the floor is the sole projection delta: restoring only the Android
        # floor yields the floor-retaining feed byte-for-byte on the entry.
        restored = json.loads(out["android/catalog.json"])
        for row in restored["entries"]:
            if row["id"] == GUIDE_ID:
                row["minimumAppVersion"] = GUIDE_FLOOR
        self.assertEqual(restored["counts"], projected["counts"])
        a, i = self._row(restored, GUIDE_ID), ios_row
        for key in set(a) | set(i):
            va, vi = a[key], i[key]
            if key == "package":
                self.assertTrue(vi["path"].startswith("packages/"))
                self.assertTrue(va["path"].startswith("android/packages/"))
                self.assertEqual({k: v for k, v in va.items() if k != "path"},
                                 {k: v for k, v in vi.items() if k != "path"})
            elif key == "runtime":
                ra = {k: v for k, v in va.items() if k != "installPlatforms"}
                ri = {k: v for k, v in vi.items() if k != "installPlatforms"}
                self.assertEqual(ra, ri)
                self.assertEqual(va["installPlatforms"], ["android"])
                self.assertEqual(vi["installPlatforms"], ["ios"])
            else:
                self.assertEqual(va, vi, key)
        # determinism: rebuilding identical inputs yields identical bytes
        out2 = self._build(snap, entry)
        self.assertEqual(out["android/catalog.json"], out2["android/catalog.json"])
        self.assertEqual(out["catalog.json"], out2["catalog.json"])

    def test_sentinel_is_valid_floor_while_null_would_be_rejected(self):
        """Root's rejection of the null projection is pinned: a null floor on
        a packaged entry fails the UNCHANGED validator clause, while the
        sentinel "0.0.0" is a strict X.Y.Z version accepted unchanged by
        require_version, validate_catalog and the published schema."""
        hubcore.require_version(SENTINEL)  # unchanged version grammar accepts
        with self.assertRaises(hubcore.HubError):
            hubcore.require_version(None)
        entry, version = self._guide_entry()
        snap = self._snapshot()
        self._stage(snap, entry, version, ["ios", "linux"],
                    capabilities=("workspace.read", "workspace.write"))
        out = self._build(snap, entry)
        projected = json.loads(out["android/catalog.json"])
        nulled = copy.deepcopy(projected)
        self._row(nulled, GUIDE_ID)["minimumAppVersion"] = None
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_catalog(nulled, channel="android")
        # and the unchanged schema keeps both variants expressible but the
        # validator clause (never weakened here) is what rejects null:
        self._assert_unchanged_schema(projected)

    def test_projection_is_idempotent_over_its_own_output(self):
        """Never re-project an entry already carrying the sentinel floor."""
        entry, version = self._guide_entry()
        snap = self._snapshot()
        self._stage(snap, entry, version, ["ios", "linux"],
                    capabilities=("workspace.read", "workspace.write"))
        out = self._build(snap, entry)
        projected = json.loads(out["android/catalog.json"])
        again = build_catalog.project_android_portable_guide_feed(
            projected, snap.root, snap.root)
        self.assertIsNone(again)
        # a floor-retaining feed still projects exactly once, to the sentinel
        kept = copy.deepcopy(projected)
        self._row(kept, GUIDE_ID)["minimumAppVersion"] = GUIDE_FLOOR
        once = build_catalog.project_android_portable_guide_feed(
            kept, snap.root, snap.root)
        self.assertIsNotNone(once)
        self.assertEqual(self._row(once, GUIDE_ID)["minimumAppVersion"], SENTINEL)

    def test_pre_linux_ios_only_manifest_keeps_floor_both_channels(self):
        entry, version = self._guide_entry()
        snap = self._snapshot()
        self._stage(snap, entry, version, ["ios"],
                    capabilities=("workspace.read", "workspace.write"))
        out = self._build(snap, entry)
        self.assertEqual(self._row(self._feed(out, "ios"), GUIDE_ID)["minimumAppVersion"],
                         GUIDE_FLOOR)
        self.assertEqual(
            self._row(self._feed(out, "android"), GUIDE_ID)["minimumAppVersion"],
            GUIDE_FLOOR)
        feed = json.loads(out["android/catalog.json"])
        self.assertIsNone(build_catalog.project_android_portable_guide_feed(
            feed, snap.root, snap.root))
        # no sentinel anywhere on a pre-Linux feed, and it is schema-valid:
        for row in feed["entries"]:
            self.assertNotEqual(row["minimumAppVersion"], SENTINEL)
        self._assert_unchanged_schema(feed)

    # ------------------------------------------------------------------
    # negatives: every predicate is mandatory (real feed-build integration)
    # ------------------------------------------------------------------

    def test_unknown_id_with_perfect_shape_is_never_projected(self):
        probe_id = "probe-portable-guide"
        entry, version = self._guide_entry()
        entry["id"] = probe_id
        snap = self._snapshot()
        self._stage(snap, entry, version, ["ios", "linux"],
                    capabilities=("workspace.read", "workspace.write"))
        out = self._build(snap, entry)
        self.assertEqual(self._row(self._feed(out, "android"), probe_id)
                         ["minimumAppVersion"], GUIDE_FLOOR)

    def test_nonbasic_caps_and_tools_keep_floor(self):
        """The four extra-capability guides of the staged 1.0.1 batch —
        floe-file-organizer (workspace.delete), deep-research and
        research-summarizer (network), a11y-audit (browser.observe) — keep
        their 1.7.59 floor because their OWN frozen manifests exceed the
        ceiling; the shapes below replay exactly those ceiling breaches
        (24 project, these 4 keep — see the lane's eligibility log)."""
        cases = {
            "workspace.delete cap": ("workspace.read", "workspace.write",
                                     "workspace.delete"),
            "network cap": ("network", "workspace.read"),
            "browser.observe cap": ("workspace.read", "browser.observe"),
        }
        for label, capabilities in cases.items():
            with self.subTest(label):
                entry, version = self._guide_entry(capabilities=capabilities)
                snap = self._snapshot()
                self._stage(snap, entry, version, ["ios", "linux"],
                            capabilities=capabilities)
                out = self._build(snap, entry)
                self.assertEqual(
                    self._row(self._feed(out, "android"), GUIDE_ID)["minimumAppVersion"],
                    GUIDE_FLOOR)

    def test_nonempty_tools_keep_floor(self):
        entry, version = self._guide_entry(tools=("data.search",))
        snap = self._snapshot()
        self._stage(snap, entry, version, ["ios", "linux"],
                    capabilities=("workspace.read", "workspace.write"),
                    tools=("data.search",))
        out = self._build(snap, entry)
        self.assertEqual(self._row(self._feed(out, "android"), GUIDE_ID)
                         ["minimumAppVersion"], GUIDE_FLOOR)

    def test_python_packages_and_remote_runtime_keep_floor(self):
        capabilities = ("execution.remote", "workspace.read")
        tools = ("exec.shell",)
        packages = ({"spec": "requests==2.32.3", "purpose": "fixture dep",
                     "capabilities": ["net.fetch"]},)
        entry, version = self._guide_entry(capabilities=capabilities, tools=tools,
                                           python_packages=list(packages),
                                           script_runtime="remote")
        snap = self._snapshot()
        self._stage(snap, entry, version, ["ios", "linux"], capabilities=capabilities,
                    tools=tools, python_packages=list(packages), script_runtime="remote",
                    scripts=True, execution={"os": "linux", "arch": "x86_64",
                                             "evidence": "unproven"})
        out = self._build(snap, entry)
        self.assertEqual(self._row(self._feed(out, "android"), GUIDE_ID)
                         ["minimumAppVersion"], GUIDE_FLOOR)

    def test_scripted_manifest_for_frozen_id_keeps_floor(self):
        """Registry plan is never authority: a frozen id whose BOUND manifest
        is a real script package keeps the floor via scriptRuntime/tools."""
        capabilities = ("execution.remote", "workspace.read")
        tools = ("exec.shell",)
        entry, version = self._guide_entry(capabilities=capabilities, tools=tools,
                                           script_runtime="remote")
        snap = self._snapshot()
        self._stage(snap, entry, version, ["ios", "linux"], capabilities=capabilities,
                    tools=tools, script_runtime="remote", scripts=True,
                    execution={"os": "linux", "arch": "x86_64", "evidence": "unproven"})
        out = self._build(snap, entry)
        self.assertEqual(self._row(self._feed(out, "android"), GUIDE_ID)
                         ["minimumAppVersion"], GUIDE_FLOOR)

    def test_guest_claim_or_wrong_stage_fails_closed_before_projection(self):
        """A guide-only package whose review claims guest execution (or any
        stage/evidence mismatch) is refused by the UNCHANGED bind/join gates:
        the whole release build refuses — never a silent floor waiver."""
        entry, version = self._guide_entry()
        snap = self._snapshot()
        manifest_bytes = make_manifest_bytes(GUIDE_ID, version, ["ios", "linux"],
                                             ["workspace.read", "workspace.write"])
        files = make_package_files(GUIDE_ID, manifest_bytes)
        _rel, package_bytes = snap.write_package(GUIDE_ID, version, "ios", files)
        snap.write_package(GUIDE_ID, version, "android", files)
        guest_record = make_record_bytes(
            GUIDE_ID, version, package_bytes, stage="guest-execution-qualified",
            execution={"os": "linux", "arch": "aarch64", "evidence": "guest-verified"})
        snap.write_review(GUIDE_ID, version, guest_record)
        with self.assertRaises(hubcore.HubError):
            self._build(snap, entry)

    def test_static_stage_with_claimed_execution_fails_closed(self):
        entry, version = self._guide_entry()
        snap = self._snapshot()
        self._stage(snap, entry, version, ["ios", "linux"],
                    capabilities=("workspace.read", "workspace.write"),
                    execution={"os": "linux", "arch": "x86_64", "evidence": "unproven"})
        with self.assertRaises(hubcore.HubError):
            self._build(snap, entry)

    def test_preview_without_package_or_review_binding_keeps_floor(self):
        entry, version = self._guide_entry()
        entry["status"] = dict(entry["status"], qualified=False, reviewed=False)
        snap = self._snapshot()
        manifest_bytes = make_manifest_bytes(GUIDE_ID, version, ["ios", "linux"],
                                             ["workspace.read", "workspace.write"])
        snap.write_package(GUIDE_ID, version, "ios",
                           make_package_files(GUIDE_ID, manifest_bytes))
        snap.write_package(GUIDE_ID, version, "android",
                           make_package_files(GUIDE_ID, manifest_bytes))
        # no review records at all and status.reviewed False: conservative keep
        out = self._build(snap, entry, mode="preview")
        row = self._row(self._feed(out, "android"), GUIDE_ID)
        self.assertEqual(row["minimumAppVersion"], GUIDE_FLOOR)
        self.assertIsNone(row["review"])

    # ------------------------------------------------------------------
    # purity of the projection helper
    # ------------------------------------------------------------------

    def test_projection_helper_is_nonmutating_and_pure(self):
        entry, version = self._guide_entry()
        snap = self._snapshot()
        self._stage(snap, entry, version, ["ios", "linux"],
                    capabilities=("workspace.read", "workspace.write"))
        # rebuild the SAME data with the frozen set temporarily emptied, so we
        # capture the fully-validated floor-retaining feed exactly as the
        # builder assembled it (real bindings, real bytes).
        saved = build_catalog.ANDROID_PORTABLE_GUIDE_IDS
        try:
            build_catalog.ANDROID_PORTABLE_GUIDE_IDS = frozenset()
            kept = self._build(snap, entry)
        finally:
            build_catalog.ANDROID_PORTABLE_GUIDE_IDS = saved
        feed = json.loads(kept["android/catalog.json"])
        before = copy.deepcopy(feed)
        projected1 = build_catalog.project_android_portable_guide_feed(
            feed, snap.root, snap.root)
        self.assertIsNotNone(projected1)
        self.assertEqual(feed, before)  # input feed never mutated
        self.assertEqual(self._row(feed, GUIDE_ID)["minimumAppVersion"], GUIDE_FLOOR)
        projected2 = build_catalog.project_android_portable_guide_feed(
            feed, snap.root, snap.root)
        self.assertEqual(projected1, projected2)  # deterministic over same bytes
        self.assertEqual(self._row(projected1, GUIDE_ID)["minimumAppVersion"],
                         SENTINEL)
        # the projected result passes the FULL unchanged validator as-is —
        # the sentinel, not null, is what the pipeline publishes:
        hubcore.validate_catalog(projected1, channel="android")
        # the helper's projection equals exactly what the wired builder emits:
        wired = self._build(snap, entry)
        self.assertEqual(hubcore.encoded(projected1), wired["android/catalog.json"])
        # non-projected entries are shared untouched objects, never copies
        kept_rows = {row["id"]: row for row in feed["entries"]}
        for row in projected1["entries"]:
            if row["id"] != GUIDE_ID:
                self.assertIs(kept_rows[row["id"]], row)
                self.assertIsNotNone(row["minimumAppVersion"])
                self.assertNotEqual(row["minimumAppVersion"], SENTINEL)

    # ------------------------------------------------------------------
    # current published B feeds rebuild byte-identical with this code
    # ------------------------------------------------------------------

    def test_published_current_feeds_rebuild_byte_identical(self):
        try:
            subprocess.run(["git", "-C", str(REPO), "cat-file", "-e", X_COMMIT],
                           check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.skipTest("audited X object is unavailable in this clone")
        tmp = tempfile.TemporaryDirectory(prefix="floe-projection-x-")
        self.addCleanup(tmp.cleanup)
        tar_path = pathlib.Path(tmp.name) / "x.tar"
        subprocess.run(["git", "-C", str(REPO), "archive", "--format=tar",
                        "-o", str(tar_path), X_COMMIT], check=True, capture_output=True)
        tree = pathlib.Path(tmp.name) / "tree"
        tree.mkdir()
        with tarfile.open(tar_path) as archive:
            archive.extractall(tree)
        registry = hubcore.validate_registry(build_catalog.load_registry(tree))
        public_keys = build_catalog.load_trust(REPO)
        outputs = build_catalog.build(registry, "release", X_COMMIT, tree, tree,
                                      public_keys)
        self.assertIn("catalog.json", outputs)
        self.assertIn("android/catalog.json", outputs)
        for name, data in outputs.items():
            published = subprocess.run(
                ["git", "-C", str(REPO), "show", f"{BASE_COMMIT}:{name}"],
                check=True, capture_output=True).stdout
            self.assertEqual(data, published, f"{name} bytes drifted from the publication")
        android = json.loads(outputs["android/catalog.json"])
        self.assertEqual(len(android["entries"]), 36)
        for row in android["entries"]:
            self.assertIsNotNone(row["minimumAppVersion"],
                                 f"{row['id']} floor must stay on the pre-Linux feed")
            self.assertNotEqual(row["minimumAppVersion"], SENTINEL,
                                f"{row['id']} must not carry the sentinel pre-Linux")
        # the published ios-only bytes remain fully current-validator- and
        # schema-valid under this code, unchanged:
        hubcore.validate_catalog(android, channel="android")
        self._assert_unchanged_schema(android)


if __name__ == "__main__":
    unittest.main(verbosity=2)
