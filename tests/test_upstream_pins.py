#!/usr/bin/env python3
"""Focused contract tests for scripts/upstream_pins.py (per-skill pin advance).

These tests pin the CONTRACT, not incidental implementation:
  * legacy documents (repository defaults only) validate exactly as before,
    with the ORIGINAL check_catalog failure strings kept byte-for-byte;
  * an optional reviewed skillOverrides entry IS that row's effective pin —
    an accepted guide advances via its override while a held script in the
    same repository keeps the old default, and every comparison stays EXACT
    (a well-formed commit alone never passes);
  * overrides cannot target unknown/local/builtin ids, change repository
    identity, use an unlisted repository, or carry duplicate keys, oversized
    or bad-UTF-8 bytes, malformed SHAs/dates or unknown fields;
  * advance_pin_document refuses id-set/identity changes, unaccepted pin
    changes and mis-set accepted ids, compacts a fully-advanced repository,
    preserves watch-only baselines, recomputes overrides honestly, never
    mutates its inputs, and is deterministic;
  * the live docs/UPSTREAM-PINS.json + catalog/skills.json still pass the
    integrated read-only check with their bytes untouched.

Fixtures are minimal (id + upstream block); the full 43-row candidate shape
is hubcore.validate_registry's gate, exercised via the real check_catalog
integration, not re-implemented here. Stdlib only.

Run (PYTHONDONTWRITEBYTECODE / sys.dont_write_bytecode keeps the tree clean):
    python3 tests/test_upstream_pins.py
"""
import copy
import hashlib
import json
import pathlib
import sys
import unittest

sys.dont_write_bytecode = True

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "scripts"))

import upstream_pins as up  # noqa: E402

A = "a" * 40
B = "b" * 40
C = "c" * 40
D = "d" * 40

# Original check_catalog.check_pins failure strings (kept verbatim by the
# contract for the no-override path; expectations fixed from the legacy
# implementation BEFORE the helper existed, never rewritten from it).
LEGACY_UNLISTED = "{eid}: repository {repo} is not in docs/UPSTREAM-PINS.json"
LEGACY_DIVERGES = ("{eid}: commit {got} diverges from the review baseline {want}")


def registry_rows(*rows):
    """rows: (id, repo_short|None, commit|None) -> minimal candidate snapshot."""
    skills = []
    for eid, repo_short, commit in rows:
        upstream = None
        if repo_short is not None:
            upstream = {"repository": up.GITHUB_URL_PREFIX + repo_short,
                        "commit": commit}
        skills.append({"id": eid, "upstream": upstream})
    return {"skills": skills}


def pins_doc(repos=None, overrides=None, date="2026-10-26"):
    doc = {"reviewBaselineDate": date,
           "repositories": dict(repos if repos is not None else {"corpus/repo": A})}
    if overrides is not None:
        doc["skillOverrides"] = copy.deepcopy(overrides)
    return doc


def doc_bytes(doc):
    return json.dumps(doc, ensure_ascii=False).encode("utf-8")


class LegacyGlobalPinTests(unittest.TestCase):
    def test_exact_match_passes_and_ignores_local_rows(self):
        doc = pins_doc({"corpus/repo": A})
        reg = registry_rows(("guide-a", "corpus/repo", A), ("script-b", "corpus/repo", A),
                            ("floe-builtin", None, None))
        self.assertEqual(up.check_registry_pins(doc, reg), [])

    def test_default_divergence_keeps_legacy_message(self):
        doc = pins_doc({"corpus/repo": A})
        reg = registry_rows(("guide-a", "corpus/repo", B))
        reasons = up.check_registry_pins(doc, reg)
        self.assertEqual(reasons, [LEGACY_DIVERGES.format(eid="guide-a",
                                                           got=B[:10], want=A[:10])])

    def test_unlisted_repository_keeps_legacy_message(self):
        doc = pins_doc({"corpus/repo": A})
        reg = registry_rows(("guide-a", "newcorp/repo", B))
        reasons = up.check_registry_pins(doc, reg)
        self.assertEqual(reasons, [LEGACY_UNLISTED.format(eid="guide-a",
                                                          repo="newcorp/repo")])

    def test_no_override_never_falls_back_on_malformed_registry_commit(self):
        reg = registry_rows(("guide-a", "corpus/repo", "not-a-sha"))
        with self.assertRaises(up.UpstreamPinError):
            up.check_registry_pins(pins_doc(), reg)


