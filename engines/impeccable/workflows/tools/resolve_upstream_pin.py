#!/usr/bin/env python3
"""Resolve the upstream engine release candidate and compare it with the pin.

Used by the updater workflow's first job. It follows upstream **release tags**
(`engine-v*`), never upstream `main`, and it never writes to the repository: the
only output is a JSON document on stdout or at `--out`.

Resolution order:
  1. `--requested-ref` (a commit or a tag) when the run was dispatched manually;
  2. otherwise the newest stable (non-draft, non-prerelease) `engine-v*`
     release tag on the upstream repository.

Automatic update policy (the scheduled path): a candidate is only reported as
`changed` when it is a **strictly newer** semantic engine version than the
pinned one. A same-version release tag that was retargeted at a different
commit, or an older version, yields `changed: false` with an explicit reason:
the pin is retained, nothing is rebuilt, and no same-version/downgrade PR is
proposed. An explicit manual `--requested-ref` may still stage a
different-commit/same-version candidate, marked `manual-review`, for a human
to review — never an automatic install. Identical pins are a no-op.

Every value this tool hands to the workflow is shape-checked here, before any
`git` argv, before any API URL and before the JSON is written: a requested ref
must be a full 40-hex commit or an exact `engine-v<digits>.<digits>.<digits>`
release tag (never a dash-leading option string, never anything carrying
newlines or shell metacharacters), and `ENGINE_VERSION` read from the upstream
tree must be an exact dotted-semver string. A release tag must also agree with
the `ENGINE_VERSION` in its own tree — a tag/version mismatch is a hard exit 2,
not a warning. The workflow interpolates these outputs into shell steps, so a
hostile upstream release could otherwise forge `$GITHUB_OUTPUT` lines or
inject commands; validation here is the choke point.

The candidate's `ENGINE_VERSION` is read from the upstream tree at that commit,
so a tag that does not match its own version file is reported instead of trusted.
`--source` (a local clone) is preferred when present; otherwise the public GitHub
API is used, optionally through `gh` when it is authenticated.

  resolve_upstream_pin.py --lock engines/impeccable/ENGINE-LOCK.json \
      --upstream-repo pbakaus/impeccable [--requested-ref engine-v0.1.18] \
      [--source <clone>] [--releases-json <releases.json>] [--out <pin.json>]

`--releases-json` is a hermetic regression hook: a JSON array of release
objects (`tag_name`, `draft`, `prerelease`) used instead of the GitHub API
when the automatic path must be tested without network. Production runs
leave it unset.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

API = "https://api.github.com"

HEX40_RE = re.compile(r"[0-9a-f]{40}")
ENGINE_VERSION_RE = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
ENGINE_TAG_RE = re.compile(r"engine-v[0-9]+\.[0-9]+\.[0-9]+")


class ShapeError(ValueError):
    """A value failed the anchored shape check; the run must stop here."""


def validate_engine_version(value, label: str) -> str:
    if not isinstance(value, str) or not ENGINE_VERSION_RE.fullmatch(value):
        raise ShapeError(f"{label} is not an exact dotted-semver string: {value!r}")
    return value


def validate_hex_sha(value, label: str) -> str:
    if not isinstance(value, str) or not HEX40_RE.fullmatch(value):
        raise ShapeError(f"{label} is not a full lowercase 40-hex sha: {value!r}")
    return value


def validate_requested_ref(value: str) -> str:
    """A dispatch ref is a commit sha or an engine-v* release tag, and never
    something git would read as an option or the API would read as a path."""
    ref = value.strip()
    if not ref:
        return ""
    if ref.startswith("-"):
        raise ShapeError(f"requested ref starts with a dash: {ref!r}")
    if HEX40_RE.fullmatch(ref):
        return ref
    if not ENGINE_TAG_RE.fullmatch(ref):
        raise ShapeError(
            "requested ref must be a full 40-hex commit sha or an exact "
            f"engine-v<semver> release tag, got: {ref!r}")
    return ref


def parse_semver(value: str) -> tuple[int, int, int]:
    """Validated dotted-semver -> comparable tuple. Input must have passed
    validate_engine_version first."""
    major, minor, patch = value.split(".")
    return int(major), int(minor), int(patch)


def select_latest_stable_release(releases: list) -> str | None:
    """Newest stable `engine-v<semver>` release tag, or None.

    Only non-draft, non-prerelease releases whose tag matches the exact
    official shape are considered — upstream-controlled tag text with
    newlines, spaces or option-looking punctuation can never be selected.
    `draft`/`prerelease` are honoured only as literal booleans `true`, the
    exact values the GitHub API emits."""
    tags = []
    for release in releases:
        if not isinstance(release, dict):
            continue
        if release.get("draft") is True or release.get("prerelease") is True:
            continue
        tag = release.get("tag_name")
        if isinstance(tag, str) and ENGINE_TAG_RE.fullmatch(tag):
            tags.append(tag)
    if not tags:
        return None

    def key(tag: str) -> tuple[int, int, int]:
        return parse_semver(tag.removeprefix("engine-v"))

    return sorted(tags, key=key)[-1]


def decide_pin_change(*, current_commit: str, current_version: str,
                      candidate_commit: str, candidate_version: str,
                      requested_ref: str | None) -> dict:
    """Pure forward-only update policy.

    Returns {"changed": bool, "mode": ..., "reason": ...} where mode is
    `automatic` (scheduled run found a strictly newer engine release),
    `manual-review` (a human dispatched this ref; staged for review only)
    or `no-op` (nothing to do; the pin is retained). The reason is always a
    single-line printable-ASCII string safe to cross $GITHUB_OUTPUT.
    """
    manual = bool(requested_ref)
    if candidate_commit == current_commit and candidate_version == current_version:
        return {
            "changed": False,
            "mode": "no-op",
            "reason": "candidate is identical to the current pin; nothing to do",
        }
    if manual:
        how = "commit" if candidate_version == current_version else \
            f"engine {candidate_version} (pinned: {current_version})"
        return {
            "changed": True,
            "mode": "manual-review",
            "reason": f"manual dispatch staged {requested_ref} = {how} at a different commit; review only, never an automatic install",
        }
    if parse_semver(candidate_version) > parse_semver(current_version):
        return {
            "changed": True,
            "mode": "automatic",
            "reason": f"forward release: engine {candidate_version} is strictly newer than the pinned {current_version}",
        }
    if candidate_version == current_version:
        return {
            "changed": False,
            "mode": "no-op",
            "reason": f"engine {candidate_version} release tag points at a different commit; automatic updates follow strictly newer releases only, so the pin is retained",
        }
    return {
        "changed": False,
        "mode": "no-op",
        "reason": f"engine {candidate_version} is older than the pinned {current_version}; downgrades are never proposed automatically, so the pin is retained",
    }


def fail(error: str) -> int:
    print(json.dumps({"ok": False, "error": error}, indent=2))
    return 2


def http_json(url: str, token: str | None = None):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "floe-skill-hub-engine-updater",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def gh_token() -> str | None:
    try:
        result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    token = result.stdout.strip()
    return token or None


def local_clone(args, ref: str) -> dict | None:
    if not args.source:
        return None
    source = Path(args.source)
    if not (source / ".git").exists():
        return None

    def git(*command: str) -> str:
        return subprocess.run(["git", "-C", str(source), *command],
                              capture_output=True, text=True, check=True).stdout.strip()

    try:
        git("fetch", "--quiet", "--filter=blob:none", "origin", ref)
        commit = git("rev-parse", f"{ref}^{{commit}}")
        tree = git("rev-parse", f"{commit}^{{tree}}")
        version = subprocess.run(["git", "-C", str(source), "show", f"{commit}:ENGINE_VERSION"],
                                 capture_output=True, text=True, check=True).stdout.strip()
        meta = git("log", "-1", "--format=%cI%x09%s", commit).split("\t", 1)
    except subprocess.CalledProcessError:
        return None
    return {
        "commit": commit,
        "tree": tree,
        "engineVersion": version,
        "commitDate": meta[0] if meta else None,
        "commitSubject": meta[1] if len(meta) > 1 else None,
        "resolvedVia": f"local clone at {source.name}",
    }


def remote(args, ref: str) -> dict:
    token = gh_token()
    repo = args.upstream_repo
    if HEX40_RE.fullmatch(ref):
        commit = ref
    else:
        commit = http_json(f"{API}/repos/{repo}/commits/{ref}", token)["sha"]
    tree = http_json(f"{API}/repos/{repo}/commits/{commit}", token)["commit"]["tree"]["sha"]
    blob = http_json(f"{API}/repos/{repo}/contents/ENGINE_VERSION?ref={commit}", token)
    import base64
    version = base64.b64decode(blob["content"]).decode("utf-8").strip()
    meta = http_json(f"{API}/repos/{repo}/commits/{commit}", token)["commit"]
    return {
        "commit": commit,
        "tree": tree,
        "engineVersion": version,
        "commitDate": meta["committer"]["date"],
        "commitSubject": meta["message"].splitlines()[0],
        "resolvedVia": "github api",
    }


def load_releases(path: Path | None, repo: str, token: str | None) -> list:
    """Release list for the automatic path: the GitHub API live, or a local
    JSON file in the hermetic `--releases-json` regression hook."""
    if path is None:
        return http_json(f"{API}/repos/{repo}/releases?per_page=50", token)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ShapeError(f"--releases-json is not readable JSON: {error}")
    if not isinstance(data, list):
        raise ShapeError("--releases-json must hold a JSON array of release objects")
    return data


def latest_engine_tag(releases: list) -> str:
    """The newest stable `engine-v*` release tag, by semver rather than by name.

    Only non-draft, non-prerelease releases with the exact official tag shape
    are candidates; a retargeted same-version tag is still returned (the
    forward-only policy in decide_pin_change turns it into a no-op)."""
    tag = select_latest_stable_release(releases)
    if tag is None:
        raise SystemExit(json.dumps(
            {"error": "no stable engine-v* release tag found upstream"}))
    return tag


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lock", required=True, type=Path)
    ap.add_argument("--upstream-repo", default="pbakaus/impeccable")
    ap.add_argument("--requested-ref", default="")
    ap.add_argument("--source", type=Path, default=None)
    ap.add_argument("--releases-json", type=Path, default=None,
                    help="hermetic regression hook: release list JSON used "
                         "instead of the GitHub API for the automatic path")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    upstream = lock["upstream"]
    token = gh_token()

    # Shape-check every value before it can reach git argv, an API URL or the
    # emitted document. The current pin comes from the tracked lock but is
    # still interpolated downstream; the candidate values come from upstream.
    try:
        validate_hex_sha(upstream.get("commit"), "lock upstream.commit")
        validate_hex_sha(upstream.get("tree"), "lock upstream.tree")
        validate_engine_version(upstream.get("engineVersion"), "lock upstream.engineVersion")
        requested = validate_requested_ref(args.requested_ref)
        if requested:
            ref = requested
        else:
            ref = latest_engine_tag(load_releases(args.releases_json, args.upstream_repo, token))
        candidate = local_clone(args, ref) or remote(args, ref)
        validate_hex_sha(candidate["commit"], "candidate commit")
        validate_hex_sha(candidate["tree"], "candidate tree")
        validate_engine_version(candidate["engineVersion"], "upstream ENGINE_VERSION")
        # A release tag must carry the ENGINE_VERSION its name claims; a
        # retargeted or lying tag is refused, not silently followed.
        if ref.startswith("engine-v") and ref.removeprefix("engine-v") != candidate["engineVersion"]:
            raise ShapeError(
                f"release tag {ref} disagrees with its own tree: ENGINE_VERSION at "
                f"{candidate['commit']} is {candidate['engineVersion']}")
    except ShapeError as error:
        return fail(str(error))

    decision = decide_pin_change(
        current_commit=upstream.get("commit"),
        current_version=upstream.get("engineVersion"),
        candidate_commit=candidate["commit"],
        candidate_version=candidate["engineVersion"],
        requested_ref=requested,
    )
    tag = ref if ref.startswith("engine-v") else f"engine-v{candidate['engineVersion']}"
    changed = decision["changed"]
    result = {
        "changed": changed,
        "decision_mode": decision["mode"],
        "decision_reason": decision["reason"],
        "current_commit": upstream.get("commit"),
        "current_tree": upstream.get("tree"),
        "current_engine_version": upstream.get("engineVersion"),
        "candidate_commit": candidate["commit"],
        "candidate_tree": candidate["tree"],
        "candidate_engine_version": candidate["engineVersion"],
        "candidate_tag": tag,
        "candidate_commit_date": candidate.get("commitDate"),
        "candidate_commit_subject": candidate.get("commitSubject"),
        "resolved_via": candidate["resolvedVia"],
        "requested_ref": requested or None,
        "policy": {
            "follows": "upstream stable (non-draft, non-prerelease) engine-v* release tags only",
            "neverFollows": "upstream main, a draft/prerelease, or an untagged commit",
            "automatic": "changed only for a strictly newer semantic engine version than the pin",
            "manual": "a dispatched ref may stage a same-version/different-commit candidate for review only",
            "publishes": False,
            "signs": False,
            "installs": False,
        },
    }
    text = json.dumps(result, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
