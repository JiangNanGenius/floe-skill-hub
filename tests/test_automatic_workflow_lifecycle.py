#!/usr/bin/env python3
"""Workflow branch/CLI lifecycle tests for the cloud publication pipeline.

Offline only: isolated local Git fixtures (bare "origin" repositories over
file:// paths), the ACTUAL trusted module CLIs executed through the REAL step
bodies extracted from the three workflow YAMLs, and no network, no tokens
(only an inert fixture string), no pushes to any real remote. Unlike string
grep, each lifecycle bug this file guards was reproduced through the real
shell/Git sequence: primary checkouts wiped by branch swipes, orphan branches
carrying source/.github leftovers, relay payloads staged inside the worktree,
unauthenticated pushes, control transactions that stall busy forever on a
stale request, crash-after-push states (an X or H tip ahead of the open
request), sign jobs about to use the key against a moved base, and placeholder
artifact paths. Test-only environment variables point at a private candidate
workflow root and a read-only trusted hub root while a patch is under review;
with neither set, the normal repository root is used in CI.

    FLOE_SKILL_HUB_WORKFLOW_TEST_CANDIDATE_ROOT  root holding the YAMLs under test
    FLOE_SKILL_HUB_WORKFLOW_TEST_TRUSTED_ROOT    root holding scripts/ + docs/
"""
import argparse
import atexit
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_REPO = HERE.parent
TRUSTED = pathlib.Path(os.environ.get("FLOE_SKILL_HUB_WORKFLOW_TEST_TRUSTED_ROOT")
                       or DEFAULT_REPO).resolve()
CANDIDATE = pathlib.Path(os.environ.get("FLOE_SKILL_HUB_WORKFLOW_TEST_CANDIDATE_ROOT")
                         or str(TRUSTED)).resolve()

TRACKER_REL = ".github/workflows/skill-hub-upstream-tracker.yml"
PUBLISHER_REL = ".github/workflows/skill-hub-auto-publish.yml"
APP_REL = "automation/workflows/floe-skill-hub-auto-publication.yml"
DOCS_REL = "docs/AUTOMATIC-PUBLICATION.md"

TODAY = "2026-10-28"
RUN_ID = "9001"
FIXTURE_TOKEN = "fixture-token-never-used"
HEX64 = "ab" * 32
CANDIDATE_STAGING = "auto/candidate-2026-10-28-9001-1"
CANDIDATE_BRANCH = "auto/candidate-2026-10-28-9001-1"  # full branch under refs/heads/

sys.path.insert(0, str(TRUSTED / "scripts"))
try:
    import hubcore  # noqa: E402
    import automatic_publication as ap  # noqa: E402
    CORE = True
except Exception:  # pragma: no cover - CI installs the pinned library first
    hubcore = None
    ap = None
    CORE = False

HAS_GIT = shutil.which("git") is not None


def _git(where, *args, check=True):
    proc = subprocess.run(["git", "-C", str(where), *args],
                          capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise AssertionError(f"git {args} failed: {proc.stderr}")
    return proc


def _run_bash(script, cwd, env):
    return subprocess.run(["/bin/bash", "-c", script], cwd=str(cwd), env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, timeout=300)


# ---------------------------------------------------------------------------
# minimal GitHub-Actions-subset parser (stdlib only, no runtime dependency)
# ---------------------------------------------------------------------------

class Step:
    def __init__(self):
        self.name = ""
        self.id = ""
        self.uses = ""
        self.run = None
        self.env = {}
        self.with_ = {}
        self.cond = ""


def _set_field(step, key, value):
    target = {"name": "name", "id": "id", "uses": "uses", "if": "cond"}.get(key)
    if target is None:
        return
    setattr(step, target, value.strip())


def _scan_step_fields(lines, index, total, step):
    while index < total:
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if (re.match(r"^\S", line) or re.match(r"^  [A-Za-z0-9_-]+:", line)
                or re.match(r"^    [A-Za-z0-9_-]+:", line)
                or re.match(r"^      (- |\S)", line)):
            return index
        field = re.match(r"^        (name|id|uses|if|shell|continue-on-error):"
                         r"\s*(.*)$", line)
        if field:
            _set_field(step, field.group(1), field.group(2))
            index += 1
            continue
        run_head = re.match(r"^        run:\s*(.*)$", line)
        if run_head:
            head = run_head.group(1).strip()
            if head in ("|", "|-", "|+", ">", ">-", ">+"):
                index += 1
                body = []
                while index < total:
                    candidate = lines[index]
                    stripped = candidate.lstrip(" ")
                    indent = len(candidate) - len(stripped)
                    if candidate.strip() and indent >= 10:
                        body.append(candidate[10:])
                        index += 1
                        continue
                    if not candidate.strip():
                        body.append("")
                        index += 1
                        continue
                    break
                step.run = "\n".join(body).rstrip("\n") + "\n"
                continue
            step.run = head + "\n"
            index += 1
            continue
        block = re.match(r"^        (env|with):\s*$", line)
        if block:
            which = block.group(1)
            index += 1
            while index < total:
                pair = re.match(r"^          ([A-Za-z0-9_.-]+):\s*(.*)$",
                                lines[index])
                if pair:
                    target = step.env if which == "env" else step.with_
                    target[pair.group(1)] = pair.group(2).strip().strip('"')
                    index += 1
                    continue
                break
            continue
        index += 1
    return index


def _scan_steps(lines, index, total, job):
    while index < total:
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if re.match(r"^\S", line) or re.match(r"^  [A-Za-z0-9_-]+:", line):
            return index
        start = re.match(r"^      - (.*)$", line)
        if start:
            step = Step()
            job["steps"].append(step)
            first = re.match(r"^(name|id|uses|if):\s*(.*)$", start.group(1))
            if first:
                _set_field(step, first.group(1), first.group(2))
            index = _scan_step_fields(lines, index + 1, total, step)
            continue
        index += 1
    return index


def _scan_job(lines, index, total, job):
    while index < total:
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if re.match(r"^\S", line) or re.match(r"^  [A-Za-z0-9_-]+:\s*$", line):
            return index
        head = re.match(r"^    if:\s*(.*)$", line)
        if head:
            value = head.group(1).strip()
            if value in (">-", ">", "|", "|-"):
                index += 1
                parts = []
                while index < total:
                    candidate = lines[index]
                    if not candidate.strip():
                        index += 1
                        continue
                    stripped = candidate.lstrip(" ")
                    indent = len(candidate) - len(stripped)
                    if indent >= 6 and not re.match(r"^    [A-Za-z0-9_-]+:", candidate):
                        parts.append(stripped)
                        index += 1
                        continue
                    break
                job["if"] = " ".join(parts)
                continue
            job["if"] = value
            index += 1
            continue
        if re.match(r"^    steps:\s*$", line):
            index = _scan_steps(lines, index + 1, total, job)
            continue
        index += 1
    return index


def parse_workflow(text):
    """Parse the exact indentation style these three files use."""
    lines = text.split("\n")
    total = len(lines)
    index = 0
    while index < total and lines[index] != "jobs:":
        index += 1
    jobs = {}
    index += 1
    while index < total:
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if re.match(r"^\S", line):
            break
        head = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if head:
            job = {"if": "", "steps": []}
            jobs[head.group(1)] = job
            index = _scan_job(lines, index + 1, total, job)
            continue
        index += 1
    return jobs


def workflow_text(relative):
    path = CANDIDATE / relative
    return path.read_text() if path.is_file() else ""


TRACKER = workflow_text(TRACKER_REL)
PUBLISHER = workflow_text(PUBLISHER_REL)
APP = workflow_text(APP_REL)
DOCS = workflow_text(DOCS_REL)


def steps_of(text, job_name):
    jobs = parse_workflow(text)
    if job_name not in jobs:
        raise AssertionError(f"job {job_name} missing; parsed {sorted(jobs)}")
    return jobs[job_name]["steps"]


def step_named(text, job_name, needle):
    for step in steps_of(text, job_name):
        if needle.lower() in step.name.lower():
            return step
    raise AssertionError(f"step '{needle}' not found in job {job_name}")


def substitute(body, ctx):
    missing = []

    def replace(match):
        key = match.group(1).strip()
        if key in ctx:
            return str(ctx[key])
        missing.append(key)
        return match.group(0)

    out = re.sub(r"\$\{\{\s*([^{}]+?)\s*\}\}", replace, body)
    if missing:
        raise AssertionError(f"unsubstituted expressions: {sorted(set(missing))}")
    return out


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

SCRIPT_CLOSURE = [
    "automatic_publication.py", "automatic_transport.py", "build_catalog.py",
    "check_catalog.py", "hubcore.py", "publication_immutability.py",
    "runtime_dependency.py", "sign_publication.py", "upstream_pins.py",
    "upstream_updates.py", "dependency_declaration.py",
]


class RepoFixture:
    """bare origin + one primary checkout holding the trusted script closure."""

    def __init__(self, kind, trusted_scripts=True):
        self.kind = kind
        self.tmp = tempfile.TemporaryDirectory(prefix=f"floe-wf-{kind}-")
        root = pathlib.Path(self.tmp.name)
        self.root = root
        self.origin = root / f"{kind}.git"
        subprocess.run(["git", "init", "--bare", "-b", "main", str(self.origin)],
                       check=True, capture_output=True)
        self.workspace = root / kind
        self.workspace.mkdir()
        _git(self.workspace, "init", "-q", "-b", "main")
        _git(self.workspace, "config", "user.name", "fixture")
        _git(self.workspace, "config", "user.email", "fixture@invalid.invalid")
        if kind == "hub" and trusted_scripts:
            scripts = self.workspace / "scripts"
            scripts.mkdir()
            for name in SCRIPT_CLOSURE:
                source = TRUSTED / "scripts" / name
                if source.is_file():
                    shutil.copyfile(source, scripts / name)
            catalog = self.workspace / "catalog"
            catalog.mkdir()
            shutil.copyfile(TRUSTED / "catalog" / "upstream-update-policy.json",
                            catalog / "upstream-update-policy.json")
        (self.workspace / "README.md").write_text(f"floe {kind} fixture\n")
        if kind == "app":
            gh = self.workspace / ".github" / "workflows"
            gh.mkdir(parents=True)
            (gh / "sample-workflow.yml").write_text(
                "# fixture workflow that must never enter the relay branch\n")
            (self.workspace / ".gitignore").write_text("ignored/\n")
            (self.workspace / "ignored").mkdir()
            (self.workspace / "ignored" / "junk.txt").write_text("junk\n")
        _git(self.workspace, "add", "-A")
        _git(self.workspace, "commit", "-q", "-m", "fixture base")
        self.base = _git(self.workspace, "rev-parse", "HEAD").stdout.strip()
        _git(self.workspace, "remote", "add", "origin", self.origin_uri())
        _git(self.workspace, "push", "-q", "origin", "main")

    def origin_uri(self):
        return self.origin.as_uri()

    def cleanup(self):
        self.tmp.cleanup()

    def commit_tree(self, ref, files, message, parent=None, push=True):
        """push a constructed commit onto refs/heads/<ref> without a checkout"""
        index_file = self.root / f"index-{ref.replace('/', '_')}"
        env = dict(os.environ, GIT_INDEX_FILE=str(index_file),
                   GIT_AUTHOR_NAME="fixture",
                   GIT_AUTHOR_EMAIL="fixture@invalid.invalid",
                   GIT_COMMITTER_NAME="fixture",
                   GIT_COMMITTER_EMAIL="fixture@invalid.invalid")
        base = ["--git-dir", str(self.workspace / ".git")]
        subprocess.run(["git", *base, "read-tree", "--empty"], env=env, check=True)
        for rel, data in sorted(files.items()):
            blob = subprocess.run(["git", *base, "hash-object", "-w", "--stdin"],
                                  input=data, env=env, check=True,
                                  stdout=subprocess.PIPE).stdout.decode().strip()
            subprocess.run(["git", *base, "update-index", "--add", "--cacheinfo",
                            f"100644,{blob},{rel}"], env=env, check=True,
                           capture_output=True)
        tree = subprocess.run(["git", *base, "write-tree"], env=env, check=True,
                              stdout=subprocess.PIPE).stdout.decode().strip()
        commit_args = ["git", *base, "commit-tree", tree, "-m", message]
        if parent:
            commit_args += ["-p", parent]
        sha = subprocess.run(commit_args, env=env, check=True,
                             stdout=subprocess.PIPE).stdout.decode().strip()
        index_file.unlink(missing_ok=True)
        if push:
            _git(self.workspace, "push", "-q", "origin", f"{sha}:refs/heads/{ref}")
        return sha

    def fetch_ref(self, ref, local):
        _git(self.workspace, "-c", "gc.auto=0", "fetch", "-q", "--no-tags",
             self.origin_uri(), f"+refs/heads/{ref}:{local}")

    def tree_paths(self, rev):
        out = _git(self.workspace, "ls-tree", "-r", "--name-only", rev).stdout
        return sorted(line for line in out.splitlines() if line)

    def commit_subject(self, rev):
        return _git(self.workspace, "log", "-1", "--format=%s", rev).stdout.strip()


def default_ctx(fixture=None, **extra):
    ctx = {
        "github.sha": fixture.base if fixture else "0" * 40,
        "github.workspace": str(fixture.workspace) if fixture else "",
        "github.token": FIXTURE_TOKEN,
        "secrets.GITHUB_TOKEN": FIXTURE_TOKEN,
        "runner.temp": "",
        "github.run_id": RUN_ID,
        "inputs.dry_run": "false",
        "env.PYTHON_VERSION": "3.11",
        "steps.today.outputs.date": TODAY,
        "steps.recompute.outputs.today": TODAY,
        "steps.livebase.outputs.live": fixture.base if fixture else "0" * 40,
        "steps.precheck.outputs.proceed": "1",
        "steps.stale-guard.outputs.signed": "1",
    }
    ctx.update(extra)
    return ctx


def step_environment(fixture, work_dir, ctx, step, extra_env=None):
    runner_temp = work_dir / "runner-temp"
    runner_temp.mkdir(exist_ok=True)
    (work_dir / "home").mkdir(exist_ok=True)
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(work_dir / "home"),
        "TMPDIR": str(work_dir),
        "RUNNER_TEMP": str(runner_temp),
        "GITHUB_WORKSPACE": str(fixture.workspace),
        "GITHUB_OUTPUT": str(work_dir / "github_output"),
        "GITHUB_ENV": str(work_dir / "github_env"),
        "GITHUB_RUN_ID": RUN_ID,
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_REPOSITORY": "fixture/repo",
        "GITHUB_SERVER_URL": "https://github.invalid",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "HUB_ORIGIN": fixture.origin_uri(),
        "APP_ORIGIN": fixture.origin_uri(),
        "GH_TOKEN": FIXTURE_TOKEN,
        "TRUSTED": str(fixture.workspace),
    }
    for key, value in step.env.items():
        env[key] = substitute(value, ctx) if "${{" in value else value
    if extra_env:
        env.update(extra_env)
    return env


