#!/usr/bin/env python3
"""Stdlib-only regressions for the three source-admission findings (2026-10-26)
plus the updater-integration round (same day, job-3cd75dcf27434e54).

Covers, in the shape the review asked for:

1. `build/export_evidence.py` redaction — checkout-relative private paths
   (`Local/Private/...`, `Local/Scratch/...`) are scrubbed to the same
   placeholders as their absolute forms, normal evidence data is retained
   byte-equal, and a raw file whose private layout was never mapped fails the
   export closed on the `Local/Private`/`Local/Scratch` needles.
2. `tools/resolve_upstream_pin.py` — anchored shape validation before anything
   crosses an argv/API/output boundary: valid dotted-semver versions and
   exact `engine-v<semver>` refs pass; newline-carrying or shell-special
   `ENGINE_VERSION` values, and dash-leading or malformed requested refs,
   exit 2 without writing the pin document. Positive cases run against a
   temporary local git clone, so the real tree/`ENGINE_VERSION` comparison is
   exercised with no network.
3. the workflow template itself — no `${{ … }}` expression inside any `run:`
   block (untrusted data only reaches shells through `env:` mappings), every
   `uses:` action is pinned to a full 40-hex commit SHA, and the trigger set
   is still schedule + workflow_dispatch only (no pull_request, no push).
4. the forward-only update policy — `decide_pin_change` proposes automatic
   updates only for strictly newer semantic engine versions; a same-version
   release tag retargeted at a different commit and an older version are
   unchanged no-ops with a recorded reason; a dispatched ref stages
   `manual-review` only; an identical pin is a no-op. The stable-release
   selector ignores drafts, prereleases and malformed entries. The automatic
   path is exercised end to end against a temporary local git clone through
   the hermetic `--releases-json` hook, including the refusal of a release
   tag whose name disagrees with its own tree's `ENGINE_VERSION`.
5. updater integration — the build job calls the real public stage 1
   normalizer with explicit candidate commit AND tree plus a staged candidate
   `ENGINE-LOCK.json`, and the reviewer artifact carries the candidate-derived
   source next to the binary and logs; the PR checklist requires the canonical
   package regeneration, the digest-bound descriptor and real guest/App
   qualification; the root `.github/workflows/impeccable-engine-updater.yml`
   review copy stays byte-identical to the template body.

Run from the repository root:

    python3 -m unittest engines.impeccable.workflows.tools.tests.test_template_hardening
or, more simply:
    python3 -m unittest discover -s engines/impeccable/workflows/tools/tests
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS_DIR = HERE.parent
WORKFLOWS_DIR = TOOLS_DIR.parent
ENGINE_DIR = WORKFLOWS_DIR.parent
HUB_ROOT = ENGINE_DIR.parent.parent

RESOLVE_PY = TOOLS_DIR / "resolve_upstream_pin.py"
EXPORT_PY = ENGINE_DIR / "build" / "export_evidence.py"
STAGE_PY = TOOLS_DIR / "stage_candidate_engine.py"
TEMPLATE_YML = WORKFLOWS_DIR / "impeccable-engine-updater.yml"
ROOT_REVIEW_YML = HUB_ROOT / ".github" / "workflows" / "impeccable-engine-updater.yml"
TRACKED_LOCK = ENGINE_DIR / "ENGINE-LOCK.json"
TRACKED_CONTRACT = ENGINE_DIR / "contract" / "snapshot-contract.v1.json"
TRACKED_BUILDER = ENGINE_DIR / "build" / "build_engine.py"

# Hermetic-ish subprocess environment: system tools only, no user PATH extras
# (keeps `gh` and other host binaries out of the resolution path).
BASE_ENV = {
    "PATH": "/usr/bin:/bin",
    "HOME": os.environ.get("HOME", "/tmp"),
    "GIT_CONFIG_NOSYSTEM": "1",
}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


resolve = load_module(RESOLVE_PY, "resolve_upstream_pin")
export = load_module(EXPORT_PY, "export_evidence")
stage = load_module(STAGE_PY, "stage_candidate_engine")


class TestShapeValidators(unittest.TestCase):
    def test_valid_engine_version_accepted(self):
        self.assertEqual(resolve.validate_engine_version("0.1.18", "v"), "0.1.18")
        self.assertEqual(resolve.validate_engine_version("10.0.100", "v"), "10.0.100")

    def test_engine_version_rejects_newline_forgery(self):
        # The review's attack shape: a version that forges an extra output line.
        with self.assertRaises(resolve.ShapeError):
            resolve.validate_engine_version("0.1.18\nchanged=true", "v")

    def test_engine_version_rejects_shell_metacharacters(self):
        for evil in ("0.1.18; touch /tmp/pwn", "0.1.18`id`", "0.1.18 $(whoami)",
                     "0.1.18\nPY", "", "1.2", "0.1.18.4", " 0.1.18", "0.1.18 ",
                     "01.1.1x", None):
            with self.assertRaises(resolve.ShapeError, msg=repr(evil)):
                resolve.validate_engine_version(evil, "v")

    def test_valid_refs_accepted(self):
        self.assertEqual(resolve.validate_requested_ref(""), "")
        sha = "78e89d517c11304f903dd793580cabf30e59b362"
        self.assertEqual(resolve.validate_requested_ref(sha), sha)
        self.assertEqual(resolve.validate_requested_ref("engine-v0.1.18"), "engine-v0.1.18")
        self.assertEqual(resolve.validate_requested_ref("  engine-v1.2.3 "), "engine-v1.2.3")

    def test_dash_and_newline_refs_rejected(self):
        for bad in ("--upload-pack=evil", "-b", "-engine-v1.2.3",
                    "engine-v1.2.3\nref=main", "engine-v1.2.3-rc1", "main",
                    "0.1.18", "refs/heads/main", "sha", "ENGINE-V1.2.3",
                    "engine-v1.2", "engine-vx.y.z", "engine-v1.2.3; rm -rf /"):
            with self.assertRaises(resolve.ShapeError, msg=repr(bad)):
                resolve.validate_requested_ref(bad)

    def test_hex_sha_validation(self):
        sha = "a" * 40
        self.assertEqual(resolve.validate_hex_sha(sha, "c"), sha)
        for bad in ("a" * 39, "A" * 40, "z" * 40, sha + "\n", None, ""):
            with self.assertRaises(resolve.ShapeError, msg=repr(bad)):
                resolve.validate_hex_sha(bad, "c")


def run_resolve(lock_path: Path, extra: list[str], out: Path | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(RESOLVE_PY), "--lock", str(lock_path), "--out", str(out)]
    return subprocess.run(cmd + extra, capture_output=True, text=True,
                          env=BASE_ENV, timeout=120)


class TestResolvePinFailClosed(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.lock = self.root / "lock.json"
        self.out = self.root / "pin.json"

    def write_lock(self, commit: str = "c" * 40, tree: str = "d" * 40,
                   version: str = "0.1.0") -> None:
        self.lock.write_text(json.dumps({
            "upstream": {"commit": commit, "tree": tree, "engineVersion": version},
        }))

    def test_dash_leading_ref_exits_2_before_resolution(self):
        self.write_lock()
        # The equals form is what actually reaches the tool's own validator;
        # the space form is rejected by argparse itself (also fail-closed).
        proc = run_resolve(self.lock, ["--requested-ref=--upload-pack=evil"], self.out)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["ok"])
        self.assertIn("dash", payload["error"])
        self.assertFalse(self.out.exists(), "pin document must not be written")

    def test_dash_leading_ref_space_form_fails_closed_via_argparse(self):
        self.write_lock()
        proc = run_resolve(self.lock, ["--requested-ref", "-b"], self.out)
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(self.out.exists())

    def test_hostile_lock_shape_exits_2(self):
        self.write_lock(version="0.1\nchanged=x")
        proc = run_resolve(self.lock, [], self.out)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("lock upstream.engineVersion", json.loads(proc.stdout)["error"])
        self.assertFalse(self.out.exists())

    def make_clone(self, engine_version: str):
        origin = self.root / "origin.git"
        work = self.root / "work"
        subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(origin)],
                       check=True, env=BASE_ENV, cwd=str(self.root))
        subprocess.run(["git", "init", "-q", "-b", "main", str(work)],
                       check=True, env=BASE_ENV, cwd=str(self.root))
        subprocess.run(["git", "remote", "add", "origin", "../origin.git"],
                       check=True, env=BASE_ENV, cwd=str(work))
        (work / "ENGINE_VERSION").write_text(engine_version + "\n")
        subprocess.run(["git", "add", "ENGINE_VERSION"], check=True, cwd=str(work), env=BASE_ENV)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                       "commit", "-qm", "x"],
                       check=True, cwd=str(work), env=BASE_ENV)
        sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                             text=True, check=True, cwd=str(work), env=BASE_ENV).stdout.strip()
        tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], capture_output=True,
                              text=True, check=True, cwd=str(work), env=BASE_ENV).stdout.strip()
        subprocess.run(["git", "push", "-q", "origin", "HEAD:main"],
                       check=True, cwd=str(work), env=BASE_ENV)
        return sha, tree, work

    def test_valid_candidate_from_temporary_clone(self):
        sha, tree, work = self.make_clone("0.1.18")
        self.write_lock(commit="e" * 40, tree="f" * 40, version="0.1.17")
        proc = run_resolve(self.lock, ["--requested-ref", sha, "--source", str(work)], self.out)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        pin = json.loads(self.out.read_text())
        self.assertEqual(pin["candidate_commit"], sha)
        # The actual tree is compared, not assumed:
        self.assertEqual(pin["candidate_tree"], tree)
        self.assertEqual(pin["candidate_engine_version"], "0.1.18")
        self.assertEqual(pin["candidate_tag"], "engine-v0.1.18")
        self.assertTrue(pin["changed"])
        self.assertIn("local clone", pin["resolved_via"])

    def test_tag_ref_resolves_and_reports_real_version(self):
        sha, tree, work = self.make_clone("0.9.9")
        subprocess.run(["git", "tag", "engine-v0.9.9"], check=True, cwd=str(work), env=BASE_ENV)
        subprocess.run(["git", "push", "-q", "origin", "engine-v0.9.9"],
                       check=True, cwd=str(work), env=BASE_ENV)
        self.write_lock(commit="e" * 40, tree="f" * 40, version="0.1.17")
        proc = run_resolve(self.lock, ["--requested-ref", "engine-v0.9.9", "--source", str(work)], self.out)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        pin = json.loads(self.out.read_text())
        self.assertEqual(pin["candidate_engine_version"], "0.9.9")
        self.assertEqual(pin["candidate_tag"], "engine-v0.9.9")

    def test_forgeable_engine_version_from_tree_is_rejected(self):
        # A hostile upstream ENGINE_VERSION file cannot pass the emitter gate,
        # even when it arrives from a "trusted" local resolution path.
        sha, tree, work = self.make_clone("0.1.18\nchanged=true")
        self.write_lock(commit="e" * 40, tree="f" * 40, version="0.1.17")
        proc = run_resolve(self.lock, ["--requested-ref", sha, "--source", str(work)], self.out)
        self.assertEqual(proc.returncode, 2, proc.stderr + proc.stdout)
        self.assertIn("ENGINE_VERSION", json.loads(proc.stdout)["error"])
        self.assertFalse(self.out.exists(), "pin document must not be written")


class TestTemplateDataFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lines = TEMPLATE_YML.read_text(encoding="utf-8").splitlines()

    def run_blocks(self):
        """Yield (start_line_number, [script lines]) for every `run: |` block."""
        block: list[str] | None = None
        start = 0
        for i, line in enumerate(self.lines, 1):
            stripped = line.strip()
            if stripped.startswith("run:"):
                if block is not None:
                    yield start, block
                block, start = [], i
                continue
            if block is not None:
                indent = len(line) - len(line.lstrip())
                # A run block's content is indented deeper than the step key;
                # any non-blank line at or shallower than 8 spaces ends it.
                if line.strip() and indent <= 8:
                    yield start, block
                    block = None
                    continue
                block.append(line)
        if block is not None:
            yield start, block

    def test_no_expression_interpolation_inside_run_blocks(self):
        offenders = [(start, line) for start, block in self.run_blocks()
                     for line in block if "${{" in line]
        self.assertEqual(offenders, [], f"run: blocks must take data via env only: {offenders}")

    def test_untrusted_values_arrive_only_as_env_or_output_mappings(self):
        mapping = re.compile(r"^\s+[a-zA-Z_][a-zA-Z0-9_]*: \$\{\{[^}]+\}\}\s*$")
        for i, line in enumerate(self.lines, 1):
            if "needs.pin.outputs" in line or "steps.compare.outputs" in line:
                if line.lstrip().startswith("if:"):
                    continue  # job-level `if:` is a GitHub expression, not shell text
                self.assertRegex(line, mapping, f"line {i} interpolates outputs outside a mapping")

    def test_actions_pinned_to_full_commit_shas(self):
        pinned = re.compile(r"^(\s+)-? ?uses: [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@([0-9a-f]{40})\s+# v[0-9.]+")
        seen = []
        for i, line in enumerate(self.lines, 1):
            if "uses: " in line and "actions/" in line:
                m = pinned.match(line)
                self.assertIsNotNone(m, f"line {i}: action must be SHA-pinned with a version comment: {line!r}")
                seen.append(m.group(2))
        self.assertEqual(len(seen), 5, "3 checkouts + 2 upload-artifact expected")
        self.assertTrue(set(seen) == {
            "11d5960a326750d5838078e36cf38b85af677262",   # actions/checkout v4.4.0
            "ea165f8d65b6e75b540449e92b4886f43607fa02",   # actions/upload-artifact v4.6.2
        }, seen)

    def test_triggers_not_broadened(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed on this host")
        doc = yaml.safe_load("\n".join(self.lines))
        on = doc.get("on") or doc.get(True)
        self.assertEqual(sorted(on), ["schedule", "workflow_dispatch"])

    def test_output_emission_gate_checks_shapes(self):
        text = TEMPLATE_YML.read_text()
        # The heredoc that writes $GITHUB_OUTPUT must fullmatch-check every
        # shape-bearing field instead of dumping pin.get(key, "") raw.
        self.assertIn("$GITHUB_OUTPUT", text)
        self.assertIn('re.fullmatch(shape, value)', text)
        self.assertIn('sys.exit(f"refusing to emit output', text)

    def test_yaml_parses(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed on this host")
        doc = yaml.safe_load(TEMPLATE_YML.read_text(encoding="utf-8"))
        self.assertEqual(sorted(doc["jobs"]), ["build-and-verify", "open-update-pr", "pin"])
        on = doc.get("on") or doc.get(True)
        self.assertEqual(sorted(on), ["schedule", "workflow_dispatch"])
        # least privilege: read by default, write only in the PR job
        self.assertEqual(doc["permissions"], {"contents": "read"})
        self.assertEqual(doc["jobs"]["pin"]["permissions"], {"contents": "read"})
        self.assertEqual(doc["jobs"]["build-and-verify"]["permissions"], {"contents": "read"})
        self.assertEqual(doc["jobs"]["open-update-pr"]["permissions"],
                         {"contents": "write", "pull-requests": "write"})


class TestExportEvidenceRedaction(unittest.TestCase):
    def make_args(self, repo: Path, scratch: Path, cache: Path):
        class A:
            pass
        a = A()
        a.wrapper = None
        a.scratch = str(scratch)
        a.cache = str(cache)
        a.repo = str(repo)
        return a

    def test_relative_and_absolute_forms_map_to_one_placeholder(self):
        with tempfile.TemporaryDirectory() as t:
            repo = Path(t).resolve() / "checkout"
            scratch = repo / "Local/Scratch/lane"
            cache = Path(t).resolve() / "cache"
            subs = export.build_substitutions(self.make_args(repo, scratch, cache))
            doc = {
                "contractDir": "Local/Private/floe-skill-hub/engines/impeccable/contract",
                "upstream": "Local/Scratch/lane/upstream",
                "absUpstream": str(scratch / "upstream"),
                "absHubRootFile": str(repo / "Local/Private/floe-skill-hub/README.md"),
                # normal data that must survive untouched:
                "engineVersion": "0.1.17",
                "checksTotal": 61,
                "digest": "baf2453164be6162703af9d671be16da152fa874db53ce95ad5b3516d40de4a3",
                "prose": "the local private renderer kept its meaning",
                "otherCacheApp": "Library/Caches/other-app/thing",
            }
            red = export.redact(doc, subs)
            self.assertEqual(red["contractDir"], "<hub-root>/engines/impeccable/contract")
            self.assertEqual(red["upstream"], "<scratch>/upstream")
            self.assertEqual(red["absUpstream"], "<scratch>/upstream")
            self.assertEqual(red["absHubRootFile"], "<hub-root>/README.md")
            # semantics unchanged
            self.assertEqual(red["engineVersion"], "0.1.17")
            self.assertEqual(red["checksTotal"], 61)
            self.assertEqual(red["digest"], doc["digest"])
            self.assertEqual(red["prose"], doc["prose"])
            self.assertEqual(red["otherCacheApp"], doc["otherCacheApp"])

    def test_cli_end_to_end_export_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t).resolve()
            repo = root / "checkout"
            scratch = repo / "Local/Scratch/lane"
            raw = root / "raw"
            dst = root / "pub"
            raw.mkdir()
            (raw / "e.json").write_text(json.dumps({
                "contractDir": "Local/Private/floe-skill-hub/engines/impeccable/contract",
                "upstream": "Local/Scratch/lane/upstream",
                "cache": str(root / "cache" / "x"),
                "checksPassed": 61,
            }))
            base = [sys.executable, str(EXPORT_PY), "--from", str(raw)]
            env = dict(BASE_ENV)
            ok = subprocess.run(base + [
                "--to", str(dst), "--file", "e.json",
                "--repo", str(repo), "--scratch", str(scratch),
                "--cache", str(root / "cache"),
            ], capture_output=True, text=True, env=env, timeout=60)
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
            written = json.loads((dst / "e.json").read_text())
            self.assertEqual(written["contractDir"], "<hub-root>/engines/impeccable/contract")
            self.assertEqual(written["upstream"], "<scratch>/upstream")
            self.assertEqual(written["checksPassed"], 61)
            # without the scratch mapping the layout marker must fail closed
            dst2 = root / "pub2"
            bad = subprocess.run(base + ["--to", str(dst2), "--file", "e.json", "--repo", str(repo)],
                                 capture_output=True, text=True, env=env, timeout=60)
            self.assertEqual(bad.returncode, 1, bad.stdout + bad.stderr)
            report = json.loads(bad.stdout)
            self.assertFalse(report["ok"])
            self.assertTrue(any(n["needle"] == "Local/Scratch" for n in report["leftovers"]))


class TestReExportedEvidence(unittest.TestCase):
    """The tracked public file the finding named must now be clean."""

    def test_contract_validation_has_no_private_layout(self):
        text = (ENGINE_DIR / "evidence" / "contract-validation.json").read_text(encoding="utf-8")
        self.assertNotIn("Local/Private", text)
        self.assertNotIn("Local/Scratch", text)
        doc = json.loads(text)
        self.assertEqual(doc["contractDir"], "<hub-root>/engines/impeccable/contract")
        self.assertEqual(doc["upstream"], "<scratch>/upstream")
        self.assertEqual((doc["checksTotal"], doc["checksPassed"]), (61, 61))
        self.assertEqual(doc["engineVersion"], "0.1.17")


class TestUpdatePolicy(unittest.TestCase):
    """Pure forward-only decision policy (no git, no network)."""

    def decide(self, current_version="0.1.17", current_commit="a" * 40,
               candidate_version="0.1.18", candidate_commit="b" * 40,
               requested_ref=None):
        return resolve.decide_pin_change(
            current_commit=current_commit, current_version=current_version,
            candidate_commit=candidate_commit, candidate_version=candidate_version,
            requested_ref=requested_ref)

    def test_newer_version_is_automatic_change(self):
        d = self.decide()
        self.assertTrue(d["changed"])
        self.assertEqual(d["mode"], "automatic")
        self.assertIn("strictly newer", d["reason"])

    def test_same_version_diverged_is_unchanged_noop(self):
        # The live upstream case: release tag retargeted at a different commit
        # at the SAME engine version must not churn a build/PR every day.
        d = self.decide(candidate_version="0.1.17")
        self.assertFalse(d["changed"])
        self.assertEqual(d["mode"], "no-op")
        self.assertIn("strictly newer releases only", d["reason"])
        self.assertIn("pin is retained", d["reason"])

    def test_older_version_is_unchanged_noop(self):
        d = self.decide(candidate_version="0.1.16")
        self.assertFalse(d["changed"])
        self.assertEqual(d["mode"], "no-op")
        self.assertIn("older than the pinned", d["reason"])
        self.assertIn("downgrades are never proposed", d["reason"])

    def test_manual_same_version_stages_review_only(self):
        d = self.decide(candidate_version="0.1.17",
                        requested_ref="157a5722d54be684f869c7e0bb517f07ca66fbb5")
        self.assertTrue(d["changed"])
        self.assertEqual(d["mode"], "manual-review")
        self.assertIn("review only", d["reason"])
        self.assertIn("never an automatic install", d["reason"])

    def test_manual_newer_version_stages_review(self):
        d = self.decide(requested_ref="engine-v0.1.18")
        self.assertTrue(d["changed"])
        self.assertEqual(d["mode"], "manual-review")

    def test_identical_pin_is_noop(self):
        d = self.decide(candidate_version="0.1.17", candidate_commit="a" * 40)
        self.assertFalse(d["changed"])
        self.assertEqual(d["mode"], "no-op")
        self.assertIn("identical", d["reason"])

    def test_reasons_are_single_line_printable_ascii(self):
        cases = [
            self.decide(),
            self.decide(candidate_version="0.1.17"),
            self.decide(candidate_version="0.1.16"),
            self.decide(candidate_version="0.1.17",
                        requested_ref="b" * 40),
            self.decide(candidate_version="0.1.17", candidate_commit="a" * 40),
        ]
        for d in cases:
            self.assertIsNotNone(
                re.fullmatch(r"[ -~]{1,240}", d["reason"]), d["reason"])


class TestStableReleaseSelector(unittest.TestCase):
    def test_draft_and_prerelease_releases_are_ignored(self):
        releases = [
            {"tag_name": "engine-v0.1.20", "draft": True, "prerelease": False},
            {"tag_name": "engine-v0.1.19", "draft": False, "prerelease": True},
            {"tag_name": "engine-v0.1.18", "draft": False, "prerelease": False},
        ]
        self.assertEqual(resolve.select_latest_stable_release(releases), "engine-v0.1.18")

    def test_highest_semver_wins_not_lexicographic(self):
        releases = [
            {"tag_name": "engine-v0.1.9", "draft": False, "prerelease": False},
            {"tag_name": "engine-v0.1.10", "draft": False, "prerelease": False},
        ]
        self.assertEqual(resolve.select_latest_stable_release(releases), "engine-v0.1.10")

    def test_no_stable_release_returns_none(self):
        self.assertIsNone(resolve.select_latest_stable_release([
            {"tag_name": "engine-v0.1.18", "draft": True, "prerelease": False},
            {"tag_name": "engine-v0.1.19", "draft": False, "prerelease": True},
        ]))
        self.assertIsNone(resolve.select_latest_stable_release([]))

    def test_malformed_or_hostile_entries_are_never_selected(self):
        releases = [
            "engine-v9.9.9",
            {"tag_name": "engine-v9.9.9\nevil=true"},
            {"tag_name": "--upload-pack=evil"},
            {"tag_name": "engine-v1.2.3-rc1", "draft": False, "prerelease": False},
            {"tag_name": "engine-v0.2.0", "draft": False, "prerelease": False},
        ]
        self.assertEqual(resolve.select_latest_stable_release(releases), "engine-v0.2.0")


class TestResolveAutomaticPath(unittest.TestCase):
    """End-to-end automatic path against a temporary local git clone, with the
    hermetic `--releases-json` hook standing in for the GitHub API."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.lock = self.root / "lock.json"
        self.out = self.root / "pin.json"
        self.releases = self.root / "releases.json"

    def write_lock(self, commit: str, tree: str, version: str) -> None:
        self.lock.write_text(json.dumps({
            "upstream": {"commit": commit, "tree": tree, "engineVersion": version},
        }))

    def make_clone(self, tagged_versions: list[tuple[str, str]]):
        """[(tag, engine_version), ...] -> one commit per entry, all pushed."""
        origin = self.root / "origin.git"
        work = self.root / "work"
        subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(origin)],
                       check=True, env=BASE_ENV, cwd=str(self.root))
        subprocess.run(["git", "init", "-q", "-b", "main", str(work)],
                       check=True, env=BASE_ENV, cwd=str(self.root))
        subprocess.run(["git", "remote", "add", "origin", "../origin.git"],
                       check=True, env=BASE_ENV, cwd=str(work))
        commits = {}
        for tag, version in tagged_versions:
            (work / "ENGINE_VERSION").write_text(version + "\n")
            subprocess.run(["git", "add", "ENGINE_VERSION"], check=True,
                           cwd=str(work), env=BASE_ENV)
            subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                            "commit", "-qm", f"engine {version}"],
                           check=True, cwd=str(work), env=BASE_ENV)
            sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                                 text=True, check=True, cwd=str(work),
                                 env=BASE_ENV).stdout.strip()
            tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], capture_output=True,
                                  text=True, check=True, cwd=str(work),
                                  env=BASE_ENV).stdout.strip()
            subprocess.run(["git", "tag", tag], check=True, cwd=str(work), env=BASE_ENV)
            subprocess.run(["git", "push", "-q", "origin", f"HEAD:refs/tags/{tag}"],
                           check=True, cwd=str(work), env=BASE_ENV)
            commits[tag] = (sha, tree)
        return commits, work

    def run_auto(self, work: Path, lock=None):
        cmd = [sys.executable, str(RESOLVE_PY), "--lock", str(lock or self.lock),
               "--out", str(self.out), "--releases-json", str(self.releases),
               "--source", str(work)]
        return subprocess.run(cmd, capture_output=True, text=True,
                              env=BASE_ENV, timeout=120)

    def test_automatic_newer_release_is_a_forward_change(self):
        commits, work = self.make_clone([
            ("engine-v0.1.17", "0.1.17"),
            ("engine-v0.1.18", "0.1.18"),
        ])
        pin_sha, _ = commits["engine-v0.1.17"]
        self.write_lock(pin_sha, "d" * 40, "0.1.17")
        self.releases.write_text(json.dumps([
            {"tag_name": "engine-v0.1.17", "draft": False, "prerelease": False},
            {"tag_name": "engine-v0.1.18", "draft": False, "prerelease": False},
        ]))
        proc = self.run_auto(work)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        pin = json.loads(self.out.read_text())
        self.assertTrue(pin["changed"])
        self.assertEqual(pin["decision_mode"], "automatic")
        self.assertEqual(pin["candidate_engine_version"], "0.1.18")
        self.assertEqual(pin["candidate_commit"], commits["engine-v0.1.18"][0])
        self.assertEqual(pin["candidate_tree"], commits["engine-v0.1.18"][1])
        self.assertIsNone(pin["requested_ref"])

    def test_automatic_same_version_diverged_release_is_unchanged(self):
        # The exact live failure mode: newest stable release tag sits at a
        # different commit with the SAME engine version as the pin.
        commits, work = self.make_clone([("engine-v0.1.17", "0.1.17")])
        pin_sha, pin_tree = commits["engine-v0.1.17"]
        self.write_lock(pin_sha, pin_tree, "0.1.17")
        # The upstream tag moved on: new commit, still engine 0.1.17.
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                        "commit", "--allow-empty", "-qm", "retargeted release"],
                       check=True, cwd=str(work), env=BASE_ENV)
        subprocess.run(["git", "tag", "-f", "engine-v0.1.17"], check=True,
                       cwd=str(work), env=BASE_ENV)
        diverged = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                                  text=True, check=True, cwd=str(work),
                                  env=BASE_ENV).stdout.strip()
        self.assertNotEqual(diverged, pin_sha)
        subprocess.run(["git", "push", "-q", "-f", "origin", "HEAD:refs/tags/engine-v0.1.17"],
                       check=True, cwd=str(work), env=BASE_ENV)
        self.releases.write_text(json.dumps([
            {"tag_name": "engine-v0.1.17", "draft": False, "prerelease": False},
        ]))
        proc = self.run_auto(work)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        pin = json.loads(self.out.read_text())
        self.assertFalse(pin["changed"])
        self.assertEqual(pin["decision_mode"], "no-op")
        self.assertIn("strictly newer releases only", pin["decision_reason"])
        self.assertEqual(pin["current_commit"], pin_sha, "the pin must be retained")

    def test_automatic_older_release_is_unchanged(self):
        commits, work = self.make_clone([("engine-v0.1.16", "0.1.16")])
        self.write_lock("e" * 40, "f" * 40, "0.1.17")
        self.releases.write_text(json.dumps([
            {"tag_name": "engine-v0.1.16", "draft": False, "prerelease": False},
        ]))
        proc = self.run_auto(work)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        pin = json.loads(self.out.read_text())
        self.assertFalse(pin["changed"])
        self.assertEqual(pin["decision_mode"], "no-op")
        self.assertIn("downgrades are never proposed", pin["decision_reason"])

    def test_draft_and_prerelease_never_selected_automatically(self):
        commits, work = self.make_clone([
            ("engine-v0.1.17", "0.1.17"),
            ("engine-v0.1.19", "0.1.19"),
            ("engine-v0.1.20", "0.1.20"),
        ])
        pin_sha, pin_tree = commits["engine-v0.1.17"]
        self.write_lock(pin_sha, pin_tree, "0.1.17")
        self.releases.write_text(json.dumps([
            {"tag_name": "engine-v0.1.20", "draft": True, "prerelease": False},
            {"tag_name": "engine-v0.1.19", "draft": False, "prerelease": True},
            {"tag_name": "engine-v0.1.17", "draft": False, "prerelease": False},
        ]))
        proc = self.run_auto(work)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        pin = json.loads(self.out.read_text())
        # newest STABLE is the pinned tag itself -> identical pin -> no-op.
        self.assertEqual(pin["candidate_tag"], "engine-v0.1.17")
        self.assertFalse(pin["changed"])
        self.assertEqual(pin["decision_mode"], "no-op")
        self.assertIn("identical", pin["decision_reason"])

    def test_tag_version_mismatch_is_refused(self):
        # tag engine-v0.1.18 naming a tree that still carries ENGINE_VERSION 0.1.17
        commits, work = self.make_clone([("engine-v0.1.18", "0.1.17")])
        self.write_lock("e" * 40, "f" * 40, "0.1.17")
        proc = run_resolve(self.lock, [
            "--requested-ref", "engine-v0.1.18", "--source", str(work)], self.out)
        self.assertEqual(proc.returncode, 2, proc.stderr + proc.stdout)
        self.assertIn("disagrees with its own tree", json.loads(proc.stdout)["error"])
        self.assertFalse(self.out.exists(), "pin document must not be written")

    def test_manual_commit_ref_stages_same_version_review(self):
        commits, work = self.make_clone([("engine-v0.1.17", "0.1.17")])
        pin_sha, pin_tree = commits["engine-v0.1.17"]
        self.write_lock(pin_sha, pin_tree, "0.1.17")
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                        "commit", "--allow-empty", "-qm", "manual candidate"],
                       check=True, cwd=str(work), env=BASE_ENV)
        manual = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                                text=True, check=True, cwd=str(work),
                                env=BASE_ENV).stdout.strip()
        proc = run_resolve(self.lock, [
            "--requested-ref", manual, "--source", str(work)], self.out)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        pin = json.loads(self.out.read_text())
        self.assertTrue(pin["changed"])
        self.assertEqual(pin["decision_mode"], "manual-review")
        self.assertEqual(pin["requested_ref"], manual)
        self.assertIn("review only", pin["decision_reason"])

    def test_malformed_releases_json_fails_closed(self):
        commits, work = self.make_clone([("engine-v0.1.17", "0.1.17")])
        pin_sha, pin_tree = commits["engine-v0.1.17"]
        self.write_lock(pin_sha, pin_tree, "0.1.17")
        self.releases.write_text(json.dumps({"not": "a list"}))
        proc = self.run_auto(work)
        self.assertEqual(proc.returncode, 2, proc.stderr + proc.stdout)
        self.assertIn("releases-json", json.loads(proc.stdout)["error"])
        self.assertFalse(self.out.exists())


