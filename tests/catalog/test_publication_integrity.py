#!/usr/bin/env python3
"""Publication-path integrity regressions (H1 close).

These exercise the ACTUAL CLIs (build_catalog.py / check_catalog.py), the
configured public trust (public-key.json), the signing-identity gate, the
both-channel feed+signature gate, the audited-source X -> publication commit Y
pinned-fetch flow, and the rule that verifying a publication reads only the
published bytes — never the mutable candidate HEAD.

Everything runs against clearly isolated ephemeral keys and temp trees with
child processes; nothing asserts a real production publication, and the real
signing secret is never read.

Run: python3 -m unittest discover -s tests/catalog -t tests/catalog
"""
import base64
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "scripts"))
import hubcore
import build_catalog

REPO = HERE.parents[2]
SIGN_ENV = "FLOE_TEST_EPHEMERAL_SIGNING_KEY"  # test-local name; value is ephemeral
SOURCE_X = "1111111111111111111111111111111111111111"
QUALIFIED_VERSION = "1.3.1"  # Isolated test identity, independent of live candidates.

# Canonical public trust root, deliberately hardcoded so the regression is
# identical in a standalone Hub clone (CI) and in the full App workspace,
# without reading any outer checkout. This mirrors the published
# skill-hub/public-key.json of the Floe main checkout and the Hub's own
# committed public-key.json; changing the real root requires an audited
# rotation commit touching BOTH this constant and public-key.json together.
CANONICAL_ROOT_KEY_ID = "official-2026-09"
CANONICAL_ROOT_PUBLIC_B64 = "qOMhhkiyMpw1tWRgbuNH79PjlL6nynbFGqBxeNX2Hco="