def outputs_of(work_dir):
    path = work_dir / "github_output"
    result = {}
    if path.is_file():
        for line in path.read_text().splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                result[key] = value
    return result


def run_extracted_step(fixture, work_dir, text, job_name, needle, ctx,
                        extra_env=None, expect_ok=True):
    step = step_named(text, job_name, needle)
    body = substitute(step.run, ctx)
    env = step_environment(fixture, work_dir, ctx, step, extra_env)
    proc = _run_bash(body, fixture.workspace, env)
    if expect_ok and proc.returncode != 0:
        raise AssertionError(
            f"step '{step.name}' failed rc={proc.returncode}\n{proc.stdout[-9000:]}")
    return step, proc, env


def build_request_bytes(mode, source_commit, base_publication):
    policy = (TRUSTED / "catalog" / "upstream-update-policy.json").read_bytes()
    return ap.build_request(mode, source_commit, base_publication, policy)


def manifest_bytes(request_doc, mode, source_commit, base, staging=CANDIDATE_STAGING):
    manifest = {
        "schemaVersion": 1, "mode": mode, "basePublication": base,
        "sourceCommit": source_commit, "stagingRef": staging,
        "requestId": request_doc["requestId"],
        "policySha256": request_doc["policySha256"],
        "stageToday": TODAY, "createdAtUTC": TODAY,
    }
    return json.dumps(manifest, sort_keys=True).encode()


# ---------------------------------------------------------------------------
# behaviour: tracker control branch lifecycle
# ---------------------------------------------------------------------------

