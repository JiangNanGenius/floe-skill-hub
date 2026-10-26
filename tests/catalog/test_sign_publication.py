#!/usr/bin/env python3
"""Meaningful tests for the DATA-ONLY signing bridge (sign_publication.py).

Every signing here uses ONLY ephemeral public-knowledge test keys inside a
temporary copied test tooling root that CONFIGURES a fake public key under
the official keyID. The production pinned root is never used, weakened or
copied here. Positive paths bind real review/package/catalog bytes (the
impeccable mandatory slot reuses the REAL frozen contract inputs: the actual
sources/impeccable package bytes, the 563-byte canonical runtime descriptor
and the real static-ELF riscv64 engine, copied as data and NEVER executed);
negative paths must fail closed WITHOUT any output. The data and tooling
roots are real disposable Git repositories with the official origin intent
so the bridge's exact-snapshot verification is exercised, not stubbed.

The gate is exercised in BOTH admission shapes of the Root-approved
incremental policy (2026-10-27): the complete-selection fixture (all 39
optional rows qualified with all nine mandatory deep IDs admitted — 39
download offers once the four App-provided builtins are excluded) and the
incremental fixture carrying exactly the rows the REAL registry admits today
(28 guide-only plus the 2 guest-qualified skills, the nine mandatory IDs held
back — 30/30 download offers), plus a key-free in-memory gate probe against
the ACTUAL signed repository data whose expectations are DERIVED from the
registry (so a future honest admission changes no test, only the counts), and
a FROZEN initial-release fixture pinning the exact first-wave semantics.
Held-back mandatory IDs no longer block the qualified set; every per-item
trust refusal stays enforced.
"""
import base64
import copy
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

HERE = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERE / "scripts"))
import hubcore  # noqa: E402
import fixture_status  # noqa: E402

OFFICIAL_ORIGIN = "https://github.com/JiangNanGenius/floe-skill-hub.git"
KEY_ID = hubcore.PRODUCTION_KEY_ID
REVIEWED_AT = "2026-10-26"
REVIEWER = "signing-bridge-fixture-reviewer"
MANDATORY = [
    "algorithmic-art", "canvas-design", "exploratory-data-analysis",
    "impeccable", "literature-review", "markitdown",
    "scientific-visualization", "statistical-analysis", "webapp-testing",
]
GATE_REJECT_CODES = (2,)

TEST_SEED = hashlib.sha256(
    b"floe-skill-hub signing-bridge ephemeral TEST key -- NOT production").digest()
FOREIGN_SEED = hashlib.sha256(
    b"floe-skill-hub signing-bridge ephemeral FOREIGN key -- NOT production").digest()


def _key(seed):
    Ed25519PrivateKey, _, serialization, _ = hubcore._load_ed25519()
    key = Ed25519PrivateKey.from_private_bytes(seed)
    public = key.public_key().public_bytes(serialization.Encoding.Raw,
                                           serialization.PublicFormat.Raw)
    return key, base64.b64encode(public).decode()


def _env_value(seed):
    """Strict base64 of the raw 32-byte seed (legacy build.py representation)."""
    return base64.b64encode(seed).decode()


REAL_REGISTRY = json.loads((HERE / "catalog" / "skills.json").read_bytes())


def base_registry():
    # Temp-tree bridge fixtures stage only their own synthetic qualified rows;
    # every copied real row is explicitly demoted to the unadmitted fixture
    # state (see tests/catalog/fixture_status.py). The repository registry is
    # never touched and no gate is weakened.
    return fixture_status.stage_unadmitted_fixture(REAL_REGISTRY)


