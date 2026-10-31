"""Complete-view admission and history use actual bound bytes and test keys."""
import copy
import json
import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests/catalog"))
import build_catalog
import catalog_views as cv
import hubcore
import publication_immutability as pi
import sign_publication as sp
import runtime_dependency
from test_publication_immutability import LedgerFixture, feed, feed_entry, _commit_all


class CompleteHistoryTests(LedgerFixture):
    def publish_complete(self):
        bodies = {}
        for channel in cv.LEGACY_VIEWS:
            old = feed_entry("skill-old", "1.0.0", self.digest_a, channel)
            new = feed_entry("skill-new", "1.0.0", self.digest_b, channel, plan=44)
            for view, entries in ((channel, [old]), (channel + "-full", [old, new])):
                raw = hubcore.encoded(feed(channel, entries))
                rel, sig = cv.FEED_PATHS[view]
                (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
                (self.root / rel).write_bytes(raw)
                (self.root / sig).write_bytes(hubcore.sign_envelope(raw, self.key, hubcore.PRODUCTION_KEY_ID))
                bodies[rel] = raw
        pin = _commit_all(self.root, "complete publication")
        rows = self.ledger_rows_for(pin, channels=cv.VIEWS)
        self.write_ledger(rows)
        return pin, bodies, rows

    def test_full_only_offer_is_a_normalized_immutable_fact(self):
        pin, bodies, _ = self.publish_complete()
        baseline = pi.build_validated_baseline(self.root, published_pin=pin)
        self.assertEqual(baseline[("ios", "skill-new", "1.0.0")], self.digest_b)
        self.assertTrue(baseline.complete_view_seen)
        bad = dict(bodies)
        changed = json.loads(bad["catalog-full.json"])
        changed["entries"][-1]["package"]["contentDigest"] = "9" * 64
        bad["catalog-full.json"] = hubcore.encoded(changed)
        with self.assertRaisesRegex(hubcore.HubError, "immutable publication"):
            pi.assert_immutable_publication(bad, baseline)

    def test_complete_view_cannot_be_removed_after_introduction(self):
        pin, bodies, _ = self.publish_complete()
        baseline = pi.build_validated_baseline(self.root, published_pin=pin)
        legacy = {name: raw for name, raw in bodies.items() if "-full" not in name}
        with self.assertRaisesRegex(hubcore.HubError, "complete and legacy"):
            pi.assert_immutable_publication(legacy, baseline)

    def test_partial_full_signature_set_is_not_historical_absence(self):
        self.publish_complete()
        (self.root / "android/catalog-full.sig").unlink()
        with self.assertRaisesRegex(hubcore.HubError, "incomplete complete-view"):
            pi.load_trustworthy_baseline(self.root)

    def test_forged_full_signature_is_rejected(self):
        self.publish_complete()
        (self.root / "catalog-full.sig").write_bytes(b"{}")
        with self.assertRaises(hubcore.HubError):
            pi.load_trustworthy_baseline(self.root)

    def test_ledger_view_is_not_a_new_signed_channel(self):
        pin, _, rows = self.publish_complete()
        row = next(r for r in rows if r["channel"] == "ios-full")
        self.assertEqual(row, pi.build_ledger_row(self.root, pin, "ios-full"))
        signed = json.loads((self.root / "catalog-full.json").read_bytes())
        self.assertEqual(signed["channel"], "ios")
        with self.assertRaisesRegex(hubcore.HubError, "unknown channel"):
            pi.build_ledger_row(self.root, pin, "unknown-full")

    def test_historical_row_order_is_preserved(self):
        _, _, rows = self.publish_complete()
        self.write_ledger(list(reversed(rows)), commit=False)
        with self.assertRaisesRegex(hubcore.HubError, "append-only"):
            pi.verify_ledger(self.root / pi.LEDGER_REL, self.root)

    def test_source_or_retained_row_disagreement_is_rejected(self):
        _, bodies, _ = self.publish_complete()
        bad = dict(bodies)
        legacy = json.loads(bad["catalog.json"])
        legacy["sourceCommit"] = "e" * 40
        bad["catalog.json"] = hubcore.encoded(legacy)
        with self.assertRaisesRegex(hubcore.HubError, "exact complete-view projection"):
            cv.assert_projection(bad)


class AppendedGuideTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="hub-full-guide-")
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        Ed25519PrivateKey, _, serialization, _ = hubcore._load_ed25519()
        self.key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
        import base64
        public = base64.b64encode(self.key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
        self.trust = {hubcore.PRODUCTION_KEY_ID: public}
        self.registry = json.loads((ROOT / "catalog/skills.json").read_bytes())
        self.registry["skills"] = [r for r in self.registry["skills"] if r["planNumber"] <= 43]
        for row in self.registry["skills"]:
            row["status"].update(qualified=False, packaged=False, reviewed=False,
                                 published=False, executionVerified=False)
            row["plannedRuntime"]["execution"] = {"os": None, "arch": "n/a", "evidence": "unproven"}
        old = next(r for r in self.registry["skills"] if r["id"] == "meetings")
        new = copy.deepcopy(old)
        new.update(id="construction-estimate-builder", planNumber=44, source="O")
        new["upstream"].update(repository="https://github.com/example/maintained-skills",
                               path="skills/estimate", skillManifestPath="skills/estimate/SKILL.md")
        self.registry["skills"].append(new)
        for row in (old, new):
            row.update(versionTarget="1.0.0", minimumAppVersion="1.7.59")
            row["plannedRuntime"].update(scriptRuntime="none", tools=[], pythonPackagesPlan=[],
                installPlatforms=["ios", "android"], capabilities=["workspace.read", "workspace.write"],
                execution={"os": None, "arch": "n/a", "evidence": "unproven"})
            row["status"].update(qualified=True, packaged=True, reviewed=True, adaptation="frozen")
            manifest = {"schemaVersion": 1, "id": row["id"], "version": "1.0.0",
                "platforms": ["ios", "linux"], "scriptRuntime": "none", "tools": [],
                "pythonPackages": [], "capabilities": ["workspace.read", "workspace.write"]}
            files = {"SKILL.md": ("---\nname: " + row["id"] + "\ndescription: Synthetic guide.\n---\n\nUse supplied files.\n").encode(),
                     "floe.json": hubcore.encoded(manifest),
                     "references/UPSTREAM-LICENSE.txt": b"MIT license notice, synthetic test data only.\n"}
            archive = hubcore.make_zip(files)
            for channel in cv.LEGACY_VIEWS:
                path = self.root / hubcore.package_path_for(row["id"], "1.0.0", channel)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive)
            record = {"schemaVersion": 1, "id": row["id"], "version": "1.0.0",
                "contentDigest": hubcore.content_digest(files), "packageSha256": hubcore.sha256_hex(archive),
                "reviewedCapabilities": manifest["capabilities"], "reviewedTools": [], "reviewedPythonPackages": [],
                "execution": {"os": None, "arch": "n/a", "evidence": "unproven"},
                "reviewStage": "static-content-reviewed", "reviewedAt": "2026-10-31",
                "reviewer": "synthetic fixture", "decision": "approve", "notes": {"en": "fixture", "zh-Hans": "测试"}}
            path = self.root / "reviews" / row["id"] / "1.0.0.review.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(hubcore.encoded(record))
            path.with_name(path.name + ".sig").write_bytes(hubcore.sign_envelope(path.read_bytes(), self.key, hubcore.PRODUCTION_KEY_ID))
        hubcore.validate_registry(self.registry)

    def outputs(self):
        return build_catalog.build(self.registry, "release", "a" * 40, self.root, self.root, self.trust)

    def test_real_bound_append_is_only_in_complete_view(self):
        outputs = self.outputs()
        for prefix in ("", "android/"):
            self.assertEqual(len(json.loads(outputs[prefix + "catalog.json"])["entries"]), 1)
            complete = json.loads(outputs[prefix + "catalog-full.json"])
            self.assertEqual([r["planNumber"] for r in complete["entries"]], [41, 44])
            self.assertEqual(complete["entries"][-1]["source"], "O")
        gate = sp.enforce_launch_gate(hubcore, runtime_dependency,
            SimpleNamespace(data=str(self.root), source_commit="a" * 40), self.registry, outputs)
        self.assertEqual((gate["iosQualified"], gate["androidQualified"]), (2, 2))

    def test_android_floor_needs_reviewed_known_guide(self):
        outputs = self.outputs()
        added = json.loads(outputs["android/catalog-full.json"])["entries"][-1]
        self.assertEqual(added["minimumAppVersion"], "0.0.0")
        manifest = {"platforms": ["ios", "linux"], "scriptRuntime": "none",
                    "capabilities": ["workspace.read"], "tools": [], "pythonPackages": []}
        review = {"reviewStage": "static-content-reviewed",
                  "execution": {"os": None, "arch": "n/a", "evidence": "unproven"}}
        self.assertTrue(build_catalog.android_portable_guide_eligible(manifest, review))
        for key, value in (("tools", ["exec.shell"]), ("scriptRuntime", "remote"),
                           ("platforms", ["ios"]), ("pythonPackages", [{"spec": "a==1"}])):
            self.assertFalse(build_catalog.android_portable_guide_eligible(dict(manifest, **{key: value}), review))

    def test_missing_complete_view_cannot_pass_launch_gate(self):
        outputs = self.outputs()
        del outputs["android/catalog-full.json"]
        with self.assertRaises(sp.SigningError):
            sp.enforce_launch_gate(hubcore, runtime_dependency,
                SimpleNamespace(data=str(self.root), source_commit="a" * 40), self.registry, outputs)

    def test_unknown_or_misattributed_source_is_refused(self):
        for source in ("unknown", "R"):
            registry = copy.deepcopy(self.registry)
            registry["skills"][-1]["source"] = source
            with self.assertRaises(hubcore.HubError):
                hubcore.validate_registry(registry)
        registry = copy.deepcopy(self.registry)
        registry["skills"][0]["source"] = "O"
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_registry(registry)
