#!/usr/bin/env python3
"""Commit one verified ENGINE-LOCK proposal and open (or report) its draft PR.

This is the write half of the PR-only recovery path and the shared tail of the
normal updater. It is deliberately small and fail-closed:

  * the branch is fixed by the candidate version (`chore/impeccable-engine-X`);
  * only `engines/impeccable/ENGINE-LOCK.json` may be committed — the helper
    refuses any other staged, untracked or committed file, and never copies a
    binary, source packet, descriptor or current-main change into the review
    branch;
  * the commit is made with the corrected `git -c key=value` identity form and
    a real git failure propagates (no `|| exit 0`);
  * only a genuinely empty cached diff is a no-op; the lock must already carry
    the exact verified proposal, otherwise the helper fails;
  * an existing open draft PR is reported idempotently only when its branch
    lock proposes the same candidate pin (byte-identical except for the
    descriptive `commitDate` UTC-offset spelling and `resolvedVia` label that
    the local-clone and API resolution paths legitimately differ on) and every
    changed file is still the lock; a conflicting branch, a non-draft PR, a
    user edit to any real field, a fork PR or any extra file is a HOLD with no
    force-push and no overwrite;
  * a matching branch that lost its PR is re-proposed without touching the
    branch; otherwise the branch is created from the current checkout and
    pushed without force;
  * the created PR is read back and must really be a draft whose only file is
    the lock.

Two input modes:

  --metadata <verified payload>   write the exact lock proposal carried by the
                                  payload produced by verify_candidate_reuse.py
                                  (the payload is re-validated here, including
                                  the current-tree/protected-input digests), and
                                  render a truthful PR body from that payload;
  --lock-auto --candidate-commit <sha> --candidate-version <semver>
                                  the normal updater has already run the trusted
                                  update_lock.py; this helper only validates the
                                  resulting lock, commits, pushes and opens the
                                  draft PR using the supplied body file.

Nothing is merged, approved, signed, published or installed. `gh` is used with
the workflow's default token only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# Importing the local verifier must never create an untracked __pycache__
# directory in the repository the write job later checks for cleanliness.
sys.dont_write_bytecode = True
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import verify_candidate_reuse as reuse  # noqa: E402

PR_URL_RE = re.compile(
    r"https://github\.com/JiangNanGenius/floe-skill-hub/pull/[0-9]+")
MAX_BODY_BYTES = 64 << 10
COMMIT_NAME = "floe-skill-hub-bot"
COMMIT_EMAIL = "bot@users.noreply.github.com"


def git_bytes(repo_root: Path, *args: str) -> bytes:
    proc = subprocess.run(["git", "-C", str(repo_root), *args],
                          capture_output=True)
    if proc.returncode != 0:
        reuse.refuse(f"git {' '.join(args)} failed: "
                     f"{proc.stderr.decode('utf-8', 'replace').strip()[:500]}")
    return proc.stdout


def gh_run(gh_bin: str, args: list[str]) -> str:
    environment = dict(os.environ)
    environment["GH_PROMPT_DISABLED"] = "1"
    environment["NO_COLOR"] = "1"
    proc = subprocess.run([gh_bin, *args], capture_output=True, text=True,
                          env=environment)
    if proc.returncode != 0:
        reuse.refuse(f"gh {args[0]} {args[1]} failed: {proc.stderr.strip()[:500]}")
    return proc.stdout


def gh_json(gh_bin: str, args: list[str]):
    output = gh_run(gh_bin, args)
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        reuse.refuse(f"gh returned invalid JSON: {exc}")


def check_status(repo_root: Path, lock_rel: str, *, allow_lock: bool) -> None:
    status = reuse.git(repo_root, "status", "--porcelain", "--untracked-files=all").stdout
    lines = [line for line in status.splitlines() if line.strip()]
    if not allow_lock:
        reuse.require(not lines,
                      f"the write checkout is not clean: {status.strip()[:500]}")
        return
    for line in lines:
        code, _, path = line[:2], line[2:3], line[3:]
        reuse.require(path == lock_rel and code in {" M", "M ", "MM", "A ", "AM"},
                      f"refusing to touch anything other than {lock_rel}: {line!r}")


def read_base_lock(repo_root: Path, lock_rel: str) -> dict:
    raw = git_bytes(repo_root, "show", f"HEAD:{lock_rel}")
    try:
        base = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        reuse.refuse(f"the committed ENGINE-LOCK.json at HEAD is unusable: {exc}")
    reuse.require(isinstance(base, dict), "the committed ENGINE-LOCK.json is not an object")
    return base


def render_review_body(metadata: dict) -> str:
    source = metadata["sourceRun"]
    artifact = metadata["artifact"]
    candidate = metadata["candidate"]
    baseline = metadata["baseline"]
    build = metadata["buildJob"]
    repository = metadata["repository"]
    run_url = source["url"]
    artifact_url = f"https://github.com/{repository}/actions/artifacts/{artifact['id']}"
    source_url = f"https://github.com/{repository}/commit/{source['headSha']}"
    route = build["comparisonRoute"]
    return f"""## Impeccable engine {candidate['engineVersion']} — draft review proposal