def _git(where, *args):
    proc = subprocess.run(["git", "-C", str(where)] + list(args),
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError(f"fixture git failed: {args}: {proc.stderr}")
    return proc.stdout


def _commit_all(path, message="fixture snapshot"):
    _git(path, "add", "-A")
    _git(path, "-c", "user.name=floe-signing-bridge-fixture",
         "-c", "user.email=fixture@invalid", "commit", "-q", "-m", message)
    return _git(path, "rev-parse", "HEAD").strip()


def guide_package(entry):
    manifest = {"schemaVersion": 1, "id": entry["id"], "version": entry["versionTarget"],
                "capabilities": [], "tools": [], "platforms": ["ios"],
                "scriptRuntime": "none", "pythonPackages": []}
    return {
        "SKILL.md": ("---\nname: " + entry["id"] + "\ndescription: Fixture signing-"
                     "bridge guide package for the bridge tests.\n---\n\nFixture-only"
                     " signing-bridge body; never installed.\n").encode(),
        "floe.json": json.dumps(manifest, sort_keys=True).encode(),
        "references/LICENSE.fixture.txt": b"Fixture signing-bridge license notice.\n",
    }


def script_package(entry):
    planned = entry["plannedRuntime"]
    manifest = {"schemaVersion": 1, "id": entry["id"], "version": entry["versionTarget"],
                "capabilities": list(planned["capabilities"]),
                "tools": list(planned["tools"]), "platforms": ["ios"],
                "scriptRuntime": "remote", "pythonPackages": []}
    return {
        "SKILL.md": ("---\nname: " + entry["id"] + "\ndescription: Fixture signing-"
                     "bridge script package for the bridge tests.\n---\n\nFixture-only"
                     " script body; never executed.\n").encode(),
        "floe.json": json.dumps(manifest, sort_keys=True).encode(),
        "scripts/tool.sh": b"#!/bin/sh\necho fixture-never-executed\n",
        "references/LICENSE.fixture.txt": b"Fixture signing-bridge license notice.\n",
    }


def real_package(entry):
    """The frozen actual staged source (same file rules as build_packages)."""
    folder = HERE / "sources" / entry["id"]
    files = {}
    for path in sorted(folder.rglob("*")):
        rel = path.relative_to(folder).as_posix()
        if path.is_symlink():
            raise AssertionError("symlink in real source tree")
        if not path.is_file():
            continue
        if path.name == "release.json":
            continue
        files[rel] = path.read_bytes()
    hubcore.validate_package_files(files, require_notice=bool(entry["upstream"]))
    manifest, _ = hubcore.validate_package_files(files,
                                                 require_notice=bool(entry["upstream"]))
    data = hubcore.make_zip(files)
    return {"files": files, "data": data, "sha256": hubcore.sha256_hex(data),
            "contentDigest": hubcore.content_digest(files), "manifest": manifest,
            "real": True}


def package_for(entry, scripted, real=False):
    if real:
        return real_package(entry)
    files = script_package(entry) if scripted else guide_package(entry)
    data = hubcore.make_zip(files)
    return {"files": files, "data": data,
            "sha256": hubcore.sha256_hex(data),
            "contentDigest": hubcore.content_digest(files),
            "manifest": json.loads(files["floe.json"])}


def review_record(entry, pkg, scripted, stage="auto"):
    if stage == "auto":
        stage = "guest-execution-qualified" if scripted else "static-content-reviewed"
    execution = ({"os": "linux", "arch": "riscv64", "evidence": "guest-verified"}
                 if scripted else {"os": None, "arch": "n/a", "evidence": "unproven"})
    return {
        "schemaVersion": 1, "id": entry["id"], "version": entry["versionTarget"],
        "contentDigest": pkg["contentDigest"], "packageSha256": pkg["sha256"],
        "reviewedCapabilities": list(pkg["manifest"]["capabilities"]),
        "reviewedTools": list(pkg["manifest"]["tools"]),
        "reviewedPythonPackages": list(pkg["manifest"]["pythonPackages"]),
        "execution": execution, "reviewStage": stage,
        "reviewedAt": REVIEWED_AT, "reviewer": REVIEWER,
        "decision": "approve",
        "notes": {"en": "Fixture signing-bridge review record; binds the test package "
                        "bytes only.",
                  "zh-Hans": "签名桥测试夹具审核记录；仅绑定测试包字节。"},
    }


class BridgeFixture(unittest.TestCase):
    """Shared temporary tooling-root + real git snapshots per test class."""

    maxDiff = None

    @classmethod
    def setUpClass(cls):
        cls.root = pathlib.Path(tempfile.mkdtemp(prefix="floe-signing-bridge-"))
        cls.key, cls.public_b64 = _key(TEST_SEED)
        cls.foreign_key, _ = _key(FOREIGN_SEED)
        cls._build_tooling()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    @classmethod
    def _build_tooling(cls):
        tooling = cls.root / "tooling"
        scripts = tooling / "scripts"
        scripts.mkdir(parents=True)
        for name in ("hubcore.py", "build_catalog.py", "runtime_dependency.py",
                     "sign_publication.py"):
            shutil.copy(HERE / "scripts" / name, scripts / name)
        (tooling / "public-key.json").write_bytes(hubcore.encoded(
            {"keyID": KEY_ID, "publicKey": cls.public_b64}))
        subprocess.run(["git", "init", "-q", "-b", "main", str(tooling)], check=True)
        _git(tooling, "remote", "add", "origin", OFFICIAL_ORIGIN)
        cls.tooling = tooling
        cls.tooling_commit = _commit_all(tooling, "fixture tooling pin")

    def _new_data(self, name):
        data = self.root / name
        if data.exists():
            shutil.rmtree(data)
        (data / "catalog").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(data)], check=True)
        _git(data, "remote", "add", "origin", OFFICIAL_ORIGIN)
        return data

    def _stage_registry(self, data, registry):
        (data / "catalog" / "skills.json").write_bytes(hubcore.encoded(registry))

    def _stage_packages(self, data, entry, pkg):
        for channel in entry["plannedRuntime"]["installPlatforms"]:
            rel = hubcore.package_path_for(entry["id"], entry["versionTarget"], channel)
            target = data / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(pkg["data"])

    def _stage_review(self, data, entry, record, signed_with=None):
        rel = f"reviews/{entry['id']}/{entry['versionTarget']}.review.json"
        target = data / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        record_bytes = hubcore.encoded(record)
        target.write_bytes(record_bytes)
        if signed_with is not None:
            envelope = hubcore.sign_envelope(record_bytes, signed_with, KEY_ID)
            (data / (rel + ".sig")).write_bytes(envelope)
        return record_bytes

    def _stage_engine_tree(self, data):
        """Copy the real engines/impeccable data files (frozen descriptor and
        the static riscv64 engine) as snapshot input bytes. They are read and
        hashed only; nothing is ever executed."""
        src = HERE / "engines" / "impeccable"
        for path in sorted(src.rglob("*")):
            if path.is_symlink():
                raise AssertionError("symlink in engines subtree")
            if not path.is_file():
                continue
            rel = path.relative_to(src).as_posix()
            target = data / "engines" / "impeccable" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())

    def _run_bridge(self, mode, data, commit, out, env_value=None, tooling=None):
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env.pop("PYTHONPATH", None)
        if env_value is None:
            env.pop("FLOE_SKILL_HUB_SIGNING_KEY", None)
        else:
            env["FLOE_SKILL_HUB_SIGNING_KEY"] = env_value
        proc = subprocess.run(
            [sys.executable, str(self.tooling / "scripts" / "sign_publication.py"),
             "--mode", mode, "--source-commit", commit, "--data", str(data),
             "--out", str(out), "--tooling", str(tooling or self.tooling)],
            capture_output=True, text=True, env=env,
            cwd=str(self.root))
        return proc

    def _standard_catalog_registry(self):
        """Complete-selection fixture: all 39 optional rows qualified (the 9
        mandatory deep plus every other optional row, scripted rows
        guest-verified, guides static) — 40 qualified registry rows of which
        exactly 39 are download offers, because the four App-provided builtins
        are never Hub download offers (floe-office/network/video stay
        candidates; floe-pdf is qualified registry data but excluded from the
        feed by its fixed ID)."""
        registry = base_registry()
        entries = {e["id"]: e for e in registry["skills"]}
        qualified = set()
        for entry in registry["skills"]:
            if entry["kind"] != "optional":
                continue
            scripted = entry["plannedRuntime"]["scriptRuntime"] != "none"
            status = dict(entry["status"], licenseChecked=True, packaged=True,
                          reviewed=True, qualified=True)
            if scripted:
                status = dict(status, adaptation="frozen", executionVerified=True)
            entry["status"] = status
            qualified.add(entry["id"])
        for id_ in MANDATORY:
            self.assertTrue(entries[id_]["status"]["qualified"])
            self.assertEqual(entries[id_]["plannedRuntime"]["scriptRuntime"], "remote")
        pdf = entries["floe-pdf"]
        pdf["status"] = dict(pdf["status"], licenseChecked=True, packaged=True,
                             reviewed=True, qualified=True)
        qualified.add("floe-pdf")
        return registry, qualified

    def _incremental_catalog_registry(self):
        """Frozen first-release shape for synthetic bridge tests.

        The 30-offer assertions below describe the initial release fixture,
        not the mutable real registry. Live admission and future mandatory
        additions are exercised independently by RealDataIncrementalGateTests.
        """
        initial = json.loads((HERE / "tests" / "catalog" / "fixtures" /
                              "initial-release-registry-2026-10.json").read_bytes())
        registry = fixture_status.stage_unadmitted_fixture(initial)
        real_by_id = {e["id"]: e for e in initial["skills"]}
        qualified = {e["id"]: e for e in initial["skills"]
                     if e["status"]["qualified"]}
        self.assertFalse(set(MANDATORY) & set(qualified))
        for entry in registry["skills"]:
            if entry["id"] not in qualified:
                continue
            real = real_by_id[entry["id"]]
            scripted = real["plannedRuntime"]["scriptRuntime"] != "none"
            status = dict(entry["status"], licenseChecked=True, packaged=True,
                          reviewed=True, qualified=True)
            if scripted:
                status = dict(status, adaptation="frozen", executionVerified=True)
            entry["status"] = status
        return registry, set(qualified)

    def _stage_catalog_data(self, name, registry, qualified_ids, sign=True,
                            real_impeccable=True, impeccable_real=False):
        data = self._new_data(name)
        self._stage_registry(data, registry)
        entries = {e["id"]: e for e in registry["skills"]}
        if real_impeccable:
            self._stage_engine_tree(data)
        staged = {}
        for id_ in sorted(qualified_ids):
            entry = entries[id_]
            scripted = entry["plannedRuntime"]["scriptRuntime"] != "none"
            pkg = package_for(entry, scripted,
                              real=(real_impeccable and id_ == "impeccable"))
            self._stage_packages(data, entry, pkg)
            record = review_record(entry, pkg, scripted)
            self._stage_review(data, entry, record,
                               signed_with=self.key if sign else None)
            staged[id_] = pkg
        commit = _commit_all(data)
        return data, commit, staged

    def verify_receipt(self, out, trust):
        receipt_bytes = (out / "signing-receipt.json").read_bytes()
        sidecar = (out / "signing-receipt.json.sig").read_bytes()
        self.assertEqual(hubcore.encoded(json.loads(receipt_bytes)), receipt_bytes)
        self.assertEqual(hubcore.verify_envelope(receipt_bytes, sidecar, trust), KEY_ID)
        with self.assertRaises(hubcore.HubError):
            hubcore.verify_envelope(receipt_bytes + b" ", sidecar, trust)
        receipt = json.loads(receipt_bytes)
        listed = {entry["path"]: entry for entry in receipt["outputs"]}
        self.assertNotIn("signing-receipt.json", listed)
        self.assertNotIn("signing-receipt.json.sig", listed)
        for rel, meta in listed.items():
            body = (out / rel).read_bytes()
            self.assertEqual(meta["sha256"], hubcore.sha256_hex(body), rel)
            self.assertEqual(meta["size"], len(body), rel)
        return receipt