@unittest.skipUnless(CORE and HAS_GIT, "trusted modules or git unavailable")
class TrackerControlLifecycle(unittest.TestCase):
    def setUp(self):
        self.fixture = RepoFixture("hub")
        self.work = pathlib.Path(self.fixture.root) / "wt"
        self.work.mkdir(exist_ok=True)
        self.ctx = default_ctx(self.fixture)

    def tearDown(self):
        self.fixture.cleanup()

    def make_held_stage(self):
        stage = self.work / "runner-temp" / "stage"
        (stage / "apply").mkdir(parents=True, exist_ok=True)
        (stage / "staging-manifest.json").write_text(json.dumps(
            {"candidateFacts": {"changedSkillIds": [], "bumpedVersions": {},
                                "pinAdvances": {},
                                "holdReasons": ["fixture-hold"]}}))
        (stage / "apply" / "manifest.json").write_text("[]")
        return stage

    def livebase_step(self):
        _, proc, _ = run_extracted_step(
            self.fixture, self.work, TRACKER, "track",
            "Resolve the live base freshly", self.ctx)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(outputs_of(self.work).get("action"), "live")

    def test_held_transaction_bootstraps_orphan_control_and_stays_bounded(self):
        self.make_held_stage()
        self.livebase_step()
        run_extracted_step(self.fixture, self.work, TRACKER, "track",
                           "Emit held-only state payload", self.ctx)
        run_extracted_step(self.fixture, self.work, TRACKER, "track",
                           "Transaction the control branch", self.ctx)
        self.fixture.fetch_ref("auto-state", "refs/test/auto-state")
        tip = _git(self.fixture.workspace, "rev-parse",
                   "refs/test/auto-state").stdout.strip()
        self.assertEqual(self.fixture.tree_paths(tip), ["state.json"])
        state = json.loads(_git(self.fixture.workspace, "show",
                                f"{tip}:state.json").stdout)
        self.assertEqual(state["pipelineStage"], "held")
        self.assertEqual(state["lastCheckUTC"], TODAY)
        # orphan bootstrap: the very first control commit's tree is EMPTY and
        # the source base commit is not an ancestor through a wiped checkout
        first = _git(self.fixture.workspace, "rev-list", "--max-parents=0",
                     tip).stdout.split()
        self.assertEqual(len(first), 1)
        self.assertEqual(self.fixture.tree_paths(f"{first[0]}"), [])
        # primary checkout intact: helpers still run from the trusted path
        self.assertEqual(_git(self.fixture.workspace, "rev-parse",
                              "HEAD").stdout.strip(), self.fixture.base)
        self.assertEqual(_git(self.fixture.workspace, "status",
                              "--porcelain").stdout, "")
        self.assertTrue((self.fixture.workspace / "scripts" /
                         "automatic_publication.py").is_file())
        # origin main untouched
        self.assertEqual(_git(self.fixture.workspace, "ls-remote",
                              self.fixture.origin_uri(), "refs/heads/main"
                              ).stdout.split()[0], self.fixture.base)
        # rerunning the same transaction is bounded (no duplicate commit)
        run_extracted_step(self.fixture, self.work, TRACKER, "track",
                           "Transaction the control branch", self.ctx)
        self.fixture.fetch_ref("auto-state", "refs/test/auto-state")
        self.assertEqual(_git(self.fixture.workspace, "rev-parse",
                              "refs/test/auto-state").stdout.strip(), tip)

    def test_orphan_bootstrap_commit_tree_produces_empty_tree(self):
        sha = self.fixture.commit_tree("probe-empty", {}, "empty probe")
        self.fixture.fetch_ref("probe-empty", "refs/test/probe")
        self.assertEqual(self.fixture.tree_paths("refs/test/probe"), [])
        del sha

    def test_noop_creates_nothing_when_control_absent(self):
        _, proc, _ = run_extracted_step(self.fixture, self.work, TRACKER,
                                        "track", "No-op checkpoint", self.ctx)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("no-op scan creates nothing", proc.stdout)
        self.assertEqual(_git(self.fixture.workspace, "ls-remote",
                              self.fixture.origin_uri(),
                              "refs/heads/auto-state").stdout.strip(), "")

    def test_noop_daily_checkpoint_is_bounded(self):
        self.fixture.commit_tree("auto-state",
                                 {"state.json": hubcore.encoded({"schemaVersion": 1})},
                                 "seed control")
        run_extracted_step(self.fixture, self.work, TRACKER, "track",
                           "No-op checkpoint", self.ctx)
        self.fixture.fetch_ref("auto-state", "refs/test/auto-state")
        tip1 = _git(self.fixture.workspace, "rev-parse", "refs/test/auto-state").stdout.strip()
        state = json.loads(_git(self.fixture.workspace, "show",
                                f"{tip1}:state.json").stdout)
        self.assertEqual(state["lastCheckUTC"], TODAY)
        self.assertEqual(state["pipelineStage"], "up-to-date")
        run_extracted_step(self.fixture, self.work, TRACKER, "track",
                           "No-op checkpoint", self.ctx)
        self.fixture.fetch_ref("auto-state", "refs/test/auto-state")
        self.assertEqual(_git(self.fixture.workspace, "rev-parse",
                              "refs/test/auto-state").stdout.strip(), tip1)

    def seed_open_request(self, base_publication, mode="reviews"):
        request_bytes, request_doc = build_request_bytes(
            mode, "1" * 40, base_publication)
        self.fixture.commit_tree("auto-state", {
            "request.json": request_bytes,
            "candidate-manifest.json": manifest_bytes(request_doc, mode, "1" * 40,
                                                      base_publication),
            "state.json": hubcore.encoded({
                "schemaVersion": 1,
                "openRequestId": request_doc["requestId"],
                "processedRequestIds": [],
            }),
        }, "seed open request")
        return request_doc

    def test_noop_stale_close_is_idempotent_and_archives(self):
        stale_base = "2" * 40
        request_doc = self.seed_open_request(stale_base)
        rid = request_doc["requestId"]
        run_extracted_step(self.fixture, self.work, TRACKER, "track",
                           "No-op checkpoint", self.ctx)
        self.fixture.fetch_ref("auto-state", "refs/test/auto-state")
        tip = _git(self.fixture.workspace, "rev-parse", "refs/test/auto-state").stdout.strip()
        paths = self.fixture.tree_paths(tip)
        self.assertNotIn("request.json", paths)
        self.assertNotIn("candidate-manifest.json", paths)
        self.assertIn(f"requests/{rid}/request.json", paths)
        self.assertIn(f"requests/{rid}/candidate-manifest.json", paths)
        state = json.loads(_git(self.fixture.workspace, "show",
                                f"{tip}:state.json").stdout)
        self.assertIn(rid, state["closedStaleRequestIds"])
        self.assertIsNone(state["openRequestId"])
        # idempotent: nothing further is recorded
        run_extracted_step(self.fixture, self.work, TRACKER, "track",
                           "No-op checkpoint", self.ctx)
        self.fixture.fetch_ref("auto-state", "refs/test/auto-state")
        self.assertEqual(_git(self.fixture.workspace, "rev-parse",
                              "refs/test/auto-state").stdout.strip(), tip)

    def test_transaction_supersedes_stale_with_candidate_payload(self):
        stale_base = "2" * 40
        request_doc = self.seed_open_request(stale_base)
        rid = request_doc["requestId"]
        policy = (TRUSTED / "catalog" / "upstream-update-policy.json").read_bytes()
        control_dir = self.work / "runner-temp" / "control"
        ap.control_payload(control_dir, base_commit=self.fixture.base,
                           candidate_commit="3" * 40, mode="reviews",
                           staging_ref=CANDIDATE_STAGING,
                           manifest_extra={"stageToday": TODAY}, today=TODAY,
                           policy_bytes=policy)
        run_extracted_step(self.fixture, self.work, TRACKER, "track",
                           "Transaction the control branch", self.ctx)
        self.fixture.fetch_ref("auto-state", "refs/test/auto-state")
        tip = _git(self.fixture.workspace, "rev-parse", "refs/test/auto-state").stdout.strip()
        paths = self.fixture.tree_paths(tip)
        self.assertIn("request.json", paths)
        self.assertIn(f"requests/{rid}/request.json", paths)
        new_request = json.loads(_git(self.fixture.workspace, "show",
                                      f"{tip}:request.json").stdout)
        self.assertNotEqual(new_request["requestId"], rid)
        state = json.loads(_git(self.fixture.workspace, "show",
                                f"{tip}:state.json").stdout)
        self.assertIn(rid, state["closedStaleRequestIds"])
        self.assertEqual(state["openRequestId"], new_request["requestId"])

    def test_failure_checkpoint_records_actionable_state(self):
        self.fixture.commit_tree("auto-state",
                                 {"state.json": hubcore.encoded({"schemaVersion": 1})},
                                 "seed control")
        run_extracted_step(self.fixture, self.work, TRACKER, "track",
                           "Failure checkpoint", self.ctx)
        self.fixture.fetch_ref("auto-state", "refs/test/auto-state")
        tip = _git(self.fixture.workspace, "rev-parse", "refs/test/auto-state").stdout.strip()
        state = json.loads(_git(self.fixture.workspace, "show",
                                f"{tip}:state.json").stdout)
        self.assertEqual(state["pipelineStage"], "scan-failed")
        self.assertIn("runs/", state["failedRunUrl"])
        self.assertEqual(self.fixture.tree_paths(tip), ["state.json"])

    def test_livebase_stale_event_exits_before_expensive_work(self):
        moved = self.fixture.commit_tree("main", {"README.md": b"advanced\n"},
                                         "live advanced", parent=self.fixture.base)
        _, proc, _ = run_extracted_step(
            self.fixture, self.work, TRACKER, "track",
            "Resolve the live base freshly",
            default_ctx(self.fixture, **{"github.sha": self.fixture.base}),
            expect_ok=True)
        outputs = outputs_of(self.work)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(outputs.get("action"), "stale-event")
        self.assertEqual(outputs.get("live"), moved)
        del moved


# ---------------------------------------------------------------------------
# behaviour: publisher route classification with freshly resolved live main
# ---------------------------------------------------------------------------