class EffectivePinTests(unittest.TestCase):
    def test_override_beats_default_exactly(self):
        doc = pins_doc({"corpus/repo": A}, {"guide-a": {"repository": "corpus/repo",
                                                        "commit": B}})
        reg = registry_rows(("guide-a", "corpus/repo", B))
        self.assertEqual(up.check_registry_pins(doc, reg), [])
        commit, is_override = up.effective_pin_for_entry(doc, "guide-a", "corpus/repo")
        self.assertEqual((commit, is_override), (B, True))

    def test_override_mismatch_refused_even_when_default_would_match(self):
        # A stale override is still that row's effective pin: matching the
        # repository default is NOT an escape hatch; exact equality against
        # the reviewed effective pin is required.
        doc = pins_doc({"corpus/repo": A}, {"guide-a": {"repository": "corpus/repo",
                                                        "commit": B}})
        reg = registry_rows(("guide-a", "corpus/repo", A))
        reasons = up.check_registry_pins(doc, reg)
        self.assertEqual(len(reasons), 1)
        self.assertIn("diverges from its reviewed per-entry baseline", reasons[0])
        self.assertIn(A[:10], reasons[0])
        self.assertIn(B[:10], reasons[0])

    def test_default_mismatch_with_override_present_refused(self):
        doc = pins_doc({"corpus/repo": A}, {"guide-a": {"repository": "corpus/repo",
                                                        "commit": B}})
        reg = registry_rows(("guide-a", "corpus/repo", C))
        reasons = up.check_registry_pins(doc, reg)
        self.assertEqual(len(reasons), 1)
        self.assertIn("diverges from its reviewed per-entry baseline", reasons[0])

    def test_effective_pin_reader_refuses_misbound_or_unlisted(self):
        doc = pins_doc({"corpus/repo": A}, {"guide-a": {"repository": "other/repo",
                                                        "commit": B}})
        with self.assertRaises(up.UpstreamPinError):
            up.effective_pin_for_entry(doc, "guide-a", "corpus/repo")
        with self.assertRaises(up.UpstreamPinError):
            up.effective_pin_for_entry(pins_doc(), "guide-a", "absent/repo")


class OverrideBindingDenialTests(unittest.TestCase):
    def test_override_on_unknown_id_refused(self):
        doc = pins_doc({"corpus/repo": A}, {"ghost-skill": {"repository": "corpus/repo",
                                                            "commit": B}})
        reg = registry_rows(("guide-a", "corpus/repo", A))
        reasons = up.check_registry_pins(doc, reg)
        self.assertEqual(len(reasons), 1)
        self.assertIn("ghost-skill", reasons[0])
        self.assertIn("no registry entry", reasons[0])

    def test_override_on_local_builtin_row_refused(self):
        doc = pins_doc({"corpus/repo": A}, {"floe-builtin": {"repository": "corpus/repo",
                                                             "commit": B}})
        reg = registry_rows(("floe-builtin", None, None),
                            ("guide-a", "corpus/repo", A))
        reasons = up.check_registry_pins(doc, reg)
        self.assertEqual(len(reasons), 1)
        self.assertIn("no upstream block", reasons[0])

    def test_override_changing_repository_identity_refused(self):
        doc = pins_doc({"corpus/repo": A, "other/repo": C},
                       {"guide-a": {"repository": "other/repo", "commit": C}})
        reg = registry_rows(("guide-a", "corpus/repo", A))
        reasons = up.check_registry_pins(doc, reg)
        self.assertEqual(len(reasons), 1)
        self.assertIn("does not match the entry's upstream repository", reasons[0])

    def test_override_on_new_unlisted_repository_refused_at_parse(self):
        doc = pins_doc({"corpus/repo": A}, {"guide-a": {"repository": "fresh/repo",
                                                        "commit": B}})
        with self.assertRaises(up.UpstreamPinError) as caught:
            up.parse_pins_bytes(doc_bytes(doc))
        self.assertIn("not listed in the repositories map", str(caught.exception))


