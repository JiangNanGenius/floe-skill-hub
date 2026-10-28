#!/usr/bin/env python3
"""Behaviour tests for the automatic_transport trusted transport primitives.

Covers the three primitives exactly as Root scoped them:
  * the strict canonical bounded candidate-request parser (identity binding,
    unknown-field/path/override refusal, oversize, non-canonical bytes);
  * the safe trusted-tooling history refresh over REAL disposable Git
    fixtures (code/trust/policy/engine drift — bytes AND executable mode —
    denied by default; allowed data-only refresh passes, including the sole
    permitted deletion of ordinary sources/** prose data while licence/
    notice, ledger, feed, review, key and every other tracked removal is
    denied; the cumulative ledger is enforced over EVERY effective main
    first-parent transition, so a mid-history row drop hidden by a later
    append is rejected even when the endpoints and current offers look
    coherent; every observed publication pin must stay reachable on live
    main; the anchor must sit on the live first-parent mainline; anchor
    ledger row deletion/rewrite/reorder/duplicate and missing current-offer
    coverage rejected; snapshot hygiene through the unchanged
    sign_publication helper; fixed-origin live resolution without any
    caller-selected pin; the request CAS base binds to the fetched live
    main, never to a stale historical publication pin);
  * the signed relay metadata validation (official receipt/envelope
    verification against the anchor trust, exact request binding, per-file
    receipt hash binding, traversal/duplicate/symlink/executable/package and
    forged-signature refusal, bounded size).
Plus the X-vs-B engine-authority freeze the architecture evidence requires
(engines/** drift including executable mode, embedded
references/engine-dependency.json drift, published archive immutability AND
archive-deletion refusal on the candidate side, and the mode-aware
immutable review history — catalog mode retains every base review record
and sidecar exactly while the canonical requestId-bound reviews mode
permits the expected minimal pruning but never mutation of retained
records; the request wrapper binds the candidate commit to the canonical
request sourceCommit).

Ephemeral public-knowledge test keys only; the production private key never
exists in these fixtures and nothing here signs for real distribution.
"""
import base64
import hashlib
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile

sys.dont_write_bytecode = True  # before any transport/hubcore import

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "scripts"))

import automatic_transport as at  # noqa: E402
import hubcore  # noqa: E402
import publication_immutability as pi  # noqa: E402

OFFICIAL_ORIGIN = "https://github.com/JiangNanGenius/floe-skill-hub.git"
X_COMMIT = "b" * 40
B_COMMIT = "c" * 40
POLICY = "d" * 64

TEST_SEED = hashlib.sha256(
    b"floe-skill-hub automatic-transport ephemeral TEST key -- NOT production").digest()
FOREIGN_SEED = hashlib.sha256(
    b"floe-skill-hub automatic-transport ephemeral FOREIGN key -- NOT production").digest()

REAL_REGISTRY = json.loads((REPO / "catalog" / "skills.json").read_bytes())


def _key(seed):
    Ed25519PrivateKey, _, serialization, _ = hubcore._load_ed25519()
    key = Ed25519PrivateKey.from_private_bytes(seed)
    public = key.public_key().public_bytes(serialization.Encoding.Raw,
                                           serialization.PublicFormat.Raw)
    return key, base64.b64encode(public).decode()


TEST_KEY, TEST_PUB = _key(TEST_SEED)
FOREIGN_KEY, _FOREIGN_PUB = _key(FOREIGN_SEED)
TRUST = {hubcore.PRODUCTION_KEY_ID: TEST_PUB}


def _git(where, *args):
    proc = subprocess.run(["git", "-C", str(where)] + list(args),
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError(f"fixture git failed: {args}: {proc.stderr}")
    return proc.stdout


def _init_repo(path, origin=OFFICIAL_ORIGIN):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    _git(path, "remote", "add", "origin", origin)
    return path


def _write(root, rel, data):
    full = pathlib.Path(root) / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))


def _commit_all(root, message):
    _git(root, "add", "-A")
    _git(root, "-c", "user.name=floe-transport-fixture",
         "-c", "user.email=fixture@invalid", "commit", "-q", "-m", message)
    return _git(root, "rev-parse", "HEAD").strip()


def _rm(root, rel):
    pathlib.Path(root, rel).unlink()


def _chmod(root, rel, executable=True):
    """Flip the executable bit only — the blob content stays identical."""
    path = pathlib.Path(root, rel)
    mode = path.stat().st_mode
    os.chmod(path, mode | 0o111 if executable else mode & ~0o111)


def _blob(root, commit, rel):
    """Exact committed bytes via a plain read-only git show (fixture-side)."""
    proc = subprocess.run(["git", "-C", str(root), "show", f"{commit}:{rel}"],
                          capture_output=True)
    if proc.returncode != 0:
        raise AssertionError(f"fixture blob read failed: {commit}:{rel}")
    return proc.stdout


# ---------------------------------------------------------------------------
# synthetic publication-data builders (shapes reused from the existing
# tests/catalog fixtures; fixture identity = official keyID, test-only key)
# ---------------------------------------------------------------------------

def _feed_entry(id_, channel, version="1.0.0", review=None, plan=1):
    package = {
        "path": hubcore.package_path_for(id_, version, channel),
        "size": 4, "sha256": hashlib.sha256(b"zip-" + id_.encode()).hexdigest(),
        "contentDigest": hashlib.sha256(b"cd-" + id_.encode()).hexdigest(),
        "containsScripts": False,
    }
    return {
        "id": id_, "planNumber": plan, "kind": "optional", "source": "A",
        "name": {"en": id_, "zh-Hans": id_},
        "description": {"en": "t", "zh-Hans": "t"},
        "category": hubcore.CATEGORIES[0],
        "tags": ["test", "fixture"], "deepAdaptation": False,
        "upstream": None, "firstParty": None,
        "runtime": {"scriptRuntime": "none", "capabilities": [], "tools": [],
                    "installPlatforms": [channel], "pythonPackagesPlan": [],
                    "execution": {"os": None, "arch": "n/a", "evidence": "unproven"}},
        "version": version, "minimumAppVersion": "1.7.0",
        "status": {"sourcePinned": True, "licenseChecked": True,
                   "adaptation": "frozen", "packaged": True,
                   "reviewed": review is not None, "qualified": False,
                   "published": True, "executionVerified": False},
        "notes": {"en": "", "zh-Hans": ""},
        "package": package, "review": review, "installOffer": "none",
    }


def _feed_bytes(channel, entries, source_commit):
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
    feed = {"schemaVersion": hubcore.CATALOG_SCHEMA_VERSION,
            "publisher": "JiangNanGenius", "channel": channel,
            "feedStatus": "production",
            "hubRepository": "JiangNanGenius/floe-skill-hub",
            "sourceCommit": source_commit,
            "permissionPolicy": hubcore.PERMISSION_POLICY,
            "entries": entries, "counts": counts}
    return hubcore.encoded(feed)


def _signed(rel_bytes_map):
    """(bytes, envelope) for one member."""
    return hubcore.sign_envelope(rel_bytes_map, TEST_KEY, hubcore.PRODUCTION_KEY_ID)


def _review_pair(id_, version, package):
    record = {
        "schemaVersion": hubcore.REVIEW_SCHEMA_VERSION, "id": id_, "version": version,
        "contentDigest": package["contentDigest"], "packageSha256": package["sha256"],
        "reviewedCapabilities": [], "reviewedTools": [], "reviewedPythonPackages": [],
        "execution": {"os": None, "arch": "n/a", "evidence": "unproven"},
        "reviewStage": "static-content-reviewed", "reviewedAt": "2026-10-28",
        "reviewer": "transport-fixture", "decision": "approve",
        "notes": {"en": "fixture approval", "zh-Hans": "测试批准"},
    }
    raw = hubcore.encoded(record)
    return raw, hubcore.sign_envelope(raw, TEST_KEY, hubcore.PRODUCTION_KEY_ID)


