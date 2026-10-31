"""Append new candidates without repurposing an installed legacy identity."""
import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hubcore


class RegistryExpansionTests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads((ROOT / "catalog/skills.json").read_bytes())
        self.registry["skills"] = [row for row in self.registry["skills"]
                                   if row["planNumber"] <= 43]

    def append_guide(self, number=44):
        row = copy.deepcopy(next(row for row in self.registry["skills"]
                                 if row["id"] == "meetings"))
        row.update(id=f"candidate-{number}", planNumber=number,
                   versionTarget="1.0.0")
        row["status"].update(reviewed=False, qualified=False, packaged=False,
                             published=False, adaptation="planned")
        self.registry["skills"].append(row)
        return row

    def test_legacy_identity_constants_match_original_frozen_fixture(self):
        frozen = json.loads((ROOT / "tests/catalog/fixtures/initial-release-registry-2026-10.json").read_bytes())
        expected = tuple(row["id"] for row in sorted(frozen["skills"],
                                                    key=lambda row: row["planNumber"]))
        self.assertEqual(hubcore.LEGACY_PLAN_IDS, expected)

    def test_new_optional_guide_is_not_implicitly_qualified(self):
        row = self.append_guide()
        hubcore.validate_registry(self.registry)
        self.assertFalse(row["status"]["qualified"])
        self.assertFalse(row["status"]["published"])

    def test_replacing_original_identity_is_rejected_even_at_original_count(self):
        row = next(row for row in self.registry["skills"] if row["id"] == "meetings")
        row["id"] = "replacement-meeting"
        with self.assertRaisesRegex(hubcore.HubError, "legacy planNumber"):
            hubcore.validate_registry(self.registry)

    def test_swapping_original_plan_numbers_is_rejected(self):
        rows = [row for row in self.registry["skills"] if row["planNumber"] in (5, 6)]
        rows[0]["planNumber"], rows[1]["planNumber"] = rows[1]["planNumber"], rows[0]["planNumber"]
        with self.assertRaisesRegex(hubcore.HubError, "legacy planNumber"):
            hubcore.validate_registry(self.registry)

    def test_moving_mandatory_deep_flag_to_an_added_id_is_rejected(self):
        added = self.append_guide()
        original = next(row for row in self.registry["skills"] if row["id"] == "impeccable")
        original["deepAdaptation"] = False
        added["deepAdaptation"] = True
        with self.assertRaisesRegex(hubcore.HubError, "legacy deep-adaptation identity"):
            hubcore.validate_registry(self.registry)

    def test_extra_builtin_cannot_be_smuggled_as_new_optional_identity(self):
        self.append_guide()["kind"] = "builtin"
        with self.assertRaisesRegex(hubcore.HubError, "builtin kind must agree"):
            hubcore.validate_registry(self.registry)

    def test_boolean_is_not_a_plan_number(self):
        self.registry["skills"][0]["planNumber"] = True
        with self.assertRaisesRegex(hubcore.HubError, "planNumber"):
            hubcore.validate_registry(self.registry)

    def test_existing_client_entry_bound_is_preserved(self):
        for number in range(44, hubcore.MAX_REGISTRY_ENTRIES + 2):
            self.append_guide(number)
        with self.assertRaisesRegex(hubcore.HubError, "at most 256"):
            hubcore.validate_registry(self.registry)

    def test_explicit_fixture_counts_remain_exact(self):
        guides = [row for row in self.registry["skills"]
                  if row["kind"] == "optional" and not row["deepAdaptation"]][:2]
        for number, row in enumerate(guides, 1):
            row["planNumber"] = number
        self.registry["skills"] = guides
        hubcore.validate_registry(self.registry, expect_counts=(2, 0, 2, 0))
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_registry(self.registry)
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_registry(self.registry, expect_counts=(3, 0, 3, 0))


if __name__ == "__main__":
    unittest.main()
