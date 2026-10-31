#!/usr/bin/env python3
"""Publication-immutability guard tests: module semantics AND the real signer.

Root's architecture review found that a CLI-only guard is not enforcement: the
actual trusted signing entry point is ``sign_publication.run_catalog_mode``,
which calls ``build_catalog.build`` directly, and a baseline taken from the
latest feed of a frozen tooling checkout loses history for versions published
after that pin or removed from the latest feed. These tests therefore cover
BOTH levels:

  1. module semantics — the cumulative ledger is verified row-by-row against
     the signed feed bytes at its pinned publication commit, merged with the
     verified current publication (working tree OR an explicitly resolved
     published-Y pin), and refuses: re-signed same (channel,id,version) with
     changed bytes, tampered/unverifiable rows, a stale ledger that does not
     cover the current publication, and production history without a ledger
     (no first-publication downgrade). Unchanged bytes, genuinely new versions
     and versions removed from the latest feed but retained in the ledger keep
     their exact semantics.
  2. the ACTUAL signer API — the data-only bridge is run as a subprocess over
     disposable Git repositories exactly as the coordinator runs it, proving
     the gate fires inside ``run_catalog_mode`` before any signature exists,
     that a ledger planted in the caller's data checkout X is never used, and
     that a missing ledger beside published history refuses.

Ephemeral public-knowledge test keys configure a disposable tooling root under
the official keyID; the production pinned root is never used, weakened or
copied. Real repository probes are strictly read-only.
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
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERE / "scripts"))
sys.path.insert(0, str(HERE / "tests" / "catalog"))
import fixture_status  # noqa: E402
import admission_baseline as BASE  # noqa: E402
import hubcore  # noqa: E402
import publication_immutability as pi  # noqa: E402
import sign_publication  # noqa: E402

OFFICIAL_ORIGIN = "https://github.com/JiangNanGenius/floe-skill-hub.git"
KEY_ID = hubcore.PRODUCTION_KEY_ID
REVIEWED_AT = "2026-10-27"
REVIEWER = "immutability-fixture-reviewer"
REAL_REGISTRY = json.loads((HERE / "tests/catalog/fixtures/reviewed-registry-2026-10-31.json").read_bytes())

TEST_SEED = hashlib.sha256(
    b"floe-skill-hub immutability ephemeral TEST key -- NOT production").digest()
FOREIGN_SEED = hashlib.sha256(
    b"floe-skill-hub immutability ephemeral FOREIGN key -- NOT production").digest()

GUIDE_ID = "doc-coauthoring"
SYNTHETIC_VERSION = "9.9.9"
NEW_VERSION = "9.9.10"


def _key(seed):
    Ed25519PrivateKey, _, serialization, _ = hubcore._load_ed25519()
    key = Ed25519PrivateKey.from_private_bytes(seed)
    public = key.public_key().public_bytes(serialization.Encoding.Raw,
                                           serialization.PublicFormat.Raw)
    return key, base64.b64encode(public).decode()


def _git(where, *args):
    proc = subprocess.run(["git", "-C", str(where)] + list(args),
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError(f"fixture git failed: {args}: {proc.stderr}")
    return proc.stdout


def _commit_all(path, message="fixture snapshot"):
    _git(path, "add", "-A")
    _git(path, "-c", "user.name=floe-immutability-fixture",
         "-c", "user.email=fixture@invalid", "commit", "-q", "-m", message)
    return _git(path, "rev-parse", "HEAD").strip()


def _init_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    _git(path, "remote", "add", "origin", OFFICIAL_ORIGIN)
    return path


# --- synthetic feed helpers (module-level scenarios) -----------------------

def feed_entry(skill_id, version, digest, channel, plan=1):
    return {
        "id": skill_id, "planNumber": plan, "kind": "optional", "source": "A",
        "name": {"en": skill_id, "zh-Hans": skill_id},
        "description": {"en": "t", "zh-Hans": "t"},
        "category": hubcore.CATEGORIES[0],
        "tags": ["test", "fixture"], "deepAdaptation": False,
        "upstream": None, "firstParty": None,
        "runtime": {"scriptRuntime": "none", "capabilities": [], "tools": [],
                    "installPlatforms": [channel], "pythonPackagesPlan": [],
                    "execution": {"os": None, "arch": "n/a", "evidence": "unproven"}},
        "version": version, "minimumAppVersion": "1.7.0",
        "status": {"sourcePinned": True, "licenseChecked": True,
                   "adaptation": "hub-native", "packaged": True, "reviewed": False,
                   "qualified": False, "published": True, "executionVerified": False},
        "notes": {"en": "", "zh-Hans": ""},
        "package": {"path": hubcore.package_path_for(skill_id, version, channel),
                    "size": 4, "sha256": "a" * 64, "contentDigest": digest,
                    "containsScripts": False},
        "review": None, "installOffer": "none",
    }


def feed(channel, entries):
    counts = {
        "total": len(entries),
        "builtin": sum(1 for e in entries if e["kind"] == "builtin"),
        "optional": sum(1 for e in entries if e["kind"] == "optional"),
        "deepAdaptation": sum(1 for e in entries if e["deepAdaptation"]),
        "packaged": sum(1 for e in entries if e["package"]),
        "reviewed": sum(1 for e in entries if e["review"]),
        "qualified": sum(1 for e in entries if e["status"]["qualified"]),
        "offerQualified": sum(1 for e in entries if e["installOffer"] == "qualified"),
    }
    return {"schemaVersion": hubcore.CATALOG_SCHEMA_VERSION,
            "publisher": "JiangNanGenius", "channel": channel,
            "feedStatus": "production",
            "hubRepository": "JiangNanGenius/floe-skill-hub",
            "sourceCommit": "d" * 40, "permissionPolicy": hubcore.PERMISSION_POLICY,
            "entries": entries, "counts": counts}


class LedgerFixture(unittest.TestCase):
    """Disposable tooling root (real Git repo) with signed published history."""

    maxDiff = None

    def setUp(self):
        self._tmp = pathlib.Path(tempfile.mkdtemp(prefix="hub-immut-"))
        self.root = _init_repo(self._tmp / "tooling")
        (self.root / "scripts").mkdir()
        for name in ("catalog_views.py", "hubcore.py", "build_catalog.py", "runtime_dependency.py",
                     "dependency_declaration.py", "publication_immutability.py",
                     "sign_publication.py"):
            shutil.copy(HERE / "scripts" / name, self.root / "scripts" / name)
        self.key, public = _key(TEST_SEED)
        (self.root / "public-key.json").write_bytes(hubcore.encoded(
            {"keyID": KEY_ID, "publicKey": public}))
        self.tooling_commit = _commit_all(self.root, "fixture tooling pin")
        self.digest_a = "1" * 64
        self.digest_b = "2" * 64

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    # -- publication helpers -------------------------------------------------
    def write_feed(self, channel, entries):
        """Write+sign one channel feed pair into the tooling root (no commit)."""
        body = hubcore.encoded(feed(channel, entries))
        prefix = "" if channel == "ios" else "android/"
        target = self.root / prefix
        target.mkdir(parents=True, exist_ok=True)
        (target / "catalog.json").write_bytes(body)
        (target / "catalog.sig").write_bytes(
            hubcore.sign_envelope(body, self.key, KEY_ID))
        return body

    def publish(self, channel, entries):
        self.write_feed(channel, entries)
        return _commit_all(self.root, f"publish {channel}")

    def publish_pair(self, entries_by_channel):
        """One publication commit carrying BOTH channel feeds (one Y pin)."""
        for channel, entries in entries_by_channel.items():
            self.write_feed(channel, entries)
        return _commit_all(self.root, "publication generation")

    def write_ledger(self, rows, commit=True):
        (self.root / "catalog").mkdir(exist_ok=True)
        (self.root / pi.LEDGER_REL).write_bytes(pi.render_ledger(rows))
        return _commit_all(self.root, "ledger") if commit else None

    def ledger_rows_for(self, pin, channels=("ios", "android")):
        return [pi.build_ledger_row(self.root, pin, channel) for channel in channels]


class ModuleSemanticsTests(LedgerFixture):
    def test_git_environment_cannot_redirect_historical_objects(self):
        pin = self._pair([feed_entry("skill-a", "1.0.0", self.digest_a, "ios")])
        expected = pi.build_ledger_row(self.root, pin, "ios")
        trap = _init_repo(self._tmp / "unrelated-git-dir")
        with mock.patch.dict(os.environ, {
                "GIT_DIR": str(trap / ".git"), "GIT_WORK_TREE": str(trap)}):
            self.assertEqual(pi.build_ledger_row(self.root, pin, "ios"), expected)

    def test_replace_ref_cannot_forge_a_historical_publication(self):
        old = self._pair([feed_entry("skill-a", "1.0.0", self.digest_a, "ios")])
        replacement = self._pair([
            feed_entry("skill-a", "1.0.0", self.digest_b, "ios")])
        rows = self.ledger_rows_for(replacement)
        for row in rows:
            row["publication"] = old
        _git(self.root, "replace", old, replacement)
        self.write_ledger(rows)
        with self.assertRaises(hubcore.HubError):
            pi.build_validated_baseline(self.root)

    def test_partial_old_publication_cannot_drop_a_removed_offer(self):
        old = self._pair([
            feed_entry("skill-a", "1.0.0", self.digest_a, "ios"),
            feed_entry("skill-b", "1.0.0", self.digest_b, "ios")])
        old_rows = self.ledger_rows_for(old)
        current = self._pair([
            feed_entry("skill-b", "1.0.0", self.digest_b, "ios")])
        for row in old_rows:
            row["offers"] = [o for o in row["offers"] if o["id"] == "skill-b"]
        self.write_ledger(old_rows + self.ledger_rows_for(current))
        with self.assertRaisesRegex(hubcore.HubError, "every packaged offer"):
            pi.build_validated_baseline(self.root)

    def test_ledger_rows_cannot_be_removed_after_unrelated_commits(self):
        old = self._pair([feed_entry("skill-a", "1.0.0", self.digest_a, "ios")])
        old_rows = self.ledger_rows_for(old)
        self.write_ledger(old_rows)
        current = self._pair([
            feed_entry("skill-a", "2.0.0", self.digest_b, "ios")])
        current_rows = self.ledger_rows_for(current)
        self.write_ledger(old_rows + current_rows)
        self.write_ledger(current_rows)
        (self.root / "editorial-note.txt").write_text("unrelated metadata\n")
        _commit_all(self.root, "unrelated editorial change")
        with self.assertRaisesRegex(hubcore.HubError, "append-only"):
            pi.build_validated_baseline(self.root)

    def _pair(self, ios_entries, android_entries=None):
        return self.publish_pair({
            "ios": ios_entries,
            "android": android_entries if android_entries is not None else [
                dict(e, runtime=dict(e["runtime"], installPlatforms=["android"]),
                     package=dict(e["package"],
                                  path=hubcore.package_path_for(e["id"], e["version"],
                                                                "android")))
                for e in ios_entries]})

    def test_first_publication_without_history_allowed(self):
        baseline = pi.build_validated_baseline(self.root)
        self.assertEqual(baseline, {})
        candidate = {"catalog.json": hubcore.encoded(
            feed("ios", [feed_entry("skill-a", "1.0.0", self.digest_b, "ios")]))}
        self.assertTrue(pi.assert_immutable_publication(candidate, baseline))

    def test_unchanged_and_new_version_allowed(self):
        pin = self._pair([feed_entry("skill-a", "1.0.0", self.digest_a, "ios")])
        self.write_ledger(self.ledger_rows_for(pin))
        baseline = pi.build_validated_baseline(self.root)
        same = {"catalog.json": hubcore.encoded(
            feed("ios", [feed_entry("skill-a", "1.0.0", self.digest_a, "ios")]))}
        self.assertTrue(pi.assert_immutable_publication(same, baseline))
        newer = {"catalog.json": hubcore.encoded(
            feed("ios", [feed_entry("skill-a", "1.1.0", self.digest_b, "ios")]))}
        self.assertTrue(pi.assert_immutable_publication(newer, baseline))

    def test_resigned_same_version_changed_bytes_refused(self):
        pin = self._pair([feed_entry("skill-a", "1.0.0", self.digest_a, "ios")])
        self.write_ledger(self.ledger_rows_for(pin))
        baseline = pi.build_validated_baseline(self.root)
        resigned = {"catalog.json": hubcore.encoded(
            feed("ios", [feed_entry("skill-a", "1.0.0", self.digest_b, "ios")]))}
        with self.assertRaises(hubcore.HubError):
            pi.assert_immutable_publication(resigned, baseline)

    def test_per_channel_identity_is_preserved(self):
        pin = self.publish_pair({
            "ios": [feed_entry("skill-a", "1.0.0", self.digest_a, "ios")],
            "android": [feed_entry("skill-a", "1.0.0", self.digest_b, "android")]})
        self.write_ledger(self.ledger_rows_for(pin))
        baseline = pi.build_validated_baseline(self.root)
        self.assertEqual(baseline[("ios", "skill-a", "1.0.0")], self.digest_a)
        self.assertEqual(baseline[("android", "skill-a", "1.0.0")], self.digest_b)
        # the Android digest is not an iOS fact and vice versa
        with self.assertRaises(hubcore.HubError):
            pi.assert_immutable_publication(
                {"catalog.json": hubcore.encoded(
                    feed("ios", [feed_entry("skill-a", "1.0.0", self.digest_b, "ios")]))},
                baseline)

    def test_version_removed_from_latest_feed_stays_immutable(self):
        gen1 = self._pair([feed_entry("skill-a", "1.0.0", self.digest_a, "ios")])
        rows = self.ledger_rows_for(gen1)
        # second generation drops skill-a entirely from both feeds
        gen2 = self._pair([feed_entry("skill-b", "1.0.0", self.digest_b, "ios")])
        rows += self.ledger_rows_for(gen2)
        self.write_ledger(rows)
        baseline = pi.build_validated_baseline(self.root)
        self.assertIn(("ios", "skill-a", "1.0.0"), baseline)
        with self.assertRaises(hubcore.HubError):
            pi.assert_immutable_publication(
                {"catalog.json": hubcore.encoded(
                    feed("ios", [feed_entry("skill-a", "1.0.0", self.digest_b, "ios"),
                                 feed_entry("skill-b", "1.0.0", self.digest_b, "ios", 2)]))},
                baseline)

    def test_missing_ledger_beside_history_fails_closed(self):
        self._pair([feed_entry("skill-a", "1.0.0", self.digest_a, "ios")])
        with self.assertRaises(hubcore.HubError) as ctx:
            pi.build_validated_baseline(self.root)
        self.assertIn("ledger", str(ctx.exception))

    def test_stale_tooling_ledger_fails_closed(self):
        """A tooling pin predating the latest publication cannot hide history:
        the ledger must cover the currently published offers."""
        gen1 = self._pair([feed_entry("skill-a", "1.0.0", self.digest_a, "ios")])
        self.write_ledger(self.ledger_rows_for(gen1))
        # a later publication adds skill-b but the (stale) ledger is not updated
        self._pair([feed_entry("skill-a", "1.0.0", self.digest_a, "ios"),
                    feed_entry("skill-b", "1.0.0", self.digest_b, "ios", 2)])
        with self.assertRaises(hubcore.HubError) as ctx:
            pi.build_validated_baseline(self.root)
        self.assertIn("does not cover", str(ctx.exception))

    def test_explicit_published_pin_beats_a_lying_working_tree(self):
        """The baseline can be anchored to an independently resolved published
        Y, so tampering with (or rolling back) the tooling working tree cannot
        weaken it."""
        pin = self._pair([feed_entry("skill-a", "1.0.0", self.digest_a, "ios")])
        self.write_ledger(self.ledger_rows_for(pin))
        # tamper with the working-tree feed bytes (signature no longer matches)
        self.write_feed("ios", [feed_entry("skill-a", "1.0.0", self.digest_b, "ios")])
        self.write_feed("android", [feed_entry("skill-a", "1.0.0", self.digest_b, "android")])
        with self.assertRaises(hubcore.HubError):
            pi.build_validated_baseline(self.root)
        baseline = pi.build_validated_baseline(self.root, published_pin=pin)
        self.assertEqual(baseline[("ios", "skill-a", "1.0.0")], self.digest_a)
        with self.assertRaises(hubcore.HubError):
            pi.assert_immutable_publication(
                {"catalog.json": hubcore.encoded(
                    feed("ios", [feed_entry("skill-a", "1.0.0", self.digest_b, "ios")]))},
                baseline)

    def test_tampered_ledger_row_digest_refused(self):
        pin = self._pair([feed_entry("skill-a", "1.0.0", self.digest_a, "ios")])
        rows = self.ledger_rows_for(pin)
        rows[0]["offers"][0]["contentDigest"] = self.digest_b
        (self.root / "catalog").mkdir(exist_ok=True)
        (self.root / pi.LEDGER_REL).write_bytes(pi.render_ledger(rows))
        _commit_all(self.root, "tampered ledger")
        with self.assertRaises(hubcore.HubError):
            pi.build_validated_baseline(self.root)

    def test_tampered_ledger_feed_hash_refused(self):
        pin = self._pair([feed_entry("skill-a", "1.0.0", self.digest_a, "ios")])
        rows = self.ledger_rows_for(pin)
        rows[0]["feedSha256"] = "9" * 64
        (self.root / "catalog").mkdir(exist_ok=True)
        (self.root / pi.LEDGER_REL).write_bytes(pi.render_ledger(rows))
        _commit_all(self.root, "tampered feed hash")
        with self.assertRaises(hubcore.HubError):
            pi.build_validated_baseline(self.root)

    def test_noncanonical_ledger_bytes_refused(self):
        pin = self._pair([feed_entry("skill-a", "1.0.0", self.digest_a, "ios")])
        rows = self.ledger_rows_for(pin)
        doc = json.loads(pi.render_ledger(rows))
        (self.root / "catalog").mkdir(exist_ok=True)
        (self.root / pi.LEDGER_REL).write_text(json.dumps(doc, indent=2) + "\n")
        _commit_all(self.root, "non-canonical ledger")
        with self.assertRaises(hubcore.HubError):
            pi.build_validated_baseline(self.root)

    def test_ledger_row_signed_by_foreign_key_refused(self):
        body = hubcore.encoded(
            feed("ios", [feed_entry("skill-a", "1.0.0", self.digest_a, "ios")]))
        foreign, _ = _key(FOREIGN_SEED)
        (self.root / "catalog.json").write_bytes(body)
        (self.root / "catalog.sig").write_bytes(
            hubcore.sign_envelope(body, foreign, KEY_ID))
        pin = _commit_all(self.root, "foreign-key publication")
        with self.assertRaises(hubcore.HubError):
            pi.build_ledger_row(self.root, pin, "ios")

    def test_unknown_pin_fails_closed(self):
        with self.assertRaises(hubcore.HubError):
            pi.build_ledger_row(self.root, "f" * 40, "ios")


class SignerApiTests(LedgerFixture):
    """The ACTUAL trusted signer path (sign_publication CLI subprocess)."""

    def _data_root(self, name, version, body_suffix, ledger_bytes=None):
        """Stage a clean data checkout X with exactly one qualified guide offer."""
        data = _init_repo(self._tmp / name)
        registry = fixture_status.stage_unadmitted_fixture(REAL_REGISTRY)
        entry = next(e for e in registry["skills"] if e["id"] == GUIDE_ID)
        entry["versionTarget"] = version
        entry["status"] = dict(entry["status"], licenseChecked=True, packaged=True,
                               reviewed=True, qualified=True)
        (data / "catalog").mkdir(parents=True)
        (data / "catalog" / "skills.json").write_bytes(hubcore.encoded(registry))
        if ledger_bytes is not None:
            # A caller-planted ledger inside X must never be trusted.
            (data / pi.LEDGER_REL).write_bytes(ledger_bytes)
        files = {
            "SKILL.md": (f"---\nname: {GUIDE_ID}\ndescription: Fixture guide package "
                         f"for the immutability tests.\n---\n\n{body_suffix}\n").encode(),
            "floe.json": json.dumps({
                "schemaVersion": 1, "id": GUIDE_ID, "version": version,
                "capabilities": [], "tools": [], "platforms": ["ios"],
                "scriptRuntime": "none", "pythonPackages": []}, sort_keys=True).encode(),
            "references/LICENSE.fixture.txt":
                b"Fixture-only license notice for the immutability tests.\n",
        }
        archive = hubcore.make_zip(files)
        manifest = json.loads(files["floe.json"])
        for channel in ("ios", "android"):
            rel = hubcore.package_path_for(GUIDE_ID, version, channel)
            target = data / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive)
        record = {
            "schemaVersion": 1, "id": GUIDE_ID, "version": version,
            "contentDigest": hubcore.content_digest(files),
            "packageSha256": hubcore.sha256_hex(archive),
            "reviewedCapabilities": [], "reviewedTools": [],
            "reviewedPythonPackages": [],
            "execution": {"os": None, "arch": "n/a", "evidence": "unproven"},
            "reviewStage": "static-content-reviewed", "reviewedAt": REVIEWED_AT,
            "reviewer": REVIEWER, "decision": "approve",
            "notes": {"en": "Fixture review record for the immutability tests.",
                      "zh-Hans": "用于不可变性测试的夹具审核记录。"},
        }
        record_bytes = hubcore.encoded(record)
        review_rel = f"reviews/{GUIDE_ID}/{version}.review.json"
        (data / review_rel).parent.mkdir(parents=True, exist_ok=True)
        (data / review_rel).write_bytes(record_bytes)
        (data / (review_rel + ".sig")).write_bytes(
            hubcore.sign_envelope(record_bytes, self.key, KEY_ID))
        commit = _commit_all(data, f"data X {GUIDE_ID} {version}")
        return data, commit, hubcore.content_digest(files)

    def _run_bridge(self, data, commit, out, tooling=None, extra=(), anchor=True):
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env.pop("PYTHONPATH", None)
        env[sign_publication.SIGNING_ENV_NAME] = base64.b64encode(TEST_SEED).decode()
        root = tooling or self.root
        if anchor and any((root / rel).exists()
                          for _, feed, sig in pi.FEED_PAIRS for rel in (feed, sig)):
            extra = ("--published-y", _git(root, "rev-parse", "HEAD").strip(), *extra)
        return subprocess.run(
            [sys.executable, str((tooling or self.root) / "scripts" / "sign_publication.py"),
             "--mode", "catalog", "--source-commit", commit, "--data", str(data),
             "--out", str(out), "--tooling", str(tooling or self.root), *extra],
            capture_output=True, text=True, env=env, cwd=str(self._tmp))

    def test_published_signing_requires_an_independent_publication_pin(self):
        data, commit, _ = self._data_root("data-anchor", SYNTHETIC_VERSION, "v1")
        first = self._tmp / "first-anchor"
        proc = self._run_bridge(data, commit, first)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for rel in ("catalog.json", "catalog.sig", "android/catalog.json",
                    "android/catalog.sig"):
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((first / rel).read_bytes())
        pin = _commit_all(self.root, "first anchored publication")
        self.write_ledger(self.ledger_rows_for(pin))
        out = self._tmp / "unanchored-signing"
        proc = self._run_bridge(data, commit, out, anchor=False)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("requires --published-y", proc.stderr)
        self.assertFalse((out / "catalog.sig").exists())

    def test_first_publication_signs_and_history_then_blocks_changed_bytes(self):
        # 1. genuine first publication: no history anywhere -> signs fine
        data, commit, digest_v1 = self._data_root("data1", SYNTHETIC_VERSION, "body v1")
        out1 = self._tmp / "out1"
        proc = self._run_bridge(data, commit, out1)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue((out1 / "catalog.json").is_file())
        self.assertTrue((out1 / "catalog.sig").is_file())

        # 2. publish that output as the actual history inside the tooling root
        for rel in ("catalog.json", "catalog.sig", "android/catalog.json",
                    "android/catalog.sig"):
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((out1 / rel).read_bytes())
        pin = _commit_all(self.root, "publication Y1")
        self.write_ledger(self.ledger_rows_for(pin))

        # 3. re-signed SAME id+version with DIFFERENT bytes must be refused by
        #    the signer itself, before any signature exists
        data2, commit2, digest_v2 = self._data_root("data2", SYNTHETIC_VERSION,
                                                    "body v2 -- changed bytes")
        self.assertNotEqual(digest_v1, digest_v2)
        out2 = self._tmp / "out2"
        proc = self._run_bridge(data2, commit2, out2)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("immutable publication refused", proc.stderr + proc.stdout)
        self.assertFalse((out2 / "catalog.sig").exists())
        self.assertFalse((out2 / "catalog.json").exists())

        # 4. a genuinely new version of the same skill is allowed
        data3, commit3, _ = self._data_root("data3", NEW_VERSION, "body v3")
        out3 = self._tmp / "out3"
        proc = self._run_bridge(data3, commit3, out3)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_data_checkout_ledger_is_never_used(self):
        """A caller-planted ledger inside X cannot replace the tooling baseline."""
        data, commit, _ = self._data_root("dataX", SYNTHETIC_VERSION, "body v1")
        out1 = self._tmp / "outX1"
        proc = self._run_bridge(data, commit, out1)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for rel in ("catalog.json", "catalog.sig", "android/catalog.json",
                    "android/catalog.sig"):
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((out1 / rel).read_bytes())
        pin = _commit_all(self.root, "publication Y1")
        self.write_ledger(self.ledger_rows_for(pin))

        # same version, changed bytes, plus a caller-planted EMPTY ledger in X
        # that would "prove" no history exists if the signer ever read it
        planted = hubcore.encoded({
            "schemaVersion": 1, "publisher": "JiangNanGenius",
            "description": "planted by the caller; must never be trusted",
            "publications": []})
        data2, commit2, _ = self._data_root("dataX2", SYNTHETIC_VERSION,
                                            "body v2", ledger_bytes=planted)
        out2 = self._tmp / "outX2"
        proc = self._run_bridge(data2, commit2, out2)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("immutable publication refused", proc.stderr + proc.stdout)

    def test_missing_ledger_beside_published_history_refuses_in_signer(self):
        data, commit, _ = self._data_root("dataM", SYNTHETIC_VERSION, "body v1")
        out1 = self._tmp / "outM1"
        proc = self._run_bridge(data, commit, out1)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for rel in ("catalog.json", "catalog.sig", "android/catalog.json",
                    "android/catalog.sig"):
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((out1 / rel).read_bytes())
        _commit_all(self.root, "publication Y1 without ledger")
        data2, commit2, _ = self._data_root("dataM2", NEW_VERSION, "body v2")
        out2 = self._tmp / "outM2"
        proc = self._run_bridge(data2, commit2, out2)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("ledger", proc.stderr + proc.stdout)
        self.assertFalse((out2 / "catalog.json").exists())

    def test_ledger_outside_tooling_root_refused(self):
        data, commit, _ = self._data_root("dataL", SYNTHETIC_VERSION, "body v1")
        outside = self._tmp / "outside-ledger.json"
        outside.write_bytes(pi.render_ledger([
            {"publication": "a" * 40, "channel": "ios", "feedSha256": "b" * 64,
             "offers": [{"id": "x", "version": "1.0.0", "contentDigest": "c" * 64}]}]))
        out = self._tmp / "outL"
        proc = self._run_bridge(data, commit, out,
                                extra=("--publication-ledger", str(outside)))
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("inside the trusted tooling", proc.stderr + proc.stdout)


class RealRepositoryTests(unittest.TestCase):
    """Read-only probes against the ACTUAL published repository history.

    The reviewed 2026-10-28 cumulative baseline (12 rows / 6 pins /
    39 iOS + 36 Android = 75 facts) is an EXPLICIT historical fact: it is
    verified from the canonical ledger blob committed at the immutable pin
    ``admission_baseline.REVIEWED_BASELINE_COMMIT`` (Root's reviewed branch
    head), cryptographically anchored row-by-row to the signed feed bytes at
    each publication pin. It is never re-read from whatever the live tree
    happens to contain, because valid authorized appends (new immutable
    versions per publication) legitimately GROW the live ledger. The live
    ledger must pass the full cryptographic verification, must contain every
    reviewed row unchanged (append-only over real history), and the live
    cumulative baseline must still agree with every reviewed fact. No test
    in this class compares the LIVE cumulative count to a fixed number, so
    appending a valid publication never requires a manual baseline-count
    patch; mutating or dropping any old fact still fails closed.
    """

    @classmethod
    def setUpClass(cls):
        # The ledger guardrail verifies signed feed bytes at their pinned
        # publication commits. A CI checkout made with default fetch-depth 1
        # cannot read those trusted objects yet (environment gap, never a
        # content pass); complete the fetch so the SAME full verification
        # runs everywhere. Fail-closed: a pin that still cannot be read
        # raises out of this helper instead of skipping the guarantee. The
        # live ledger's own pins are included so future append publications
        # are trusted objects here too, never a false content failure.
        live = BASE.load_ledger(HERE)["publications"]
        BASE.ensure_pinned_commits_available(
            HERE, commits=set(BASE.PUBLICATION_PINS)
            | {row["publication"] for row in live})
        cls.reviewed_rows = cls._verify_reviewed_blob()
        cls.reviewed_facts = cls._facts_of(cls.reviewed_rows)

    @staticmethod
    def _facts_of(rows):
        facts = {}
        for row in rows:
            for offer in row["offers"]:
                facts[(row["channel"], offer["id"], offer["version"])] = \
                    offer["contentDigest"]
        return facts

    @staticmethod
    def _verify_reviewed_blob():
        """Fully verify the historical ledger bytes at the immutable pin."""
        blob = BASE.reviewed_ledger_blob(HERE)
        if hashlib.sha256(blob).hexdigest() != BASE.REVIEWED_LEDGER_SHA256:
            raise AssertionError(
                "the reviewed baseline blob at "
                f"{BASE.REVIEWED_BASELINE_COMMIT[:10]} is not the exact "
                "bytes Root transcribed on 2026-10-28")
        with tempfile.TemporaryDirectory(prefix="hub-reviewed-ledger-") as tmp:
            path = pathlib.Path(tmp) / "publication-ledger.json"
            path.write_bytes(blob)
            # Every row is anchored to the signed feed bytes at ITS pinned
            # publication commit (full crypto verification of real history).
            # Being outside the tooling ledger path, the HEAD-ancestry
            # append-only leg targets the live tree instead and is exercised
            # directly against real history below.
            return pi.verify_ledger(path, HERE)

    def test_reviewed_baseline_is_immutable_at_the_pinned_commit(self):
        # The transcribed 2026-10-28 reviewed baseline, verified as literal
        # explicit expectations against the blob at the content-addressed
        # commit — expected values come from admission_baseline literals,
        # never from the live tree or the function under test.
        rows = self.reviewed_rows
        self.assertEqual(len(rows), BASE.REVIEWED_LEDGER_ROWS)
        pins = sorted({row["publication"] for row in rows})
        self.assertEqual(len(pins), BASE.REVIEWED_LEDGER_PINS)
        self.assertEqual(pins, sorted(BASE.PUBLICATION_PINS))
        facts = self.reviewed_facts
        self.assertEqual(len(facts), BASE.CUMULATIVE_FACTS)  # 75
        ios = {k for k in facts if k[0] == "ios"}
        android = {k for k in facts if k[0] == "android"}
        self.assertEqual(len(ios), 39)
        self.assertEqual(len(android), 36)
        self.assertEqual({k[1] for k in ios}, set(BASE.IOS_OPTIONAL_OFFER_IDS))
        self.assertEqual({k[1] for k in android},
                         set(BASE.ANDROID_OPTIONAL_OFFER_IDS))

    def test_bootstrap_ledger_covers_the_published_31_per_channel(self):
        # Historical bootstrap fact (immutable): the first signed publication
        # e02b3e94 carries exactly 31 packaged offers per channel, verified
        # at the reviewed baseline blob (see test above for the full 75-fact
        # literal identity). The LIVE cumulative baseline must still agree
        # with every bootstrap fact after any number of valid appends.
        boot = [row for row in self.reviewed_rows
                if row["publication"] == BASE.BOOTSTRAP_PIN]
        self.assertEqual(len(boot), 2)
        for row in boot:
            self.assertEqual(len(row["offers"]), BASE.BOOTSTRAP_OFFERS_PER_CHANNEL)
        self.assertEqual({row["channel"] for row in boot}, {"ios", "android"})
        prov = {}
        baseline = pi.build_validated_baseline(HERE, provenance=prov)
        # every historical bootstrap fact survives unchanged in the live
        # cumulative baseline (same (id,version) -> same contentDigest).
        for row in boot:
            for offer in row["offers"]:
                self.assertEqual(baseline[(row["channel"], offer["id"],
                                           offer["version"])],
                                 offer["contentDigest"])

    def test_current_ledger_verifies_and_preserves_every_reviewed_fact(self):
        # Live truth check (no fixed cumulative count): the current ledger
        # fully crypto-verifies row-by-row, retains every reviewed 2026-10-28
        # row byte-for-byte, pins form a superset, every reviewed fact still
        # maps to its exact digest, and the ACTUAL current feeds' packaged
        # offers are all covered (feeds parsed independently here, not
        # derived from the function under test).
        prov = {}
        current = pi.build_validated_baseline(HERE, provenance=prov)
        for key, digest in self.reviewed_facts.items():
            self.assertIn(key, current)
            self.assertEqual(current[key], digest, f"old fact mutated: {key}")
        self.assertGreaterEqual(len(current), len(self.reviewed_facts))
        self.assertEqual(prov["historicalFacts"], len(current))
        self.assertLessEqual(set(BASE.PUBLICATION_PINS),
                             set(prov["publicationPins"]))
        live_rows = BASE.load_ledger(HERE)["publications"]
        live_keys = {json.dumps(row, sort_keys=True) for row in live_rows}
        for row in self.reviewed_rows:
            self.assertIn(json.dumps(row, sort_keys=True), live_keys)
        for channel, rel in (("ios", "catalog.json"),
                             ("android", "android/catalog.json")):
            feed = json.loads((HERE / rel).read_bytes())
            for entry in feed["entries"]:
                package = entry.get("package")
                if package is not None:
                    self.assertEqual(
                        current.get((channel, entry["id"], entry["version"])),
                        package["contentDigest"],
                        f"current {channel} offer {entry['id']} "
                        f"{entry['version']} not covered")

    def test_republishing_the_current_bytes_is_allowed(self):
        baseline = pi.build_validated_baseline(HERE)
        outputs = {
            "catalog.json": (HERE / "catalog.json").read_bytes(),
            "android/catalog.json": (HERE / "android" / "catalog.json").read_bytes(),
        }
        self.assertTrue(pi.assert_immutable_publication(outputs, baseline))

    def test_a_single_changed_offer_digest_is_refused(self):
        baseline = pi.build_validated_baseline(HERE)
        for channel, rel in (("ios", "catalog.json"),
                             ("android", "android/catalog.json")):
            doc = json.loads((HERE / rel).read_bytes())
            doc["entries"][0]["package"] = dict(doc["entries"][0]["package"],
                                                contentDigest="f" * 64)
            outputs = {rel: hubcore.encoded(doc)}
            with self.assertRaises(hubcore.HubError, msg=channel):
                pi.assert_immutable_publication(outputs, baseline)

    def test_current_publication_commit_pin_verifies(self):
        head = _git(HERE, "rev-parse", "HEAD").strip()
        baseline = pi.build_validated_baseline(HERE, published_pin=head)
        # An append grows the cumulative record; the pin-read baseline must
        # still contain every reviewed fact with its exact digest.
        for key, digest in self.reviewed_facts.items():
            self.assertIn(key, baseline)
            self.assertEqual(baseline[key], digest, f"old fact mutated: {key}")

    def test_valid_new_version_appends_are_accepted_without_count_patch(self):
        # The next authorized publication re-signs today's bytes PLUS three
        # genuinely new (id, version) offers per channel. Against the REAL
        # cumulative baseline this passes with no expected-count anywhere —
        # appending never requires a manual baseline update.
        baseline = pi.build_validated_baseline(HERE)
        outputs = {}
        for rel, channel in (("catalog.json", "ios"),
                             ("android/catalog.json", "android")):
            doc = json.loads((HERE / rel).read_bytes())
            appended = [
                {"id": entry["id"], "version": "99.0.0",
                 "package": {"path": hubcore.package_path_for(
                     entry["id"], "99.0.0", channel),
                     "contentDigest": "e" * 64}}
                for entry in doc["entries"][:3]]
            doc["entries"] = list(doc["entries"]) + appended
            outputs[rel] = hubcore.encoded(doc)
        self.assertTrue(pi.assert_immutable_publication(outputs, baseline))
        # Once the coordinator's ledger extension carries the appended
        # version, re-signing that SAME (channel, id, version) with changed
        # bytes is refused against the grown baseline.
        first_ios_id = json.loads(
            (HERE / "catalog.json").read_bytes())["entries"][0]["id"]
        extended = dict(baseline)
        extended[("ios", first_ios_id, "99.0.0")] = "e" * 64
        doc = json.loads(outputs["catalog.json"])
        moved = next(e for e in doc["entries"]
                     if e["id"] == first_ios_id and e["version"] == "99.0.0")
        moved["package"]["contentDigest"] = "d" * 64
        with self.assertRaises(hubcore.HubError):
            pi.assert_immutable_publication(
                {"catalog.json": hubcore.encoded(doc)}, extended)

    def test_changed_or_dropped_historical_fact_is_refused(self):
        # Real-data refusal legs, strictly read-only against the repository:
        # (1) a reviewed offer digest swapped in a copy of the ledger is
        # caught by the cryptographic anchor at the pinned publication's
        # signed bytes (verify_ledger on a scratch path); (2) dropping the
        # bootstrap rows is caught by the production append-only guard
        # reading the REAL committed ledger history.
        doc = json.loads(BASE.reviewed_ledger_blob(HERE))
        doc["publications"][0]["offers"][0]["contentDigest"] = "9" * 64
        with tempfile.TemporaryDirectory(prefix="hub-tamper-") as tmp:
            path = pathlib.Path(tmp) / "ledger.json"
            path.write_bytes(pi.render_ledger(
                doc["publications"], description=doc["description"]))
            with self.assertRaisesRegex(hubcore.HubError, "contentDigest"):
                pi.verify_ledger(path, HERE)
        truncated = json.loads(BASE.reviewed_ledger_blob(HERE))
        truncated["publications"] = [
            row for row in truncated["publications"]
            if row["publication"] != BASE.BOOTSTRAP_PIN]
        raw = pi.render_ledger(truncated["publications"],
                               description=truncated["description"])
        with self.assertRaisesRegex(hubcore.HubError, "append-only"):
            # the same production leg verify_ledger runs for the live tooling
            # ledger, exercised against the real committed history; the repo
            # itself is never written.
            pi._assert_ledger_append_only(HERE, raw, truncated)


if __name__ == "__main__":
    unittest.main()
