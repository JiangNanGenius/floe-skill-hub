#!/usr/bin/env python3
"""Regressions for the PR-only candidate-reuse and draft-PR controller.

Covers the review's required shapes with compact synthetic fixtures:

* the real verifier accepts the complete synthetic proof and emits the tiny
  metadata payload;
* wrong repository/workflow/branch/attempt/conclusion, a skipped build job, a
  missing gate, an ambiguous routed comparison, an expired/extra/bad-digest
  artifact, a wrong pin/status/native-payload zip, unsafe zip paths and a
  wrong-machine ELF all fail closed;
* the real commit path uses a real temporary Git remote, the corrected
  `git -c key=value` identity form, commits only `ENGINE-LOCK.json`, and a real
  Git failure propagates (no `|| exit 0`);
* an existing matching draft PR is reported without a write, a conflicting
  branch / non-draft PR / user file edit is held without force, and a matching
  branch that lost its PR is re-proposed;
* the new review workflow is dispatch-only, read-only for verification, grants
  write only to the draft-PR job, honors the existing switch, pins actions and
  interpolates no expression into `run:` text.

The fixture never executes the artifact binary and never touches a real remote.
"""

from __future__ import annotations

import copy
import hashlib
import http.server
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.parse
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
TOOLS_DIR = HERE.parent
ENGINE_DIR = TOOLS_DIR.parent.parent
HUB_ROOT = ENGINE_DIR.parent.parent
sys.path.insert(0, str(TOOLS_DIR))
sys.path.insert(0, str(HERE))

import review_fixture as fixture  # noqa: E402
import verify_candidate_reuse as verify  # noqa: E402

VERIFY_PY = TOOLS_DIR / "verify_candidate_reuse.py"
PR_PY = TOOLS_DIR / "open_review_pr.py"
REVIEW_YML = HUB_ROOT / ".github" / "workflows" / "impeccable-engine-review.yml"
UPDATER_TEMPLATE = ENGINE_DIR / "workflows" / "impeccable-engine-updater.yml"
UPDATER_ROOT = HUB_ROOT / ".github" / "workflows" / "impeccable-engine-updater.yml"

BASE_ENV = {
    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
    "HOME": os.environ.get("HOME", "/tmp"),
    "GIT_CONFIG_NOSYSTEM": "1",
}

GIT_IDENTITY = ("-c", "user.name=floe-skill-hub-bot",
                "-c", "user.email=bot@users.noreply.github.com")


class ReviewHarness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.fixture = fixture.make_repo(cls.root / "repo")
        cls.repo = cls.fixture["root"]
        cls.artifact_root = cls.root / "artifact"
        cls.base_zip = fixture.build_artifact(cls.artifact_root, cls.fixture)
        cls.api = fixture.build_api(cls.root / "api-root", cls.fixture, cls.base_zip)
        cls.api_dir = cls.api["dir"]
        cls.original = {
            "run": json.loads((cls.api_dir / "run.json").read_text()),
            "jobs": json.loads((cls.api_dir / "jobs.json").read_text()),
            "artifacts": json.loads((cls.api_dir / "artifacts.json").read_text()),
        }
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), cls.handler())
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]
        cls.happy = cls._run_cli("happy")
        cls.happy_work = cls.happy[2]
        cls.happy_out = cls.happy[3]
        cls.metadata = json.loads(cls.happy_out.read_text()) if cls.happy_out.exists() else None

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    @classmethod
    def handler(cls):
        api_dir = cls.api_dir

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                path = urllib.parse.urlsplit(self.path).path
                mapping = {
                    f"/repos/{verify.OFFICIAL_REPOSITORY}/actions/runs/{fixture.RUN_ID}": "run.json",
                    f"/repos/{verify.OFFICIAL_REPOSITORY}/actions/runs/{fixture.RUN_ID}/jobs": "jobs.json",
                    f"/repos/{verify.OFFICIAL_REPOSITORY}/actions/runs/{fixture.RUN_ID}/artifacts": "artifacts.json",
                    f"/repos/{verify.OFFICIAL_REPOSITORY}/actions/artifacts/{fixture.ARTIFACT_ID}/zip": "candidate.zip",
                }
                relative = mapping.get(path)
                if relative is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                data = (api_dir / relative).read_bytes()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        return Handler

    @classmethod
    def _run_cli(cls, name: str):
        work = cls.root / "runs" / name / "work"
        work.parent.mkdir(parents=True, exist_ok=True)
        out = work.parent / "out.json"
        command = [
            sys.executable, str(VERIFY_PY),
            "--repository", verify.OFFICIAL_REPOSITORY,
            "--run-id", str(fixture.RUN_ID),
            "--engine-dir", str(cls.repo / "engines" / "impeccable"),
            "--repo-root", str(cls.repo),
            "--work-dir", str(work),
            "--out", str(out),
            "--api-base", f"http://127.0.0.1:{cls.port}",
        ]
        proc = subprocess.run(command, capture_output=True, text=True,
                              env=BASE_ENV, timeout=120)
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            payload = {"ok": False, "error": proc.stdout + "\n" + proc.stderr}
        return proc, payload, work, out

    def run_cli(self, name: str):
        return self._run_cli(name)

    def write_api(self, name: str, document) -> None:
        (self.api_dir / name).write_text(json.dumps(document, indent=2) + "\n",
                                         encoding="utf-8")

    def restore_api(self) -> None:
        for name, document in self.original.items():
            self.write_api(f"{name}.json", document)
        shutil.copyfile(self.base_zip, self.api_dir / "candidate.zip")

    def rebuild_zip(self, mutate) -> None:
        with zipfile.ZipFile(self.base_zip) as archive:
            entries = {name: archive.read(name) for name in archive.namelist()}
        mutate(entries)
        with zipfile.ZipFile(self.api_dir / "candidate.zip", "w",
                             zipfile.ZIP_DEFLATED) as archive:
            for name, data in entries.items():
                info = zipfile.ZipInfo(name)
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data)
        zip_path = self.api_dir / "candidate.zip"
        artifacts = copy.deepcopy(self.original["artifacts"])
        artifacts["artifacts"][0]["size_in_bytes"] = zip_path.stat().st_size
        artifacts["artifacts"][0]["digest"] = \
            "sha256:" + hashlib.sha256(zip_path.read_bytes()).hexdigest()
        self.write_api("artifacts.json", artifacts)

    def cli_refusal(self, name: str, expected: str) -> None:
        proc, payload, _, _ = self.run_cli(name)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertFalse(payload.get("ok"), payload)
        self.assertIn(expected, payload.get("error", ""), payload)