@unittest.skipUnless(CORE and HAS_GIT, "trusted modules or git unavailable")
class PublisherRouteClassification(unittest.TestCase):
    def setUp(self):
        self.fixture = RepoFixture("hub")
        self.work = pathlib.Path(self.fixture.root) / "rt"
        self.work.mkdir(exist_ok=True)
        self.ctx = default_ctx(self.fixture)

    def tearDown(self):
        self.fixture.cleanup()

    def run_route(self):
        step = step_named(PUBLISHER, "verify", "Route the open request")
        env = step_environment(self.fixture, self.work, self.ctx, step)
        proc = _run_bash(substitute(step.run, self.ctx), self.fixture.workspace, env)
        return proc, outputs_of(self.work)

    def seed_request(self, mode, source, base, processed=False):
        request_bytes, request_doc = build_request_bytes(mode, source, base)
        self.fixture.commit_tree("auto-state", {
            "request.json": request_bytes,
            "candidate-manifest.json": manifest_bytes(request_doc, mode, source, base),
            "state.json": hubcore.encoded({
                "schemaVersion": 1,
                "openRequestId": None if processed else request_doc["requestId"],
                "processedRequestIds": ([request_doc["requestId"]] if processed else []),
            }),
        }, "seed control")
        return request_doc

    def push_candidate(self, files, message, parent):
        return self.fixture.commit_tree(CANDIDATE_BRANCH, files, message,
                                        parent=parent)

    def test_idle_without_control(self):
        proc, outputs = self.run_route()
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(outputs["action"], "none")
        self.assertEqual(outputs["mode"], "none")

    def test_processed_request_is_idempotent_none(self):
        self.seed_request("reviews", "1" * 40, self.fixture.base, processed=True)
        proc, outputs = self.run_route()
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(outputs["action"], "none")

    def test_open_request_without_candidate_ref_fails_precisely(self):
        self.seed_request("reviews", "1" * 40, self.fixture.base)
        proc, _ = self.run_route()
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("no candidate ref tip", proc.stdout)

    def test_recover_catalog_when_tip_ahead_of_reviews_source(self):
        source = self.push_candidate({"catalog/skills.json": b"{}"}, "S", self.fixture.base)
        self.push_candidate({"catalog/skills.json": b"{}",
                             "reviews/a/1.0.0.review.json.sig": b"x"}, "X", source)
        self.seed_request("reviews", source, self.fixture.base)
        proc, outputs = self.run_route()
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(outputs["action"], "recover-catalog")
        self.assertEqual(outputs["sourceCommit"], source)
        self.assertEqual(outputs["requestId"],
                         build_request_bytes("reviews", source, self.fixture.base)[1]["requestId"])

    def test_recover_cas_when_tip_ahead_of_catalog_source_and_live_is_base(self):
        source = self.push_candidate({"catalog.json": b"{}"}, "X", self.fixture.base)
        self.push_candidate({"catalog.json": b"{}", "HISTORY.md": b"row\n"},
                            "H", source)
        self.seed_request("catalog", source, self.fixture.base)
        proc, outputs = self.run_route()
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(outputs["action"], "recover-cas")
        self.assertEqual(outputs["stagingRef"], CANDIDATE_STAGING)

    def test_recover_close_when_live_already_equals_tip_although_event_sha_stale(self):
        source = self.push_candidate({"catalog.json": b"{}"}, "X", self.fixture.base)
        published = self.push_candidate({"catalog.json": b"{}",
                                         "HISTORY.md": b"row\n"}, "H", source)
        self.seed_request("catalog", source, self.fixture.base)
        _git(self.fixture.workspace, "push", "-q", "origin",
             f"{published}:refs/heads/main")
        proc, outputs = self.run_route()
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(outputs["action"], "recover-close")

    def test_hold_when_unrelated_live_move(self):
        source = self.push_candidate({"catalog.json": b"{}"}, "X", self.fixture.base)
        self.push_candidate({"catalog.json": b"{}", "HISTORY.md": b"r\n"},
                            "H", source)
        unrelated = self.fixture.commit_tree("curation", {"catalog.json": b"other"},
                                             "manual curation", parent=self.fixture.base)
        self.seed_request("catalog", source, self.fixture.base)
        _git(self.fixture.workspace, "push", "-q", "origin",
             f"{unrelated}:refs/heads/main")
        proc, outputs = self.run_route()
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(outputs["action"], "hold")
        self.assertIn("stale-close owns", proc.stdout)

    def test_route_never_writes_and_origin_state_untouched(self):
        source = self.push_candidate({"catalog.json": b"{}"}, "X", self.fixture.base)
        self.seed_request("catalog", source, self.fixture.base)
        before = _git(self.fixture.workspace, "ls-remote",
                      self.fixture.origin_uri(), "refs/heads/auto-state").stdout
        proc, _ = self.run_route()
        self.assertEqual(proc.returncode, 0, proc.stdout)
        after = _git(self.fixture.workspace, "ls-remote",
                     self.fixture.origin_uri(), "refs/heads/auto-state").stdout
        self.assertEqual(before, after)


# ---------------------------------------------------------------------------
# behaviour: catalog continuation control write + control-state helpers
# ---------------------------------------------------------------------------

@unittest.skipUnless(CORE and HAS_GIT, "trusted modules or git unavailable")
class ContinuationAndStateProtocol(unittest.TestCase):
    def setUp(self):
        self.fixture = RepoFixture("hub")
        self.work = pathlib.Path(self.fixture.root) / "cc"
        self.work.mkdir(exist_ok=True)

    def tearDown(self):
        self.fixture.cleanup()

    def _cli(self, args, expect_rc=0):
        proc = subprocess.run(
            [sys.executable, str(self.fixture.workspace / "scripts" /
                                 "automatic_publication.py"), *args],
            cwd=str(self.fixture.workspace), capture_output=True, text=True)
        if expect_rc is not None:
            self.assertEqual(proc.returncode, expect_rc,
                             f"{args}: {proc.stdout[-1500:]} {proc.stderr[-1500:]}")
        return proc

    def test_catalog_continuation_processes_reviews_and_applies_catalog(self):
        source = self.fixture.commit_tree(CANDIDATE_BRANCH,
                                          {"catalog/skills.json": b"{}"},
                                          "S commit", parent=self.fixture.base)
        tip = self.fixture.commit_tree(CANDIDATE_BRANCH,
                                       {"catalog/skills.json": b"{}",
                                        "reviews/a/1.0.0.review.json.sig": b"x"},
                                       "X commit", parent=source)
        request_bytes, request_doc = build_request_bytes("reviews", source,
                                                         self.fixture.base)
        self.fixture.commit_tree("auto-state", {
            "request.json": request_bytes,
            "candidate-manifest.json": manifest_bytes(request_doc, "reviews",
                                                      source, self.fixture.base),
            "state.json": hubcore.encoded({
                "schemaVersion": 1,
                "openRequestId": request_doc["requestId"],
                "processedRequestIds": [],
            }),
        }, "seed open reviews request")
        policy = (TRUSTED / "catalog" / "upstream-update-policy.json").read_bytes()
        runner_temp = self.work / "runner-temp"
        runner_temp.mkdir(exist_ok=True)
        (runner_temp / "request.json").write_bytes(request_bytes)
        (runner_temp / "state.json").write_bytes(hubcore.encoded({
            "schemaVersion": 1,
            "openRequestId": request_doc["requestId"],
            "processedRequestIds": [],
        }))
        catalog_payload = runner_temp / "control-catalog"
        ap.control_payload(catalog_payload, base_commit=self.fixture.base,
                           candidate_commit=tip, mode="catalog",
                           staging_ref=CANDIDATE_STAGING,
                           manifest_extra={"stageToday": TODAY}, today=TODAY,
                           policy_bytes=policy)
        # the precheck step of the job fetched refs/floe/auto-state; do the
        # same here so the extracted control-write step runs its exact body
        self.fixture.fetch_ref("auto-state", "refs/floe/auto-state")
        ctx = default_ctx(self.fixture,
                          **{"needs.verify.outputs.requestId": request_doc["requestId"],
                             "needs.verify.outputs.stagingRef": CANDIDATE_STAGING,
                             "needs.verify.outputs.base": self.fixture.base,
                             "needs.verify.outputs.sourceCommit": source})
        step = step_named(PUBLISHER, "advance-x", "Write the catalog continuation")
        env = step_environment(self.fixture, self.work, ctx, step,
                               extra_env={"S_SHA": source, "X_SHA": tip,
                                          "REQ_ID": request_doc["requestId"],
                                          "BASE_SHA": self.fixture.base,
                                          "STAGING_REF": CANDIDATE_STAGING,
                                          "LIVE_BASE": self.fixture.base,
                                          "RUNNER_TEMP": str(runner_temp)})
        proc = _run_bash(substitute(step.run, ctx), self.fixture.workspace, env)
        self.assertEqual(proc.returncode, 0, proc.stdout[-12000:])
        self.fixture.fetch_ref("auto-state", "refs/test/auto-state")
        final = _git(self.fixture.workspace, "rev-parse", "refs/test/auto-state").stdout.strip()
        root_request = json.loads(_git(self.fixture.workspace, "show",
                                       f"{final}:request.json").stdout)
        state = json.loads(_git(self.fixture.workspace, "show",
                                f"{final}:state.json").stdout)
        self.assertEqual(root_request["mode"], "catalog")
        self.assertEqual(root_request["sourceCommit"], tip)
        self.assertIn(request_doc["requestId"], state["processedRequestIds"])
        self.assertEqual(state["openRequestId"], root_request["requestId"])
        paths = self.fixture.tree_paths(final)
        self.assertIn(f"requests/{request_doc['requestId']}/request.json", paths)
        self.assertIn(f"requests/{root_request['requestId']}/request.json", paths)
        # main untouched and the tip stayed the SAME original X
        self.assertEqual(_git(self.fixture.workspace, "ls-remote",
                              self.fixture.origin_uri(), "refs/heads/main"
                              ).stdout.split()[0], self.fixture.base)
        self.assertEqual(_git(self.fixture.workspace, "ls-remote",
                              self.fixture.origin_uri(),
                              f"refs/heads/{CANDIDATE_BRANCH}").stdout.split()[0], tip)

    def test_busy_checkpoint_keeps_inflight_state(self):
        request_bytes, request_doc = build_request_bytes("reviews", "1" * 40,
                                                         self.fixture.base)
        state_in = {"schemaVersion": 1, "openRequestId": request_doc["requestId"],
                    "processedRequestIds": [], "pipelineStage": "reviews-requested"}
        out = self.work / "planned-busy"
        state_path = self.work / "busy-state.json"
        request_path = self.work / "busy-open.json"
        state_path.write_bytes(hubcore.encoded(state_in))
        request_path.write_bytes(request_bytes)
        payload = self.work / "busy-payload"
        policy = (TRUSTED / "catalog" / "upstream-update-policy.json").read_bytes()
        ap.control_payload(payload, base_commit=self.fixture.base,
                           candidate_commit="3" * 40, mode="reviews",
                           staging_ref="auto/candidate-busy-1",
                           manifest_extra={"stageToday": TODAY}, today=TODAY,
                           policy_bytes=policy)
        self._cli(["plan-control-update", "--payload-dir", str(payload),
                   "--state-file", str(state_path),
                   "--request-file", str(request_path),
                   "--live-main", self.fixture.base, "--today", TODAY,
                   "--out", str(out)])
        plan = json.loads((out / "control-plan.json").read_bytes())
        self.assertEqual(plan["action"], "busy-checkpoint")
        self.assertEqual(plan["mirror"], ["state.json"])
        written = json.loads((out / "state.json").read_bytes())
        self.assertEqual(written["openRequestId"], request_doc["requestId"])
        self.assertEqual(written["pipelineStage"], "reviews-requested")
        self.assertIn("still in flight", written["note"])

    def test_mark_processed_is_idempotent_and_processed_check_exits_three(self):
        request_bytes, request_doc = build_request_bytes("catalog", "4" * 40,
                                                         self.fixture.base)
        state_path = self.work / "mp-state.json"
        request_path = self.work / "mp-request.json"
        out_path = self.work / "mp-new-state.json"
        state_path.write_bytes(hubcore.encoded({"schemaVersion": 1,
                                                "processedRequestIds": []}))
        request_path.write_bytes(request_bytes)
        for _ in range(2):
            self._cli(["mark-processed", "--state-file", str(state_path),
                       "--request-file", str(request_path),
                       "--out", str(out_path)])
            shutil.copyfile(out_path, state_path)
        written = json.loads(out_path.read_bytes())
        self.assertEqual(written["processedRequestIds"], [request_doc["requestId"]])
        proc = self._cli(["processed-check", "--state-file", str(state_path),
                          "--request-file", str(request_path)], expect_rc=3)
        self.assertIn('"processed": true', proc.stdout)
        other_state = self.work / "mp-other.json"
        other_state.write_bytes(hubcore.encoded({"schemaVersion": 1,
                                                 "processedRequestIds": []}))
        self._cli(["processed-check", "--state-file", str(other_state),
                   "--request-file", str(request_path)], expect_rc=0)

    def test_prune_requests_is_bounded_and_keeps_referenced_dirs(self):
        requests_dir = self.work / "requests"
        ids = [f"{i:064x}" for i in range(25)]
        for rid in ids:
            (requests_dir / rid).mkdir(parents=True)
            (requests_dir / rid / "request.json").write_text("{}")
        keep_open, keep_processed, keep_stale = ids[0], ids[1], ids[2]
        state_path = self.work / "prune-state.json"
        state_path.write_bytes(json.dumps({
            "schemaVersion": 1, "openRequestId": keep_open,
            "processedRequestIds": [keep_processed],
            "closedStaleRequestIds": [keep_stale]}).encode())
        self._cli(["prune-requests", "--requests-dir", str(requests_dir),
                   "--state-file", str(state_path)])
        remaining = sorted(p.name for p in requests_dir.iterdir())
        self.assertLessEqual(len(remaining), ap.REQUEST_HISTORY_KEEP)
        for rid in (keep_open, keep_processed, keep_stale):
            self.assertIn(rid, remaining)
        self.assertNotIn(ids[3], remaining)