def ephemeral_key():
    Ed25519PrivateKey, _, serialization, _ = hubcore._load_ed25519()
    seed = hashlib_seed()
    key = Ed25519PrivateKey.from_private_bytes(seed)
    pub = base64.b64encode(key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
    return key, pub, base64.b64encode(seed).decode()


def hashlib_seed():
    import hashlib
    return hashlib.sha256(("hub-pub-test-" + os.urandom(16).hex()).encode()).digest()


def trust_file(pub_b64, key_id=hubcore.PRODUCTION_KEY_ID):
    return hubcore.encoded({"keyID": key_id, "publicKey": pub_b64})


def synthetic_registry():
    """Registry copy with exactly one synthetically qualified builtin.

    The status flip is isolated temp-tree test data letting the real release
    CLI walk its qualified branch. It never claims real review or publication,
    and the repository registry file stays untouched.
    """
    reg = json.loads((REPO / "catalog" / "skills.json").read_bytes())
    for entry in reg["skills"]:
        if entry["id"] == "floe-pdf":
            entry["versionTarget"] = QUALIFIED_VERSION
            entry["firstParty"]["stagedSourceVersion"] = QUALIFIED_VERSION
            entry["status"] = dict(entry["status"], licenseChecked=True,
                                   adaptation="frozen", packaged=True,
                                   reviewed=True, qualified=True)
            entry["plannedRuntime"] = dict(entry["plannedRuntime"],
                                           installPlatforms=["ios", "android"])
    return reg


def qualified_entry(registry):
    return next(e for e in registry["skills"] if e["id"] == "floe-pdf")


def stage_package(root, entry):
    """Deterministic synthetic archive at both channel paths; returns (files, bytes)."""
    files = {
        "SKILL.md": (b"---\nname: floe-pdf\ndescription: Isolated publication-path "
                     b"test sample; synthetic data, never released content.\n"
                     b"---\n\nSynthetic guide body for the ephemeral publication CLI "
                     b"regression. Not a published artifact.\n"),
        "floe.json": hubcore.encoded({
            "schemaVersion": 1, "id": "floe-pdf", "version": entry["versionTarget"],
            "capabilities": [], "tools": [], "platforms": ["ios"],
            "scriptRuntime": "none", "pythonPackages": []}),
        "references/NOTICE.md": (b"Floe-owned synthetic test material staged only for "
                                b"isolated CLI regressions.\n"),
    }
    hubcore.validate_package_files(files)
    data = hubcore.make_zip(files)
    for channel in ("ios", "android"):
        rel = hubcore.package_path_for("floe-pdf", entry["versionTarget"], channel)
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return files, data


def stage_review(root, key, files, data, entry):
    manifest, _ = hubcore.validate_package_files(files)
    record = {
        "schemaVersion": 1, "id": "floe-pdf", "version": entry["versionTarget"],
        "contentDigest": hubcore.content_digest(files),
        "packageSha256": hubcore.sha256_hex(data),
        "reviewedCapabilities": list(manifest["capabilities"]),
        "reviewedTools": list(manifest["tools"]),
        "reviewedPythonPackages": list(manifest["pythonPackages"]),
        "execution": {"os": None, "arch": "n/a", "evidence": "unproven"},
        "reviewStage": "static-content-reviewed",
        "reviewedAt": "2026-10-26",
        "reviewer": "isolated-ephemeral-test-reviewer",
        "decision": "approve",
        "notes": {"en": "Synthetic review for an isolated ephemeral-key CLI regression only.",
                  "zh-Hans": "仅供隔离临时密钥 CLI 回归使用的合成审核记录。"},
    }
    record_bytes = hubcore.encoded(record)
    path = root / "reviews" / "floe-pdf" / (entry["versionTarget"] + ".review.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(record_bytes)
    path.with_suffix(path.suffix + ".sig").write_bytes(
        hubcore.sign_envelope(record_bytes, key, hubcore.PRODUCTION_KEY_ID))


def stage_repo(tmp, pub_b64=None):
    """Materialize an isolated hub tree: tooling + one qualified synthetic entry."""
    root = pathlib.Path(tmp)
    for name in ("scripts", "schema"):
        shutil.copytree(REPO / name, root / name, ignore=shutil.ignore_patterns("__pycache__"))
    (root / "docs").mkdir(exist_ok=True)
    shutil.copy(REPO / "docs" / "UPSTREAM-PINS.json", root / "docs")
    fixtures_dst = root / "tests" / "catalog" / "fixtures"
    fixtures_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(REPO / "tests" / "catalog" / "fixtures", fixtures_dst)
    registry = synthetic_registry()
    (root / "catalog").mkdir(exist_ok=True)
    (root / "catalog" / "skills.json").write_bytes(hubcore.encoded(registry))
    if pub_b64 is not None:
        (root / "public-key.json").write_bytes(trust_file(pub_b64))
    return root


def freeze_snapshot(root, dest):
    """Explicit staging freeze: an isolated copy used as the audited X snapshot."""
    shutil.copytree(root, dest, ignore=shutil.ignore_patterns("out", "staging", ".git"))
    return pathlib.Path(dest)


def run_script(root, script, argv, env=None):
    proc = subprocess.run([sys.executable, str(pathlib.Path(root) / "scripts" / script)]
                          + list(argv), capture_output=True, text=True, env=env)
    return proc.returncode, proc.stdout + proc.stderr


def release_cli(root, snapshot, out, sign_raw=None, source_commit=SOURCE_X, extra=()):
    argv = ["--mode", "release", "--source-commit", source_commit,
            "--source-snapshot", str(snapshot), "--out-root", str(out), *extra]
    env = {**os.environ, SIGN_ENV: sign_raw} if sign_raw is not None else None
    if sign_raw is not None:
        argv += ["--sign-env", SIGN_ENV]
    return run_script(root, "build_catalog.py", argv, env=env)


def published_repo(tmp):
    """Isolated tree with a fully published, ephemeral-key-signed Y state."""
    key, pub, raw = ephemeral_key()
    root = stage_repo(tmp, pub_b64=pub)
    registry = json.loads((root / "catalog" / "skills.json").read_bytes())
    entry = qualified_entry(registry)
    files, data = stage_package(root, entry)
    stage_review(root, key, files, data, entry)
    snapshot = freeze_snapshot(root, pathlib.Path(tmp) / "snapshot-x")
    code, out = release_cli(root, snapshot, root / "out", sign_raw=raw)
    assert code == 0, out
    for src in sorted((root / "out").rglob("*")):
        if src.is_file():
            rel = src.relative_to(root / "out")
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, target)
    shutil.rmtree(root / "out")
    shutil.rmtree(snapshot)
    return root, key, pub, raw


class TestSourceCommitWireShape(unittest.TestCase):
    """Rename + semantics at the validator level."""

    def setUp(self):
        self.registry = json.loads((REPO / "catalog" / "skills.json").read_bytes())

    def test_production_feed_serializes_source_commit(self):
        feed = hubcore.build_catalog(self.registry, "ios", "production", [], SOURCE_X)
        self.assertEqual(feed["sourceCommit"], SOURCE_X)
        self.assertNotIn("catalogCommit", feed)

    def test_legacy_catalog_commit_key_fails_validation(self):
        feed = hubcore.build_catalog(self.registry, "ios", "production", [], SOURCE_X)
        drifted = dict(feed)
        drifted.pop("sourceCommit")
        drifted["catalogCommit"] = SOURCE_X
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_catalog(drifted, channel="ios")

    def test_fixture_feed_keeps_null_source_commit(self):
        for rel in ("catalog.json", "android/catalog.json"):
            feed = json.loads((REPO / "tests" / "catalog" / "fixtures" / rel).read_bytes())
            self.assertIsNone(feed["sourceCommit"])
            self.assertNotIn("catalogCommit", feed)

    def test_no_catalog_commit_string_remains_in_hub_sources(self):
        roots = [REPO / "scripts", REPO / "schema", REPO / "catalog",
                 REPO / "tests" / "catalog", REPO / "docs" / "CATALOG-CONTRACT.md",
                 REPO / ".github" / "workflows" / "catalog.yml"]
        stale = []
        for root in roots:
            for path in (root.rglob("*") if root.is_dir() else [root]):
                if (path.is_file() and "__pycache__" not in path.parts
                        and path.suffix != ".zip"
                        # this file deliberately references the retired key name
                        # to prove it fails validation:
                        and path.name != "test_publication_integrity.py"
                        and b"catalogCommit" in path.read_bytes()):
                    stale.append(str(path.relative_to(REPO)))
        self.assertEqual(stale, [])

    def test_fixture_sample_rebuilds_with_source_commit_field(self):
        import make_fixture
        outputs = make_fixture.build_outputs()
        for rel in ("catalog.json", "android/catalog.json"):
            feed = json.loads(outputs[rel])
            self.assertIsNone(feed["sourceCommit"])
            self.assertNotIn("catalogCommit", feed)


class TestCliSourceCommitArguments(unittest.TestCase):
    def test_cli_accepts_hub_commit_alias_with_identical_bytes(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            code, out = run_script(REPO, "build_catalog.py",
                                   ["--mode", "preview", "--source-commit", SOURCE_X,
                                    "--out-root", a])
            self.assertEqual(code, 0, out)
            code, out = run_script(REPO, "build_catalog.py",
                                   ["--mode", "preview", "--hub-commit", SOURCE_X,
                                    "--out-root", b])
            self.assertEqual(code, 0, out)
            for name in ("catalog.json", "android/catalog.json"):
                self.assertEqual((pathlib.Path(a) / name).read_bytes(),
                                 (pathlib.Path(b) / name).read_bytes())

    def test_cli_requires_source_commit(self):
        code, out = run_script(REPO, "build_catalog.py",
                               ["--mode", "preview", "--out-root",
                                tempfile.mkdtemp(prefix="hub-nocommit-")])
        self.assertNotEqual(code, 0)
        self.assertIn("source-commit", out.lower())

    def test_release_refuses_without_frozen_source_snapshot(self):
        # honest X binding: no arbitrary X may be claimed over mutable-tree bytes
        with tempfile.TemporaryDirectory() as tmp:
            root = stage_repo(tmp, pub_b64=ephemeral_key()[1])
            code, out = run_script(root, "build_catalog.py",
                                   ["--mode", "release", "--source-commit", SOURCE_X,
                                    "--out-root", str(root / "out")])
            self.assertNotEqual(code, 0)
            self.assertIn("--source-snapshot", out)
            self.assertFalse((root / "out" / "catalog.json").exists())

    def test_release_payload_comes_from_snapshot_not_mutable_tree(self):
        key, pub, raw = ephemeral_key()
        with tempfile.TemporaryDirectory() as tmp:
            root = stage_repo(tmp, pub_b64=pub)
            registry = json.loads((root / "catalog" / "skills.json").read_bytes())
            entry = qualified_entry(registry)
            files, data = stage_package(root, entry)
            stage_review(root, key, files, data, entry)
            snapshot = freeze_snapshot(root, pathlib.Path(tmp) / "frozen-x")
            first = pathlib.Path(tmp) / "out1"
            code, out = release_cli(root, snapshot, first, sign_raw=raw)
            self.assertEqual(code, 0, out)
            # advance the mutable candidate tree AFTER the freeze: same snapshot
            # must still produce byte-identical release payloads.
            (root / "packages" / "floe-pdf" / QUALIFIED_VERSION / "floe-pdf.zip").unlink()
            advanced = synthetic_registry()
            for e in advanced["skills"]:
                if e["id"] == "floe-pdf":
                    e["versionTarget"] = "1.4.0"
            (root / "catalog" / "skills.json").write_bytes(hubcore.encoded(advanced))
            second = pathlib.Path(tmp) / "out2"
            code, out = release_cli(root, snapshot, second, sign_raw=raw)
            self.assertEqual(code, 0, out)
            for name in ("catalog.json", "catalog.sig", "android/catalog.json",
                         "android/catalog.sig"):
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes(),
                                 name)
            # the tree no longer matches the claimed X content, so building from
            # the (now-different) tree as "snapshot" must honestly fail — a
            # missing archive for the claimed version, never a fabricated feed.
            code, out = release_cli(root, root, pathlib.Path(tmp) / "out3", sign_raw=raw)
            self.assertNotEqual(code, 0)

    def test_check_mode_never_writes_publication_paths(self):
        snapshot = {}
        for root in (REPO / "scripts", REPO / "schema", REPO / "tests" / "catalog",
                     REPO / "catalog"):
            for path in root.rglob("*"):
                if path.is_file() and "__pycache__" not in path.parts:
                    snapshot[str(path)] = base64.b64encode(
                        hashlib_bytes(path.read_bytes())).decode()
        run_script(REPO, "build_catalog.py", ["--mode", "preview",
                                              "--source-commit", SOURCE_X, "--check"])
        run_script(REPO, "build_catalog.py", ["--mode", "release",
                                              "--source-commit", SOURCE_X, "--check"])
        for path, digest in snapshot.items():
            self.assertEqual(base64.b64encode(
                hashlib_bytes(pathlib.Path(path).read_bytes())).decode(), digest, path)
        self.assertFalse((REPO / "catalog.json").exists())


def hashlib_bytes(data):
    import hashlib
    return hashlib.sha256(data).digest()


class TestConfiguredPublicTrust(unittest.TestCase):
    def test_load_trust_matches_canonical_public_root(self):
        # The expected identity/key is this test's own immutable baseline,
        # never a value discovered at runtime, so a clean CI checkout cannot
        # silently accept whatever key file happens to be present.
        self.assertEqual(CANONICAL_ROOT_KEY_ID, hubcore.PRODUCTION_KEY_ID)
        self.assertNotEqual(CANONICAL_ROOT_KEY_ID, hubcore.FIXTURE_KEY_ID)
        self.assertNotEqual(CANONICAL_ROOT_PUBLIC_B64,
                            hubcore.fixture_public_b64())
        canonical_raw = base64.b64decode(CANONICAL_ROOT_PUBLIC_B64,
                                         validate=True)
        self.assertEqual(len(canonical_raw), 32)  # raw Ed25519 material
        self.assertEqual(
            base64.b64encode(canonical_raw).decode(),
            CANONICAL_ROOT_PUBLIC_B64)  # canonical strict base64 form

        # The committed Hub trust file must carry exactly the canonical
        # identity/key in the documented two-field shape.
        doc = json.loads((REPO / "public-key.json").read_bytes())
        self.assertEqual(doc, {"keyID": CANONICAL_ROOT_KEY_ID,
                               "publicKey": CANONICAL_ROOT_PUBLIC_B64})

        # And the production trust load must resolve to that single root.
        trust = build_catalog.load_trust(REPO)
        self.assertEqual(trust, {CANONICAL_ROOT_KEY_ID:
                                 CANONICAL_ROOT_PUBLIC_B64})
        self.assertEqual(list(trust), [hubcore.PRODUCTION_KEY_ID])

    def test_load_trust_rejects_fixture_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / "public-key.json").write_bytes(
                trust_file(hubcore.fixture_public_b64(), hubcore.FIXTURE_KEY_ID))
            with self.assertRaises(hubcore.HubError):
                build_catalog.load_trust(tmp)

    def test_load_trust_rejects_malformed_key_material(self):
        for doc in ({"keyID": "k", "publicKey": "not-base64!!"},
                    {"keyID": "k", "publicKey": base64.b64encode(b"short").decode()},
                    {"keyID": "k"}, {"publicKey": "A" * 44}):
            with self.subTest(doc=doc):
                with tempfile.TemporaryDirectory() as tmp:
                    (pathlib.Path(tmp) / "public-key.json").write_bytes(
                        hubcore.encoded(doc))
                    with self.assertRaises(hubcore.HubError):
                        build_catalog.load_trust(tmp)

    def test_absent_trust_is_empty_and_release_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = stage_repo(tmp, pub_b64=None)
            self.assertEqual(build_catalog.load_trust(root), {})
            registry = json.loads((root / "catalog" / "skills.json").read_bytes())
            entry = qualified_entry(registry)
            files, data = stage_package(root, entry)
            key, pub, raw = ephemeral_key()
            stage_review(root, key, files, data, entry)
            snapshot = freeze_snapshot(root, pathlib.Path(tmp) / "frozen-x")
            code, out = release_cli(root, snapshot, root / "out")
            self.assertNotEqual(code, 0)
            self.assertIn("unknown signing keyID", out)
            self.assertFalse((root / "out" / "catalog.json").exists())


