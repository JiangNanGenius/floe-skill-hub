"""Exercise large-source admission through the actual isolated signer.

Only the disposable tooling fixture's ephemeral key is used. The synthetic
script is never executed; these tests prove signing policy, not execution.
"""
import copy
import json
import pathlib
import sys
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_sign_publication import (BridgeFixture, TEST_SEED, KEY_ID, _env_value,
                                   _commit_all, review_record, hubcore)
import build_catalog
import runtime_dependency
import sign_publication


class LargeSourceSigningTests(BridgeFixture):
    def _candidate(self, name):
        registry, qualified = self._incremental_catalog_registry()
        entry = next(e for e in registry["skills"] if e["id"] == "algorithmic-art")
        entry["packageProfile"] = "large-source-v1"
        entry["minimumAppVersion"] = "1.9.0"
        entry["plannedRuntime"]["installPlatforms"] = ["ios"]
        entry["status"].update(licenseChecked=True, packaged=True, reviewed=True,
                               qualified=True, adaptation="frozen", executionVerified=True)
        qualified.add(entry["id"])
        data, _, staged = self._stage_catalog_data(
            name, registry, qualified, real_impeccable=False)
        pkg = staged[entry["id"]]
        for index in range(129):
            pkg["files"][f"assets/resource-{index:03d}.txt"] = b"fixture resource\n"
        hubcore.validate_package_files(pkg["files"], profile="large-source-v1")
        with self.assertRaises(hubcore.HubError):
            hubcore.validate_package_files(pkg["files"])
        pkg["data"] = hubcore.make_zip(pkg["files"])
        pkg["sha256"] = hubcore.sha256_hex(pkg["data"])
        pkg["contentDigest"] = hubcore.content_digest(pkg["files"])
        self._stage_packages(data, entry, pkg)
        self._stage_review(data, entry, review_record(entry, pkg, True), signed_with=self.key)
        commit = _commit_all(data, "fixture large-source package and bound review")
        return registry, entry, data, commit

    def _outputs(self, registry, data, commit):
        return build_catalog.build(registry, "release", commit, data, data,
                                   {KEY_ID: self.public_b64})

    def _gate(self, registry, data, outputs):
        return sign_publication.enforce_launch_gate(
            hubcore, runtime_dependency, SimpleNamespace(data=str(data)), registry, outputs)

    def test_real_catalog_signer_publishes_both_atomic_capability_pairs(self):
        registry, entry, data, commit = self._candidate("large-source-signing")
        out = self.root / "out-large-source-signing"
        proc = self._run_bridge("catalog", data, commit, out,
                                env_value=_env_value(TEST_SEED))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        trust = {KEY_ID: self.public_b64}
        receipt = self.verify_receipt(out, trust)
        for prefix in ("", "android/"):
            feed_path = prefix + "catalog-large-source-v1.json"
            raw = (out / feed_path).read_bytes()
            self.assertEqual(hubcore.verify_envelope(
                raw, (out / (prefix + "catalog-large-source-v1.sig")).read_bytes(), trust), KEY_ID)
            full = json.loads((out / (prefix + "catalog-full.json")).read_bytes())
            capability = json.loads(raw)
            hubcore.validate_capability_projection(capability, full)
            self.assertEqual(capability["sourceCommit"], commit)
            self.assertNotIn(entry["id"], {e["id"] for e in full["entries"]})
            if prefix:
                self.assertEqual(raw, (out / (prefix + "catalog-full.json")).read_bytes())
            else:
                offer = next(e for e in capability["entries"] if e["id"] == entry["id"])
                self.assertEqual(offer["package"]["profile"], "large-source-v1")
                archive = (out / offer["package"]["path"]).read_bytes()
                self.assertGreater(len(hubcore.check_archive_bytes(
                    archive, profile=offer["package"]["profile"])), 128)
        self.assertEqual(receipt["launchGate"]["iosQualified"], 31)
        self.assertEqual(receipt["launchGate"]["androidQualified"], 30)

    def test_real_reviews_signer_binds_large_archive_before_qualification(self):
        registry, entry, data, _ = self._candidate("large-source-review-signing")
        entry["status"]["qualified"] = False
        self._stage_registry(data, registry)
        rel = f"reviews/{entry['id']}/{entry['versionTarget']}.review.json"
        # Reviews mode deliberately accepts an unsigned data-only snapshot,
        # never a mixture of already-published signatures and new records.
        for path in (data / "reviews").rglob("*"):
            if path.is_file() and path != data / rel:
                path.unlink()
        for path in sorted((data / "reviews").rglob("*"), reverse=True):
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()
        commit = _commit_all(data, "fixture packaged and reviewed, not yet qualified")
        out = self.root / "out-large-source-review-signing"
        proc = self._run_bridge("reviews", data, commit, out,
                                env_value=_env_value(TEST_SEED))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        trust = {KEY_ID: self.public_b64}
        self.verify_receipt(out, trust)
        self.assertEqual((out / rel).read_bytes(), (data / rel).read_bytes())
        self.assertEqual(hubcore.verify_envelope(
            (out / rel).read_bytes(), (out / (rel + ".sig")).read_bytes(), trust), KEY_ID)

    def test_missing_or_partial_capability_pair_is_refused(self):
        registry, _, data, commit = self._candidate("large-source-missing")
        original = self._outputs(registry, data, commit)
        for paths in [("catalog-large-source-v1.json",),
                      ("android/catalog-large-source-v1.json",),
                      ("catalog-large-source-v1.json", "android/catalog-large-source-v1.json")]:
            with self.subTest(paths=paths):
                outputs = {p: b for p, b in original.items() if p not in paths}
                with self.assertRaisesRegex(sign_publication.SigningError, "capability feeds"):
                    self._gate(registry, data, outputs)

    def test_large_rows_keep_execution_and_mandatory_runtime_gates(self):
        registry, entry, data, commit = self._candidate("large-source-runtime")
        outputs = self._outputs(registry, data, commit)
        for field, value, error in [("executionVerified", False, "executionVerified"),
                                     ("adaptation", "in-progress", "frozen adaptation")]:
            with self.subTest(field=field):
                changed = copy.deepcopy(registry)
                next(e for e in changed["skills"] if e["id"] == entry["id"])["status"][field] = value
                with self.assertRaisesRegex(sign_publication.SigningError, error):
                    self._gate(changed, data, outputs)
        changed = copy.deepcopy(outputs)
        feed = json.loads(changed["catalog-large-source-v1.json"])
        next(e for e in feed["entries"] if e["id"] == entry["id"])["runtime"]["scriptRuntime"] = "none"
        changed["catalog-large-source-v1.json"] = hubcore.encoded(feed)
        with self.assertRaisesRegex(sign_publication.SigningError, "guide-only package"):
            self._gate(registry, data, changed)

    def test_capability_cannot_drop_standard_rows_or_invent_channels(self):
        registry, entry, data, commit = self._candidate("large-source-projection")
        original = self._outputs(registry, data, commit)
        for path, mutate in [
            ("catalog-large-source-v1.json", lambda rows: rows.pop(0)),
            ("android/catalog-large-source-v1.json", lambda rows: rows.append(
                next(e for e in json.loads(original["catalog-large-source-v1.json"])["entries"]
                     if e["id"] == entry["id"]))),
        ]:
            with self.subTest(path=path):
                outputs = dict(original)
                feed = json.loads(outputs[path])
                mutate(feed["entries"])
                outputs[path] = hubcore.encoded(feed)
                with self.assertRaisesRegex(sign_publication.SigningError, "exactly the qualified"):
                    self._gate(registry, data, outputs)

    def test_standard_projection_cannot_hide_or_absorb_large_rows(self):
        registry, entry, data, commit = self._candidate("large-source-standard")
        original = self._outputs(registry, data, commit)
        for addition in (False, True):
            outputs = dict(original)
            feed = json.loads(outputs["catalog-full.json"])
            if addition:
                feed["entries"].append(next(
                    e for e in json.loads(outputs["catalog-large-source-v1.json"])["entries"]
                    if e["id"] == entry["id"]))
            else:
                feed["entries"].pop()
            outputs["catalog-full.json"] = hubcore.encoded(feed)
            with self.assertRaisesRegex(sign_publication.SigningError, "standard-profile rows"):
                self._gate(registry, data, outputs)