This draft PR was created by the PR-only recovery workflow from an already
completed, successful updater run. **No native rebuild ran for this PR**: the
verified candidate binary and its receipts were reused unchanged.

- current pin: `{baseline['engineVersion']}` @ `{baseline['commit']}`
- candidate: `{candidate['engineVersion']}` @ `{candidate['commit']}` (tree `{candidate['tree']}`, adapter `{candidate['adapterVersion']}`, upstream package `{candidate['packageVersion']}`)
- source commit: {source_url}
- source run: [run {source['id']}]({run_url}) (`{source['event']}`, attempt {source['attempt']}, `{source['headSha']}`)
- candidate artifact: [`impeccable-engine-candidate` {artifact['id']}]({artifact_url}) with digest `{artifact['digest']}`
- routed comparison: `{route}` (exactly one Needs/facts comparison ran)

Gates that ran on the candidate in that run: pinned-source riscv64 static build
(from the staged candidate engine tree) with the dependency audit, adapter suite
on the host, contract coherence, the behaviour matrix on emulated riscv64 and on
the host, exactly one routed Needs/facts fixpoint regression against the
digest-bound published baseline, and the public stage 1 regeneration of the
candidate-derived skill source.

**Status: `candidate-update-not-qualified`.** This is host and hosted-emulated
proof only. The real Floe Linux guest (TinyEMU) run and the App-side acceptance
have NOT been performed and remain required before packaging or publication.
Nothing here is published, signed, merged or installed. Only
`engines/impeccable/ENGINE-LOCK.json` is proposed in this PR; no binary, source
packet, descriptor or current-main change is included.

Reviewer checklist before this can move forward:

1. read the upstream diff and rebase `patches/0001` if it no longer applies;
2. confirm the skill/engine pairing: run the public regeneration
   (`sh engines/impeccable/build/skill-source/run_pipeline.sh <clone> <hub> <work>`),
   bump the canonical package version deliberately, and adopt `<work>/canonical`
   into `sources/impeccable` by hand — never an unreviewed regenerated packet;
3. bind the new digest-bound descriptor
   (`engines/impeccable/runtime-dependency/descriptor.v1.json`) to the rebuilt
   engine artifact;
4. review the routed Needs/facts comparison (the verify job and the source run
   name the route and its reason): engine identity changes appear as
   `candidateIdentityChanges` evidence and any real finding/coverage change
   stays review-blocking;
5. run the engine in the real Floe Linux guest (TinyEMU; emulated execution is
   not guest proof), record latency and peak memory, and complete the App-side
   acceptance;
6. only then let the release owner package, sign and publish. A failed gate
   leaves the current pin and any installed engine untouched.
