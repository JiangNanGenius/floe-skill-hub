#!/usr/bin/env python3
"""Fail-closed proof that one completed updater run already built the candidate.

This tool is the read-only half of the PR-only recovery path. It proves that a
specific `impeccable-engine-updater` run really built the candidate binary from
the engine inputs that are checked out now, then extracts the canonical
`impeccable-engine-candidate` artifact, re-verifies its receipts and emits a
TINY metadata payload. The payload carries the exact `ENGINE-LOCK.json`
proposal, the source run/artifact identity and the current-input digests; the
separate write job consumes nothing else. No artifact code or binary is ever
executed.

What is checked, in order:

  * the run is from the fixed official repository and the fixed updater
    workflow path, ran on `main`, completed successfully on attempt 1, and its
    head commit is an immutable ancestor of the current checkout;
  * the build job really succeeded (not skipped), every required gate step
    succeeded, and exactly one of the two routed Needs/facts comparisons ran:
    the published-baseline comparison or the historical-goldens comparison;
  * the protected engine inputs (tracked lock, adapter, build, contract,
    patches, published dist, root LICENSE and the five tools the old recipe
    actually invoked) are byte-identical between that run's head and the
    current checkout, so later PR-tail/test-fixture changes do not invalidate
    the native proof;
  * the updater recipe ABOVE `open-update-pr:` is text-identical between the
    two commits, while the tail (the fixed PR controller) may differ;
  * exactly one unexpired `impeccable-engine-candidate` artifact exists and its
    downloaded zip matches GitHub's recorded digest;
  * the zip is extracted safely (no traversal, links, devices, odd modes, or
    unknown top-level payloads) and the compiled riscv64 ELF, its build
    receipt, SHA256SUMS, provenance, projected-test receipt, contract digests,
    behavioural logs, routed comparison, published-baseline record and derived
    source all bind to that one candidate and to the current published base;
  * the candidate lock proposal differs from the current lock only in the pin
    fields `update_lock.py` owns, keeps `candidate-update-not-qualified`, and
    the current published base/adapter are still byte-identical to the ones the
    original run authenticated.

Any disagreement is a refusal (exit 2). Nothing is committed, pushed, merged,
published or dispatched; the read-only API calls and the artifact download are
the only network work.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import stat
import struct
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

# This tool is run from a checked-out repository; never leave bytecode behind
# for the write job's clean-tree check (and keep the test/CI checkout clean).
sys.dont_write_bytecode = True

# --------------------------------------------------------------------------
# Fixed official identity. These are deliberately not configurable: a run from
# another repository, workflow path or branch is not this proof.
# --------------------------------------------------------------------------

OFFICIAL_REPOSITORY = "JiangNanGenius/floe-skill-hub"
OFFICIAL_REPOSITORY_ID = 1433339884
UPDATER_WORKFLOW_PATH = ".github/workflows/impeccable-engine-updater.yml"
PIN_JOB_NAME = "Compare the pin with the upstream engine release"
BUILD_JOB_NAME = "Build and verify the candidate engine"
CANDIDATE_ARTIFACT_NAME = "impeccable-engine-candidate"
TARGET_TRIPLE = "riscv64gc-unknown-linux-musl"
LOCK_REL = "engines/impeccable/ENGINE-LOCK.json"

SEMVER_RE = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
ENGINE_ID_RE = re.compile(r"impeccable-([0-9]+\.[0-9]+\.[0-9]+)\+floe\.([0-9]+\.[0-9]+\.[0-9]+)")
HEX40_RE = re.compile(r"[0-9a-f]{40}")
HEX64_RE = re.compile(r"[0-9a-f]{64}")
BRANCH_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,99}")
SUPERSEDED_NOTE = ("the pin this update replaces; artifacts built from it stay valid "
                   "until reviewed out")

# Every input the old updater recipe (the part above `open-update-pr:`) reads
# while it builds and verifies the native candidate. New helpers, tests, docs
# and the PR tail are deliberately NOT here: they may change without
# invalidating a proof that was produced by the original recipe.
PROTECTED_PATHS = (
    LOCK_REL,
    "engines/impeccable/adapter",
    "engines/impeccable/build",
    "engines/impeccable/contract",
    "engines/impeccable/patches",
    "engines/impeccable/dist",
    "engines/impeccable/workflows/tools/compare_expected.py",
    "engines/impeccable/workflows/tools/resolve_upstream_pin.py",
    "engines/impeccable/workflows/tools/stage_candidate_engine.py",
    "engines/impeccable/workflows/tools/update_lock.py",
    "engines/impeccable/workflows/tools/verify_published_baseline.py",
    "LICENSE",
)

PUBLISHED_COMPARISON_STEP = "Needs/facts fixpoint regression against the published baseline"
HISTORICAL_COMPARISON_STEP = "Needs/facts fixpoint regression against the recorded goldens"
PUBLISHED_ROUTE_STEPS = (
    "Record the Needs/facts comparison route",
    "Check out the baseline's own pinned tree (temp worktree of the existing clone)",
    "Behaviour matrix on the published baseline (emulated riscv64)",
    "Record the versioned baseline results (temp only; never committed, never blessed)",
    "Bind the recorded baseline tree to the official lock and binary",
)
REQUIRED_BUILD_STEPS = (
    "Install the pinned Rust toolchain and target",
    "Install the pinned zig cross toolchain",
    "Register a riscv64 binfmt handler (emulated behaviour matrix)",
    "Fetch the pinned upstream source at the candidate commit",
    "Stage the candidate ENGINE-LOCK.json (temp only; the tracked lock is untouched here)",
    "Stage the candidate engine tree (temp only; the tracked lock, contract and binary stay untouched)",
    "Preflight the tracked patches against the candidate",
    "Build the riscv64 engine from the pinned source",
    "Build the host engine and run the adapter suite",
    "Contract coherence gate",
    "Behaviour matrix on riscv64 (emulated)",
    "Behaviour matrix on the host build",
    "Verify the published baseline binary against the official lock",
    "Route the Needs/facts comparison by authenticated baseline identity",
    "Regenerate the derived skill source for the candidate (public stage 1 normalizer)",
    "Collect reviewer artifacts (never committed, never published)",
    "Collect gate-failure logs for reviewers",
)

REQUIRED_LOGS = (
    "logs/baseline-binary-verify.json",
    "logs/baseline-record-verify.json",
    "logs/build-summary-riscv64gc-unknown-linux-musl-release.json",
    "logs/build-summary-x86_64-unknown-linux-gnu-dev.json",
    "logs/contract-validation.json",
    "logs/golden-comparison-vs-baseline.json",
    "logs/stage-candidate-engine.json",
    "logs/verify-baseline.json",
    "logs/verify-host.json",
    "logs/verify-riscv64.json",
)
ALLOWED_TOP_LEVEL = ("candidate-lock", "dist", "expected-baseline", "logs",
                     "sources-impeccable")
DIST_FILES = (
    "BUILD-RECEIPT.json",
    "LICENSE-adapter",
    "LICENSE-impeccable-apache-2.0",
    "NOTICE-impeccable.md",
    "PROVENANCE.json",
    "SHA256SUMS.txt",
    "floe-impeccable",
)
ALLOWED_IDENTITY_FIELDS = {
    "engine.engineId",
    "engine.upstreamCommit",
    "engine.upstreamTree",
    "engine.upstreamEngineVersion",
    "diagnostics.engineVersion",
    "diagnostics.upstreamCommit",
}

# Caps: the real artifact is ~3.3 MB, its binary 5.6 MB and its uncompressed
# tree well under 32 MB. Generous for the fixed shape, far below anything that
# could exhaust a hosted runner.
MAX_API_BYTES = 8 << 20
MAX_ARTIFACT_BYTES = 64 << 20
MAX_ZIP_ENTRIES = 3000
MAX_ZIP_UNCOMPRESSED = 128 << 20
MAX_ZIP_ENTRY_BYTES = 32 << 20
MAX_JSON_BYTES = 32 << 20
MIN_ARTIFACT_REMAINING = timedelta(hours=1)

METADATA_SCHEMA = "floe.impeccable-engine-review.v1"
METADATA_KEYS = (
    "schema", "repository", "updaterWorkflow", "sourceRun", "buildJob",
    "artifact", "candidate", "baseline", "binary", "lockProposal",
    "lockProposalSha256", "protectedInputs", "recipe", "verifiedAt",
)
SOURCE_RUN_KEYS = ("id", "attempt", "headSha", "headBranch", "event",
                   "conclusion", "url")
BUILD_JOB_KEYS = ("id", "name", "conclusion", "comparisonRoute")
ARTIFACT_KEYS = ("id", "name", "digest", "sizeInBytes", "expiresAt")
CANDIDATE_KEYS = ("engineVersion", "commit", "tree", "adapterVersion",
                  "engineId", "packageVersion", "commitDate", "commitSubject",
                  "resolvedVia")
BASELINE_KEYS = ("engineId", "commit", "tree", "engineVersion", "binarySha256",
                 "binaryBytes")
BINARY_KEYS = ("path", "sha256", "bytes", "elfMachine", "static")
PROTECTED_KEYS = ("paths", "digest")
RECIPE_KEYS = ("prefixSha256", "headWorkflowBlob")


class Refusal(Exception):
    """A fail-closed refusal: the supplied proof is not reusable."""


def refuse(message: str) -> None:
    raise Refusal(message)


def require(condition, message: str) -> None:
    if not condition:
        refuse(message)


# --------------------------------------------------------------------------
# Small shared primitives
# --------------------------------------------------------------------------


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path, what: str, *, max_bytes: int = MAX_JSON_BYTES):
    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        refuse(f"{what} is unreadable: {exc}")
    if len(raw) > max_bytes:
        refuse(f"{what} is larger than the {max_bytes}-byte cap")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        refuse(f"{what} is not valid UTF-8 JSON: {exc}")


def write_json(path, document) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def canonical_lock_bytes(lock: dict) -> bytes:
    """The exact serialization `update_lock.py` writes."""
    return (json.dumps(lock, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def parse_iso(value, what: str) -> datetime:
    require(isinstance(value, str) and value, f"{what} is not an ISO-8601 string")
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        refuse(f"{what} is not a valid ISO-8601 timestamp: {value!r}")
    require(parsed.tzinfo is not None, f"{what} carries no timezone: {value!r}")
    return parsed


def require_semver(value, what: str) -> str:
    require(isinstance(value, str) and SEMVER_RE.fullmatch(value),
            f"{what} is not dotted-semver: {value!r}")
    return value


def require_hex(value, shape, what: str) -> str:
    require(isinstance(value, str) and shape.fullmatch(value),
            f"{what} is not the expected hex shape: {value!r}")
    return value


def semver_tuple(value: str) -> tuple[int, int, int]:
    return tuple(int(part) for part in value.split("."))  # type: ignore[return-value]


def same_candidate_lock(left, right) -> bool:
    """True when two lock documents propose the same candidate pin.

    `update_lock.py` can resolve the same immutable commit through a local clone
    or the GitHub API. The pin, adapter, status, superseded pin and every other
    field are identical; only the descriptive `commitDate` UTC-offset spelling
    and the `resolvedVia` provenance label can differ. Normalize exactly those
    two descriptive values, never a pin/identity field, so an automatic-path
    retry can report a review-path draft PR (and vice versa) without treating a
    user edit to any real field as the same proposal.
    """
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False

    def normalized(document: dict) -> dict:
        copy_doc = copy.deepcopy(document)
        copy_doc.pop("resolvedVia", None)
        upstream = copy_doc.get("upstream")
        if isinstance(upstream, dict):
            value = upstream.get("commitDate")
            if isinstance(value, str):
                try:
                    upstream["commitDate"] = parse_iso(value, "commit date").timestamp()
                except Refusal:
                    return {}
        return copy_doc

    return bool(normalized(left)) and normalized(left) == normalized(right)


def first_diff(expected, actual, path: str = "") -> str | None:
    if type(expected) is not type(actual) and not (
            isinstance(expected, (int, float)) and isinstance(actual, (int, float))):
        return f"{path or '<root>'}: {expected!r} != {actual!r}"
    if isinstance(expected, dict):
        for key in sorted(set(expected) | set(actual)):
            if key not in expected:
                return f"{path}/{key}: unexpected key"
            if key not in actual:
                return f"{path}/{key}: missing key"
            found = first_diff(expected[key], actual[key], f"{path}/{key}")
            if found:
                return found
        return None
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return f"{path}: list length {len(expected)} != {len(actual)}"
        for index, (left, right) in enumerate(zip(expected, actual)):
            found = first_diff(left, right, f"{path}[{index}]")
            if found:
                return found
        return None
    if expected != actual:
        return f"{path or '<root>'}: {expected!r} != {actual!r}"
    return None


def git(repo_root, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", "-C", str(repo_root), *args],
                          capture_output=True, text=True)
    if check and proc.returncode != 0:
        refuse(f"git {' '.join(args)} failed: {proc.stderr.strip()[:500]}")
    return proc


def git_out(repo_root, *args: str, check: bool = True) -> str:
    return git(repo_root, *args, check=check).stdout.strip()


def protected_inputs_digest(repo_root, rev: str) -> str:
    """Digest of every protected path as mode/type/blob at one commit."""
    proc = git(repo_root, "ls-tree", "-r", "-z", "--full-tree", rev,
               "--", *PROTECTED_PATHS)
    records = [record for record in proc.stdout.split("\0") if record]
    require(records, f"no protected inputs exist at {rev}")
    lines = []
    for record in records:
        meta, _, path = record.partition("\t")
        mode, kind, blob = meta.split()
        require(kind in ("blob", "commit"),
                f"unexpected git object kind for {path!r}: {kind!r}")
        lines.append(f"{mode} {kind} {blob}\t{path}")
    return sha256_bytes("\n".join(sorted(lines)).encode("utf-8"))


def recipe_prefix_bytes(repo_root, rev: str) -> bytes:
    text = git(repo_root, "show", f"{rev}:{UPDATER_WORKFLOW_PATH}").stdout
    marker = "\n  open-update-pr:"
    index = text.find(marker)
    require(index > 0, f"the updater recipe has no open-update-pr job at {rev}")
    return (text[:index + 1]).encode("utf-8")


# --------------------------------------------------------------------------
# GitHub API (fixed origin, bounded reads, token never printed)
# --------------------------------------------------------------------------


class _RedirectWithoutAuth(urllib.request.HTTPRedirectHandler):
    """Keep the bearer token on api.github.com, strip it from a storage host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_request = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_request is not None:
            old_host = urllib.parse.urlsplit(req.full_url).netloc
            new_host = urllib.parse.urlsplit(new_request.full_url).netloc
            if new_host != old_host:
                new_request.remove_header("Authorization")
        return new_request


