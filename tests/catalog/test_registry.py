#!/usr/bin/env python3
"""Registry contract tests: 43 rows, pins, statuses, names and blockers."""
import hashlib
import json
import pathlib
import re
import shutil
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "scripts"))
sys.path.insert(0, str(HERE.parents[1]))
import build_catalog
import hubcore
import admission_baseline as BASE

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
# 2026-10-28 reviewed baseline (see admission_baseline.py): the two original
# guest receipts plus the nine mandatory deep IDs, each admitted after a real
# riscv64 guest run, are the ONLY rows that may carry executionVerified.
EXPECTED_GUEST_EXEC_VERIFIED = set(BASE.EXECUTION_VERIFIED_IDS)
# Every scripted (non-guide) row now holds its own real guest receipt; the
# exact nine deep IDs are the last admitted set (2026-10-27).  Historical
# policy negatives are constructed explicitly in the tests below, never by
# assuming the live registry still sits in the old held-back epoch.
EXPECTED_SCRIPT_ROWS = EXPECTED_DEEP | {"citation-management", "sympy"}
PLAN_ZH = {5: "文档协作", 7: "技术写作检查", 15: "文献综述", 22: "格式转 Markdown",
           24: "Impeccable", 30: "React 最佳实践", 41: "会议纪要"}

# ---------------------------------------------------------------------------
# Owned-guide provenance binding (regression repair after the reviewed
# Linux-compatibility publication).
#
# PROVENANCE.md inside each owned source tree was written AT admission and is
# part of the admitted immutable record, so its hashes are HISTORICAL
# evidence and must never be rewritten to chase new bytes. A legitimate
# manifest-only release may therefore not be judged against the working tree
# alone. Both faces are enforced together, fail-closed:
#   * historical — every recorded hash (floe.json included; skipping the
#     manifest is refused) matches the ORIGINAL admitted, officially signed
#     and reviewed archive retained on disk, so the frozen hash proof of the
#     old package survives unchanged; and
#   * current — the working-tree manifest is byte-identical to the officially
#     signed archive of the registry's own versionTarget, the tree's copy of
#     PROVENANCE.md still equals the archived copy (history cannot be
#     rewritten), and a manifest-only migration may change ONLY the version
#     (strictly forward) and platforms (append-only) fields while every other
#     archived byte and every other manifest field stays preserved.
# ---------------------------------------------------------------------------
MIGRATION_MANIFEST_FIELDS = frozenset({"version", "platforms"})


def _version_tuple(version):
    return tuple(int(part) for part in version.split("."))


def _reviewed_archive(root, sid, version, trust):
    """One officially signed, reviewed archive, verified against its own
    digests and the manifest inside it. Any missing, unsigned, tampered or
    digest-drifting surface raises; nothing is skipped."""
    archive_path = root / hubcore.package_path_for(sid, version, "ios")
    review_path = root / "reviews" / sid / f"{version}.review.json"
    signature_path = review_path.parent / (review_path.name + ".sig")
    for path, what in ((archive_path, "reviewed archive"),
                       (review_path, "review record"),
                       (signature_path, "review signature")):
        if not path.is_file():
            raise hubcore.HubError(
                f"{sid} {version}: no signed {what} exists; an unsigned "
                "snapshot can never satisfy provenance")
    archive_bytes = archive_path.read_bytes()
    files = hubcore.check_archive_bytes(archive_bytes)
    manifest = hubcore.parse_manifest(files["floe.json"])
    record_bytes = review_path.read_bytes()
    hubcore.verify_envelope(record_bytes, signature_path.read_bytes(), trust)
    record = json.loads(record_bytes)
    hubcore.validate_review(record)
    binding = {"sha256": hubcore.sha256_hex(archive_bytes),
               "contentDigest": hubcore.content_digest(files)}
    hubcore.join_review(record, manifest, binding, f"{sid} {version}")
    return {"version": version, "manifest": manifest, "files": files,
            "record": record,
            "manifest_sha": hubcore.sha256_hex(files["floe.json"])}