class TestUpdaterIntegrationWiring(unittest.TestCase):
    """The template must call the real public tooling and carry the derived
    source into the reviewer artifact; the PR checklist must name the
    regeneration, the digest-bound descriptor and real guest/App proof."""

    @classmethod
    def setUpClass(cls):
        cls.text = TEMPLATE_YML.read_text(encoding="utf-8")

    def test_removed_private_normalizer_is_gone(self):
        self.assertNotIn("$SOURCE_DIR/scripts/normalize_skill_source.py", self.text)

    def test_build_job_calls_public_stage1_normalizer(self):
        self.assertIn("build/skill-source/stage1_normalize_skill_source.py", self.text)
        self.assertIn('--engine-lock "$RUNNER_TEMP/candidate-lock/ENGINE-LOCK.json"', self.text)

    def test_candidate_lock_is_staged_in_temp_not_the_tracked_lock(self):
        self.assertIn('cp "$ENGINE_DIR/ENGINE-LOCK.json" "$RUNNER_TEMP/candidate-lock/ENGINE-LOCK.json"',
                      self.text)

    def test_candidate_commit_and_tree_are_both_emitted_and_revalidated(self):
        self.assertIn("candidate_tree: ${{ steps.compare.outputs.candidate_tree }}", self.text)
        self.assertIn('[[ "$CANDIDATE_TREE" =~ ^[0-9a-f]{40}$ ]]', self.text)
        self.assertIn('CANDIDATE_TREE: ${{ needs.pin.outputs.candidate_tree }}', self.text)

    def test_artifact_includes_candidate_derived_source_and_lock(self):
        self.assertIn("${{ runner.temp }}/sources-impeccable/**", self.text)
        self.assertIn("${{ runner.temp }}/candidate-lock/ENGINE-LOCK.json", self.text)

    def test_pr_checklist_requires_regeneration_descriptor_and_guest(self):
        for needle in ("run_pipeline.sh", "descriptor.v1.json", "TinyEMU",
                       "candidate-derived source"):
            self.assertIn(needle, self.text)

    def test_decision_metadata_is_emitted_with_shapes(self):
        self.assertIn("decision_mode: ${{ steps.compare.outputs.decision_mode }}", self.text)
        self.assertIn("decision_reason: ${{ steps.compare.outputs.decision_reason }}", self.text)
        self.assertIn('"decision_mode": r"automatic|manual-review|no-op"', self.text)
        self.assertIn('"decision_reason": r"[ -~]{1,240}"', self.text)

    def test_open_pr_still_draft_only(self):
        self.assertIn("gh pr create --draft", self.text)
        self.assertNotIn("gh pr merge", self.text)
        self.assertNotIn("--auto", self.text)
        self.assertNotIn("gh release", self.text)