# ---------------------------------------------------------------------------
# behaviour: App relay orphan lifecycle (metadata-only, primary intact)
# ---------------------------------------------------------------------------

@unittest.skipUnless(HAS_GIT, "git unavailable")
class AppRelayLifecycle(unittest.TestCase):
    RELAY = "skill-hub-signing-relay"

    def setUp(self):
        self.fixture = RepoFixture("app")
        self.work = pathlib.Path(self.fixture.root) / "ap"
        self.work.mkdir(exist_ok=True)
        self.ctx = default_ctx(self.fixture)
        self.runner_temp = self.work / "runner-temp"
        self.runner_temp.mkdir(exist_ok=True)

    def tearDown(self):
        self.fixture.cleanup()

    def make_download(self, *, symlink=False, stray=False):
        root = self.runner_temp / "relay-download" / "signing-relay"
        request_dir = root / "requests" / HEX64
        request_dir.mkdir(parents=True, exist_ok=True)
        for rel in ("request.json", "relay-manifest.json",
                    "signing-receipt.json", "signing-receipt.json.sig",
                    "catalog.sig", "android/catalog.sig"):
            target = request_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("fixture bytes\n")
        reviews = request_dir / "reviews" / "guide-skill"
        reviews.mkdir(parents=True, exist_ok=True)
        (reviews / "1.0.0.review.json.sig").write_text("sig\n")
        (root / "state.json").write_text("{}\n")
        if symlink:
            outside = self.runner_temp / "outside-secret-target"
            outside.write_text("never enter a data ref\n")
            (request_dir / "evil.sig").symlink_to(outside)
        if stray:
            (request_dir / "not-in-the-contract.json").write_text("nope\n")

    def run_relay_steps(self):
        bootstrap = step_named(APP, "relay", "Fetch or bootstrap the orphan")
        env = step_environment(self.fixture, self.work, self.ctx, bootstrap,
                               extra_env={"RELAY_BRANCH": self.RELAY})
        proc = _run_bash(substitute(bootstrap.run, self.ctx),
                         self.fixture.workspace, env)
        self.assertEqual(proc.returncode, 0, proc.stdout[-8000:])
        publish = step_named(APP, "relay", "Publish only signing-relay/ paths")
        env = step_environment(self.fixture, self.work, self.ctx, publish,
                               extra_env={"MODE": "reviews", "REQ_ID": HEX64,
                                          "RELAY_BRANCH": self.RELAY,
                                          "RUNNER_TEMP": str(self.runner_temp)})
        proc = _run_bash(substitute(publish.run, self.ctx),
                         self.fixture.workspace, env)
        return proc

    def relay_tip(self):
        return _git(self.fixture.workspace, "ls-remote", self.fixture.origin_uri(),
                    f"refs/heads/{self.RELAY}").stdout.split()[0]

    def test_relay_orphan_stays_metadata_only_and_primary_intact(self):
        self.make_download()
        proc = self.run_relay_steps()
        self.assertEqual(proc.returncode, 0, proc.stdout[-12000:])
        tip = self.relay_tip()
        self.fixture.fetch_ref(self.RELAY, "refs/test/relay")
        paths = self.fixture.tree_paths("refs/test/relay")
        self.assertTrue(paths)
        for path in paths:
            self.assertTrue(path.startswith("signing-relay/"), path)
            parts = path.split("/")
            if parts[1] == "requests":
                self.assertRegex(parts[2], r"^[0-9a-f]{64}$")
        self.assertNotIn("README.md", paths)
        self.assertNotIn(".gitignore", paths)
        self.assertFalse(any(p.startswith(".github") for p in paths))
        self.assertFalse(any("relay-download" in p for p in paths))
        self.assertIn("[skip ci]", self.fixture.commit_subject(tip))
        # App main untouched
        self.assertEqual(_git(self.fixture.workspace, "ls-remote",
                              self.fixture.origin_uri(), "refs/heads/main"
                              ).stdout.split()[0], self.fixture.base)
        # primary App checkout intact: the OLD recipe wiped these
        self.assertEqual(_git(self.fixture.workspace, "status",
                              "--porcelain").stdout, "")
        self.assertTrue((self.fixture.workspace / ".github" / "workflows" /
                         "sample-workflow.yml").is_file())
        self.assertTrue((self.fixture.workspace / "README.md").is_file())
        # re-publishing the same payload is idempotent
        second = self.run_relay_steps()
        self.assertEqual(second.returncode, 0, second.stdout[-8000:])
        self.assertEqual(self.relay_tip(), tip)

    def test_bootstrap_leaves_empty_tree_then_symlink_payload_rejected(self):
        bootstrap = step_named(APP, "relay", "Fetch or bootstrap the orphan")
        env = step_environment(self.fixture, self.work, self.ctx, bootstrap,
                               extra_env={"RELAY_BRANCH": self.RELAY,
                                          "RUNNER_TEMP": str(self.runner_temp)})
        proc = _run_bash(substitute(bootstrap.run, self.ctx),
                         self.fixture.workspace, env)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.fixture.fetch_ref(self.RELAY, "refs/test/relay")
        self.assertEqual(self.fixture.tree_paths("refs/test/relay"), [])
        after_bootstrap = self.relay_tip()
        self.make_download(symlink=True)
        failing = self.run_relay_steps()
        self.assertNotEqual(failing.returncode, 0)
        self.assertIn("symlink", failing.stdout)
        self.assertEqual(self.relay_tip(), after_bootstrap)

    def test_relay_rejects_stray_path(self):
        self.make_download(stray=True)
        proc = self.run_relay_steps()
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("refusing unexpected relay payload path", proc.stdout)
        # the branch may exist from the empty-tree bootstrap, but the stray
        # payload must never have been committed onto it
        self.fixture.fetch_ref(self.RELAY, "refs/test/relay")
        self.assertEqual(self.fixture.tree_paths("refs/test/relay"), [])


# ---------------------------------------------------------------------------
# behaviour: App sign-job stale-base guard
# ---------------------------------------------------------------------------

@unittest.skipUnless(HAS_GIT, "git unavailable")
class AppSignStaleBaseGuard(unittest.TestCase):
    def setUp(self):
        self.hub = RepoFixture("hub")
        self.work = pathlib.Path(self.hub.root) / "sg"
        self.work.mkdir(exist_ok=True)

    def tearDown(self):
        self.hub.cleanup()

    def run_guard(self, base_commit, origin_uri=None):
        ctx = default_ctx(self.hub)
        step = step_named(APP, "sign-reviews", "Stale-base guard")
        env = step_environment(self.hub, self.work, ctx, step,
                               extra_env={"BASE_COMMIT": base_commit,
                                          "HUB_ORIGIN": origin_uri or
                                          self.hub.origin_uri()})
        proc = _run_bash(substitute(step.run, ctx), self.hub.workspace, env)
        return proc, outputs_of(self.work)

    def test_guard_passes_when_live_equals_verified_base(self):
        proc, outputs = self.run_guard(self.hub.base)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(outputs.get("signed"), "1")

    def test_guard_holds_without_error_when_main_advanced(self):
        moved = self.hub.commit_tree("main", {"catalog.json": b"manual"},
                                     "manual curation", parent=self.hub.base)
        proc, outputs = self.run_guard(self.hub.base)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(outputs.get("signed"), "0")
        self.assertIn("HOLD", proc.stdout)
        self.assertIn(moved, proc.stdout)

    def test_guard_fails_precisely_on_unreachable_origin(self):
        proc, _ = self.run_guard(self.hub.base,
                                 origin_uri="file:///nonexistent/floe-fixtures/hub.git")
        self.assertNotEqual(proc.returncode, 0)
        self.assertTrue("does not appear to be a git repository" in proc.stdout
                        or "not exactly one line" in proc.stdout, proc.stdout[-3000:])