"""


def pr_detail(gh_bin: str, repository: str, reference, *, require_files: bool = True) -> dict:
    fields = ("number,url,isDraft,isCrossRepository,headRefName,headRefOid,"
              "files,headRepository,headRepositoryOwner")
    detail = gh_json(gh_bin, ["pr", "view", str(reference), "--repo", repository,
                              "--json", fields])
    reuse.require(isinstance(detail, dict), "the PR detail is not an object")
    url = detail.get("url")
    reuse.require(isinstance(url, str) and PR_URL_RE.fullmatch(url),
                  f"the PR URL is not canonical: {url!r}")
    reuse.require(detail.get("isDraft") is True,
                  "the existing PR is not a draft; refusing to touch independent review work")
    reuse.require(detail.get("isCrossRepository") is False,
                  "the existing PR comes from a different repository; refusing to touch it")
    head_oid = detail.get("headRefOid")
    reuse.require(isinstance(head_oid, str) and reuse.HEX40_RE.fullmatch(head_oid),
                  f"the PR head commit is not a 40-hex sha: {head_oid!r}")
    files = detail.get("files")
    reuse.require(isinstance(files, list), "the PR detail carries no file list")
    paths = []
    for entry in files:
        reuse.require(isinstance(entry, dict) and isinstance(entry.get("path"), str),
                      "a PR file entry is malformed")
        paths.append(entry["path"])
    if require_files:
        reuse.require(paths == [reuse.LOCK_REL],
                      f"the existing PR changes more than {reuse.LOCK_REL}: {paths}")
    owner = repository.split("/", 1)[0]
    name = repository.split("/", 1)[1]
    head_owner = detail.get("headRepositoryOwner")
    head_repo = detail.get("headRepository")
    reuse.require(isinstance(head_owner, dict) and head_owner.get("login") == owner
                  and isinstance(head_repo, dict) and head_repo.get("name") == name,
                  "the existing PR head is not the official repository branch")
    return detail


def list_open_prs(gh_bin: str, repository: str, branch: str) -> list:
    result = gh_json(gh_bin, ["pr", "list", "--repo", repository, "--head", branch,
                              "--state", "open", "--json", "number"])
    reuse.require(isinstance(result, list), "gh pr list did not return a list")
    reuse.require(len(result) <= 1,
                  f"multiple open PRs use {branch!r}; refusing to choose one")
    return result


def remote_branch_exists(repo_root: Path, branch: str) -> bool:
    proc = reuse.git(repo_root, "ls-remote", "--exit-code", "--heads", "origin",
                     f"refs/heads/{branch}", check=False)
    if proc.returncode == 0:
        return True
    if proc.returncode == 2:
        return False
    reuse.refuse(f"git ls-remote failed: {proc.stderr.strip()[:500]}")


def fetch_branch(repo_root: Path, branch: str) -> None:
    proc = reuse.git(repo_root, "fetch", "--no-tags", "origin",
                     f"refs/heads/{branch}:refs/remotes/origin/{branch}", check=False)
    reuse.require(proc.returncode == 0,
                  f"fetching origin/{branch} failed: {proc.stderr.strip()[:500]}")


def branch_lock_bytes(repo_root: Path, branch: str) -> bytes:
    return git_bytes(repo_root, "show", f"refs/remotes/origin/{branch}:{reuse.LOCK_REL}")


def branch_lock_document(repo_root: Path, branch: str) -> dict:
    raw = branch_lock_bytes(repo_root, branch)
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        reuse.refuse(f"the branch ENGINE-LOCK.json is unusable: {exc}")
    reuse.require(isinstance(document, dict), "the branch ENGINE-LOCK.json is not an object")
    return document


def fetch_live_base(repo_root: Path, base: str) -> str:
    """Fetch the live official default branch before any external PR write."""
    proc = reuse.git(repo_root, "fetch", "--no-tags", "origin",
                     f"refs/heads/{base}:refs/remotes/origin/{base}", check=False)
    reuse.require(proc.returncode == 0,
                  f"fetching the live origin/{base} failed: {proc.stderr.strip()[:500]}")
    sha = reuse.git_out(repo_root, "rev-parse", f"refs/remotes/origin/{base}")
    reuse.require(reuse.HEX40_RE.fullmatch(sha) is not None,
                  f"the live origin/{base} is not a 40-hex commit: {sha!r}")
    return sha


def lock_at_ref(repo_root: Path, rev: str, lock_rel: str) -> dict:
    raw = git_bytes(repo_root, "show", f"{rev}:{lock_rel}")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        reuse.refuse(f"the ENGINE-LOCK.json at {rev} is unusable: {exc}")
    reuse.require(isinstance(document, dict), f"the ENGINE-LOCK.json at {rev} is not an object")
    return document


def assert_ref_matches_metadata(repo_root: Path, metadata: dict, rev: str) -> None:
    """The live default branch must still carry the proof's protected inputs."""
    source = metadata["sourceRun"]["headSha"]
    local_head = reuse.git_out(repo_root, "rev-parse", "HEAD")
    for name, commit in (("source", source), ("dispatch", local_head)):
        reuse.require(reuse.git(repo_root, "cat-file", "-e", f"{commit}^{{commit}}",
                                check=False).returncode == 0,
                      f"the {name} commit {commit} is not present in the checkout")
        reuse.require(reuse.git(repo_root, "merge-base", "--is-ancestor",
                                commit, rev, check=False).returncode == 0,
                      f"the live default branch does not contain the {name} commit {commit}")
    drift = reuse.git(repo_root, "diff", "--quiet", source, rev, "--",
                      *reuse.PROTECTED_PATHS, check=False)
    reuse.require(drift.returncode == 0,
                  "the live default branch drifted from the proof's protected engine inputs")
    digest = metadata["protectedInputs"]["digest"]
    reuse.require(reuse.protected_inputs_digest(repo_root, source) == digest,
                  "the source-run protected-input digest does not match the proof")
    reuse.require(reuse.protected_inputs_digest(repo_root, rev) == digest,
                  "the live default branch protected-input digest does not match the proof")
    source_prefix = reuse.recipe_prefix_bytes(repo_root, source)
    live_prefix = reuse.recipe_prefix_bytes(repo_root, rev)
    reuse.require(reuse.sha256_bytes(source_prefix) == metadata["recipe"]["prefixSha256"],
                  "the source-run recipe prefix digest does not match the proof")
    reuse.require(reuse.sha256_bytes(live_prefix) == metadata["recipe"]["prefixSha256"],
                  "the live default branch updater recipe changed above open-update-pr")
    reuse.require(reuse.git_out(repo_root, "rev-parse",
                                f"{source}:{reuse.UPDATER_WORKFLOW_PATH}")
                  == metadata["recipe"]["headWorkflowBlob"],
                  "the source-run updater workflow blob does not match the proof")