class ReviewsModeTests(BridgeFixture):

    def _stage_single(self, name, id_="a11y-audit", mutate=None):
        registry = base_registry()
        entry = next(e for e in registry["skills"] if e["id"] == id_)
        self.assertEqual(entry["plannedRuntime"]["scriptRuntime"], "none")
        entry["status"] = dict(entry["status"], licenseChecked=True,
                               packaged=True, reviewed=True)
        if mutate is not None:
            mutate(registry, entry)
        data = self._new_data(name)
        self._stage_registry(data, registry)
        pkg = package_for(entry, scripted=False)
        self._stage_packages(data, entry, pkg)
        record = review_record(entry, pkg, scripted=False)
        record_bytes = self._stage_review(data, entry, record)
        if mutate is not None:
            mutate(registry, entry, data=data, record=record, record_bytes=record_bytes)
        commit = _commit_all(data)
        return data, commit, pkg, record_bytes

    def test_positive_signs_and_receipts_without_promotion(self):
        data, commit, pkg, record_bytes = self._stage_single("reviews-positive")
        out = self.root / "out-reviews-positive"
        proc = self._run_bridge("reviews", data, commit, out, env_value=_env_value(TEST_SEED))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        written = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
        self.assertEqual(written, [
            "reviews/a11y-audit/1.0.0.review.json",
            "reviews/a11y-audit/1.0.0.review.json.sig",
            "signing-receipt.json",
            "signing-receipt.json.sig",
        ])
        self.assertEqual((out / "reviews/a11y-audit/1.0.0.review.json").read_bytes(),
                         record_bytes)
        trust = {KEY_ID: self.public_b64}
        key_id = hubcore.verify_envelope(
            record_bytes,
            (out / "reviews/a11y-audit/1.0.0.review.json.sig").read_bytes(), trust)
        self.assertEqual(key_id, KEY_ID)
        receipt = self.verify_receipt(out, trust)
        self.assertEqual(receipt["mode"], "reviews")
        self.assertEqual(receipt["sourceCommit"], commit)
        self.assertEqual(receipt["toolingCommit"], self.tooling_commit)
        self.assertEqual(receipt["keyID"], KEY_ID)
        (review,) = receipt["reviews"]
        self.assertEqual(review["recordSha256"], hubcore.sha256_hex(record_bytes))
        self.assertEqual(review["packageSha256"], pkg["sha256"])
        self.assertEqual(review["contentDigest"], pkg["contentDigest"])
        self.assertEqual(review["reviewStage"], "static-content-reviewed")
        # no key material anywhere in the output
        for path in out.rglob("*"):
            if path.is_file():
                body = path.read_bytes()
                self.assertNotIn(base64.b64encode(TEST_SEED).decode().encode(), body)
                self.assertNotIn(self.public_b64.encode(), body)
        # no promotion: the data registry bytes are untouched and the snapshot
        # stays clean at the same commit
        self.assertEqual(_git(data, "rev-parse", "HEAD").strip(), commit)
        registry_after = json.loads((data / "catalog" / "skills.json").read_bytes())
        entry_after = next(e for e in registry_after["skills"] if e["id"] == "a11y-audit")
        self.assertFalse(entry_after["status"]["qualified"])
        self.assertFalse(entry_after["status"]["executionVerified"])

    def test_foreign_key_refused_no_output(self):
        data, commit, pkg, record_bytes = self._stage_single("reviews-foreignkey")
        out = self.root / "out-reviews-foreignkey"
        proc = self._run_bridge("reviews", data, commit, out, env_value=_env_value(FOREIGN_SEED))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("official trust root", proc.stderr)
        self.assertFalse(out.exists() and any(out.rglob("*")))
        self.assertNotIn(base64.b64encode(FOREIGN_SEED).decode(), proc.stderr)
        self.assertNotIn(_env_value(FOREIGN_SEED), proc.stderr)

    def test_missing_env_refused(self):
        data, commit, pkg, record_bytes = self._stage_single("reviews-noenv")
        out = self.root / "out-reviews-noenv"
        proc = self._run_bridge("reviews", data, commit, out, env_value=None)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("fabricate", proc.stderr)
        self.assertFalse(out.exists() and any(out.rglob("*")))

    def test_noncanonical_record_refused(self):
        def mutate(registry, entry, data=None, record=None, record_bytes=None):
            if data is not None:
                (data / "reviews" / entry["id"] / f"{entry['versionTarget']}.review.json"
                 ).write_bytes(json.dumps(record, indent=2, sort_keys=True).encode())
        data, commit, pkg, record_bytes = self._stage_single("reviews-noncanonical",
                                                             mutate=mutate)
        out = self.root / "out-reviews-noncanonical"
        proc = self._run_bridge("reviews", data, commit, out, env_value=_env_value(TEST_SEED))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("canonical", proc.stderr)
        self.assertFalse(out.exists() and any(out.rglob("*")))

    def test_digest_drift_refused(self):
        def drift(registry, entry, data=None, record=None, record_bytes=None):
            if data is not None:
                bad = dict(record, contentDigest="f" * 64)
                (data / "reviews" / entry["id"] / f"{entry['versionTarget']}.review.json"
                 ).write_bytes(hubcore.encoded(bad))
        data, commit, pkg, record_bytes = self._stage_single("reviews-digest", mutate=drift)
        out = self.root / "out-reviews-digest"
        proc = self._run_bridge("reviews", data, commit, out, env_value=_env_value(TEST_SEED))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("join failed", proc.stderr)
        self.assertFalse(out.exists() and any(out.rglob("*")))

    def test_package_size_cap_refused(self):
        data, commit, pkg, record_bytes = self._stage_single("reviews-caps")
        target = next((data / "packages").rglob("*.zip"))
        files = dict(pkg["files"])
        files["references/BIG.md"] = b"x" * (hubcore.MAX_FILE_BYTES + 1)
        new_bytes = hubcore.make_zip(files)
        target.write_bytes(new_bytes)
        # also keep the index/HEAD honest about a DIFFERENT tamper path:
        # re-commit, then re-sign a record that matches nothing else the gate knows
        _commit_all(data, "oversized package")
        commit = _git(data, "rev-parse", "HEAD").strip()
        out = self.root / "out-reviews-caps"
        proc = self._run_bridge("reviews", data, commit, out, env_value=_env_value(TEST_SEED))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("recompute failed", proc.stderr)
        self.assertFalse(out.exists() and any(out.rglob("*")))

    def test_status_and_identity_refused(self):
        def unreviewed(registry, entry, data=None, **_kw):
            if data is not None:
                entry["status"] = dict(entry["status"], reviewed=False)
                self._stage_registry(data, registry)
        data, commit, pkg, record_bytes = self._stage_single("reviews-status",
                                                             mutate=unreviewed)
        out = self.root / "out-reviews-status"
        proc = self._run_bridge("reviews", data, commit, out, env_value=_env_value(TEST_SEED))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("status", proc.stderr)
        self.assertFalse(out.exists() and any(out.rglob("*")))

    def test_reject_decision_refused(self):
        def rejected(registry, entry, data=None, record=None, record_bytes=None):
            if data is not None:
                bad = dict(record, decision="reject")
                (data / "reviews" / entry["id"] / f"{entry['versionTarget']}.review.json"
                 ).write_bytes(hubcore.encoded(bad))
        data, commit, pkg, record_bytes = self._stage_single("reviews-reject",
                                                             mutate=rejected)
        out = self.root / "out-reviews-reject"
        proc = self._run_bridge("reviews", data, commit, out, env_value=_env_value(TEST_SEED))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("approve", proc.stderr)

    def test_existing_signature_input_refused(self):
        data, commit, pkg, record_bytes = self._stage_single("reviews-signed")
        (data / "reviews" / "a11y-audit" / "1.0.0.review.json.sig").write_bytes(
            hubcore.sign_envelope(record_bytes, self.key, KEY_ID))
        _commit_all(data, "already signed")
        commit = _git(data, "rev-parse", "HEAD").strip()
        out = self.root / "out-reviews-signed"
        proc = self._run_bridge("reviews", data, commit, out, env_value=_env_value(TEST_SEED))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("UNSIGNED", proc.stderr)

    def test_dirty_and_head_mismatch_refused(self):
        data, commit, pkg, record_bytes = self._stage_single("reviews-dirty")
        (data / "EXTRA").write_text("untracked\n")
        out = self.root / "out-reviews-dirty"
        proc = self._run_bridge("reviews", data, commit, out, env_value=_env_value(TEST_SEED))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("untracked", proc.stderr)

        proc2 = self._run_bridge("reviews", data, "0" * 40,
                                 self.root / "out-reviews-head",
                                 env_value=_env_value(TEST_SEED))
        self.assertNotEqual(proc2.returncode, 0)
        self.assertIn("does not equal", proc2.stderr)

    def test_ignored_shadow_refused(self):
        data, commit, pkg, record_bytes = self._stage_single("reviews-ignored")
        (data / ".gitignore").write_text("/SHADOW.md\n")
        _commit_all(data, "gitignore tracked")
        commit = _git(data, "rev-parse", "HEAD").strip()
        (data / "SHADOW.md").write_text("ignored shadow review material\n")
        out = self.root / "out-reviews-ignored"
        proc = self._run_bridge("reviews", data, commit, out, env_value=_env_value(TEST_SEED))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("ignored", proc.stderr)
        self.assertFalse(out.exists() and any(out.rglob("*")))

    def test_assume_unchanged_tamper_refused(self):
        data, commit, pkg, record_bytes = self._stage_single("reviews-assume")
        rel = "reviews/a11y-audit/1.0.0.review.json"
        bad = dict(json.loads(record_bytes), reviewer="attacker-in-place")
        (data / rel).write_bytes(hubcore.encoded(bad))
        _git(data, "update-index", "--assume-unchanged", "--", rel)
        self.assertEqual(_git(data, "status", "--porcelain"), "")
        out = self.root / "out-reviews-assume"
        proc = self._run_bridge("reviews", data, commit, out, env_value=_env_value(TEST_SEED))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("differs from the HEAD blob", proc.stderr)
        self.assertFalse(out.exists() and any(out.rglob("*")))

    def test_replace_object_tamper_refused(self):
        data, commit, pkg, record_bytes = self._stage_single("reviews-replace")
        rel = "reviews/a11y-audit/1.0.0.review.json"
        original_blob = _git(data, "rev-parse", f"HEAD:{rel}").strip()
        bad = dict(json.loads(record_bytes), reviewer="attacker-via-replace")
        bad_bytes = hubcore.encoded(bad)
        (data / rel).write_bytes(bad_bytes)
        replacement_blob = _git(data, "hash-object", "-w", "--", rel).strip()
        _git(data, "replace", original_blob, replacement_blob)
        self.assertTrue(_git(data, "for-each-ref", "refs/replace/"))
        self.assertEqual(_git(data, "rev-parse", "HEAD").strip(), commit)
        # with replacement resolution DISABLED (the bridge's posture), ls-tree
        # still names the ORIGINAL blob while disk carries replacement bytes
        check = subprocess.run(
            ["git", "-C", str(data), "ls-tree", "-r", "HEAD", "--", rel],
            capture_output=True, text=True,
            env={**os.environ, "GIT_NO_REPLACE_OBJECTS": "1"})
        self.assertIn(original_blob, check.stdout)
        out = self.root / "out-reviews-replace"
        proc = self._run_bridge("reviews", data, commit, out, env_value=_env_value(TEST_SEED))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("differs from the HEAD blob", proc.stderr)
        self.assertFalse(out.exists() and any(out.rglob("*")))

    def test_command_shaped_source_commit_refused(self):
        data, commit, pkg, record_bytes = self._stage_single("reviews-injection")
        canary = self.root / "pwned"
        out = self.root / "out-reviews-injection"
        proc = self._run_bridge("reviews", data, f"$(touch {canary})", out,
                                env_value=_env_value(TEST_SEED))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("40 lowercase hex", proc.stderr)
        self.assertFalse(canary.exists())
        proc2 = self._run_bridge("reviews", data, f"deadbeef;touch {canary}", out,
                                 env_value=_env_value(TEST_SEED))
        self.assertNotEqual(proc2.returncode, 0)
        self.assertFalse(canary.exists())

    def test_data_git_hooks_never_execute(self):
        data, commit, pkg, record_bytes = self._stage_single("reviews-hooks")
        hooks = data / ".git" / "hooks"
        hooks.mkdir(exist_ok=True)
        for name in ("post-checkout", "post-index-change", "reference-transaction",
                     "pre-commit"):
            script = hooks / name
            script.write_text("#!/bin/sh\ntouch " + str(self.root / "hook-ran") + "\n")
            script.chmod(0o755)
        # hostile repo-local config too: fsmonitor + fake filter process
        config = data / ".git" / "config"
        config.write_text(config.read_text() +
                          "\n[core]\n\tfsmonitor = " + str(self.root / "nope.sh") +
                          "\n[filter \"evil\"]\n\tprocess = touch " +
                          str(self.root / "filter-ran") + "\n")
        out = self.root / "out-reviews-hooks"
        proc = self._run_bridge("reviews", data, commit, out, env_value=_env_value(TEST_SEED))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse((self.root / "hook-ran").exists())
        self.assertFalse((self.root / "filter-ran").exists())

    def test_tracked_symlink_refused(self):
        registry = base_registry()
        entry = next(e for e in registry["skills"] if e["id"] == "a11y-audit")
        entry["status"] = dict(entry["status"], licenseChecked=True, packaged=True,
                               reviewed=True)
        data = self._new_data("reviews-symlink")
        self._stage_registry(data, registry)
        pkg = package_for(entry, scripted=False)
        self._stage_packages(data, entry, pkg)
        self._stage_review(data, entry, review_record(entry, pkg, scripted=False))
        (data / "reviews" / "a11y-audit" / "EXTRA.link").symlink_to(
            pathlib.Path("..") / ".." / "catalog" / "skills.json")
        _commit_all(data, "with symlink")
        commit = _git(data, "rev-parse", "HEAD").strip()
        out = self.root / "out-reviews-symlink"
        proc = self._run_bridge("reviews", data, commit, out, env_value=_env_value(TEST_SEED))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("symlink", proc.stderr)

    def test_out_inside_data_and_nonempty_refused(self):
        data, commit, pkg, record_bytes = self._stage_single("reviews-outpath")
        inside = data / "brand-new-out"
        proc = self._run_bridge("reviews", data, commit, inside, env_value=_env_value(TEST_SEED))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("outside", proc.stderr)
        self.assertFalse(inside.exists())

        out = self.root / "out-reviews-nonempty"
        out.mkdir()
        (out / "foreign.txt").write_text("do not touch\n")
        proc2 = self._run_bridge("reviews", data, commit, out, env_value=_env_value(TEST_SEED))
        self.assertNotEqual(proc2.returncode, 0)
        self.assertIn("foreign", proc2.stderr)
        self.assertEqual((out / "foreign.txt").read_text(), "do not touch\n")

    def test_fresh_nested_out_writes_exact_requested_leaf(self):
        data, commit, pkg, record_bytes = self._stage_single("reviews-nestedout")
        stage_parent = self.root / "stage-parent"
        stage_parent.mkdir(exist_ok=True)
        sentinel = stage_parent / "sentinel.txt"
        sentinel.write_text("parent sentinel\n")
        out = stage_parent / "brand-new-out"
        proc = self._run_bridge("reviews", data, commit, out, env_value=_env_value(TEST_SEED))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(sentinel.read_text(), "parent sentinel\n")
        self.assertEqual(sorted(p.relative_to(stage_parent).as_posix()
                                for p in stage_parent.rglob("*") if p.is_file()),
                         ["brand-new-out/reviews/a11y-audit/1.0.0.review.json",
                          "brand-new-out/reviews/a11y-audit/1.0.0.review.json.sig",
                          "brand-new-out/signing-receipt.json",
                          "brand-new-out/signing-receipt.json.sig",
                          "sentinel.txt"])
        self.assertFalse((stage_parent / "reviews").exists())
        self.assertFalse((stage_parent / "signing-receipt.json").exists())

    def test_out_symlink_refused(self):
        data, commit, pkg, record_bytes = self._stage_single("reviews-outlink")
        victim = self.root / "victim-dir"
        victim.mkdir()
        link = self.root / "out-link"
        link.symlink_to(victim)
        proc = self._run_bridge("reviews", data, commit, link, env_value=_env_value(TEST_SEED))
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(any(victim.iterdir()))