def _outputs(files):
    return [{"path": rel, "sha256": hubcore.sha256_hex(data), "size": len(data)}
            for rel, data in sorted(files.items())]


# ===========================================================================
# 1. strict canonical bounded request parser
# ===========================================================================


class RequestParserTests(unittest.TestCase):
    def test_canonical_roundtrip_and_derivation(self):
        raw, doc = at.build_request("reviews", X_COMMIT, B_COMMIT, POLICY)
        parsed = at.parse_request_bytes(raw)
        self.assertEqual(parsed["requestId"], at.derive_request_id(parsed))
        self.assertEqual(parsed["mode"], "reviews")
        # requestId is a pure function of the canonical core fields
        core = at.request_core(doc)
        self.assertEqual(sorted(core), sorted(at.REQUEST_CORE_FIELDS))
        raw2, doc2 = at.build_request("reviews", X_COMMIT, B_COMMIT, POLICY)
        self.assertEqual(raw, raw2)
        self.assertEqual(doc, doc2)

    def test_catalog_mode_accepted(self):
        raw, doc = at.build_request("catalog", X_COMMIT, B_COMMIT, POLICY)
        self.assertEqual(at.parse_request_bytes(raw)["mode"], "catalog")

    def test_tampered_field_breaks_identity_binding(self):
        _raw, doc = at.build_request("reviews", X_COMMIT, B_COMMIT, POLICY)
        doc["sourceCommit"] = "e" * 40  # stale requestId over changed fields
        self.assertRaises(at.TransportError,
                          at.validate_request, doc)

    def test_unknown_fields_and_identity_overrides_refused(self):
        for extra in ({"repository": "JiangNanGenius/evil"},
                      {"branch": "refs/heads/main"},
                      {"hubRepository": "JiangNanGenius/evil-hub"},
                      {"out": "/tmp/evil"},
                      {"tooling": "/tmp/evil"},
                      {"publishedY": "f" * 40}):
            _raw, doc = at.build_request("reviews", X_COMMIT, B_COMMIT, POLICY)
            doc.update(extra)
            with self.assertRaises(at.TransportError, msg=str(extra)):
                at.validate_request(doc)

    def test_missing_fields_refused(self):
        for field in at.REQUEST_FIELDS:
            _raw, doc = at.build_request("reviews", X_COMMIT, B_COMMIT, POLICY)
            del doc[field]
            self.assertRaises(at.TransportError, at.validate_request, doc)

    def test_value_grammar_refused(self):
        cases = [
            ("mode", "publish"), ("mode", 1),
            ("sourceCommit", X_COMMIT.upper()), ("sourceCommit", "b" * 39),
            ("basePublication", "not-a-commit"),
            ("policySha256", "d" * 63), ("policySha256", "z" * 64),
            ("schemaVersion", "1"), ("schemaVersion", True),
        ]
        for field, value in cases:
            _raw, doc = at.build_request("reviews", X_COMMIT, B_COMMIT, POLICY)
            doc[field] = value
            with self.assertRaises(at.TransportError, msg=f"{field}={value!r}"):
                at.validate_request(doc)

    def test_non_canonical_bytes_refused(self):
        _raw, doc = at.build_request("reviews", X_COMMIT, B_COMMIT, POLICY)
        pretty = (json.dumps(doc, indent=2) + "\n").encode("utf-8")
        self.assertRaises(at.TransportError, at.parse_request_bytes, pretty)
        self.assertRaises(at.TransportError, at.parse_request_bytes,
                          hubcore.encoded(doc) + b"\n")

    def test_oversized_input_refused(self):
        _raw, doc = at.build_request("reviews", X_COMMIT, B_COMMIT, POLICY)
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "request.json"
            path.write_bytes(hubcore.encoded(doc))
            self.assertEqual(at.parse_request_file(path)["mode"], "reviews")
            path.write_bytes(hubcore.encoded(doc).ljust(
                at.MAX_REQUEST_FILE_BYTES + 1, b" "))
            self.assertRaises(at.TransportError, at.parse_request_file, path)
        self.assertRaises(at.TransportError, at.parse_request_bytes,
                          b" " * (at.MAX_REQUEST_FILE_BYTES + 1))

    def test_symlink_request_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            real = pathlib.Path(tmp) / "real.json"
            link = pathlib.Path(tmp) / "link.json"
            raw, _ = at.build_request("reviews", X_COMMIT, B_COMMIT, POLICY)
            real.write_bytes(raw)
            link.symlink_to(real)
            self.assertRaises(at.TransportError, at.parse_request_file, link)

    def test_policy_digest_binding(self):
        _raw, doc = at.build_request("catalog", X_COMMIT, B_COMMIT,
                                     hubcore.sha256_hex(b"policy-v1"))
        self.assertTrue(at.request_policy_matches(doc, b"policy-v1"))
        self.assertFalse(at.request_policy_matches(doc, b"policy-v2"))

    def test_fixed_official_urls_only(self):
        self.assertTrue(at.is_official_url(
            "https://github.com/JiangNanGenius/floe-skill-hub.git",
            at.OFFICIAL_HUB_REPO))
        self.assertFalse(at.is_official_url(
            "https://github.com/evil/floe-skill-hub.git", at.OFFICIAL_HUB_REPO))
        self.assertTrue(at.is_official_url(
            "https://github.com/JiangNanGenius/floe-agent", at.OFFICIAL_APP_REPO))
        self.assertRaises(at.TransportError, at.is_official_url,
                          "https://github.com/JiangNanGenius/other", "x/y")


# ===========================================================================
# 2. trusted-tooling history refresh (real disposable Git repositories)
# ===========================================================================