class TestRootReviewCopySync(unittest.TestCase):
    def test_root_copy_body_is_byte_identical_to_template(self):
        template = TEMPLATE_YML.read_text(encoding="utf-8")
        root = ROOT_REVIEW_YML.read_text(encoding="utf-8")
        self.assertEqual(template[template.index("name:"):],
                         root[root.index("name:"):])

    def test_root_copy_keeps_pr_creation_disabled_until_owner_approval(self):
        root = ROOT_REVIEW_YML.read_text(encoding="utf-8")
        head = root[:root.index("name:")]
        self.assertIn("Draft PR creation is DISABLED", head)
        self.assertIn("FLOE_IMPECCABLE_UPDATE_PRS=enabled", head)
        pr_job = root[root.index("  open-update-pr:"):]
        self.assertIn("vars.FLOE_IMPECCABLE_UPDATE_PRS == 'enabled'", pr_job)
        build_job = root[root.index("  build-and-verify:"):root.index("  open-update-pr:")]
        self.assertNotIn("vars.FLOE_IMPECCABLE_UPDATE_PRS", build_job)


# The adapter crate Cargo.toml version is the single component version constant
# the staged identity projection derives from; keep the synthetic candidate in
# the canonical `impeccable-<version>+floe.<crate>` form the stager authenticates.
ADAPTER_CRATE_VERSION = re.search(
    r'^version\s*=\s*"([^"]+)"\s*$',
    (ENGINE_DIR / "adapter" / "Cargo.toml").read_text(encoding="utf-8"),
    re.MULTILINE).group(1)