class StrictParserDenialTests(unittest.TestCase):
    def parse_fail(self, data, fragment=None):
        with self.assertRaises(up.UpstreamPinError) as caught:
            up.parse_pins_bytes(data)
        if fragment is not None:
            self.assertIn(fragment, str(caught.exception))

    def test_duplicate_keys_at_any_depth(self):
        self.parse_fail(b'{"reviewBaselineDate": "2026-10-26",'
                        b' "reviewBaselineDate": "2026-10-27",'
                        b' "repositories": {"a/b": "' + A.encode() + b'"}}',
                        "duplicate JSON key")
        # duplicate inside a nested override object
        self.parse_fail(json.dumps(
            {"reviewBaselineDate": "2026-10-26", "repositories": {"a/b": A},
             "skillOverrides": {"guide-a": {"repository": "a/b", "commit": B}}},
            ensure_ascii=False)
            .replace('"commit": "%s"' % B,
                     '"commit": "%s", "commit": "%s"' % (B, B)).encode(),
            "duplicate JSON key")

    def test_oversized_input(self):
        data = b" " * up.MAX_PINS_BYTES + doc_bytes(pins_doc())
        self.parse_fail(data, "oversized")

    def test_bad_utf8(self):
        self.parse_fail(b'{"reviewBaselineDate": "\xff\xfe\x81",', "UTF-8")

    def test_non_bytes_and_nan(self):
        self.parse_fail("string not bytes", "raw bytes")
        self.parse_fail(b'{"reviewBaselineDate": NaN, "repositories": {}}',
                        "not a legal pin value")

    def test_unknown_and_missing_fields(self):
        doc = pins_doc()
        doc["branches"] = {"main": A}
        self.parse_fail(doc_bytes(doc), "unknown field")
        doc = pins_doc()
        del doc["repositories"]
        self.parse_fail(doc_bytes(doc), "missing field")
        doc = pins_doc()
        doc["skillOverrides"] = []
        self.parse_fail(doc_bytes(doc), "skillOverrides must be an object")
        doc = pins_doc({"corpus/repo": A}, {"guide-a": {"repository": "corpus/repo",
                                                        "commit": B, "branch": "main"}})
        self.parse_fail(doc_bytes(doc), "keys must be exactly repository+commit")
        doc = pins_doc({"corpus/repo": A}, {"guide-a": {"repository": "corpus/repo"}})
        self.parse_fail(doc_bytes(doc), "keys must be exactly repository+commit")

    def test_malformed_commits_ids_and_dates(self):
        for bad_commit in ("A" * 40, "b" * 39, "b" * 41, "g" * 40):
            self.parse_fail(doc_bytes(pins_doc({"corpus/repo": bad_commit})),
                            "40 lowercase hex")
        self.parse_fail(doc_bytes({"reviewBaselineDate": "2026-10-26",
                                   "repositories": {"n slash": A}}), "owner/repo")
        for bad_date in ("2026-02-30", "2026-13-01", "2026-1-1", "not-a-date",
                         "2025-02-29"):
            self.parse_fail(doc_bytes(pins_doc(date=bad_date)), "real YYYY-MM-DD")
        self.parse_fail(doc_bytes(pins_doc({"corpus/repo": A},
                                           {"Bad_Id": {"repository": "corpus/repo",
                                                       "commit": B}})),
                        "SkillIdentifier")

    def test_empty_repositories_and_non_object(self):
        self.parse_fail(doc_bytes(pins_doc({})), "non-empty object")
        self.parse_fail(b"[1, 2, 3]", "must be a JSON object")
        self.parse_fail(b"{not json", "not valid JSON")

    def test_valid_legacy_bytes_parse_without_overrides(self):
        doc = up.parse_pins_bytes(doc_bytes(pins_doc()))
        self.assertNotIn("skillOverrides", doc)