class HistoryRefreshTestCase(unittest.TestCase):
    """Anchor A -> live main Y comparison over disposable Git snapshots."""

    def build_hub(self, tmp):
        self.root = _init_repo(pathlib.Path(tmp) / "hub")
        _write(self.root, "public-key.json", hubcore.encoded(
            {"keyID": hubcore.PRODUCTION_KEY_ID, "publicKey": TEST_PUB}))
        _write(self.root, "scripts/signer.py", b"TRUSTED-V1\n")
        _write(self.root, "schema/feed.schema.json", b'{"schema":"v1"}\n')
        _write(self.root, ".github/workflows/ci.yml", b"name: ci\n")
        _write(self.root, "engines/impeccable/ENGINE-LOCK.json", b'{"lock":1}\n')
        _write(self.root, "catalog/curation.json", b'{"policy":"hold"}\n')
        _write(self.root, "catalog/skills.json", hubcore.pretty(REAL_REGISTRY))
        _write(self.root, "docs/UPSTREAM-PINS.json", b'{"pins":{}}\n')
        _write(self.root, "docs/OTHER.md", b"# notes\n")
        _write(self.root, "showcase/links.json", b'{"links":[]}\n')
        _write(self.root, "showcase/README.md", b"# showcase\n")
        _write(self.root, "showcase/scripts/validate_showcase.py", b"# v1\n")
        _write(self.root, "showcase/media/one.jpg", b"\xff\xd8jpeg-fixture")
        _write(self.root, "tests/tool/test_registry.py", b"# tooling test v1\n")
        _write(self.root, "sources/alpha-guide/SKILL.md", b"# alpha upstream prose\n")
        _write(self.root, "sources/alpha-guide/notes.md", b"ordinary upstream notes\n")
        _write(self.root, "sources/alpha-guide/references/licenses/UPSTREAM-LICENSE.txt",
               b"MIT-style fixture licence notice -- NOT production\n")

        self.alpha = _feed_entry("alpha-guide", "ios", plan=1)
        self.beta = _feed_entry("beta-guide", "android", plan=2)
        araw, asig = _review_pair("alpha-guide", "1.0.0", self.alpha["package"])
        _write(self.root, "reviews/alpha-guide/1.0.0.review.json", araw)
        _write(self.root, "reviews/alpha-guide/1.0.0.review.json.sig", asig)
        self.alpha["review"] = {"path": "reviews/alpha-guide/1.0.0.review.json",
                                "sha256": hubcore.sha256_hex(araw),
                                "keyID": hubcore.PRODUCTION_KEY_ID}
        _write(self.root, "packages/alpha-guide/1.0.0/alpha-guide.zip", b"ZIP1")
        _write(self.root, "android/packages/beta-guide/1.0.0/beta-guide.zip", b"ZIP2")
        _write(self.root, "catalog.json", _feed_bytes("ios", [self.alpha], X_COMMIT))
        _write(self.root, "catalog.sig", _signed(
            _feed_bytes("ios", [self.alpha], X_COMMIT)))
        _write(self.root, "android/catalog.json",
               _feed_bytes("android", [self.beta], X_COMMIT))
        _write(self.root, "android/catalog.sig", _signed(
            _feed_bytes("android", [self.beta], X_COMMIT)))
        p1 = _commit_all(self.root, "publication pin P1")

        rows = [pi.build_ledger_row(self.root, p1, "ios"),
                pi.build_ledger_row(self.root, p1, "android")]
        _write(self.root, "catalog/publication-ledger.json", pi.render_ledger(rows))
        self.anchor = _commit_all(self.root, "reviewed anchor A (T + ledger)")
        return p1

    def publish_new_offer(self):
        """Y data-only refresh: new iOS offer + reviews + appended ledger."""
        gamma = _feed_entry("gamma-guide", "ios", plan=3)
        graw, gsig = _review_pair("gamma-guide", "1.0.0", gamma["package"])
        _write(self.root, "reviews/gamma-guide/1.0.0.review.json", graw)
        _write(self.root, "reviews/gamma-guide/1.0.0.review.json.sig", gsig)
        gamma["review"] = {"path": "reviews/gamma-guide/1.0.0.review.json",
                           "sha256": hubcore.sha256_hex(graw),
                           "keyID": hubcore.PRODUCTION_KEY_ID}
        _write(self.root, "packages/gamma-guide/1.0.0/gamma-guide.zip", b"ZIP3")
        _write(self.root, "sources/gamma-guide/SKILL.md", b"# gamma\n")
        feed = _feed_bytes("ios", [self.alpha, gamma], X_COMMIT)
        _write(self.root, "catalog.json", feed)
        _write(self.root, "catalog.sig", _signed(feed))
        pins_publish = _commit_all(self.root, "publication P2 (new feed)")
        doc = json.loads((self.root / "catalog/publication-ledger.json").read_bytes())
        rows = list(doc["publications"])
        rows.append(pi.build_ledger_row(self.root, pins_publish, "ios"))
        _write(self.root, "catalog/publication-ledger.json", pi.render_ledger(rows))
        return _commit_all(self.root, "live main Y (ledger appended)")

    def publish_second_offer(self):
        """A further legitimate data publication on top of publish_new_offer."""
        delta = _feed_entry("delta-guide", "ios", plan=4)
        draw, dsig = _review_pair("delta-guide", "1.0.0", delta["package"])
        _write(self.root, "reviews/delta-guide/1.0.0.review.json", draw)
        _write(self.root, "reviews/delta-guide/1.0.0.review.json.sig", dsig)
        delta["review"] = {"path": "reviews/delta-guide/1.0.0.review.json",
                           "sha256": hubcore.sha256_hex(draw),
                           "keyID": hubcore.PRODUCTION_KEY_ID}
        _write(self.root, "packages/delta-guide/1.0.0/delta-guide.zip", b"ZIP4")
        _write(self.root, "sources/delta-guide/SKILL.md", b"# delta\n")
        feed = _feed_bytes("ios", [self.alpha, self._gamma_feed_entry(), delta],
                           X_COMMIT)
        _write(self.root, "catalog.json", feed)
        _write(self.root, "catalog.sig", _signed(feed))
        pins_publish = _commit_all(self.root, "publication P3 (second new feed)")
        doc = json.loads((self.root / "catalog/publication-ledger.json").read_bytes())
        rows = list(doc["publications"])
        rows.append(pi.build_ledger_row(self.root, pins_publish, "ios"))
        _write(self.root, "catalog/publication-ledger.json", pi.render_ledger(rows))
        return _commit_all(self.root, "live main Y2 (second ledger append)")

    def _gamma_feed_entry(self):
        """Rebuild the gamma entry exactly as publish_new_offer signed it."""
        gamma = _feed_entry("gamma-guide", "ios", plan=3)
        gamma["review"] = {"path": "reviews/gamma-guide/1.0.0.review.json",
                           "sha256": hubcore.sha256_hex(
                               _blob(self.root, "HEAD",
                                     "reviews/gamma-guide/1.0.0.review.json")),
                           "keyID": hubcore.PRODUCTION_KEY_ID}
        return gamma

    def refresh(self, live):
        return at.verify_history_refresh(self.root, self.anchor, live)

    # ---- passes ----------------------------------------------------------

    def test_allowed_data_only_refresh_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_hub(tmp)
            live = self.publish_new_offer()
            verdict = self.refresh(live)
            self.assertEqual(verdict["status"], "refresh-ok")
            self.assertEqual(verdict["appendedLedgerRows"], 1)
            self.assertIn("packages/gamma-guide/1.0.0/gamma-guide.zip",
                          verdict["addedDataPaths"])
            self.assertIn("catalog.json", verdict["modifiedDataPaths"])
            self.assertGreaterEqual(verdict["baselineHistoricalFacts"], 3)

    def test_showcase_media_and_json_updates_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_hub(tmp)
            _write(self.root, "showcase/media/two.png", b"\x89PNG-fixture")
            links = {"links": [{"id": "alpha-guide", "url": "https://x.example/a"}]}
            _write(self.root, "showcase/links.json", hubcore.encoded(links))
            live = _commit_all(self.root, "showcase evidence refresh")
            self.assertEqual(self.refresh(live)["status"], "refresh-ok")

    def test_no_change_refresh_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_hub(tmp)
            verdict = self.refresh(self.anchor)
            self.assertEqual(verdict["status"], "refresh-ok")
            self.assertEqual(verdict["appendedLedgerRows"], 0)

    # ---- trust/code/policy/engine drift denied by default -----------------

    def _drift(self, mutate):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_hub(tmp)
            mutate()
            live = _commit_all(self.root, "drift")
            with self.assertRaises(at.TransportError) as ctx:
                self.refresh(live)
            self.assertIn("HOLD", str(ctx.exception))

    def test_scripts_drift_denied(self):
        self._drift(lambda: _write(self.root, "scripts/signer.py", b"TRUSTED-V2\n"))

    def test_public_key_drift_denied(self):
        self._drift(lambda: _write(
            self.root, "public-key.json", hubcore.encoded(
                {"keyID": hubcore.PRODUCTION_KEY_ID, "publicKey": _key(FOREIGN_SEED)[1]})))

    def test_schema_drift_denied(self):
        self._drift(lambda: _write(self.root, "schema/feed.schema.json",
                                   b'{"schema":"v2"}\n'))

    def test_workflow_drift_denied(self):
        self._drift(lambda: _write(self.root, ".github/workflows/ci.yml",
                                   b"name: changed\n"))

    def test_engine_lock_drift_denied(self):
        self._drift(lambda: _write(self.root, "engines/impeccable/ENGINE-LOCK.json",
                                   b'{"lock":2}\n'))

    def test_engine_addition_denied(self):
        self._drift(lambda: _write(self.root, "engines/impeccable/EXTRA.bin",
                                   b"new"))

    def test_policy_config_drift_denied(self):
        self._drift(lambda: _write(self.root, "catalog/curation.json",
                                   b'{"policy":"open"}\n'))

    def test_tests_drift_denied(self):
        self._drift(lambda: _write(self.root, "tests/tool/test_registry.py",
                                   b"# tooling test v2\n"))

    def test_unknown_path_denied(self):
        self._drift(lambda: _write(self.root, "tools/evil.sh", b"#!/bin/sh\n"))

    def test_showcase_scripts_and_markdown_denied(self):
        self._drift(lambda: _write(self.root, "showcase/scripts/validate_showcase.py",
                                   b"# v2 executes differently\n"))
        self._drift(lambda: _write(self.root, "showcase/README.md", b"# changed\n"))

    def test_tracked_removal_denied(self):
        self._drift(lambda: _rm(self.root, "packages/alpha-guide/1.0.0/alpha-guide.zip"))

    def test_skills_registry_drift_must_stay_valid(self):
        self._drift(lambda: _write(self.root, "catalog/skills.json", b'{"broken":1}\n'))

    def test_invalid_json_data_denied(self):
        self._drift(lambda: _write(self.root, "showcase/links.json", b"{not json\n"))

    def test_scripts_mode_drift_denied(self):
        """Executable-bit drift on the SAME blob is code drift, not identity."""
        self._drift(lambda: _chmod(self.root, "scripts/signer.py"))

    # ---- deletion zone: only ordinary mutable sources/** data may vanish ---

    def test_sources_prose_deletion_refresh_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_hub(tmp)
            live = self.publish_new_offer()
            _rm(self.root, "sources/alpha-guide/SKILL.md")
            _rm(self.root, "sources/alpha-guide/notes.md")
            live = _commit_all(self.root, "upstream legitimately deleted prose files")
            verdict = self.refresh(live)
            self.assertEqual(verdict["status"], "refresh-ok")
            self.assertIn("sources/alpha-guide/SKILL.md", verdict["removedDataPaths"])
            self.assertIn("sources/alpha-guide/notes.md", verdict["removedDataPaths"])

    def test_sources_license_deletion_denied(self):
        self._drift(lambda: _rm(
            self.root,
            "sources/alpha-guide/references/licenses/UPSTREAM-LICENSE.txt"))

    def test_ledger_file_deletion_denied(self):
        self._drift(lambda: _rm(self.root, "catalog/publication-ledger.json"))

    def test_public_key_deletion_denied(self):
        self._drift(lambda: _rm(self.root, "public-key.json"))

    def test_review_pair_deletion_denied(self):
        self._drift(lambda: _rm(self.root, "reviews/alpha-guide/1.0.0.review.json"))

    # ---- CAS base binding: live main Y, never a stale historical pin -------

    def test_request_base_must_equal_live_main_not_historical_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_hub(tmp)
            live = self.publish_new_offer()
            verdict = self.refresh(live)
            # live Y is a data/ledger commit that is NOT any feed publication
            # pin (exactly like today's real 3e145cd): it is THE valid base
            self.assertNotIn(verdict["liveCommit"],
                             verdict["baselineProvenance"]["publicationPins"])
            bound = at.build_request("catalog", X_COMMIT,
                                     verdict["liveCommit"], POLICY)[1]
            self.assertEqual(at.verify_request_history_base(bound, verdict),
                             verdict["liveCommit"])
            # a genuinely signed historical publication pin is still a stale
            # base and must be refused
            stale = min(verdict["baselineProvenance"]["publicationPins"])
            bad = at.build_request("catalog", X_COMMIT, stale, POLICY)[1]
            with self.assertRaises(at.TransportError) as ctx:
                at.verify_request_history_base(bad, verdict)
            self.assertIn("live main", str(ctx.exception))
            # malformed or non-successful verdicts fail closed
            self.assertRaises(at.TransportError, at.verify_request_history_base,
                              bad, {"status": "not-ok"})
            self.assertRaises(at.TransportError, at.verify_request_history_base,
                              bad, {"status": "refresh-ok"})

    def test_non_descendant_history_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_hub(tmp)
            with self.assertRaises(at.TransportError):
                # an OLD commit is not a descendant of the anchor
                self.refresh(_git(self.root, "rev-parse",
                                  f"{self.anchor}~1").strip())

    # ---- ledger continuity and coverage -----------------------------------

    def test_anchor_row_removal_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_hub(tmp)
            doc = json.loads((self.root / "catalog/publication-ledger.json").read_bytes())
            doc["publications"] = doc["publications"][:1]
            _write(self.root, "catalog/publication-ledger.json",
                   hubcore.encoded(doc))
            live = _commit_all(self.root, "ledger rows deleted")
            with self.assertRaises(at.TransportError) as ctx:
                self.refresh(live)
            self.assertIn("append-only", str(ctx.exception))

    def test_anchor_row_rewrite_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_hub(tmp)
            doc = json.loads((self.root / "catalog/publication-ledger.json").read_bytes())
            row = dict(doc["publications"][0])
            row["feedSha256"] = "f" * 64
            doc["publications"][0] = row
            _write(self.root, "catalog/publication-ledger.json",
                   hubcore.encoded(doc))
            live = _commit_all(self.root, "ledger row rewritten")
            with self.assertRaises(at.TransportError) as ctx:
                self.refresh(live)
            self.assertIn("rewritten", str(ctx.exception))

    def test_anchor_row_reorder_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_hub(tmp)
            doc = json.loads((self.root / "catalog/publication-ledger.json").read_bytes())
            doc["publications"] = list(reversed(doc["publications"]))
            _write(self.root, "catalog/publication-ledger.json",
                   hubcore.encoded(doc))
            live = _commit_all(self.root, "ledger rows reordered")
            self.assertRaises(at.TransportError, self.refresh, live)

    def test_duplicate_row_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_hub(tmp)
            doc = json.loads((self.root / "catalog/publication-ledger.json").read_bytes())
            doc["publications"].append(doc["publications"][0])
            _write(self.root, "catalog/publication-ledger.json",
                   hubcore.encoded(doc))
            live = _commit_all(self.root, "ledger row duplicated")
            with self.assertRaises(at.TransportError) as ctx:
                self.refresh(live)
            self.assertIn("duplicates", str(ctx.exception))

    def test_missing_current_history_denied(self):
        """New published offers whose current rows are missing from the ledger."""
        with tempfile.TemporaryDirectory() as tmp:
            self.build_hub(tmp)
            gamma = _feed_entry("gamma-guide", "ios", plan=3)
            _write(self.root, "packages/gamma-guide/1.0.0/gamma-guide.zip", b"ZIP3")
            feed = _feed_bytes("ios", [self.alpha, gamma], X_COMMIT)
            _write(self.root, "catalog.json", feed)
            _write(self.root, "catalog.sig", _signed(feed))
            live = _commit_all(self.root, "feed advanced, ledger NOT appended")
            with self.assertRaises(at.TransportError) as ctx:
                self.refresh(live)
            self.assertIn("does not cover", str(ctx.exception))

    def test_tampered_appended_row_signature_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_hub(tmp)
            self.publish_new_offer()  # correct rows first
            doc = json.loads((self.root / "catalog/publication-ledger.json").read_bytes())
            rows = [json.loads(json.dumps(row)) for row in doc["publications"]]
            rows[-1]["offers"][0]["contentDigest"] = "a" * 64
            _write(self.root, "catalog/publication-ledger.json",
                   pi.render_ledger(rows))
            live = _commit_all(self.root, "ledger offer tampered")
            with self.assertRaises(at.TransportError):
                self.refresh(live)

    # ---- cumulative ledger HISTORY over every mainline transition ----------

    def test_multi_transition_ledger_history_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_hub(tmp)
            self.publish_new_offer()
            live = self.publish_second_offer()
            verdict = self.refresh(live)
            self.assertEqual(verdict["status"], "refresh-ok")
            self.assertEqual(verdict["ledgerTransitions"], 2)
            self.assertGreaterEqual(verdict["ledgerStatesVerified"], 2)
            self.assertGreaterEqual(verdict["baselineHistoricalFacts"], 4)

    def build_dropped_history(self, tmp):
        """A -> H1 appends a row -> H2 drops the post-A row -> H3 appends.

        The visible final state alone stays coherent (anchor prefix intact,
        every live row valid at its pin, current offers covered): the earlier
        gamma publication is only observable in the intermediate H1 ledger
        state that H2 silently rolled back.
        """
        self.build_hub(tmp)
        self.publish_new_offer()  # H1: gamma feed + appended row
        anchor_doc = json.loads(_blob(self.root, self.anchor,
                                      pi.LEDGER_REL))  # A rows only
        # H2: drop the post-anchor gamma row, anchor prefix still exact
        _write(self.root, pi.LEDGER_REL,
               pi.render_ledger(anchor_doc["publications"]))
        _commit_all(self.root, "H2: silently drop the gamma row")
        # H3: withdraw gamma from the feed, publish delta with valid bytes
        delta = _feed_entry("delta-guide", "ios", plan=4)
        draw, dsig = _review_pair("delta-guide", "1.0.0", delta["package"])
        _write(self.root, "reviews/delta-guide/1.0.0.review.json", draw)
        _write(self.root, "reviews/delta-guide/1.0.0.review.json.sig", dsig)
        delta["review"] = {"path": "reviews/delta-guide/1.0.0.review.json",
                           "sha256": hubcore.sha256_hex(draw),
                           "keyID": hubcore.PRODUCTION_KEY_ID}
        _write(self.root, "packages/delta-guide/1.0.0/delta-guide.zip", b"ZIP4")
        _write(self.root, "sources/delta-guide/SKILL.md", b"# delta\n")
        feed = _feed_bytes("ios", [self.alpha, delta], X_COMMIT)
        _write(self.root, "catalog.json", feed)
        _write(self.root, "catalog.sig", _signed(feed))
        h3_pin = _commit_all(self.root, "H3 feed: gamma withdrawn, delta published")
        doc = json.loads((self.root / pi.LEDGER_REL).read_bytes())
        rows = list(doc["publications"])
        rows.append(pi.build_ledger_row(self.root, h3_pin, "ios"))
        _write(self.root, pi.LEDGER_REL, pi.render_ledger(rows))
        return _commit_all(self.root, "H3 append hides the earlier drop")

    def test_intermediate_history_drop_hidden_by_later_append_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            live = self.build_dropped_history(tmp)
            # the endpoint pair alone is coherent — the old A→latest-only
            # helper cannot see the loss; the HOLD below must come from the
            # per-transition cumulative chain
            at.verify_ledger_continuity(_blob(self.root, self.anchor, pi.LEDGER_REL),
                                        _blob(self.root, live, pi.LEDGER_REL))
            with self.assertRaises(at.TransportError) as ctx:
                self.refresh(live)
            self.assertIn("append-only", str(ctx.exception))

    def test_unreachable_publication_pin_denied(self):
        """A row pinned to history that never landed on main is refused."""
        with tempfile.TemporaryDirectory() as tmp:
            self.build_hub(tmp)
            _git(self.root, "checkout", "-q", "-b", "side", self.anchor)
            gamma = _feed_entry("gamma-guide", "ios", plan=3)
            graw, gsig = _review_pair("gamma-guide", "1.0.0", gamma["package"])
            _write(self.root, "reviews/gamma-guide/1.0.0.review.json", graw)
            _write(self.root, "reviews/gamma-guide/1.0.0.review.json.sig", gsig)
            gamma["review"] = {"path": "reviews/gamma-guide/1.0.0.review.json",
                               "sha256": hubcore.sha256_hex(graw),
                               "keyID": hubcore.PRODUCTION_KEY_ID}
            _write(self.root, "packages/gamma-guide/1.0.0/gamma-guide.zip", b"ZIP3")
            feed = _feed_bytes("ios", [self.alpha, gamma], X_COMMIT)
            _write(self.root, "catalog.json", feed)
            _write(self.root, "catalog.sig", _signed(feed))
            side_pin = _commit_all(self.root, "side branch never merged to main")
            _git(self.root, "checkout", "-q", "main")
            doc = json.loads((self.root / pi.LEDGER_REL).read_bytes())
            rows = list(doc["publications"])
            rows.append(pi.build_ledger_row(self.root, side_pin, "ios"))
            _write(self.root, pi.LEDGER_REL, pi.render_ledger(rows))
            live = _commit_all(self.root, "main ledger pins an unreachable commit")
            with self.assertRaises(at.TransportError) as ctx:
                self.refresh(live)
            self.assertIn("not reachable", str(ctx.exception))

    def test_anchor_not_on_first_parent_mainline_denied(self):
        """A descendant that reaches the anchor only via a side parent fails."""
        with tempfile.TemporaryDirectory() as tmp:
            self.build_hub(tmp)
            self.publish_new_offer()
            parent_of_anchor = _git(self.root, "rev-parse",
                                    f"{self.anchor}~1").strip()
            tree = _git(self.root, "rev-parse", "HEAD^{tree}").strip()
            alt = _git(self.root, "-c", "user.name=floe-transport-fixture",
                       "-c", "user.email=fixture@invalid",
                       "commit-tree", tree, "-p", parent_of_anchor,
                       "-p", self.anchor,
                       "-m", "live whose first parent skips the anchor").strip()
            self.assertTrue(hubcore.COMMIT_PATTERN.fullmatch(alt))
            with self.assertRaises(at.TransportError) as ctx:
                self.refresh(alt)
            self.assertIn("first-parent", str(ctx.exception))

    # ---- snapshot hygiene via the UNCHANGED sign_publication helper --------

    def test_dirty_anchor_snapshot_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_hub(tmp)
            _write(self.root, "scripts/signer.py", b"tampered on disk, not committed")
            with self.assertRaises(at.TransportError):
                at.run_history_refresh(self.root, self.anchor)

    def test_non_official_origin_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_hub(tmp)
            _git(self.root, "remote", "set-url", "origin",
                 "https://github.com/EVIL/floe-skill-hub.git")
            with self.assertRaises(at.TransportError):
                at.run_history_refresh(self.root, self.anchor)

    def test_fixed_origin_fetch_argv(self):
        argv = at.fetch_official_refspec("main")
        self.assertEqual(argv[0], "fetch")
        self.assertEqual(argv[2], at.FETCH_ORIGIN_URL)
        self.assertEqual(argv[3], "+refs/heads/main:" + at.LIVE_MAIN_LOCAL_REF)
        self.assertTrue(at.is_official_url(at.FETCH_ORIGIN_URL, at.OFFICIAL_HUB_REPO))
        for bad in ("main; rm -rf /", "..", "-x", "sub\ndir", "../escape",
                    "refs heads x"):
            self.assertRaises(at.TransportError, at.fetch_official_refspec, bad)

    def test_resolve_live_main_no_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_hub(tmp)
            _git(self.root, "update-ref", at.LIVE_MAIN_LOCAL_REF, self.anchor)
            self.assertEqual(at.resolve_live_main(self.root), self.anchor)