# ---------------------------------------------------------------------------
# structure: whole-surface invariants that cannot run locally
# ---------------------------------------------------------------------------

class StructuralInvariants(unittest.TestCase):
    def test_all_candidate_files_present_and_nonempty(self):
        for rel in (TRACKER_REL, PUBLISHER_REL, APP_REL, DOCS_REL):
            self.assertGreater(len(workflow_text(rel)), 500, rel)

    def test_every_run_script_is_bash_valid(self):
        checked = 0
        failures = []
        for label, text in ((TRACKER_REL, TRACKER), (PUBLISHER_REL, PUBLISHER),
                            (APP_REL, APP)):
            for job_name, job in parse_workflow(text).items():
                for step in job["steps"]:
                    if not step.run:
                        continue
                    scrubbed = re.sub(r"\$\{\{[^{}]*\}\}", "dummies", step.run)
                    proc = subprocess.run(["/bin/bash", "-n"], input=scrubbed,
                                          capture_output=True, text=True)
                    checked += 1
                    if proc.returncode != 0:
                        failures.append(f"{label}:{job_name}:{step.name}: "
                                        f"{proc.stderr.strip()}")
        self.assertEqual(failures, [])
        self.assertGreaterEqual(checked, 30)

    def test_jobs_are_var_guarded_and_workflows_read_default(self):
        for label, text in (("tracker", TRACKER), ("publisher", PUBLISHER),
                            ("app", APP)):
            jobs = parse_workflow(text)
            self.assertTrue(jobs)
            for job_name, job in jobs.items():
                self.assertIn("vars.FLOE_SKILL_HUB_AUTO", job["if"],
                              f"{label}/{job_name}")
            self.assertIn("permissions:\n  contents: read\n", text, label)
            self.assertNotIn("\n  push:\n", text, f"{label} push trigger")
            self.assertNotIn("self-hosted", text, label)

    def test_no_branch_swipe_or_orphan_checkout_anywhere(self):
        for label, text in (("tracker", TRACKER), ("publisher", PUBLISHER),
                            ("app", APP)):
            bodies = "\n".join(
                step.run or ""
                for job in parse_workflow(text).values() for step in job["steps"])
            self.assertNotIn("checkout --orphan", bodies, label)
            self.assertNotIn("checkout -q --orphan", bodies, label)
            self.assertNotIn("checkout -B ", bodies, label)
            self.assertNotIn("git rm -rqf", bodies, label)
            if label != "publisher":
                # only the two jobs that bootstrap orphan refs prove the
                # empty-tree commit path; the publisher consumes them
                self.assertIn("commit-tree", bodies, label)
                self.assertIn("hash-object -t tree /dev/null", bodies, label)

    def test_checkout_persist_credentials_always_false(self):
        for label, text in (("tracker", TRACKER), ("publisher", PUBLISHER),
                            ("app", APP)):
            for job_name, job in parse_workflow(text).items():
                for step in job["steps"]:
                    if "actions/checkout" in step.uses:
                        self.assertEqual(step.with_.get("persist-credentials"),
                                         "false",
                                         f"{label}/{job_name}/{step.name}")

    def test_push_targets_are_scoped_and_auth_env_only_where_used(self):
        allowed_ref_patterns = (
            "refs/heads/auto-state", "refs/heads/auto/candidate",
            "refs/heads/${RELAY_BRANCH}",
            "refs/heads/${{ steps.commit.outputs.ref }}",
            "refs/heads/${STAGING_REF}",
        )
        for label, text in (("tracker", TRACKER), ("publisher", PUBLISHER),
                            ("app", APP)):
            for job_name, job in parse_workflow(text).items():
                for step in job["steps"]:
                    body = step.run or ""
                    if "actions/checkout" in step.uses:
                        continue
                    has_push = bool(re.search(r"git[^\n]*\bpush\b", body))
                    if has_push:
                        self.assertIn("GH_TOKEN", step.env or {},
                                      f"{label}/{job_name}/{step.name}")
                        self.assertIn("credential.helper", body,
                                      f"{label}/{job_name}/{step.name}")
                    for line in body.splitlines():
                        if re.search(r"git[^\n]*\bpush\b", line):
                            self.assertTrue(
                                any(pattern in line for pattern in allowed_ref_patterns),
                                f"{label}/{job_name}/{step.name}: {line}")
                            self.assertNotIn("--force", line)
                            self.assertNotIn("refs/heads/main", line)
                            self.assertNotIn("refs/tags", line)

    def test_no_literal_token_values_in_helper_lines(self):
        helper = ("credential.helper='!f() { echo \"username=x-access-token\"; "
                  "echo \"password=${GH_TOKEN}\"; }; f'")
        for text in (TRACKER, PUBLISHER, APP):
            for line in text.splitlines():
                if "credential.helper" in line:
                    self.assertIn(helper, line, line)

    def test_token_env_and_cas_literals_survive(self):
        self.assertIn("python3 scripts/automatic_publication.py cas", PUBLISHER)
        self.assertIn("--token-env GITHUB_TOKEN", PUBLISHER)
        self.assertIn("GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}", PUBLISHER)
        self.assertIn("verify-public", PUBLISHER)
        self.assertNotIn("ANCHOR_PENDING", TRACKER)
        self.assertNotIn("ANCHOR_PENDING", PUBLISHER)
        self.assertIn("HUB_ANCHOR_COMMIT: \"ANCHOR_PENDING_ROOT_REVIEW_"
                      "00000000000000000000000000000000\"", APP)
        self.assertIn("${RELAY_BRANCH}:refs/heads/${RELAY_BRANCH}", APP)
        self.assertIn("group: floe-skill-hub-signing", APP)
        self.assertEqual(APP.count("FLOE_SKILL_HUB_SIGNING_KEY:"), 2)
        self.assertNotIn("FLOE_SKILL_HUB_SIGNING_KEY", TRACKER)
        self.assertNotIn("FLOE_SKILL_HUB_SIGNING_KEY", PUBLISHER)
        for text in (TRACKER, PUBLISHER, APP):
            for line in text.splitlines():
                if "uses: actions/" in line:
                    ref = line.split("uses:")[1].strip().split("@")[1].split("#")[0].strip()
                    self.assertRegex(ref, r"^[0-9a-f]{40}$", line)
        for line in APP.splitlines():
            if "run:" in line or "script" in line:
                self.assertNotIn("refs/heads/main", line, line)

    def test_candidate_gates_order_and_unsigned_s_never_signed_gates(self):
        names = [s.name for s in steps_of(TRACKER, "track")]

        def find(needle):
            for i, name in enumerate(names):
                if needle.lower() in name.lower():
                    return i
            raise AssertionError(needle)

        base_gates = find("full-repository gates on the clean BASE")
        apply_step = find("Apply the staged candidate")
        self.assertLess(base_gates, apply_step)
        for step in steps_of(TRACKER, "track")[apply_step + 1:]:
            body = step.run or ""
            for forbidden in ("check_catalog.py", "build_catalog.py",
                              "gen_schemas.py", "make_fixture.py",
                              "-m unittest discover"):
                self.assertNotIn(forbidden, body, step.name)
        combined = " ".join((s.run or "") for s in steps_of(TRACKER, "track"))
        self.assertIn("stage-build", combined)
        self.assertIn("emit-request", combined)
        self.assertIn("verify-candidate", combined)

    def test_rederive_and_actual_recover_cli_binding(self):
        combined = PUBLISHER + APP
        self.assertGreaterEqual(combined.count("rederive-candidate"), 5)
        # the draft-only prove-x-tip/prove-h-tip helpers never shipped in the
        # final core API (apiVersion 3); the workflows bind the ACTUAL
        # recover CLI and never a fabricated proof command
        for body in (TRACKER, PUBLISHER, APP):
            self.assertNotIn("prove-x-tip", body)
            self.assertNotIn("prove-h-tip", body)
        for step_body in (step_named(PUBLISHER, "advance-x", "Re-derive").run,
                          step_named(PUBLISHER, "recover-catalog",
                                     "Re-derive the tip").run,
                          step_named(PUBLISHER, "advance-publication",
                                     "Re-derive").run,
                          step_named(PUBLISHER, "recover-publish",
                                     "Re-derive the candidate's immutable").run):
            for flag in ("--repo-root", "--base-commit", "--candidate-commit",
                         "--today", "--stage-root"):
                self.assertIn(flag, step_body)
        x_proof = step_named(PUBLISHER, "recover-catalog",
                             "core recover proof").run
        h_proof = step_named(PUBLISHER, "recover-publish",
                             "core recover proof").run
        for body in (x_proof, h_proof):
            # the proof runs the REAL core CLI from the trusted live-base
            # worktree with the final parser's arguments
            self.assertIn('base-wt/scripts/automatic_publication.py" recover',
                          body)
            for flag in ("--request-file", "--manifest-file", "--live-main",
                         "--candidate-tip", "--stage-root", "--relay-dir"):
                self.assertIn(flag, body)
        self.assertIn('"reuse-x"', x_proof)
        self.assertNotIn("--x-root", x_proof)
        for flag in ("--x-root", '"cas-existing-h"', '"close-published"',
                     "publication-diffs-ok", "relay-ok", "candidate-ok"):
            self.assertIn(flag, h_proof)
        # close/cas derivation base is the REQUEST base (REQ_BASE), never the
        # live H; the OLD->NEW selections come from the candidate's committed
        # registry diff, never from live upstream HEADs
        rederive_h = step_named(PUBLISHER, "recover-publish",
                                "Re-derive the candidate's immutable").run
        self.assertIn('--base-commit "$REQ_BASE"', rederive_h)
        self.assertIn('--candidate-commit "$SOURCE_SHA"', rederive_h)
        # main advances ONLY through the core module's cas CLI with the token
        # strictly from the environment: no raw GraphQL duplication in YAML
        for body in (TRACKER, PUBLISHER, APP):
            for forbidden in ("mutation", "updateRefs(", "clientMutationId",
                              "refUpdates", "api.github.com", "query cas"):
                self.assertNotIn(forbidden, body)
        self.assertIn("--token-env GITHUB_TOKEN", PUBLISHER)
        # every production verify-public readback also attests the append-only
        # ledger prefix over the request base
        for body in (step_named(PUBLISHER, "advance-publication",
                                "Verify the actual public bytes").run,
                     step_named(PUBLISHER, "recover-publish",
                                "Verify the actual public bytes").run):
            self.assertIn("--base-commit", body)
        # the relay payload audit is one explicit regex mirroring the Python
        # whole-tree authority (no slash-crossing case globs that silently
        # shadow each other, shellcheck SC2221/SC2222)
        self.assertIn("RELAY_PATH_RE=", APP)
        self.assertIn("[0-9a-f]{64}", APP)
        # the tracker job outputs bind REAL producer steps (actionlint)
        self.assertNotIn("steps.emit.outputs", TRACKER)
        self.assertIn("steps.commit.outputs.requestId", TRACKER)
        for forbidden in ("--remote ", "--url ", "--force-push",
                          "redirect", "skip-verify"):
            self.assertNotIn(forbidden, PUBLISHER)
            self.assertNotIn(forbidden, APP)
            self.assertNotIn(forbidden, TRACKER)

    def test_no_fabricated_control_plan_fallback_and_fresh_live_binding(self):
        continuation = step_named(PUBLISHER, "advance-x",
                                  "Write the catalog continuation").run
        self.assertNotIn("catalog-continuation\",\"mirror\"", continuation)
        self.assertNotIn("STAGEREQ", PUBLISHER)
        self.assertIn("resolve_live_main", PUBLISHER)
        self.assertIn("resolve_live_main", TRACKER)
        live_refs = re.findall(r"steps\.livebase\.outputs\.(?:live|action)", TRACKER)
        self.assertGreaterEqual(len(live_refs), 8)

    def test_downloads_and_artifacts_are_real_and_outside_worktrees(self):
        for job_name, job in parse_workflow(APP).items():
            for step in job["steps"]:
                if "download-artifact" in step.uses:
                    path = step.with_.get("path", "")
                    self.assertTrue(path.startswith("${{ runner.temp }}"),
                                    f"{job_name}/{step.name}: {path}")
                if "upload-artifact" in step.uses:
                    self.assertEqual(step.with_.get("if-no-files-found"), "error")
                    self.assertNotIn("none", step.with_.get("path", "x"))
        evidence = step_named(APP, "orchestrate", "Stage verification evidence")
        for real in ("request.json", "candidate-manifest.json", "verdict.json",
                     "history.json"):
            self.assertIn(f"/{real}\"", evidence.run, real)
        self.assertIn("test -f", evidence.run)
        self.assertIn("test -n", evidence.run)

    def test_relay_commit_carries_skip_ci_but_signing_steps_never(self):
        relay_body = " ".join(s.run or "" for s in steps_of(APP, "relay"))
        self.assertEqual(relay_body.count("[skip ci]"), 2)
        for job_name in ("orchestrate", "sign-reviews", "sign-catalog"):
            body = " ".join(s.run or "" for s in steps_of(APP, job_name))
            self.assertNotIn("[skip ci]", body, job_name)
        # the trigger blocks never gained a push trigger from [skip ci] work
        self.assertIn("schedule:", APP)

    def test_sign_jobs_gate_every_key_touching_step_on_stale_guard(self):
        for job_name in ("sign-reviews", "sign-catalog"):
            steps = steps_of(APP, job_name)
            self.assertIn("Stale-base guard", steps[0].name)
            for step in steps[1:]:
                self.assertIn("stale-guard.outputs.signed == '1'", step.cond,
                              f"{job_name}/{step.name}")
        key_steps = [s for s in steps_of(APP, "sign-reviews")
                     if "FLOE_SKILL_HUB_SIGNING_KEY" in json.dumps(s.env)]
        self.assertEqual(len(key_steps), 1)

    def test_stale_guard_holds_before_key_without_skipping_verification(self):
        step = step_named(APP, "sign-catalog", "Stale-base guard")
        self.assertIn("ls-remote", step.run)
        self.assertIn("$BASE_COMMIT", step.run)
        self.assertIn("signed=0", step.run)
        self.assertNotIn("[skip ci]", step.run)

    def test_control_branch_tree_audit_is_closed_over_paths(self):
        self.assertGreaterEqual(
            PUBLISHER.count('allowed = ("state.json", "request.json", '
                            '"candidate-manifest.json")'), 3)
        self.assertIn("control branch path is outside the allowlist", PUBLISHER)
        self.assertIn("control branch carries a non-blob mode", PUBLISHER)
        tracker_audit = step_named(TRACKER, "track", "Transaction the control branch")
        self.assertIn("control branch path is outside the allowlist", tracker_audit.run)

    def test_relay_path_allowlist_regex_present_in_app(self):
        publish = step_named(APP, "relay", "Publish only signing-relay")
        self.assertIn("refusing non-allowlisted tracked path", publish.run)
        self.assertIn("relay branch carries a non-blob mode", publish.run)

    def test_public_docs_only_link_existing_public_paths(self):
        forbidden = ("PIPELINE-CONTRACT", "ROOT-ACCEPTANCE-CONTRACT",
                     "YAML-TRANSFER", "ROOT-LIVE-CAS-PROBE",
                     "ROOT-TRACKER-ACCEPTANCE", "REDERIVE",
                     "Local/Private", "skill-hub-auto-update",
                     "workflow-lifecycle", "job-0", "job-4")
        for needle in forbidden:
            self.assertNotIn(needle, DOCS, needle)
        for match in re.finditer(r"\]\(([^)#\s]+)", DOCS):
            target = match.group(1).strip()
            if target.startswith(("http://", "https://")):
                continue
            resolved = (CANDIDATE / "docs" / target).resolve()
            alt = (TRUSTED / "docs" / target).resolve()
            self.assertTrue(resolved.is_file() or alt.is_file(), target)

    def test_schedule_shapes_offset_from_peaks(self):
        tracker = re.search(r'cron: "([^"]+)"', TRACKER).group(1).split()
        self.assertNotEqual(tracker[0], "0")
        self.assertEqual(len(tracker[1].split(",")), 4)
        publisher = re.search(r'cron: "([^"]+)"', PUBLISHER).group(1).split()
        self.assertNotEqual(publisher[0].split(",")[0], "0")
        self.assertEqual(publisher[1], "*")
        app = re.search(r'cron: "([^"]+)"', APP).group(1).split()
        self.assertNotEqual(app[0].split(",")[0], "0")

    def test_no_optional_fetch_swallows_unexpected_network_failures(self):
        for label, text in (("tracker", TRACKER), ("publisher", PUBLISHER),
                            ("app", APP)):
            occurrences = re.findall(r'fetch --no-tags [^\n]*\|\| true', text)
            self.assertEqual(occurrences, [], f"{label}: {occurrences}")
            self.assertIn("couldn't find remote ref", text, label)


