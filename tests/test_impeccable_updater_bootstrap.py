#!/usr/bin/env python3
"""Bootstrap regression for the impeccable engine updater log directory.

Real failure (scheduled run 40462256034): the "Stage the candidate engine
tree" step pipes `stage_candidate_engine.py` into
`tee "$RUNNER_TEMP/logs/stage-candidate-engine.json"`. That tee is the first
write into `$RUNNER_TEMP/logs`, and on a fresh runner the directory does not
exist yet: `tee: ...: No such file or directory` failed the whole pipeline
under `set -euo pipefail` even though the staging script itself succeeded.
The repair creates `$RUNNER_TEMP/logs` with `mkdir -p` before the first log
write in both the installed root copy and the mirrored template.

These tests pin the repaired bootstrap in three independent ways:

1. structure — in every `build-and-verify` run block, no write into
   `"$RUNNER_TEMP/logs/` appears before `mkdir -p "$RUNNER_TEMP/logs"` in the
   same job, the staging block keeps `set -euo pipefail`, and nothing
   weakens failure propagation (`|| true`, `|| :`, `set +o pipefail`);
2. mirror equality — the template under `engines/impeccable/workflows/` and
   the installed copy under `.github/workflows/` stay byte-identical from
   `name:` onward, so a future fix cannot silently land on one side only;
3. behavior — the actual extracted `run:` block is executed locally with
   `/bin/bash` against the real staging tool and a copy of the tracked
   candidate lock in an ephemeral temp root: the fixed block stages and
   records the receipt; the same block with only the `mkdir -p` line removed
   reproduces the run-40462256034 failure (script succeeds, pipeline fails,
   no receipt file); and a genuinely failing staging run still fails the
   step with the failure receipt kept in the log.

Stdlib only. Run:

    python3 -m unittest discover -s tests -t tests -p "test_impeccable_updater_bootstrap.py"
    python3 tests/test_impeccable_updater_bootstrap.py

Set TMPDIR outside the hub checkout first (the staging tool refuses an
output root that resolves inside the tracked hub tree), e.g.
    TMPDIR=<private lane scratch> python3 tests/test_impeccable_updater_bootstrap.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "engines" / "impeccable" / "workflows" / "impeccable-engine-updater.yml"
ROOT_COPY = REPO / ".github" / "workflows" / "impeccable-engine-updater.yml"
TRACKED_LOCK = REPO / "engines" / "impeccable" / "ENGINE-LOCK.json"
BUILD_JOB = "build-and-verify"
NAME_KEY = "name: impeccable-engine-updater"

# A line that opens a file inside the shared run log directory. Comment
# lines never match because the patterns require the opening quote.
LOGS_MKDIR_RE = re.compile(r'^\s*(?:[^#]*\s)?mkdir -p "\$RUNNER_TEMP/logs"?\s*$')
LOGS_WRITE_RE = re.compile(r'"\$RUNNER_TEMP/logs[/"$]')
PIPE_STRENGTHEN_FORBIDDEN = ("|| true", "|| :", "set +o pipefail", "set +e", "set +u")


def workflow_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def run_blocks(text: str):
    """Yield (job, step_name, block_lines) for every `run: |` block, in order.

    Pure text parsing: `jobs:` keys sit at indent 2, steps at indent 6, and
    block bodies are the lines indented deeper than the `run: |` marker.
    """
    lines = text.splitlines()
    in_jobs = False
    job = None
    step = None
    i = 0
    while i < len(lines):
        line = lines[i]
        if line == "jobs:":
            in_jobs = True
            i += 1
            continue
        if in_jobs and re.match(r"^[A-Za-z0-9_.-]+:", line):
            in_jobs = False  # next top-level key ends the jobs mapping
        if not in_jobs:
            i += 1
            continue
        job_match = re.match(r"^  ([A-Za-z0-9_.-]+):\s*$", line)
        if job_match:
            job = job_match.group(1)
            step = None
            i += 1
            continue
        step_match = re.match(r"^      - (?:.*?name:\s*(.*)|uses:\s*(\S+)|id:\s*(\S+))", line)
        if step_match:
            step = next(g for g in step_match.groups() if g)
            i += 1
            continue
        if line.strip() == "run: |":
            body = []
            i += 1
            while i < len(lines):
                cur = lines[i]
                if cur.strip() == "" or (len(cur) - len(cur.lstrip())) >= 10:
                    body.append(cur)
                    i += 1
                else:
                    break
            yield job, step, body
            continue
        i += 1


def staging_block(path: Path) -> str:
    """The exact repaired run block of the staging step, as shell text."""
    for job, step, body in run_blocks(workflow_text(path)):
        if job != BUILD_JOB or not step or "Stage the candidate engine tree" not in step:
            continue
        return "\n".join(body) + "\n"
    raise AssertionError(f"staging step not found in {path}")


class TestWorkflowStructure(unittest.TestCase):
    def test_mirror_bodies_identical(self):
        template = workflow_text(TEMPLATE)
        root = workflow_text(ROOT_COPY)
        self.assertEqual(template[template.index(NAME_KEY):],
                         root[root.index(NAME_KEY):],
                         "the installed root copy and the mirrored template must stay "
                         "byte-identical from the name: key onward")

    def test_no_logs_write_before_the_logs_dir_is_created(self):
        for path in (TEMPLATE, ROOT_COPY):
            text = workflow_text(path)
            # RUNNER_TEMP is per job: track the mkdir per job, in step order.
            created: dict = {}
            for job, step, body in run_blocks(text):
                for lineno, line in enumerate(body):
                    if line.lstrip().startswith("#"):
                        continue
                    if LOGS_MKDIR_RE.match(line):
                        created[job] = (step, lineno)
                    elif LOGS_WRITE_RE.search(line):
                        self.assertIn(job, created,
                                      f"{path.name}: {job}/{step!r} writes into "
                                      f"$RUNNER_TEMP/logs before any step creates the "
                                      f"directory (run 40462256034 shape): {line.strip()}")

    def test_staging_block_creates_logs_before_the_first_tee(self):
        for path in (TEMPLATE, ROOT_COPY):
            block = staging_block(path)
            lines = [ln for ln in block.splitlines() if not ln.lstrip().startswith("#")]
            flat = "\n".join(lines)
            mkdirs = [k for k, ln in enumerate(lines) if LOGS_MKDIR_RE.match(ln)]
            tees = [k for k, ln in enumerate(lines) if 'tee "$RUNNER_TEMP/logs' in ln]
            self.assertEqual(len(mkdirs), 1, f"{path.name}: exactly one logs mkdir expected")
            self.assertEqual(len(tees), 1, f"{path.name}: exactly one first tee expected")
            self.assertLess(mkdirs[0], tees[0],
                            f"{path.name}: tee must not precede mkdir -p \"$RUNNER_TEMP/logs\"")
            self.assertEqual(lines[0].strip(), "set -euo pipefail",
                             f"{path.name}: staging block must keep pipefail")
            for forbidden in PIPE_STRENGTHEN_FORBIDDEN:
                self.assertNotIn(forbidden, flat,
                                 f"{path.name}: {forbidden!r} would weaken real failure "
                                 f"propagation")

    def test_staging_is_the_first_logs_consumer_job_wide(self):
        for path in (TEMPLATE, ROOT_COPY):
            seen_write = False
            first_step = None
            for job, step, body in run_blocks(path.read_text(encoding="utf-8")):
                if job != BUILD_JOB:
                    continue
                for line in body:
                    if line.lstrip().startswith("#"):
                        continue
                    if LOGS_WRITE_RE.search(line) and not seen_write:
                        first_step, seen_write = step, True
            self.assertTrue(seen_write)
            self.assertIn("Stage the candidate engine tree", first_step)


class TestRealBootstrapBehavior(unittest.TestCase):
    """Execute the actual extracted run block against the real staging tool."""

    BLOCK = staging_block(ROOT_COPY)
    CANDIDATE = json.loads(TRACKED_LOCK.read_text(encoding="utf-8"))["upstream"]["commit"]

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="impeccable-bootstrap-"))
        self.runner_temp = self.tmp / "runner-temp"
        self.runner_temp.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def prepare_candidate_lock(self, contents: str | None = None):
        lock_dir = self.runner_temp / "candidate-lock"
        lock_dir.mkdir(parents=True, exist_ok=True)
        target = lock_dir / "ENGINE-LOCK.json"
        if contents is None:
            shutil.copyfile(TRACKED_LOCK, target)
        else:
            target.write_text(contents, encoding="utf-8")

    def run_block(self, block: str) -> subprocess.CompletedProcess:
        script = self.tmp / "staging-step.sh"
        script.write_text(block, encoding="utf-8")
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(self.tmp),
            "RUNNER_TEMP": str(self.runner_temp),
            "ENGINE_DIR": "engines/impeccable",
            "CANDIDATE_COMMIT": self.CANDIDATE,
            "TMPDIR": str(self.tmp),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        return subprocess.run(["/bin/bash", str(script)], cwd=str(REPO),
                              env=env, capture_output=True, text=True, timeout=600)

    def staged_marker(self):
        return self.runner_temp / "candidate-engine" / "hub" / "engines" / "impeccable" / "ENGINE-LOCK.json"

    def test_fixed_block_stages_and_records_the_receipt(self):
        self.prepare_candidate_lock()
        result = self.run_block(self.BLOCK)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        receipt = self.runner_temp / "logs" / "stage-candidate-engine.json"
        self.assertTrue(receipt.is_file(), "the tee receipt must land in the created logs dir")
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["candidate"]["commit"], self.CANDIDATE)
        self.assertTrue(self.staged_marker().is_file(), "the staged candidate tree must exist")

    def test_block_without_the_mkdir_reproduces_the_run_failure(self):
        # Same block, only the bootstrap mkdir removed: the staging script
        # still succeeds, but tee cannot open its target and pipefail fails
        # the step — exactly the scheduled run 40462256034 shape.
        self.assertIn('mkdir -p "$RUNNER_TEMP/logs"', self.BLOCK)
        broken = self.BLOCK.replace('mkdir -p "$RUNNER_TEMP/logs"\n', "", 1)
        self.assertNotIn('mkdir -p "$RUNNER_TEMP/logs"', broken)
        self.prepare_candidate_lock()
        result = self.run_block(broken)
        self.assertNotEqual(result.returncode, 0,
                            "without the logs dir the tee must still fail the pipeline")
        self.assertIn("No such file or directory", result.stderr)
        self.assertIn("tee", result.stderr)
        self.assertTrue(self.staged_marker().is_file(),
                        "the staging script itself must have succeeded")
        stdout_json = json.loads(result.stdout)
        self.assertTrue(stdout_json["ok"],
                        "the script succeeded while the pipeline failed: the tee "
                        "bootstrap, not staging, is the cause")
        self.assertFalse((self.runner_temp / "logs" / "stage-candidate-engine.json").exists())

    def test_genuine_staging_failure_still_fails_the_step_with_receipt(self):
        # pipefail propagation survives the fix: an unusable candidate lock
        # makes the tool exit non-zero, the step must fail, and the failure
        # JSON must still be recorded in the log directory.
        self.prepare_candidate_lock('{"engineId": "not-an-impeccable-id"}\n')
        result = self.run_block(self.BLOCK)
        self.assertNotEqual(result.returncode, 0,
                            "mkdir -p must not mask a real staging failure")
        self.assertEqual(result.returncode, 2)
        receipt = self.runner_temp / "logs" / "stage-candidate-engine.json"
        self.assertTrue(receipt.is_file(), "the failed gate still leaves a receipt")
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertFalse(payload["ok"])
        self.assertFalse(self.staged_marker().exists(),
                         "an invalid candidate must stage nothing")


if __name__ == "__main__":
    unittest.main(verbosity=2)