def _is_loopback(api_base: str) -> bool:
    host = urllib.parse.urlsplit(api_base).hostname
    return host in ("127.0.0.1", "::1", "localhost")


class Api:
    def __init__(self, base: str, token: str | None):
        base = base.rstrip("/")
        parsed = urllib.parse.urlsplit(base)
        require(parsed.scheme in ("https", "http"), f"unsupported API origin: {base!r}")
        if parsed.scheme != "https":
            require(_is_loopback(base), "plain HTTP is only allowed for a loopback test origin")
        require(parsed.query == "" and parsed.fragment == "",
                "the API origin must not carry a query or fragment")
        self.base = base
        self.token = token
        self.opener = urllib.request.build_opener(_RedirectWithoutAuth())

    def _headers(self, accept: str) -> dict:
        headers = {
            "Accept": accept,
            "User-Agent": "floe-skill-hub-candidate-reuse",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def get_json(self, path: str):
        require(path.startswith("/repos/"), "API path must stay repository-relative")
        request = urllib.request.Request(self.base + path,
                                         headers=self._headers("application/vnd.github+json"))
        try:
            with self.opener.open(request, timeout=90) as response:
                raw = response.read(MAX_API_BYTES + 1)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            refuse(f"the GitHub API read failed: {exc}")
        require(len(raw) <= MAX_API_BYTES, "the GitHub API response exceeded the cap")
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            refuse(f"the GitHub API returned invalid JSON: {exc}")

    def download(self, path: str, destination: Path, max_bytes: int) -> None:
        require(path.startswith("/repos/"), "download path must stay repository-relative")
        request = urllib.request.Request(
            self.base + path,
            headers=self._headers("application/vnd.github+json"))
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        try:
            with self.opener.open(request, timeout=180) as response:
                length = response.headers.get("Content-Length")
                if length is not None:
                    try:
                        require(int(length) <= max_bytes,
                                "the artifact Content-Length exceeds the cap")
                    except ValueError:
                        refuse("the artifact Content-Length is not an integer")
                with destination.open("xb") as handle:
                    while True:
                        chunk = response.read(1 << 20)
                        if not chunk:
                            break
                        written += len(chunk)
                        require(written <= max_bytes, "the artifact download exceeded the cap")
                        handle.write(chunk)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            destination.unlink(missing_ok=True)
            refuse(f"the artifact download failed: {exc}")
        require(written > 0, "the artifact download was empty")


def api_token() -> str | None:
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or None


# --------------------------------------------------------------------------
# Run / job / artifact document checks
# --------------------------------------------------------------------------


def validate_repository(value) -> str:
    require(value == OFFICIAL_REPOSITORY,
            f"refusing repository {value!r}; this proof is fixed to {OFFICIAL_REPOSITORY}")
    return value


def validate_run_id(value) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        refuse(f"the run id is not an integer: {value!r}")
    text = str(value)
    require(re.fullmatch(r"[1-9][0-9]{0,19}", text), f"the run id is not positive digits: {value!r}")
    return int(text)


def fetch_run(api: Api, repository: str, run_id: int) -> dict:
    run = api.get_json(f"/repos/{repository}/actions/runs/{run_id}")
    require(isinstance(run, dict), "the run document is not an object")
    require(run.get("id") == run_id, "the run id does not match the requested id")
    require(run.get("run_attempt") == 1,
            f"the run attempt is {run.get('run_attempt')!r}; only the original successful attempt is reusable")
    require(run.get("status") == "completed", f"the run is not completed: {run.get('status')!r}")
    require(run.get("conclusion") == "success",
            f"the run did not complete successfully: {run.get('conclusion')!r}")
    require(run.get("event") in ("workflow_dispatch", "schedule"),
            f"the run event is not a trusted updater trigger: {run.get('event')!r}")
    require(run.get("head_branch") == "main",
            f"the run did not execute on main: {run.get('head_branch')!r}")
    require(run.get("path") == UPDATER_WORKFLOW_PATH,
            f"the run used {run.get('path')!r}, not {UPDATER_WORKFLOW_PATH}")
    require(run.get("name") == "impeccable-engine-updater",
            f"the run workflow name is unexpected: {run.get('name')!r}")
    repository_doc = run.get("repository")
    require(isinstance(repository_doc, dict)
            and repository_doc.get("full_name") == OFFICIAL_REPOSITORY
            and repository_doc.get("id") == OFFICIAL_REPOSITORY_ID,
            "the run repository is not the fixed official repository")
    head_repository = run.get("head_repository")
    require(isinstance(head_repository, dict)
            and head_repository.get("full_name") == OFFICIAL_REPOSITORY,
            "the run head repository is not the fixed official repository")
    require_hex(run.get("head_sha"), HEX40_RE, "the run head sha")
    return run


def _paginate(api: Api, path: str, field: str, max_pages: int = 20) -> list:
    items: list = []
    page = 1
    while True:
        separator = "&" if "?" in path else "?"
        document = api.get_json(f"{path}{separator}per_page=100&page={page}")
        require(isinstance(document, dict), f"the {field} document is not an object")
        chunk = document.get(field)
        require(isinstance(chunk, list), f"the {field} document carries no list")
        items.extend(chunk)
        total = document.get("total_count", len(items))
        if not chunk or len(items) >= total:
            break
        page += 1
        require(page <= max_pages, f"the {field} pagination exceeded {max_pages} pages")
    require(len(items) <= 1000, f"the {field} list is unreasonably large")
    return items


def fetch_jobs(api: Api, repository: str, run_id: int) -> list:
    return _paginate(api, f"/repos/{repository}/actions/runs/{run_id}/jobs?filter=latest",
                     "jobs")


def verify_jobs(jobs: list, head_sha: str) -> dict:
    by_name: dict[str, list] = {}
    for job in jobs:
        require(isinstance(job, dict), "a job entry is not an object")
        name = job.get("name")
        require(isinstance(name, str) and name, "a job entry has no name")
        by_name.setdefault(name, []).append(job)
    for name in (PIN_JOB_NAME, BUILD_JOB_NAME):
        require(len(by_name.get(name, [])) == 1,
                f"expected exactly one {name!r} job, found {len(by_name.get(name, []))}")

    pin_job = by_name[PIN_JOB_NAME][0]
    require(pin_job.get("status") == "completed" and pin_job.get("conclusion") == "success",
            "the pin job did not complete successfully")

    build_job = by_name[BUILD_JOB_NAME][0]
    require(build_job.get("status") == "completed",
            f"the build job is not completed: {build_job.get('status')!r}")
    require(build_job.get("conclusion") == "success",
            f"the build job did not succeed: {build_job.get('conclusion')!r} (a skipped or failed job is not proof)")
    if "head_sha" in build_job:
        require(build_job.get("head_sha") == head_sha,
                "the build job head sha disagrees with the run head sha")

    steps = build_job.get("steps")
    require(isinstance(steps, list) and steps, "the build job carries no steps")
    conclusions: dict[str, str] = {}
    for step in steps:
        require(isinstance(step, dict), "a build step is not an object")
        name = step.get("name")
        conclusion = step.get("conclusion")
        require(isinstance(name, str) and name, "a build step has no name")
        require(isinstance(conclusion, str) and conclusion, f"step {name!r} has no conclusion")
        require(name not in conclusions, f"duplicate build step {name!r}")
        conclusions[name] = conclusion

    for name in REQUIRED_BUILD_STEPS:
        require(conclusions.get(name) == "success",
                f"required build step {name!r} is {conclusions.get(name)!r}, not success")

    published = conclusions.get(PUBLISHED_COMPARISON_STEP)
    historical = conclusions.get(HISTORICAL_COMPARISON_STEP)
    require(published is not None and historical is not None,
            "the routed Needs/facts comparison steps are missing")
    routes = {"published": published, "historical": historical}
    successes = [route for route, conclusion in routes.items() if conclusion == "success"]
    skipped = [route for route, conclusion in routes.items() if conclusion == "skipped"]
    require(len(successes) == 1 and len(skipped) == 1,
            f"exactly one routed comparison must run: {routes!r}")
    route = successes[0]
    require(conclusions.get("Record the Needs/facts comparison route") == "success",
            "the routed Needs/facts comparison was not recorded")
    if route == "published":
        for name in PUBLISHED_ROUTE_STEPS:
            require(conclusions.get(name) == "success",
                    f"published-route step {name!r} is {conclusions.get(name)!r}, not success")
    else:
        for name in PUBLISHED_ROUTE_STEPS:
            if name == "Record the Needs/facts comparison route":
                continue
            require(conclusions.get(name) == "skipped",
                    f"historical route step {name!r} is {conclusions.get(name)!r}, not skipped")

    require(build_job.get("id") is not None, "the build job has no id")
    return {
        "id": build_job.get("id"),
        "name": BUILD_JOB_NAME,
        "conclusion": "success",
        "comparisonRoute": route,
    }


def fetch_artifacts(api: Api, repository: str, run_id: int) -> list:
    return _paginate(api, f"/repos/{repository}/actions/runs/{run_id}/artifacts", "artifacts")


def verify_artifacts(artifacts: list, run_id: int, head_sha: str) -> dict:
    canonical = [item for item in artifacts
                 if isinstance(item, dict) and item.get("name") == CANDIDATE_ARTIFACT_NAME]
    require(len(canonical) == 1,
            f"expected exactly one {CANDIDATE_ARTIFACT_NAME!r} artifact, found {len(canonical)}")
    artifact = canonical[0]
    require(artifact.get("expired") is False, "the canonical candidate artifact is expired")
    expires_at = parse_iso(artifact.get("expires_at"), "the artifact expiry")
    require(expires_at > datetime.now(timezone.utc) + MIN_ARTIFACT_REMAINING,
            f"the canonical candidate artifact expires too soon: {artifact.get('expires_at')!r}")
    size = artifact.get("size_in_bytes")
    require(isinstance(size, int) and not isinstance(size, bool) and 0 < size <= MAX_ARTIFACT_BYTES,
            f"the artifact size is outside the cap: {size!r}")
    digest = artifact.get("digest")
    require(isinstance(digest, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", digest),
            f"the artifact digest is not sha256:<64hex>: {digest!r}")
    require(isinstance(artifact.get("id"), int), "the artifact id is not an integer")
    workflow_run = artifact.get("workflow_run")
    require(isinstance(workflow_run, dict)
            and workflow_run.get("id") == run_id
            and workflow_run.get("head_sha") == head_sha,
            "the artifact is not attached to the verified run and head sha")
    return {
        "id": artifact["id"],
        "name": CANDIDATE_ARTIFACT_NAME,
        "digest": digest,
        "sizeInBytes": size,
        "expiresAt": expires_at.isoformat().replace("+00:00", "Z"),
    }


# --------------------------------------------------------------------------
# Safe zip extraction
# --------------------------------------------------------------------------


def safe_extract(zip_path: Path, destination: Path) -> list[str]:
    destination = Path(destination)
    require(not destination.exists() or not any(destination.iterdir()),
            "the artifact extraction directory is not empty")
    destination.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    names: list[str] = []
    total = 0
    try:
        archive = zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile, OSError) as exc:
        refuse(f"the artifact zip is unreadable: {exc}")
    with archive:
        infos = archive.infolist()
        require(0 < len(infos) <= MAX_ZIP_ENTRIES,
                f"the zip carries {len(infos)} entries, outside the allowed range")
        for info in infos:
            name = info.filename
            require(isinstance(name, str) and name, "a zip entry has no name")
            require("\x00" not in name, "a zip entry contains a NUL byte")
            require("\\" not in name, f"a zip entry contains a backslash: {name!r}")
            pure = PurePosixPath(name)
            require(not pure.is_absolute(), f"a zip entry is absolute: {name!r}")
            require(all(part not in ("", ".", "..") for part in pure.parts),
                    f"a zip entry traverses outside the extraction root: {name!r}")
            if name in seen:
                refuse(f"duplicate zip entry: {name!r}")
            seen.add(name)
            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                refuse(f"a zip entry is a symlink: {name!r}")
            require(not (mode & 0o6000), f"a zip entry carries setuid/setgid bits: {name!r}")
            if info.is_dir():
                continue
            require(mode == 0 or stat.S_ISREG(mode),
                    f"a zip entry is not a regular file: {name!r} (mode {mode:o})")
            require(info.file_size <= MAX_ZIP_ENTRY_BYTES,
                    f"a zip entry exceeds the per-file cap: {name!r}")
            total += info.file_size
            require(total <= MAX_ZIP_UNCOMPRESSED,
                    "the zip uncompressed size exceeds the cap")
            target = destination.joinpath(*pure.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            written = 0
            with archive.open(info) as source, target.open("xb") as sink:
                while True:
                    chunk = source.read(1 << 20)
                    if not chunk:
                        break
                    written += len(chunk)
                    require(written <= MAX_ZIP_ENTRY_BYTES,
                            f"a zip entry exceeded the per-file cap while extracting: {name!r}")
                    require(total + written - info.file_size <= MAX_ZIP_UNCOMPRESSED,
                            "the zip exceeded the uncompressed cap while extracting")
                    sink.write(chunk)
            require(written == info.file_size,
                    f"a zip entry expanded to an unexpected size: {name!r}")
            target.chmod(0o644)
            names.append(name)
    require(names, "the artifact zip carried no files")
    return names


def check_layout(root: Path, names: list[str]) -> None:
    root = Path(root)
    top = {path.split("/", 1)[0] for path in names}
    require(top <= set(ALLOWED_TOP_LEVEL),
            f"the artifact carries unexpected top-level entries: {sorted(top - set(ALLOWED_TOP_LEVEL))}")
    required = ("candidate-lock/ENGINE-LOCK.json", *REQUIRED_LOGS)
    for rel in required:
        path = root / rel
        require(path.is_file(), f"the artifact is missing {rel}")
    logs = {path[len("logs/"):] for path in names if path.startswith("logs/")}
    require(logs == {rel[len("logs/"):] for rel in REQUIRED_LOGS},
            f"the artifact log set is unexpected: {sorted(logs)}")
    expected_files = {path for path in names
                      if path.startswith("expected-baseline/") and path.count("/") == 2
                      and path.endswith(".json")}
    require(expected_files, "the artifact carries no expected-baseline records")
    for path in names:
        if path.startswith("expected-baseline/"):
            parts = path.split("/")
            require(len(parts) == 3 and parts[1] == "riscv64-docker",
                    f"unexpected expected-baseline entry: {path}")
            require(parts[2] == "MANIFEST.json" or parts[2].endswith(".result.v1.json"),
                    f"unexpected expected-baseline file: {path}")
    dist_binaries = [path for path in names if path.endswith("/floe-impeccable")]
    require(len(dist_binaries) == 1,
            f"expected exactly one compiled candidate binary, found {len(dist_binaries)}")
    require(re.fullmatch(
        r"dist/impeccable-[0-9]+\.[0-9]+\.[0-9]+\+floe\.[0-9]+\.[0-9]+\.[0-9]+/"
        r"riscv64gc-unknown-linux-musl/floe-impeccable", dist_binaries[0]) is not None,
        f"the compiled candidate binary is not in the canonical dist path: {dist_binaries[0]}")
    dist_root = root / "dist"
    require(dist_root.is_dir(), "the artifact carries no dist tree")
    require(all(path.is_dir() for path in dist_root.iterdir()),
            "the dist root carries a non-directory entry")
    engine_dirs = [path for path in dist_root.iterdir() if path.is_dir()]
    require(len(engine_dirs) == 1, "the dist tree must carry exactly one engine identity")
    require(all(path.is_dir() for path in engine_dirs[0].iterdir()),
            "the engine dist directory carries a non-directory entry")
    targets = [path for path in engine_dirs[0].iterdir() if path.is_dir()]
    require(len(targets) == 1 and targets[0].name == TARGET_TRIPLE,
            "the dist tree must carry exactly the riscv64gc-unknown-linux-musl target")
    present = sorted(path.name for path in targets[0].iterdir())
    require(present == sorted(DIST_FILES),
            f"the dist file set is unexpected: {present}")


# --------------------------------------------------------------------------
# Binary and receipt verification
# --------------------------------------------------------------------------


def elf_facts(path: Path) -> dict:
    data = Path(path).read_bytes()
    require(len(data) >= 64, "the candidate binary is too short to be an ELF")
    require(data[:4] == b"\x7fELF", "the candidate binary does not start with the ELF magic")
    require(data[4] == 2, "the candidate binary is not ELF64")
    require(data[5] == 1, "the candidate binary is not little-endian")
    (e_type, e_machine, e_version, e_entry, e_phoff, e_shoff, e_flags, e_ehsize,
     e_phentsize, e_phnum, e_shentsize, e_shnum, e_shstrndx) = struct.unpack_from(
        "<HHIQQQIHHHHHH", data, 16)
    require(e_type == 2, f"the candidate binary is not ET_EXEC: {e_type}")
    require(e_machine == 243, f"the candidate binary is not RISC-V: e_machine={e_machine}")
    require(e_version == 1, "the candidate binary has an unexpected ELF version")
    require(e_phentsize == 56, f"unexpected program-header size: {e_phentsize}")
    require(e_phnum > 0, "the candidate binary has no program headers")
    require(e_phoff + e_phnum * e_phentsize <= len(data),
            "the candidate program headers run past the file")
    has_interp = False
    has_dynamic = False
    for index in range(e_phnum):
        (p_type, _p_flags, _p_offset, _p_vaddr, _p_paddr, _p_filesz, _p_memsz,
         _p_align) = struct.unpack_from("<IIQQQQQQ", data, e_phoff + index * e_phentsize)
        has_interp = has_interp or p_type == 3
        has_dynamic = has_dynamic or p_type == 2
    require(not has_interp, "the candidate binary has a PT_INTERP dynamic loader")
    require(not has_dynamic, "the candidate binary has a PT_DYNAMIC segment")
    return {
        "e_type": e_type,
        "e_machine": e_machine,
        "elfClass": "ELF64",
        "endian": "little",
        "elfType": "EXEC",
        "static": True,
        "dynamic": False,
    }


def verify_sha256sums(directory: Path) -> dict[str, str]:
    sums_path = Path(directory) / "SHA256SUMS.txt"
    require(sums_path.is_file(), f"missing SHA256SUMS.txt in {directory}")
    require(sums_path.stat().st_size <= 1 << 20,
            f"SHA256SUMS.txt is larger than the 1 MiB cap: {sums_path}")
    entries: dict[str, str] = {}
    for number, line in enumerate(sums_path.read_text(encoding="utf-8").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64})  ([^/\\\x00]+)", line)
        require(match is not None, f"SHA256SUMS.txt line {number} is malformed")
        digest, name = match.group(1), match.group(2)
        require(name not in entries, f"SHA256SUMS.txt names {name!r} twice")
        file_path = Path(directory) / name
        require(file_path.is_file() and file_path.is_symlink() is False,
                f"SHA256SUMS.txt names a non-regular file: {name!r}")
        require(sha256_file(file_path) == digest,
                f"the SHA256SUMS entry for {name!r} does not verify")
        entries[name] = digest
    present = {path.name for path in Path(directory).iterdir() if path.is_file()}
    require(set(entries) == present - {"SHA256SUMS.txt"},
            f"SHA256SUMS.txt does not cover exactly the dist files: {sorted(entries)}")
    require("floe-impeccable" in entries, "SHA256SUMS.txt does not cover the engine binary")
    return entries


def check_baseline_still_current(engine_dir: Path, base_lock: dict,
                                 receipt_path: Path) -> dict:
    require(isinstance(base_lock, dict), "the tracked ENGINE-LOCK.json is not an object")
    engine_id = base_lock.get("engineId")
    require(isinstance(engine_id, str) and ENGINE_ID_RE.fullmatch(engine_id),
            f"the tracked engineId is not canonical: {engine_id!r}")
    upstream = base_lock.get("upstream")
    floe = base_lock.get("floe")
    component = base_lock.get("component")
    require(isinstance(upstream, dict) and isinstance(floe, dict) and isinstance(component, dict),
            "the tracked lock is missing upstream/floe/component")
    adapter = require_semver(floe.get("adapterVersion"), "the tracked adapter version")
    commit = require_hex(upstream.get("commit"), HEX40_RE, "the tracked upstream commit")
    tree = require_hex(upstream.get("tree"), HEX40_RE, "the tracked upstream tree")
    version = require_semver(upstream.get("engineVersion"), "the tracked engine version")
    require(engine_id == f"impeccable-{version}+floe.{adapter}",
            "the tracked engineId disagrees with its own pin/adapter")

    dist = Path(engine_dir) / "dist" / engine_id / TARGET_TRIPLE
    binary = dist / "floe-impeccable"
    require(binary.is_file() and binary.is_symlink() is False,
            f"the published baseline binary is missing: {binary}")
    binary_sha = sha256_file(binary)
    binary_bytes = binary.stat().st_size
    require(component.get("artifactSha256") == binary_sha,
            "the tracked lock artifactSha256 does not match the published baseline binary")
    require(component.get("artifactBytes") == binary_bytes,
            "the tracked lock artifactBytes does not match the published baseline binary")
    sums = verify_sha256sums(dist)
    require(sums.get("floe-impeccable") == binary_sha,
            "the baseline SHA256SUMS entry does not match the published binary")

    receipt = load_json(receipt_path, "the original baseline-binary receipt")
    require(isinstance(receipt, dict), "the baseline-binary receipt is not an object")
    require(receipt.get("ok") is True and receipt.get("mode") == "verify-binary",
            "the original baseline-binary receipt is not a successful verification")
    require(receipt.get("engineId") == engine_id, "the baseline receipt engineId drifted")
    require(receipt.get("componentVersion") == component.get("componentVersion"),
            "the baseline receipt componentVersion drifted")
    require(receipt.get("adapterVersion") == adapter, "the baseline receipt adapterVersion drifted")
    require(receipt.get("sha256") == binary_sha, "the baseline receipt sha256 drifted")
    require(receipt.get("bytes") == binary_bytes, "the baseline receipt size drifted")
    upstream_receipt = receipt.get("upstream")
    require(isinstance(upstream_receipt, dict), "the baseline receipt carries no upstream pin")
    require(upstream_receipt.get("commit") == commit
            and upstream_receipt.get("tree") == tree
            and upstream_receipt.get("engineVersion") == version,
            "the baseline receipt upstream pin drifted")
    contract_sha = sha256_file(Path(engine_dir) / "contract" / "snapshot-contract.v1.json")
    require(receipt.get("contractSnapshotSha256") == contract_sha,
            "the baseline receipt contract digest drifted")
    return {
        "engineId": engine_id,
        "commit": commit,
        "tree": tree,
        "engineVersion": version,
        "adapterVersion": adapter,
        "binarySha256": binary_sha,
        "binaryBytes": binary_bytes,
        "componentVersion": component.get("componentVersion"),
    }


def check_baseline_matches_metadata(engine_dir: Path, base_lock: dict,
                                    baseline: dict) -> None:
    """The write job re-checks the current published base without the artifact.

    `check_baseline_still_current` needs the original receipt from the artifact;
    the write job only has the tiny metadata. This function still proves that
    the tracked lock and the published dist bytes are the same base the
    verification job authenticated, so a later base rebuild cannot be smuggled
    into an existing pin move.
    """
    require(isinstance(baseline, dict), "the metadata baseline is not an object")
    require(baseline.get("engineId") == base_lock.get("engineId"),
            "the metadata baseline engineId is not the tracked published base")
    upstream = base_lock.get("upstream")
    require(isinstance(upstream, dict), "the tracked lock carries no upstream block")
    require(baseline.get("commit") == upstream.get("commit")
            and baseline.get("tree") == upstream.get("tree")
            and baseline.get("engineVersion") == upstream.get("engineVersion"),
            "the metadata baseline pin is not the tracked published pin")
    engine_id = baseline["engineId"]
    dist = Path(engine_dir) / "dist" / engine_id / TARGET_TRIPLE
    binary = dist / "floe-impeccable"
    require(binary.is_file() and binary.is_symlink() is False,
            "the tracked published baseline binary is missing")
    require(sha256_file(binary) == baseline.get("binarySha256"),
            "the tracked published baseline binary digest changed")
    require(binary.stat().st_size == baseline.get("binaryBytes"),
            "the tracked published baseline binary size changed")
    component = base_lock.get("component")
    require(isinstance(component, dict), "the tracked lock carries no component block")
    require(component.get("artifactSha256") == baseline.get("binarySha256")
            and component.get("artifactBytes") == baseline.get("binaryBytes"),
            "the tracked lock component digests drifted from the metadata baseline")
    sums = verify_sha256sums(dist)
    require(sums.get("floe-impeccable") == baseline.get("binarySha256"),
            "the published baseline SHA256SUMS entry drifted")


# --------------------------------------------------------------------------
# Candidate lock / artifact checks
# --------------------------------------------------------------------------


def candidate_from_proposal(proposal: dict) -> dict:
    require(isinstance(proposal, dict), "the candidate lock proposal is not an object")
    upstream = proposal.get("upstream")
    floe = proposal.get("floe")
    require(isinstance(upstream, dict) and isinstance(floe, dict),
            "the candidate lock proposal is missing upstream/floe")
    engine_id = proposal.get("engineId")
    require(isinstance(engine_id, str) and ENGINE_ID_RE.fullmatch(engine_id),
            f"the candidate engineId is not canonical: {engine_id!r}")
    version = require_semver(upstream.get("engineVersion"), "the candidate engine version")
    adapter = require_semver(floe.get("adapterVersion"), "the candidate adapter version")
    require(engine_id == f"impeccable-{version}+floe.{adapter}",
            "the candidate engineId disagrees with its own pin/adapter")
    commit = require_hex(upstream.get("commit"), HEX40_RE, "the candidate upstream commit")
    tree = require_hex(upstream.get("tree"), HEX40_RE, "the candidate upstream tree")
    package_version = require_semver(upstream.get("packageVersion"),
                                     "the candidate upstream package version")
    commit_date = upstream.get("commitDate")
    parse_iso(commit_date, "the candidate commit date")
    subject = upstream.get("commitSubject")
    require(isinstance(subject, str) and subject and len(subject) <= 240
            and all(character.isprintable() for character in subject),
            "the candidate commit subject is not a bounded printable line")
    resolved_via = proposal.get("resolvedVia")
    require(resolved_via in ("local clone", "github api"),
            f"the candidate resolvedVia is unexpected: {resolved_via!r}")
    return {
        "engineVersion": version,
        "commit": commit,
        "tree": tree,
        "adapterVersion": adapter,
        "engineId": engine_id,
        "packageVersion": package_version,
        "commitDate": commit_date,
        "commitSubject": subject,
        "resolvedVia": resolved_via,
    }


def expected_candidate_lock(base_lock: dict, candidate: dict) -> dict:
    expected = copy.deepcopy(base_lock)
    upstream = expected.get("upstream")
    require(isinstance(upstream, dict), "the base lock carries no upstream block")
    previous = {
        "commit": upstream.get("commit"),
        "tree": upstream.get("tree"),
        "engineVersion": upstream.get("engineVersion"),
    }
    upstream["commit"] = candidate["commit"]
    upstream["tree"] = candidate["tree"]
    upstream["engineVersion"] = candidate["engineVersion"]
    upstream["commitDate"] = candidate["commitDate"]
    upstream["commitSubject"] = candidate["commitSubject"]
    upstream["supersededPin"] = {
        "commit": previous["commit"],
        "tree": previous["tree"],
        "engineVersion": previous["engineVersion"],
        "note": SUPERSEDED_NOTE,
    }
    expected["engineId"] = f"impeccable-{candidate['engineVersion']}+floe.{candidate['adapterVersion']}"
    expected["status"] = "candidate-update-not-qualified"
    expected["resolvedVia"] = candidate["resolvedVia"]
    return expected


def check_proposal_against_base(base_lock: dict, proposal: dict, candidate: dict) -> None:
    expected = expected_candidate_lock(base_lock, candidate)
    difference = first_diff(expected, proposal)
    if difference:
        refuse(f"the candidate lock proposal moves more than the reviewed pin fields: {difference}")
    require(proposal.get("status") == "candidate-update-not-qualified",
            "the candidate lock did not preserve candidate-update-not-qualified")
    base_version = require_semver(base_lock.get("upstream", {}).get("engineVersion"),
                                  "the base engine version")
    candidate_version = candidate["engineVersion"]
    # The automatic updater only builds strictly newer releases, but an
    # explicitly dispatched manual-review candidate may intentionally retarget
    # the SAME engine version at a different commit. A same-version build can
    # only reach this point through that manual path (the automatic pin policy
    # marks same/older versions unchanged and the build job is skipped). Keep
    # that review-only case valid against the SAME baseline, while never
    # proposing a downgrade or a no-change pin.
    require(semver_tuple(candidate_version) >= semver_tuple(base_version),
            f"the candidate {candidate_version} is older than the pin {base_version}; "
            "downgrades are never proposed")
    if semver_tuple(candidate_version) == semver_tuple(base_version):
        require(candidate["commit"] != base_lock.get("upstream", {}).get("commit"),
                "the same-version candidate names the base commit; there is nothing to review")


def _identity_value(field: str, identity: dict, diagnostics: dict):
    mapping = {
        "engine.engineId": identity.get("engineId"),
        "engine.upstreamCommit": identity.get("upstreamCommit"),
        "engine.upstreamTree": identity.get("upstreamTree"),
        "engine.upstreamEngineVersion": identity.get("upstreamEngineVersion"),
        "diagnostics.engineVersion": diagnostics.get("engineVersion")
        if isinstance(diagnostics, dict) else None,
        "diagnostics.upstreamCommit": diagnostics.get("upstreamCommit")
        if isinstance(diagnostics, dict) else None,
    }
    require(field in mapping, f"unexpected identity field: {field!r}")
    return mapping[field]


def verify_receipt(receipt: dict, candidate: dict, binary_sha: str, binary_bytes: int,
                   elf: dict, base_lock: dict) -> None:
    require(isinstance(receipt, dict), "the build receipt is not an object")
    require(receipt.get("engineId") == candidate["engineId"], "the build receipt engineId drifted")
    require(receipt.get("componentVersion") ==
            f"{candidate['engineVersion']}+floe.{candidate['adapterVersion']}",
            "the build receipt componentVersion drifted")
    require(receipt.get("adapterVersion") == candidate["adapterVersion"],
            "the build receipt adapterVersion drifted")
    require(receipt.get("contractVersion") == base_lock.get("floe", {}).get("contractVersion"),
            "the build receipt contractVersion drifted")
    require(receipt.get("upstreamPackageVersion") == candidate["packageVersion"],
            "the build receipt upstream package version drifted")
    pin = receipt.get("pin")
    require(isinstance(pin, dict), "the build receipt carries no pin")
    require(pin.get("commit") == candidate["commit"]
            and pin.get("tree") == candidate["tree"]
            and pin.get("engineVersion") == candidate["engineVersion"],
            "the build receipt pin drifted")
    artifact = receipt.get("artifact")
    require(isinstance(artifact, dict), "the build receipt carries no artifact block")
    require(artifact.get("sha256") == binary_sha, "the build receipt binary sha256 drifted")
    require(artifact.get("bytes") == binary_bytes, "the build receipt binary size drifted")
    require(artifact.get("format") == "ELF", "the build receipt does not describe an ELF")
    require(artifact.get("elfClass") == elf["elfClass"], "the build receipt ELF class drifted")
    require(artifact.get("endian") == elf["endian"], "the build receipt ELF endianness drifted")
    require(artifact.get("elfMachine") == "RISC-V", "the build receipt is not RISC-V")
    require(artifact.get("elfType") == elf["elfType"], "the build receipt ELF type drifted")
    require(artifact.get("static") is True and artifact.get("dynamic") is False,
            "the build receipt does not describe a static binary")
    build = receipt.get("build")
    require(isinstance(build, dict), "the build receipt carries no build block")
    require(build.get("target") == TARGET_TRIPLE, "the build receipt target drifted")
    require(build.get("profile") == "release", "the build receipt profile drifted")
    require(build.get("jobs") == 6, "the build receipt job count drifted")
    require(build.get("toolchain") == base_lock.get("toolchain", {}).get("rust"),
            "the build receipt Rust toolchain drifted")
    audit = receipt.get("dependencyAudit")
    require(isinstance(audit, dict), "the build receipt carries no dependency audit")
    for crate in ("ring", "rustls", "aws-lc-rs", "rustls-native-certs", "webpki-roots"):
        entry = audit.get(crate)
        require(isinstance(entry, dict) and entry.get("present") is False,
                f"the dependency audit shows {crate!r} present")
    require(isinstance(audit.get("cratesInGraph"), int) and audit["cratesInGraph"] > 0,
            "the dependency audit graph is empty")
    require(audit.get("target") == TARGET_TRIPLE, "the dependency audit target drifted")


def verify_provenance(provenance: dict, candidate: dict, base_lock: dict, engine_dir: Path,
                      binary_sha: str, binary_bytes: int, stage_log: dict) -> None:
    require(isinstance(provenance, dict), "PROVENANCE.json is not an object")
    require(provenance.get("engineId") == candidate["engineId"],
            "PROVENANCE.json engineId drifted")
    require(provenance.get("binary") == "floe-impeccable", "PROVENANCE.json binary name drifted")
    require(provenance.get("target") == TARGET_TRIPLE, "PROVENANCE.json target drifted")
    upstream = provenance.get("upstream")
    require(isinstance(upstream, dict), "PROVENANCE.json carries no upstream block")
    require(upstream.get("commit") == candidate["commit"]
            and upstream.get("tree") == candidate["tree"]
            and upstream.get("engineVersion") == candidate["engineVersion"]
            and upstream.get("packageVersion") == candidate["packageVersion"],
            "PROVENANCE.json upstream pin drifted")
    floe = provenance.get("floe")
    require(isinstance(floe, dict), "PROVENANCE.json carries no floe block")
    require(floe.get("adapterVersion") == candidate["adapterVersion"],
            "PROVENANCE.json adapter version drifted")
    require(floe.get("contractVersion") == base_lock.get("floe", {}).get("contractVersion"),
            "PROVENANCE.json contract version drifted")
    artifact = provenance.get("artifact")
    require(isinstance(artifact, dict), "PROVENANCE.json carries no artifact block")
    require(artifact.get("sha256") == binary_sha and artifact.get("bytes") == binary_bytes,
            "PROVENANCE.json binary digest drifted")
    require(artifact.get("format") == "ELF" and artifact.get("elfMachine") == "RISC-V"
            and artifact.get("elfType") == "EXEC" and artifact.get("static") is True
            and artifact.get("dynamic") is False,
            "PROVENANCE.json binary format drifted")

    projected = stage_log.get("stagedTestIdentity")
    require(isinstance(projected, dict), "the stage receipt carries no staged test identity")
    projected_files = projected.get("files")
    require(isinstance(projected_files, dict), "the stage receipt carries no projected files")
    adapter_sources = floe.get("adapterSources")
    require(isinstance(adapter_sources, dict) and adapter_sources,
            "PROVENANCE.json carries no adapter source digests")
    for rel, wanted in adapter_sources.items():
        require(isinstance(rel, str) and rel and ".." not in PurePosixPath(rel).parts,
                f"PROVENANCE.json carries an unsafe adapter path: {rel!r}")
        path = Path(engine_dir) / "adapter" / rel
        require(path.is_file(), f"the tracked adapter file is missing: {rel}")
        if rel in projected_files:
            entry = projected_files[rel]
            require(isinstance(entry, dict), f"the stage receipt entry for {rel} is malformed")
            require(entry.get("trackedSha256") == sha256_file(path),
                    f"the stage receipt tracked hash for {rel} does not match the current adapter")
            require(entry.get("stagedSha256") == wanted,
                    f"the stage receipt staged hash for {rel} does not match PROVENANCE.json")
        else:
            require(sha256_file(path) == wanted,
                    f"PROVENANCE.json adapter digest for {rel} does not match the current adapter")
    for rel, entry in projected_files.items():
        require(isinstance(rel, str) and rel and ".." not in PurePosixPath(rel).parts,
                f"the stage receipt carries an unsafe projected path: {rel!r}")
        require(isinstance(entry, dict), f"the stage receipt entry for {rel} is malformed")
        staged_sha = require_hex(entry.get("stagedSha256"), HEX64_RE,
                                 f"the stage receipt staged hash for {rel}")
        require(entry.get("trackedSha256") == sha256_file(Path(engine_dir) / "adapter" / rel),
                f"the stage receipt tracked hash for {rel} is not the current adapter")
        if rel in adapter_sources:
            require(staged_sha == adapter_sources[rel],
                    f"the stage receipt staged hash for {rel} is not bound to PROVENANCE.json")
        else:
            # The stager also projects two adapter test-data fixtures whose
            # bytes are not part of PROVENANCE.json's adapterSources map.
            require(rel.startswith("tests/data/"),
                    f"the stage receipt projects an unexpected file outside adapterSources: {rel!r}")

    contract_files = floe.get("contractFiles")
    require(isinstance(contract_files, dict) and contract_files,
            "PROVENANCE.json carries no contract digests")
    for rel, wanted in contract_files.items():
        require(isinstance(rel, str) and rel and ".." not in PurePosixPath(rel).parts,
                f"PROVENANCE.json carries an unsafe contract path: {rel!r}")
        path = Path(engine_dir) / "contract" / rel
        require(path.is_file(), f"the tracked contract file is missing: {rel}")
        if rel == "snapshot-contract.v1.json":
            require(wanted == stage_log.get("stagedContractSha256"),
                    "the staged snapshot contract digest disagrees with the stage receipt")
        else:
            require(sha256_file(path) == wanted,
                    f"PROVENANCE.json contract digest for {rel} does not match the tracked contract")
    require(stage_log.get("trackedContractSha256") ==
            sha256_file(Path(engine_dir) / "contract" / "snapshot-contract.v1.json"),
            "the stage receipt tracked contract digest does not match the current contract")

    patches = floe.get("patches")
    require(isinstance(patches, list) and patches, "PROVENANCE.json carries no patch digests")
    patch_names = []
    for entry in patches:
        require(isinstance(entry, dict), "a PROVENANCE.json patch entry is malformed")
        name = entry.get("patch")
        require(isinstance(name, str) and name and "/" not in name and name not in patch_names,
                f"the PROVENANCE.json patch name is unsafe: {name!r}")
        path = Path(engine_dir) / "patches" / name
        require(path.is_file(), f"the tracked patch is missing: {name}")
        require(sha256_file(path) == entry.get("sha256"),
                f"PROVENANCE.json patch digest for {name} does not match the tracked patch")
        patch_names.append(name)
    require([f"patches/{name}" for name in patch_names]
            == base_lock.get("floe", {}).get("patches"),
            "the PROVENANCE.json patch list disagrees with the tracked lock")

    toolchain = provenance.get("toolchain")
    require(isinstance(toolchain, dict), "PROVENANCE.json carries no toolchain block")
    require(toolchain.get("target") == TARGET_TRIPLE
            and toolchain.get("profile") == "release"
            and toolchain.get("jobs") == 6
            and toolchain.get("toolchain") == base_lock.get("toolchain", {}).get("rust"),
            "PROVENANCE.json toolchain drifted")


def _verify_behaviour_log(document: dict, what: str, *, architecture: str,
                          binary_sha: str | None) -> None:
    require(isinstance(document, dict), f"{what} is not an object")
    require(document.get("ok") is True, f"{what} is not ok")
    require(document.get("runnerExitCode") == 0, f"{what} did not exit cleanly")
    failures = document.get("failures")
    require(isinstance(failures, list) and not failures, f"{what} carries failures")
    total = document.get("checksTotal")
    passed = document.get("checksPassed")
    checks = document.get("checks")
    require(isinstance(total, int) and total > 0 and passed == total,
            f"{what} did not pass every check")
    require(isinstance(checks, list) and len(checks) == total, f"{what} check list is inconsistent")
    require(all(isinstance(check, dict) and check.get("ok") is True for check in checks),
            f"{what} carries a failed check")
    environment = document.get("environment")
    require(isinstance(environment, dict), f"{what} carries no environment")
    uname = environment.get("uname")
    require(isinstance(uname, list) and len(uname) >= 2 and uname[1] == architecture,
            f"{what} did not run on {architecture}")
    if binary_sha is not None:
        require(environment.get("binarySha256") == binary_sha,
                f"{what} is not bound to the expected binary digest")
    parity = document.get("parity")
    require(isinstance(parity, dict), f"{what} carries no parity block")
    cases = parity.get("cases")
    identical = parity.get("byteIdentical")
    mismatched = parity.get("mismatched")
    require(isinstance(cases, int) and cases > 0 and identical == cases,
            f"{what} did not reproduce every parity case")
    require(isinstance(mismatched, list) and not mismatched,
            f"{what} carries mismatched parity cases")


def verify_logs(extracted: Path, engine_dir: Path, candidate: dict, baseline: dict,
                binary_sha: str, base_lock: dict) -> dict:
    logs = Path(extracted) / "logs"
    stage_log = load_json(logs / "stage-candidate-engine.json", "the stage receipt")
    require(isinstance(stage_log, dict) and stage_log.get("ok") is True,
            "the stage receipt is not ok")
    require(stage_log.get("identitySelfCheck") == "passed",
            "the stage receipt identity self-check did not pass")
    require(stage_log.get("adapterVersion") == candidate["adapterVersion"],
            "the stage receipt adapter version drifted")
    require(stage_log.get("componentVersion") ==
            f"{candidate['engineVersion']}+floe.{candidate['adapterVersion']}",
            "the stage receipt component version drifted")
    staged_candidate = stage_log.get("candidate")
    require(isinstance(staged_candidate, dict), "the stage receipt carries no candidate")
    require(staged_candidate.get("commit") == candidate["commit"]
            and staged_candidate.get("tree") == candidate["tree"]
            and staged_candidate.get("version") == candidate["engineVersion"]
            and staged_candidate.get("engineId") == candidate["engineId"],
            "the stage receipt candidate identity drifted")

    contract_log = load_json(logs / "contract-validation.json", "the contract receipt")
    require(isinstance(contract_log, dict), "the contract receipt is not an object")
    require(contract_log.get("upstreamCommit") == candidate["commit"]
            and contract_log.get("upstreamTree") == candidate["tree"]
            and contract_log.get("engineVersion") == candidate["engineVersion"]
            and contract_log.get("adapterVersion") == candidate["adapterVersion"]
            and contract_log.get("contractVersion") == base_lock.get("floe", {}).get("contractVersion"),
            "the contract receipt identity drifted")
    require(contract_log.get("checksTotal") == contract_log.get("checksPassed")
            and isinstance(contract_log.get("checksTotal"), int)
            and contract_log["checksTotal"] > 0,
            "the contract receipt did not pass every check")
    require(contract_log.get("failures") == [], "the contract receipt carries failures")
    digests = contract_log.get("digests")
    require(isinstance(digests, dict) and digests, "the contract receipt carries no digests")
    for rel, wanted in digests.items():
        require(isinstance(rel, str) and rel and ".." not in PurePosixPath(rel).parts,
                f"the contract receipt carries an unsafe path: {rel!r}")
        if rel == "snapshot-contract.v1.json":
            require(wanted == stage_log.get("stagedContractSha256"),
                    "the contract receipt staged snapshot digest drifted")
        else:
            path = Path(engine_dir) / "contract" / rel
            require(path.is_file(), f"the contract receipt names a missing tracked file: {rel}")
            require(sha256_file(path) == wanted,
                    f"the contract receipt digest for {rel} does not match the tracked contract")

    riscv = load_json(logs / "verify-riscv64.json", "the emulated riscv64 behaviour log")
    _verify_behaviour_log(riscv, "the emulated riscv64 behaviour log",
                          architecture="riscv64", binary_sha=binary_sha)
    host = load_json(logs / "verify-host.json", "the host behaviour log")
    _verify_behaviour_log(host, "the host behaviour log", architecture="x86_64",
                          binary_sha=None)
    baselinerun = load_json(logs / "verify-baseline.json", "the published baseline behaviour log")
    _verify_behaviour_log(baselinerun, "the published baseline behaviour log",
                          architecture="riscv64", binary_sha=baseline["binarySha256"])
    require(riscv.get("checksTotal") == baselinerun.get("checksTotal"),
            "the candidate and baseline behaviour matrices differ in size")

    record = load_json(logs / "baseline-record-verify.json", "the baseline record receipt")
    require(isinstance(record, dict) and record.get("ok") is True
            and record.get("mode") == "verify-record",
            "the baseline record receipt is not a successful verification")
    require(record.get("engineId") == baseline["engineId"], "the baseline record engineId drifted")
    require(record.get("engineSha256") == baseline["binarySha256"],
            "the baseline record binary digest drifted")
    require(record.get("cases") == record.get("trackedGoldenCasesCovered")
            and isinstance(record.get("cases"), int) and record["cases"] > 0,
            "the baseline record does not cover the tracked goldens")

    comparison = load_json(logs / "golden-comparison-vs-baseline.json",
                           "the routed needs/facts comparison")
    require(isinstance(comparison, dict) and comparison.get("ok") is True,
            "the routed needs/facts comparison is not ok")
    require(comparison.get("goldenLabel") == f"published-baseline-{baseline['engineId']}",
            "the routed comparison label drifted")
    require(comparison.get("candidateRunner") == "linux/riscv64",
            "the routed comparison did not run on emulated riscv64")
    engine_doc = comparison.get("engine")
    require(isinstance(engine_doc, dict), "the routed comparison carries no engine block")
    require(engine_doc.get("observedSha256") == binary_sha,
            "the routed comparison observed a different candidate binary")
    require(engine_doc.get("goldenSha256") == baseline["binarySha256"],
            "the routed comparison used a different published baseline")
    cases = comparison.get("cases")
    require(isinstance(cases, int) and cases > 0 and comparison.get("identical") == cases,
            "the routed comparison did not reproduce every case")
    require(comparison.get("changed") == 0 and comparison.get("changedUnapproved") == []
            and comparison.get("missing") == [] and comparison.get("newCases") == [],
            "the routed comparison carries a behavioural difference")
    require(comparison.get("verification") == riscv.get("checksTotal"),
            "the routed comparison verification count drifted")
    identity = comparison.get("candidateIdentity")
    require(isinstance(identity, dict) and identity.get("authenticated") is True,
            "the routed comparison candidate identity was not authenticated")
    changes = identity.get("changes")
    require(isinstance(changes, list), "the routed comparison carries no identity changes")
    for change in changes:
        require(isinstance(change, dict), "a routed identity change is malformed")
        field = change.get("field")
        require(field in ALLOWED_IDENTITY_FIELDS,
                f"the routed comparison allowed a non-identity field to move: {field!r}")
        if field.startswith("diagnostics."):
            old_value, new_value = (base_lock["upstream"].get("engineVersion"),
                                    candidate["engineVersion"]) if field == "diagnostics.engineVersion" else (
                base_lock["upstream"].get("commit"), candidate["commit"])
        else:
            old_value, new_value = {
                "engine.engineId": (base_lock["engineId"], candidate["engineId"]),
                "engine.upstreamCommit": (base_lock["upstream"]["commit"], candidate["commit"]),
                "engine.upstreamTree": (base_lock["upstream"]["tree"], candidate["tree"]),
                "engine.upstreamEngineVersion": (base_lock["upstream"]["engineVersion"],
                                                 candidate["engineVersion"]),
            }[field]
        require(change.get("goldenValue") == old_value
                and change.get("candidateValue") == new_value,
                f"the routed identity change for {field} does not match the pin move")

    expected = load_json(Path(extracted) / "expected-baseline" / "riscv64-docker" / "MANIFEST.json",
                         "the baseline manifest")
    require(isinstance(expected, dict) and expected.get("kind") == "engine-observed goldens",
            "the baseline manifest kind drifted")
    expected_engine = expected.get("engine")
    require(isinstance(expected_engine, dict)
            and expected_engine.get("sha256") == baseline["binarySha256"],
            "the baseline manifest is not bound to the published binary")
    expected_cases = expected.get("cases")
    require(isinstance(expected_cases, dict) and expected_cases,
            "the baseline manifest carries no cases")
    for case, entry in expected_cases.items():
        require(isinstance(entry, dict), f"baseline case {case!r} is malformed")
        name = entry.get("file")
        require(isinstance(name, str) and name and "/" not in name and "\\" not in name,
                f"baseline case {case!r} names an unsafe file")
        path = Path(extracted) / "expected-baseline" / "riscv64-docker" / name
        require(path.is_file(), f"baseline case {case!r} file is missing")
        require(entry.get("sha256") == sha256_file(path),
                f"baseline case {case!r} drifted from the manifest digest")
        result = load_json(path, f"baseline case {case!r}")
        result_engine = result.get("engine") if isinstance(result, dict) else None
        require(isinstance(result_engine, dict), f"baseline case {case!r} carries no engine block")
        require(result_engine.get("engineId") == baseline["engineId"]
                and result_engine.get("upstreamCommit") == baseline["commit"]
                and result_engine.get("upstreamTree") == baseline["tree"]
                and result_engine.get("upstreamEngineVersion") == baseline["engineVersion"]
                and result_engine.get("floeAdapterVersion") == baseline["adapterVersion"]
                and result_engine.get("adapterCrateVersion") == baseline["adapterVersion"]
                and result_engine.get("targetTriple") == TARGET_TRIPLE
                and result_engine.get("runtimeExecution") == "riscv64-linux",
                f"baseline case {case!r} does not carry the published identity")

    return {
        "stage": stage_log,
        "contract": contract_log,
        "riscv": riscv,
        "host": host,
        "baselineRun": baselinerun,
        "record": record,
        "comparison": comparison,
        "expected": expected,
    }


def verify_source_lock(extracted: Path, candidate: dict) -> None:
    root = Path(extracted) / "sources-impeccable"
    lock = load_json(root / "SOURCE-LOCK.json", "the derived source lock")
    require(isinstance(lock, dict), "the derived source lock is not an object")
    upstream = lock.get("upstream")
    require(isinstance(upstream, dict), "the derived source lock carries no upstream block")
    require(upstream.get("commit") == candidate["commit"]
            and upstream.get("tree") == candidate["tree"]
            and upstream.get("engineVersion") == candidate["engineVersion"]
            and upstream.get("skillPackageVersion") == candidate["packageVersion"],
            "the derived source lock upstream pin drifted")
    pairing = lock.get("pairing")
    require(isinstance(pairing, dict) and pairing.get("engineId") == candidate["engineId"],
            "the derived source lock engine pairing drifted")
    derived = lock.get("derivedFiles")
    require(isinstance(derived, dict) and derived, "the derived source lock carries no file digests")
    require(lock.get("derivedFileCount") == len(derived),
            "the derived source lock file count drifted")
    for rel, wanted in derived.items():
        require(isinstance(rel, str) and rel and ".." not in PurePosixPath(rel).parts,
                f"the derived source lock carries an unsafe path: {rel!r}")
        path = root / rel
        require(path.is_file() and path.is_symlink() is False,
                f"the derived source file is missing: {rel}")
        require(sha256_file(path) == wanted,
                f"the derived source file drifted from its recorded digest: {rel}")
    version_file = root / "skill" / "VERSION"
    require(version_file.is_file(), "the derived skill source carries no VERSION file")
    require(version_file.read_text(encoding="utf-8").strip() == candidate["engineVersion"],
            "the derived skill VERSION does not match the candidate engine version")


def verify_candidate_artifact(extracted: Path, engine_dir: Path, base_lock: dict,
                              baseline: dict) -> dict:
    lock_path = Path(extracted) / "candidate-lock" / "ENGINE-LOCK.json"
    raw = lock_path.read_bytes()
    proposal = load_json(lock_path, "the candidate lock proposal")
    require(canonical_lock_bytes(proposal) == raw,
            "the candidate lock proposal is not in the canonical update_lock.py serialization")
    candidate = candidate_from_proposal(proposal)
    check_proposal_against_base(base_lock, proposal, candidate)

    dist = Path(extracted) / "dist" / candidate["engineId"] / TARGET_TRIPLE
    binary = dist / "floe-impeccable"
    require(binary.is_file() and binary.is_symlink() is False,
            "the candidate binary is missing from the artifact")
    binary_sha = sha256_file(binary)
    binary_bytes = binary.stat().st_size
    require(binary_bytes > 0 and binary_bytes <= MAX_ZIP_ENTRY_BYTES,
            "the candidate binary size is outside the allowed range")
    sums = verify_sha256sums(dist)
    require(sums.get("floe-impeccable") == binary_sha,
            "the candidate SHA256SUMS entry does not match the binary")
    elf = elf_facts(binary)
    receipt = load_json(dist / "BUILD-RECEIPT.json", "the candidate build receipt")
    verify_receipt(receipt, candidate, binary_sha, binary_bytes, elf, base_lock)

    logs = verify_logs(extracted, engine_dir, candidate, baseline, binary_sha, base_lock)
    provenance = load_json(dist / "PROVENANCE.json", "the candidate provenance")
    verify_provenance(provenance, candidate, base_lock, engine_dir,
                      binary_sha, binary_bytes, logs["stage"])
    verify_source_lock(extracted, candidate)

    return {
        "candidate": candidate,
        "proposal": proposal,
        "proposalSha256": sha256_bytes(raw),
        "binarySha256": binary_sha,
        "binaryBytes": binary_bytes,
        "elf": elf,
        "receipt": receipt,
        "provenance": provenance,
        "logs": logs,
    }

# --------------------------------------------------------------------------
# Metadata payload validation (shared with the PR write job)
# --------------------------------------------------------------------------


def _require_keys(document: dict, keys: tuple[str, ...], what: str) -> None:
    require(isinstance(document, dict), f"{what} is not an object")
    require(set(document) == set(keys),
            f"{what} has unexpected/missing keys: {sorted(set(document) ^ set(keys))}")


def validate_metadata_payload(metadata: dict, repo_root, repository: str) -> dict:
    repo_root = Path(repo_root).resolve()
    _require_keys(metadata, METADATA_KEYS, "the verified metadata payload")
    require(metadata.get("schema") == METADATA_SCHEMA,
            f"the metadata schema is not {METADATA_SCHEMA}")
    require(metadata.get("repository") == repository == OFFICIAL_REPOSITORY,
            "the metadata repository is not the fixed official repository")
    require(metadata.get("updaterWorkflow") == UPDATER_WORKFLOW_PATH,
            "the metadata does not name the fixed updater workflow")

    source = metadata.get("sourceRun")
    _require_keys(source, SOURCE_RUN_KEYS, "the metadata sourceRun")
    run_id = validate_run_id(source.get("id"))
    require(source.get("attempt") == 1, "the metadata source run is not attempt 1")
    head_sha = require_hex(source.get("headSha"), HEX40_RE, "the metadata source head sha")
    require(source.get("headBranch") == "main", "the metadata source run is not on main")
    require(source.get("event") in ("workflow_dispatch", "schedule"),
            "the metadata source event is not trusted")
    require(source.get("conclusion") == "success", "the metadata source run is not successful")
    require(source.get("url") == f"https://github.com/{repository}/actions/runs/{run_id}",
            "the metadata source run URL is not the immutable canonical URL")

    build = metadata.get("buildJob")
    _require_keys(build, BUILD_JOB_KEYS, "the metadata buildJob")
    require(isinstance(build.get("id"), int), "the metadata build job id is not an integer")
    require(build.get("name") == BUILD_JOB_NAME, "the metadata names another build job")
    require(build.get("conclusion") == "success", "the metadata build job is not successful")
    require(build.get("comparisonRoute") in ("published", "historical"),
            "the metadata comparison route is unexpected")

    artifact = metadata.get("artifact")
    _require_keys(artifact, ARTIFACT_KEYS, "the metadata artifact")
    require(isinstance(artifact.get("id"), int) and not isinstance(artifact.get("id"), bool),
            "the metadata artifact id is not an integer")
    require(artifact.get("name") == CANDIDATE_ARTIFACT_NAME,
            "the metadata artifact name is not canonical")
    require(isinstance(artifact.get("digest"), str)
            and re.fullmatch(r"sha256:[0-9a-f]{64}", artifact["digest"]),
            "the metadata artifact digest is malformed")
    require(isinstance(artifact.get("sizeInBytes"), int)
            and 0 < artifact["sizeInBytes"] <= MAX_ARTIFACT_BYTES,
            "the metadata artifact size is outside the cap")
    require(parse_iso(artifact.get("expiresAt"), "the metadata artifact expiry")
            > datetime.now(timezone.utc), "the metadata artifact is already expired")

    candidate_doc = metadata.get("candidate")
    _require_keys(candidate_doc, CANDIDATE_KEYS, "the metadata candidate")
    candidate = {
        "engineVersion": require_semver(candidate_doc.get("engineVersion"),
                                        "the metadata candidate engine version"),
        "commit": require_hex(candidate_doc.get("commit"), HEX40_RE,
                              "the metadata candidate commit"),
        "tree": require_hex(candidate_doc.get("tree"), HEX40_RE,
                            "the metadata candidate tree"),
        "adapterVersion": require_semver(candidate_doc.get("adapterVersion"),
                                         "the metadata candidate adapter version"),
        "engineId": candidate_doc.get("engineId"),
        "packageVersion": require_semver(candidate_doc.get("packageVersion"),
                                         "the metadata candidate package version"),
        "commitDate": candidate_doc.get("commitDate"),
        "commitSubject": candidate_doc.get("commitSubject"),
        "resolvedVia": candidate_doc.get("resolvedVia"),
    }
    require(isinstance(candidate["engineId"], str)
            and ENGINE_ID_RE.fullmatch(candidate["engineId"]),
            "the metadata candidate engineId is not canonical")
    require(candidate["engineId"] ==
            f"impeccable-{candidate['engineVersion']}+floe.{candidate['adapterVersion']}",
            "the metadata candidate engineId disagrees with its pin")
    parse_iso(candidate["commitDate"], "the metadata candidate commit date")
    require(isinstance(candidate["commitSubject"], str) and candidate["commitSubject"]
            and len(candidate["commitSubject"]) <= 240
            and all(character.isprintable() for character in candidate["commitSubject"]),
            "the metadata candidate commit subject is not a bounded printable line")
    require(candidate["resolvedVia"] in ("local clone", "github api"),
            "the metadata candidate resolvedVia is unexpected")

    baseline_doc = metadata.get("baseline")
    _require_keys(baseline_doc, BASELINE_KEYS, "the metadata baseline")
    baseline = {
        "engineId": baseline_doc.get("engineId"),
        "commit": require_hex(baseline_doc.get("commit"), HEX40_RE,
                              "the metadata baseline commit"),
        "tree": require_hex(baseline_doc.get("tree"), HEX40_RE,
                            "the metadata baseline tree"),
        "engineVersion": require_semver(baseline_doc.get("engineVersion"),
                                        "the metadata baseline engine version"),
        "binarySha256": require_hex(baseline_doc.get("binarySha256"), HEX64_RE,
                                    "the metadata baseline binary sha256"),
        "binaryBytes": baseline_doc.get("binaryBytes"),
    }
    require(isinstance(baseline["engineId"], str)
            and ENGINE_ID_RE.fullmatch(baseline["engineId"]),
            "the metadata baseline engineId is not canonical")
    require(isinstance(baseline["binaryBytes"], int) and baseline["binaryBytes"] > 0,
            "the metadata baseline binary size is invalid")

    binary = metadata.get("binary")
    _require_keys(binary, BINARY_KEYS, "the metadata binary")
    expected_path = (f"dist/{candidate['engineId']}/{TARGET_TRIPLE}/floe-impeccable")
    require(binary.get("path") == expected_path, "the metadata binary path is not canonical")
    require_hex(binary.get("sha256"), HEX64_RE, "the metadata binary sha256")
    require(isinstance(binary.get("bytes"), int) and not isinstance(binary.get("bytes"), bool)
            and binary["bytes"] > 0, "the metadata binary size is invalid")
    require(binary.get("elfMachine") == 243, "the metadata binary is not RISC-V")
    require(binary.get("static") is True, "the metadata binary is not static")

    proposal = metadata.get("lockProposal")
    require(isinstance(proposal, dict), "the metadata lock proposal is not an object")
    proposal_sha = require_hex(metadata.get("lockProposalSha256"), HEX64_RE,
                               "the metadata lock proposal sha256")
    require(sha256_bytes(canonical_lock_bytes(proposal)) == proposal_sha,
            "the metadata lock proposal does not match its recorded digest")
    require(candidate_from_proposal(proposal) == candidate,
            "the metadata candidate does not match the lock proposal")

    base_lock = load_json(repo_root / LOCK_REL, "the tracked ENGINE-LOCK.json")
    check_proposal_against_base(base_lock, proposal, candidate)
    check_baseline_matches_metadata(Path(repo_root) / "engines" / "impeccable",
                                    base_lock, baseline)

    protected = metadata.get("protectedInputs")
    _require_keys(protected, PROTECTED_KEYS, "the metadata protectedInputs")
    require(protected.get("paths") == list(PROTECTED_PATHS),
            "the metadata protected-input path list is not the fixed list")
    require_hex(protected.get("digest"), HEX64_RE, "the metadata protected-input digest")

    recipe = metadata.get("recipe")
    _require_keys(recipe, RECIPE_KEYS, "the metadata recipe")
    require_hex(recipe.get("prefixSha256"), HEX64_RE, "the metadata recipe prefix digest")
    require_hex(recipe.get("headWorkflowBlob"), HEX40_RE, "the metadata recipe blob sha")

    parse_iso(metadata.get("verifiedAt"), "the metadata verification time")

    assert_current_tree_still_matches(repo_root, metadata)
    return {
        "source": source,
        "build": build,
        "artifact": artifact,
        "candidate": candidate,
        "baseline": baseline,
        "binary": binary,
        "proposal": proposal,
        "proposalSha256": proposal_sha,
    }


def assert_current_tree_still_matches(repo_root, metadata: dict) -> None:
    repo_root = Path(repo_root).resolve()
    head_sha = metadata["sourceRun"]["headSha"]
    current = git_out(repo_root, "rev-parse", "HEAD")
    require_hex(current, HEX40_RE, "the current HEAD")
    proc = git(repo_root, "cat-file", "-e", f"{head_sha}^{{commit}}", check=False)
    require(proc.returncode == 0,
            f"the source run head {head_sha} is not present in the current checkout")
    proc = git(repo_root, "merge-base", "--is-ancestor", head_sha, current, check=False)
    require(proc.returncode == 0,
            "the source run head is not an ancestor of the current main checkout")
    drift = git(repo_root, "diff", "--name-status", head_sha, current, "--",
                *PROTECTED_PATHS, check=False)
    require(drift.returncode == 0, "git could not compare the protected inputs")
    require(not drift.stdout.strip(),
            f"the protected engine inputs drifted after the source run: {drift.stdout.strip()[:500]}")
    require(protected_inputs_digest(repo_root, head_sha) == metadata["protectedInputs"]["digest"],
            "the protected-input digest does not match the source run")
    require(protected_inputs_digest(repo_root, current) == metadata["protectedInputs"]["digest"],
            "the protected-input digest does not match the current checkout")

    prefix = recipe_prefix_bytes(repo_root, head_sha)
    current_prefix = recipe_prefix_bytes(repo_root, current)
    require(sha256_bytes(prefix) == metadata["recipe"]["prefixSha256"],
            "the source run recipe prefix digest does not match")
    require(current_prefix == prefix,
            "the updater recipe above open-update-pr changed after the source run")
    require(git_out(repo_root, "rev-parse", f"{head_sha}:{UPDATER_WORKFLOW_PATH}")
            == metadata["recipe"]["headWorkflowBlob"],
            "the source run updater workflow blob drifted")
    clean = git(repo_root, "diff", "--quiet", "HEAD", "--", UPDATER_WORKFLOW_PATH, check=False)
    require(clean.returncode == 0,
            "the updater workflow has uncommitted changes in the write checkout")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def prepare_work_dir(path: Path) -> Path:
    path = Path(path)
    if path.exists():
        require(path.is_dir(), f"the work directory is not a directory: {path}")
        require(not any(path.iterdir()), f"the work directory is not empty: {path}")
    else:
        path.mkdir(parents=True)
    return path


def verify(args) -> dict:
    repository = validate_repository(args.repository)
    run_id = validate_run_id(args.run_id)
    repo_root = Path(args.repo_root).resolve()
    engine_dir = Path(args.engine_dir).resolve()
    require(engine_dir == repo_root / "engines" / "impeccable",
            f"the engine directory is not {repo_root / 'engines' / 'impeccable'}")
    require(git(repo_root, "rev-parse", "--show-toplevel").stdout.strip() == str(repo_root),
            "the repository root is not the git top level")
    status = git(repo_root, "status", "--porcelain", "--untracked-files=all").stdout
    require(not status.strip(),
            f"the verification checkout is not clean: {status.strip()[:500]}")

    api = Api(args.api_base, api_token())
    run = fetch_run(api, repository, run_id)
    head_sha = run["head_sha"]
    jobs = fetch_jobs(api, repository, run_id)
    build_job = verify_jobs(jobs, head_sha)
    artifacts = fetch_artifacts(api, repository, run_id)
    artifact = verify_artifacts(artifacts, run_id, head_sha)

    work = prepare_work_dir(Path(args.work_dir))
    zip_path = work / "artifact.zip"
    api.download(f"/repos/{repository}/actions/artifacts/{artifact['id']}/zip",
                 zip_path, MAX_ARTIFACT_BYTES)
    downloaded_sha = sha256_file(zip_path)
    require(f"sha256:{downloaded_sha}" == artifact["digest"],
            "the downloaded artifact digest does not match GitHub's recorded digest")
    extracted = work / "artifact"
    names = safe_extract(zip_path, extracted)
    check_layout(extracted, names)

    current = git_out(repo_root, "rev-parse", "HEAD")
    require_hex(current, HEX40_RE, "the current HEAD")
    require(git(repo_root, "cat-file", "-e", f"{head_sha}^{{commit}}", check=False).returncode == 0,
            f"the source run head {head_sha} is not present in the current checkout")
    require(git(repo_root, "merge-base", "--is-ancestor", head_sha, current,
                check=False).returncode == 0,
            "the source run head is not an ancestor of the current main checkout")
    drift = git(repo_root, "diff", "--name-status", head_sha, current, "--",
                *PROTECTED_PATHS, check=False)
    require(drift.returncode == 0, "git could not compare the protected inputs")
    require(not drift.stdout.strip(),
            f"the protected engine inputs drifted after the source run: {drift.stdout.strip()[:500]}")
    run_prefix = recipe_prefix_bytes(repo_root, head_sha)
    current_prefix = recipe_prefix_bytes(repo_root, current)
    require(run_prefix == current_prefix,
            "the updater recipe above open-update-pr changed after the source run")

    base_lock = load_json(engine_dir / "ENGINE-LOCK.json", "the tracked ENGINE-LOCK.json")
    baseline = check_baseline_still_current(
        engine_dir, base_lock, extracted / "logs" / "baseline-binary-verify.json")
    verified = verify_candidate_artifact(extracted, engine_dir, base_lock, baseline)
    candidate = verified["candidate"]

    require(verified["binarySha256"] == verified["receipt"]["artifact"]["sha256"],
            "the candidate binary digest is not the build receipt digest")
    require(verified["binaryBytes"] == verified["receipt"]["artifact"]["bytes"],
            "the candidate binary size is not the build receipt size")
    require(verified["elf"]["e_machine"] == 243 and verified["elf"]["static"] is True,
            "the candidate binary is not a static RISC-V ELF")

    protected_digest = protected_inputs_digest(repo_root, head_sha)
    metadata = {
        "schema": METADATA_SCHEMA,
        "repository": repository,
        "updaterWorkflow": UPDATER_WORKFLOW_PATH,
        "sourceRun": {
            "id": run_id,
            "attempt": run["run_attempt"],
            "headSha": head_sha,
            "headBranch": run["head_branch"],
            "event": run["event"],
            "conclusion": run["conclusion"],
            "url": f"https://github.com/{repository}/actions/runs/{run_id}",
        },
        "buildJob": build_job,
        "artifact": artifact,
        "candidate": candidate,
        "baseline": {key: baseline[key] for key in BASELINE_KEYS},
        "binary": {
            "path": f"dist/{candidate['engineId']}/{TARGET_TRIPLE}/floe-impeccable",
            "sha256": verified["binarySha256"],
            "bytes": verified["binaryBytes"],
            "elfMachine": verified["elf"]["e_machine"],
            "static": verified["elf"]["static"],
        },
        "lockProposal": verified["proposal"],
        "lockProposalSha256": verified["proposalSha256"],
        "protectedInputs": {
            "paths": list(PROTECTED_PATHS),
            "digest": protected_digest,
        },
        "recipe": {
            "prefixSha256": sha256_bytes(run_prefix),
            "headWorkflowBlob": git_out(repo_root, "rev-parse",
                                        f"{head_sha}:{UPDATER_WORKFLOW_PATH}"),
        },
        "verifiedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    # Validate the payload through exactly the same gate the write job uses.
    validate_metadata_payload(metadata, repo_root, repository)
    write_json(args.out, metadata)
    return {
        "ok": True,
        "repository": repository,
        "run": run_id,
        "headSha": head_sha,
        "artifact": artifact,
        "candidate": candidate,
        "route": build_job["comparisonRoute"],
        "binarySha256": verified["binarySha256"],
        "output": str(Path(args.out).resolve()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify a completed updater run and emit tiny PR metadata.")
    parser.add_argument("--repository", required=True,
                        help=f"must be {OFFICIAL_REPOSITORY}")
    parser.add_argument("--run-id", required=True,
                        help="completed successful impeccable-engine-updater run id")
    parser.add_argument("--engine-dir", required=True, type=Path,
                        help="the current engines/impeccable checkout")
    parser.add_argument("--repo-root", type=Path, default=Path("."),
                        help="the current repository root (default: .)")
    parser.add_argument("--work-dir", required=True, type=Path,
                        help="empty scratch directory for the downloaded artifact")
    parser.add_argument("--out", required=True, type=Path,
                        help="where to write the tiny verified metadata payload")
    parser.add_argument("--api-base", default="https://api.github.com",
                        help="GitHub API origin (loopback HTTP is allowed for tests)")
    args = parser.parse_args()
    try:
        result = verify(args)
    except Refusal as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