def live_base_guard(repo_root: Path, base: str, engine_dir: Path, *,
                    metadata: dict | None, local_base_lock: dict | None,
                    proposal: dict, candidate: dict) -> tuple[str, dict]:
    """Re-resolve the live default branch and re-check the proposal base.

    A job can wait. The immutable dispatch checkout is not enough: the official
    default branch may have moved to a newer published baseline while the job
    waited. If the live ENGINE-LOCK no longer equals the proposal's base, or a
    protected engine input / the updater recipe above open-update-pr changed,
    this HOLDs before any commit, push or PR. Unrelated main advances are
    allowed because they do not change those inputs or the baseline.
    """
    live_sha = fetch_live_base(repo_root, base)
    local_head = reuse.git_out(repo_root, "rev-parse", "HEAD")
    if metadata is not None:
        assert_ref_matches_metadata(repo_root, metadata, live_sha)
    else:
        reuse.require(local_base_lock is not None,
                      "the automatic path has no local base lock")
        reuse.require(reuse.git(repo_root, "merge-base", "--is-ancestor",
                                local_head, live_sha, check=False).returncode == 0,
                      "the live default branch does not contain the dispatch commit")
        drift = reuse.git(repo_root, "diff", "--quiet", local_head, live_sha, "--",
                          *reuse.PROTECTED_PATHS, check=False)
        reuse.require(drift.returncode == 0,
                      "the live default branch drifts from the dispatch's protected engine inputs")
        reuse.require(reuse.protected_inputs_digest(repo_root, local_head)
                      == reuse.protected_inputs_digest(repo_root, live_sha),
                      "the live default branch protected-input digest changed")
        reuse.require(reuse.sha256_bytes(reuse.recipe_prefix_bytes(repo_root, local_head))
                      == reuse.sha256_bytes(reuse.recipe_prefix_bytes(repo_root, live_sha)),
                      "the live default branch updater recipe changed above open-update-pr")
        reuse.require(reuse.same_candidate_lock(
                          lock_at_ref(repo_root, live_sha, reuse.LOCK_REL),
                          local_base_lock),
                      "the live default branch baseline is not the dispatch's base lock")
    live_lock = lock_at_ref(repo_root, live_sha, reuse.LOCK_REL)
    # The exact proposal must be the one this live base produces. This is the
    # stale-baseline gate: a newer published baseline changes the expected
    # superseded/pin/component fields and refuses here.
    reuse.check_proposal_against_base(live_lock, proposal, candidate)
    if metadata is not None:
        reuse.check_baseline_matches_metadata(engine_dir, live_lock, metadata["baseline"])
    return live_sha, live_lock


