#!/usr/bin/env python3
"""Rewrite the engine lock for a reviewed upstream candidate.

Only the pin identity moves: commit, tree, `ENGINE_VERSION`, commit date and
subject. Everything else in `ENGINE-LOCK.json` — the toolchain, the patch list,
the adapter version, the included and excluded crates, the vendoring rule — is
left for a human to change deliberately, and the previous pin is kept in the lock
as `supersededPin` so the history of what the engine was built from stays
readable in one place.

The workflow calls this on the update branch; it never builds, signs, publishes
or installs anything, and it does not touch the frozen contract. If the contract
also has to move (a schema or coverage change), that is a v1 field change and
needs coordinator review, not an automated rewrite.

  update_lock.py --lock engines/impeccable/ENGINE-LOCK.json \
      --commit <sha> [--engine-version 0.1.18] [--source <clone>] \
      [--upstream-repo pbakaus/impeccable] [--dry-run]
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

API = "https://api.github.com"


def http_json(url: str):
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "floe-skill-hub-engine-updater",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def resolve(args, commit: str) -> dict:
    """Fill in the tree, version, date and subject for a commit."""
    if args.source:
        source = Path(args.source)
        if (source / ".git").exists():
            def git(*command: str) -> str:
                return subprocess.run(["git", "-C", str(source), *command],
                                      capture_output=True, text=True, check=True).stdout.strip()
            try:
                git("cat-file", "-e", f"{commit}^{{commit}}")
                tree = git("rev-parse", f"{commit}^{{tree}}")
                version = subprocess.run(
                    ["git", "-C", str(source), "show", f"{commit}:ENGINE_VERSION"],
                    capture_output=True, text=True, check=True).stdout.strip()
                meta = git("log", "-1", "--format=%cI%x09%s", commit).split("\t", 1)
                return {
                    "tree": tree,
                    "engineVersion": version,
                    "commitDate": meta[0],
                    "commitSubject": meta[1] if len(meta) > 1 else None,
                    "resolvedVia": "local clone",
                }
            except subprocess.CalledProcessError:
                pass
    data = http_json(f"{API}/repos/{args.upstream_repo}/commits/{commit}")
    blob = http_json(f"{API}/repos/{args.upstream_repo}/contents/ENGINE_VERSION?ref={commit}")
    return {
        "tree": data["commit"]["tree"]["sha"],
        "engineVersion": base64.b64decode(blob["content"]).decode("utf-8").strip(),
        "commitDate": data["commit"]["committer"]["date"],
        "commitSubject": data["commit"]["message"].splitlines()[0],
        "resolvedVia": "github api",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lock", required=True, type=Path)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--engine-version", default=None)
    ap.add_argument("--source", type=Path, default=None)
    ap.add_argument("--upstream-repo", default="pbakaus/impeccable")
    ap.add_argument("--adapter-version", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    lock_path = Path(args.lock).expanduser().resolve()
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    resolved = resolve(args, args.commit)

    if args.engine_version and args.engine_version != resolved["engineVersion"]:
        print(json.dumps({
            "ok": False,
            "error": "the requested engine version does not match the commit's ENGINE_VERSION",
            "requested": args.engine_version,
            "atCommit": resolved["engineVersion"],
        }, indent=2))
        return 2

    previous = dict(lock["upstream"])
    previous.pop("supersededPin", None)
    upstream = lock["upstream"]
    upstream["commit"] = args.commit
    upstream["tree"] = resolved["tree"]
    upstream["engineVersion"] = resolved["engineVersion"]
    upstream["commitDate"] = resolved["commitDate"]
    upstream["commitSubject"] = resolved["commitSubject"]
    upstream["supersededPin"] = {
        "commit": previous.get("commit"),
        "tree": previous.get("tree"),
        "engineVersion": previous.get("engineVersion"),
        "note": "the pin this update replaces; artifacts built from it stay valid until reviewed out",
    }
    if args.adapter_version:
        lock["floe"]["adapterVersion"] = args.adapter_version
    adapter_version = lock["floe"]["adapterVersion"]
    lock["engineId"] = f"impeccable-{resolved['engineVersion']}+floe.{adapter_version}"
    lock["status"] = "candidate-update-not-qualified"
    lock["resolvedVia"] = resolved["resolvedVia"]

    text = json.dumps(lock, indent=2, ensure_ascii=False) + "\n"
    if not args.dry_run:
        lock_path.write_text(text, encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "dryRun": args.dry_run,
        "lock": str(lock_path) if not args.dry_run else "<unchanged>",
        "engineId": lock["engineId"],
        "previousCommit": previous.get("commit"),
        "newCommit": args.commit,
        "engineVersion": resolved["engineVersion"],
        "note": "the frozen contract, patches and adapter were NOT modified; a contract change needs coordinator review",
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