# ===========================================================================
# 3. signed relay metadata validation/extraction
# ===========================================================================


class RelayTests(unittest.TestCase):
    maxDiff = None

    def build_catalog_relay(self):
        """A standalone catalog relay: feeds + review pairs + receipt."""
        files = {}
        alpha = _feed_entry("alpha-guide", "ios")
        araw, asig = _review_pair("alpha-guide", "1.0.0", alpha["package"])
        alpha["review"] = {"path": "reviews/alpha-guide/1.0.0.review.json",
                           "sha256": hubcore.sha256_hex(araw),
                           "keyID": hubcore.PRODUCTION_KEY_ID}
        files["reviews/alpha-guide/1.0.0.review.json"] = araw
        files["reviews/alpha-guide/1.0.0.review.json.sig"] = asig
        beta = _feed_entry("beta-guide", "android", plan=2)
        ios_feed = _feed_bytes("ios", [alpha], X_COMMIT)
        android_feed = _feed_bytes("android", [beta], X_COMMIT)
        files["catalog.json"] = ios_feed
        files["catalog.sig"] = _signed(ios_feed)
        files["android/catalog.json"] = android_feed
        files["android/catalog.sig"] = _signed(android_feed)
        # package archives stay at the immutable candidate source: they are
        # bound in the receipt but NEVER relayed here.
        package_outputs = [
            {"path": alpha["package"]["path"], "sha256": hubcore.sha256_hex(b"ZIP1"),
             "size": 4},
            {"path": beta["package"]["path"], "sha256": hubcore.sha256_hex(b"ZIP2"),
             "size": 4},
        ]
        relay_files = dict(files)
        receipt = {"schemaVersion": 1, "mode": "catalog",
                   "hubRepository": "JiangNanGenius/floe-skill-hub",
                   "sourceCommit": X_COMMIT,
                   "keyID": hubcore.PRODUCTION_KEY_ID,
                   "signedFeeds": ["android/catalog.json", "catalog.json"],
                   "outputs": _outputs(relay_files) + package_outputs}
        receipt_bytes = hubcore.encoded(receipt)
        files[at.RELAY_RECEIPT_REL] = receipt_bytes
        files[at.RELAY_RECEIPT_SIG_REL] = _signed(receipt_bytes)
        request = at.build_request("catalog", X_COMMIT, B_COMMIT, POLICY)[1]
        return files, request

    def build_reviews_relay(self):
        raw, sig = _review_pair("alpha-guide", "1.0.0",
                                _feed_entry("alpha-guide", "ios")["package"])
        files = {"reviews/alpha-guide/1.0.0.review.json": raw,
                 "reviews/alpha-guide/1.0.0.review.json.sig": sig}
        receipt = {"schemaVersion": 1, "mode": "reviews",
                   "hubRepository": "JiangNanGenius/floe-skill-hub",
                   "sourceCommit": X_COMMIT,
                   "keyID": hubcore.PRODUCTION_KEY_ID,
                   "reviews": [{"id": "alpha-guide", "version": "1.0.0",
                                "reviewPath": "reviews/alpha-guide/1.0.0.review.json",
                                "recordSha256": hubcore.sha256_hex(raw),
                                "signatureSha256": hubcore.sha256_hex(sig),
                                "keyID": hubcore.PRODUCTION_KEY_ID}],
                   "outputs": _outputs(files)}
        receipt_bytes = hubcore.encoded(receipt)
        files[at.RELAY_RECEIPT_REL] = receipt_bytes
        files[at.RELAY_RECEIPT_SIG_REL] = _signed(receipt_bytes)
        request = at.build_request("reviews", X_COMMIT, B_COMMIT, POLICY)[1]
        return files, request

    @staticmethod
    def container(files, extra_entries=()):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as archive:
            for rel in sorted(files):
                info = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
                info.external_attr = 0o100644 << 16
                archive.writestr(info, files[rel])
            for rel, data, mode in extra_entries:
                info = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
                info.external_attr = mode << 16
                archive.writestr(info, data)
        return buf.getvalue()

    def test_catalog_relay_validates_and_returns_metadata_map(self):
        files, request = self.build_catalog_relay()
        verdict = at.validate_relay_archive(self.container(files), request, TRUST)
        self.assertEqual(verdict["status"], "relay-ok")
        self.assertEqual(set(verdict["files"]), set(files))
        self.assertEqual(verdict["reviewRecordCount"], 1)
        refs = verdict["packageReferences"]
        self.assertEqual({(r["channel"], r["path"]) for r in refs},
                         {("ios", "packages/alpha-guide/1.0.0/alpha-guide.zip"),
                          ("android", "android/packages/beta-guide/1.0.0/beta-guide.zip")})

    def test_reviews_relay_validates(self):
        files, request = self.build_reviews_relay()
        verdict = at.validate_signed_relay(files, request, TRUST)
        self.assertEqual(verdict["status"], "relay-ok")

    def test_forged_receipt_signature_refused(self):
        files, request = self.build_catalog_relay()
        files[at.RELAY_RECEIPT_SIG_REL] = hubcore.sign_envelope(
            files[at.RELAY_RECEIPT_REL], FOREIGN_KEY, hubcore.PRODUCTION_KEY_ID)
        with self.assertRaises(at.TransportError):
            at.validate_signed_relay(files, request, TRUST)

    def test_forged_feed_signature_refused(self):
        files, request = self.build_catalog_relay()
        files["catalog.sig"] = hubcore.sign_envelope(files["catalog.json"],
                                                     FOREIGN_KEY,
                                                     hubcore.PRODUCTION_KEY_ID)
        with self.assertRaises(at.TransportError):
            at.validate_signed_relay(files, request, TRUST)

    def test_metadata_hash_tamper_refused(self):
        files, request = self.build_catalog_relay()
        rel = "reviews/alpha-guide/1.0.0.review.json"
        mutated = bytearray(files[rel])
        mutated[-2] ^= 0x20
        files[rel] = bytes(mutated)
        with self.assertRaises(at.TransportError):
            at.validate_signed_relay(files, request, TRUST)

    def test_source_commit_mismatch_refused(self):
        files, request = self.build_catalog_relay()
        other = at.build_request("catalog", "e" * 40, B_COMMIT, POLICY)[1]
        with self.assertRaises(at.TransportError):
            at.validate_signed_relay(files, other, TRUST)

    @staticmethod
    def resign_receipt(files):
        """Re-bind and re-sign the receipt over the CURRENT metadata files."""
        receipt = json.loads(files[at.RELAY_RECEIPT_REL])
        outputs = []
        for entry in receipt["outputs"]:
            rel = entry["path"]
            if rel in files and rel not in (at.RELAY_RECEIPT_REL,
                                            at.RELAY_RECEIPT_SIG_REL):
                outputs.append({"path": rel,
                                "sha256": hubcore.sha256_hex(files[rel]),
                                "size": len(files[rel])})
            else:
                outputs.append(entry)
        receipt["outputs"] = outputs
        raw = hubcore.encoded(receipt)
        files[at.RELAY_RECEIPT_REL] = raw
        files[at.RELAY_RECEIPT_SIG_REL] = _signed(raw)

    def test_feed_source_commit_drift_refused(self):
        files, request = self.build_catalog_relay()
        feed = json.loads(files["catalog.json"])
        feed["sourceCommit"] = "9" * 40
        raw = hubcore.encoded(feed)
        files["catalog.json"] = raw
        files["catalog.sig"] = _signed(raw)
        self.resign_receipt(files)
        with self.assertRaises(at.TransportError):
            at.validate_signed_relay(files, request, TRUST)

    def test_mode_mismatch_refused(self):
        files, request = self.build_catalog_relay()
        receipt = json.loads(files[at.RELAY_RECEIPT_REL])
        receipt["mode"] = "reviews"
        rb = hubcore.encoded(receipt)
        files[at.RELAY_RECEIPT_REL] = rb
        files[at.RELAY_RECEIPT_SIG_REL] = _signed(rb)
        with self.assertRaises(at.TransportError):
            at.validate_signed_relay(files, request, TRUST)

    def test_unbound_relay_field_refused(self):
        files, request = self.build_reviews_relay()
        raw, sig = _review_pair("sneaky-tool", "1.0.0",
                                _feed_entry("sneaky-tool", "ios")["package"])
        files["reviews/sneaky-tool/1.0.0.review.json"] = raw
        files["reviews/sneaky-tool/1.0.0.review.json.sig"] = sig
        with self.assertRaises(at.TransportError):
            at.validate_signed_relay(files, request, TRUST)

    def test_missing_feed_in_catalog_relay_refused(self):
        files, request = self.build_catalog_relay()
        del files["android/catalog.json"], files["android/catalog.sig"]
        with self.assertRaises(at.TransportError):
            at.validate_signed_relay(files, request, TRUST)

    def test_feeds_never_appear_in_reviews_relay(self):
        files, request = self.build_reviews_relay()
        cfiles, _ = self.build_catalog_relay()
        files["catalog.json"] = cfiles["catalog.json"]
        files["catalog.sig"] = cfiles["catalog.sig"]
        with self.assertRaises(at.TransportError):
            at.validate_signed_relay(files, request, TRUST)

    def test_package_and_executable_members_refused(self):
        files, request = self.build_catalog_relay()
        for bad in ("packages/alpha-guide/1.0.0/alpha-guide.zip",
                    "scripts/evil.py", "android/packages/beta-guide/1.0.0/x.zip",
                    "engines/impeccable/floe-impeccable"):
            members = dict(files)
            members[bad] = b"PK\x03\x04" if bad.endswith(".zip") else b"#!/bin/sh\n"
            with self.assertRaises(at.TransportError, msg=bad):
                at.validate_signed_relay(members, request, TRUST)

    def test_traversal_and_hidden_members_refused(self):
        files, request = self.build_catalog_relay()
        for bad in ("../evil.json", "/etc/passwd", "reviews/../x/review.json",
                    "catalog.json/", ".hidden", "evil\\name.json"):
            members = dict(files)
            members[bad] = b"x"
            with self.assertRaises(at.TransportError, msg=bad):
                at.validate_signed_relay(members, request, TRUST)

    def test_container_duplicate_symlink_directory_refused(self):
        files, request = self.build_catalog_relay()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)  # intentional dup entry
            dup = self.container(files, extra_entries=[
                ("catalog.json", b"second copy", 0o100644)])
        with self.assertRaises(at.TransportError):
            at.validate_relay_archive(dup, request, TRUST)
        sym = self.container(files, extra_entries=[
            ("reviews/alpha-guide/2.0.0.review.json", b"link-target", 0o120000)])
        with self.assertRaises(at.TransportError):
            at.validate_relay_archive(sym, request, TRUST)
        dirow = self.container(files, extra_entries=[
            ("catalog.json/", b"", 0o040000)])
        with self.assertRaises(at.TransportError):
            at.validate_relay_archive(dirow, request, TRUST)

    def test_oversized_member_refused(self):
        files, request = self.build_catalog_relay()
        members = dict(files)
        members["reviews/gamma-guide/1.0.0.review.json"] = \
            b"a" * (at.MAX_RELAY_MEMBER_BYTES + 1)
        members["reviews/gamma-guide/1.0.0.review.json.sig"] = b"{}"
        with self.assertRaises(at.TransportError) as ctx:
            at.validate_signed_relay(members, request, TRUST)
        self.assertIn("bytes", str(ctx.exception))
        with self.assertRaises(at.TransportError):
            at.parse_relay_archive_bytes(b"PK\x03\x04garbage")

    def test_non_canonical_receipt_refused(self):
        files, request = self.build_catalog_relay()
        receipt = json.loads(files[at.RELAY_RECEIPT_REL])
        files[at.RELAY_RECEIPT_REL] = (json.dumps(receipt, indent=1) + "\n").encode()
        with self.assertRaises(at.TransportError):
            at.validate_signed_relay(files, request, TRUST)

    def test_fixture_identity_trust_refused(self):
        files, request = self.build_catalog_relay()
        with self.assertRaises(at.TransportError):
            at.validate_signed_relay(files, request,
                                     {hubcore.FIXTURE_KEY_ID: TEST_PUB})
        with self.assertRaises(at.TransportError):
            at.validate_signed_relay(files, request, {})

    def test_reject_review_record_signed_outside_official_identity(self):
        files, request = self.build_catalog_relay()
        rel = "reviews/alpha-guide/1.0.0.review.json"
        files[rel + ".sig"] = hubcore.sign_envelope(files[rel], FOREIGN_KEY,
                                                    hubcore.PRODUCTION_KEY_ID)
        # rebind the receipt so the forged envelope IS hash-bound: only real
        # cryptographic verification under the anchor trust can stop it now
        self.resign_receipt(files)
        with self.assertRaises(at.TransportError):
            at.validate_signed_relay(files, request, TRUST)