def create_pr(gh_bin: str, repository: str, base: str, branch: str, title: str,
              body_file: Path) -> dict:
    output = gh_run(gh_bin, ["pr", "create", "--repo", repository, "--draft",
                             "--base", base, "--head", branch, "--title", title,
                             "--body-file", str(body_file)])
    url = None
    for line in reversed(output.splitlines()):
        candidate = line.strip()
        if PR_URL_RE.fullmatch(candidate):
            url = candidate
            break
    reuse.require(url is not None, f"gh pr create printed no canonical PR URL: {output[-500:]!r}")
    detail = None
    paths = []
    # GitHub can take a moment to populate a new PR's file list. Retry only an
    # empty read-back (never a non-empty wrong one), then fail closed.
    for attempt in range(3):
        detail = pr_detail(gh_bin, repository, url, require_files=False)
        paths = [entry["path"] for entry in detail["files"]]
        if paths:
            break
        if attempt < 2:
            time.sleep(2)
    reuse.require(detail is not None and detail.get("url") == url,
                  "the created PR read-back URL disagrees")
    reuse.require(detail.get("headRefName") == branch,
                  "the created PR head branch disagrees")
    reuse.require(paths == [reuse.LOCK_REL],
                  f"the created PR changes more than {reuse.LOCK_REL}: {paths}")
    return detail