CANDIDATE_IDENTITY = {
    "commit": "b" * 40,
    "tree": "c" * 40,
    "version": "0.1.18",
    "engineId": f"impeccable-0.1.18+floe.{ADAPTER_CRATE_VERSION}",
}


def write_candidate_lock(path: Path, identity: dict = CANDIDATE_IDENTITY) -> None:
    path.write_text(json.dumps({
        "engineId": identity["engineId"],
        "status": "candidate-update-not-qualified",
        "upstream": {"commit": identity["commit"], "tree": identity["tree"],
                     "engineVersion": identity["version"]},
    }))


def run_stage(engine_dir: Path, lock: Path, out: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(STAGE_PY), "--engine-dir", str(engine_dir),
         "--candidate-lock", str(lock), "--out", str(out)],
        capture_output=True, text=True, env=BASE_ENV, timeout=120)


class TestStageCandidateEngine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.lock = self.root / "candidate-lock"
        self.lock.mkdir()
        self.candidate_lock = self.lock / "ENGINE-LOCK.json"
        write_candidate_lock(self.candidate_lock)
        self.out = self.root / "staged" / "hub"

    def test_stages_byte_identical_build_inputs_and_license(self):
        proc = run_stage(ENGINE_DIR, self.candidate_lock, self.out)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        receipt = json.loads(proc.stdout)
        identity = receipt["stagedTestIdentity"]
        # the trusted Rust tests pin the published identity as literals, and the
        # staged rule-pass harness carries the candidate-only host-target
        # binding (hosted run 40642311746); exactly these staged TEMP files
        # differ, every other build/adapter/patch byte stays the tracked byte
        projected = set(identity["files"])
        self.assertEqual(projected, {
            "tests/contract_embedded.rs",
            "tests/snapshot_scan.rs",
            "tests/data/expected-large-shape.v1.json",
            "tests/data/expected-admission-exactcap.v1.json",
            "tests/rule_pass_limiter.rs",
        })
        self.assertTrue(identity["hostTargetBinding"]["applied"])
        for name in ("build", "adapter", "patches"):
            tracked_files = {str(p.relative_to(ENGINE_DIR / name))
                             for p in (ENGINE_DIR / name).rglob("*") if p.is_file()}
            staged_files = {str(p.relative_to(self.out / "engines" / "impeccable" / name))
                            for p in (self.out / "engines" / "impeccable" / name).rglob("*")
                            if p.is_file()}
            self.assertEqual(tracked_files, staged_files)
            for rel in tracked_files:
                if name == "adapter" and rel in projected:
                    continue
                self.assertEqual(
                    (ENGINE_DIR / name / rel).read_bytes(),
                    (self.out / "engines" / "impeccable" / name / rel).read_bytes(), rel)
        for rel in sorted(projected):
            entry = identity["files"][rel]
            staged = (self.out / "engines" / "impeccable" / "adapter" / rel).read_bytes()
            self.assertEqual(hashlib.sha256(staged).hexdigest(), entry["stagedSha256"], rel)
            self.assertTrue(entry["changed"], rel)
            # reversing every recorded projection reproduces the tracked test
            # byte exactly: no non-projected byte moved
            restored = staged.decode("utf-8")
            for change in reversed(identity["changes"]):
                if change["file"] == rel and change["pinned"] != change["projected"]:
                    restored = restored.replace(change["projected"], change["pinned"])
            self.assertEqual(restored,
                             (ENGINE_DIR / "adapter" / rel).read_bytes().decode("utf-8"), rel)
        staged_lock = (self.out / "engines" / "impeccable" / "ENGINE-LOCK.json").read_bytes()
        self.assertEqual(staged_lock, self.candidate_lock.read_bytes())
        self.assertEqual((self.out / "LICENSE").read_bytes(), (HUB_ROOT / "LICENSE").read_bytes())

    def test_staged_contract_differs_only_in_candidate_identity(self):
        proc = run_stage(ENGINE_DIR, self.candidate_lock, self.out)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        tracked = json.loads(TRACKED_CONTRACT.read_text(encoding="utf-8"))
        staged = json.loads((self.out / "engines" / "impeccable" / "contract"
                             / "snapshot-contract.v1.json").read_text(encoding="utf-8"))

        def diff_keys(a, b, prefix=""):
            keys = set()
            if isinstance(a, dict) and isinstance(b, dict):
                for k in set(a) | set(b):
                    if a.get(k) != b.get(k):
                        keys |= diff_keys(a.get(k), b.get(k), f"{prefix}{k}.")
            else:
                keys.add(prefix.rstrip("."))
            return keys

        changed = diff_keys(tracked, staged)
        self.assertEqual(changed, {
            "engine.upstreamCommit", "engine.upstreamTree",
            "engine.upstreamEngineVersion", "engine.engineId",
            "provenance.upstreamCommit", "provenance.upstreamTree",
            "provenance.engineVersionFile",
            # the engine-probe verb's documented stdout is part of the same
            # projected identity set (hosted run 40622397082 failed precisely
            # because the projection missed it)
            "verbs",
        }, changed)
        self.assertEqual(staged["engine"]["upstreamCommit"], CANDIDATE_IDENTITY["commit"])
        self.assertEqual(staged["provenance"]["upstreamTree"], CANDIDATE_IDENTITY["tree"])
        probe = next(v for v in staged["verbs"] if v.get("name") == "engine-probe")
        self.assertEqual(
            probe["stdout"],
            f"impeccable-engine {CANDIDATE_IDENTITY['version']}+floe.{ADAPTER_CRATE_VERSION}\n")
        # the component version constant is the crate's own, not a caller string
        self.assertEqual(staged["engine"]["floeAdapterVersion"], ADAPTER_CRATE_VERSION)
        self.assertEqual(staged["engine"]["engineId"], CANDIDATE_IDENTITY["engineId"])
        # schemas, fixtures, coverage, expected goldens: untouched bytes
        for rel in ("producer/snapshot.schema.v1.json", "fixtures/snapshot-positive.v1.json"):
            self.assertEqual((ENGINE_DIR / "contract" / rel).read_bytes(),
                             (self.out / "engines" / "impeccable" / "contract" / rel).read_bytes())

    def test_tracked_tree_is_untouched_after_staging(self):
        lock_before = TRACKED_LOCK.read_bytes()
        contract_before = TRACKED_CONTRACT.read_bytes()
        binary = next((ENGINE_DIR / "dist").rglob("floe-impeccable"))
        binary_before = binary.read_bytes()
        proc = run_stage(ENGINE_DIR, self.candidate_lock, self.out)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertEqual(TRACKED_LOCK.read_bytes(), lock_before)
        self.assertEqual(TRACKED_CONTRACT.read_bytes(), contract_before)
        self.assertEqual(binary.read_bytes(), binary_before)

    def test_refuses_non_empty_out(self):
        self.out.mkdir(parents=True)
        (self.out / "foreign.txt").write_text("keep me")
        proc = run_stage(ENGINE_DIR, self.candidate_lock, self.out)
        self.assertEqual(proc.returncode, 2, proc.stderr + proc.stdout)
        self.assertFalse(json.loads(proc.stdout)["ok"])
        self.assertEqual((self.out / "foreign.txt").read_text(), "keep me")

    def test_refuses_symlink_out_before_resolve(self):
        real = self.root / "real"
        real.mkdir()
        link = self.root / "link-out"
        link.symlink_to(real)
        proc = run_stage(ENGINE_DIR, self.candidate_lock, link)
        self.assertEqual(proc.returncode, 2, proc.stderr + proc.stdout)
        self.assertIn("symbolic link", json.loads(proc.stdout)["error"])
        # nothing was written through the link
        self.assertEqual(list(real.iterdir()), [])

    def test_refuses_out_inside_engine_dir_and_hub(self):
        for bad in (ENGINE_DIR / "staged-test-out", HUB_ROOT / "staged-test-out"):
            proc = run_stage(ENGINE_DIR, self.candidate_lock, bad)
            self.assertEqual(proc.returncode, 2, f"{bad}: " + proc.stderr + proc.stdout)
            self.assertFalse(bad.exists() or (bad.is_dir() and any(bad.iterdir())),
                             f"{bad} must not be created")
            self.assertIn("must not resolve", json.loads(proc.stdout)["error"])

    def test_refuses_bad_candidate_lock_shapes(self):
        for mutate in (
            lambda d: d["upstream"].update(commit="z" * 40),
            lambda d: d["upstream"].update(tree="c" * 39),
            lambda d: d["upstream"].update(engineVersion="0.1.18-rc1"),
            lambda d: d.update(engineId="not-an-engine-id"),
        ):
            doc = json.loads(self.candidate_lock.read_text())
            mutate(doc)
            self.candidate_lock.write_text(json.dumps(doc))
            proc = run_stage(ENGINE_DIR, self.candidate_lock, self.out)
            self.assertEqual(proc.returncode, 2, proc.stderr + proc.stdout)
            self.assertFalse(self.out.exists(), "staged tree must not be written")

    def test_copy_tree_rejects_symlink_entries(self):
        src = self.root / "src"
        src.mkdir()
        (src / "real.txt").write_text("x")
        (src / "evil-link").symlink_to(HUB_ROOT / "LICENSE")
        with self.assertRaises(SystemExit):
            stage.copy_tree(src, self.root / "dst")