class AdvancePositiveTests(unittest.TestCase):
    def setUp(self):
        self.repos = {"corpus/repo": A, "watch/repo": D}
        self.doc = pins_doc(self.repos)
        self.old = registry_rows(("guide-a", "corpus/repo", A),
                                 ("script-b", "corpus/repo", A),
                                 ("floe-owned", None, None))

    def new_registry(self, **commits_by_id):
        rows = []
        for entry in self.old["skills"]:
            eid = entry["id"]
            if eid in commits_by_id:
                commit = commits_by_id[eid]
                repo = entry["upstream"]["repository"][len(up.GITHUB_URL_PREFIX):]
                rows.append((eid, repo, commit))
            else:
                repo = None if entry["upstream"] is None else \
                    entry["upstream"]["repository"][len(up.GITHUB_URL_PREFIX):]
                commit = None if entry["upstream"] is None else entry["upstream"]["commit"]
                rows.append((eid, repo, commit))
        return registry_rows(*rows)

    def test_accepted_guide_advances_override_while_peer_held(self):
        new = self.new_registry(**{"guide-a": B})
        advanced = up.advance_pin_document(self.doc, self.old, new, {"guide-a"},
                                           "2026-10-28")
        self.assertEqual(advanced["reviewBaselineDate"], "2026-10-28")
        self.assertEqual(advanced["repositories"], self.repos)  # default held
        self.assertEqual(advanced["skillOverrides"],
                         {"guide-a": {"repository": "corpus/repo", "commit": B}})
        self.assertEqual(up.check_registry_pins(advanced, new), [])
        # the held peer still validates only against the OLD default
        self.assertEqual(up.effective_pin_for_entry(advanced, "script-b",
                                                    "corpus/repo"), (A, False))
        # and the new document honestly does NOT match the old registry
        reasons = up.check_registry_pins(advanced, self.old)
        self.assertEqual(len(reasons), 1)
        self.assertIn("guide-a", reasons[0])

    def test_all_repo_entries_advance_compacts_default_and_drops_overrides(self):
        mixed = up.advance_pin_document(self.doc, self.old,
                                        self.new_registry(**{"guide-a": B}),
                                        ["guide-a"], "2026-10-27")
        final = up.advance_pin_document(mixed,
                                        self.new_registry(**{"guide-a": B}),
                                        self.new_registry(**{"guide-a": B,
                                                             "script-b": B}),
                                        ("script-b",), "2026-10-28")
        self.assertEqual(final["repositories"]["corpus/repo"], B)
        self.assertNotIn("skillOverrides", final)
        self.assertEqual(final["repositories"]["watch/repo"], D)  # watch-only kept
        self.assertEqual(up.check_registry_pins(final, self.new_registry(
            **{"guide-a": B, "script-b": B})), [])

    def test_independent_multi_repo_updates(self):
        doc = pins_doc({"repo/one": A, "repo/two": A})
        old = registry_rows(("g1", "repo/one", A), ("s1", "repo/one", A),
                           ("g2", "repo/two", A))
        new = registry_rows(("g1", "repo/one", B), ("s1", "repo/one", A),
                            ("g2", "repo/two", C))
        advanced = up.advance_pin_document(doc, old, new, {"g1", "g2"}, "2026-10-28")
        self.assertEqual(advanced["repositories"], {"repo/one": A, "repo/two": C})
        self.assertEqual(advanced["skillOverrides"],
                         {"g1": {"repository": "repo/one", "commit": B}})
        self.assertEqual(up.check_registry_pins(advanced, new), [])

    def test_redundant_valid_overrides_are_dropped_on_recompute(self):
        # prior keeps a stale repository default with reviewed overrides while
        # both rows already share one commit: a no-change advance compacts the
        # default to that commit and honestly drops the redundant overrides.
        doc = pins_doc({"corpus/repo": A},
                       {"guide-a": {"repository": "corpus/repo", "commit": B},
                        "script-b": {"repository": "corpus/repo", "commit": B}})
        rows_b = registry_rows(("guide-a", "corpus/repo", B),
                               ("script-b", "corpus/repo", B))
        self.assertEqual(up.check_registry_pins(doc, rows_b), [])
        compact = up.advance_pin_document(doc, rows_b, rows_b, set(), "2026-10-28")
        self.assertEqual(compact["repositories"], {"corpus/repo": B})
        self.assertNotIn("skillOverrides", compact)
        # then one held one advanced stays mixed: default retained, overrides
        # recomputed only for the differing rows, and a later full advance
        # compacts again.
        rows_mixed = registry_rows(("guide-a", "corpus/repo", B),
                                   ("script-b", "corpus/repo", C))
        advanced = up.advance_pin_document(compact, rows_b, rows_mixed,
                                           {"script-b"}, "2026-10-29")
        self.assertEqual(advanced["repositories"], {"corpus/repo": B})
        self.assertEqual(advanced["skillOverrides"],
                         {"script-b": {"repository": "corpus/repo", "commit": C}})
        rows_c = registry_rows(("guide-a", "corpus/repo", C),
                               ("script-b", "corpus/repo", C))
        settled = up.advance_pin_document(advanced, rows_mixed, rows_c,
                                          {"guide-a"}, "2026-10-30")
        self.assertEqual(settled["repositories"], {"corpus/repo": C})
        self.assertNotIn("skillOverrides", settled)

    def test_deterministic_and_input_shape_independent(self):
        new = self.new_registry(**{"guide-a": B})
        one = up.advance_pin_document(self.doc, self.old, new, ["guide-a"], "2026-10-28")
        two = up.advance_pin_document(json.loads(doc_bytes(pins_doc(self.repos))),
                                      json.loads(json.dumps(self.old)),
                                      json.loads(json.dumps(new)),
                                      {"guide-a"}, "2026-10-28")
        self.assertEqual(up.deterministic_bytes(one), up.deterministic_bytes(two))

    def test_no_side_effects_on_inputs(self):
        doc_copy = copy.deepcopy(self.doc)
        old_copy = copy.deepcopy(self.old)
        new = self.new_registry(**{"guide-a": B})
        new_copy = copy.deepcopy(new)
        accepted = {"guide-a"}
        accepted_copy = set(accepted)
        advanced = up.advance_pin_document(self.doc, self.old, new, accepted,
                                           "2026-10-28")
        self.assertEqual(self.doc, doc_copy)
        self.assertEqual(self.old, old_copy)
        self.assertEqual(new, new_copy)
        self.assertEqual(accepted, accepted_copy)
        # mutating the result never reaches the inputs
        advanced["repositories"]["corpus/repo"] = C
        advanced["skillOverrides"]["guide-a"]["commit"] = D
        self.assertEqual(self.doc, doc_copy)

    def test_check_registry_pins_has_no_side_effects(self):
        doc_copy = copy.deepcopy(self.doc)
        reg_copy = copy.deepcopy(self.old)
        up.check_registry_pins(self.doc, self.old)
        self.assertEqual(self.doc, doc_copy)
        self.assertEqual(self.old, reg_copy)