class TestCandidateReuseProof(ReviewHarness):
    def test_happy_path_emits_verified_metadata(self):
        proc, payload, work, out = self.happy
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(payload.get("ok"), payload)
        self.assertEqual(payload["headSha"], self.fixture["run_head"])
        self.assertEqual(payload["route"], "published")
        metadata = json.loads(out.read_text())
        self.assertEqual(metadata["schema"], verify.METADATA_SCHEMA)
        self.assertEqual(metadata["candidate"], fixture.CANDIDATE)
        self.assertEqual(metadata["baseline"]["engineId"], fixture.BASE_ENGINE_ID)
        self.assertEqual(metadata["buildJob"]["comparisonRoute"], "published")
        self.assertEqual(metadata["protectedInputs"]["paths"],
                         list(verify.PROTECTED_PATHS))
        self.assertRegex(metadata["lockProposalSha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(metadata["lockProposal"],
                         verify.expected_candidate_lock(self.fixture["base_lock"],
                                                        fixture.CANDIDATE))
        # The emitted payload is exactly the gate the write job uses.
        verify.validate_metadata_payload(metadata, self.repo, verify.OFFICIAL_REPOSITORY)
        # The extracted artifact contains the candidate binary and no executable bit.
        binary = work / "artifact" / "dist" / fixture.CANDIDATE["engineId"] / \
            verify.TARGET_TRIPLE / "floe-impeccable"
        self.assertTrue(binary.is_file())
        self.assertFalse(binary.stat().st_mode & 0o111)

    def test_wrong_repository_is_refused(self):
        run = copy.deepcopy(self.original["run"])
        run["repository"]["full_name"] = "evil/repo"
        self.write_api("run.json", run)
        self.addCleanup(self.restore_api)
        self.cli_refusal("wrong-repo", "fixed official repository")

    def test_wrong_workflow_path_is_refused(self):
        run = copy.deepcopy(self.original["run"])
        run["path"] = ".github/workflows/other.yml"
        self.write_api("run.json", run)
        self.addCleanup(self.restore_api)
        self.cli_refusal("wrong-path", "not .github/workflows/impeccable-engine-updater.yml")

    def test_non_main_or_rerun_context_is_refused(self):
        for name, mutate, expected in (
            ("wrong-branch", lambda run: run.__setitem__("head_branch", "feature"),
             "did not execute on main"),
            ("pull-request", lambda run: run.__setitem__("event", "pull_request"),
             "not a trusted updater trigger"),
            ("attempt-two", lambda run: run.__setitem__("run_attempt", 2),
             "only the original successful attempt"),
        ):
            run = copy.deepcopy(self.original["run"])
            mutate(run)
            self.write_api("run.json", run)
            try:
                self.cli_refusal(name, expected)
            finally:
                self.restore_api()

    def test_skipped_build_job_is_refused(self):
        jobs = copy.deepcopy(self.original["jobs"])
        build = next(job for job in jobs["jobs"] if job["name"] == verify.BUILD_JOB_NAME)
        build["conclusion"] = "skipped"
        self.write_api("jobs.json", jobs)
        self.addCleanup(self.restore_api)
        self.cli_refusal("skipped-build", "build job did not succeed")

    def test_missing_gate_is_refused(self):
        jobs = copy.deepcopy(self.original["jobs"])
        build = next(job for job in jobs["jobs"] if job["name"] == verify.BUILD_JOB_NAME)
        build["steps"] = [step for step in build["steps"]
                          if step["name"] != "Contract coherence gate"]
        self.write_api("jobs.json", jobs)
        self.addCleanup(self.restore_api)
        self.cli_refusal("missing-gate", "required build step")

    def test_ambiguous_routed_comparison_is_refused(self):
        jobs = copy.deepcopy(self.original["jobs"])
        build = next(job for job in jobs["jobs"] if job["name"] == verify.BUILD_JOB_NAME)
        for step in build["steps"]:
            if step["name"] == verify.HISTORICAL_COMPARISON_STEP:
                step["conclusion"] = "success"
        self.write_api("jobs.json", jobs)
        self.addCleanup(self.restore_api)
        self.cli_refusal("two-routes", "exactly one routed comparison")

    def test_expired_artifact_is_refused(self):
        artifacts = copy.deepcopy(self.original["artifacts"])
        artifacts["artifacts"][0]["expired"] = True
        artifacts["artifacts"][0]["expires_at"] = "2000-01-01T00:00:00Z"
        self.write_api("artifacts.json", artifacts)
        self.addCleanup(self.restore_api)
        self.cli_refusal("expired", "expired")

    def test_bad_artifact_digest_is_refused(self):
        artifacts = copy.deepcopy(self.original["artifacts"])
        artifacts["artifacts"][0]["digest"] = "sha256:" + "0" * 64
        self.write_api("artifacts.json", artifacts)
        self.addCleanup(self.restore_api)
        self.cli_refusal("bad-digest", "downloaded artifact digest")

    def test_extra_canonical_artifact_is_refused(self):
        artifacts = copy.deepcopy(self.original["artifacts"])
        artifacts["artifacts"].append(copy.deepcopy(artifacts["artifacts"][0]))
        self.write_api("artifacts.json", artifacts)
        self.addCleanup(self.restore_api)
        self.cli_refusal("two-artifacts", "exactly one 'impeccable-engine-candidate'")

    def test_native_payload_in_dist_is_refused(self):
        def mutate(entries):
            name = f"dist/{fixture.CANDIDATE['engineId']}/{verify.TARGET_TRIPLE}/native-tool"
            entries[name] = b"\x7fELF" + b"\x00" * 64
        self.rebuild_zip(mutate)
        self.addCleanup(self.restore_api)
        self.cli_refusal("native-payload", "dist file set is unexpected")

    def test_zip_traversal_is_refused(self):
        def mutate(entries):
            entries["../evil"] = b"escape"
        self.rebuild_zip(mutate)
        self.addCleanup(self.restore_api)
        self.cli_refusal("traversal", "traverses outside")

    def test_wrong_machine_elf_is_refused(self):
        def mutate(entries):
            binary_name = (f"dist/{fixture.CANDIDATE['engineId']}/"
                           f"{verify.TARGET_TRIPLE}/floe-impeccable")
            data = bytearray(entries[binary_name])
            data[18:20] = (62).to_bytes(2, "little")  # x86-64
            entries[binary_name] = bytes(data)
            sums_name = (f"dist/{fixture.CANDIDATE['engineId']}/"
                         f"{verify.TARGET_TRIPLE}/SHA256SUMS.txt")
            new_sha = hashlib.sha256(bytes(data)).hexdigest()
            lines = []
            for line in entries[sums_name].decode().splitlines():
                digest, name = line.split("  ", 1)
                lines.append(f"{new_sha if name == 'floe-impeccable' else digest}  {name}")
            entries[sums_name] = ("\n".join(lines) + "\n").encode()
        self.rebuild_zip(mutate)
        self.addCleanup(self.restore_api)
        self.cli_refusal("wrong-machine", "not RISC-V")

    def test_changed_proposal_status_is_refused(self):
        def mutate(entries):
            name = "candidate-lock/ENGINE-LOCK.json"
            lock = json.loads(entries[name])
            lock["status"] = "ready"
            entries[name] = (json.dumps(lock, indent=2, ensure_ascii=False) + "\n").encode()
        self.rebuild_zip(mutate)
        self.addCleanup(self.restore_api)
        self.cli_refusal("status", "reviewed pin fields")

    def test_bad_sha256sums_is_refused(self):
        def mutate(entries):
            name = (f"dist/{fixture.CANDIDATE['engineId']}/"
                    f"{verify.TARGET_TRIPLE}/SHA256SUMS.txt")
            lines = entries[name].decode().splitlines()
            lines[0] = "0" * 64 + "  " + lines[0].split("  ", 1)[1]
            entries[name] = ("\n".join(lines) + "\n").encode()
        self.rebuild_zip(mutate)
        self.addCleanup(self.restore_api)
        self.cli_refusal("bad-sums", "does not verify")

    def _commit_drift(self, path: Path, payload: bytes) -> None:
        path.write_bytes(payload)
        subprocess.run(["git", "-C", str(self.repo), "add", str(path.relative_to(self.repo))],
                       check=True, env=fixture.GIT_ENV)
        subprocess.run(["git", "-C", str(self.repo), *GIT_IDENTITY, "commit", "-qm",
                        "fixture drift"], check=True, env=fixture.GIT_ENV)

    def _reset_fixture(self) -> None:
        subprocess.run(["git", "-C", str(self.repo), "reset", "-q", "--hard",
                        self.fixture["head"]], check=True, env=fixture.GIT_ENV)
        subprocess.run(["git", "-C", str(self.repo), "clean", "-fdq"],
                       check=True, env=fixture.GIT_ENV)

    def test_published_baseline_drift_is_refused(self):
        # The fixture's published baseline is a protected input; changing it
        # after the run must invalidate the proof.
        baseline = (self.repo / "engines/impeccable/dist" / fixture.BASE_ENGINE_ID /
                    verify.TARGET_TRIPLE / "floe-impeccable")
        self._commit_drift(baseline, baseline.read_bytes() + b"\x00")
        try:
            proc, payload, _, _ = self.run_cli("baseline-drift")
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            self.assertIn("protected engine inputs drifted", payload.get("error", ""))
        finally:
            self._reset_fixture()

    def test_recipe_prefix_drift_is_refused(self):
        updater = self.repo / ".github/workflows/impeccable-engine-updater.yml"
        original = updater.read_text()
        self._commit_drift(updater, original.replace(
            "name: impeccable-engine-updater", "name: changed-recipe", 1).encode())
        try:
            proc, payload, _, _ = self.run_cli("prefix-drift")
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            self.assertIn("updater recipe above open-update-pr changed",
                          payload.get("error", ""))
        finally:
            self._reset_fixture()

    def test_in_process_gate_refusals(self):
        jobs = copy.deepcopy(self.original["jobs"])
        build = next(job for job in jobs["jobs"] if job["name"] == verify.BUILD_JOB_NAME)
        for step in build["steps"]:
            if step["name"] == verify.HISTORICAL_COMPARISON_STEP:
                step["conclusion"] = "success"
        with self.assertRaises(verify.Refusal):
            verify.verify_jobs(jobs["jobs"], self.fixture["run_head"])

        jobs = copy.deepcopy(self.original["jobs"])
        build = next(job for job in jobs["jobs"] if job["name"] == verify.BUILD_JOB_NAME)
        build["steps"] = [step for step in build["steps"]
                          if step["name"] != "Contract coherence gate"]
        with self.assertRaises(verify.Refusal):
            verify.verify_jobs(jobs["jobs"], self.fixture["run_head"])

        artifacts = copy.deepcopy(self.original["artifacts"])
        artifacts["artifacts"].append(copy.deepcopy(artifacts["artifacts"][0]))
        with self.assertRaises(verify.Refusal):
            verify.verify_artifacts(artifacts["artifacts"], fixture.RUN_ID,
                                    self.fixture["run_head"])

    def test_historical_route_is_accepted(self):
        jobs = copy.deepcopy(self.original["jobs"])
        build = next(job for job in jobs["jobs"] if job["name"] == verify.BUILD_JOB_NAME)
        for step in build["steps"]:
            if step["name"] == verify.PUBLISHED_COMPARISON_STEP:
                step["conclusion"] = "skipped"
            elif step["name"] == verify.HISTORICAL_COMPARISON_STEP:
                step["conclusion"] = "success"
            elif step["name"] in verify.PUBLISHED_ROUTE_STEPS and \
                    step["name"] != "Record the Needs/facts comparison route":
                step["conclusion"] = "skipped"
        result = verify.verify_jobs(jobs["jobs"], self.fixture["run_head"])
        self.assertEqual(result["comparisonRoute"], "historical")

    def test_unsafe_zip_entries_are_refused(self):
        for label, name, mode in (
            ("traversal", "../evil", 0o100644),
            ("absolute", "/evil", 0o100644),
            ("symlink", "link", 0o120777),
            ("device", "dev", 0o020644),
        ):
            zip_path = self.root / f"unsafe-{label}.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                info = zipfile.ZipInfo(name)
                info.external_attr = mode << 16
                archive.writestr(info, b"x")
            with self.assertRaises(verify.Refusal, msg=label):
                verify.safe_extract(zip_path, self.root / f"unsafe-{label}-out")

    def test_elf_parser_refuses_dynamic_and_interp(self):
        for label, kwargs in (("interp", {"interp": True}),
                              ("dynamic", {"dynamic": True}),
                              ("machine", {"machine": 62})):
            path = self.root / f"elf-{label}"
            path.write_bytes(fixture.make_elf(512, **kwargs))
            with self.assertRaises(verify.Refusal, msg=label):
                verify.elf_facts(path)

    def test_same_candidate_lock_normalizes_only_descriptive_fields(self):
        proposal = copy.deepcopy(self.metadata["lockProposal"])
        other = copy.deepcopy(proposal)
        from datetime import datetime
        parsed = datetime.fromisoformat(other["upstream"]["commitDate"])
        other["upstream"]["commitDate"] = parsed.astimezone(
            __import__("datetime").timezone.utc).isoformat().replace("+00:00", "Z")
        other["resolvedVia"] = "github api"
        self.assertTrue(verify.same_candidate_lock(proposal, other))
        for mutate in (
            lambda doc: doc["upstream"].__setitem__("commitSubject", "user edit"),
            lambda doc: doc["upstream"].__setitem__("commit", "a" * 40),
            lambda doc: doc.__setitem__("status", "ready"),
        ):
            changed = copy.deepcopy(other)
            mutate(changed)
            self.assertFalse(verify.same_candidate_lock(proposal, changed))

    def test_same_version_manual_review_needs_a_different_commit(self):
        base = copy.deepcopy(self.fixture["base_lock"])
        same = copy.deepcopy(fixture.CANDIDATE)
        same.update({
            "engineVersion": "0.1.17",
            "engineId": "impeccable-0.1.17+floe.1.1.1",
            "commit": "a" * 40,
            "tree": "b" * 40,
            "commitDate": "2026-10-27T00:00:00Z",
            "commitSubject": "same-version manual review",
            "resolvedVia": "github api",
        })
        proposal = verify.expected_candidate_lock(base, same)
        verify.check_proposal_against_base(base, proposal, same)  # no refusal

        older = copy.deepcopy(same)
        older.update({"engineVersion": "0.1.16",
                      "engineId": "impeccable-0.1.16+floe.1.1.1",
                      "commit": "c" * 40, "tree": "d" * 40})
        with self.assertRaises(verify.Refusal):
            verify.check_proposal_against_base(
                base, verify.expected_candidate_lock(base, older), older)

        unchanged = copy.deepcopy(same)
        unchanged["commit"] = base["upstream"]["commit"]
        with self.assertRaises(verify.Refusal):
            verify.check_proposal_against_base(
                base, verify.expected_candidate_lock(base, unchanged), unchanged)

    def test_metadata_refusals(self):
        metadata = copy.deepcopy(self.metadata)
        metadata["files"] = ["dist/native"]
        with self.assertRaises(verify.Refusal):
            verify.validate_metadata_payload(metadata, self.repo,
                                             verify.OFFICIAL_REPOSITORY)

        metadata = copy.deepcopy(self.metadata)
        metadata["protectedInputs"]["digest"] = "0" * 64
        with self.assertRaises(verify.Refusal):
            verify.validate_metadata_payload(metadata, self.repo,
                                             verify.OFFICIAL_REPOSITORY)

        metadata = copy.deepcopy(self.metadata)
        metadata["baseline"]["binarySha256"] = "0" * 64
        with self.assertRaises(verify.Refusal):
            verify.validate_metadata_payload(metadata, self.repo,
                                             verify.OFFICIAL_REPOSITORY)

        metadata = copy.deepcopy(self.metadata)
        metadata["sourceRun"]["headSha"] = "a" * 40
        with self.assertRaises(verify.Refusal):
            verify.validate_metadata_payload(metadata, self.repo,
                                             verify.OFFICIAL_REPOSITORY)

        metadata = copy.deepcopy(self.metadata)
        metadata["lockProposal"]["status"] = "ready"
        metadata["lockProposalSha256"] = hashlib.sha256(
            verify.canonical_lock_bytes(metadata["lockProposal"])).hexdigest()
        with self.assertRaises(verify.Refusal):
            verify.validate_metadata_payload(metadata, self.repo,
                                             verify.OFFICIAL_REPOSITORY)


class TestOpenReviewPr(ReviewHarness):
    def setUp(self):
        self.bin = self.root / "bin"
        self.bin.mkdir(exist_ok=True)
        self.gh_log = self.root / "gh.log"
        self.gh_log.write_text("", encoding="utf-8")
        script = self.bin / "gh"
        script.write_text("""#!/bin/sh
set -e
case "$1 $2" in
  "pr list")
    case "${FAKE_GH_MODE:-empty}" in
      empty|branch-only) echo '[]' ;;
      *) echo '[{"number":7}]' ;;
    esac
    ;;
  "pr create")
    echo "create $*" >> "$FAKE_GH_LOG"
    echo "https://github.com/JiangNanGenius/floe-skill-hub/pull/7"
    ;;
  "pr view")
    if [ "${FAKE_GH_MODE:-empty}" = "existing" ] || [ "${FAKE_GH_MODE:-empty}" = "nondraft" ] || [ "${FAKE_GH_MODE:-empty}" = "extra" ] || [ "${FAKE_GH_MODE:-empty}" = "branch-only" ]; then
      HEAD=$(git rev-parse refs/remotes/origin/chore/impeccable-engine-0.1.18)
    else
      HEAD=$(git rev-parse HEAD)
    fi
    FILES='[{"path":"engines/impeccable/ENGINE-LOCK.json"}]'
    if [ "${FAKE_GH_MODE:-empty}" = "extra" ]; then
      FILES='[{"path":"engines/impeccable/ENGINE-LOCK.json"},{"path":"README.md"}]'
    fi
    DRAFT=true
    if [ "${FAKE_GH_MODE:-empty}" = "nondraft" ]; then
      DRAFT=false
    fi
    cat <<JSON
{"number":7,"url":"https://github.com/JiangNanGenius/floe-skill-hub/pull/7","isDraft":$DRAFT,"isCrossRepository":false,"headRefName":"chore/impeccable-engine-0.1.18","headRefOid":"$HEAD","files":$FILES,"headRepository":{"name":"floe-skill-hub"},"headRepositoryOwner":{"login":"JiangNanGenius"}}
JSON
    ;;
  *)
    echo "unexpected gh: $*" >&2
    exit 1
    ;;
esac
""", encoding="utf-8")
        script.chmod(0o755)

    def make_copy(self, name: str) -> Path:
        target = self.root / name
        shutil.copytree(self.repo, target)
        return target

    def make_remote(self, repo: Path) -> Path:
        remote = self.root / (repo.name + "-remote.git")
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)],
                       check=True, env=BASE_ENV)
        self.attach_remote(repo, remote)
        subprocess.run(["git", "-C", str(repo), "push", "-q", "origin",
                        "HEAD:refs/heads/main"], check=True, env=BASE_ENV)
        return remote

    def attach_remote(self, repo: Path, remote: Path) -> None:
        subprocess.run(["git", "-C", str(repo), "remote", "remove", "origin"],
                       capture_output=True, env=BASE_ENV)
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(remote)],
                       check=True, env=BASE_ENV)
        subprocess.run(["git", "-C", str(repo), "fetch", "-q", "origin"],
                       check=True, env=BASE_ENV)

    def run_pr(self, repo: Path, mode: str = "empty", *extra: str,
               metadata: Path | None = None, pr_py: Path | None = None):
        body = self.root / f"body-{mode}.md"
        out = self.root / f"pr-{mode}.json"
        env = dict(os.environ)
        env.update(BASE_ENV)
        # Prove the helper itself disables bytecode; never rely on the parent
        # environment for the clean-tree guarantee.
        env.pop("PYTHONDONTWRITEBYTECODE", None)
        env["PATH"] = f"{self.bin}:" + env["PATH"]
        env["FAKE_GH_MODE"] = mode
        env["FAKE_GH_LOG"] = str(self.gh_log)
        command = [sys.executable, str(pr_py or PR_PY),
                   "--engine-dir", "engines/impeccable",
                   "--repository", verify.OFFICIAL_REPOSITORY,
                   "--base", "main",
                   "--body-file", str(body),
                   "--out", str(out),
                   "--gh", str(self.bin / "gh")]
        command.extend(extra)
        if "--lock-auto" in extra:
            body.write_text("fixture automatic PR body\n", encoding="utf-8")
        if metadata is not None:
            command.extend(["--metadata", str(metadata)])
        proc = subprocess.run(command, cwd=str(repo), capture_output=True,
                              text=True, env=env, timeout=120)
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            payload = {"ok": False, "error": proc.stdout + "\n" + proc.stderr}
        return proc, payload, out, body

    def test_metadata_mode_commits_only_the_lock(self):
        repo = self.make_copy("write-new")
        self.make_remote(repo)
        proc, payload, out, body = self.run_pr(repo, "empty", metadata=self.happy_out)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(payload["action"], "created")
        self.assertEqual(payload["prUrl"],
                         "https://github.com/JiangNanGenius/floe-skill-hub/pull/7")
        log = subprocess.run(["git", "-C", str(repo), "log", "-1",
                              "--format=%an <%ae>%n%s%n%b"],
                             capture_output=True, text=True, env=BASE_ENV).stdout
        self.assertIn("floe-skill-hub-bot <bot@users.noreply.github.com>", log)
        self.assertIn(f"updater run {fixture.RUN_ID}", log)
        committed = subprocess.run(["git", "-C", str(repo), "show", "--name-only",
                                    "--format=", "HEAD"], capture_output=True,
                                   text=True, env=BASE_ENV).stdout.splitlines()
        self.assertEqual(committed, [verify.LOCK_REL])
        self.assertEqual(subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"], capture_output=True,
            text=True, env=BASE_ENV).stdout.strip(), "")
        remote_lock = subprocess.run(
            ["git", "-C", str(repo), "show",
             f"refs/remotes/origin/chore/impeccable-engine-0.1.18:{verify.LOCK_REL}"],
            capture_output=True, text=True, env=BASE_ENV).stdout
        self.assertEqual(remote_lock.encode(), verify.canonical_lock_bytes(
            verify.expected_candidate_lock(self.fixture["base_lock"], fixture.CANDIDATE)))
        body_text = body.read_text()
        self.assertIn("No native rebuild ran for this PR", body_text)
        self.assertIn("candidate-update-not-qualified", body_text)
        self.assertIn("TinyEMU", body_text)
        self.assertNotIn("dist/", body_text)

    def first_run(self, name: str):
        repo = self.make_copy(name)
        remote = self.make_remote(repo)
        proc, payload, _, _ = self.run_pr(repo, "empty", metadata=self.happy_out)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(payload["action"], "created")
        return repo, remote

    def fresh_at_main(self, name: str, remote: Path) -> Path:
        repo = self.make_copy(name)
        self.attach_remote(repo, remote)
        return repo

    def test_existing_matching_pr_is_reported_without_a_write(self):
        _, remote = self.first_run("write-existing-base")
        repo = self.fresh_at_main("write-existing-fresh", remote)
        head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                              capture_output=True, text=True, env=BASE_ENV).stdout.strip()
        self.gh_log.write_text("", encoding="utf-8")
        proc, payload, _, _ = self.run_pr(repo, "existing", metadata=self.happy_out)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(payload["action"], "existing")
        self.assertEqual(payload["prUrl"],
                         "https://github.com/JiangNanGenius/floe-skill-hub/pull/7")
        self.assertNotIn("create", self.gh_log.read_text())
        self.assertEqual(subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                                        capture_output=True, text=True,
                                        env=BASE_ENV).stdout.strip(), head)

    def test_existing_pr_with_api_representation_is_reported(self):
        _, remote = self.first_run("write-api-base")
        # Simulate the automatic updater's update_lock output for the same
        # immutable commit: only the descriptive UTC spelling and resolvedVia
        # label differ. This must be reported as the same candidate, not HOLD.
        branch_repo = self.fresh_at_main("write-api-branch", remote)
        subprocess.run(["git", "-C", str(branch_repo), "checkout", "-q", "-b",
                        "chore/impeccable-engine-0.1.18",
                        "refs/remotes/origin/chore/impeccable-engine-0.1.18"],
                       check=True, env=BASE_ENV)
        lock_path = branch_repo / verify.LOCK_REL
        proposal = json.loads(lock_path.read_text())
        from datetime import datetime, timezone
        parsed = datetime.fromisoformat(proposal["upstream"]["commitDate"])
        proposal["upstream"]["commitDate"] = parsed.astimezone(
            timezone.utc).isoformat().replace("+00:00", "Z")
        proposal["resolvedVia"] = "github api"
        lock_path.write_bytes(verify.canonical_lock_bytes(proposal))
        subprocess.run(["git", "-C", str(branch_repo), "add", verify.LOCK_REL],
                       check=True, env=BASE_ENV)
        subprocess.run(["git", "-C", str(branch_repo), *GIT_IDENTITY, "commit", "-qm",
                        "same candidate via API representation"], check=True,
                       env=BASE_ENV)
        subprocess.run(["git", "-C", str(branch_repo), "push", "-q", "origin",
                        "HEAD:refs/heads/chore/impeccable-engine-0.1.18"],
                       check=True, env=BASE_ENV)
        repo = self.fresh_at_main("write-api-fresh", remote)
        self.gh_log.write_text("", encoding="utf-8")
        proc, payload, _, _ = self.run_pr(repo, "existing", metadata=self.happy_out)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(payload["action"], "existing")
        self.assertNotIn("create", self.gh_log.read_text())

    def test_branch_without_pr_is_reproposed(self):
        _, remote = self.first_run("write-branch-base")
        repo = self.fresh_at_main("write-branch-fresh", remote)
        head = subprocess.run(["git", "-C", str(repo), "rev-parse",
                               "refs/remotes/origin/chore/impeccable-engine-0.1.18"],
                              capture_output=True, text=True, env=BASE_ENV).stdout.strip()
        self.gh_log.write_text("", encoding="utf-8")
        proc, payload, _, _ = self.run_pr(repo, "branch-only", metadata=self.happy_out)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(payload["action"], "created")
        self.assertIn("create", self.gh_log.read_text())
        self.assertEqual(subprocess.run(
            ["git", "-C", str(repo), "rev-parse",
             "refs/remotes/origin/chore/impeccable-engine-0.1.18"],
            capture_output=True, text=True, env=BASE_ENV).stdout.strip(), head)

    def test_conflicting_branch_is_held(self):
        _, remote = self.first_run("write-conflict-base")
        branch_repo = self.fresh_at_main("write-conflict-branch", remote)
        subprocess.run(["git", "-C", str(branch_repo), "checkout", "-q", "-b",
                        "chore/impeccable-engine-0.1.18",
                        "refs/remotes/origin/chore/impeccable-engine-0.1.18"],
                       check=True, env=BASE_ENV)
        lock = branch_repo / verify.LOCK_REL
        data = json.loads(lock.read_text())
        data["upstream"]["commitSubject"] = "independent edit"
        lock.write_text(json.dumps(data, indent=2) + "\n")
        subprocess.run(["git", "-C", str(branch_repo), "add", verify.LOCK_REL],
                       check=True, env=BASE_ENV)
        subprocess.run(["git", "-C", str(branch_repo), *GIT_IDENTITY, "commit", "-qm",
                        "independent branch edit"], check=True, env=BASE_ENV)
        subprocess.run(["git", "-C", str(branch_repo), "push", "-q", "origin",
                        "HEAD:refs/heads/chore/impeccable-engine-0.1.18"],
                       check=True, env=BASE_ENV)
        repo = self.fresh_at_main("write-conflict-fresh", remote)
        self.gh_log.write_text("", encoding="utf-8")
        proc, payload, _, _ = self.run_pr(repo, "empty", metadata=self.happy_out)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("different lock", payload.get("error", ""))
        self.assertNotIn("create", self.gh_log.read_text())

    def test_non_draft_or_user_edited_pr_is_held(self):
        _, remote = self.first_run("write-held-base")
        for mode, expected in (("nondraft", "not a draft"),
                               ("extra", "changes more than")):
            repo = self.fresh_at_main(f"write-held-{mode}", remote)
            self.gh_log.write_text("", encoding="utf-8")
            proc, payload, _, _ = self.run_pr(repo, mode, metadata=self.happy_out)
            self.assertEqual(proc.returncode, 2, (mode, proc.stdout, proc.stderr))
            self.assertIn(expected, payload.get("error", ""))
            self.assertNotIn("create", self.gh_log.read_text())

    def test_git_failure_propagates_and_does_not_open_a_pr(self):
        repo = self.make_copy("write-gitfail")
        self.make_remote(repo)
        hook = repo / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)
        self.gh_log.write_text("", encoding="utf-8")
        proc, payload, _, _ = self.run_pr(repo, "empty", metadata=self.happy_out)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("commit", payload.get("error", "").lower())
        self.assertNotIn("create", self.gh_log.read_text())

    def test_auto_mode_uses_the_corrected_commit_path(self):
        repo = self.make_copy("write-auto")
        upstream = self.root / "upstream-auto"
        upstream.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(upstream)],
                       check=True, env=BASE_ENV)
        (upstream / "ENGINE_VERSION").write_text("0.1.18\n")
        subprocess.run(["git", "-C", str(upstream), "add", "ENGINE_VERSION"],
                       check=True, env=BASE_ENV)
        subprocess.run(["git", "-C", str(upstream), *GIT_IDENTITY, "commit", "-qm",
                        "Engine 0.1.18"], check=True, env=BASE_ENV)
        commit = subprocess.run(["git", "-C", str(upstream), "rev-parse", "HEAD"],
                                capture_output=True, text=True,
                                env=BASE_ENV).stdout.strip()
        update = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "update_lock.py"),
             "--lock", str(repo / verify.LOCK_REL), "--commit", commit,
             "--engine-version", "0.1.18", "--source", str(upstream)],
            capture_output=True, text=True, env=BASE_ENV, timeout=120)
        self.assertEqual(update.returncode, 0, update.stdout + update.stderr)
        self.make_remote(repo)
        proc, payload, _, _ = self.run_pr(
            repo, "empty", "--lock-auto", "--candidate-commit", commit,
            "--candidate-version", "0.1.18")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(payload["action"], "created")
        committed = subprocess.run(["git", "-C", str(repo), "show", "--name-only",
                                    "--format=", "HEAD"], capture_output=True,
                                   text=True, env=BASE_ENV).stdout.splitlines()
        self.assertEqual(committed, [verify.LOCK_REL])
        author = subprocess.run(["git", "-C", str(repo), "log", "-1",
                                 "--format=%an <%ae>"], capture_output=True,
                                text=True, env=BASE_ENV).stdout.strip()
        self.assertEqual(author, "floe-skill-hub-bot <bot@users.noreply.github.com>")

    def advance_live(self, remote: Path, name: str, mutate) -> str:
        advance = self.make_copy(name)
        self.attach_remote(advance, remote)
        mutate(advance)
        subprocess.run(["git", "-C", str(advance), "add", "-A"],
                       check=True, env=BASE_ENV)
        subprocess.run(["git", "-C", str(advance), *GIT_IDENTITY, "commit", "-qm",
                        "live default branch advance"], check=True, env=BASE_ENV)
        subprocess.run(["git", "-C", str(advance), "push", "-q", "origin",
                        "HEAD:refs/heads/main"], check=True, env=BASE_ENV)
        return subprocess.run(["git", "-C", str(advance), "rev-parse", "HEAD"],
                              capture_output=True, text=True,
                              env=BASE_ENV).stdout.strip()

    def test_unrelated_live_advance_is_allowed_and_rebased(self):
        repo = self.make_copy("write-live-positive")
        remote = self.make_remote(repo)
        live_sha = self.advance_live(
            remote, "write-live-positive-advance",
            lambda path: (path / "docs").mkdir(exist_ok=True) or
            (path / "docs/UNRELATED.md").write_text("unrelated main change\n"))
        self.gh_log.write_text("", encoding="utf-8")
        proc, payload, _, _ = self.run_pr(repo, "empty", metadata=self.happy_out)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(payload["action"], "created")
        self.assertIn("create", self.gh_log.read_text())
        # The new branch starts from the live default branch, not the stale
        # dispatch checkout, so it does not revert the unrelated change.
        parent = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD^"],
                                capture_output=True, text=True,
                                env=BASE_ENV).stdout.strip()
        self.assertEqual(parent, live_sha)
        self.assertEqual(subprocess.run(
            ["git", "-C", str(repo), "show", "HEAD:docs/UNRELATED.md"],
            capture_output=True, text=True, env=BASE_ENV).returncode, 0)
        diff = subprocess.run(["git", "-C", str(repo), "diff", "--name-only",
                               f"{live_sha}...HEAD"], capture_output=True,
                              text=True, env=BASE_ENV).stdout.splitlines()
        self.assertEqual(diff, [verify.LOCK_REL])

    def test_new_live_baseline_is_held(self):
        repo = self.make_copy("write-live-negative")
        remote = self.make_remote(repo)

        def new_baseline(path: Path):
            lock = path / verify.LOCK_REL
            data = json.loads(lock.read_text())
            data["component"]["artifactSha256"] = "9" * 64
            data["component"]["artifactBytes"] = 1234567
            lock.write_text(json.dumps(data, indent=2) + "\n")

        self.advance_live(remote, "write-live-negative-advance", new_baseline)
        head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                              capture_output=True, text=True,
                              env=BASE_ENV).stdout.strip()
        self.gh_log.write_text("", encoding="utf-8")
        proc, payload, _, _ = self.run_pr(repo, "empty", metadata=self.happy_out)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("live default branch", payload.get("error", ""))
        self.assertNotIn("create", self.gh_log.read_text())
        self.assertEqual(subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                                        capture_output=True, text=True,
                                        env=BASE_ENV).stdout.strip(), head)

    def test_auto_mode_new_live_baseline_is_held(self):
        repo = self.make_copy("write-auto-live-negative")
        upstream = self.root / "upstream-auto-live"
        upstream.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(upstream)],
                       check=True, env=BASE_ENV)
        (upstream / "ENGINE_VERSION").write_text("0.1.18\n")
        subprocess.run(["git", "-C", str(upstream), "add", "ENGINE_VERSION"],
                       check=True, env=BASE_ENV)
        subprocess.run(["git", "-C", str(upstream), *GIT_IDENTITY, "commit", "-qm",
                        "Engine 0.1.18"], check=True, env=BASE_ENV)
        commit = subprocess.run(["git", "-C", str(upstream), "rev-parse", "HEAD"],
                                capture_output=True, text=True,
                                env=BASE_ENV).stdout.strip()
        update = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "update_lock.py"),
             "--lock", str(repo / verify.LOCK_REL), "--commit", commit,
             "--engine-version", "0.1.18", "--source", str(upstream)],
            capture_output=True, text=True, env=BASE_ENV, timeout=120)
        self.assertEqual(update.returncode, 0, update.stdout + update.stderr)
        remote = self.make_remote(repo)

        def new_baseline(path: Path):
            lock = path / verify.LOCK_REL
            data = json.loads(lock.read_text())
            data["component"]["artifactSha256"] = "9" * 64
            lock.write_text(json.dumps(data, indent=2) + "\n")

        self.advance_live(remote, "write-auto-live-negative-advance", new_baseline)
        self.gh_log.write_text("", encoding="utf-8")
        proc, payload, _, _ = self.run_pr(
            repo, "empty", "--lock-auto", "--candidate-commit", commit,
            "--candidate-version", "0.1.18")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("live default branch", payload.get("error", ""))
        self.assertNotIn("create", self.gh_log.read_text())

    def test_helper_does_not_leave_pycache_without_env(self):
        repo = self.make_copy("write-pycache")
        tools = repo / "engines/impeccable/workflows/tools"
        for name in ("open_review_pr.py", "verify_candidate_reuse.py"):
            shutil.copyfile(TOOLS_DIR / name, tools / name)
        subprocess.run(["git", "-C", str(repo), "add", "engines/impeccable/workflows/tools"],
                       check=True, env=fixture.GIT_ENV)
        subprocess.run(["git", "-C", str(repo), *GIT_IDENTITY, "commit", "-qm",
                        "fixture helper copies"], check=True, env=fixture.GIT_ENV)
        self.make_remote(repo)
        # Run the helper from the same write checkout/tools path the real job
        # uses, with PYTHONDONTWRITEBYTECODE removed from the child env.
        proc, payload, _, _ = self.run_pr(
            repo, "empty", metadata=self.happy_out,
            pr_py=tools / "open_review_pr.py")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(payload["action"], "created")
        self.assertEqual(list(tools.rglob("__pycache__")), [],
                         f"unexpected bytecode under {tools}")
        self.assertEqual(subprocess.run(["git", "-C", str(repo), "status",
                                         "--porcelain"], capture_output=True,
                                        text=True, env=BASE_ENV).stdout.strip(), "")
        source = (tools / "open_review_pr.py").read_text()
        self.assertLess(source.index("sys.dont_write_bytecode = True"),
                        source.index("import verify_candidate_reuse"))

    def test_metadata_with_native_payload_is_refused(self):
        metadata = json.loads(self.happy_out.read_text())
        metadata["files"] = ["dist/native"]
        path = self.root / "bad-metadata.json"
        path.write_text(json.dumps(metadata))
        repo = self.make_copy("write-bad-meta")
        self.make_remote(repo)
        proc, payload, _, _ = self.run_pr(repo, "empty", metadata=path)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("unexpected/missing keys", payload.get("error", ""))


class TestReviewWorkflowWiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import yaml
        except ImportError:
            raise unittest.SkipTest("PyYAML is not installed on this host")
        cls.review = yaml.safe_load(REVIEW_YML.read_text())
        cls.template = yaml.safe_load(UPDATER_TEMPLATE.read_text())
        cls.review_text = REVIEW_YML.read_text()
        cls.template_text = UPDATER_TEMPLATE.read_text()
        cls.root_text = UPDATER_ROOT.read_text()

    @staticmethod
    def run_blocks(document):
        for job in document["jobs"].values():
            for step in job.get("steps", []):
                if "run" in step:
                    yield step["run"]

    @staticmethod
    def uses(document):
        for job in document["jobs"].values():
            for step in job.get("steps", []):
                if "uses" in step:
                    yield step["uses"]

    def test_dispatch_only_and_read_default(self):
        self.assertEqual(sorted(self.review.get("on") or self.review.get(True)),
                         ["workflow_dispatch"])
        self.assertEqual(self.review["permissions"], {"contents": "read"})
        self.assertEqual(self.review["jobs"]["verify-candidate"]["permissions"],
                         {"contents": "read", "actions": "read"})
        self.assertEqual(self.review["jobs"]["open-draft-pr"]["permissions"],
                         {"contents": "write", "pull-requests": "write"})
        self.assertEqual(self.review["env"]["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertEqual(self.template["env"]["PYTHONDONTWRITEBYTECODE"], "1")
        for job in self.review["jobs"].values():
            self.assertIn("FLOE_IMPECCABLE_UPDATE_PRS == 'enabled'", job["if"])

    def test_no_expression_reaches_run_text(self):
        for block in self.run_blocks(self.review):
            self.assertNotIn("${{", block)
        for block in self.run_blocks(self.template):
            self.assertNotIn("${{", block)

    def test_actions_are_pinned_and_only_the_known_set(self):
        for uses in self.uses(self.review):
            action, _, ref = uses.partition("@")
            self.assertRegex(ref, r"^[0-9a-f]{40}$")
            self.assertIn(action, {
                "actions/checkout", "actions/upload-artifact",
                "actions/download-artifact"})
        for uses in self.uses(self.template):
            action, _, ref = uses.partition("@")
            self.assertRegex(ref, r"^[0-9a-f]{40}$")
            self.assertIn(action, {"actions/checkout", "actions/upload-artifact"})

    def test_review_calls_the_shared_helpers_and_uploads_only_metadata(self):
        self.assertIn("verify_candidate_reuse.py", self.review_text)
        self.assertIn("open_review_pr.py", self.review_text)
        self.assertIn("impeccable-engine-review-payload", self.review_text)
        self.assertIn("candidate_run_id", self.review_text)
        self.assertIn("refs/heads/main", self.review_text)
        self.assertIn("--draft", (TOOLS_DIR / "open_review_pr.py").read_text())
        for forbidden in ("pull_request_target", "gh pr merge", "gh pr review --approve",
                          "gh release", "--force"):
            self.assertNotIn(forbidden, self.review_text)

    def test_updater_tail_uses_the_corrected_helper(self):
        pr_job = self.template["jobs"]["open-update-pr"]
        self.assertEqual(pr_job["permissions"],
                         {"contents": "write", "pull-requests": "write"})
        self.assertIn("open_review_pr.py", self.template_text)
        self.assertNotIn('git -c user.name "', self.template_text)
        self.assertNotIn("|| exit 0", self.template_text)
        helper = (TOOLS_DIR / "open_review_pr.py").read_text()
        self.assertIn('"-c", f"user.name={COMMIT_NAME}"', helper)
        self.assertIn('"-c", f"user.email={COMMIT_EMAIL}"', helper)
        self.assertIn('"commit", "-m"', helper)
        self.assertNotIn("--force", self.template_text)
        self.assertIn("update_lock.py", self.template_text)
        self.assertEqual(self.template_text[self.template_text.index("name:"):],
                         self.root_text[self.root_text.index("name:"):])
        marker = "\n  open-update-pr:"
        template_body = self.template_text[self.template_text.index("name:"):]
        root_body = self.root_text[self.root_text.index("name:"):]
        self.assertEqual(
            template_body[:template_body.index(marker) + 1],
            root_body[:root_body.index(marker) + 1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