def verify_admitted_source_provenance(root, sid, entry):
    """Bind one owned guide's provenance inventory to the admitted archive
    AND the current signed snapshot. Returns (historical, current) versions.
    Fail-closed: every refusal is a raised HubError, never a silent skip."""
    root = pathlib.Path(root)
    trust = build_catalog.load_trust(root)
    if not trust:
        raise hubcore.HubError(
            f"{sid}: no official signing trust is configured; provenance "
            "cannot be trusted, only refused")
    source = root / "sources" / sid
    provenance_path = source / "references/PROVENANCE.md"
    if not provenance_path.is_file():
        raise hubcore.HubError(f"{sid}: PROVENANCE.md is missing")
    provenance_bytes = provenance_path.read_bytes()
    inventory = re.findall(r"`([^`]+)` sha256 `([0-9a-f]{64})`",
                           provenance_bytes.decode())
    if not inventory:
        raise hubcore.HubError(f"{sid}: no per-file hash inventory")
    recorded = {}
    for rel, sha in inventory:
        if rel in recorded:
            raise hubcore.HubError(f"{sid}: duplicate inventory path {rel}")
        recorded[rel] = sha
    if "floe.json" not in recorded:
        raise hubcore.HubError(
            f"{sid}: the provenance inventory must cover floe.json; "
            "skipping the manifest to dodge a drift is refused")
    packages_dir = root / "packages" / sid
    versions = sorted(p.name for p in packages_dir.iterdir()
                      if p.is_dir() and hubcore.VERSION_PATTERN.fullmatch(p.name)) \
        if packages_dir.is_dir() else []
    if not versions:
        raise hubcore.HubError(
            f"{sid}: no reviewed archive version is retained on disk")
    archives = {v: _reviewed_archive(root, sid, v, trust) for v in versions}
    historical_versions = [v for v, a in archives.items()
                           if a["manifest_sha"] == recorded["floe.json"]]
    if not historical_versions:
        raise hubcore.HubError(
            f"{sid}: the manifest hash recorded by PROVENANCE.md matches no "
            "officially signed reviewed archive (forged historical record)")
    if len(historical_versions) > 1:
        raise hubcore.HubError(
            f"{sid}: the recorded manifest hash matches more than one "
            "retained archive (ambiguous history)")
    historical = archives[historical_versions[0]]
    current_version = entry["versionTarget"]
    if current_version not in archives:
        raise hubcore.HubError(
            f"{sid}: registry versionTarget {current_version} has no "
            "officially signed reviewed archive")
    current = archives[current_version]
    if current["record"]["id"] != sid or current["record"]["version"] != current_version:
        raise hubcore.HubError(
            f"{sid}: the signed review identity drifts from the registry row")
    archived_provenance = current["files"].get("references/PROVENANCE.md")
    if archived_provenance is None:
        raise hubcore.HubError(
            f"{sid}: the signed archive does not carry the provenance record")
    if hashlib.sha256(provenance_bytes).hexdigest() != hubcore.sha256_hex(archived_provenance):
        raise hubcore.HubError(
            f"{sid}: the working PROVENANCE.md no longer matches the signed "
            "archive copy; rewritten history is refused")
    tree_manifest_bytes = (source / "floe.json").read_bytes()
    hubcore.parse_manifest(tree_manifest_bytes)  # exact-key manifest contract on the tree
    if hubcore.sha256_hex(tree_manifest_bytes) != current["manifest_sha"]:
        raise hubcore.HubError(
            f"{sid}: the working floe.json is not the officially signed "
            f"{current_version} snapshot bytes (current drift is refused)")
    for rel, sha in recorded.items():
        if rel == "floe.json":
            continue
        path = source / rel
        if not path.is_file():
            raise hubcore.HubError(f"{sid}: inventory lists missing {rel}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise hubcore.HubError(f"{sid}: committed bytes drifted for {rel}")
    for rel, sha in recorded.items():
        if rel not in historical["files"]:
            raise hubcore.HubError(
                f"{sid}: inventory lists {rel}, which the admitted "
                f"{historical['version']} archive does not carry")
        if hubcore.sha256_hex(historical["files"][rel]) != sha:
            raise hubcore.HubError(
                f"{sid}: PROVENANCE.md no longer describes the admitted "
                f"{historical['version']} archive bytes for {rel}")
    names = set(historical["files"])
    if names != set(current["files"]):
        raise hubcore.HubError(
            f"{sid}: file membership drifted between the signed "
            f"{historical['version']} and {current_version} archives")
    for name in names:
        if name != "floe.json" and historical["files"][name] != current["files"][name]:
            raise hubcore.HubError(
                f"{sid}: {name} changed between signed archives; only the "
                "manifest may migrate")
    old, new = historical["manifest"], current["manifest"]
    if old != new:
        if _version_tuple(current_version) <= _version_tuple(historical["version"]):
            raise hubcore.HubError(
                f"{sid}: the current snapshot must be strictly newer than "
                "the admitted one it migrates from")
        for field in old:
            if field in MIGRATION_MANIFEST_FIELDS:
                continue
            if old[field] != new.get(field):
                raise hubcore.HubError(
                    f"{sid}: manifest field {field!r} drifted across the "
                    "migration; only version and platforms may change")
        if new["platforms"][:len(old["platforms"])] != old["platforms"]:
            raise hubcore.HubError(
                f"{sid}: the migration may only append platforms, never "
                "drop or reorder the admitted ones")
    return historical["version"], current_version


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
        # Positive truth of the reviewed 2026-10-28 admission baseline (see
        # admission_baseline.py): every row is packaged+reviewed+licenseChecked
        # (all 43 records carry verified signatures), the FULL selection is
        # qualified — the 32 guides + 2 guest scripts + the nine mandatory
        # deep IDs admitted after real guest receipts — exactly the 11 script
        # rows carry executionVerified, and the candidate registry itself
        # never claims published=true (publication is the separate signed
        # feed act). The expectation is the explicit reviewed ID literal, not
        # a recomputation of the file under test.
        admitted = EXPECTED_GUIDE_QUALIFIED | EXPECTED_GUEST_EXEC_VERIFIED
        self.assertEqual(len(admitted), BASE.QUALIFIED_SELECTION)
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
        # the scripted population of the registry is exactly the eleven rows
        # that hold guest receipts; nothing else may hide behind a script plan
        self.assertEqual({e["id"] for e in REGISTRY["skills"]
                          if e["plannedRuntime"]["scriptRuntime"] != "none"},
                         EXPECTED_SCRIPT_ROWS)
        # The nine mandatory deep IDs are the final admitted script set: each
        # ships as a remote-script package with its own real guest receipt,
        # and a guide row can never appear in that verified set.
        for e in REGISTRY["skills"]:
            if e["id"] in EXPECTED_DEEP:
                self.assertEqual(e["plannedRuntime"]["scriptRuntime"], "remote", e["id"])
                self.assertTrue(e["status"]["qualified"], e["id"])
                self.assertTrue(e["status"]["executionVerified"], e["id"])
            if e["plannedRuntime"]["scriptRuntime"] == "none":
                self.assertNotIn(e["id"], EXPECTED_GUEST_EXEC_VERIFIED, e["id"])
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
        # Every real script row now carries its own verified receipt, so the
        # unverified-script fixture is STAGED explicitly inside the copy:
        # first a coherent held-back script baseline (executionVerified false
        # with unproven evidence, which must validate), then the single
        # targeted invariant violation — a borrowed guest-verified claim.
        script = json.loads(json.dumps(REGISTRY))
        row = next(e for e in script["skills"]
                   if e["id"] == "literature-review")
        row["status"]["executionVerified"] = False
        row["plannedRuntime"]["execution"]["evidence"] = "unproven"
        hubcore.validate_registry(script)  # staged baseline is coherent
        row["plannedRuntime"]["execution"]["evidence"] = "guest-verified"
        with self.assertRaisesRegex(hubcore.HubError, "executionVerified"):
            hubcore.validate_registry(script)

    def test_pins_equal_review_baseline_document(self):
        # Per-entry pin contract (Root lane job-a000dc2309224d6b, 2026-10-28):
        # docs/UPSTREAM-PINS.json may gain "skillOverrides":
        # { entryId: { repository: owner/repo, commit: 40-hex } } — an
        # explicitly reviewed override IS that entry's effective pin, and an
        # accepted guide may advance while a held peer keeps its old pin. No
        # override may loosen the rule: each entry must still equal its
        # EFFECTIVE pin exactly (override first, else the repository default),
        # and every override must be well-shaped for a real upstream row. The
        # current reviewed baseline carries no overrides, so today this
        # resolves to the original default-only equality, unchanged.
        doc = json.loads((REPO / "docs" / "UPSTREAM-PINS.json").read_bytes())
        pins = doc["repositories"]
        overrides = doc.get("skillOverrides", {})
        self.assertIsInstance(overrides, dict)
        by_id = {e["id"]: e for e in REGISTRY["skills"]}
        for sid, ov in overrides.items():
            row = by_id.get(sid)
            self.assertTrue(row is not None and row["upstream"] is not None,
                            f"override {sid}: no upstream row to bind")
            self.assertEqual(set(ov), {"repository", "commit"}, sid)
            self.assertTrue(re.fullmatch(r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+",
                                         ov["repository"]), sid)
            self.assertTrue(hubcore.COMMIT_PATTERN.fullmatch(ov["commit"]), sid)
        for e in REGISTRY["skills"]:
            if e["upstream"]:
                repo = e["upstream"]["repository"].removeprefix("https://github.com/")
                ov = overrides.get(e["id"])
                if ov is not None:
                    self.assertEqual(repo, ov["repository"], e["id"])
                    self.assertEqual(e["upstream"]["commit"], ov["commit"], e["id"])
                else:
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
        freeze (2026-10-26): their own content is pinned by the actual Hub
        source commit, not by fabricated upstream/firstParty pin blocks.
        # These replace the obsolete planning-state assertions that required
        # sourcePinned=False (and awaiting-implementation) forever. After the
        # signed-review admission these eight owned guides are packaged,
        # reviewed and qualified; publication stays closed. The provenance
        # inventory is verified BOTH ways: the recorded hashes must match the
        # retained admitted immutable archive (historical hash proof), while
        # the working tree must match the CURRENT officially signed snapshot,
        # with a manifest-only migration preserving every other byte and
        # every other manifest field (see verify_admitted_source_provenance)."""
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
        # Re-provenance, historical AND current: every hash recorded in
        # PROVENANCE.md still matches the original admitted signed archive it
        # was written against (and the unchanged working-tree bytes), while
        # the working manifest itself is the current officially signed
        # snapshot bound to its review digests and the registry row. A silent
        # source drift, a rewritten history or an unsigned replacement breaks
        # this regression; nothing is skipped and no mismatch is tolerated.
        verify_admitted_source_provenance(REPO, sid, e)

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

    def test_owned_guides_bind_historical_archive_and_current_snapshot(self):
        # Both provenance faces hold simultaneously for all eight owned
        # guides: the recorded manifest hash resolves to exactly one retained
        # officially signed historical archive, and the current snapshot the
        # registry points at is itself officially signed, review-bound and
        # byte-identical to the working tree. Upstream/firstParty stay null
        # (no fabricated pins) across every row.
        for sid in EXPECTED_FIRST_PARTY_PENDING | EXPECTED_ORIGINAL_REPLACEMENTS:
            with self.subTest(sid=sid):
                entry = self.entries[sid]
                self.assertIsNone(entry["upstream"], sid)
                self.assertIsNone(entry["firstParty"], sid)
                historical, current = verify_admitted_source_provenance(
                    REPO, sid, entry)
                self.assertEqual(current, entry["versionTarget"], sid)
                self.assertLessEqual(_version_tuple(historical),
                                     _version_tuple(current), sid)

    def _isolated_provenance_root(self, sid):
        """Ephemeral copy of ONE owned guide's real artifacts (source tree,
        retained signed archives, signed reviews, public trust) so a negative
        can forge exactly one surface without touching any repository byte."""
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="floe-provenance-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        for rel in (f"sources/{sid}", f"packages/{sid}", f"reviews/{sid}"):
            shutil.copytree(REPO / rel, tmp / rel)
        shutil.copy2(REPO / "public-key.json", tmp / "public-key.json")
        return tmp

    def test_provenance_refuses_forged_historical_manifest_or_hash(self):
        sid = "floe-email-drafting"
        entry = self.entries[sid]
        root = self._isolated_provenance_root(sid)
        historical, current = verify_admitted_source_provenance(root, sid, entry)
        self.assertNotEqual(historical, current)  # this row really migrated
        prov_path = root / f"sources/{sid}/references/PROVENANCE.md"
        original = prov_path.read_text()
        recorded = re.search(r"`floe\.json` sha256 `([0-9a-f]{64})`",
                             original).group(1)
        current_sha = hashlib.sha256(
            (root / f"sources/{sid}/floe.json").read_bytes()).hexdigest()
        cases = {
            # Rewriting the record to today's bytes "proves" the manifest was
            # always current: the archived copy of PROVENANCE.md refutes it.
            "rewritten-to-current": (recorded, current_sha),
            # An invented hash matches no retained signed archive.
            "invented": (recorded, "0" * 64),
            # Silently dropping the manifest line to dodge a drift is refused.
            "manifest-skipped": (f"- `floe.json` sha256 `{recorded}`\n", ""),
        }
        for label, (find, replace) in cases.items():
            with self.subTest(case=label):
                prov_path.write_text(original.replace(find, replace, 1))
                with self.assertRaises(hubcore.HubError):
                    verify_admitted_source_provenance(root, sid, entry)
                prov_path.write_text(original)
        # Forging the ORIGINAL archive content itself (the admitted 1.0.0
        # bytes, tampered after the fact) breaks the signed review's digest
        # proof for that archive and is refused even though the tampered
        # manifest still parses as a valid manifest.
        zip_path = root / hubcore.package_path_for(sid, historical, "ios")
        files = hubcore.check_archive_bytes(zip_path.read_bytes())
        forged = hubcore.parse_manifest(files["floe.json"])
        forged["tools"] = ["exec.shell"]
        files["floe.json"] = hubcore.encoded(forged) + b"\n"
        zip_path.write_bytes(hubcore.make_zip(files))
        with self.assertRaisesRegex(hubcore.HubError, "does not match"):
            verify_admitted_source_provenance(root, sid, entry)

    def test_provenance_refuses_current_manifest_grant_or_dependency_drift(self):
        sid = "composition-patterns"
        entry = self.entries[sid]
        root = self._isolated_provenance_root(sid)
        verify_admitted_source_provenance(root, sid, entry)  # baseline coherent
        manifest_path = root / f"sources/{sid}/floe.json"
        original = manifest_path.read_bytes()
        baseline = hubcore.parse_manifest(original)
        # A grant the signed snapshot never reviewed: extra tool + capability
        # in the working manifest must never pass as "current".
        granted = dict(baseline)
        granted["tools"] = ["exec.shell"]
        granted["capabilities"] = ["execution.remote"]
        manifest_path.write_bytes(hubcore.encoded(granted) + b"\n")
        with self.assertRaisesRegex(hubcore.HubError,
                                    "not the officially signed"):
            verify_admitted_source_provenance(root, sid, entry)
        # A dependency smuggled into a guide manifest is rejected by the
        # manifest contract itself before any hash is trusted.
        packaged = dict(baseline)
        packaged["pythonPackages"] = [{"spec": "numpy==1.26.4",
                                       "purpose": "ungranted dependency",
                                       "capabilities": ["data.numeric"]}]
        manifest_path.write_bytes(hubcore.encoded(packaged) + b"\n")
        with self.assertRaisesRegex(hubcore.HubError, "pythonPackages"):
            verify_admitted_source_provenance(root, sid, entry)

    def test_provenance_refuses_unsigned_or_tampered_snapshot(self):
        sid = "floe-email-drafting"
        entry = self.entries[sid]
        root = self._isolated_provenance_root(sid)
        _, current = verify_admitted_source_provenance(root, sid, entry)
        review_dir = root / "reviews" / sid
        sig_path = review_dir / f"{current}.review.json.sig"
        original_sig = sig_path.read_bytes()
        # An unsigned current snapshot is refused, never treated as absent history.
        sig_path.unlink()
        with self.assertRaisesRegex(hubcore.HubError,
                                    "no signed review signature"):
            verify_admitted_source_provenance(root, sid, entry)
        # A snapshot claiming a key outside the configured trust is refused.
        sig_path.write_bytes(hubcore.encoded(
            {"keyID": "rogue-key",
             "signature": "A" * 43 + "="}))
        with self.assertRaisesRegex(hubcore.HubError, "unknown signing keyID"):
            verify_admitted_source_provenance(root, sid, entry)
        # A signed review record edited after signing no longer verifies.
        sig_path.write_bytes(original_sig)
        review_path = review_dir / f"{current}.review.json"
        tampered = json.loads(review_path.read_bytes())
        tampered["packageSha256"] = "1" * 64
        review_path.write_bytes(hubcore.encoded(tampered))
        with self.assertRaisesRegex(hubcore.HubError,
                                    "signature verification failed"):
            verify_admitted_source_provenance(root, sid, entry)

    def test_synthetic_qualification_without_prerequisites_is_rejected(self):
        # Negatives stay real even after admission: a row may not claim a
        # stage above the one it actually holds, and a script that does not
        # actually hold a verified receipt (staged explicitly inside the
        # fixture, because every live script row is verified today) cannot
        # borrow the guest-verified evidence of the real receipts.
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
        target = next(e for e in broken["skills"] if e["id"] == "markitdown")
        self.assertTrue(target["status"]["executionVerified"])
        # stage the held-back baseline first (verified False + unproven stays
        # coherent), then inject only the borrowed claim under test.
        target["status"]["executionVerified"] = False
        target["plannedRuntime"]["execution"]["evidence"] = "unproven"
        hubcore.validate_registry(broken)  # staged baseline is coherent
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
        # 32 of 43 rows must keep unproven evidence; only the eleven script
        # rows with genuine guest receipts (the 2 early guests + the nine
        # mandatory deep IDs) may claim guest-verified, and only with
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