class AdvanceDenialTests(unittest.TestCase):
    def setUp(self):
        self.doc = pins_doc({"corpus/repo": A})
        self.old = registry_rows(("guide-a", "corpus/repo", A),
                                 ("script-b", "corpus/repo", A))
        self.new = registry_rows(("guide-a", "corpus/repo", B),
                                 ("script-b", "corpus/repo", A))

    def fail_advance(self, doc, old, new, accepted, today="2026-10-28",
                     fragment=None):
        with self.assertRaises(up.UpstreamPinError) as caught:
            up.advance_pin_document(doc, old, new, accepted, today)
        if fragment is not None:
            self.assertIn(fragment, str(caught.exception))

    def test_unaccepted_pin_change_refused(self):
        self.fail_advance(self.doc, self.old,
                          registry_rows(("guide-a", "corpus/repo", B),
                                        ("script-b", "corpus/repo", C)),
                          {"guide-a"}, fragment="unaccepted entry changed")

    def test_id_set_change_refused(self):
        self.fail_advance(self.doc, self.old,
                          registry_rows(("guide-a", "corpus/repo", B)),
                          {"guide-a"}, fragment="exact same entry id set")
        self.fail_advance(self.doc, self.old,
                          registry_rows(("guide-a", "corpus/repo", A),
                                        ("script-b", "corpus/repo", A),
                                        ("guide-c", "corpus/repo", A)),
                          {"guide-a"}, fragment="exact same entry id set")

    def test_repository_identity_change_refused(self):
        self.fail_advance(pins_doc({"corpus/repo": A, "other/repo": A}), self.old,
                          registry_rows(("guide-a", "other/repo", B),
                                        ("script-b", "corpus/repo", A)),
                          {"guide-a"}, fragment="repository identity changed")

    def test_upstream_null_flips_refused(self):
        # no automatic import of Floe-original replacements and no silent
        # admission of a new upstream row through a pin advance
        self.fail_advance(self.doc, self.old,
                          registry_rows(("guide-a", None, None),
                                        ("script-b", "corpus/repo", A)),
                          {"guide-a"}, fragment="repository identity changed")
        self.fail_advance(self.doc, self.old,
                          registry_rows(("guide-a", "corpus/repo", A),
                                        ("script-b", None, None)),
                          {"script-b"}, fragment="repository identity changed")

    def test_accepted_ids_must_be_external_entries(self):
        # no pin changes at all, only a ghost accepted id -> that exact denial
        self.fail_advance(self.doc, self.old, self.old, {"ghost"},
                          fragment="must exist in both registries")
        mixed = registry_rows(("guide-a", "corpus/repo", A), ("floe-owned", None, None))
        self.fail_advance(pins_doc(), mixed, mixed, {"floe-owned"},
                          fragment="no upstream block")
        self.fail_advance(self.doc, self.old, self.new, "guide-a",
                          fragment="not a single string")

    def test_prior_document_must_match_old_registry(self):
        stale = pins_doc({"corpus/repo": A}, {"guide-a": {"repository": "corpus/repo",
                                                          "commit": C}})
        self.fail_advance(stale, self.old, self.new, {"guide-a"},
                          fragment="does not match the old registry")

    def test_bad_today_refused(self):
        self.fail_advance(self.doc, self.old, self.new, {"guide-a"},
                          today="2026-02-30", fragment="real YYYY-MM-DD")

    def test_malformed_new_commit_refused(self):
        self.fail_advance(self.doc, self.old,
                          registry_rows(("guide-a", "corpus/repo", "zz"),
                                        ("script-b", "corpus/repo", A)),
                          {"guide-a"}, fragment="40 lowercase hex")


