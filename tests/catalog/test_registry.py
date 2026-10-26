#!/usr/bin/env python3
"""Registry contract tests: 43 rows, pins, statuses, names and blockers."""
import hashlib
import json
import pathlib
import re
import sys
import unittest

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "scripts"))
import hubcore

REPO = HERE.parents[2]
REGISTRY = json.loads((REPO / "catalog" / "skills.json").read_bytes())

EXPECTED_DEEP = {"literature-review", "exploratory-data-analysis", "statistical-analysis",
                 "scientific-visualization", "markitdown", "impeccable",
                 "algorithmic-art", "canvas-design", "webapp-testing"}
EXPECTED_ORIGINAL_REPLACEMENTS = {"doc-coauthoring", "writing-guidelines", "react-best-practices",
                    "composition-patterns", "web-design-guidelines"}
EXPECTED_FIRST_PARTY_PENDING = {"floe-email-drafting", "floe-file-organizer",
                                "floe-invoice-organizer"}
# Signed-review admission epoch (Root curation decision, 2026-10-26): the 32
# guide-only IDs carry a static-content-reviewed approve record and are
# admitted qualified; the 2 guest IDs also hold a real riscv64 guest receipt.
EXPECTED_GUIDE_QUALIFIED = {
    "a11y-audit", "code-to-prd", "composition-patterns", "content-production",
    "copy-editing", "copywriting", "deep-research", "deepread", "doc-coauthoring",
    "floe-email-drafting", "floe-file-organizer", "floe-invoice-organizer",
    "floe-network", "floe-office", "floe-pdf", "floe-video", "internal-comms",
    "meetings", "product-discovery", "product-manager-toolkit",
    "react-best-practices", "requesting-code-review", "research-summarizer",
    "scientific-critical-thinking", "social-content", "systematic-debugging",
    "test-driven-development", "theme-factory", "ui-design-system",
    "ux-researcher-designer", "web-design-guidelines", "writing-guidelines"}
EXPECTED_GUEST_EXEC_VERIFIED = {"citation-management", "sympy"}
# The remaining scripted rows keep executionVerified False and unproven
# evidence until their own real guest runs exist; none may claim qualification.
EXPECTED_UNQUALIFIED_SCRIPT_IDS = {
    "algorithmic-art", "canvas-design", "exploratory-data-analysis", "impeccable",
    "literature-review", "markitdown", "scientific-visualization",
    "statistical-analysis", "webapp-testing"}
PLAN_ZH = {5: "文档协作", 7: "技术写作检查", 15: "文献综述", 22: "格式转 Markdown",
           24: "Impeccable", 30: "React 最佳实践", 41: "会议纪要"}


