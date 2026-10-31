#!/usr/bin/env python3
"""Upstream tracking core tests: coverage, merges, gates, holds, determinism.

Offline and deterministic: synthetic fixture upstreams drive the merge/gate/
tier logic; ONE integration test uses a real local bare git repository (no
network) to exercise GitUpstreamSource commit resolution, subpath tree
comparison and unsafe-entry detection. The live repository policy/registry
cross-coverage is validated against the real committed files.

Run: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_upstream_updates -v
 or: PYTHONDONTWRITEBYTECODE=1 python3 tests/test_upstream_updates.py -v
"""
import copy
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import hubcore  # noqa: E402
import upstream_updates as uu  # noqa: E402

TODAY = "2026-10-28"
PIN = "1" * 40
HEAD = "2" * 40
OTHER = "3" * 40
FIXTURE_REPO = "https://github.com/fixture-owner/fixture-skills"
FIXTURE_ENGINE_REPO = "https://github.com/fixture-owner/fixture-engine"
FIXTURE_WATCH_REPO = "https://github.com/watch-owner/watch-repo"


# ---------------------------------------------------------------------------
# builders
# ---------------------------------------------------------------------------

def skill_md(name, description="fixture skill", body="Body text.\n"):
    return f"---\nname: {name}\ndescription: {description}\n---\n\n{body}".encode("utf-8")


def floe_json(skill_id, version, runtime="none", caps=None, tools=None):
    return hubcore.encoded({
        "schemaVersion": 1, "id": skill_id, "version": version,
        "capabilities": caps or [], "tools": tools or [],
        "platforms": ["ios"], "scriptRuntime": runtime, "pythonPackages": []})


def provenance_md(skill_id, repo_url, pin, subpath, files=None):
    lines = [
        f"# Provenance — {skill_id}",
        "",
        f"- Upstream repository: {repo_url}",
        f"- Pinned commit: `{pin}` (verified at fetch)",
        f"- Upstream path: `{subpath}`",
        "",
        "## File inventory (sha256, this checkout; PROVENANCE.md self-hash intentionally omitted)",
    ]
    for path in sorted(files or {}):
        if path == "references/PROVENANCE.md":
            continue
        lines.append(f"- `{path}` sha256 `{hubcore.sha256_hex(files[path].encode() if isinstance(files[path], str) else files[path])}`")
    return ("\n".join(lines) + "\n").encode("utf-8")


def guide_local_tree(skill_id, version, repo_url=FIXTURE_REPO, pin=PIN, subpath="skills/x",
                     guide_body="local adapted line\n", skill_body="old body line\n"):
    files = {
        "SKILL.md": skill_md(skill_id, body=skill_body),
        "floe.json": floe_json(skill_id, version),
        "references/guide.md": ("# Guide\n\n" + guide_body).encode("utf-8"),
        "references/licenses/UPSTREAM-LICENSE.txt": b"MIT fixture license\n",
        "references/licenses/LICENSE-NOTE.md": b"Floe-owned note.\n",
    }
    files["references/PROVENANCE.md"] = provenance_md(skill_id, repo_url, pin, subpath, files)
    return files


def snap(files, modes=None, sizes=None, types=None):
    """Build an upstream snapshot dict directly (unit-level)."""
    modes = modes or {}
    sizes = sizes or {}
    types = types or {}
    out = {}
    for rel, data in files.items():
        mode = modes.get(rel, "100644")
        problem = None
        if types.get(rel) == "commit":
            problem = "non-blob upstream tree entry (type=commit)"
        elif mode == "120000":
            problem = "upstream symlink entries are never carried"
        out[rel] = {"mode": mode, "type": types.get(rel, "blob"),
                    "sha": hubcore.sha256_hex(data)[:40],
                    "size": sizes.get(rel, len(data)), "data": data, "problem": problem}
    return out


def make_entry(skill_id, *, pin=PIN, repo_url=FIXTURE_REPO, subpath="skills/x",
               version="1.0.0", runtime="none", plan=1, upstream=True, kind="optional",
               source="A", deep=False):
    if runtime == "none":
        planned = {"scriptRuntime": "none", "capabilities": [], "tools": [],
                   "installPlatforms": ["ios", "android"], "pythonPackagesPlan": [],
                   "execution": {"os": None, "arch": "n/a", "evidence": "unproven"}}
    else:
        planned = {"scriptRuntime": runtime, "capabilities": ["execution.remote"],
                   "tools": ["exec.shell"], "installPlatforms": ["ios", "android"],
                   "pythonPackagesPlan": [],
                   "execution": {"os": None, "arch": "n/a", "evidence": "unproven"}}
    caps = planned["capabilities"]
    tools = planned["tools"]
    floe_runtime = runtime
    entry = {
        "id": skill_id, "planNumber": plan, "kind": kind, "source": source,
        "name": {"en": "Fixture Skill", "zh-Hans": "夹具技能"},
        "description": {"en": "fixture", "zh-Hans": "夹具"},
        "category": "research-data", "tags": ["fixture", "test"],
        "deepAdaptation": deep,
        "upstream": None, "firstParty": None,
        "plannedRuntime": planned, "versionTarget": version, "minimumAppVersion": None,
        "status": {"sourcePinned": True, "licenseChecked": True, "adaptation": "frozen",
                   "packaged": True, "reviewed": True, "qualified": True,
                   "published": False, "executionVerified": False},
        "notes": {"en": "", "zh-Hans": ""},
    }
    if upstream:
        entry["upstream"] = {
            "repository": repo_url, "commit": pin, "path": subpath,
            "skillManifestPath": subpath + "/SKILL.md", "retrievedAt": "2026-10-26",
            "licenseStatus": "verified", "licenseEvidencePath": "LICENSE",
        }
    entry["_floe"] = {"runtime": floe_runtime, "caps": caps, "tools": tools}
    return entry


def strip_private(entry):
    return {k: v for k, v in entry.items() if not k.startswith("_")}


def make_registry(entries):
    return {
        "schemaVersion": 1, "registry": "candidate", "publisher": "JiangNanGenius",
        "hub": {"repository": "JiangNanGenius/floe-skill-hub",
                "channelRoots": {"ios": ".", "android": "android"},
                "pinsAuthority": "docs/UPSTREAM-PINS.json",
                "productionLayout": {}},
        "categories": [{"id": cat, "name": {"en": cat.replace("-", " ").title(),
                                            "zh-Hans": "夹具类目"}}
                       for cat in hubcore.CATEGORIES],
        "notes": {"en": "fixture", "zh-Hans": "夹具"},
        "skills": [strip_private(e) for e in entries],
    }


def make_policy(tracked, skills_cfg, repositories, *, engine=None, watch=None,
                builtins=None, first_party=None):
    selection = {
        "tracked": list(tracked),
        "engineManaged": [e["skillId"] for e in (engine or {}).values()],
        "watchOnly": watch or [],
        "notTracked": {"builtins": builtins or [], "firstParty": first_party or [],
                       "note": "fixture"},
    }
    return {
        "schemaVersion": 1, "policyId": "floe-skill-hub-upstream-update-policy",
        "updatedAt": TODAY,
        "description": {"en": "fixture", "zh-Hans": "夹具"},
        "executionModel": {"unattended": "github-actions-only", "localDaemonsProhibited": True,
                           "noMacAppCodexOnlineDependency": True,
                           "eligibleUpdates": "fixture", "heldUpdates": "fixture"},
        "pinsAuthority": "docs/UPSTREAM-PINS.json",
        "registryAuthority": "catalog/skills.json",
        "repositories": repositories,
        "engineTracking": engine or {},
        "selection": selection,
        "layoutDefaults": {"licenseCarryRule": "fixture", "floeOwnedDefaults": [],
                           "floeOwnedNote": "fixture"},
        "skills": skills_cfg,
        "versioning": {"bump": "patch", "rule": "fixture"},
        "gates": {"packageGates": "f", "upstreamEntryGates": "f", "driftHolds": "f",
                  "editorialHolds": "f", "minimumAppVersion": "f"},
    }


def fixture_source(repos):
    return uu.FixtureUpstreamSource(repos)


def commit(files, modes=None):
    return {"files": dict(files), "modes": modes or {}}