class CatalogModeTests(BridgeFixture):

    def test_positive_launch_gate_and_standalone_publication(self):
        registry, qualified = self._standard_catalog_registry()
        data, commit, staged = self._stage_catalog_data("catalog-positive", registry,
                                                        qualified)
        out = self.root / "out-catalog-positive"
        proc = self._run_bridge("catalog", data, commit, out, env_value=_env_value(TEST_SEED))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        trust = {KEY_ID: self.public_b64}
        for rel in ("catalog.json", "catalog.sig", "android/catalog.json",
                    "android/catalog.sig", "signing-receipt.json",
                    "signing-receipt.json.sig"):
            self.assertTrue((out / rel).is_file(), rel)
        for feed, sig in (("catalog.json", "catalog.sig"),
                          ("android/catalog.json", "android/catalog.sig")):
            payload = (out / feed).read_bytes()
            self.assertEqual(hubcore.encoded(json.loads(payload)), payload)
            self.assertEqual(hubcore.verify_envelope(payload, (out / sig).read_bytes(),
                                                     trust), KEY_ID)
        ios = json.loads((out / "catalog.json").read_bytes())
        android = json.loads((out / "android/catalog.json").read_bytes())
        self.assertEqual(ios["sourceCommit"], commit)
        # 40 qualified registry rows (39 optional + the floe-pdf builtin) but
        # only 39 download offers: the four App-provided builtins are never
        # Hub download offers.
        self.assertEqual(len(ios["entries"]), 39)
        self.assertEqual(len(android["entries"]), 39)
        self.assertNotIn("floe-pdf", {e["id"] for e in ios["entries"]})
        for entry in ios["entries"]:
            self.assertTrue(entry["status"]["published"], entry["id"])
        for id_ in MANDATORY:
            self.assertIn(id_, {e["id"] for e in ios["entries"]})
            self.assertIn(id_, {e["id"] for e in android["entries"]})
        # standalone publication: feed-referenced archives + reviews + sigs staged
        for feed_name, prefix in (("catalog.json", ""), ("android/catalog.json", "android/")):
            feed = json.loads((out / feed_name).read_bytes())
            for entry in feed["entries"]:
                archive = out / entry["package"]["path"]
                self.assertTrue(archive.is_file(), entry["package"]["path"])
                body = archive.read_bytes()
                self.assertEqual(hubcore.sha256_hex(body), entry["package"]["sha256"])
                self.assertEqual(len(body), entry["package"]["size"])
                record = out / entry["review"]["path"]
                self.assertTrue(record.is_file())
                self.assertEqual(hubcore.sha256_hex(record.read_bytes()),
                                 entry["review"]["sha256"])
                envelope = out / (entry["review"]["path"] + ".sig")
                self.assertTrue(envelope.is_file())
                self.assertEqual(
                    hubcore.verify_envelope(record.read_bytes(), envelope.read_bytes(),
                                            trust), KEY_ID)
        # immutable impeccable runtime bytes are carried end to end
        impeccable_pkg = next(e for e in ios["entries"] if e["id"] == "impeccable")
        self.assertEqual(impeccable_pkg["package"]["contentDigest"],
                         staged["impeccable"]["contentDigest"])
        self.assertIn(b'"componentID":"impeccable-engine"',
                      (out / impeccable_pkg["package"]["path"]).read_bytes())
        frozen_rel = "engines/impeccable/runtime-dependency/descriptor.v1.json"
        self.assertTrue((out / frozen_rel).is_file())
        self.assertEqual((out / frozen_rel).read_bytes(),
                         (HERE / frozen_rel).read_bytes())
        engine_rel = ("engines/impeccable/dist/impeccable-0.1.17+floe.1.0.0/"
                      "riscv64gc-unknown-linux-musl/floe-impeccable")
        self.assertTrue((out / engine_rel).is_file())
        self.assertEqual(hubcore.sha256_hex((out / engine_rel).read_bytes()),
                         hashlib.sha256((HERE / engine_rel).read_bytes()).hexdigest())
        receipt = self.verify_receipt(out, trust)
        self.assertEqual(receipt["mode"], "catalog")
        self.assertEqual(receipt["sourceCommit"], commit)
        self.assertEqual(receipt["toolingCommit"], self.tooling_commit)
        self.assertEqual(receipt["launchGate"]["policy"], "incremental-2026-10-27")
        self.assertEqual(receipt["launchGate"]["iosQualified"], 39)
        self.assertEqual(receipt["launchGate"]["androidQualified"], 39)
        self.assertEqual(receipt["launchGate"]["selectionQualified"], 40)
        self.assertEqual(receipt["launchGate"]["builtinProvided"], 1)
        self.assertEqual(receipt["launchGate"]["mandatoryDeepIds"], sorted(MANDATORY))
        self.assertEqual(receipt["launchGate"]["mandatoryDeepOffered"], sorted(MANDATORY))
        coverage = receipt["launchGate"]["completeSelectionCoverage"]
        self.assertTrue(coverage["informationalOnly"])
        self.assertEqual(coverage["selectionQualified"], 40)
        self.assertTrue(coverage["meetsQualifiedTarget"])
        self.assertEqual(coverage["builtinProvided"], 1)
        self.assertEqual(coverage["downloadEligible"], 39)
        self.assertTrue(coverage["mandatoryDeepAllPresent"])
        self.assertTrue(coverage["complete"])
        listed = {entry["path"] for entry in receipt["outputs"]}
        self.assertIn(engine_rel, listed)
        self.assertIn(frozen_rel, listed)
        self.assertIn(impeccable_pkg["review"]["path"], listed)
        all_receipt_bytes = b"".join((out / p).read_bytes() for p in
                                     ("signing-receipt.json", "signing-receipt.json.sig",
                                      "catalog.json", "catalog.sig"))
        self.assertNotIn(base64.b64encode(TEST_SEED).decode().encode(), all_receipt_bytes)
        self.assertNotIn(self.public_b64.encode(), all_receipt_bytes)
        # data untouched
        self.assertEqual(_git(data, "rev-parse", "HEAD").strip(), commit)
        registry_after = json.loads((data / "catalog" / "skills.json").read_bytes())
        entry_after = next(e for e in registry_after["skills"] if e["id"] == "a11y-audit")
        self.assertFalse(entry_after["status"]["published"])

    def _expect_refused(self, out, message_fragment):
        proc = self._last_proc
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn(message_fragment, proc.stderr)
        self.assertFalse(out.exists() and any(out.rglob("*")))

    def test_incremental_admission_publishes_exact_30_download_feeds(self):
        """Frozen initial incremental shape: exactly the first 30 qualified optional
        rows (28 guides + 2 guest skills) publish as the 30/30 download feeds
        while all nine mandatory deep IDs and the four App-provided builtins
        stay out of the download offers. No engine bytes may be staged because
        impeccable is not offered; the coverage metadata must honestly say
        NOT complete (34 selection / 40, 0/9)."""
        registry, qualified = self._incremental_catalog_registry()
        data, commit, _staged = self._stage_catalog_data(
            "catalog-incremental", registry, qualified, real_impeccable=False)
        out = self.root / "out-catalog-incremental"
        proc = self._run_bridge("catalog", data, commit, out,
                                env_value=_env_value(TEST_SEED))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        trust = {KEY_ID: self.public_b64}
        for rel in ("catalog.json", "catalog.sig", "android/catalog.json",
                    "android/catalog.sig", "signing-receipt.json",
                    "signing-receipt.json.sig"):
            self.assertTrue((out / rel).is_file(), rel)
        for feed, sig in (("catalog.json", "catalog.sig"),
                          ("android/catalog.json", "android/catalog.sig")):
            payload = (out / feed).read_bytes()
            self.assertEqual(hubcore.encoded(json.loads(payload)), payload)
            self.assertEqual(hubcore.verify_envelope(payload, (out / sig).read_bytes(),
                                                     trust), KEY_ID)
        ios = json.loads((out / "catalog.json").read_bytes())
        android = json.loads((out / "android/catalog.json").read_bytes())
        self.assertEqual(ios["sourceCommit"], commit)
        self.assertEqual(len(ios["entries"]), 30)
        self.assertEqual(len(android["entries"]), 30)
        download = qualified - set(hubcore.RESERVED_BUILTIN_IDS)
        self.assertEqual(len(download), 30)
        self.assertEqual({e["id"] for e in ios["entries"]}, download)
        self.assertEqual({e["id"] for e in android["entries"]}, download)
        for entry in ios["entries"]:
            self.assertTrue(entry["status"]["published"], entry["id"])
        self.assertNotIn("impeccable", {e["id"] for e in ios["entries"]})
        for id_ in MANDATORY:
            self.assertNotIn(id_, {e["id"] for e in ios["entries"]})
            self.assertNotIn(id_, {e["id"] for e in android["entries"]})
        for id_ in hubcore.RESERVED_BUILTIN_IDS:
            self.assertNotIn(id_, {e["id"] for e in ios["entries"]})
            self.assertNotIn(id_, {e["id"] for e in android["entries"]})
        # per-item stages stay honest: exactly the two real guest receipts
        # carry guest-execution-qualified; the other 28 offers are static.
        guest, static = set(), set()
        for entry in ios["entries"]:
            record = json.loads((out / entry["review"]["path"]).read_bytes())
            if record["reviewStage"] == "guest-execution-qualified":
                guest.add(entry["id"])
            else:
                static.add(entry["id"])
        self.assertEqual(guest, {"citation-management", "sympy"})
        self.assertEqual(len(static), 28)
        # standalone staging of every offered archive + signed review
        for feed_name in ("catalog.json", "android/catalog.json"):
            feed = json.loads((out / feed_name).read_bytes())
            for entry in feed["entries"]:
                body = (out / entry["package"]["path"]).read_bytes()
                self.assertEqual(hubcore.sha256_hex(body), entry["package"]["sha256"])
                self.assertEqual(len(body), entry["package"]["size"])
                record = out / entry["review"]["path"]
                self.assertEqual(hubcore.sha256_hex(record.read_bytes()),
                                 entry["review"]["sha256"])
                self.assertEqual(
                    hubcore.verify_envelope(record.read_bytes(),
                                            (out / (entry["review"]["path"]
                                                    + ".sig")).read_bytes(),
                                            trust), KEY_ID)
        receipt = self.verify_receipt(out, trust)
        gate = receipt["launchGate"]
        self.assertEqual(gate["policy"], "incremental-2026-10-27")
        self.assertEqual(gate["iosQualified"], 30)
        self.assertEqual(gate["androidQualified"], 30)
        self.assertEqual(gate["selectionQualified"], 34)
        self.assertEqual(gate["builtinProvided"], 4)
        self.assertEqual(gate["mandatoryDeepIds"], sorted(MANDATORY))
        self.assertEqual(gate["mandatoryDeepOffered"], [])
        coverage = gate["completeSelectionCoverage"]
        self.assertTrue(coverage["informationalOnly"])
        self.assertEqual(coverage["selectionQualified"], 34)
        self.assertFalse(coverage["meetsQualifiedTarget"])
        self.assertEqual(coverage["builtinProvided"], 4)
        self.assertEqual(coverage["downloadEligible"], 30)
        self.assertFalse(coverage["mandatoryDeepAllPresent"])
        self.assertFalse(coverage["complete"])
        listed = {entry["path"] for entry in receipt["outputs"]}
        self.assertFalse(any(p.startswith("engines/") for p in listed))
        self.assertFalse((out / "engines").exists())
        self.assertEqual(_git(data, "rev-parse", "HEAD").strip(), commit)

    def test_empty_qualified_refused(self):
        """An empty advertised set is never publishable: with nothing
        admitted the release build fails closed before any signing."""
        registry = base_registry()
        data, commit, _ = self._stage_catalog_data("catalog-empty", registry, set(),
                                                   real_impeccable=False)
        out = self.root / "out-catalog-empty"
        self._last_proc = self._run_bridge("catalog", data, commit, out,
                                           env_value=_env_value(TEST_SEED))
        self._expect_refused(out, "empty catalog")

    def test_stale_false_execution_verified_refused(self):
        """A scripted offer whose registry admission was NOT actually earned
        (stale/false executionVerified under a perfectly signed guest review)
        is refused: signatures alone never substitute for the real status."""
        registry, qualified = self._incremental_catalog_registry()
        entries = {e["id"]: e for e in registry["skills"]}
        entries["sympy"]["status"] = dict(entries["sympy"]["status"],
                                          executionVerified=False)
        data, commit, _ = self._stage_catalog_data("catalog-stale-ev", registry,
                                                   qualified,
                                                   real_impeccable=False)
        out = self.root / "out-catalog-stale-ev"
        self._last_proc = self._run_bridge("catalog", data, commit, out,
                                           env_value=_env_value(TEST_SEED))
        self._expect_refused(out, "status.executionVerified true")

    def test_offered_mandatory_single_channel_refused(self):
        """Held-back mandatory IDs no longer block the qualified 34, but a
        mandatory ID that IS offered must appear in BOTH feeds: an iOS-only
        advertisement of markitdown is refused fail-closed."""
        registry, qualified = self._incremental_catalog_registry()
        entries = {e["id"]: e for e in registry["skills"]}
        markitdown = entries["markitdown"]
        markitdown["status"] = dict(markitdown["status"], licenseChecked=True,
                                    packaged=True, reviewed=True, qualified=True,
                                    adaptation="frozen", executionVerified=True)
        markitdown["plannedRuntime"] = dict(markitdown["plannedRuntime"],
                                            installPlatforms=["ios"])
        qualified = set(qualified) | {"markitdown"}
        data, commit, _ = self._stage_catalog_data("catalog-mandatory-single",
                                                   registry, qualified,
                                                   real_impeccable=False)
        out = self.root / "out-catalog-mandatory-single"
        self._last_proc = self._run_bridge("catalog", data, commit, out,
                                           env_value=_env_value(TEST_SEED))
        self._expect_refused(out, "single channel")

    def test_relabel_deep_flag_refused(self):
        registry, qualified = self._standard_catalog_registry()
        for entry in registry["skills"]:
            if entry["id"] == "markitdown":
                entry["deepAdaptation"] = False
            if entry["id"] == "a11y-audit":
                entry["deepAdaptation"] = True
        src = self.root / "catalog-positive"
        self.assertTrue(src.is_dir())
        data = self._new_data("catalog-relabel")
        for path in sorted(src.rglob("*")):
            if path.is_dir() or ".git" in path.parts:
                continue
            rel = path.relative_to(src)
            if rel.as_posix() == "catalog/skills.json":
                continue
            target = data / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
        self._stage_registry(data, registry)
        commit = _commit_all(data, "relabel deepAdaptation")
        out = self.root / "out-catalog-relabel"
        self._last_proc = self._run_bridge("catalog", data, commit, out,
                                           env_value=_env_value(TEST_SEED))
        self._expect_refused(out, "relabeling")

    def test_mandatory_as_guide_refused(self):
        """A pinned mandatory ID relabeled guide-only (static review, scriptRuntime
        none) is refused even though it remains qualified in both feeds."""
        registry, qualified = self._standard_catalog_registry()
        entries = {e["id"]: e for e in registry["skills"]}
        markitdown = entries["markitdown"]
        markitdown["status"] = dict(markitdown["status"], executionVerified=False)
        markitdown["plannedRuntime"] = dict(
            markitdown["plannedRuntime"], scriptRuntime="none",
            capabilities=[], tools=[], pythonPackagesPlan=[],
            execution={"os": None, "arch": "n/a", "evidence": "unproven"})
        data = self._new_data("catalog-guide-relabel")
        self._stage_registry(data, registry)
        self._stage_engine_tree(data)
        for id_ in sorted(qualified):
            entry = entries[id_]
            scripted = (id_ == "markitdown") is False and \
                entry["plannedRuntime"]["scriptRuntime"] != "none"
            pkg = package_for(entry, scripted, real=(id_ == "impeccable"))
            self._stage_packages(data, entry, pkg)
            record = review_record(entry, pkg, scripted)
            self._stage_review(data, entry, record, signed_with=self.key)
        commit = _commit_all(data)
        out = self.root / "out-catalog-guide-relabel"
        self._last_proc = self._run_bridge("catalog", data, commit, out,
                                           env_value=_env_value(TEST_SEED))
        self._expect_refused(out, "guide-only replacement")

    def test_impeccable_missing_runtime_refused(self):
        """Omitting impeccable's embedded runtime descriptor must not bypass H6."""
        registry, qualified = self._standard_catalog_registry()
        entries = {e["id"]: e for e in registry["skills"]}
        data = self._new_data("catalog-no-runtime")
        self._stage_registry(data, registry)
        self._stage_engine_tree(data)
        for id_ in sorted(qualified):
            entry = entries[id_]
            scripted = entry["plannedRuntime"]["scriptRuntime"] != "none"
            pkg = package_for(entry, scripted, real=False)  # synthetic: no descriptor
            self._stage_packages(data, entry, pkg)
            self._stage_review(data, entry, review_record(entry, pkg, scripted),
                               signed_with=self.key)
        commit = _commit_all(data)
        out = self.root / "out-catalog-no-runtime"
        self._last_proc = self._run_bridge("catalog", data, commit, out,
                                           env_value=_env_value(TEST_SEED))
        self._expect_refused(out, "mandatory runtime gate failed")

    def test_script_static_stage_refused_despite_valid_signature(self):
        registry, qualified = self._standard_catalog_registry()
        entries = {e["id"]: e for e in registry["skills"]}
        data = self._new_data("catalog-static-script")
        self._stage_registry(data, registry)
        self._stage_engine_tree(data)
        for id_ in sorted(qualified):
            entry = entries[id_]
            scripted = entry["plannedRuntime"]["scriptRuntime"] != "none"
            pkg = package_for(entry, scripted, real=(id_ == "impeccable"))
            self._stage_packages(data, entry, pkg)
            if id_ == "markitdown":
                record = review_record(entry, pkg, scripted,
                                       stage="static-content-reviewed")
                record = dict(record, execution={"os": None, "arch": "n/a",
                                                 "evidence": "unproven"})
            else:
                record = review_record(entry, pkg, scripted)
            self._stage_review(data, entry, record, signed_with=self.key)
        commit = _commit_all(data)
        out = self.root / "out-catalog-static"
        proc = self._run_bridge("catalog", data, commit, out, env_value=_env_value(TEST_SEED))
        self.assertNotEqual(proc.returncode, 0)
        self.assertTrue("guest-execution-qualified" in proc.stderr
                        or "Linux environment" in proc.stderr
                        or "join" in proc.stderr)
        self.assertFalse(out.exists() and any(out.rglob("*")))

    def test_foreign_key_review_refused(self):
        registry, qualified = self._standard_catalog_registry()
        entries = {e["id"]: e for e in registry["skills"]}
        data = self._new_data("catalog-foreignsig")
        self._stage_registry(data, registry)
        self._stage_engine_tree(data)
        for id_ in sorted(qualified):
            entry = entries[id_]
            scripted = entry["plannedRuntime"]["scriptRuntime"] != "none"
            pkg = package_for(entry, scripted, real=(id_ == "impeccable"))
            self._stage_packages(data, entry, pkg)
            record = review_record(entry, pkg, scripted)
            rel = f"reviews/{entry['id']}/{entry['versionTarget']}.review.json"
            (data / rel).parent.mkdir(parents=True, exist_ok=True)
            record_bytes = hubcore.encoded(record)
            (data / rel).write_bytes(record_bytes)
            signer = self.foreign_key if id_ == "markitdown" else self.key
            (data / (rel + ".sig")).write_bytes(hubcore.sign_envelope(record_bytes,
                                                                      signer, KEY_ID))
        commit = _commit_all(data)
        out = self.root / "out-catalog-foreignsig"
        self._last_proc = self._run_bridge("catalog", data, commit, out,
                                           env_value=_env_value(TEST_SEED))
        self._expect_refused(out, "verification failed")

    def test_unsigned_review_refused(self):
        registry, qualified = self._standard_catalog_registry()
        entries = {e["id"]: e for e in registry["skills"]}
        data = self._new_data("catalog-nosig")
        self._stage_registry(data, registry)
        self._stage_engine_tree(data)
        for id_ in sorted(qualified):
            entry = entries[id_]
            scripted = entry["plannedRuntime"]["scriptRuntime"] != "none"
            pkg = package_for(entry, scripted, real=(id_ == "impeccable"))
            self._stage_packages(data, entry, pkg)
            record = review_record(entry, pkg, scripted)
            self._stage_review(data, entry, record,
                               signed_with=None if id_ == "a11y-audit" else self.key)
        commit = _commit_all(data)
        out = self.root / "out-catalog-nosig"
        self._last_proc = self._run_bridge("catalog", data, commit, out,
                                           env_value=_env_value(TEST_SEED))
        self._expect_refused(out, "requires the record and its .sig")