def publish(args) -> dict:
    repository = args.repository
    reuse.require(repository == reuse.OFFICIAL_REPOSITORY,
                  f"refusing repository {repository!r}")
    reuse.require(isinstance(args.base, str) and reuse.BRANCH_RE.fullmatch(args.base)
                  and ".." not in args.base,
                  f"the base branch is not a safe name: {args.base!r}")
    engine_dir = Path(args.engine_dir).resolve()
    repo_root = Path(reuse.git_out(engine_dir, "rev-parse", "--show-toplevel"))
    reuse.require(engine_dir == repo_root / "engines" / "impeccable",
                  f"the engine directory is not {repo_root / 'engines' / 'impeccable'}")
    lock_path = engine_dir / "ENGINE-LOCK.json"
    lock_rel = lock_path.relative_to(repo_root).as_posix()
    reuse.require(lock_rel == reuse.LOCK_REL, "the lock path is not the fixed tracked path")

    reuse.require(reuse.git(repo_root, "rev-parse", "--show-toplevel",
                            check=False).stdout.strip() == str(repo_root),
                  "the engine directory is not inside the current git checkout")

    metadata = None
    local_base_lock = None
    if args.metadata:
        check_status(repo_root, lock_rel, allow_lock=False)
        metadata = reuse.load_json(args.metadata, "the verified review payload")
        validated = reuse.validate_metadata_payload(metadata, repo_root, repository)
        candidate = validated["candidate"]
        proposal = validated["proposal"]
        proposal_bytes = reuse.canonical_lock_bytes(proposal)
        reuse.require(reuse.sha256_bytes(proposal_bytes) == validated["proposalSha256"],
                      "the verified lock proposal bytes do not match their digest")
        body_path = Path(args.body_file)
        body_path.parent.mkdir(parents=True, exist_ok=True)
        run_id = metadata["sourceRun"]["id"]
        artifact_id = metadata["artifact"]["id"]
        commit_extra = (f"\n\nVerified candidate from updater run {run_id}, "
                        f"artifact {artifact_id}.")
    else:
        reuse.require(isinstance(args.candidate_commit, str)
                      and reuse.HEX40_RE.fullmatch(args.candidate_commit),
                      "the candidate commit is not a 40-hex sha")
        reuse.require(isinstance(args.candidate_version, str)
                      and reuse.SEMVER_RE.fullmatch(args.candidate_version),
                      "the candidate version is not dotted-semver")
        check_status(repo_root, lock_rel, allow_lock=True)
        proposal = reuse.load_json(lock_path, "the updated ENGINE-LOCK.json")
        reuse.require(isinstance(proposal, dict), "the updated lock is not an object")
        candidate = reuse.candidate_from_proposal(proposal)
        reuse.require(candidate["commit"] == args.candidate_commit,
                      "the updated lock commit is not the candidate commit")
        reuse.require(candidate["engineVersion"] == args.candidate_version,
                      "the updated lock engine version is not the candidate version")
        local_base_lock = read_base_lock(repo_root, lock_rel)
        reuse.check_proposal_against_base(local_base_lock, proposal, candidate)
        proposal_bytes = lock_path.read_bytes()
        reuse.require(reuse.canonical_lock_bytes(proposal) == proposal_bytes,
                      "the updated lock is not in the canonical update_lock.py serialization")
        body_path = Path(args.body_file)
        reuse.require(body_path.is_file(), "the automatic PR body file is missing")
        reuse.require(body_path.stat().st_size <= MAX_BODY_BYTES,
                      "the automatic PR body exceeds the cap")
        reuse.require(body_path.read_text(encoding="utf-8").strip(),
                      "the automatic PR body is empty")
        run_id = None
        artifact_id = None
        commit_extra = ""

    # Re-resolve the LIVE official default branch. A newer published baseline
    # (or any protected engine/recipe drift) must HOLD here, before the write.
    live_sha, _live_lock = live_base_guard(
        repo_root, args.base, engine_dir, metadata=metadata,
        local_base_lock=local_base_lock, proposal=proposal, candidate=candidate)

    if metadata is not None:
        body = render_review_body(metadata)
        reuse.require(len(body.encode("utf-8")) <= MAX_BODY_BYTES,
                      "the generated PR body exceeds the cap")
        body_path.write_text(body, encoding="utf-8")
    branch = f"chore/impeccable-engine-{candidate['engineVersion']}"
    title = f"Impeccable engine {candidate['engineVersion']} (review required)"

    open_prs = list_open_prs(args.gh, repository, branch)
    if open_prs:
        # Fetch first so the PR head oid can be compared with the real remote
        # branch, not just with whatever the API last reported.
        fetch_branch(repo_root, branch)
        detail = pr_detail(args.gh, repository, open_prs[0]["number"])
        reuse.require(detail.get("headRefName") == branch,
                      "the open PR head branch disagrees with the requested branch")
        local_head = reuse.git_out(repo_root, "rev-parse", f"refs/remotes/origin/{branch}")
        reuse.require(local_head == detail.get("headRefOid"),
                      "the fetched branch head disagrees with the PR head")
        reuse.require(reuse.same_candidate_lock(branch_lock_document(repo_root, branch),
                                                proposal),
                      "the existing PR branch carries a different lock; refusing to overwrite it")
        if metadata is None:
            reuse.git(repo_root, "restore", "--source=HEAD", "--staged", "--worktree",
                      "--", lock_rel)
        return {
            "ok": True,
            "action": "existing",
            "reason": "an open draft PR already proposes the same verified candidate",
            "branch": branch,
            "candidate": candidate,
            "prUrl": detail["url"],
            "commit": detail["headRefOid"],
        }

    if remote_branch_exists(repo_root, branch):
        fetch_branch(repo_root, branch)
        reuse.require(reuse.same_candidate_lock(branch_lock_document(repo_root, branch),
                                                proposal),
                      "the existing branch carries a different lock; refusing to overwrite it")
        reuse.require(reuse.git(repo_root, "merge-base", "--is-ancestor", live_sha,
                                f"refs/remotes/origin/{branch}",
                                check=False).returncode == 0,
                      "the existing branch is behind the live default branch; refusing to open a stale PR")
        diff_names = reuse.git(repo_root, "diff", "--name-only",
                               f"{live_sha}...refs/remotes/origin/{branch}").stdout.splitlines()
        reuse.require(diff_names == [lock_rel],
                      f"the existing branch carries independent changes: {diff_names}")
        detail = create_pr(args.gh, repository, args.base, branch, title, body_path)
        if metadata is None:
            reuse.git(repo_root, "restore", "--source=HEAD", "--staged", "--worktree",
                      "--", lock_rel)
        return {
            "ok": True,
            "action": "created",
            "reason": "a matching branch existed without a PR; the draft PR was opened",
            "branch": branch,
            "candidate": candidate,
            "prUrl": detail["url"],
            "commit": reuse.git_out(repo_root, "rev-parse", f"refs/remotes/origin/{branch}"),
        }

    existing_local = reuse.git(repo_root, "rev-parse", "--verify", "--quiet",
                               f"refs/heads/{branch}", check=False)
    reuse.require(existing_local.returncode != 0,
                  f"a local branch {branch!r} already exists; refusing to reuse it")
    if metadata is None:
        # The automatic path wrote the proposal into the worktree before this
        # helper ran. Restore only that lock to the dispatch base, then start a
        # fresh branch from the live default branch so unrelated main advances
        # are not reverted by the PR.
        reuse.git(repo_root, "restore", "--source=HEAD", "--staged", "--worktree",
                  "--", lock_rel)
        check_status(repo_root, lock_rel, allow_lock=False)
    reuse.git(repo_root, "switch", "-c", branch, f"refs/remotes/origin/{args.base}")
    lock_path.write_bytes(proposal_bytes)
    check_status(repo_root, lock_rel, allow_lock=True)
    reuse.require(lock_path.read_bytes() == proposal_bytes,
                  "the worktree lock bytes differ from the verified proposal")
    reuse.git(repo_root, "add", "--", lock_rel)
    staged = reuse.git(repo_root, "diff", "--cached", "--name-only").stdout.splitlines()
    if not staged:
        # Only a genuinely empty cached diff may be a no-op. The worktree lock
        # must already be the exact proposal and nothing else may be pending.
        reuse.require(lock_path.read_bytes() == proposal_bytes,
                      "the empty cached diff does not carry the verified proposal")
        status = reuse.git(repo_root, "status", "--porcelain",
                           "--untracked-files=all").stdout
        reuse.require(not status.strip(),
                      f"the empty cached diff hides other worktree changes: {status.strip()[:500]}")
        reuse.git(repo_root, "reset", "-q", "--", lock_rel)
        return {
            "ok": True,
            "action": "no-op",
            "reason": "the live default branch already carries the verified candidate",
            "branch": branch,
            "candidate": candidate,
            "prUrl": None,
            "commit": reuse.git_out(repo_root, "rev-parse", "HEAD"),
        }
    reuse.require(staged == [lock_rel],
                  f"the staged change is not exactly {lock_rel}: {staged}")
    changed = reuse.git(repo_root, "diff", "--cached", "--name-status").stdout.strip()
    reuse.require(changed.split("\t")[0] in {"M", "A"},
                  f"the staged change is not a modification/addition: {changed!r}")
    commit_message = (f"chore(impeccable): propose engine {candidate['engineVersion']}"
                      f"{commit_extra}")
    reuse.git(repo_root, "-c", f"user.name={COMMIT_NAME}",
              "-c", f"user.email={COMMIT_EMAIL}", "commit", "-m", commit_message)
    commit_sha = reuse.git_out(repo_root, "rev-parse", "HEAD")
    reuse.require(reuse.HEX40_RE.fullmatch(commit_sha) is not None,
                  "the new commit sha is not 40-hex")
    committed = reuse.git(repo_root, "show", "--name-only", "--format=",
                          "HEAD").stdout.splitlines()
    reuse.require(committed == [lock_rel],
                  f"the commit carries more than {lock_rel}: {committed}")
    reuse.require(reuse.git(repo_root, "diff", "--name-only",
                            f"{live_sha}...HEAD").stdout.splitlines() == [lock_rel],
                  f"the commit is not based on the live default branch with only {lock_rel}")
    author = reuse.git_out(repo_root, "log", "-1", "--format=%an <%ae>")
    reuse.require(author == f"{COMMIT_NAME} <{COMMIT_EMAIL}>",
                  f"the commit identity is unexpected: {author!r}")
    reuse.require(not reuse.git(repo_root, "status", "--porcelain",
                                "--untracked-files=all").stdout.strip(),
                  "the worktree is not clean after the lock commit")

    push = reuse.git(repo_root, "push", "--set-upstream", "origin",
                     f"refs/heads/{branch}:refs/heads/{branch}", check=False)
    reuse.require(push.returncode == 0,
                  f"git push failed: {push.stderr.strip()[:500]}")
    detail = create_pr(args.gh, repository, args.base, branch, title, body_path)
    reuse.require(detail.get("headRefOid") == commit_sha,
                  "the created PR head is not the commit this helper pushed")
    return {
        "ok": True,
        "action": "created",
        "reason": "the verified lock was committed and the draft PR was opened",
        "branch": branch,
        "candidate": candidate,
        "prUrl": detail["url"],
        "commit": commit_sha,
    }

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Commit a verified ENGINE-LOCK proposal and open its draft PR.")
    parser.add_argument("--engine-dir", required=True, type=Path)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--body-file", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--gh", default="gh")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--metadata", type=Path,
                      help="tiny verified payload from verify_candidate_reuse.py")
    mode.add_argument("--lock-auto", action="store_true",
                      help="the updater already wrote the lock with update_lock.py")
    parser.add_argument("--candidate-commit")
    parser.add_argument("--candidate-version")
    args = parser.parse_args()
    if args.lock_auto:
        if not args.candidate_commit or not args.candidate_version:
            parser.error("--lock-auto requires --candidate-commit and --candidate-version")
    else:
        if args.candidate_commit or args.candidate_version:
            parser.error("candidate arguments are only valid with --lock-auto")
    try:
        result = publish(args)
    except reuse.Refusal as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2
    reuse.write_json(args.out, result)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