class TestSigningIdentityGate(unittest.TestCase):
    """The real CLI refuses to sign under an identity outside the trust file."""

    def test_signing_key_must_match_configured_trust(self):
        key, pub, _raw = ephemeral_key()
        _other, _p, raw_b = ephemeral_key()
        with tempfile.TemporaryDirectory() as tmp:
            root = stage_repo(tmp, pub_b64=pub)
            registry = json.loads((root / "catalog" / "skills.json").read_bytes())
            entry = qualified_entry(registry)
            files, data = stage_package(root, entry)
            stage_review(root, key, files, data, entry)  # reviews match the trust
            snapshot = freeze_snapshot(root, pathlib.Path(tmp) / "frozen-x")
            code, out = release_cli(root, snapshot, root / "out", sign_raw=raw_b)
            self.assertNotEqual(code, 0)
            self.assertIn("does not match", out)
            self.assertFalse((root / "out" / "catalog.sig").exists())

    def test_signing_refused_without_configured_trust(self):
        key, _pub, raw = ephemeral_key()
        with tempfile.TemporaryDirectory() as tmp:
            root = stage_repo(tmp, pub_b64=None)
            registry = json.loads((root / "catalog" / "skills.json").read_bytes())
            entry = qualified_entry(registry)
            files, data = stage_package(root, entry)
            stage_review(root, key, files, data, entry)
            snapshot = freeze_snapshot(root, pathlib.Path(tmp) / "frozen-x")
            code, out = release_cli(root, snapshot, root / "out", sign_raw=raw)
            self.assertNotEqual(code, 0)
            # fail-closed before signing: either no trust for reviews, or no
            # configured production identity for the sign step.
            self.assertTrue("does not configure" in out or "unknown signing keyID" in out)

    def test_real_cli_release_signs_and_verifies_under_matching_trust(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _key, _pub, _raw = published_repo(tmp)
            body = (root / "catalog.json").read_bytes()
            envelope = (root / "catalog.sig").read_bytes()
            trust = build_catalog.load_trust(root)
            self.assertEqual(hubcore.verify_envelope(body, envelope, trust),
                             hubcore.PRODUCTION_KEY_ID)
            for prefix in ("", "android/"):
                feed = json.loads((root / (prefix + "catalog.json")).read_bytes())
                self.assertEqual(feed["sourceCommit"], SOURCE_X)
                floe_pdf = next(e for e in feed["entries"] if e["id"] == "floe-pdf")
                self.assertEqual(floe_pdf["installOffer"], "qualified")
                self.assertNotEqual(floe_pdf["review"]["keyID"], hubcore.FIXTURE_KEY_ID)

    def test_release_refuses_review_signed_by_untrusted_key(self):
        _key_a, pub_a, _raw_a = ephemeral_key()
        key_b, _pub_b, _raw_b = ephemeral_key()
        with tempfile.TemporaryDirectory() as tmp:
            root = stage_repo(tmp, pub_b64=pub_a)
            registry = json.loads((root / "catalog" / "skills.json").read_bytes())
            entry = qualified_entry(registry)
            files, data = stage_package(root, entry)
            stage_review(root, key_b, files, data, entry)  # wrong key, same keyID
            snapshot = freeze_snapshot(root, pathlib.Path(tmp) / "frozen-x")
            code, out = release_cli(root, snapshot, root / "out")
            self.assertNotEqual(code, 0)
            self.assertIn("signature verification failed", out)
            self.assertFalse((root / "out" / "catalog.json").exists())


class TestPublicationGate(unittest.TestCase):
    """check_catalog's production branch on actual published-byte trees."""

    def test_full_published_pair_passes_the_real_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, *_ = published_repo(tmp)
            code, out = run_script(root, "check_catalog.py", [])
            self.assertEqual(code, 0, out)
            self.assertIn("audited sourceCommit", out)
            self.assertIn("production feed present", out)

    def test_valid_publication_survives_unreviewed_registry_advance(self):
        # coordinator-required regression: a lane staging the next unreviewed
        # version on candidate HEAD must not invalidate the signed publication,
        # must not produce an unreviewed offer, and must not be used to
        # regenerate the production feed.
        with tempfile.TemporaryDirectory() as tmp:
            root, *_ = published_repo(tmp)
            before = {rel: (root / rel).read_bytes() for rel in
                      ("catalog.json", "catalog.sig", "android/catalog.json",
                       "android/catalog.sig")}
            registry = json.loads((root / "catalog" / "skills.json").read_bytes())
            for e in registry["skills"]:
                if e["id"] == "floe-pdf":
                    e["versionTarget"] = "1.4.0"          # pending next version
                    e["status"] = dict(e["status"], packaged=False, reviewed=False,
                                       qualified=False, adaptation="in-progress")
            (root / "catalog" / "skills.json").write_bytes(hubcore.encoded(registry))
            code, out = run_script(root, "check_catalog.py", [])
            self.assertEqual(code, 0, out)
            for rel, blob in before.items():
                self.assertEqual((root / rel).read_bytes(), blob,
                                 f"gate mutated published bytes: {rel}")
            feed = json.loads((root / "catalog.json").read_bytes())
            entry = next(e for e in feed["entries"] if e["id"] == "floe-pdf")
            self.assertEqual(entry["installOffer"], "qualified")  # old published truth
            self.assertEqual(entry["version"], QUALIFIED_VERSION)
            self.assertNotIn("1.4.0", json.dumps(feed))

    def test_missing_root_signature_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, *_ = published_repo(tmp)
            (root / "catalog.sig").unlink()
            code, out = run_script(root, "check_catalog.py", [])
            self.assertNotEqual(code, 0)
            self.assertIn("ios feed published without its signature", out)

    def test_missing_android_signature_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, *_ = published_repo(tmp)
            (root / "android" / "catalog.sig").unlink()
            code, out = run_script(root, "check_catalog.py", [])
            self.assertNotEqual(code, 0)
            self.assertIn("android feed published without its signature", out)

    def _tamper_feed(self, path):
        # keep the bytes valid JSON/canonical, change content: only the
        # exact-byte signature can catch this, never a re-parse-and-rebuild
        feed = json.loads(path.read_bytes())
        for e in feed["entries"]:
            if e["id"] == "floe-pdf":
                e["installOffer"] = "none"
        path.write_bytes(hubcore.encoded(feed))

    def test_tampered_android_feed_fails_exact_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, *_ = published_repo(tmp)
            self._tamper_feed(root / "android" / "catalog.json")
            code, out = run_script(root, "check_catalog.py", [])
            self.assertNotEqual(code, 0)
            self.assertIn("android catalog signature invalid", out)

    def test_tampered_root_feed_fails_exact_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, *_ = published_repo(tmp)
            self._tamper_feed(root / "catalog.json")
            code, out = run_script(root, "check_catalog.py", [])
            self.assertNotEqual(code, 0)
            self.assertIn("ios catalog signature invalid", out)

    def test_noncanonical_feed_bytes_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, key, pub, _raw = published_repo(tmp)
            path = root / "catalog.json"
            feed = json.loads(path.read_bytes())
            pretty = (json.dumps(feed, ensure_ascii=False, sort_keys=True, indent=1)
                      + "\n").encode()
            path.write_bytes(pretty)
            (root / "catalog.sig").write_bytes(
                hubcore.sign_envelope(pretty, key, hubcore.PRODUCTION_KEY_ID))
            code, out = run_script(root, "check_catalog.py", [])
            self.assertNotEqual(code, 0)
            self.assertTrue("not canonical" in out or "shape invalid" in out or
                            "counts drifted" in out or "feed shape" in out,
                            out)

    def test_wrong_key_android_signature_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, *_ = published_repo(tmp)
            other, _p, _r = ephemeral_key()
            (root / "android" / "catalog.sig").write_bytes(
                hubcore.sign_envelope((root / "android" / "catalog.json").read_bytes(),
                                      other, hubcore.PRODUCTION_KEY_ID))
            code, out = run_script(root, "check_catalog.py", [])
            self.assertNotEqual(code, 0)
            self.assertIn("android catalog signature invalid", out)

    def test_fixture_identity_signature_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, *_ = published_repo(tmp)
            (root / "catalog.sig").write_bytes(
                hubcore.sign_envelope((root / "catalog.json").read_bytes(),
                                      hubcore.fixture_private_key(),
                                      hubcore.FIXTURE_KEY_ID))
            code, out = run_script(root, "check_catalog.py", [])
            self.assertNotEqual(code, 0)
            self.assertIn("ios catalog signature invalid", out)

    def test_published_without_trust_config_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, *_ = published_repo(tmp)
            (root / "public-key.json").unlink()
            code, out = run_script(root, "check_catalog.py", [])
            self.assertNotEqual(code, 0)
            self.assertIn("no public-key.json trust", out)

    def test_tampered_published_archive_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, *_ = published_repo(tmp)
            path = root / "packages" / "floe-pdf" / QUALIFIED_VERSION / "floe-pdf.zip"
            path.write_bytes(path.read_bytes() + b"x")
            code, out = run_script(root, "check_catalog.py", [])
            self.assertNotEqual(code, 0)
            self.assertIn("ios/floe-pdf", out)
            self.assertIn("sha256", out)

    def test_missing_bound_archive_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, *_ = published_repo(tmp)
            (root / "android" / "packages" / "floe-pdf" / QUALIFIED_VERSION /
             "floe-pdf.zip").unlink()
            code, out = run_script(root, "check_catalog.py", [])
            self.assertNotEqual(code, 0)
            self.assertIn("android/floe-pdf", out)

    def test_feed_only_publication_still_requires_android_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, *_ = published_repo(tmp)
            (root / "android" / "catalog.json").unlink()
            (root / "android" / "catalog.sig").unlink()
            code, out = run_script(root, "check_catalog.py", [])
            self.assertNotEqual(code, 0)
            self.assertIn("android channel published but feed missing", out)


class TestXPinnedYPublication(unittest.TestCase):
    """Meaningful audited-source X -> artifact commit Y -> pinned fetch flow."""

    def git(self, root, *args):
        proc = subprocess.run(["git", "-c", "user.name=H1PublicationTest",
                               "-c", "user.email=h1-test@invalid", "-C", str(root)]
                              + list(args), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return proc.stdout.strip()

    def fetch_at(self, repo, rev, dest):
        archive = subprocess.run(["git", "-C", str(repo), "archive", rev],
                                 capture_output=True)
        self.assertEqual(archive.returncode, 0, archive.stderr.decode())
        dest.mkdir(parents=True, exist_ok=True)
        subprocess.run(["tar", "-x", "-C", str(dest)], input=archive.stdout, check=True)
        return dest

    def test_pinned_fetch_at_y_verifies_regardless_of_mutable_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp) / "hub"
            repo.mkdir()
            key, pub, raw = ephemeral_key()
            root = stage_repo(str(repo), pub_b64=pub)
            registry = json.loads((root / "catalog" / "skills.json").read_bytes())
            entry = qualified_entry(registry)
            files, data = stage_package(root, entry)
            stage_review(root, key, files, data, entry)
            self.git(root, "init", "-q", "-b", "main")
            self.git(root, "add", "-A")
            self.git(root, "commit", "-q", "-m", "audited source X")
            x = self.git(root, "rev-parse", "HEAD")
            self.assertEqual(len(x), 40)
            # publication run: freeze X, build from exactly that snapshot, sign,
            # then commit the outputs — the feed must not contain its own commit.
            snapshot = self.fetch_at(repo, x, pathlib.Path(tmp) / "snapshot-x")
            staging = pathlib.Path(tmp) / "staging"
            code, out = release_cli(repo, snapshot, staging, sign_raw=raw,
                                    source_commit=x)
            self.assertEqual(code, 0, out)
            for src in sorted(staging.rglob("*")):
                if src.is_file():
                    rel = src.relative_to(staging)
                    target = repo / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(src, target)
            self.git(root, "add", "-A")
            self.git(root, "commit", "-q", "-m", "published artifacts Y")
            y = self.git(root, "rev-parse", "HEAD")
            self.assertNotEqual(x, y, "publication commit must be distinct")
            self.git(root, "merge-base", "--is-ancestor", x, y)  # X is an ancestor of Y
            fetch_y = self.fetch_at(repo, y, pathlib.Path(tmp) / "fetch-y")
            feed = json.loads((fetch_y / "catalog.json").read_bytes())
            self.assertEqual(feed["sourceCommit"], x)
            self.assertNotEqual(feed["sourceCommit"], y)
            code, out = run_script(fetch_y, "check_catalog.py", [])
            self.assertEqual(code, 0, out)
            # advance the mutable head with an unreviewed candidate change plus
            # a tampered feed at head; the pinned Y fetch is unaffected and the
            # tampered head tree honestly fails.
            advanced = json.loads((repo / "catalog" / "skills.json").read_bytes())
            for e in advanced["skills"]:
                if e["id"] == "floe-pdf":
                    e["versionTarget"] = "1.4.0"
                    e["status"] = dict(e["status"], packaged=False, reviewed=False,
                                       qualified=False, adaptation="in-progress")
            (repo / "catalog" / "skills.json").write_bytes(hubcore.encoded(advanced))
            bad = json.loads((repo / "catalog.json").read_bytes())
            for e in bad["entries"]:
                if e["id"] == "floe-pdf":
                    e["installOffer"] = "none"
            (repo / "catalog.json").write_bytes(hubcore.encoded(bad))
            self.git(root, "add", "-A")
            self.git(root, "commit", "-q", "-m", "mutable head advance/tamper Z")
            code, out = run_script(fetch_y, "check_catalog.py", [])
            self.assertEqual(code, 0, out)  # pinned verification ignores mutable HEAD
            head_fetch = self.fetch_at(repo, self.git(root, "rev-parse", "HEAD"),
                                       pathlib.Path(tmp) / "fetch-head")
            code, out = run_script(head_fetch, "check_catalog.py", [])
            self.assertNotEqual(code, 0)
            self.assertIn("ios catalog signature invalid", out)


class TestWorkflowPinIntegrity(unittest.TestCase):
    def test_action_refs_are_immutable_pinned_shas(self):
        text = (REPO / ".github" / "workflows" / "catalog.yml").read_text()
        refs = [line.split("uses: ")[1].strip().split(" #")[0]
                for line in text.splitlines() if line.strip().startswith("- uses: ")]
        self.assertTrue(refs, "workflow must run the gates")
        for ref in refs:
            self.assertRegex(ref, r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+@[0-9a-f]{40}$",
                             f"mutable action tag must be replaced by a pinned SHA: {ref}")


class TestFixtureTrustBoundary(unittest.TestCase):
    def test_fixture_public_key_never_loads_as_production_trust(self):
        doc = json.loads((REPO / "tests" / "catalog" / "fixtures" /
                          "fixture-public-key.json").read_bytes())
        self.assertTrue(doc["fixtureOnly"] and doc["notATrustRoot"])
        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / "public-key.json").write_bytes(hubcore.encoded(
                {"keyID": doc["keyID"], "publicKey": doc["publicKey"]}))
            with self.assertRaises(hubcore.HubError):
                build_catalog.load_trust(tmp)

    def test_fixture_feed_signature_never_verifies_under_production_trust(self):
        body = (REPO / "tests" / "catalog" / "fixtures" / "catalog.json").read_bytes()
        envelope = (REPO / "tests" / "catalog" / "fixtures" / "catalog.sig").read_bytes()
        trust = build_catalog.load_trust(REPO)
        with self.assertRaises(hubcore.HubError):
            hubcore.verify_envelope(body, envelope, trust)


if __name__ == "__main__":
    unittest.main()