class LiveBaselineTests(unittest.TestCase):
    """The real repository bytes today: legacy document, zero overrides,
    integrated read-only gate, untouched live files."""

    PINS = REPO / "docs" / "UPSTREAM-PINS.json"
    REGISTRY = REPO / "catalog" / "skills.json"

    def test_live_documents_validate_with_zero_reasons_and_stay_untouched(self):
        pins_before = self.PINS.read_bytes()
        registry_before = self.REGISTRY.read_bytes()
        doc = up.parse_pins_bytes(pins_before)
        self.assertNotIn("skillOverrides", doc,
                         "the current reviewed baseline must not carry overrides yet")
        registry = json.loads(registry_before)
        self.assertEqual(up.check_registry_pins(doc, registry), [])
        self.assertEqual(self.PINS.read_bytes(), pins_before)
        self.assertEqual(self.REGISTRY.read_bytes(), registry_before)

    def test_live_advance_noop_compacts_to_equivalent_content(self):
        doc = up.parse_pins_bytes(self.PINS.read_bytes())
        registry = json.loads(self.REGISTRY.read_bytes())
        advanced = up.advance_pin_document(doc, registry, registry, [], "2026-10-28")
        self.assertEqual(advanced["repositories"], doc["repositories"])
        self.assertNotIn("skillOverrides", advanced)
        self.assertEqual(up.check_registry_pins(advanced, registry), [])

    def test_deterministic_bytes_are_stable_across_insertion_order(self):
        one = {"reviewBaselineDate": "2026-10-28",
               "repositories": {"z/repo": B, "a/repo": A},
               "skillOverrides": {"g-z": {"repository": "z/repo", "commit": C},
                                  "g-a": {"repository": "a/repo", "commit": D}}}
        two = {"skillOverrides": {"g-a": {"commit": D, "repository": "a/repo"},
                                  "g-z": {"commit": C, "repository": "z/repo"}},
               "repositories": {"a/repo": A, "z/repo": B},
               "reviewBaselineDate": "2026-10-28"}
        self.assertEqual(up.deterministic_bytes(one), up.deterministic_bytes(two))
        self.assertEqual(hashlib.sha256(up.deterministic_bytes(one)).hexdigest(),
                         hashlib.sha256(up.deterministic_bytes(two)).hexdigest())

    def test_check_catalog_check_pins_integration_passes_read_only(self):
        import check_catalog
        reasons = []
        pins_before = self.PINS.read_bytes()
        registry_before = self.REGISTRY.read_bytes()
        check_catalog.check_pins(reasons)
        self.assertEqual(reasons, [])
        self.assertEqual(self.PINS.read_bytes(), pins_before)
        self.assertEqual(self.REGISTRY.read_bytes(), registry_before)

    def test_held_repo_scenario_matches_real_shape(self):
        # One corpus repository carries many guides plus a script runtime row;
        # accepting exactly one guide must not move the held peers. Uses the
        # REAL live registry snapshot (read-only) so the 43-row contract, ids
        # and per-repo membership are the shipped ones.
        pins_before = self.PINS.read_bytes()
        registry_before = self.REGISTRY.read_bytes()
        doc = up.parse_pins_bytes(pins_before)
        old_registry = json.loads(registry_before)
        external = [e for e in old_registry["skills"] if e["upstream"] is not None]
        from collections import defaultdict
        by_repo = defaultdict(list)
        for entry in external:
            repo = entry["upstream"]["repository"][len(up.GITHUB_URL_PREFIX):]
            by_repo[repo].append(entry)
        repo, rows = max(by_repo.items(), key=lambda kv: len(kv[1]))
        guide, held = rows[0], rows[1]
        new_commit = B if guide["upstream"]["commit"] != B else C
        new_registry = json.loads(json.dumps(old_registry))
        for entry in new_registry["skills"]:
            if entry["id"] == guide["id"]:
                entry["upstream"]["commit"] = new_commit
        advanced = up.advance_pin_document(doc, old_registry, new_registry,
                                           {guide["id"]}, "2026-10-28")
        self.assertEqual(advanced["repositories"][repo], doc["repositories"][repo])
        self.assertEqual(advanced["skillOverrides"][guide["id"]],
                         {"repository": repo, "commit": new_commit})
        self.assertNotIn(held["id"], advanced["skillOverrides"])
        self.assertEqual(up.check_registry_pins(advanced, new_registry), [])
        # every other repository's baseline is byte-identical
        for other, other_commit in doc["repositories"].items():
            if other != repo:
                self.assertEqual(advanced["repositories"][other], other_commit)
        # the advance never rewrites the live baseline document
        self.assertEqual(self.PINS.read_bytes(), pins_before)
        self.assertEqual(self.REGISTRY.read_bytes(), registry_before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