class TestCandidateIdentityProjection(unittest.TestCase):
    """Hosted preflight run 40622397082: the staged contract must carry the
    COMPLETE candidate identity — including the engine-probe verb's stdout and
    floeAdapterVersion derived from the crate Cargo.toml component version —
    so the UNCHANGED build_engine identity gate passes, while a candidate lock
    whose identity shape or version disagrees is refused before anything is
    written, and a 0.1.17 candidate keeps producing value-identical bytes."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.candidate_lock = self.root / "ENGINE-LOCK.json"
        write_candidate_lock(self.candidate_lock)
        self.out = self.root / "staged" / "hub"

    def staged_contract(self):
        return json.loads((self.out / "engines" / "impeccable" / "contract"
                           / "snapshot-contract.v1.json").read_text(encoding="utf-8"))

    def test_probe_identity_projected_and_receipt_hashes_match(self):
        proc = run_stage(ENGINE_DIR, self.candidate_lock, self.out)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        receipt = json.loads(proc.stdout)
        self.assertTrue(receipt["ok"])
        self.assertEqual(receipt["identitySelfCheck"], "passed")
        self.assertEqual(receipt["adapterVersion"], ADAPTER_CRATE_VERSION)
        self.assertEqual(receipt["componentVersion"],
                         f"{CANDIDATE_IDENTITY['version']}+floe.{ADAPTER_CRATE_VERSION}")
        fields = {c["field"]: c for c in receipt["contractChanges"]}
        probe_change = fields["verbs[engine-probe].stdout"]
        self.assertEqual(probe_change["before"], "impeccable-engine 0.1.17+floe.1.1.1\n")
        self.assertEqual(probe_change["after"],
                         f"impeccable-engine {CANDIDATE_IDENTITY['version']}"
                         f"+floe.{ADAPTER_CRATE_VERSION}\n")
        self.assertEqual(fields["engine.floeAdapterVersion"]["after"], ADAPTER_CRATE_VERSION)
        staged_bytes = (self.out / "engines" / "impeccable" / "contract"
                        / "snapshot-contract.v1.json").read_bytes()
        import hashlib
        self.assertEqual(hashlib.sha256(staged_bytes).hexdigest(),
                         receipt["stagedContractSha256"],
                         "the receipt hash must match the rewritten bytes")

    def test_staged_contract_passes_the_unchanged_identity_validator(self):
        proc = run_stage(ENGINE_DIR, self.candidate_lock, self.out)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        builder = load_module(TRACKED_BUILDER, "build_engine_identity_probe")
        staged_adapter = self.out / "engines" / "impeccable" / "adapter"
        adapter_version = builder.crate_adapter_version(staged_adapter)
        pin = {"commit": CANDIDATE_IDENTITY["commit"],
               "tree": CANDIDATE_IDENTITY["tree"],
               "engineVersion": CANDIDATE_IDENTITY["version"]}
        component = builder.verify_contract_identity(self.staged_contract(),
                                                     adapter_version, pin)
        self.assertEqual(component,
                         f"{CANDIDATE_IDENTITY['version']}+floe.{ADAPTER_CRATE_VERSION}")

    def test_refuses_lock_identity_disagreeing_with_the_canonical_derivation(self):
        cases = {
            "wrong crate suffix": "impeccable-0.1.18+floe.9.9.9",
            "wrong version part": "impeccable-0.9.9+floe.1.1.1",
            "malformed shape": "impeccable-0.1.18",
        }
        for label, engine_id in cases.items():
            with self.subTest(label):
                doc = json.loads(self.candidate_lock.read_text(encoding="utf-8"))
                doc["engineId"] = engine_id
                self.candidate_lock.write_text(json.dumps(doc))
                proc = run_stage(ENGINE_DIR, self.candidate_lock, self.out)
                self.assertEqual(proc.returncode, 2, proc.stderr + proc.stdout)
                self.assertFalse(self.out.exists(),
                                 "a refused candidate must stage nothing")

    def test_refuses_lock_floe_adapter_version_disagreeing_with_the_crate(self):
        doc = json.loads(self.candidate_lock.read_text(encoding="utf-8"))
        doc["floe"] = {"adapterVersion": "9.9.9"}
        self.candidate_lock.write_text(json.dumps(doc))
        proc = run_stage(ENGINE_DIR, self.candidate_lock, self.out)
        self.assertEqual(proc.returncode, 2, proc.stderr + proc.stdout)
        self.assertIn("floe.adapterVersion", json.loads(proc.stdout)["error"])
        self.assertFalse(self.out.exists())

    def test_published_0117_candidate_stages_value_identical_contract(self):
        # Re-staging the currently published pin must reproduce the tracked
        # contract values byte-for-byte in parsed form: full backward
        # compatibility of the projection for the 0.1.17 data.
        tracked_lock_copy = self.root / "tracked-lock.json"
        tracked_lock_copy.write_bytes(TRACKED_LOCK.read_bytes())
        proc = run_stage(ENGINE_DIR, tracked_lock_copy, self.out)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        receipt = json.loads(proc.stdout)
        self.assertTrue(receipt["ok"])
        self.assertEqual(self.staged_contract(),
                         json.loads(TRACKED_CONTRACT.read_text(encoding="utf-8")))
        self.assertEqual(receipt["trackedContractSha256"], receipt["stagedContractSha256"])
        # and the frozen tracked contract/lock themselves stay untouched
        self.assertEqual(TRACKED_LOCK.read_bytes(), tracked_lock_copy.read_bytes())


class TestStagedBuilderIntegration(unittest.TestCase):
    """No heavy build: a synthetic candidate source proves the staged builder
    passes verify_pin against the CANDIDATE lock (where the tracked builder
    fails the old pin) and reaches the patch/preflight boundary."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def make_candidate_source(self):
        origin = self.root / "origin.git"
        work = self.root / "upstream"
        subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(origin)],
                       check=True, env=BASE_ENV, cwd=str(self.root))
        subprocess.run(["git", "init", "-q", "-b", "main", str(work)],
                       check=True, env=BASE_ENV, cwd=str(self.root))
        subprocess.run(["git", "remote", "add", "origin", "../origin.git"],
                       check=True, env=BASE_ENV, cwd=str(work))
        (work / "ENGINE_VERSION").write_text(CANDIDATE_IDENTITY["version"] + "\n")
        (work / "package.json").write_text(json.dumps({"version": "4.7.1"}) + "\n")
        (work / "LICENSE").write_text("Apache-2.0\n")
        (work / "NOTICE.md").write_text("notices\n")
        filler = work / "crates" / "filler"
        filler.mkdir(parents=True)
        for i in range(1100):
            (filler / f"f{i}.rs").write_text("// filler\n")
        subprocess.run(["git", "add", "-A"], check=True, cwd=str(work), env=BASE_ENV)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                        "commit", "-qm", "synthetic candidate"],
                       check=True, cwd=str(work), env=BASE_ENV)
        sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                             text=True, check=True, cwd=str(work), env=BASE_ENV).stdout.strip()
        tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], capture_output=True,
                              text=True, check=True, cwd=str(work), env=BASE_ENV).stdout.strip()
        return sha, tree, work

    def run_builder(self, builder: Path, work: Path, tag: str):
        return subprocess.run(
            [sys.executable, str(builder), "--source", str(work),
             "--target", "riscv64gc-unknown-linux-musl", "--profile", "release",
             "--cargo-target-dir", str(self.root / f"target-{tag}"),
             "--build-dir", str(self.root / f"build-{tag}"),
             "--log-dir", str(self.root / f"logs-{tag}"),
             "--skip-build", "--allow-network"],
            capture_output=True, text=True, env=BASE_ENV, timeout=300)

    def test_staged_builder_verifies_candidate_and_reaches_patch_boundary(self):
        sha, tree, work = self.make_candidate_source()
        identity = dict(CANDIDATE_IDENTITY, commit=sha, tree=tree)
        candidate_lock = self.root / "ENGINE-LOCK.json"
        write_candidate_lock(candidate_lock, identity)
        staged_hub = self.root / "staged-hub"
        proc = run_stage(ENGINE_DIR, candidate_lock, staged_hub)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)

        # The tracked builder still enforces the OLD pin: same source, refused.
        tracked = self.run_builder(TRACKED_BUILDER, work, "tracked")
        self.assertEqual(tracked.returncode, 2, tracked.stdout + tracked.stderr)
        self.assertIn("source HEAD is not the pinned commit", tracked.stdout)

        # The staged builder accepts the candidate identity in the temp path
        # and stops at the patch boundary (tracked patch cannot apply to the
        # synthetic tree) — never building unpatched.
        staged = self.run_builder(staged_hub / "engines" / "impeccable" / "build"
                                  / "build_engine.py", work, "staged")
        self.assertEqual(staged.returncode, 2, staged.stdout + staged.stderr)
        self.assertIn(f"[pin] {sha}", staged.stdout)
        self.assertNotIn("[patches] applied", staged.stdout)
        self.assertIn("patch", (staged.stdout + staged.stderr).lower())


