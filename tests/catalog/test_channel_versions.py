"""Reviewed per-channel client floors; no production signing or App claim."""
import copy
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import build_catalog
import hubcore
from tests.catalog.test_package_profiles import registry_entry, registry_with


class TestChannelVersions(unittest.TestCase):
    def entry(self):
        entry = registry_entry("channel-floor-fixture", 1, minimumAppVersion="1.9.0")
        entry["plannedRuntime"]["installPlatforms"] = ["ios", "android"]
        entry["status"]["packaged"] = False
        return entry

    def validate(self, entry):
        hubcore.validate_registry(registry_with([entry]), expect_counts=(1, 0, 1, 0))

    def render(self, entry):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            return build_catalog.build(registry_with([entry]), "preview", "a" * 40,
                                       root, root, {})

    def test_absent_field_preserves_both_historical_floors(self):
        entry = self.entry()
        self.validate(entry)
        self.assertEqual(hubcore.minimum_app_version_for_channel(entry, "ios"), "1.9.0")
        self.assertEqual(hubcore.minimum_app_version_for_channel(entry, "android"), "1.9.0")

    def test_distinct_client_domains_project_into_existing_wire_field(self):
        entry = self.entry()
        entry["minimumAppVersions"] = {"android": "0.1.1"}
        self.validate(entry)
        before = copy.deepcopy(entry)
        output = self.render(entry)
        for path, expected in [("catalog-full.json", "1.9.0"),
                               ("android/catalog-full.json", "0.1.1")]:
            row = json.loads(output[path])["entries"][0]
            self.assertEqual(row["minimumAppVersion"], expected)
            self.assertNotIn("minimumAppVersions", row)
        self.assertEqual(entry, before)

    def test_same_explicit_versions_rebuild_identical_bytes(self):
        entry = self.entry()
        explicit = copy.deepcopy(entry)
        explicit["minimumAppVersions"] = {"ios": "1.9.0", "android": "1.9.0"}
        self.assertEqual(self.render(entry), self.render(explicit))

    def test_large_capability_uses_each_channel_floor(self):
        entry = self.entry()
        entry["packageProfile"] = "large-source-v1"
        entry["minimumAppVersions"] = {"android": "0.1.1"}
        output = self.render(entry)
        for path, expected in [("catalog-large-source-v1.json", "1.9.0"),
                               ("android/catalog-large-source-v1.json", "0.1.1")]:
            self.assertEqual(json.loads(output[path])["entries"][0]["minimumAppVersion"], expected)
        self.assertEqual(json.loads(output["catalog-full.json"])["entries"], [])

    def test_invalid_override_shapes_and_marketing_versions_refused(self):
        for invalid in [None, {}, [], "0.1.1", {"macos": "1.0.0"},
                        {"android": None}, {"android": True}, {"android": 1},
                        {"android": "0.1.0-alpha.78"}, {"android": "latest"}]:
            with self.subTest(invalid=invalid):
                entry = self.entry()
                entry["minimumAppVersions"] = invalid
                with self.assertRaises(hubcore.HubError):
                    self.validate(entry)

    def test_one_channel_offer_still_emits_both_atomic_capability_views(self):
        entry = self.entry()
        entry["packageProfile"] = "large-source-v1"
        entry["plannedRuntime"]["installPlatforms"] = ["ios"]
        output = self.render(entry)
        self.assertEqual(len(json.loads(output["catalog-large-source-v1.json"])["entries"]), 1)
        self.assertEqual(output["android/catalog-large-source-v1.json"],
                         output["android/catalog-full.json"])

    def test_override_cannot_name_an_unoffered_channel(self):
        entry = self.entry()
        entry["plannedRuntime"]["installPlatforms"] = ["ios"]
        entry["minimumAppVersions"] = {"android": "0.1.1"}
        with self.assertRaises(hubcore.HubError):
            self.validate(entry)

    def test_explicit_floor_is_not_replaced_by_portable_guide_sentinel(self):
        identifier = next(iter(build_catalog.ANDROID_PORTABLE_GUIDE_IDS))
        entry = {"id": identifier, "package": {"bound": "fixture"},
                 "review": {"bound": "fixture"}, "minimumAppVersion": "0.1.1"}
        feed = {"entries": [entry]}
        with mock.patch.object(build_catalog, "_rebound_portable_guide_facts",
                               side_effect=AssertionError("explicit reviewed floor must be retained")):
            self.assertIsNone(build_catalog.project_android_portable_guide_feed(
                feed, pathlib.Path("."), pathlib.Path("."), explicit_minimum_ids={identifier}))
        self.assertEqual(entry["minimumAppVersion"], "0.1.1")


if __name__ == "__main__":
    unittest.main()