class TestRegistry(unittest.TestCase):
    def setUp(self):
        hubcore.validate_registry(REGISTRY)
        self.entries = {e["id"]: e for e in REGISTRY["skills"]}

    def test_counts_and_kinds(self):
        self.assertEqual(len(REGISTRY["skills"]), 43)
        builtins = [e for e in REGISTRY["skills"] if e["kind"] == "builtin"]
        self.assertEqual({e["id"] for e in builtins}, set(hubcore.RESERVED_BUILTIN_IDS))
        self.assertEqual(sum(1 for e in REGISTRY["skills"] if e["kind"] == "optional"), 39)

    def test_plan_rows_unique(self):
        self.assertEqual(sorted(e["planNumber"] for e in REGISTRY["skills"]),
                         list(range(1, 44)))

    def test_deep_adaptations_are_the_nine_planned(self):
        self.assertEqual({e["id"] for e in REGISTRY["skills"] if e["deepAdaptation"]},
                         EXPECTED_DEEP)

    def test_current_admission_is_exact_after_signed_reviews(self):
        # Positive truth of the signed-review admission epoch: every row is
        # packaged+reviewed (all 43 records now carry verified signatures),
        # exactly the 32 guides + 2 guest scripts are qualified, the 2 guests
        # alone carry executionVerified from real receipts, and NOTHING is
        # published until the coordinator runs the launch gate and signs feeds.
        admitted = EXPECTED_GUIDE_QUALIFIED | EXPECTED_GUEST_EXEC_VERIFIED
        for e in REGISTRY["skills"]:
            st = e["status"]
            self.assertTrue(st["packaged"] and st["reviewed"] and st["licenseChecked"],
                            f"{e['id']} must be packaged+reviewed+licenseChecked")
            self.assertFalse(st["published"], f"{e['id']} claims publication")
            self.assertEqual(st["qualified"], e["id"] in admitted, e["id"])
            self.assertEqual(st["executionVerified"], e["id"] in EXPECTED_GUEST_EXEC_VERIFIED,
                             e["id"])
        self.assertEqual({e["id"] for e in REGISTRY["skills"] if e["status"]["qualified"]},
                         admitted)
        # The nine held scripts stay fully unqualified and unproven.
        for e in REGISTRY["skills"]:
            if e["id"] in EXPECTED_UNQUALIFIED_SCRIPT_IDS:
                self.assertEqual(e["plannedRuntime"]["scriptRuntime"], "remote", e["id"])
                self.assertFalse(e["status"]["qualified"], e["id"])
                self.assertFalse(e["status"]["executionVerified"], e["id"])

    def test_status_invariants_reject_explicitly_constructed_invalid_rows(self):
        # Negatives are real fixtures, not accidental registry state: each
        # case deliberately builds a status claim the entry has not earned.
        cases = ("published_without_qualified", "qualified_without_reviewed",
                 "qualified_without_packaged", "executionVerified_without_frozen")
        for case in cases:
            with self.subTest(case=case):
                broken = json.loads(json.dumps(REGISTRY))
                target = next(e for e in broken["skills"] if e["id"] == "a11y-audit")
                if case == "published_without_qualified":
                    target["status"]["qualified"] = False
                    target["status"]["published"] = True
                elif case == "qualified_without_reviewed":
                    target["status"]["reviewed"] = False
                elif case == "qualified_without_packaged":
                    target["status"]["packaged"] = False
                elif case == "executionVerified_without_frozen":
                    target["status"]["adaptation"] = "in-progress"
                    target["status"]["executionVerified"] = True
                with self.assertRaises(hubcore.HubError):
                    hubcore.validate_registry(broken)
        # A guide-only row can never carry an execution claim, and an
        # unverified script can never claim guest evidence.
        guide = json.loads(json.dumps(REGISTRY))
        row = next(e for e in guide["skills"] if e["plannedRuntime"]["scriptRuntime"] == "none")
        row["plannedRuntime"]["execution"] = {"os": "linux", "arch": "riscv64",
                                              "evidence": "guest-verified"}
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_registry(guide)
        script = json.loads(json.dumps(REGISTRY))
        row = next(e for e in script["skills"]
                   if e["plannedRuntime"]["scriptRuntime"] != "none"
                   and not e["status"]["executionVerified"])
        row["plannedRuntime"]["execution"]["evidence"] = "guest-verified"
        with self.assertRaisesRegex(hubcore.HubError, "executionVerified"):
            hubcore.validate_registry(script)

    def test_pins_equal_review_baseline_document(self):
        pins = json.loads((REPO / "docs" / "UPSTREAM-PINS.json").read_bytes())["repositories"]
        for e in REGISTRY["skills"]:
            if e["upstream"]:
                repo = e["upstream"]["repository"].removeprefix("https://github.com/")
                self.assertEqual(e["upstream"]["commit"], pins[repo], e["id"])
            elif e["firstParty"]:
                self.assertEqual(e["firstParty"]["licenseStatus"], "floe-owned")

    def test_skill_md_paths_exist_under_pin_path(self):
        for e in REGISTRY["skills"]:
            if e["upstream"]:
                self.assertTrue(e["upstream"]["skillManifestPath"].endswith("SKILL.md"))
                self.assertTrue(e["upstream"]["skillManifestPath"]
                                .startswith(e["upstream"]["path"] + "/"))
        self.assertEqual(self.entries["impeccable"]["upstream"]["path"],
                         "plugin/skills/impeccable")

    def assert_admitted_first_party_source(self, sid, required_phrases):
        """Shared truth for first-party owned optional sources AFTER the
        coordinator admitted the 34 complete ordinary sources at the source
        freeze 4e1b3ff (2026-10-26): their own content is pinned by the actual
        Hub source commit, not by fabricated upstream/firstParty pin blocks.
        # These replace the obsolete planning-state assertions that required
        # sourcePinned=False (and awaiting-implementation) forever. After the
        # signed-review admission these eight owned guides are packaged,
        # reviewed and qualified; publication stays closed."""
        e = self.entries[sid]
        # Identity stays honest: no fabricated upstream or firstParty pin.
        self.assertEqual(e["source"], "F", sid)
        self.assertIsNone(e["upstream"], sid)
        self.assertIsNone(e["firstParty"], sid)
        # Current admitted source state.
        self.assertTrue(e["status"]["sourcePinned"], sid)
        self.assertTrue(e["status"]["licenseChecked"], sid)
        self.assertEqual(e["status"]["adaptation"], "frozen", sid)
        # Signed-review admission: guide-only owned rows are packaged,
        # reviewed and qualified; publication and any guest execution claim
        # stay closed for every guide.
        self.assertTrue(e["status"]["packaged"], sid)
        self.assertTrue(e["status"]["reviewed"], sid)
        self.assertTrue(e["status"]["qualified"], sid)
        for pending in ("published", "executionVerified"):
            self.assertFalse(e["status"][pending], f"{sid} claims {pending}")
        self.assertTrue(e["notes"]["en"].strip() and e["notes"]["zh-Hans"].strip())
        # Stronger positives: the actual owned source files exist and bind the
        # registry row (valid manifest version/id).
        source = REPO / "sources" / sid
        skill = source / "SKILL.md"
        self.assertTrue(skill.is_file() and skill.read_bytes().strip(), sid)
        manifest = json.loads((source / "floe.json").read_bytes())
        self.assertEqual(manifest["schemaVersion"], 1, sid)
        self.assertEqual(manifest["id"], sid)
        hubcore.require_version(manifest["version"], f"{sid} manifest version")
        self.assertEqual(manifest["version"], e["versionTarget"], sid)
        # Recorded provenance: original candidate identity and no-upstream
        # bytes are documented, plus the full ownership notice and license.
        provenance = (source / "references/PROVENANCE.md").read_text()
        for phrase in required_phrases:
            self.assertIn(phrase, provenance, f"{sid}: {phrase!r}")
        self.assertTrue((source / "references/licenses/FLOE-OWNED-NOTICE.md").is_file())
        self.assertTrue((source / "references/licenses/FLOE-LICENSE.txt").is_file())
        # Re-provenance against the committed checkout bytes: every per-file
        # sha256 recorded in PROVENANCE.md must still match what is on disk,
        # so a silent source drift breaks this regression.
        inventory = re.findall(r"`([^`]+)` sha256 `([0-9a-f]{64})`", provenance)
        self.assertTrue(inventory, f"{sid}: no per-file hash inventory")
        for rel, sha in inventory:
            path = source / rel
            self.assertTrue(path.is_file(), f"{sid}: inventory lists missing {rel}")
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), sha,
                             f"{sid}: committed bytes drifted for {rel}")

    def test_unlicensed_candidates_use_documented_first_party_replacements(self):
        # The five license-blocked upstream candidates were replaced by
        # first-party owned content (no upstream bytes) and admitted at the
        # 4e1b3ff source freeze; the row identity is preserved and every
        # approval flag stays false.
        for sid in EXPECTED_ORIGINAL_REPLACEMENTS:
            with self.subTest(sid=sid):
                self.assert_admitted_first_party_source(
                    sid, ("Original candidate identity", "No upstream bytes"))

    def test_verified_status_requires_evidence_path(self):
        for e in REGISTRY["skills"]:
            if e["upstream"] and e["upstream"]["licenseStatus"] == "verified":
                self.assertTrue(e["upstream"]["licenseEvidencePath"])

    def test_first_party_pending_entries_have_no_fabricated_pin(self):
        # These three first-party guides were still "awaiting-implementation"
        # when this regression was written; the coordinator has since admitted
        # their complete owned sources (4e1b3ff). The anti-fabrication core is
        # kept verbatim (upstream/firstParty must stay null); the obsolete
        # planning-state lines are replaced by the current-source positives.
        for sid in EXPECTED_FIRST_PARTY_PENDING:
            with self.subTest(sid=sid):
                self.assert_admitted_first_party_source(
                    sid, ("first-party", "No upstream sources were copied"))

    def test_synthetic_qualification_without_prerequisites_is_rejected(self):
        # Negatives stay real even after admission: a row may not claim a
        # stage above the one it actually holds, and held scripts cannot
        # borrow the two verified guests' evidence.
        for field, demote in (("qualified", "reviewed"), ("published", "qualified")):
            with self.subTest(field=field):
                broken = json.loads(json.dumps(REGISTRY))
                target = next(e for e in broken["skills"]
                              if e["id"] == "doc-coauthoring")
                target["status"][demote] = False
                target["status"][field] = True
                with self.assertRaises(hubcore.HubError):
                    hubcore.validate_registry(broken)
        broken = json.loads(json.dumps(REGISTRY))
        target = next(e for e in broken["skills"]
                      if e["id"] in EXPECTED_UNQUALIFIED_SCRIPT_IDS)
        self.assertFalse(target["status"]["executionVerified"])
        target["plannedRuntime"]["execution"]["evidence"] = "guest-verified"
        with self.assertRaisesRegex(hubcore.HubError, "executionVerified"):
            hubcore.validate_registry(broken)
        broken = json.loads(json.dumps(REGISTRY))
        row = next(e for e in broken["skills"] if e["id"] == "doc-coauthoring")
        row["status"]["licenseChecked"] = False  # reviewed requires a completed license check
        with self.assertRaisesRegex(hubcore.HubError, "license check"):
            hubcore.validate_registry(broken)

    def test_builtin_released_and_staged_versions_kept_distinct(self):
        office = self.entries["floe-office"]["firstParty"]
        self.assertEqual(office["releasedVersion"], "1.3.0")
        self.assertEqual(office["stagedSourceVersion"], "1.5.0")
        self.assertEqual(self.entries["floe-office"]["versionTarget"], "1.5.0")

    def test_bilingual_names_follow_the_plan(self):
        for row, name in PLAN_ZH.items():
            entry = next(e for e in REGISTRY["skills"] if e["planNumber"] == row)
            self.assertEqual(entry["name"]["zh-Hans"], name)

    def test_generic_zh_names_must_be_translated(self):
        broken = json.loads(json.dumps(REGISTRY))
        broken["skills"][12]["name"] = {"en": "Deep Research", "zh-Hans": "Deep Reseach"}
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_registry(broken)
        brand = json.loads(json.dumps(REGISTRY))
        target = next(e for e in brand["skills"] if e["id"] == "impeccable")
        target["name"] = {"en": "Impeccable", "zh-Hans": "Impeccable"}
        hubcore.validate_registry(brand)  # kept-identical brand names stay legal

    def test_execution_claims_are_exact_and_minimal(self):
        # 41 of 43 rows must keep unproven evidence; only the two genuine
        # guest receipts may claim guest-verified, and only with
        # executionVerified set. Guides carry no execution claim at all.
        for e in REGISTRY["skills"]:
            if e["id"] in EXPECTED_GUEST_EXEC_VERIFIED:
                self.assertEqual(e["plannedRuntime"]["execution"]["evidence"],
                                 "guest-verified", e["id"])
                self.assertTrue(e["status"]["executionVerified"], e["id"])
            else:
                self.assertEqual(e["plannedRuntime"]["execution"]["evidence"],
                                 "unproven", e["id"])
                self.assertFalse(e["status"]["executionVerified"], e["id"])
            if e["plannedRuntime"]["scriptRuntime"] == "none":
                self.assertEqual(e["plannedRuntime"]["execution"],
                                 {"os": None, "arch": "n/a", "evidence": "unproven"},
                                 e["id"])

    def test_categories_and_tags_shape(self):
        self.assertEqual({c["id"] for c in REGISTRY["categories"]}, set(hubcore.CATEGORIES))
        for e in REGISTRY["skills"]:
            self.assertIn(e["category"], hubcore.CATEGORIES)
            self.assertGreaterEqual(len(e["tags"]), 2)

    def test_guide_only_entries_declare_no_execution(self):
        for e in REGISTRY["skills"]:
            if e["plannedRuntime"]["scriptRuntime"] == "none":
                self.assertNotIn("exec.shell", e["plannedRuntime"]["tools"])
                self.assertNotIn("execution.remote", e["plannedRuntime"]["capabilities"])