class RealDataIncrementalGateTests(unittest.TestCase):
    """Key-free in-memory policy probe against the ACTUAL signed repository.

    Builds the real release feeds from the checked-in archives and the 43
    trust-verified signed review records committed at this epoch, then runs
    the unchanged per-item gates plus the incremental launch gate directly.
    Nothing here signs, writes or promotes anything: the tree is only read,
    no key material is involved, and the committed production trust root
    verifies its own signatures through the builder's review joins.
    """

    SOURCE_X = "1111111111111111111111111111111111111111"

    @classmethod
    def setUpClass(cls):
        import build_catalog
        import runtime_dependency
        import sign_publication
        cls.build_catalog = build_catalog
        cls.runtime_dependency = runtime_dependency
        cls.sign_publication = sign_publication
        cls.registry = hubcore.validate_registry(copy.deepcopy(REAL_REGISTRY))
        cls.trust = build_catalog.load_trust(HERE)
        cls.outputs = build_catalog.build(cls.registry, "release", cls.SOURCE_X,
                                         HERE, HERE, cls.trust)
        cls.args = SimpleNamespace(data=str(HERE), source_commit=cls.SOURCE_X)

    def _gate(self, outputs=None):
        return self.sign_publication.enforce_launch_gate(
            hubcore, self.runtime_dependency, self.args, self.registry,
            self.outputs if outputs is None else outputs)

    def test_actual_admission_passes_incremental_gate(self):
        # Expectations are DERIVED from the registry, not hardcoded: a future
        # honest admission (e.g. another optional skill qualifying) changes
        # only the recomputed counts, never this test's structure.
        gate = self._gate()
        self.assertEqual(gate["policy"], "incremental-2026-10-27")
        self.assertEqual(gate["mandatoryDeepIds"], sorted(MANDATORY))
        admitted = {e["id"] for e in REAL_REGISTRY["skills"]
                    if e["status"]["qualified"]}
        download_ios = {e["id"] for e in REAL_REGISTRY["skills"]
                        if e["status"]["qualified"]
                        and "ios" in e["plannedRuntime"]["installPlatforms"]
                        and not hubcore.is_download_offer_excluded(e["id"])}
        download_android = {e["id"] for e in REAL_REGISTRY["skills"]
                            if e["status"]["qualified"]
                            and "android" in e["plannedRuntime"]["installPlatforms"]
                            and not hubcore.is_download_offer_excluded(e["id"])}
        self.assertTrue(download_ios)
        self.assertTrue(download_android)
        expected_mandatory = set(MANDATORY) & (download_ios | download_android)
        self.assertEqual(gate["mandatoryDeepOffered"], sorted(expected_mandatory))
        self.assertEqual(gate["iosQualified"], len(download_ios))
        self.assertEqual(gate["androidQualified"], len(download_android))
        self.assertEqual(gate["selectionQualified"], len(admitted))
        self.assertEqual(
            gate["builtinProvided"],
            sum(1 for e in REAL_REGISTRY["skills"]
                if e["id"] in hubcore.APP_PROVIDED_BUILTIN_IDS
                and e["status"]["qualified"]))
        coverage = gate["completeSelectionCoverage"]
        self.assertTrue(coverage["informationalOnly"])
        self.assertEqual(coverage["selectionQualified"], len(admitted))
        self.assertEqual(coverage["meetsQualifiedTarget"],
                         len(admitted) >= self.sign_publication.COMPLETE_SELECTION_QUALIFIED_TARGET)
        all_mandatory = (set(MANDATORY) <= download_ios
                         and set(MANDATORY) <= download_android)
        self.assertEqual(coverage["mandatoryDeepAllPresent"], all_mandatory)
        self.assertEqual(coverage["complete"],
                         coverage["meetsQualifiedTarget"] and all_mandatory)
        ios = json.loads(self.outputs["catalog.json"])
        android = json.loads(self.outputs["android/catalog.json"])
        self.assertEqual({e["id"] for e in ios["entries"]}, download_ios)
        self.assertEqual({e["id"] for e in android["entries"]}, download_android)
        # The four App-provided builtins are qualified registry data but never
        # download offers.
        self.assertFalse(set(hubcore.RESERVED_BUILTIN_IDS) & download_ios)
        self.assertFalse(set(hubcore.RESERVED_BUILTIN_IDS) & download_android)
        # The release feed is the publication act: every offer carries the
        # feed-only published=true projection, while the source registry
        # object stays published=false (never mutated by the build).
        for feed in (ios, android):
            for entry in feed["entries"]:
                self.assertTrue(entry["status"]["published"], entry["id"])
        self.assertTrue(all(not e["status"]["published"]
                            for e in REAL_REGISTRY["skills"]))
        scripted = {e["id"] for e in ios["entries"]
                    if e["runtime"]["scriptRuntime"] != "none"}
        self.assertEqual(scripted, {
            e["id"] for e in REAL_REGISTRY["skills"]
            if e["id"] in download_ios
            and e["plannedRuntime"]["scriptRuntime"] != "none"})
        for entry in ios["entries"]:
            if entry["runtime"]["scriptRuntime"] != "none":
                self.assertTrue(entry["status"]["executionVerified"], entry["id"])
            else:
                self.assertFalse(entry["status"]["executionVerified"], entry["id"])
        self.assertEqual(any(name.startswith("engines/") for name in self.outputs),
                         "impeccable" in download_ios)

    def _refused(self, outputs, fragment):
        with self.assertRaises(self.sign_publication.SigningError) as ctx:
            self._gate(outputs)
        self.assertIn(fragment, str(ctx.exception))

    def _tamper_ios_feed(self, mutate):
        feed = json.loads(self.outputs["catalog.json"])
        mutate(feed)
        return dict(self.outputs, **{"catalog.json": hubcore.encoded(feed)})

    def test_partial_drop_refused(self):
        self._refused(self._tamper_ios_feed(lambda f: f["entries"].pop()),
                      "exactly the qualified rows advertising iOS")

    def test_invented_row_refused(self):
        registered = {e["id"] for e in REAL_REGISTRY["skills"]}
        invented = "unregistered-offer"
        while invented in registered:
            invented += "-extra"

        def add(feed):
            feed["entries"].append(dict(feed["entries"][0], id=invented))
        self._refused(self._tamper_ios_feed(add),
                      "exactly the qualified rows advertising iOS")

    def test_duplicate_ids_refused(self):
        self._refused(self._tamper_ios_feed(
            lambda f: f["entries"].append(dict(f["entries"][0]))),
            "duplicate ids inside the iOS feed")

    def test_empty_feed_refused(self):
        def empty(feed):
            feed["entries"] = []
        self._refused(self._tamper_ios_feed(empty),
                      "an empty feed is never publishable")

    def test_android_partial_drop_refused(self):
        feed = json.loads(self.outputs["android/catalog.json"])
        feed["entries"] = feed["entries"][:-1]
        self._refused(dict(self.outputs,
                           **{"android/catalog.json": hubcore.encoded(feed)}),
                      "exactly the qualified rows advertising android")

    def test_runtime_relabel_false_claim_refused(self):
        # A guide package whose feed entry falsely claims the remote runtime
        # is caught by the unchanged per-item status gate, not by any count.
        feed = json.loads(self.outputs["catalog.json"])
        guide = next((e for e in feed["entries"]
                      if e["runtime"]["scriptRuntime"] == "none"), None)
        if guide is not None:
            guide["runtime"] = dict(guide["runtime"], scriptRuntime="remote")
            refusal = "offered script package requires"
        else:
            feed["entries"][0]["runtime"] = dict(
                feed["entries"][0]["runtime"], scriptRuntime="none")
            refusal = "guide-only package"
        self._refused(dict(self.outputs, **{"catalog.json": hubcore.encoded(feed)}),
                      refusal)

    def test_unpublished_release_offer_refused(self):
        def hide(feed):
            feed["entries"][0]["status"]["published"] = False
        self._refused(self._tamper_ios_feed(hide),
                      "release offer requires feed status.published true")