class TestBuildInvocationLint(unittest.TestCase):
    """Every real compile/audit invocation must bootstrap the network on a
    fresh runner and must never weaken the audit; the tracked builder is
    never invoked directly."""

    @classmethod
    def setUpClass(cls):
        cls.text = TEMPLATE_YML.read_text(encoding="utf-8")
        cls.lines = cls.text.splitlines()

    def run_blocks(self):
        block, start = None, 0
        for i, line in enumerate(self.lines, 1):
            if line.strip().startswith("run:"):
                if block is not None:
                    yield start, "\n".join(block)
                block, start = [], i
                continue
            if block is not None:
                indent = len(line) - len(line.lstrip())
                if line.strip() and indent <= 8:
                    yield start, "\n".join(block)
                    block = None
                    continue
                block.append(line)
        if block is not None:
            yield start, "\n".join(block)

    @staticmethod
    def commands_only(block: str) -> str:
        """Drop shell comment lines so lint checks govern commands, not prose."""
        return "\n".join(line for line in block.splitlines()
                         if not line.strip().startswith("#"))

    def test_every_build_engine_invocation_is_staged_and_online(self):
        invocations = [self.commands_only(b) for _, b in self.run_blocks()
                       if "build_engine.py" in b]
        self.assertEqual(len(invocations), 3, "preflight + riscv64 + host expected")
        for block in invocations:
            self.assertIn('"$RUNNER_TEMP/candidate-engine/hub/engines/impeccable/build/build_engine.py"',
                          block)
            self.assertIn("--allow-network", block)
            self.assertNotIn("--skip-dependency-audit", block)
            self.assertNotIn('"$ENGINE_DIR/build/build_engine.py"', block)

    def test_tracked_builder_never_invoked_anywhere(self):
        self.assertNotIn('"$ENGINE_DIR/build/build_engine.py"', self.text)

    def test_audit_never_skipped(self):
        for _, block in self.run_blocks():
            self.assertNotIn("--skip-dependency-audit", self.commands_only(block))

    def test_candidate_gates_use_the_staged_contract_and_inputs(self):
        self.assertIn('--contract "$RUNNER_TEMP/candidate-engine/hub/engines/impeccable/contract"',
                      self.text)
        self.assertIn('--adapter-data "$RUNNER_TEMP/candidate-engine/hub/engines/impeccable/adapter/tests/data"',
                      self.text)
        # the recorded goldens stay the tracked regression baseline
        self.assertIn('--expected "$ENGINE_DIR/contract/expected/riscv64-docker"', self.text)

    def test_golden_comparison_carries_identity_and_cross_arch_cli(self):
        self.assertIn('--candidate-lock "$RUNNER_TEMP/candidate-lock/ENGINE-LOCK.json"', self.text)
        self.assertIn('--build-tree "$RUNNER_TEMP/build"', self.text)
        self.assertIn("--docker-platform linux/riscv64", self.text)

    def test_failure_logs_are_uploaded_even_when_gates_fail(self):
        self.assertIn("if: always()", self.text)
        self.assertIn("impeccable-engine-candidate-failure-logs", self.text)


