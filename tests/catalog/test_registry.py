#!/usr/bin/env python3
"""Registry contract tests: 43 rows, pins, statuses, names and blockers."""
import json
import pathlib
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

    def test_no_status_exceeds_candidate_evidence(self):
        for e in REGISTRY["skills"]:
            for forbidden in ("reviewed", "qualified", "published", "executionVerified"):
                self.assertFalse(e["status"][forbidden], f"{e['id']} claims {forbidden}")
            self.assertFalse(e["status"]["packaged"])

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

    def test_unlicensed_candidates_use_documented_first_party_replacements(self):
        for sid in EXPECTED_ORIGINAL_REPLACEMENTS:
            e = self.entries[sid]
            self.assertEqual(e["source"], "F")
            self.assertIsNone(e["upstream"])
            self.assertIsNone(e["firstParty"])
            self.assertFalse(e["status"]["sourcePinned"])
            self.assertTrue(e["status"]["licenseChecked"])
            self.assertTrue(e["notes"]["en"].strip() and e["notes"]["zh-Hans"].strip())
            source = REPO / "sources" / sid
            provenance = (source / "references/PROVENANCE.md").read_text()
            self.assertIn("Original candidate identity", provenance)
            self.assertIn("No upstream bytes", provenance)
            self.assertTrue((source / "references/licenses/FLOE-OWNED-NOTICE.md").is_file())

    def test_verified_status_requires_evidence_path(self):
        for e in REGISTRY["skills"]:
            if e["upstream"] and e["upstream"]["licenseStatus"] == "verified":
                self.assertTrue(e["upstream"]["licenseEvidencePath"])

    def test_first_party_pending_entries_have_no_fabricated_pin(self):
        for sid in EXPECTED_FIRST_PARTY_PENDING:
            e = self.entries[sid]
            self.assertIsNone(e["upstream"])
            self.assertIsNone(e["firstParty"])
            self.assertFalse(e["status"]["sourcePinned"])
            self.assertEqual(e["status"]["adaptation"], "awaiting-implementation")

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

    def test_execution_claims_stay_unproven(self):
        for e in REGISTRY["skills"]:
            self.assertEqual(e["plannedRuntime"]["execution"]["evidence"], "unproven", e["id"])

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