# ===========================================================================
# 4. X-vs-B engine-authority freeze
# ===========================================================================

FROZEN_DESC = hubcore.encoded({"schemaVersion": 1, "componentID": "impeccable-engine",
                               "artifact": {"path": "engines/impeccable/dist/x",
                                            "size": 4, "sha256": "a" * 64}})


def _archive(frozen_bytes):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as archive:
        archive.writestr("SKILL.md", b"# skill\n")
        archive.writestr("references/engine-dependency.json", frozen_bytes)
    return buf.getvalue()


def _guide_archive():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as archive:
        archive.writestr("SKILL.md", b"# guide\n")
    return buf.getvalue()


class EngineFreezeTests(unittest.TestCase):
    def build_repo(self, tmp):
        self.root = _init_repo(pathlib.Path(tmp) / "hub")
        _write(self.root, "engines/impeccable/ENGINE-LOCK.json", b'{"lock":1}\n')
        _write(self.root, "engines/impeccable/runtime-dependency/descriptor.v1.json",
               FROZEN_DESC)
        _write(self.root, "packages/alpha-guide/1.0.0/alpha-guide.zip",
               _archive(FROZEN_DESC))
        _write(self.root, "reviews/alpha-guide/1.0.0.review.json",
               b'{"id":"alpha-guide","version":"1.0.0","decision":"approve"}\n')
        _write(self.root, "reviews/alpha-guide/1.0.0.review.json.sig",
               b"fixture-envelope\n")
        _write(self.root, "catalog/skills.json", b"{}\n")
        self.base = _commit_all(self.root, "base publication B")

    def candidate(self, mutate):
        mutate()
        return _commit_all(self.root, "candidate X")

    def test_matching_candidate_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_repo(tmp)
            live = self.candidate(lambda: _write(
                self.root, "packages/gamma-guide/1.0.0/gamma-guide.zip",
                _archive(FROZEN_DESC)))
            verdict = at.verify_candidate_engine_freeze(self.root, self.base, live)
            self.assertEqual(verdict["status"], "engine-freeze-ok")
            self.assertEqual(verdict["embeddedDescriptorsChecked"], 1)

    def test_guide_only_new_package_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_repo(tmp)
            live = self.candidate(lambda: _write(
                self.root, "packages/delta-guide/1.0.0/delta-guide.zip",
                _guide_archive()))
            self.assertEqual(
                at.verify_candidate_engine_freeze(self.root, self.base, live)
                ["status"], "engine-freeze-ok")

    def test_engine_descriptor_drift_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_repo(tmp)
            live = self.candidate(lambda: _write(
                self.root, "engines/impeccable/runtime-dependency/descriptor.v1.json",
                b'{"schemaVersion":1,"componentID":"evil"}'))
            with self.assertRaises(at.TransportError) as ctx:
                at.verify_candidate_engine_freeze(self.root, self.base, live)
            self.assertIn("engine authority drift", str(ctx.exception))

    def test_engine_addition_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_repo(tmp)
            live = self.candidate(lambda: _write(
                self.root, "engines/impeccable/dist/other/floe-impeccable", b"ELF"))
            self.assertRaises(at.TransportError, at.verify_candidate_engine_freeze,
                              self.root, self.base, live)

    def test_embedded_descriptor_drift_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_repo(tmp)
            foreign = hubcore.encoded({"schemaVersion": 1,
                                       "componentID": "impeccable-engine",
                                       "artifact": {"path": "engines/impeccable/dist/y",
                                                    "size": 9, "sha256": "b" * 64}})
            live = self.candidate(lambda: _write(
                self.root, "packages/gamma-guide/1.0.0/gamma-guide.zip",
                _archive(foreign)))
            with self.assertRaises(at.TransportError) as ctx:
                at.verify_candidate_engine_freeze(self.root, self.base, live)
            self.assertIn("frozen descriptor", str(ctx.exception))

    def test_published_archive_immutability_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_repo(tmp)
            live = self.candidate(lambda: _write(
                self.root, "packages/alpha-guide/1.0.0/alpha-guide.zip",
                _archive(hubcore.encoded({"schemaVersion": 1, "evil": True}))))
            with self.assertRaises(at.TransportError) as ctx:
                at.verify_candidate_engine_freeze(self.root, self.base, live)
            self.assertIn("immutable published archive", str(ctx.exception))

    def test_request_wrapper_rejects_bad_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_repo(tmp)
            live = self.candidate(lambda: _write(self.root, "frozen/ok.txt", b"x"))
            _raw, request = at.build_request("reviews", "z" * 40, self.base, POLICY)
            with self.assertRaises((at.TransportError, hubcore.HubError)):
                at.verify_request_candidate_engine_freeze(self.root, request, live)
            # a well-formed request whose base IS the repo base passes
            _raw, request = at.build_request("reviews", live, self.base, POLICY)
            self.assertEqual(
                at.verify_request_candidate_engine_freeze(self.root, request, live)
                ["status"], "engine-freeze-ok")

    # ---- archive deletion and mode-aware immutable review history ---------

    def test_base_archive_deletion_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_repo(tmp)
            live = self.candidate(
                lambda: _rm(self.root, "packages/alpha-guide/1.0.0/alpha-guide.zip"))
            with self.assertRaises(at.TransportError) as ctx:
                at.verify_candidate_engine_freeze(self.root, self.base, live)
            self.assertIn("immutable published archive deleted", str(ctx.exception))
            # the reviews-mode request binding never lifts the package freeze
            request = at.build_request("reviews", live, self.base, POLICY)[1]
            with self.assertRaises(at.TransportError) as ctx:
                at.verify_request_candidate_engine_freeze(self.root, request, live)
            self.assertIn("immutable published archive deleted", str(ctx.exception))

    def test_base_archive_mode_drift_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_repo(tmp)
            live = self.candidate(lambda: _chmod(
                self.root, "packages/alpha-guide/1.0.0/alpha-guide.zip"))
            with self.assertRaises(at.TransportError) as ctx:
                at.verify_candidate_engine_freeze(self.root, self.base, live)
            self.assertIn("bytes or mode", str(ctx.exception))

    def test_engine_mode_drift_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_repo(tmp)
            live = self.candidate(
                lambda: _chmod(self.root, "engines/impeccable/ENGINE-LOCK.json"))
            with self.assertRaises(at.TransportError) as ctx:
                at.verify_candidate_engine_freeze(self.root, self.base, live)
            self.assertIn("engine authority drift", str(ctx.exception))

    def test_catalog_mode_review_pruning_denied_reviews_mode_allows_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_repo(tmp)
            live = self.candidate(lambda: (
                _rm(self.root, "reviews/alpha-guide/1.0.0.review.json"),
                _rm(self.root, "reviews/alpha-guide/1.0.0.review.json.sig")))
            for call in (lambda: at.verify_candidate_engine_freeze(
                             self.root, self.base, live),  # strict default
                         lambda: at.verify_candidate_engine_freeze(
                             self.root, self.base, live, "catalog")):
                with self.assertRaises(at.TransportError) as ctx:
                    call()
                self.assertIn("pruned from the catalog candidate",
                              str(ctx.exception))
            # only the canonical requestId-bound reviews mode permits pruning
            request = at.build_request("reviews", live, self.base, POLICY)[1]
            verdict = at.verify_request_candidate_engine_freeze(
                self.root, request, live)
            self.assertEqual(verdict["status"], "engine-freeze-ok")
            self.assertEqual(verdict["mode"], "reviews")
            self.assertEqual(verdict["reviewPathsAtBase"], 2)
            self.assertEqual(verdict["reviewPathsRetained"], 0)

    def test_retained_review_mutation_denied_in_every_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_repo(tmp)
            live = self.candidate(lambda: _write(
                self.root, "reviews/alpha-guide/1.0.0.review.json",
                b'{"id":"alpha-guide","version":"1.0.0","decision":"revoke"}\n'))
            with self.assertRaises(at.TransportError):
                at.verify_candidate_engine_freeze(self.root, self.base, live)
            request = at.build_request("reviews", live, self.base, POLICY)[1]
            with self.assertRaises(at.TransportError) as ctx:
                at.verify_request_candidate_engine_freeze(self.root, request, live)
            self.assertIn("can never mutate", str(ctx.exception))

    def test_retained_review_mode_drift_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_repo(tmp)
            live = self.candidate(lambda: _chmod(
                self.root, "reviews/alpha-guide/1.0.0.review.json"))
            request = at.build_request("reviews", live, self.base, POLICY)[1]
            with self.assertRaises(at.TransportError) as ctx:
                at.verify_request_candidate_engine_freeze(self.root, request, live)
            self.assertIn("bytes or mode", str(ctx.exception))

    def test_new_review_pairs_and_versions_allowed_in_catalog_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_repo(tmp)
            live = self.candidate(lambda: (
                _write(self.root, "reviews/alpha-guide/1.1.0.review.json",
                       b'{"id":"alpha-guide","version":"1.1.0","decision":"approve"}\n'),
                _write(self.root, "reviews/alpha-guide/1.1.0.review.json.sig",
                       b"new-envelope\n")))
            verdict = at.verify_candidate_engine_freeze(self.root, self.base, live)
            self.assertEqual(verdict["status"], "engine-freeze-ok")
            self.assertEqual(verdict["reviewPathsAtBase"], 2)
            self.assertEqual(verdict["reviewPathsRetained"], 2)

    def test_wrapper_binds_candidate_to_request_source_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_repo(tmp)
            live = self.candidate(
                lambda: _write(self.root, "sources/x/SKILL.md", b"x\n"))
            request = at.build_request("catalog", "e" * 40, self.base, POLICY)[1]
            with self.assertRaises(at.TransportError) as ctx:
                at.verify_request_candidate_engine_freeze(self.root, request, live)
            self.assertIn("does not equal the request sourceCommit",
                          str(ctx.exception))

    def test_unknown_freeze_mode_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build_repo(tmp)
            live = self.candidate(
                lambda: _write(self.root, "sources/x/SKILL.md", b"x\n"))
            with self.assertRaises(at.TransportError) as ctx:
                at.verify_candidate_engine_freeze(self.root, self.base, live,
                                                  "bypass")
            self.assertIn("no bypass mode", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
