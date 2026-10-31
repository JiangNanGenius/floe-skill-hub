"""A complete catalog cannot leak row 44 into an older client's view."""
import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import build_catalog
import hubcore


class CatalogExpansionProjectionTests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads((ROOT / "catalog/skills.json").read_bytes())
        self.registry["skills"] = [row for row in self.registry["skills"]
                                   if row["planNumber"] <= 43]

    def outputs(self, mode="preview"):
        hubcore.validate_registry(self.registry)
        return build_catalog.build(self.registry, mode, "a" * 40,
                                   ROOT, ROOT, build_catalog.load_trust(ROOT))

    def add_unqualified_guide(self):
        row = copy.deepcopy(next(row for row in self.registry["skills"]
                                 if row["id"] == "meetings"))
        row.update(id="new-business-guide", planNumber=44, versionTarget="1.0.0")
        row["status"].update(reviewed=False, qualified=False, packaged=False,
                             published=False, adaptation="planned")
        self.registry["skills"].append(row)

    def test_original_cohort_views_are_exactly_equal(self):
        out = self.outputs("release")
        for prefix in ("", "android/"):
            self.assertEqual(out[prefix + "catalog.json"],
                             out[prefix + "catalog-full.json"])

    def test_append_is_only_visible_in_full_view_and_is_not_an_offer(self):
        self.add_unqualified_guide()
        out = self.outputs()
        for prefix in ("", "android/"):
            full = json.loads(out[prefix + "catalog-full.json"])
            legacy = json.loads(out[prefix + "catalog.json"])
            self.assertNotIn("new-business-guide", {e["id"] for e in legacy["entries"]})
            added = next(e for e in full["entries"] if e["id"] == "new-business-guide")
            self.assertEqual(added["planNumber"], 44)
            self.assertEqual(added["installOffer"], "none")
            self.assertEqual(full["counts"]["total"], legacy["counts"]["total"] + 1)
            self.assertTrue(all(1 <= e["planNumber"] <= 43 for e in legacy["entries"]))
            self.assertEqual(full["sourceCommit"], legacy["sourceCommit"])
            self.assertEqual(full["schemaVersion"], 3)

    def test_retained_rows_and_bindings_do_not_change(self):
        before = self.outputs()
        self.add_unqualified_guide()
        after = self.outputs()
        for prefix in ("", "android/"):
            self.assertEqual(before[prefix + "catalog.json"], after[prefix + "catalog.json"])
            full = json.loads(after[prefix + "catalog-full.json"])
            retained = [e for e in full["entries"] if e["planNumber"] <= 43]
            self.assertEqual(retained, json.loads(before[prefix + "catalog.json"])["entries"])

    def test_qualified_row_without_real_package_cannot_enter_either_view(self):
        self.add_unqualified_guide()
        self.registry["skills"][-1]["status"].update(
            reviewed=True, qualified=True, packaged=True, adaptation="frozen")
        with self.assertRaises(hubcore.HubError):
            self.outputs("release")


if __name__ == "__main__":
    unittest.main()
