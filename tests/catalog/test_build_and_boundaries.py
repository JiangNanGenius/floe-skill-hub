#!/usr/bin/env python3
"""Feed build, immutability, legacy four-item view and fixture-boundary tests."""
import copy
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "scripts"))
import hubcore
import build_catalog
import build_packages
import make_fixture

REPO = HERE.parents[2]
FIXTURES = HERE.parents[0] / "fixtures"
FAKE_COMMIT = "554dc4b2f6a2b3e0d6a1f6d6a1f6d6a1f6d6a1f6"[:40].ljust(40, "0")
OFFICIAL = hubcore.PRODUCTION_KEY_ID
# Real public trust for the signed-review epoch: preview/release builds verify
# the actual 43 .sig sidecars against public-key.json, never an empty map.
TRUST = build_catalog.load_trust(REPO)


def demote_to_candidate_fixture(view):
    """Explicit fixture staging for synthetic production feeds: the feed
    contract binds reviewed status to a review binding and qualified status
    to package+review. A hand-built feed that carries NO real bindings must
    therefore present the row as an unbound candidate on purpose; the genuine
    signed-review rows are exercised by the real preview/release builds."""
    view["status"] = dict(view["status"], packaged=False, reviewed=False,
                          qualified=False)
    return view


def qualified_builtin(entry, channel="ios"):
    e = copy.deepcopy(entry)
    version = e["version"]
    e["version"] = version
    digest = hubcore.sha256_hex(e["id"].encode())
    binding = {"path": hubcore.package_path_for(e["id"], version, channel),
               "size": 1234, "sha256": digest,
               "contentDigest": hubcore.sha256_hex(e["id"].encode() + b"c"),
               "containsScripts": False}
    review = {"path": f"reviews/{e['id']}/{version}.review.json",
              "sha256": hubcore.sha256_hex(b"review" + e["id"].encode()),
              "keyID": OFFICIAL}
    e["package"] = binding
    e["review"] = review
    e["installOffer"] = "qualified"
    e["status"] = dict(e["status"], adaptation="frozen", packaged=True, reviewed=True,
                       qualified=True)
    e["minimumAppVersion"] = e["minimumAppVersion"] or "1.7.0"
    return e


def refresh_counts(catalog):
    entries = catalog["entries"]
    catalog["counts"] = {
        "total": len(entries),
        "builtin": sum(1 for e in entries if e["kind"] == "builtin"),
        "optional": sum(1 for e in entries if e["kind"] == "optional"),
        "deepAdaptation": sum(1 for e in entries if e["deepAdaptation"]),
        "packaged": sum(1 for e in entries if e["package"]),
        "reviewed": sum(1 for e in entries if e["review"]),
        "qualified": sum(1 for e in entries if e["status"]["qualified"]),
        "offerQualified": sum(1 for e in entries if e["installOffer"] == "qualified"),
    }
    return catalog


def production_catalog(overrides=None):
    registry = json.loads((REPO / "catalog" / "skills.json").read_bytes())
    entries = []
    for row in sorted(registry["skills"], key=lambda e: e["planNumber"]):
        view = hubcore.catalog_entry(row, package=None, review=None, install_offer="none")
        if row["id"] in hubcore.RESERVED_BUILTIN_IDS:
            view = qualified_builtin(view)
        else:
            view = demote_to_candidate_fixture(view)
        if overrides and view["id"] in overrides:
            overrides[view["id"]](view)
        entries.append(view)
    return hubcore.build_catalog(registry, "ios", "production", entries, FAKE_COMMIT)