COMPARE_PY = TOOLS_DIR / "compare_expected.py"
compare = load_module(COMPARE_PY, "compare_expected")


class TestGoldenIdentityComparison(unittest.TestCase):
    """The four engine identity keys plus the two-key diagnostics mirror may
    differ between a golden and a legitimate newer candidate, and only where
    the diagnostics presence agrees; everything else still diffs exactly."""

    LOCK_ID = {
        "engine.upstreamEngineVersion": "0.1.18",
        "engine.upstreamCommit": "b" * 40,
        "engine.upstreamTree": "c" * 40,
        "engine.engineId": "impeccable-0.1.18+floe.1.0.0",
        "diagnostics.upstreamCommit": "b" * 40,
        "diagnostics.engineVersion": "0.1.18",
    }

    def engine_block(self, version="0.1.17", commit="a" * 40, tree="d" * 40):
        return {
            "binary": "floe-impeccable",
            "upstreamEngineVersion": version,
            "upstreamCommit": commit,
            "upstreamTree": tree,
            "engineId": f"impeccable-{version}+floe.1.0.0",
            "targetTriple": "riscv64gc-unknown-linux-musl",
            "abi": "static ELF, no dynamic loader dependency",
            "runtimeExecution": "riscv64-linux",
            "adapterCrateVersion": "1.0.0",
        }

    def diagnostics_block(self, version="0.1.17", commit="a" * 40):
        return {"strictSchema": True, "upstreamCommit": commit,
                "engineVersion": version}

    def golden_doc(self):
        return {"engine": self.engine_block(), "diagnostics": self.diagnostics_block(),
                "findings": [], "facts": {}, "coverage": {"passes": []},
                "verdict": "clean"}

    def candidate_doc(self):
        return {"engine": self.engine_block("0.1.18", "b" * 40, "c" * 40),
                "diagnostics": self.diagnostics_block("0.1.18", "b" * 40),
                "findings": [], "facts": {}, "coverage": {"passes": []},
                "verdict": "clean"}

    def early_doc(self, version="0.1.17", commit="a" * 40, tree="d" * 40):
        """The early-refusal shape: no diagnostics identity mirror at all."""
        return {"engine": self.engine_block(version, commit, tree), "findings": [],
                "facts": {}, "coverage": {"passes": []}, "verdict": "clean"}

    def test_candidate_metadata_only_passes_with_review_evidence(self):
        entry = compare.diff_documents("case1", self.golden_doc(), self.candidate_doc(),
                                       self.LOCK_ID, [])
        self.assertEqual(entry["state"], "identical")
        self.assertEqual(entry["differenceCount"], 0)
        self.assertFalse(entry["structuralDrift"])
        self.assertEqual(entry["diagnosticsIdentityPresence"],
                         {"golden": True, "candidate": True})
        self.assertEqual({c["field"] for c in entry["candidateIdentityChanges"]},
                         set(compare.IDENTITY_KEYS))
        self.assertEqual(len(entry["candidateIdentityChanges"]), 6)
        values = {c["field"]: (c["goldenValue"], c["candidateValue"])
                  for c in entry["candidateIdentityChanges"]}
        self.assertEqual(values["engine.upstreamEngineVersion"], ("0.1.17", "0.1.18"))
        self.assertEqual(values["engine.engineId"],
                         ("impeccable-0.1.17+floe.1.0.0",
                          "impeccable-0.1.18+floe.1.0.0"))
        self.assertEqual(values["diagnostics.upstreamCommit"], ("a" * 40, "b" * 40))
        self.assertEqual(values["diagnostics.engineVersion"], ("0.1.17", "0.1.18"))

    def test_wrong_candidate_identity_fails_closed(self):
        bad = self.candidate_doc()
        bad["engine"]["upstreamCommit"] = "f" * 40
        with self.assertRaises(SystemExit) as ctx:
            compare.diff_documents("case1", self.golden_doc(), bad, self.LOCK_ID, [])
        self.assertIn("does not match the staged candidate lock", str(ctx.exception.code))

    def test_missing_identity_field_fails_closed(self):
        bad = self.candidate_doc()
        del bad["engine"]["engineId"]
        with self.assertRaises(SystemExit) as ctx:
            compare.diff_documents("case1", self.golden_doc(), bad, self.LOCK_ID, [])
        self.assertIn("missing an engine identity field", str(ctx.exception.code))

    def test_diagnostics_forged_value_fails_closed(self):
        bad = self.candidate_doc()
        bad["diagnostics"]["engineVersion"] = "9.9.9"
        with self.assertRaises(SystemExit) as ctx:
            compare.diff_documents("case1", self.golden_doc(), bad, self.LOCK_ID, [])
        self.assertIn("diagnostics identity does not match", str(ctx.exception.code))

    def test_diagnostics_explicit_null_fails_closed(self):
        bad = self.candidate_doc()
        bad["diagnostics"]["engineVersion"] = None
        with self.assertRaises(SystemExit) as ctx:
            compare.diff_documents("case1", self.golden_doc(), bad, self.LOCK_ID, [])
        self.assertIn("null diagnostics identity field", str(ctx.exception.code))

    def test_incoherent_golden_diagnostics_mirror_fails_closed(self):
        for label, mutate in (
            ("commit mismatch",
             lambda d: d["diagnostics"].update(upstreamCommit="f" * 40)),
            ("version mismatch",
             lambda d: d["diagnostics"].update(engineVersion="9.9.9")),
            ("explicit null commit",
             lambda d: d["diagnostics"].update(upstreamCommit=None)),
            ("explicit null version",
             lambda d: d["diagnostics"].update(engineVersion=None)),
        ):
            with self.subTest(label):
                golden = self.golden_doc()
                mutate(golden)
                with self.assertRaises(SystemExit) as ctx:
                    compare.diff_documents("case1", golden, self.candidate_doc(),
                                           self.LOCK_ID, [])
                payload = json.loads(ctx.exception.code)
                self.assertEqual(payload["error"],
                                 "golden result carries an incoherent diagnostics identity mirror")
                self.assertIn("golden", payload["error"])

    def test_diagnostics_missing_one_key_fails_closed(self):
        bad = self.candidate_doc()
        del bad["diagnostics"]["engineVersion"]
        with self.assertRaises(SystemExit) as ctx:
            compare.diff_documents("case1", self.golden_doc(), bad, self.LOCK_ID, [])
        self.assertIn("only one of the two diagnostics identity keys",
                      str(ctx.exception.code))

    def test_early_refusal_without_diagnostics_on_both_sides_is_allowed(self):
        golden = self.early_doc()
        candidate = self.early_doc("0.1.18", "b" * 40, "c" * 40)
        entry = compare.diff_documents("case1", golden, candidate, self.LOCK_ID, [])
        self.assertEqual(entry["state"], "identical")
        self.assertEqual(entry["differenceCount"], 0)
        self.assertFalse(entry["structuralDrift"])
        self.assertEqual(entry["diagnosticsIdentityPresence"],
                         {"golden": False, "candidate": False})
        self.assertEqual({c["field"] for c in entry["candidateIdentityChanges"]},
                         set(compare.ENGINE_IDENTITY_KEYS))
        self.assertFalse(any(key.startswith("diagnostics.")
                             for key in (c["field"] for c in entry["candidateIdentityChanges"])))
        self.assertFalse(any(key.startswith("diagnostics.")
                             for key in (d["field"] for d in entry["differences"])))

    def test_diagnostics_presence_disagreement_is_structural_drift(self):
        full = self.candidate_doc()
        for label, golden, candidate in (
            ("golden full / candidate early",
             self.golden_doc(), self.early_doc("0.1.18", "b" * 40, "c" * 40)),
            ("golden early / candidate full", self.early_doc(), full),
        ):
            with self.subTest(label):
                entry = compare.diff_documents("case1", golden, candidate,
                                               self.LOCK_ID, [])
                self.assertEqual(entry["state"], "changed-unapproved")
                self.assertTrue(entry["structuralDrift"])
                self.assertEqual(entry["diagnosticsIdentityPresence"],
                                 {"golden": label.startswith("golden full"),
                                  "candidate": label.endswith("candidate full")})
                fields = {d["field"] for d in entry["differences"]}
                self.assertIn("diagnostics.upstreamCommit", fields)
                self.assertIn("diagnostics.engineVersion", fields)
                # the engine keys still authenticate as review evidence, but the
                # diagnostics presence mismatch is never an ignored identity move
                self.assertEqual({c["field"] for c in entry["candidateIdentityChanges"]},
                                 set(compare.ENGINE_IDENTITY_KEYS))

    def test_other_diagnostics_fields_still_diff_strictly(self):
        bad = self.candidate_doc()
        bad["diagnostics"]["strictSchema"] = False
        entry = compare.diff_documents("case1", self.golden_doc(), bad, self.LOCK_ID, [])
        self.assertEqual(entry["state"], "changed-unapproved")
        self.assertFalse(entry["structuralDrift"])
        self.assertEqual({d["field"] for d in entry["differences"]},
                         {"diagnostics.strictSchema"})

    def test_finding_change_still_fails(self):
        bad = self.candidate_doc()
        bad["findings"] = [{"rule": "radius-plain"}]
        entry = compare.diff_documents("case1", self.golden_doc(), bad, self.LOCK_ID, [])
        self.assertEqual(entry["state"], "changed-unapproved")
        self.assertEqual({d["field"] for d in entry["differences"]},
                         {"findings", "findings[0].rule"})

    def test_empty_container_changes_still_fail(self):
        for value in ([{}], {}, None):
            with self.subTest(value=value):
                bad = self.candidate_doc()
                bad["findings"] = value
                entry = compare.diff_documents("case1", self.golden_doc(), bad, self.LOCK_ID, [])
                self.assertEqual(entry["state"], "changed-unapproved")

    def test_missing_is_distinct_from_null(self):
        old = self.golden_doc()
        old["error"] = None
        entry = compare.diff_documents("case1", old, self.candidate_doc(), self.LOCK_ID, [])
        self.assertEqual(entry["state"], "changed-unapproved")
        self.assertIn("error", {d["field"] for d in entry["differences"]})

    def test_adapter_version_and_non_timing_fields_still_fail(self):
        for field in ("adapterCrateVersion", "runtimeExecution", "abi"):
            with self.subTest(field=field):
                bad = self.candidate_doc()
                bad["engine"][field] = "changed"
                entry = compare.diff_documents("case1", self.golden_doc(), bad, self.LOCK_ID, [])
                self.assertEqual(entry["state"], "changed-unapproved")
                self.assertIn("engine." + field, {d["field"] for d in entry["differences"]})

    def test_coverage_or_engine_target_change_still_fails(self):
        bad = self.candidate_doc()
        bad["engine"]["targetTriple"] = "aarch64-apple-darwin"
        entry = compare.diff_documents("case1", self.golden_doc(), bad, self.LOCK_ID, [])
        self.assertEqual(entry["state"], "changed-unapproved")
        self.assertTrue(any(d["field"] == "engine.targetTriple" for d in entry["differences"]))

    def test_lock_identity_shape_validation_fails_closed(self):
        with tempfile.TemporaryDirectory() as t:
            bad = Path(t) / "lock.json"
            bad.write_text(json.dumps({"engineId": "impeccable-0.1.18+floe.1.0.0",
                                       "upstream": {"commit": "z" * 40,
                                                    "tree": "c" * 40,
                                                    "engineVersion": "0.1.18"}}))
            with self.assertRaises(SystemExit):
                compare.load_lock_identity(bad)
            good = Path(t) / "good.json"
            good.write_text(json.dumps({"engineId": "impeccable-0.1.18+floe.1.0.0",
                                        "upstream": {"commit": "b" * 40,
                                                     "tree": "c" * 40,
                                                     "engineVersion": "0.1.18"}}))
            self.assertEqual(compare.load_lock_identity(good)["engine.engineId"],
                             "impeccable-0.1.18+floe.1.0.0")

    def test_cli_requires_candidate_lock(self):
        proc = subprocess.run([sys.executable, str(COMPARE_PY)],
                              capture_output=True, text=True, env=BASE_ENV, timeout=60)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--candidate-lock", proc.stderr)