@unittest.skipUnless(CORE and HAS_GIT, "trusted modules or git unavailable")
class HeldStatePayloadFixture(unittest.TestCase):
    def test_held_state_cli_consumes_the_tracker_stage_shape(self):
        fixture = RepoFixture("hub")
        try:
            work = pathlib.Path(fixture.root) / "hs"
            work.mkdir()
            stage = work / "stage"
            (stage / "apply").mkdir(parents=True)
            (stage / "staging-manifest.json").write_text(json.dumps(
                {"candidateFacts": {"changedSkillIds": [],
                                    "bumpedVersions": {}, "pinAdvances": {},
                                    "holdReasons": ["fixture-hold"]}}))
            (stage / "apply" / "manifest.json").write_text("[]")
            out = work / "control"
            proc = subprocess.run(
                [sys.executable, str(fixture.workspace / "scripts" /
                                     "automatic_publication.py"), "held-state",
                 "--stage-root", str(stage), "--out", str(out), "--today", TODAY],
                capture_output=True, text=True, cwd=str(fixture.workspace))
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            state = json.loads((out / "state.json").read_bytes())
            self.assertEqual(state["pipelineStage"], "held")
            self.assertEqual(state["lastCheckUTC"], TODAY)
        finally:
            fixture.cleanup()