class TestPreviewBuild(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads((REPO / "catalog" / "skills.json").read_bytes())

    def test_deterministic_bytes(self):
        first = build_catalog.build(self.registry, "preview", FAKE_COMMIT, REPO, REPO, TRUST)
        second = build_catalog.build(self.registry, "preview", FAKE_COMMIT, REPO, REPO, TRUST)
        self.assertEqual(first, second)
        self.assertIn("catalog.json", first)
        self.assertIn("android/catalog.json", first)

    def test_preview_describes_43_with_no_offers(self):
        feeds = build_catalog.build(self.registry, "preview", FAKE_COMMIT, REPO, REPO, TRUST)
        ios = json.loads(feeds["catalog.json"])
        android = json.loads(feeds["android/catalog.json"])
        self.assertEqual(len(ios["entries"]), 43)
        self.assertEqual(len(android["entries"]), 39)  # the four builtins are iOS-only
        self.assertTrue(all(e["installOffer"] == "none" for e in ios["entries"]))
        self.assertEqual(ios["counts"]["packaged"], 43)
        self.assertEqual(ios["counts"]["reviewed"], 43)
        self.assertEqual(ios["counts"]["qualified"], 34)  # status carried from admission
        self.assertEqual(android["counts"]["qualified"], 30)  # 34 minus 4 iOS-only builtins
        self.assertEqual(ios["counts"]["offerQualified"], 0)
        self.assertEqual(android["counts"]["offerQualified"], 0)
        # Every packaged+reviewed row is bound to a real archive AND a
        # trust-verified signed review; preview just never advertises offers.
        for feed in (ios, android):
            for e in feed["entries"]:
                if e["status"]["packaged"]:
                    self.assertIsNotNone(e["package"], e["id"])
                    self.assertIsNotNone(e["review"], e["id"])
                    self.assertEqual(e["review"]["keyID"], OFFICIAL, e["id"])

    def test_release_build_offers_exactly_the_admitted_entries(self):
        # Positive current truth: a release build over the integrated tree
        # carries only the admitted rows, each with real package+review
        # bindings verified against public-key.json trust.
        feeds = build_catalog.build(self.registry, "release", FAKE_COMMIT, REPO, REPO, TRUST)
        ios = json.loads(feeds["catalog.json"])
        android = json.loads(feeds["android/catalog.json"])
        self.assertEqual(ios["counts"]["total"], 34)
        self.assertEqual(android["counts"]["total"], 30)
        for feed in (ios, android):
            self.assertEqual(feed["counts"]["offerQualified"], feed["counts"]["total"])
            for e in feed["entries"]:
                self.assertEqual(e["installOffer"], "qualified", e["id"])
                self.assertIsNotNone(e["package"], e["id"])
                self.assertIsNotNone(e["review"], e["id"])
                hubcore.validate_catalog(feed, channel=feed["channel"])

    def test_release_mode_refuses_when_nothing_is_admitted(self):
        # The fail-closed refusal stays meaningful as an explicit fixture:
        # the same tree with every real admission stripped must refuse.
        pre_admission = copy.deepcopy(self.registry)
        for e in pre_admission["skills"]:
            e["status"] = dict(e["status"], qualified=False)
        with self.assertRaisesRegex(hubcore.HubError, "refuses to emit an empty catalog"):
            build_catalog.build(pre_admission, "release", FAKE_COMMIT, REPO, REPO, TRUST)

    def test_production_requires_commit_and_schema3(self):
        with self.assertRaises(hubcore.HubError):
            hubcore.build_catalog({"publisher": "x"}, "ios", "production", [], None)
        feeds = build_catalog.build(self.registry, "preview", FAKE_COMMIT, REPO, REPO, TRUST)
        self.assertEqual(json.loads(feeds["catalog.json"])["schemaVersion"], 3)

    def test_old_clients_fail_closed_on_schema3(self):
        # the accepted legacy schemaVersion window is [1,2]; 3 must be outside it
        self.assertNotIn(3, (1, 2))

    def test_fixture_feed_never_validates_as_production(self):
        fixture_bytes = (FIXTURES / "catalog.json").read_bytes()
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_catalog(json.loads(fixture_bytes), channel="ios",
                                     allow_fixture=False)
        hubcore.validate_catalog(json.loads(fixture_bytes), channel="ios",
                                 allow_fixture=True)


class TestQualifiedFeed(unittest.TestCase):
    def test_release_view_with_synthetic_qualified_builtins(self):
        registry = json.loads((REPO / "catalog" / "skills.json").read_bytes())
        entries = []
        for row in sorted(registry["skills"], key=lambda e: e["planNumber"]):
            view = hubcore.catalog_entry(row)
            if row["id"] in hubcore.RESERVED_BUILTIN_IDS:
                view = qualified_builtin(view)
            else:
                view = demote_to_candidate_fixture(view)
            entries.append(view)
        feed = hubcore.build_catalog(registry, "ios", "production", entries, FAKE_COMMIT)
        hubcore.validate_catalog(feed, channel="ios")
        self.assertEqual(feed["counts"]["builtin"], 4)
        qualified_ids = {e["id"] for e in feed["entries"] if e["installOffer"] == "qualified"}
        self.assertEqual(qualified_ids, set(hubcore.RESERVED_BUILTIN_IDS))
        for e in feed["entries"]:
            if e["kind"] == "builtin":
                self.assertIsNotNone(e["package"])
                self.assertEqual(e["package"]["path"],
                                 f"packages/{e['id']}/{e['version']}/{e['id']}.zip")

    def test_unqualified_candidate_never_offers_install(self):
        registry = json.loads((REPO / "catalog" / "skills.json").read_bytes())
        # Explicit fixture: rows staged without bindings must also carry no
        # qualified claim, or the feed validator refuses them (see the
        # negative test just below).
        entries = [demote_to_candidate_fixture(hubcore.catalog_entry(e))
                   for e in registry["skills"]
                   if e["id"] not in hubcore.RESERVED_BUILTIN_IDS]
        feed = hubcore.build_catalog(registry, "ios", "production", entries, FAKE_COMMIT)
        self.assertTrue(all(e["installOffer"] == "none" for e in feed["entries"]))

    def test_qualified_offer_requires_package_and_review(self):
        catalog = production_catalog()
        broken = copy.deepcopy(catalog)
        for e in broken["entries"]:
            if e["id"] == "floe-pdf":
                e["review"] = None
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_catalog(broken, channel="ios")

    def test_fixture_review_key_cannot_back_production(self):
        catalog = production_catalog()
        for e in catalog["entries"]:
            if e["id"] == "floe-pdf":
                e["review"]["keyID"] = hubcore.FIXTURE_KEY_ID
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_catalog(catalog, channel="ios")


class TestLegacyView(unittest.TestCase):
    def test_renders_exactly_four_reserved_old_shape(self):
        catalog = production_catalog()
        view = json.loads(hubcore.build_legacy_view(hubcore.encoded(catalog)))
        self.assertEqual(view["schemaVersion"], 2)
        self.assertEqual(view["publisher"], "JiangNanGenius")
        self.assertEqual({p["id"] for p in view["packages"]},
                         set(hubcore.RESERVED_BUILTIN_IDS))
        for package in view["packages"]:
            self.assertTrue(package["path"].startswith("skill-hub/packages/"))
            self.assertTrue(package["releaseNotes"]["en"].strip())
            self.assertTrue(package["releaseNotes"]["zh-Hans"].strip())
            self.assertEqual(hubcore.VERSION_PATTERN.fullmatch(package["version"])
                             is not None, True)

    def test_full_43_feed_still_renders_only_four_legacy_rows(self):
        # The compatibility decoder is the four reserved guides — nothing else,
        # even when the source feed describes all 43 candidates.
        catalog = production_catalog()
        self.assertEqual(len(catalog["entries"]), 43)
        view = json.loads(hubcore.build_legacy_view(hubcore.encoded(catalog)))
        self.assertEqual({p["id"] for p in view["packages"]}, set(hubcore.RESERVED_BUILTIN_IDS))
        self.assertEqual(len(view["packages"]), 4)

    def test_even_a_qualified_candidate_id_cannot_join_the_legacy_view(self):
        # A candidate becoming qualified in the hub feed is legitimate;
        # the legacy four-item decoder must still refuse to widen.
        catalog = production_catalog()
        for e in catalog["entries"]:
            if e["id"] == "deep-research":
                promoted = qualified_builtin(e)
                e.clear(); e.update(promoted)
        refresh_counts(catalog)
        hubcore.validate_catalog(catalog, channel="ios")
        view = json.loads(hubcore.build_legacy_view(hubcore.encoded(catalog)))
        self.assertNotIn("deep-research", {p["id"] for p in view["packages"]})
        self.assertEqual(len(view["packages"]), 4)

    def test_unqualified_builtin_blocks_the_view_with_clear_reason(self):
        catalog = production_catalog()
        for e in catalog["entries"]:
            if e["id"] == "floe-network":
                e["installOffer"] = "none"
                e["package"] = None
                e["review"] = None
                e["status"] = dict(e["status"], qualified=False, packaged=False,
                                   reviewed=False)
        refresh_counts(catalog)
        with self.assertRaises(hubcore.HubError) as ctx:
            hubcore.build_legacy_view(hubcore.encoded(catalog))
        self.assertIn("no qualified package", str(ctx.exception))

    def test_legacy_cli_reports_pending_without_root_catalog(self):
        result = run_cli("build_legacy_view.py", ["--catalog", str(REPO / "catalog.json")])
        self.assertNotEqual(result["code"], 0)
        self.assertIn("production feed", result["output"])


class TestImmutability(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="hub-immutable-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        registry = json.loads((REPO / "catalog" / "skills.json").read_bytes())
        self.entry = next(e for e in registry["skills"] if e["id"] == "floe-pdf")
        # This isolated immutability case deliberately exercises one fixed
        # version; later candidate targets must not change its test identity.
        self.entry["versionTarget"] = "1.3.1"
        self.entry["firstParty"]["stagedSourceVersion"] = "1.3.1"

    def stage(self, files):
        src = self.root / "sources" / self.entry["id"]
        src.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            target = src / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)

    def test_rebuild_identical_is_a_noop_and_changed_bytes_are_refused(self):
        files = {
            "SKILL.md": b"---\nname: floe-pdf\ndescription: staged probe\n---\n\nBody.\n",
            "floe.json": hubcore.encoded({"schemaVersion": 1, "id": "floe-pdf",
                                          "version": "1.3.1", "capabilities": [],
                                          "tools": [], "platforms": ["ios"],
                                          "scriptRuntime": "none", "pythonPackages": []}),
        }
        self.stage(files)
        built = build_packages.build_one("floe-pdf", self.entry, check=False, root=self.root)
        self.assertTrue(any("packages/floe-pdf/1.3.1/floe-pdf.zip" in name for name in built))
        again = build_packages.build_one("floe-pdf", self.entry, check=False, root=self.root)
        self.assertEqual(again, [])  # immutable archive unchanged
        files["SKILL.md"] = b"---\nname: floe-pdf\ndescription: staged probe\n---\n\nChanged.\n"
        self.stage(files)
        with self.assertRaises(hubcore.HubError) as ctx:
            build_packages.build_one("floe-pdf", self.entry, check=False, root=self.root)
        self.assertIn("immutable version changed", str(ctx.exception))

    def test_version_target_must_match_staged_manifest(self):
        files = {
            "SKILL.md": b"---\nname: floe-pdf\ndescription: staged probe\n---\n\nBody.\n",
            "floe.json": hubcore.encoded({"schemaVersion": 1, "id": "floe-pdf",
                                          "version": "9.9.9", "capabilities": [],
                                          "tools": [], "platforms": ["ios"],
                                          "scriptRuntime": "none", "pythonPackages": []}),
        }
        self.stage(files)
        with self.assertRaises(hubcore.HubError):
            build_packages.build_one("floe-pdf", self.entry, check=True, root=self.root)


class TestFixtureBoundary(unittest.TestCase):
    def test_fixture_files_stay_under_tests_catalog_fixtures(self):
        # packages/** and reviews/** are now canonical admitted data (signed
        # review epoch); what must NOT exist before the coordinator's
        # publication run are the production channel feeds and their sigs.
        for production in (REPO / "catalog.json", REPO / "catalog.sig",
                           REPO / "android" / "catalog.json",
                           REPO / "android" / "catalog.sig"):
            self.assertFalse(production.exists(), f"production path claimed: {production}")

    def test_fixture_identity_is_unmistakable(self):
        marker = (FIXTURES / "FIXTURE-ONLY.md").read_text()
        self.assertIn("FIXTURE ONLY", marker)
        keydoc = json.loads((FIXTURES / "fixture-public-key.json").read_bytes())
        self.assertTrue(keydoc["fixtureOnly"] and keydoc["notATrustRoot"])
        self.assertEqual(keydoc["keyID"], hubcore.FIXTURE_KEY_ID)
        for rel in ("catalog.json", "android/catalog.json"):
            feed = json.loads((FIXTURES / rel).read_bytes())
            self.assertEqual(feed["feedStatus"], "fixture")
            self.assertIsNone(feed["sourceCommit"])
            for e in feed["entries"]:
                self.assertTrue(e["id"].startswith("fixture-"))
        for rel in ("catalog.sig", "android/catalog.sig"):
            self.assertEqual(json.loads((FIXTURES / rel).read_bytes())["keyID"],
                             hubcore.FIXTURE_KEY_ID)

    def test_fixture_rebuild_is_byte_stable(self):
        outputs = make_fixture.build_outputs()
        for name, data in outputs.items():
            self.assertEqual((FIXTURES / name).read_bytes(), data, name)

    def test_fixture_never_collides_with_registry_ids(self):
        registry = json.loads((REPO / "catalog" / "skills.json").read_bytes())
        registry_ids = {e["id"] for e in registry["skills"]}
        feed = json.loads((FIXTURES / "catalog.json").read_bytes())
        self.assertFalse({e["id"] for e in feed["entries"]} & registry_ids)

    def test_scripted_sample_has_two_states(self):
        feed = json.loads((FIXTURES / "catalog.json").read_bytes())
        offers = {e["id"]: e["installOffer"] for e in feed["entries"]}
        self.assertEqual(offers["fixture-guide"], "none")
        self.assertEqual(offers["fixture-script"], "none")      # packaged but unreviewed
        self.assertEqual(offers["fixture-reviewed"], "fixture-simulated")


def run_cli(script, argv):
    import subprocess
    proc = subprocess.run([sys.executable, str(REPO / "scripts" / script)] + argv,
                          capture_output=True, text=True)
    return {"code": proc.returncode, "output": proc.stdout + proc.stderr}