class TestToolCliPreflight(unittest.TestCase):
    """Every public tool call in the workflow carries its mandatory flags and
    resolves to a real tool path — missing flags/paths fail here, not in CI."""

    MANDATORY = {
        "resolve_upstream_pin.py": ["--lock", "--upstream-repo", "--out"],
        "update_lock.py": ["--lock", "--commit"],
        "stage_candidate_engine.py": ["--engine-dir", "--candidate-lock", "--out"],
        "build_engine.py": ["--source", "--target", "--cargo-target-dir", "--log-dir"],
        "validate_fixtures.py": ["--contract", "--upstream"],
        "verify_engine_run.py": ["--binary", "--build-tree", "--contract",
                                 "--adapter-data", "--stage", "--out"],
        "compare_expected.py": ["--engine", "--contract", "--expected", "--out",
                                "--candidate-lock", "--build-tree", "--adapter-data"],
        "verify_published_baseline.py": ["--engine-dir", "--lock", "--out"],
        "export_expected.py": ["--stage", "--label", "--out"],
        "stage1_normalize_skill_source.py": ["--upstream", "--out", "--commit",
                                             "--tree", "--engine-lock"],
    }

    PATH_PREFIXES = {
        "$ENGINE_DIR": ENGINE_DIR,
        "$RUNNER_TEMP/candidate-engine/hub/engines/impeccable": ENGINE_DIR,
    }

    @classmethod
    def setUpClass(cls):
        cls.lines = TEMPLATE_YML.read_text(encoding="utf-8").splitlines()

    def run_blocks(self):
        block, start = None, 0
        for i, line in enumerate(self.lines, 1):
            if line.strip().startswith("run:"):
                if block is not None:
                    yield start, "\n".join(block)
                block, start = [], i
                continue
            if block is not None:
                indent = len(line) - len(line.lstrip())
                if line.strip() and indent <= 8:
                    yield start, "\n".join(block)
                    block = None
                    continue
                block.append(line)
        if block is not None:
            yield start, "\n".join(block)

    def test_every_tool_invocation_has_its_mandatory_flags(self):
        checked = 0
        for start, block in self.run_blocks():
            for tool, flags in self.MANDATORY.items():
                if tool not in block:
                    continue
                checked += 1
                for flag in flags:
                    self.assertIn(flag, block,
                                  f"line {start}: {tool} invocation misses {flag}")
        self.assertGreaterEqual(checked, len(self.MANDATORY),
                                "every tracked tool must be invoked somewhere")

    def test_invoked_tool_paths_resolve_on_disk(self):
        for start, block in self.run_blocks():
            for tool in self.MANDATORY:
                if tool not in block:
                    continue
                for raw in re.findall(r'"(\\?"?[^"\\]+\\.py)"', block):
                    path = raw
                    for prefix, real in self.PATH_PREFIXES.items():
                        if path.startswith(prefix):
                            path = str(real) + path[len(prefix):]
                            break
                    else:
                        continue  # RUNNER_TEMP-only paths exist only on the runner
                    self.assertTrue(Path(path).is_file(),
                                    f"line {start}: invoked tool missing on disk: {path}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