def write_hub_root(root, registry, policy, pins, *, sources=None, packages=None,
                   links=None, engine_locks=None):
    root = pathlib.Path(root)
    (root / "catalog").mkdir(parents=True, exist_ok=True)
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "catalog" / "skills.json").write_bytes(hubcore.pretty(registry))
    (root / "catalog" / "upstream-update-policy.json").write_bytes(hubcore.pretty(policy))
    (root / "docs" / "UPSTREAM-PINS.json").write_bytes(
        (json.dumps(pins, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    for skill_id, files in (sources or {}).items():
        for rel, data in files.items():
            target = root / "sources" / skill_id / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    for skill_id, versions in (packages or {}).items():
        for version, files in versions.items():
            archive = root / "packages" / skill_id / version / f"{skill_id}.zip"
            archive.parent.mkdir(parents=True, exist_ok=True)
            archive.write_bytes(hubcore.make_zip(files))
    if links is not None:
        (root / "showcase").mkdir(parents=True, exist_ok=True)
        (root / "showcase" / "links.json").write_bytes(
            (json.dumps(links, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    for rel, doc in (engine_locks or {}).items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(json.dumps(doc).encode("utf-8"))
    return root


def links_doc_for(skill_id, rel_path, sha256_hex, line_start, line_end):
    return {"schemaVersion": 1, "entries": {skill_id: {"auditStatus": "audited", "links": [
        {"relation": "references",
         "target": {"kind": "external-skill",
                    "label": {"en": "x", "zh-Hans": "x"},
                    "url": "https://github.com/fixture-owner/fixture-skills/tree/" + PIN},
         "evidence": [{"file": f"sources/{skill_id}/{rel_path}", "sha256": sha256_hex,
                       "lineStart": line_start, "lineEnd": line_end}],
         "notes": {"en": "fixture", "zh-Hans": "夹具"}}]}}}


# ---------------------------------------------------------------------------
# real policy/registry coverage (live committed files)
# ---------------------------------------------------------------------------

class TestRealPolicyCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = uu.load_inputs(REPO)

    def test_live_policy_is_valid_and_covers_43_rows(self):
        policy = self.inputs["policy"]
        selection = policy["selection"]
        self.assertEqual(len(self.inputs["entries"]), 43)
        self.assertEqual(len(selection["tracked"]), 30)
        self.assertEqual(selection["engineManaged"], ["impeccable"])
        self.assertEqual({w["id"] for w in selection["watchOnly"]},
                         {"doc-coauthoring", "writing-guidelines", "react-best-practices",
                          "composition-patterns", "web-design-guidelines"})
        self.assertEqual(set(selection["notTracked"]["builtins"]),
                         set(hubcore.RESERVED_BUILTIN_IDS))
        self.assertEqual(set(selection["notTracked"]["firstParty"]),
                         {"floe-email-drafting", "floe-file-organizer",
                          "floe-invoice-organizer"})
        groups = (set(selection["tracked"]) | set(selection["engineManaged"])
                  | {w["id"] for w in selection["watchOnly"]}
                  | set(selection["notTracked"]["builtins"])
                  | set(selection["notTracked"]["firstParty"]))
        self.assertEqual(groups, set(self.inputs["entries"]))
        self.assertEqual(len(groups), 43)

    def test_tracked_entries_match_registry_upstream_and_pins(self):
        policy = self.inputs["policy"]
        pins = self.inputs["pins"]
        repos = set()
        for skill_id in policy["selection"]["tracked"]:
            entry = self.inputs["entries"][skill_id]
            self.assertIsNotNone(entry["upstream"], skill_id)
            short = entry["upstream"]["repository"].removeprefix("https://github.com/")
            repos.add(short)
            self.assertEqual(entry["upstream"]["commit"], pins[short], skill_id)
            self.assertIn(skill_id, policy["skills"])
        self.assertEqual(set(policy["skills"]), set(policy["selection"]["tracked"]))
        self.assertTrue(repos <= set(pins))
        # five corpus repos actually imported + engine repo; vercel-labs is watch-only
        self.assertEqual(repos, {"anthropics/skills", "alirezarezvani/claude-skills",
                                 "K-Dense-AI/scientific-agent-skills", "obra/superpowers"})

    def test_excluded_and_watch_entries_have_no_upstream(self):
        policy = self.inputs["policy"]
        for skill_id in (policy["selection"]["notTracked"]["builtins"]
                         + policy["selection"]["notTracked"]["firstParty"]
                         + [w["id"] for w in policy["selection"]["watchOnly"]]):
            self.assertIsNone(self.inputs["entries"][skill_id]["upstream"], skill_id)

    def test_engine_managed_never_generic(self):
        engine = self.inputs["policy"]["engineTracking"]["impeccable"]
        self.assertTrue(engine["genericMergeProhibited"])
        self.assertIn("sources/impeccable", engine["ownedPaths"])

    def test_policy_validation_rejects_tampering(self):
        registry = self.inputs["registry"]
        pins_doc = self.inputs["pinsDoc"]
        tampered = copy.deepcopy(self.inputs["policy"])
        del tampered["skills"]["sympy"]
        with self.assertRaises(uu.UpstreamError):
            uu.validate_policy(tampered, registry, pins_doc)
        tampered = copy.deepcopy(self.inputs["policy"])
        tampered["selection"]["tracked"].append("floe-pdf")
        tampered["selection"]["notTracked"]["builtins"].remove("floe-pdf")
        tampered["skills"]["floe-pdf"] = {"relocations": [], "fileMappings": [],
                                          "excludedUpstream": []}
        with self.assertRaises(uu.UpstreamError):
            uu.validate_policy(tampered, registry, pins_doc)
        tampered = copy.deepcopy(self.inputs["policy"])
        tampered["executionModel"]["unattended"] = "local-daemon"
        with self.assertRaises(uu.UpstreamError):
            uu.validate_policy(tampered, registry, pins_doc)


# ---------------------------------------------------------------------------
# pure core: patterns, correspondence, merge, fingerprints
# ---------------------------------------------------------------------------

class TestPatterns(unittest.TestCase):
    def test_path_matcher(self):
        matcher = uu.PathMatcher(["scripts/", "test-*.md", "exact.md"])
        self.assertEqual(matcher.match("scripts/a.py"), "scripts/")
        self.assertEqual(matcher.match("test-pressure-1.md"), "test-*.md")
        self.assertEqual(matcher.match("exact.md"), "exact.md")
        self.assertIsNone(matcher.match("references/scripts.md"))
        # '*' never crosses '/'
        self.assertIsNone(uu.PathMatcher(["test-*.md"]).match("sub/test-x.md"))

    def test_prose_allowlist_is_narrow(self):
        self.assertTrue(uu.is_prose_allowlisted("SKILL.md"))
        self.assertTrue(uu.is_prose_allowlisted("references/guide.md"))
        self.assertTrue(uu.is_prose_allowlisted("references/licenses/LICENSE-NOTE.md"))
        self.assertFalse(uu.is_prose_allowlisted("references/engine-data/reference/x.md"))
        self.assertFalse(uu.is_prose_allowlisted("references/examples/deep.md"))
        self.assertFalse(uu.is_prose_allowlisted("assets/fonts/x.ttf"))
        self.assertFalse(uu.is_prose_allowlisted("scripts/run.py"))
        self.assertFalse(uu.is_prose_allowlisted("references/requirements.lock.txt"))

    def test_instruction_files_exclude_bookkeeping(self):
        self.assertTrue(uu.is_instruction_fingerprint_file("SKILL.md"))
        self.assertTrue(uu.is_instruction_fingerprint_file("references/examples/x.md"))
        self.assertFalse(uu.is_instruction_fingerprint_file("references/PROVENANCE.md"))
        self.assertFalse(uu.is_instruction_fingerprint_file("references/ADAPTATION-NOTES.md"))
        self.assertFalse(uu.is_instruction_fingerprint_file("references/engine-data/x.md"))
        self.assertFalse(uu.is_instruction_fingerprint_file("references/licenses/L.md"))
        self.assertFalse(uu.is_instruction_fingerprint_file("assets/x.md"))


class TestCorrespondence(unittest.TestCase):
    CFG = {"relocations": [{"upstreamPrefix": "examples/", "localPrefix": "references/examples/"}],
           "fileMappings": [{"upstream": "LICENSE.txt",
                             "local": "references/licenses/UPSTREAM-LICENSE.txt",
                             "kind": "license"},
                            {"upstream": "canvas-fonts/a.ttf", "local": "assets/fonts/a.ttf",
                             "kind": "asset"}],
           "excludedUpstream": ["scripts/", "canvas-fonts/"]}

    def test_priority_filemapping_over_exclusion_then_identity_then_relocation(self):
        old = snap({"SKILL.md": b"s", "LICENSE.txt": b"l", "examples/e.md": b"e",
                    "scripts/x.py": b"p", "canvas-fonts/a.ttf": b"f",
                    "canvas-fonts/b.ttf": b"g"})
        local = {"SKILL.md": b"s-local", "references/guide.md": b"g",
                 "references/licenses/UPSTREAM-LICENSE.txt": b"l",
                 "references/examples/e.md": b"e-local", "assets/fonts/a.ttf": b"f",
                 "floe.json": b"{}"}
        corr = uu.derive_correspondence(old, local, self.CFG)
        self.assertEqual(corr["mappings"]["LICENSE.txt"]["local"],
                         "references/licenses/UPSTREAM-LICENSE.txt")
        self.assertEqual(corr["mappings"]["LICENSE.txt"]["kind"], "license")
        self.assertEqual(corr["mappings"]["canvas-fonts/a.ttf"]["local"], "assets/fonts/a.ttf")
        self.assertEqual(corr["mappings"]["SKILL.md"]["rule"], "identity")
        self.assertEqual(corr["mappings"]["examples/e.md"]["rule"], "relocation")
        self.assertEqual(corr["excluded"], {"scripts/x.py": "scripts/",
                                            "canvas-fonts/b.ttf": "canvas-fonts/"})
        self.assertIn("floe.json", corr["floeOwned"])
        self.assertIn("references/guide.md", corr["floeOwned"])
        self.assertEqual(corr["problems"], [])

    def test_undeclared_not_carried_is_a_problem(self):
        old = snap({"SKILL.md": b"s", "mystery/thing.md": b"m"})
        local = {"SKILL.md": b"s", "floe.json": b"{}"}
        corr = uu.derive_correspondence(old, local, {"relocations": [], "fileMappings": [],
                                                     "excludedUpstream": []})
        self.assertEqual(len(corr["problems"]), 1)
        self.assertEqual(corr["problems"][0]["problem"], "undeclared-not-carried")

    def test_suspected_undeclared_carry_detected_by_content(self):
        old = snap({"SKILL.md": b"s", "docs/moved.md": b"verbatim-bytes"})
        local = {"SKILL.md": b"s", "floe.json": b"{}",
                 "references/moved.md": b"verbatim-bytes"}
        corr = uu.derive_correspondence(old, local, {"relocations": [], "fileMappings": [],
                                                     "excludedUpstream": []})
        problems = [p["problem"] for p in corr["problems"]]
        self.assertIn("undeclared-not-carried", problems)
        self.assertIn("suspected-undeclared-carry", problems)


class TestThreeWayMerge(unittest.TestCase):
    def test_keep_local_when_upstream_unchanged(self):
        merged, conflicts = uu.merge_three_way(b"a\nb\n", b"a\nb\n", b"a\nB\n")
        self.assertEqual(merged, b"a\nB\n")
        self.assertEqual(conflicts, [])

    def test_carry_new_when_local_verbatim(self):
        merged, _ = uu.merge_three_way(b"a\nb\n", b"a\nB2\n", b"a\nb\n")
        self.assertEqual(merged, b"a\nB2\n")

    def test_converged_change(self):
        merged, _ = uu.merge_three_way(b"a\nb\n", b"a\nX\n", b"a\nX\n")
        self.assertEqual(merged, b"a\nX\n")

    def test_clean_merge_disjoint_hunks(self):
        old = b"l1\nl2\nl3\nl4\nl5\nl6\nl7\n"
        new = b"l1\nl2\nUPSTREAM\nl4\nl5\nl6\nl7\n"      # change at line 3
        local = b"l1\nl2\nl3\nl4\nl5\nLOCAL\nl7\n"        # change at line 6
        merged, conflicts = uu.merge_three_way(old, new, local)
        self.assertEqual(conflicts, [])
        self.assertEqual(merged, b"l1\nl2\nUPSTREAM\nl4\nl5\nLOCAL\nl7\n")

    def test_conflict_overlapping_divergent(self):
        old = b"l1\nl2\nl3\n"
        new = b"l1\nUP\nl3\n"
        local = b"l1\nLOCAL\nl3\n"
        merged, conflicts = uu.merge_three_way(old, new, local)
        self.assertIsNone(merged)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["kind"], "divergent-region")

    def test_conflict_adjacent_no_stable_anchor(self):
        old = b"l1\nl2\nl3\nl4\n"
        new = b"l1\nUP2a\nUP2b\nl3\nl4\n"     # replaces line 2
        local = b"l1\nl2\nLOCAL3\nl4\n"       # replaces line 3 (adjacent)
        merged, conflicts = uu.merge_three_way(old, new, local)
        self.assertIsNone(merged)
        self.assertTrue(conflicts)

    def test_identical_changes_deduplicate(self):
        old = b"l1\nl2\nl3\n"
        new = b"l1\nSAME\nl3\n"
        local = b"l1\nSAME\nl3\n"
        merged, conflicts = uu.merge_three_way(old, new, local)
        self.assertEqual(merged, b"l1\nSAME\nl3\n")
        self.assertEqual(conflicts, [])

    def test_binary_divergent_conflict(self):
        merged, conflicts = uu.merge_three_way(b"\xff\xfeold", b"\xff\xfenew", b"\xff\xfeloc")
        self.assertIsNone(merged)
        self.assertEqual(conflicts[0]["kind"], "binary-divergent")

    def test_merge_is_deterministic(self):
        old = ("line%d\n" % 0).encode() + b"".join(b"l%d\n" % i for i in range(1, 40))
        new = old.replace(b"l20\n", b"l20-upstream\nl20b\n")
        local = old.replace(b"l5\n", b"l5-local\n")
        first = uu.merge_three_way(old, new, local)
        second = uu.merge_three_way(old, new, local)
        self.assertEqual(first, second)
        self.assertEqual(first[1], [])
        self.assertIn(b"l20-upstream", first[0])
        self.assertIn(b"l5-local", first[0])


class TestFingerprints(unittest.TestCase):
    def base_files(self, version="1.0.0"):
        return {
            "SKILL.md": skill_md("x", body="Prose only.\n"),
            "floe.json": floe_json("x", version),
            "scripts/run.py": b"print('ok')\n",
            "assets/template.md": b"template\n",
            "references/guide.md": b"# Guide\nprose\n",
            "references/licenses/UPSTREAM-LICENSE.txt": b"MIT\n",
            "references/requirements.lock.txt": b"pkg==1.0\n",
        }

    def test_execution_fingerprint_stable_across_version_bump(self):
        files = self.base_files("1.0.0")
        bumped = dict(files, **{"floe.json": floe_json("x", "1.0.1")})
        self.assertEqual(uu.execution_fingerprint(files)["digest"],
                         uu.execution_fingerprint(bumped)["digest"])

    def test_execution_fingerprint_covers_runtime_surfaces(self):
        base = self.base_files()
        digest = uu.execution_fingerprint(base)["digest"]
        for path, data in (("scripts/run.py", b"print('changed')\n"),
                           ("assets/template.md", b"changed\n"),
                           ("references/requirements.lock.txt", b"pkg==2.0\n")):
            mutated = dict(base, **{path: data})
            self.assertNotEqual(digest, uu.execution_fingerprint(mutated)["digest"], path)
        grants = dict(base, **{"floe.json": floe_json("x", "1.0.0", runtime="remote",
                                                      caps=["execution.remote"],
                                                      tools=["exec.shell"])})
        self.assertNotEqual(digest, uu.execution_fingerprint(grants)["digest"])

    def test_execution_fingerprint_excludes_narrow_prose(self):
        base = self.base_files()
        prose = dict(base, **{"SKILL.md": skill_md("x", body="Different prose.\n"),
                              "references/guide.md": b"# Guide\ndifferent prose\n"})
        self.assertEqual(uu.execution_fingerprint(base)["digest"],
                         uu.execution_fingerprint(prose)["digest"])

    def test_execution_fingerprint_denies_by_default(self):
        base = self.base_files()
        added = dict(base, **{"references/data.json": b"{}"})
        self.assertNotEqual(uu.execution_fingerprint(base)["digest"],
                            uu.execution_fingerprint(added)["digest"])
        engine = dict(base, **{"references/engine-data/reference/x.md": b"prompt"})
        self.assertNotEqual(uu.execution_fingerprint(base)["digest"],
                            uu.execution_fingerprint(engine)["digest"])

    def test_instruction_code_fingerprint_prose_vs_commands(self):
        prose_a = b"# T\n\nRun the tool now.\n\n```bash\npython3 scripts/run.py --flag\n```\n"
        prose_b = b"# T\n\nRun the tool later, please.\n\n```bash\npython3 scripts/run.py --flag\n```\n"
        cmd_c = b"# T\n\nRun the tool now.\n\n```bash\npython3 scripts/run.py --other\n```\n"
        inline_d = b"# T\n\nRun the tool now.\n\n```bash\npython3 scripts/run.py --flag\n```\nUse `--verbose` always.\n"
        fa = {"SKILL.md": prose_a}
        self.assertEqual(uu.instruction_code_fingerprint(fa)["digest"],
                         uu.instruction_code_fingerprint({"SKILL.md": prose_b})["digest"])
        self.assertNotEqual(uu.instruction_code_fingerprint(fa)["digest"],
                            uu.instruction_code_fingerprint({"SKILL.md": cmd_c})["digest"])
        self.assertNotEqual(uu.instruction_code_fingerprint(fa)["digest"],
                            uu.instruction_code_fingerprint({"SKILL.md": inline_d})["digest"])

    def test_instruction_fingerprint_ignores_provenance_mechanics(self):
        files = {"SKILL.md": b"# s\nbody\n",
                 "references/PROVENANCE.md": provenance_md("x", FIXTURE_REPO, PIN, "p")}
        before = uu.instruction_code_fingerprint(files)["digest"]
        updated, problem = uu.update_provenance(files["references/PROVENANCE.md"], PIN, HEAD,
                                                TODAY, {"SKILL.md": b"# s\nbody\n"})
        self.assertIsNone(problem)
        after = uu.instruction_code_fingerprint(dict(files, **{"references/PROVENANCE.md":
                                                               updated}))["digest"]
        self.assertEqual(before, after)


class TestProvenanceAndManifest(unittest.TestCase):
    def test_provenance_mechanical_update(self):
        files = {"SKILL.md": b"a", "floe.json": b"b"}
        original = provenance_md("x", FIXTURE_REPO, PIN, "skills/x", files)
        updated, problem = uu.update_provenance(original, PIN, HEAD, TODAY,
                                                {"SKILL.md": b"a2", "floe.json": b"b"})
        self.assertIsNone(problem)
        text = updated.decode("utf-8")
        self.assertIn(f"`{HEAD}`", text)
        self.assertNotIn(f"- Pinned commit: `{PIN}`", text)
        self.assertIn("Upstream update: re-pinned", text)
        inventory = [line for line in text.splitlines() if line.startswith("- `")]
        self.assertEqual(inventory[0], f"- `SKILL.md` sha256 `{hubcore.sha256_hex(b'a2')}`")
        self.assertEqual(len(inventory), 2)  # PROVENANCE.md self-hash omitted

    def test_provenance_tree_shas_replaced_only_when_present(self):
        repo_tree_old, repo_tree_new = "5" * 40, "6" * 40
        sub_tree_old, sub_tree_new = "7" * 40, "8" * 40
        files = {"SKILL.md": b"a"}
        base = provenance_md("x", FIXTURE_REPO, PIN, "skills/x", files).decode("utf-8")
        enriched = base.replace(f"`{PIN}` (verified at fetch)",
                                f"`{PIN}` (tree `{repo_tree_old}`; subtree `{sub_tree_old}`)")
        updated, problem = uu.update_provenance(
            enriched.encode("utf-8"), PIN, HEAD, TODAY, files,
            old_repo_tree=repo_tree_old, new_repo_tree=repo_tree_new,
            old_subtree_tree=sub_tree_old, new_subtree_tree=sub_tree_new)
        self.assertIsNone(problem)
        text = updated.decode("utf-8")
        self.assertIn(repo_tree_new, text)
        self.assertIn(sub_tree_new, text)
        self.assertNotIn(repo_tree_old, text)
        # absent tree shas are tolerated (formats vary across real provenance files)
        plain = provenance_md("x", FIXTURE_REPO, PIN, "skills/x", files)
        updated2, problem2 = uu.update_provenance(plain, PIN, HEAD, TODAY, files,
                                                  old_repo_tree=repo_tree_old,
                                                  new_repo_tree=repo_tree_new)
        self.assertIsNone(problem2)
        self.assertIn(f"`{HEAD}`", updated2.decode("utf-8"))

    def test_provenance_unexpected_shape_holds(self):
        updated, problem = uu.update_provenance(b"# Provenance\n\nNo pin line here.\n",
                                                PIN, HEAD, TODAY, {})
        self.assertIsNone(updated)
        self.assertIn("Pinned commit", problem)

    def test_manifest_version_bump_preserves_format(self):
        original = floe_json("x", "1.0.0")
        bumped, problem = uu.bump_manifest_version(original, "1.0.1")
        self.assertIsNone(problem)
        self.assertEqual(json.loads(bumped)["version"], "1.0.1")
        self.assertEqual(bumped, hubcore.encoded(json.loads(bumped)))
        nl_variant = original + b"\n"
        bumped_nl, problem = uu.bump_manifest_version(nl_variant, "1.0.1")
        self.assertIsNone(problem)
        self.assertTrue(bumped_nl.endswith(b"\n"))
        weird = b'{\n  "version": "1.0.0"\n}'
        bumped_weird, problem = uu.bump_manifest_version(weird, "1.0.1")
        self.assertIsNone(bumped_weird)
        self.assertIn("round-trip", problem)


class TestShowcaseEvidence(unittest.TestCase):
    def build(self):
        current = b"# Title\n\ncited line one\ncited line two\n\ntrailing prose\n"
        candidate = b"# Title\n\nnew intro paragraph\n\ncited line one\ncited line two\n\ntrailing prose\n"
        links = links_doc_for("x", "SKILL.md", hubcore.sha256_hex(current), 3, 4)
        return current, candidate, links

    def test_unique_surviving_block_relocates(self):
        current, candidate, links = self.build()
        result = uu.maintain_showcase_evidence(links, "x", {"SKILL.md": current},
                                               {"SKILL.md": candidate})
        self.assertEqual(result["held"], [])
        proposed = [r for r in result["records"] if r["state"] == "proposed"]
        self.assertEqual(len(proposed), 1)
        self.assertEqual(proposed[0]["proposed"]["lineStart"], 5)
        self.assertEqual(proposed[0]["proposed"]["lineEnd"], 6)
        self.assertEqual(proposed[0]["proposed"]["sha256"], hubcore.sha256_hex(candidate))

    def test_ambiguous_or_missing_block_holds_editorial(self):
        current = b"a\nb\n"
        candidate = b"b\nx\nb\n"  # block 'b' occurs twice
        links = links_doc_for("x", "SKILL.md", hubcore.sha256_hex(current), 2, 2)
        result = uu.maintain_showcase_evidence(links, "x", {"SKILL.md": current},
                                               {"SKILL.md": candidate})
        self.assertEqual(len(result["held"]), 1)
        self.assertIn("needs-editorial-review", result["held"][0]["reason"])
        gone = b"zz\n"
        links2 = links_doc_for("x", "SKILL.md", hubcore.sha256_hex(current), 1, 1)
        result2 = uu.maintain_showcase_evidence(links2, "x", {"SKILL.md": current},
                                                {"SKILL.md": gone})
        self.assertEqual(len(result2["held"]), 1)

    def test_unchanged_file_maintained(self):
        data = b"same\n"
        links = links_doc_for("x", "SKILL.md", hubcore.sha256_hex(data), 1, 1)
        result = uu.maintain_showcase_evidence(links, "x", {"SKILL.md": data},
                                               {"SKILL.md": data})
        self.assertEqual(result["records"][0]["state"], "maintained")
        self.assertEqual(result["held"], [])


class TestVersions(unittest.TestCase):
    def test_propose_avoids_used_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            for version in ("1.0.0", "1.0.1"):
                (root / "packages" / "x" / version).mkdir(parents=True)
            (root / "catalog").mkdir()
            (root / "catalog" / "publication-ledger.json").write_text(json.dumps(
                {"publications": [{"offers": [{"id": "x", "version": "1.0.2"}]}]}))
            used = uu.used_versions(root, "x", {"versionTarget": "1.0.0"})
            self.assertEqual(uu.propose_version("1.0.0", used), "1.0.3")
            self.assertEqual(uu.propose_version("1.0.0", {"1.0.1"}), "1.0.2")


# ---------------------------------------------------------------------------
# snapshot safety gates
# ---------------------------------------------------------------------------

class TestSnapshotSafety(unittest.TestCase):
    def test_unsafe_entries_flagged_and_not_carried(self):
        repos = {FIXTURE_REPO: {
            "head": (HEAD, "refs/heads/main"), "tags": {},
            "commits": {HEAD: commit(
                {"skills/x/SKILL.md": b"s",
                 "skills/x/link.md": b"target",
                 "skills/x/big.md": b"y" * (hubcore.MAX_FILE_BYTES + 1),
                 "skills/x/native.so.md": b"\x7fELF" + b"rest",
                 "skills/x/sub/mod": b"gitlink"},
                modes={"skills/x/link.md": "120000", "skills/x/sub/mod": "160000"})}}}
        source = fixture_source(repos)
        snapshot, problems = uu.snapshot_upstream_tree(source, FIXTURE_REPO, HEAD, "skills/x")
        self.assertTrue(problems)
        self.assertIn("symlink", snapshot["link.md"]["problem"])
        self.assertIn("exceeds", snapshot["big.md"]["problem"])
        self.assertIn("native payload", snapshot["native.so.md"]["problem"])
        self.assertIn("non-blob", snapshot["sub/mod"]["problem"])
        self.assertIsNone(snapshot["SKILL.md"]["problem"])
        self.assertEqual(snapshot["SKILL.md"]["data"], b"s")


# ---------------------------------------------------------------------------
# plan_skill tiers, gates and holds (unit level, injected trees)
# ---------------------------------------------------------------------------

class PlanSkillHarness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.skill_cfg = {"relocations": [], "fileMappings": [
            {"upstream": "LICENSE.txt", "local": "references/licenses/UPSTREAM-LICENSE.txt",
             "kind": "license"}], "excludedUpstream": ["scripts/"]}

    def published(self, files, version="1.0.0"):
        archive = self.root / "packages" / "fixture-guide" / version / "fixture-guide.zip"
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(hubcore.make_zip(files))

    def plan(self, entry, old_files, new_files, local_files, published_files, *,
             root_license_changed=False, prior_proof=None, new_modes=None,
             skill_id="fixture-guide", cfg=None):
        self.published(published_files, entry["versionTarget"])
        return uu.plan_skill(
            skill_id, entry, cfg or self.skill_cfg,
            snap(old_files), snap(new_files, modes=new_modes or {}),
            local_files, published_files, entry["versionTarget"], self.root, TODAY, None,
            root_license_changed=root_license_changed, prior_proof=prior_proof,
            repo_url=FIXTURE_REPO, head_commit=HEAD,
            pinned_repo_tree=None, head_repo_tree=None)


class TestPlanSkillGuideOnly(PlanSkillHarness):
    def entry(self):
        return make_entry("fixture-guide", subpath="skills/fixture-guide")

    def trees(self, new_skill_body="new upstream body line\n"):
        local = guide_local_tree("fixture-guide", "1.0.0",
                                 subpath="skills/fixture-guide")
        old = {"SKILL.md": skill_md("fixture-guide", body="old body line\n"),
               "references/guide.md": b"# Guide\n\nupstream guide line\n",
               "LICENSE.txt": b"MIT fixture license\n"}
        new = {"SKILL.md": skill_md("fixture-guide", body=new_skill_body),
               "references/guide.md": b"# Guide\n\nupstream guide line\n",
               "LICENSE.txt": b"MIT fixture license\n"}
        return old, new, local

    def test_eligible_tier1_verbatim_carry_and_version_bump(self):
        entry = self.entry()
        old, new, local = self.trees()
        plan = self.plan(entry, old, new, local, dict(local))
        self.assertEqual(plan["status"], "eligible-tier1", plan["reasons"])
        self.assertEqual(plan["tier"], 1)
        self.assertEqual(plan["proposedVersion"], "1.0.1")
        self.assertEqual(plan["registryDelta"]["versionTarget"], "1.0.1")
        self.assertEqual(plan["registryDelta"]["upstream"]["commit"], HEAD)
        self.assertEqual(plan["pinAdvance"], {"from": PIN, "to": HEAD})
        carry = [a for a in plan["fileActions"] if a["action"] == "carry-new"]
        self.assertEqual([a["local"] for a in carry], ["SKILL.md"])
        tree = plan["_candidateTree"]
        self.assertEqual(tree["SKILL.md"], new["SKILL.md"])
        self.assertEqual(json.loads(tree["floe.json"])["version"], "1.0.1")
        self.assertIn("Upstream update: re-pinned", tree["references/PROVENANCE.md"].decode())
        record = plan["proposedReview"]
        hubcore.validate_review(record)
        self.assertEqual(record["reviewStage"], "static-content-reviewed")
        self.assertEqual(record["execution"], {"os": None, "arch": "n/a", "evidence": "unproven"})
        self.assertEqual(record["reviewer"], uu.MACHINE_REVIEWER)
        self.assertEqual(record["version"], "1.0.1")
        self.assertEqual(record["contentDigest"], plan["candidate"]["contentDigest"])

    def test_merge_preserves_local_adaptation(self):
        entry = self.entry()
        old, new, local = self.trees()
        # local adapted guide.md elsewhere than the upstream change
        old["references/guide.md"] = b"# Guide\n\nupstream para one\n\nupstream para two\n"
        new["references/guide.md"] = b"# Guide\n\nUPSTREAM CHANGED one\n\nupstream para two\n"
        local["references/guide.md"] = (b"# Guide\n\nupstream para one\n\nupstream para two\n"
                                        b"\nFloe adaptation note.\n")
        plan = self.plan(entry, old, new, local, dict(local))
        merged = plan["_candidateTree"]["references/guide.md"]
        self.assertIn(b"UPSTREAM CHANGED one", merged)
        self.assertIn(b"Floe adaptation note.", merged)
        self.assertEqual(plan["status"], "eligible-tier1", plan["reasons"])

    def test_no_change_when_only_excluded_paths_drift(self):
        entry = self.entry()
        old, new, local = self.trees(new_skill_body="old body line\n")
        old["scripts/helper.py"] = b"print(1)\n"
        new["scripts/helper.py"] = b"print(2)\n"
        plan = self.plan(entry, old, new, local, dict(local))
        self.assertEqual(plan["status"], "no-change")
        self.assertFalse(plan["contentChanged"])
        self.assertEqual(plan["pinAdvance"], {"from": PIN, "to": HEAD})
        self.assertNotIn("proposedVersion", plan)

    def test_conflict_holds_with_actionable_reason_and_no_candidate(self):
        entry = self.entry()
        old, new, local = self.trees()
        old["references/guide.md"] = b"# Guide\n\nshared line\n"
        new["references/guide.md"] = b"# Guide\n\nupstream rewrite\n"
        local["references/guide.md"] = b"# Guide\n\nlocal rewrite\n"
        plan = self.plan(entry, old, new, local, dict(local))
        self.assertEqual(plan["status"], "held-conflict")
        reason = plan["reasons"][0]
        self.assertEqual(reason["code"], "held-conflict")
        self.assertIn("references/guide.md", reason["detail"])
        self.assertIn("resolve", reason["repair"].lower())
        self.assertNotIn("_candidateTree", plan)

    def test_license_drift_holds(self):
        entry = self.entry()
        old, new, local = self.trees()
        new["LICENSE.txt"] = b"GPL-3.0 now\n"
        plan = self.plan(entry, old, new, local, dict(local))
        self.assertEqual(plan["status"], "held-license-drift")
        self.assertEqual(plan["reasons"][0]["code"], "held-license-drift")

    def test_repository_root_license_drift_holds(self):
        entry = self.entry()
        old, new, local = self.trees(new_skill_body="old body line\n")
        plan = self.plan(entry, old, new, local, dict(local), root_license_changed=True)
        self.assertEqual(plan["reasons"][0]["code"], "held-license-drift")

    def test_unsafe_new_upstream_file_holds(self):
        entry = self.entry()
        old, new, local = self.trees()
        new["references/evil.so.md"] = b"\x7fELF binary payload"
        plan = self.plan(entry, old, new, local, dict(local))
        self.assertEqual(plan["status"], "held-unsafe")

    def test_symlink_carry_change_holds_unsafe(self):
        entry = self.entry()
        old, new, local = self.trees()
        new["references/guide.md"] = b"target"
        plan = self.plan(entry, old, new, local, dict(local),
                         new_modes={"references/guide.md": "120000"})
        self.assertEqual(plan["status"], "held-unsafe")

    def test_permission_drift_holds_even_with_mapping(self):
        entry = self.entry()
        old, new, local = self.trees()
        cfg = {"relocations": [], "fileMappings": [
            {"upstream": "LICENSE.txt", "local": "references/licenses/UPSTREAM-LICENSE.txt",
             "kind": "license"},
            {"upstream": "manifest.json", "local": "floe.json", "kind": "doc"}],
            "excludedUpstream": []}
        old["manifest.json"] = local["floe.json"]
        new["manifest.json"] = floe_json("fixture-guide", "1.0.0", runtime="remote",
                                         caps=["execution.remote"], tools=["exec.shell"])
        plan = self.plan(entry, old, new, local, dict(local), cfg=cfg)
        codes = {r["code"] for r in plan["reasons"]}
        self.assertIn("held-permission-drift", codes)

    def test_dependency_drift_holds(self):
        entry = self.entry()
        old, new, local = self.trees()
        cfg = {"relocations": [], "fileMappings": [
            {"upstream": "LICENSE.txt", "local": "references/licenses/UPSTREAM-LICENSE.txt",
             "kind": "license"},
            {"upstream": "requirements.txt", "local": "references/requirements.lock.txt",
             "kind": "doc"}], "excludedUpstream": []}
        local["references/requirements.lock.txt"] = b"pkg==1.0\n"
        old["requirements.txt"] = b"pkg==1.0\n"
        new["requirements.txt"] = b"pkg==2.0\n"
        plan = self.plan(entry, old, new, local, dict(local), cfg=cfg)
        codes = {r["code"] for r in plan["reasons"]}
        self.assertIn("held-dependency-drift", codes)

    def test_new_undeclared_root_file_holds_adaptation(self):
        entry = self.entry()
        old, new, local = self.trees()
        new["CHANGELOG.md"] = b"changes\n"
        plan = self.plan(entry, old, new, local, dict(local))
        self.assertEqual(plan["status"], "held-adaptation-required")

    def test_upstream_removal_of_adapted_file_holds(self):
        entry = self.entry()
        old, new, local = self.trees()
        del new["references/guide.md"]
        plan = self.plan(entry, old, new, local, dict(local))
        codes = {r["code"] for r in plan["reasons"]}
        self.assertIn("held-conflict", codes)

    def test_showcase_evidence_ambiguous_hold(self):
        entry = self.entry()
        old, new, local = self.trees()
        current_skill = local["SKILL.md"]
        links = links_doc_for("fixture-guide", "SKILL.md",
                              hubcore.sha256_hex(current_skill), 5, 6)
        self.published(dict(local))
        plan = uu.plan_skill("fixture-guide", entry, self.skill_cfg, snap(old), snap(new),
                             local, dict(local), "1.0.0", self.root, TODAY, links,
                             repo_url=FIXTURE_REPO, head_commit=HEAD)
        self.assertEqual(plan["status"], "held-editorial-review")

class TestPlanSkillScripted(PlanSkillHarness):
    def entry(self):
        return make_entry("fixture-script", runtime="remote", subpath="skills/fixture-script")

    def trees(self):
        local = {
            "SKILL.md": skill_md("fixture-script",
                                 body="Run:\n\n```bash\npython3 scripts/run.py\n```\n"),
            "floe.json": floe_json("fixture-script", "1.0.0", runtime="remote",
                                   caps=["execution.remote"], tools=["exec.shell"]),
            "scripts/run.py": b"print('guest ok')\n",
            "references/guide.md": b"# Guide\nprose\n",
            "references/licenses/UPSTREAM-LICENSE.txt": b"MIT\n",
        }
        local["references/PROVENANCE.md"] = provenance_md(
            "fixture-script", FIXTURE_REPO, PIN, "skills/fixture-script", local)
        old = {"SKILL.md": local["SKILL.md"], "scripts/run.py": local["scripts/run.py"],
               "references/guide.md": b"# Guide\nprose\n", "LICENSE.txt": b"MIT\n"}
        return old, local

    def prior_proof(self, published_files, version="1.0.0"):
        archive = self.root / "packages" / "fixture-script" / version / "fixture-script.zip"
        return {"available": True, "reasons": [],
                "reviewSha256": "f" * 64, "publicationPin": "e" * 40,
                "keyID": hubcore.PRODUCTION_KEY_ID,
                "reviewStage": "guest-execution-qualified",
                "execution": {"os": "linux", "arch": "riscv64", "evidence": "guest-verified"},
                "priorContentDigest": hubcore.content_digest(published_files),
                "priorVersion": version}

    def plan_scripted(self, new_files, local, old, prior_proof=None, cfg=None):
        skill_cfg = cfg or {"relocations": [], "fileMappings": [
            {"upstream": "LICENSE.txt", "local": "references/licenses/UPSTREAM-LICENSE.txt",
             "kind": "license"}], "excludedUpstream": []}
        self.published(local, "1.0.0")
        archive = self.root / "packages" / "fixture-script" / "1.0.0" / "fixture-script.zip"
        if prior_proof is None:
            prior_proof = self.prior_proof(local)
        entry = self.entry()
        return uu.plan_skill("fixture-script", entry, skill_cfg, snap(old), snap(new_files),
                             local, dict(local), "1.0.0", self.root, TODAY, None,
                             prior_proof=prior_proof, repo_url=FIXTURE_REPO, head_commit=HEAD)

    def test_docs_only_change_reuses_prior_proof(self):
        old, local = self.trees()
        new = dict(old)
        new["references/guide.md"] = b"# Guide\nprose improved wording\n"
        plan = self.plan_scripted(new, local, old)
        self.assertEqual(plan["status"], "eligible-tier2", plan["reasons"])
        self.assertEqual(plan["tier"], 2)
        self.assertTrue(plan["executionFingerprint"]["equal"])
        self.assertTrue(plan["instructionCodeFingerprint"]["equal"])
        record = plan["proposedReview"]
        hubcore.validate_review(record)
        self.assertEqual(record["reviewStage"], "guest-execution-qualified")
        self.assertEqual(record["execution"],
                         {"os": "linux", "arch": "riscv64", "evidence": "guest-verified"})
        self.assertIn("NO new execution", record["notes"]["en"])

    def test_command_change_inside_skill_md_holds(self):
        old, local = self.trees()
        new = dict(old)
        new["SKILL.md"] = skill_md("fixture-script",
                                   body="Run:\n\n```bash\npython3 scripts/run.py --force\n```\n")
        plan = self.plan_scripted(new, local, old)
        self.assertEqual(plan["status"], "held-instruction-code-changed")
        self.assertTrue(plan["executionFingerprint"]["equal"])
        self.assertFalse(plan["instructionCodeFingerprint"]["equal"])

    def test_script_byte_change_holds_runtime(self):
        old, local = self.trees()
        new = dict(old)
        new["scripts/run.py"] = b"print('changed guest behaviour')\n"
        plan = self.plan_scripted(new, local, old)
        self.assertEqual(plan["status"], "held-runtime-changed")
        self.assertFalse(plan["executionFingerprint"]["equal"])
        self.assertIn("scripts/run.py", plan["executionFingerprint"]["changedPaths"])

    def test_missing_prior_proof_holds(self):
        old, local = self.trees()
        new = dict(old)
        new["references/guide.md"] = b"# Guide\nprose improved wording\n"
        plan = self.plan_scripted(new, local, old,
                                  prior_proof={"available": False,
                                               "reasons": ["record missing"]})
        self.assertEqual(plan["status"], "held-prior-proof-unavailable")


class TestPriorProofLoaderFailsClosed(unittest.TestCase):
    def test_missing_records_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            facts = uu.load_prior_proof(pathlib.Path(tmp), "x", "1.0.0", "a" * 64, "b" * 64)
            self.assertFalse(facts["available"])
            self.assertTrue(facts["reasons"])


# ---------------------------------------------------------------------------
# pins advancement (fallback mirror + real helper consumption)
# ---------------------------------------------------------------------------

def pins_doc(default_pin=PIN, overrides=None):
    doc = {"reviewBaselineDate": "2026-10-26",
           "repositories": {"fixture-owner/fixture-skills": default_pin,
                            "watch-owner/watch-repo": OTHER}}
    if overrides:
        doc["skillOverrides"] = overrides
    return doc


class TestPinAdvancement(unittest.TestCase):
    def setUp(self):
        self._saved = uu.load_pins_helper
        uu.load_pins_helper = lambda: (None, "test-mirror")
        self.addCleanup(lambda: setattr(uu, "load_pins_helper", self._saved))

    def registries(self, guide_pin, held_pin):
        old = make_registry([make_entry("fixture-guide", pin=PIN),
                             make_entry("fixture-held", pin=PIN, plan=2)])
        guide = make_entry("fixture-guide", pin=guide_pin)
        held = make_entry("fixture-held", pin=held_pin, plan=2)
        new = make_registry([guide, held])
        return old, new

    def test_mixed_repository_writes_override_and_keeps_default(self):
        old, new = self.registries(HEAD, PIN)
        result = uu.fallback_advance_pin_document(pins_doc(), old, new, ["fixture-guide"],
                                                  TODAY)
        self.assertEqual(result["repositories"]["fixture-owner/fixture-skills"], PIN)
        self.assertEqual(result["skillOverrides"]["fixture-guide"],
                         {"repository": "fixture-owner/fixture-skills", "commit": HEAD})
        self.assertNotIn("fixture-held", result.get("skillOverrides", {}))
        self.assertEqual(result["repositories"]["watch-owner/watch-repo"], OTHER)

    def test_uniform_repository_compacts_default(self):
        old, new = self.registries(HEAD, HEAD)
        prior = pins_doc(default_pin=PIN, overrides={"fixture-guide": {
            "repository": "fixture-owner/fixture-skills", "commit": HEAD}})
        result = uu.fallback_advance_pin_document(prior, old, new,
                                                  ["fixture-guide", "fixture-held"], TODAY)
        self.assertEqual(result["repositories"]["fixture-owner/fixture-skills"], HEAD)
        self.assertNotIn("skillOverrides", result)

    def test_unaccepted_pin_move_refused(self):
        old, new = self.registries(HEAD, PIN)
        with self.assertRaises(uu.UpstreamError):
            uu.fallback_advance_pin_document(pins_doc(), old, new, [], TODAY)

    def test_empty_accepted_preserves_prior_bytes_exactly(self):
        prior_bytes = (json.dumps(pins_doc(), ensure_ascii=False, indent=2) + "\n").encode()
        old = make_registry([make_entry("fixture-guide", pin=PIN)])
        result_bytes, label = uu.advance_pins(prior_bytes, old, copy.deepcopy(old), [], TODAY)
        self.assertEqual(result_bytes, prior_bytes)
        self.assertIn("preserved", label)


# ---------------------------------------------------------------------------
# run_check / run_plan / run_stage against fixture upstreams (offline)
# ---------------------------------------------------------------------------

def build_fixture_world(tmp):
    """Two tracked guide skills + engine + watch-only, all fixture-hosted."""
    root = pathlib.Path(tmp) / "hub"
    root.mkdir(parents=True)
    guide_entry = make_entry("fixture-guide", subpath="skills/fixture-guide", plan=1)
    held_entry = make_entry("fixture-held", subpath="skills/fixture-held", plan=2)
    engine_entry = make_entry("fixture-engine-skill", pin=PIN, repo_url=FIXTURE_ENGINE_REPO,
                              subpath="plugin/skill", plan=3, deep=True)
    watch_entry = make_entry("fixture-watch", plan=4, upstream=False, source="F")
    registry = make_registry([guide_entry, held_entry, engine_entry, watch_entry])
    guide_local = guide_local_tree("fixture-guide", "1.0.0",
                                   subpath="skills/fixture-guide")
    held_local = guide_local_tree("fixture-held", "1.0.0", subpath="skills/fixture-held")
    skills_cfg = {
        "fixture-guide": {"relocations": [], "fileMappings": [
            {"upstream": "LICENSE.txt", "local": "references/licenses/UPSTREAM-LICENSE.txt",
             "kind": "license"}], "excludedUpstream": ["scripts/"]},
        "fixture-held": {"relocations": [], "fileMappings": [
            {"upstream": "LICENSE.txt", "local": "references/licenses/UPSTREAM-LICENSE.txt",
             "kind": "license"}], "excludedUpstream": []},
    }
    policy = make_policy(
        tracked=["fixture-guide", "fixture-held"],
        skills_cfg=skills_cfg,
        repositories={
            FIXTURE_REPO: {"role": "corpus", "trackedRef": "HEAD", "rootLicense": "LICENSE"},
            FIXTURE_ENGINE_REPO: {"role": "engine", "trackedRef": "HEAD", "rootLicense": None,
                                  "engineReleaseTagPattern": "engine-v*"},
            FIXTURE_WATCH_REPO: {"role": "watch-only", "trackedRef": "HEAD",
                                 "rootLicense": None},
        },
        engine={"fixture-engine": {
            "skillId": "fixture-engine-skill", "repository": FIXTURE_ENGINE_REPO,
            "corpusPath": "plugin/skill", "engineLock": "engines/fixture/ENGINE-LOCK.json",
            "stableReleaseTagPattern": "engine-v<semver>", "genericMergeProhibited": True,
            "route": "fixture engine pipeline", "ownedPaths": ["sources/fixture-engine-skill"]}},
        watch=[{"id": "fixture-watch", "originalRepository": FIXTURE_WATCH_REPO,
                "originalPath": "skills/original", "reason": "fixture license watch"}],
    )
    pins = {"reviewBaselineDate": "2026-10-26",
            "repositories": {"fixture-owner/fixture-skills": PIN,
                             "fixture-owner/fixture-engine": PIN,
                             "watch-owner/watch-repo": OTHER}}

    # upstream fixture content
    guide_old = {"skills/fixture-guide/SKILL.md": skill_md("fixture-guide",
                                                           body="old body line\n"),
                 "skills/fixture-guide/references/guide.md": b"# Guide\n\nupstream line\n",
                 "skills/fixture-guide/LICENSE.txt": b"MIT fixture license\n",
                 "skills/fixture-guide/scripts/helper.py": b"print(1)\n",
                 "skills/UNSELECTED/secret.md": b"never imported\n",
                 "LICENSE": b"repo MIT license\n"}
    guide_new = dict(guide_old)
    guide_new["skills/fixture-guide/SKILL.md"] = skill_md(
        "fixture-guide", body="intro added\n\nold body line\n")
    guide_new["skills/fixture-guide/scripts/helper.py"] = b"print(2)\n"  # excluded drift
    guide_new["LICENSE"] = b"repo MIT license\n"
    held_old = {"skills/fixture-held/SKILL.md": skill_md("fixture-held", body="held body\n"),
                "skills/fixture-held/references/guide.md": b"# Guide\n\nshared line\n",
                "skills/fixture-held/LICENSE.txt": b"MIT fixture license\n",
                "LICENSE": b"repo MIT license\n"}
    held_new = dict(held_old)
    held_new["skills/fixture-held/references/guide.md"] = b"# Guide\n\nupstream rewrite\n"
    held_new["LICENSE"] = b"repo MIT license\n"
    # held skill's LOCAL guide.md diverges in the same region -> conflict
    held_local["references/guide.md"] = b"# Guide\n\nlocal rewrite\n"

    engine_pin_files = {"plugin/skill/SKILL.md": b"engine corpus old\n"}
    engine_head_files = {"plugin/skill/SKILL.md": b"engine corpus new\n"}
    watch_pin = {"skills/original/SKILL.md": b"original\n"}
    watch_head = {"skills/original/SKILL.md": b"original\n",
                  "skills/original/LICENSE": b"MIT appeared\n"}

    source = fixture_source({
        FIXTURE_REPO: {"head": (HEAD, "refs/heads/main"), "tags": {},
                       "commits": {PIN: commit(guide_old | held_old),
                                   HEAD: commit(guide_new | held_new)}},
        FIXTURE_ENGINE_REPO: {"head": (HEAD, "refs/heads/main"),
                              "tags": {"engine-v0.2.0": HEAD, "engine-v0.1.0": PIN},
                              "commits": {PIN: commit(engine_pin_files),
                                          HEAD: commit(engine_head_files)}},
        FIXTURE_WATCH_REPO: {"head": (HEAD, "refs/heads/main"), "tags": {},
                             "commits": {OTHER: commit(watch_pin), HEAD: commit(watch_head)}},
    })
    links = links_doc_for("fixture-guide", "SKILL.md",
                          hubcore.sha256_hex(guide_local["SKILL.md"]), 6, 6)
    write_hub_root(root, registry, policy, pins,
                   sources={"fixture-guide": guide_local, "fixture-held": held_local},
                   packages={"fixture-guide": {"1.0.0": guide_local},
                             "fixture-held": {"1.0.0": held_local}},
                   links=links,
                   engine_locks={"engines/fixture/ENGINE-LOCK.json":
                                 {"upstream": {"engineVersion": "0.1.0"}}})
    return root, source


class TestRunCheckPlanStageFixtures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root, self.source = build_fixture_world(self.tmp.name)
        self.inputs = uu.load_inputs(self.root, expect_counts=(4, 0, 4, 1))

    def snapshot_live_tree(self):
        paths = {}
        for rel in ("catalog/skills.json", "docs/UPSTREAM-PINS.json", "showcase/links.json"):
            paths[rel] = (self.root / rel).read_bytes()
        for path in sorted((self.root / "sources").rglob("*")):
            if path.is_file():
                paths[str(path.relative_to(self.root))] = path.read_bytes()
        for path in sorted((self.root / "packages").rglob("*")):
            if path.is_file():
                paths[str(path.relative_to(self.root))] = path.read_bytes()
        return paths

    def test_check_coverage_and_states(self):
        report = uu.run_check(self.root, self.inputs, self.source, TODAY)
        self.assertEqual(report["counts"]["reportedEntries"], 4)
        by_id = {s["id"]: s for s in report["skills"]}
        self.assertEqual(by_id["fixture-guide"]["state"], "drifted")
        self.assertEqual(by_id["fixture-held"]["state"], "drifted")
        self.assertEqual(by_id["fixture-engine-skill"]["mode"], "engine-managed")
        self.assertEqual(by_id["fixture-engine-skill"]["state"], "drifted")
        self.assertEqual(by_id["fixture-watch"]["mode"], "watch-only")
        engine = report["engineTracking"][0]
        self.assertTrue(engine["corpusDrift"])
        self.assertEqual(engine["latestStableEngineTag"], "engine-v0.2.0")
        self.assertTrue(engine["newerStableEngineRelease"])
        self.assertFalse(engine["candidateConstructed"])
        watch = report["watchOnly"][0]
        self.assertTrue(watch["licenseSignal"]["licenseAppeared"])
        self.assertTrue(watch["copyProhibited"])
        self.assertEqual(report["errors"], [])

    def test_check_unrelated_commit_never_bumps(self):
        # repository head where ONLY files outside every tracked subpath moved
        source = self.source
        repo = source.repos[FIXTURE_REPO]
        quiet_head = "4" * 40
        base = dict(repo["commits"][PIN]["files"])
        quiet = dict(base)
        quiet["skills/UNSELECTED/other.md"] = b"unrelated\n"
        quiet["README.md"] = b"unrelated repo-level commit\n"
        repo["commits"][quiet_head] = commit(quiet)
        repo["head"] = (quiet_head, "refs/heads/main")
        report = uu.run_check(self.root, self.inputs, source, TODAY)
        by_id = {s["id"]: s for s in report["skills"]}
        self.assertEqual(by_id["fixture-guide"]["state"], "up-to-date")
        self.assertIn("unrelated", by_id["fixture-guide"]["detail"])
        plan = uu.run_plan(self.root, self.inputs, source, TODAY)
        rows = {s["id"]: s for s in plan["skills"]}
        self.assertEqual(rows["fixture-guide"]["status"], "no-change")
        self.assertFalse(rows["fixture-guide"]["contentChanged"])
        self.assertEqual(plan["acceptance"]["eligibleIds"], [])
        self.assertEqual(plan["acceptance"]["acceptedIds"], [])

    def test_plan_and_stage_end_to_end(self):
        before = self.snapshot_live_tree()
        plan = uu.run_plan(self.root, self.inputs, self.source, TODAY)
        rows = {s["id"]: s for s in plan["skills"]}
        self.assertEqual(rows["fixture-guide"]["status"], "eligible-tier1",
                         rows["fixture-guide"]["reasons"])
        self.assertEqual(rows["fixture-held"]["status"], "held-conflict")
        self.assertEqual(rows["fixture-engine-skill"]["status"], "held-engine-managed")
        self.assertEqual(plan["acceptance"]["eligibleIds"], ["fixture-guide"])
        self.assertEqual(plan["acceptance"]["acceptedIds"], ["fixture-guide"])
        self.assertEqual(plan["counts"]["held"], 2)

        stage_root = pathlib.Path(self.tmp.name) / "stage"
        manifest = uu.run_stage(self.root, self.inputs, self.source, plan, stage_root)
        self.assertEqual(manifest["counts"]["staged"], 1)
        self.assertEqual(manifest["counts"]["held"], 2)
        facts = manifest["candidateFacts"]
        self.assertEqual(facts["changedSkillIds"], ["fixture-guide"])
        self.assertEqual(facts["bumpedVersions"],
                         {"fixture-guide": {"from": "1.0.0", "to": "1.0.1"}})
        self.assertEqual(facts["reviewStageCounts"]["static-content-reviewed"], 1)
        self.assertEqual(sorted(facts["heldSkillIds"]),
                         ["fixture-engine-skill", "fixture-held"])

        # candidate artifacts
        cand_dir = stage_root / "candidates" / "fixture-guide" / "1.0.1"
        self.assertTrue((cand_dir / "package.zip").is_file())
        candidate = json.loads((cand_dir / "candidate.json").read_bytes())
        self.assertTrue(candidate["replayVerification"]["digestMatch"])
        tree_files = {p.relative_to(cand_dir / "tree").as_posix(): p.read_bytes()
                      for p in (cand_dir / "tree").rglob("*") if p.is_file()}
        zip_bytes = (cand_dir / "package.zip").read_bytes()
        self.assertEqual(zip_bytes, hubcore.make_zip(tree_files))
        self.assertEqual(hubcore.sha256_hex(zip_bytes), candidate["candidate"]["packageSha256"])
        unpacked = hubcore.check_archive_bytes(zip_bytes)
        self.assertEqual(hubcore.content_digest(unpacked),
                         candidate["candidate"]["contentDigest"])
        self.assertIn("Upstream update: re-pinned", unpacked["references/PROVENANCE.md"].decode())
        self.assertNotIn("skills/UNSELECTED", json.dumps(candidate))

        # held record keeps the current version + old pin intact
        held = json.loads((stage_root / "held" / "fixture-held.json").read_bytes())
        self.assertEqual(held["status"], "held-conflict")
        self.assertEqual(held["pinnedCommit"], PIN)
        self.assertTrue(held["publishedVersionIntact"])

        # apply set: registry bumped for guide only; held entry keeps old pin/version
        apply_files = stage_root / "apply" / "files"
        new_registry = json.loads((apply_files / "catalog" / "skills.json").read_bytes())
        hubcore.validate_registry(new_registry, expect_counts=(4, 0, 4, 1))
        new_by_id = {e["id"]: e for e in new_registry["skills"]}
        self.assertEqual(new_by_id["fixture-guide"]["versionTarget"], "1.0.1")
        self.assertEqual(new_by_id["fixture-guide"]["upstream"]["commit"], HEAD)
        self.assertEqual(new_by_id["fixture-held"]["versionTarget"], "1.0.0")
        self.assertEqual(new_by_id["fixture-held"]["upstream"]["commit"], PIN)
        # pins: per-entry acceptance (helper or mirror) keeps the held pin exact
        new_pins = json.loads((apply_files / "docs" / "UPSTREAM-PINS.json").read_bytes())
        overrides = new_pins.get("skillOverrides") or {}
        default = new_pins["repositories"]["fixture-owner/fixture-skills"]
        if "fixture-guide" in overrides:
            self.assertEqual(default, PIN)
            self.assertEqual(overrides["fixture-guide"]["commit"], HEAD)
        else:
            self.assertEqual(default, HEAD)  # only legal if held also moved (it must not)
            self.fail("held entry pin must not advance")
        # review skeleton is honest and valid
        review_bytes = (apply_files / "reviews" / "fixture-guide" / "1.0.1.review.json"
                        ).read_bytes()
        record = json.loads(review_bytes)
        hubcore.validate_review(record)
        self.assertEqual(record["reviewer"], uu.MACHINE_REVIEWER)
        self.assertEqual(record["decision"], "approve")
        # showcase evidence maintained (cited body line survived the carry)
        new_links = json.loads((apply_files / "showcase" / "links.json").read_bytes())
        evidence = new_links["entries"]["fixture-guide"]["links"][0]["evidence"][0]
        self.assertEqual(evidence["sha256"],
                         hubcore.sha256_hex(tree_files["SKILL.md"]))
        # apply manifest matches the written files
        apply_manifest = json.loads((stage_root / "apply" / "manifest.json").read_bytes())
        for write in apply_manifest["writes"]:
            data = (apply_files / write["path"]).read_bytes()
            self.assertEqual(hubcore.sha256_hex(data), write["sha256"], write["path"])
        # LIVE tree untouched by stage
        self.assertEqual(before, self.snapshot_live_tree())

    def test_stage_refuses_replay_divergence_and_dirty_root(self):
        plan = uu.run_plan(self.root, self.inputs, self.source, TODAY)
        stage_root = pathlib.Path(self.tmp.name) / "stage2"
        stage_root.mkdir()
        (stage_root / "leftover").write_text("x")
        with self.assertRaises(uu.UpstreamError):
            uu.run_stage(self.root, self.inputs, self.source, plan, stage_root)
        # stage root inside the hub checkout is refused
        with self.assertRaises(uu.UpstreamError):
            uu.run_stage(self.root, self.inputs, self.source, plan, self.root / "inner-stage")
        # a tampered plan (different inputs digest) is refused
        tampered = copy.deepcopy(plan)
        tampered["inputs"]["registrySha256"] = "0" * 64
        clean = pathlib.Path(self.tmp.name) / "stage3"
        with self.assertRaises(uu.UpstreamError):
            uu.run_stage(self.root, self.inputs, self.source, tampered, clean)

    def test_error_repository_fails_closed_per_entry(self):
        class BrokenSource(uu.FixtureUpstreamSource):
            def resolve_ref(self, url, ref="HEAD"):
                if url == FIXTURE_REPO:
                    raise uu.UpstreamError("simulated network failure")
                return super().resolve_ref(url, ref)

        source = BrokenSource(self.source.repos)
        report = uu.run_check(self.root, self.inputs, source, TODAY)
        by_id = {s["id"]: s for s in report["skills"]}
        self.assertEqual(by_id["fixture-guide"]["state"], "error")
        self.assertTrue(report["errors"])
        plan = uu.run_plan(self.root, self.inputs, source, TODAY)
        rows = {s["id"]: s for s in plan["skills"]}
        self.assertEqual(rows["fixture-guide"]["status"], "error")


# ---------------------------------------------------------------------------
# GitUpstreamSource against a real local bare repository (offline)
# ---------------------------------------------------------------------------

class TestGitUpstreamSourceLocalRepo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(cls.tmp.name)
        work = base / "work"
        work.mkdir()

        def git(*args, cwd=work):
            proc = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True,
                                  text=True)
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr)
            return proc.stdout.strip()

        git("init", "-q", "-b", "main")
        git("config", "user.email", "fixture@example.com")
        git("config", "user.name", "fixture")
        (work / "skills" / "guide").mkdir(parents=True)
        (work / "skills" / "guide" / "SKILL.md").write_text("---\nname: guide\n---\nold\n")
        (work / "skills" / "guide" / "ref.md").write_text("reference old\n")
        (work / "skills" / "other" ).mkdir(parents=True)
        (work / "skills" / "other" / "SKILL.md").write_text("unselected skill\n")
        (work / "LICENSE").write_text("MIT\n")
        git("add", "-A")
        git("commit", "-q", "-m", "pin")
        cls.pin = git("rev-parse", "HEAD")
        (work / "unrelated.md").write_text("unrelated commit content\n")
        (work / "skills" / "guide" / "ref.md").write_text("reference new\n")
        (work / "skills" / "guide" / "link.md").symlink_to("ref.md")
        git("add", "-A")
        git("commit", "-q", "-m", "head")
        cls.head = git("rev-parse", "HEAD")
        git("tag", "engine-v1.2.3")
        bare = base / "repo.git"
        subprocess.run(["git", "clone", "-q", "--bare", str(work), str(bare)], check=True,
                       capture_output=True)
        subprocess.run(["git", "-C", str(bare), "config", "uploadpack.allowAnySHA1InWant",
                        "true"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(bare), "config", "uploadpack.allowFilter", "true"],
                       check=True, capture_output=True)
        cls.url = str(bare)
        cls.cache = base / "cache"
        cls.source = uu.GitUpstreamSource(cls.cache, timeout=120)
        cls.work_git = git

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_resolve_ref_and_tree_comparison(self):
        sha, ref = self.source.resolve_ref(self.url, "HEAD")
        self.assertEqual(sha, self.head)
        self.assertEqual(ref, "refs/heads/main")
        guide_pin = self.source.commit_tree_oid(self.url, self.pin, "skills/guide")
        guide_head = self.source.commit_tree_oid(self.url, self.head, "skills/guide")
        other_pin = self.source.commit_tree_oid(self.url, self.pin, "skills/other")
        other_head = self.source.commit_tree_oid(self.url, self.head, "skills/other")
        self.assertNotEqual(guide_pin, guide_head)      # relevant drift
        self.assertEqual(other_pin, other_head)          # unrelated commits never bump it
        self.assertIsNone(self.source.commit_tree_oid(self.url, self.head, "skills/absent"))

    def test_read_subtree_and_symlink_detection(self):
        snapshot, problems = uu.snapshot_upstream_tree(self.source, self.url, self.head,
                                                       "skills/guide")
        self.assertTrue(problems)
        self.assertIn("symlink", snapshot["link.md"]["problem"])
        self.assertEqual(snapshot["ref.md"]["data"], b"reference new\n")
        self.assertNotIn("../skills/other/SKILL.md", snapshot)
        self.assertEqual(sorted(snapshot), ["SKILL.md", "link.md", "ref.md"])

    def test_tags_and_root_file(self):
        tags = self.source.list_tags(self.url, "engine-v")
        self.assertEqual(tags, [("engine-v1.2.3", self.head)])
        self.assertEqual(self.source.read_file(self.url, self.pin, "LICENSE"), b"MIT\n")
        self.assertIsNone(self.source.read_file(self.url, self.pin, "NOPE"))


# ---------------------------------------------------------------------------
# CLI surface (offline paths only)
# ---------------------------------------------------------------------------

class TestCliSurface(unittest.TestCase):
    def test_validate_policy_command_on_live_repo(self):
        out = pathlib.Path(tempfile.mkdtemp()) / "validation.json"
        self.addCleanup(lambda: shutil.rmtree(out.parent, ignore_errors=True))
        rc = uu.main(["validate-policy", "--repo-root", str(REPO), "--out", str(out),
                      "--quiet"])
        self.assertEqual(rc, 0)
        report = json.loads(out.read_bytes())
        self.assertTrue(report["valid"])
        self.assertEqual(report["selection"]["registryEntries"], 43)

    def test_usage_errors(self):
        rc = uu.main(["stage", "--repo-root", str(REPO), "--quiet"])
        self.assertEqual(rc, 1)
        rc = uu.main(["check", "--repo-root", str(REPO), "--today", "28-10-2026", "--quiet"])
        self.assertEqual(rc, 1)

    def test_report_bytes_are_deterministic(self):
        report = {"b": 1, "a": [2, 3]}
        self.assertEqual(uu.dump_report(report), uu.dump_report(copy.deepcopy(report)))



class TestAdditionalLicenseEvidence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root, self.source = build_fixture_world(self.tmp.name)
        self.inputs = uu.load_inputs(self.root, expect_counts=(4, 0, 4, 1))
        policy = self.inputs["policy"]
        policy["repositories"][FIXTURE_REPO]["licenseEvidencePaths"] = ["NOTICE.md", "legal/LICENSE"]
        (self.root / "catalog/upstream-update-policy.json").write_bytes(hubcore.pretty(policy))
        self.inputs = uu.load_inputs(self.root, expect_counts=(4, 0, 4, 1))

    def license_only_head(self, old=None, new=None):
        repo = self.source.repos[FIXTURE_REPO]
        pinned = dict(repo["commits"][PIN]["files"])
        if old is not None:
            pinned["legal/LICENSE"] = old
        updated = dict(pinned)
        updated["README.md"] = b"unrelated change\n"
        if new is not None:
            updated["legal/LICENSE"] = new
        elif "legal/LICENSE" in updated:
            del updated["legal/LICENSE"]
        repo["commits"][PIN] = commit(pinned)
        repo["commits"][HEAD] = commit(updated)

    def test_changed_added_removed_license_holds_even_with_unchanged_skill(self):
        for old, new in ((b"old", b"new"), (None, b"added"), (b"removed", None)):
            with self.subTest(old=old, new=new):
                self.license_only_head(old, new)
                report = uu.run_check(self.root, self.inputs, self.source, TODAY)
                check = next(r for r in report["skills"] if r["id"] == "fixture-guide")
                self.assertTrue(check["rootLicenseChanged"])
                self.assertEqual(check["state"], "drifted")
                plan = uu.run_plan(self.root, self.inputs, self.source, TODAY)
                row = next(r for r in plan["skills"] if r["id"] == "fixture-guide")
                self.assertEqual(row["status"], "held-license-drift")
                self.assertFalse(row["contentChanged"])
                self.assertEqual(plan["acceptance"]["acceptedIds"], [])

    def test_unchanged_evidence_does_not_turn_unrelated_commits_into_updates(self):
        self.license_only_head(b"same", b"same")
        plan = uu.run_plan(self.root, self.inputs, self.source, TODAY)
        row = next(r for r in plan["skills"] if r["id"] == "fixture-guide")
        self.assertEqual(row["status"], "no-change")
        self.assertEqual(plan["acceptance"]["acceptedIds"], [])

    def test_evidence_read_error_never_means_unchanged_license(self):
        self.license_only_head(b"old", b"new")
        class BrokenEvidence(uu.FixtureUpstreamSource):
            def read_file(self, url, commit_id, path):
                if path == "legal/LICENSE":
                    raise uu.UpstreamError("synthetic evidence read failure")
                return super().read_file(url, commit_id, path)
        source = BrokenEvidence(self.source.repos)
        report = uu.run_check(self.root, self.inputs, source, TODAY)
        self.assertEqual(next(r for r in report["skills"] if r["id"] == "fixture-guide")["state"], "error")
        plan = uu.run_plan(self.root, self.inputs, source, TODAY)
        self.assertEqual(next(r for r in plan["skills"] if r["id"] == "fixture-guide")["status"], "error")
        self.assertEqual(plan["acceptance"]["acceptedIds"], [])

    def test_evidence_paths_are_bounded_and_clean(self):
        bad_values = ["NOTICE", ["NOTICE", "NOTICE"], ["../LICENSE"], ["/LICENSE"],
                      ["legal/../LICENSE"], ["legal//LICENSE"], ["legal\\LICENSE"],
                      ["bad\x00LICENSE"], [str(i) for i in range(17)]]
        for value in bad_values:
            with self.subTest(value=value):
                with self.assertRaises(uu.UpstreamError):
                    uu.license_evidence_paths({"rootLicense": "LICENSE", "licenseEvidencePaths": value})

if __name__ == "__main__":
    unittest.main(verbosity=2)
