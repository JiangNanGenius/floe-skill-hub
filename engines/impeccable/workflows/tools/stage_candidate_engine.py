#!/usr/bin/env python3
"""Stage a caller-owned candidate engine tree for the updater workflow.

`build/build_engine.py` resolves its inputs module-relative to its own
location: `ENGINE-LOCK.json`, `adapter/`, `patches/` and `contract/`. The
tracked lock names the reviewed pin, so invoking the tracked builder on a
changed candidate fails `verify_pin` (source HEAD vs the OLD lock) before any
preflight runs. This tool stages a temporary engine tree — a strict byte copy
of the reviewed build inputs plus the candidate lock, with ONLY the candidate
identity fields of the staged contract rewritten — so the staged builder
verifies the candidate against the candidate pin.

The staged tree is laid out as a minimal hub view so every module-relative
path in the staged builder resolves inside the temp root:

  <out>/LICENSE                              copy of the tracked hub LICENSE
  <out>/engines/impeccable/ENGINE-LOCK.json  the staged candidate lock (verbatim)
  <out>/engines/impeccable/build/            byte copy of the tracked builder
  <out>/engines/impeccable/adapter/          byte copy
  <out>/engines/impeccable/patches/          byte copy
  <out>/engines/impeccable/contract/         byte copy, with the candidate
      identity fields in snapshot-contract.v1.json
      (engine.upstreamCommit/upstreamTree/upstreamEngineVersion/engineId and
      provenance.upstreamCommit/upstreamTree/engineVersionFile) rewritten to
      the candidate pin; every other field, and every other file, is
      byte-identical to the tracked contract.

Nothing under the tracked engine dir, the tracked lock, the frozen contract,
the frozen binary or `sources/impeccable` is modified. The tool refuses a
non-empty or symlinked output root and validates every candidate identity
shape before writing. It never deletes caller data.

  stage_candidate_engine.py --engine-dir engines/impeccable \
      --candidate-lock <staged ENGINE-LOCK.json> --out <fresh temp hub root>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

HEX40 = __import__("re").compile(r"[0-9a-f]{40}")
SEMVER = __import__("re").compile(r"[0-9]+\.[0-9]+\.[0-9]+")

ENGINE_IDENTITY_FIELDS = (
    ("engine", "upstreamCommit"),
    ("engine", "upstreamTree"),
    ("engine", "upstreamEngineVersion"),
    ("engine", "engineId"),
    ("provenance", "upstreamCommit"),
    ("provenance", "upstreamTree"),
    ("provenance", "engineVersionFile"),
)


def fail(message: str, **detail) -> int:
    print(json.dumps({"ok": False, "error": message, **detail}, indent=2))
    return 2


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_tree(src: Path, dst: Path) -> dict:
    """Byte copy src -> dst; returns {relative: sha256} for every file.

    Symbolic links are refused, never followed: the staged tree must be
    plain files so the staged builder cannot be redirected at tracked
    content."""
    digests = {}
    for path in sorted(src.rglob("*")):
        if path.is_symlink():
            raise SystemExit(json.dumps({"ok": False,
                                         "error": f"refusing to stage a symbolic link: {path}"}))
        if not path.is_file():
            continue
        rel = path.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink():
            raise SystemExit(json.dumps({"ok": False,
                                         "error": f"refusing to overwrite a symbolic link: {target}"}))
        shutil.copyfile(path, target)
        digests[str(rel)] = sha256_file(target)
        if digests[str(rel)] != sha256_file(path):
            raise SystemExit(json.dumps({"ok": False,
                                         "error": f"copy drifted while staging: {rel}"}))
    return digests


def validate_identity(lock: dict) -> dict:
    upstream = lock.get("upstream")
    if not isinstance(upstream, dict):
        raise ValueError("candidate lock has no upstream object")
    commit = upstream.get("commit")
    tree = upstream.get("tree")
    version = upstream.get("engineVersion")
    engine_id = lock.get("engineId")
    if not isinstance(commit, str) or not HEX40.fullmatch(commit):
        raise ValueError(f"candidate lock upstream.commit is not a 40-hex sha: {commit!r}")
    if not isinstance(tree, str) or not HEX40.fullmatch(tree):
        raise ValueError(f"candidate lock upstream.tree is not a 40-hex sha: {tree!r}")
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        raise ValueError(f"candidate lock upstream.engineVersion is not dotted-semver: {version!r}")
    if not isinstance(engine_id, str) or not engine_id.startswith("impeccable-"):
        raise ValueError(f"candidate lock engineId is missing or malformed: {engine_id!r}")
    return {"commit": commit, "tree": tree, "version": version, "engineId": engine_id}


def rewrite_contract_identity(contract_dir: Path, identity: dict) -> dict:
    """Copy the contract, rewrite only the candidate identity fields, and
    return {field, before, after} for each change."""
    target = contract_dir / "snapshot-contract.v1.json"
    doc = json.loads(target.read_text(encoding="utf-8"))
    changes = []
    for section, key in ENGINE_IDENTITY_FIELDS:
        node = doc.get(section)
        if not isinstance(node, dict) or key not in node:
            raise ValueError(f"tracked contract is missing {section}.{key}")
        before = node[key]
        after = {
            ("engine", "upstreamCommit"): identity["commit"],
            ("engine", "upstreamTree"): identity["tree"],
            ("engine", "upstreamEngineVersion"): identity["version"],
            ("engine", "engineId"): identity["engineId"],
            ("provenance", "upstreamCommit"): identity["commit"],
            ("provenance", "upstreamTree"): identity["tree"],
            ("provenance", "engineVersionFile"): identity["version"],
        }[(section, key)]
        node[key] = after
        changes.append({"field": f"{section}.{key}", "before": before, "after": after})
    target.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return changes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine-dir", required=True, type=Path,
                    help="tracked engines/impeccable (read-only)")
    ap.add_argument("--candidate-lock", required=True, type=Path,
                    help="the staged candidate ENGINE-LOCK.json (already updated)")
    ap.add_argument("--out", required=True, type=Path,
                    help="fresh temp root of the staged hub view")
    args = ap.parse_args()

    # The original path is checked for symlinks BEFORE resolve(): resolve()
    # follows links, which would hide a symlinked output root. Intermediate
    # symlinked ancestors (e.g. the macOS /var -> /private/var temp prefix)
    # are allowed; the inside-tree guards below run on resolved paths.
    raw_out = Path(args.out).expanduser()
    if raw_out.is_symlink():
        return fail("the staged output root must not be a symbolic link", out=str(raw_out))
    out = raw_out.resolve()
    engine_dir = Path(args.engine_dir).expanduser().resolve()
    candidate_lock = Path(args.candidate_lock).expanduser().resolve()
    hub_root = engine_dir.parent.parent

    def inside(child: Path, parent: Path) -> bool:
        return child == parent or parent in child.parents

    if inside(out, engine_dir):
        return fail("the staged output root must not resolve inside the tracked engine dir",
                    out=str(out), engineDir=str(engine_dir))
    if inside(out, hub_root):
        return fail("the staged output root must not resolve inside the tracked hub tree",
                    out=str(out), hubRoot=str(hub_root))
    if out == candidate_lock:
        return fail("the staged output root must not be the candidate lock file itself",
                    out=str(out))

    if out.exists() and any(out.iterdir()):
        return fail("the staged output root already exists and is not empty; "
                    "this tool never deletes existing output", out=str(out))
    for required in ("build", "adapter", "patches", "contract"):
        if not (engine_dir / required).is_dir():
            return fail(f"tracked engine input missing: {engine_dir / required}")
    if not (hub_root / "LICENSE").is_file():
        return fail(f"tracked hub LICENSE missing: {hub_root / 'LICENSE'}")
    if not candidate_lock.is_file():
        return fail(f"candidate lock missing: {candidate_lock}")

    try:
        lock = json.loads(candidate_lock.read_text(encoding="utf-8"))
        identity = validate_identity(lock)
    except (json.JSONDecodeError, ValueError) as error:
        return fail(f"candidate lock is unusable: {error}")

    staged_engine = out / "engines" / "impeccable"
    staged_engine.mkdir(parents=True, exist_ok=True)

    copies = {}
    for name in ("build", "adapter", "patches", "contract"):
        copies[name] = copy_tree(engine_dir / name, staged_engine / name)
    shutil.copyfile(candidate_lock, staged_engine / "ENGINE-LOCK.json")
    shutil.copyfile(hub_root / "LICENSE", out / "LICENSE")

    changes = rewrite_contract_identity(staged_engine / "contract", identity)

    print(json.dumps({
        "ok": True,
        "stagedRoot": str(out),
        "stagedBuilder": str(staged_engine / "build" / "build_engine.py"),
        "engineDir": str(engine_dir),
        "candidate": identity,
        "contractChanges": changes,
        "trackedContractSha256": sha256_file(engine_dir / "contract" / "snapshot-contract.v1.json"),
        "stagedContractSha256": sha256_file(staged_engine / "contract" / "snapshot-contract.v1.json"),
        "copiedFiles": {name: len(files) for name, files in copies.items()},
        "note": "tracked lock, tracked contract, frozen binary and sources/impeccable are untouched; "
                "only the staged temp tree carries the candidate identity",
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