@unittest.skipUnless(HAS_GIT, "git unavailable")
class BashQuotingContract(unittest.TestCase):
    def test_token_helper_never_expands_at_argv_time(self):
        proc = subprocess.run(["/bin/bash", "-c",
                               "set -euo pipefail\n"
                               "GH_TOKEN=secretShouldNotAppear\n"
                               "git -c credential.helper='!f() { echo \"username=x-access-token\"; "
                               "echo \"password=${GH_TOKEN}\"; }; f' "
                               "config --get credential.helper"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("secretShouldNotAppear", proc.stdout)
        self.assertIn("${GH_TOKEN}", proc.stdout)

    def test_rejecting_while_pipeline_fails_the_step_under_set_e(self):
        proc = subprocess.run(
            ["/bin/bash", "-c",
             "set -euo pipefail\n"
             "tmp=$(mktemp -d); mkdir -p \"$tmp/dl\"\n"
             "printf 'evil\\n' > \"$tmp/dl/evil.txt\"\n"
             "find \"$tmp/dl\" -type f | while read -r f; do "
             "rel=\"${f#\"$tmp\"/dl/}\"; case \"$rel\" in ok) ;; "
             "*) echo \"refusing: $rel\" >&2; exit 1 ;; esac; done\n"
             "echo NOT-REACHED"],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("refusing: evil.txt", proc.stderr)
        self.assertNotIn("NOT-REACHED", proc.stdout)


# ---------------------------------------------------------------------------
# behaviour: optional-fetch failure semantics (Root-confirmed shell defect)
# ---------------------------------------------------------------------------

def fetch_helper_instances():
    """Every floe_fetch_optional helper body exactly as written in the YAMLs."""
    instances = []
    for label, text in (("tracker", TRACKER), ("publisher", PUBLISHER),
                        ("app", APP)):
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            m = re.match(r"^(\s*)floe_fetch_optional\(\) \{$", lines[i])
            if m:
                indent = m.group(1)
                j = i + 1
                while j < len(lines) and lines[j] != indent + "}":
                    j += 1
                if j >= len(lines):
                    raise AssertionError(f"{label}:{i + 1} unterminated helper")
                instances.append((label, i + 1,
                                  "\n".join(lines[i:j + 1]) + "\n"))
                i = j
            i += 1
    return instances


@unittest.skipUnless(HAS_GIT, "git unavailable")
class OptionalFetchFailureSemantics(unittest.TestCase):
    """Root-confirmed shell defect regression: `$?` after an if-compound with
    a false condition and no else branch is the compound's own 0, so the
    ORIGINAL helper turned a genuine fetch failure (network/DNS/auth) into a
    silent missing-ref no-op. Every helper copy in all three YAMLs must
    capture the real git status inside the else branch: a genuine failure
    exits NON-ZERO, while only the expected "couldn't find remote ref" stays
    a bounded idle 0."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="floe-wf-fetch-")
        root = pathlib.Path(self.tmp.name)
        self.origin = root / "origin.git"
        subprocess.run(["git", "init", "--bare", "-q", "-b", "main",
                        str(self.origin)], check=True, capture_output=True)
        # Both ordinary helpers and the App's `git -C tooling` helper run
        # inside disposable fixture repositories, never the real checkout.
        self.work = root / "work"
        self.work.mkdir()
        for checkout in (self.work, self.work / "tooling"):
            subprocess.run(["git", "init", "-q", "-b", "main", str(checkout)],
                           check=True, capture_output=True)
        self.bin_fail = self._shim(
            root / "bin-network-fail",
            "echo \"fatal: unable to access '$3/': Could not resolve host: "
            "github.com\" >&2\nexit 128\n")
        self.bin_missing = self._shim(
            root / "bin-missing-ref",
            "echo \"fatal: couldn't find remote ref refs/heads/whatever\" "
            ">&2\nexit 128\n")

    def tearDown(self):
        self.tmp.cleanup()

    def _shim(self, directory, body):
        directory.mkdir(parents=True)
        git = directory / "git"
        git.write_text("#!/bin/bash\n" + body)
        git.chmod(0o755)
        return directory

    def _run_helper(self, helper, origin, ref, path_prefix=None):
        env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null",
                   GIT_CONFIG_SYSTEM="/dev/null", GIT_TERMINAL_PROMPT="0")
        if path_prefix is not None:
            env["PATH"] = f"{path_prefix}{os.pathsep}{env.get('PATH', '')}"
        script = ("set -uo pipefail\n" + helper
                  + f'\nfloe_fetch_optional "{origin}" "{ref}"\nexit $?\n')
        return subprocess.run(["/bin/bash", "-c", script], cwd=self.work,
                              capture_output=True, text=True, env=env,
                              timeout=60)

    def test_helpers_fail_closed_on_genuine_error_and_idle_on_missing_ref(self):
        instances = fetch_helper_instances()
        self.assertEqual(len(instances), 8,
                         [(l, n) for l, n, _ in instances])
        for label, lineno, helper in instances:
            where = f"{label}:{lineno}"
            self.assertIn("else", helper,
                          f"{where}: helper lacks the else-branch rc capture")
            # 1) a FAILING fake git (genuine network-style failure) must make
            #    the helper exit non-zero — the original bug returned 0 here
            proc = self._run_helper(
                helper, "https://github.invalid/x.git",
                "+refs/heads/main:refs/floe/x", path_prefix=self.bin_fail)
            self.assertNotEqual(proc.returncode, 0,
                                f"{where}: genuine fetch failure must exit non-zero")
            self.assertIn("Could not resolve host", proc.stderr + proc.stdout)
            # 2) a fake git reporting the EXPECTED missing ref stays idle 0
            proc = self._run_helper(
                helper, "https://github.invalid/x.git",
                "+refs/heads/main:refs/floe/x", path_prefix=self.bin_missing)
            self.assertEqual(proc.returncode, 0,
                             f"{where}: missing-ref must stay a bounded idle no-op")
            self.assertIn("optional ref absent", proc.stdout)
            # 3) REAL git against a real file:// origin, ref genuinely absent
            proc = self._run_helper(helper, self.origin.as_uri(),
                                    "+refs/heads/never-exists:refs/floe/x")
            self.assertEqual(proc.returncode, 0,
                             f"{where}: real-git missing ref must idle")
            self.assertIn("optional ref absent", proc.stdout)

    def test_old_rc_capture_pattern_is_gone_from_every_workflow(self):
        for label, text in (("tracker", TRACKER), ("publisher", PUBLISHER),
                            ("app", APP)):
            self.assertNotIn("            fi\n            rc=$?\n", text,
                             f"{label} still carries the fail-open rc pattern")


# ---------------------------------------------------------------------------
# wire binding: every YAML CLI call matches the ACTUAL final core parser
# ---------------------------------------------------------------------------

@unittest.skipUnless(CORE, "trusted modules unavailable")
class FinalParserWireBinding(unittest.TestCase):
    """Small wire/parser/output regression against the FINAL core API
    (apiVersion 3): every automatic_publication.py invocation in the three
    YAMLs binds a real subcommand with real flags, and the recovery/proof
    commands keep their mandatory inputs. No fixture world, no network."""

    @staticmethod
    def _calls_in(text):
        calls = []
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            m = re.search(r"automatic_publication\.py\"?\s+([a-z][a-z-]+)(.*)$",
                          lines[i])
            if m:
                cmd = m.group(1)
                rest = m.group(2)
                cont = rest.rstrip().endswith("\\")
                flags = [t for t in rest.rstrip().rstrip("\\").split()
                         if t.startswith("--")]
                j = i
                while cont and j + 1 < len(lines):
                    j += 1
                    line = lines[j].strip()
                    cont = line.endswith("\\")
                    if cont:
                        line = line[:-1]
                    flags += [t for t in line.split() if t.startswith("--")]
                calls.append((cmd, flags, i + 1))
                i = j
            i += 1
        return calls

    @staticmethod
    def _subparsers():
        parser = ap.build_parser()
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                return action.choices
        raise AssertionError("no subparsers on the final parser")

    def test_every_yaml_cli_call_binds_the_final_parser(self):
        choices = self._subparsers()
        for label, text in (("tracker", TRACKER), ("publisher", PUBLISHER),
                            ("app", APP)):
            calls = self._calls_in(text)
            self.assertTrue(calls, f"{label}: no CLI calls found")
            for cmd, flags, lineno in calls:
                self.assertIn(cmd, choices,
                              f"{label}:{lineno} binds unknown subcommand {cmd!r}")
                allowed = {opt for a in choices[cmd]._actions
                           for opt in a.option_strings}
                for flag in flags:
                    self.assertIn(flag, allowed,
                                  f"{label}:{lineno} {cmd} does not accept {flag}")

    def test_final_recovery_api_shape(self):
        choices = self._subparsers()

        def required(cmd):
            return {a.dest for a in choices[cmd]._actions
                    if getattr(a, "required", False)}

        def opts(cmd):
            return {opt for a in choices[cmd]._actions for opt in a.option_strings}

        # recover: argv UNCHANGED per the final API card
        self.assertEqual(required("recover"),
                         {"request_file", "manifest_file", "live_main",
                          "candidate_tip", "stage_root"})
        self.assertIn("--relay-dir", opts("recover"))
        self.assertIn("--x-root", opts("recover"))
        # verify-published-chain: the full candidate proof inputs are MANDATORY
        self.assertEqual(required("verify-published-chain"),
                         {"base_commit", "x_commit", "y_commit", "h_commit",
                          "request_file", "relay_dir", "x_root", "stage_root",
                          "manifest_file"})
        # verify-public: optional --base-commit attests the ledger prefix
        self.assertIn("--base-commit", opts("verify-public"))
        self.assertNotIn("base_commit", required("verify-public"))
        # the removed draft helpers must not exist in the final parser
        self.assertNotIn("prove-x-tip", choices)
        self.assertNotIn("prove-h-tip", choices)
        # cas keeps the token strictly behind an environment-variable NAME
        self.assertIn("--token-env", opts("cas"))
        # rederive-candidate exposes no remote/url/only override
        for forbidden in ("--remote", "--url", "--only"):
            self.assertNotIn(forbidden, opts("rederive-candidate"))



if __name__ == "__main__":
    unittest.main(verbosity=2)