class FrozenInitialReleaseTests(unittest.TestCase):
    """EXPLICIT frozen first-wave semantics on the initial-release registry.

    `fixtures/initial-release-registry-2026-10.json` is an immutable copy of
    the registry as it stood when the first incremental release opened: 43
    rows, 34 qualified (28 optional guides + 2 guest-qualified scripts + the
    4 App-provided builtins), the 9 mandatory deep IDs held back. These
    expectations are pinned to that frozen data — they never drift with the
    live registry — while the real-data probe above derives its counts
    dynamically so future honest admissions never break it.
    """

    FROZEN = json.loads(
        (HERE / "tests" / "catalog" / "fixtures" /
         "initial-release-registry-2026-10.json").read_bytes())
    SOURCE_X = "1111111111111111111111111111111111111111"

    @classmethod
    def setUpClass(cls):
        import build_catalog
        import runtime_dependency
        import sign_publication
        cls.build_catalog = build_catalog
        cls.runtime_dependency = runtime_dependency
        cls.sign_publication = sign_publication
        cls.registry = hubcore.validate_registry(copy.deepcopy(cls.FROZEN))
        cls.trust = build_catalog.load_trust(HERE)
        cls.outputs = build_catalog.build(cls.registry, "release", cls.SOURCE_X,
                                          HERE, HERE, cls.trust)
        cls.args = SimpleNamespace(data=str(HERE), source_commit=cls.SOURCE_X)
        cls.gate = sign_publication.enforce_launch_gate(
            hubcore, cls.runtime_dependency, cls.args, cls.registry, cls.outputs)

    def test_frozen_initial_data_shape(self):
        skills = self.FROZEN["skills"]
        self.assertEqual(len(skills), 43)
        admitted = {e["id"] for e in skills if e["status"]["qualified"]}
        self.assertEqual(len(admitted), 34)
        self.assertEqual({e["id"] for e in skills
                          if e["id"] in hubcore.APP_PROVIDED_BUILTIN_IDS
                          and e["status"]["qualified"]},
                         set(hubcore.RESERVED_BUILTIN_IDS))
        self.assertTrue(all(not e["status"]["published"] for e in skills))
        self.assertEqual({e["id"] for e in skills
                          if e["status"]["executionVerified"]},
                         {"citation-management", "sympy"})
        deep = {e["id"] for e in skills if e["deepAdaptation"]}
        self.assertEqual(deep, set(MANDATORY))
        self.assertTrue(all(not e["status"]["qualified"] for e in skills
                            if e["deepAdaptation"]))

    def test_frozen_first_wave_download_offers_exactly_30(self):
        ios = json.loads(self.outputs["catalog.json"])
        android = json.loads(self.outputs["android/catalog.json"])
        self.assertEqual(len(ios["entries"]), 30)
        self.assertEqual(len(android["entries"]), 30)
        offered = {e["id"] for e in ios["entries"]}
        self.assertEqual(offered, {e["id"] for e in android["entries"]})
        # exactly the 30 qualified optional rows, never the 4 builtins
        self.assertFalse(offered & set(hubcore.RESERVED_BUILTIN_IDS))
        self.assertEqual(offered, {e["id"] for e in self.FROZEN["skills"]
                                   if e["status"]["qualified"]
                                   and e["id"] not in hubcore.APP_PROVIDED_BUILTIN_IDS})
        for feed in (ios, android):
            self.assertEqual(feed["counts"]["offerQualified"], 30)
            self.assertEqual(feed["counts"]["builtin"], 0)
            for entry in feed["entries"]:
                self.assertEqual(entry["installOffer"], "qualified", entry["id"])
                self.assertTrue(entry["status"]["published"], entry["id"])
        # the frozen source rows keep published=false (feed-only projection)
        self.assertTrue(all(not e["status"]["published"]
                            for e in self.FROZEN["skills"]))
        gate = self.gate
        self.assertEqual(gate["iosQualified"], 30)
        self.assertEqual(gate["androidQualified"], 30)
        self.assertEqual(gate["selectionQualified"], 34)
        self.assertEqual(gate["builtinProvided"], 4)
        coverage = gate["completeSelectionCoverage"]
        self.assertEqual(coverage["selectionQualified"], 34)
        self.assertEqual(coverage["qualifiedTarget"], 40)
        self.assertFalse(coverage["meetsQualifiedTarget"])
        self.assertEqual(coverage["builtinProvided"], 4)
        self.assertEqual(coverage["downloadEligible"], 30)
        self.assertEqual(coverage["mandatoryDeepOfferedCount"], 0)
        self.assertFalse(coverage["mandatoryDeepAllPresent"])
        self.assertFalse(coverage["complete"])
        self.assertFalse(any(name.startswith("engines/") for name in self.outputs))

    def test_offer_selection_follows_copied_registry_without_mutation(self):
        # Change eligibility of an already authenticated guide in a COPIED
        # fixture. Merely flipping a held script's qualified flag would not
        # constitute a genuine guest-qualified admission. The live registry
        # may legitimately gain such admissions later; it must be preserved,
        # not asserted to remain forever in this initial epoch.
        live_before = copy.deepcopy(REAL_REGISTRY)
        changed = copy.deepcopy(self.registry)
        for entry in changed["skills"]:
            if entry["id"] == "a11y-audit":
                entry["status"] = dict(entry["status"], qualified=False)
        changed = hubcore.validate_registry(changed)
        outputs = self.build_catalog.build(changed, "release", self.SOURCE_X,
                                           HERE, HERE, self.trust)
        ios = json.loads(outputs["catalog.json"])
        android = json.loads(outputs["android/catalog.json"])
        self.assertEqual(len(ios["entries"]), 29)
        self.assertEqual(len(android["entries"]), 29)
        self.assertNotIn("a11y-audit", {e["id"] for e in ios["entries"]})
        gate = self.sign_publication.enforce_launch_gate(
            hubcore, self.runtime_dependency, self.args, changed, outputs)
        self.assertEqual(gate["iosQualified"], 29)
        self.assertEqual(gate["androidQualified"], 29)
        self.assertEqual(REAL_REGISTRY, live_before)
        self.assertTrue(next(e for e in self.FROZEN["skills"]
                             if e["id"] == "a11y-audit")["status"]["qualified"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
