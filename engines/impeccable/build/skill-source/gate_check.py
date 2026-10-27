#!/usr/bin/env python3
"""Authoritative Hub consumer gate for the canonical Impeccable package.

Runs the frozen H1 package gates over a candidate package using the
authoritative helper code from the hub root, mirrored BYTE-IDENTICAL into an
isolated root that this tool owns inside the caller's work area. The hub tree
itself is read strictly read-only; nothing is ever written inside it.

Checks (fail closed):
  * candidate tree: regular files only, no symlinks, no unsafe relative paths;
  * top-level allow-list; the unchanged 128-file / 2 MiB / 8 MiB limits,
    require-notice licensing, manifest/frontmatter contract, script-runtime
    script rules and native-payload rejection — all delegated to the copied
    hubcore.validate_package_files / check_archive_bytes (never a weakened
    reimplementation);
  * name==id, version, and plan equality (capabilities, tools, scriptRuntime,
    pythonPackages, versionTarget) against catalog/skills.json as read from
    the hub root, plus registry minimumAppVersion bound to the frozen runtime
    descriptor value (data-driven, not a hardcoded literal);
  * the canonical package shape: 50 files, 36 engine-data references and 23
    commands in command-metadata.json, and a byte-identical embedded
    references/engine-dependency.json matching the frozen hub descriptor;
  * every markdown link in SKILL.md resolves inside the package unless
    explicitly annotated "is not shipped";
  * deterministic ZIP (two key orders byte-identical), archive round-trip
    revalidation, contentDigest, and the authoritative build_packages.py run
    (full build + --check immutability) inside the isolated mirror for every
    planned install channel. When the mirrored helper set imports
    runtime_dependency.py, the frozen descriptor and the dist artifact subtree
    are also mirrored (same-tree binding), still read-only over the hub.

  python3 gate_check.py --package <candidate dir> --hub <floe-skill-hub root> \
                         --work <gate work dir>

The gate writes ONLY under <work>/ziproot. If that directory already exists
and is not empty the gate REFUSES (it never deletes existing output; re-run
into a fresh gate directory, or let run_pipeline.sh manage its owned children).
Deterministic: the same inputs always produce the same result JSON (apart
from the disclosed helper identities).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys

EXPECTED_TOP = {"SKILL.md", "floe.json", "references", "scripts"}
EXPECTED_FILES = 50
EXPECTED_REFS = 36
EXPECTED_COMMANDS = 23
EXPECTED_VERSION = "1.1.1"
DESCRIPTOR_SHA = "e7c7984a573b5ac9a1447bcc4285d9b1ba09458033f8468f5c86961965e57233"
DESCRIPTOR_BYTES = 563


def fail(msg: str) -> None:
    raise SystemExit(f"GATE FAIL: {msg}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(repo: pathlib.Path, *args: str) -> str:
    """Run a git query only when repo is itself a repository root (or contains
    .git); never walk up into an enclosing checkout, which would disclose an
    unrelated outer commit."""
    if not (repo / ".git").exists():
        return ""
    try:
        return subprocess.run(["git", "-C", str(repo), *args],
                              capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True, type=pathlib.Path)
    ap.add_argument("--hub", required=True, type=pathlib.Path)
    ap.add_argument("--work", required=True, type=pathlib.Path,
                    help="gate work dir owned by this tool; ziproot lives under it")
    args = ap.parse_args()
    package = args.package.resolve()
    hub = args.hub.resolve()
    if not package.is_dir():
        fail(f"candidate package directory missing: {package}")
    if (args.work / "ziproot").is_symlink():
        fail(f"isolated gate root must not be a symlink: {args.work / 'ziproot'}")
    isolated = (args.work / "ziproot").resolve()
    if isolated.exists() and any(isolated.iterdir()):
        fail(f"gate output already exists and is not empty: {isolated}; "
             "this gate never deletes existing output — use a fresh --work directory")
    hub_root = hub if str(hub).endswith("/") else str(hub) + "/"
    if str(isolated) == str(hub) or str(isolated).startswith(hub_root):
        fail("gate output would be written inside the hub tree; the hub stays read-only — "
             "use a --work directory outside it")

    # ---- isolated mirror: authoritative helpers copied byte-for-byte ----
    staged_engine_files = []
    scripts_mirror = isolated / "scripts"
    shutil.copytree(hub / "scripts", scripts_mirror)
    helper_sha = {p.name: sha256_bytes(p.read_bytes())
                  for p in sorted(scripts_mirror.glob("*.py"))}
    catalog_mirror = isolated / "catalog"
    shutil.copytree(hub / "catalog", catalog_mirror)

    if (scripts_mirror / "runtime_dependency.py").is_file():
        # H6 same-tree binding helper: mirror the frozen descriptor and, when
        # present, the dist artifact subtree the descriptor points at.
        rd = hub / "engines/impeccable/runtime-dependency"
        if rd.is_dir():
            dst = isolated / "engines/impeccable/runtime-dependency"
            shutil.copytree(rd, dst)
            staged_engine_files.append(str(dst.relative_to(isolated)))
        dist = hub / "engines/impeccable/dist"
        if dist.is_dir():
            dst = isolated / "engines/impeccable/dist"
            shutil.copytree(dist, dst)
            staged_engine_files.append(str(dst.relative_to(isolated)))

    staged = isolated / "sources" / "impeccable"
    staged.mkdir(parents=True)
    for path in sorted(package.rglob("*")):
        rel = path.relative_to(package).as_posix()
        if path.is_symlink():
            fail(f"symlink in candidate package: {rel}")
        if not path.is_file():
            if path.is_dir():
                continue
            fail(f"non-regular entry in candidate package: {rel}")
        if rel.startswith("/") or "\\" in rel or "\0" in rel:
            fail(f"unsafe path in candidate package: {rel!r}")
        parts = rel.split("/")
        if any(p in ("", ".", "..") for p in parts):
            fail(f"unsafe path segment: {rel!r}")
        target = staged / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)

    files = {p.relative_to(staged).as_posix(): p.read_bytes()
             for p in sorted(staged.rglob("*")) if p.is_file()}

    # ---- top-level allow-list ----
    tops = {k.split("/")[0] for k in files}
    if not tops <= EXPECTED_TOP:
        fail(f"unexpected top-level entries: {sorted(tops - EXPECTED_TOP)}")
    if len(files) != EXPECTED_FILES:
        fail(f"canonical package must have {EXPECTED_FILES} files, found {len(files)}")

    # ---- authoritative hubcore battery (unchanged limits, never re-implemented) ----
    sys.path.insert(0, str(scripts_mirror))
    import hubcore  # isolated byte-identical copy of the authoritative helper

    manifest, front = hubcore.validate_package_files(files, require_notice=True)
    if manifest["id"] != "impeccable" or manifest["version"] != EXPECTED_VERSION:
        fail("manifest identity")
    if front["name"] != "impeccable":
        fail("frontmatter name")

    registry = json.loads((isolated / "catalog" / "skills.json").read_bytes())
    hubcore.validate_registry(registry)
    try:
        entry = {e["id"]: e for e in registry["skills"]}["impeccable"]
    except KeyError:
        fail("catalog has no impeccable entry")
    plan = entry["plannedRuntime"]
    if set(manifest["capabilities"]) != set(plan["capabilities"]):
        fail(f"capabilities differ from the current plan: {manifest['capabilities']} vs {plan['capabilities']}")
    if set(manifest["tools"]) != set(plan["tools"]):
        fail("tools differ from the current plan")
    if manifest["scriptRuntime"] != plan["scriptRuntime"]:
        fail("scriptRuntime differs from the plan")
    if [p["spec"] for p in manifest["pythonPackages"]] != plan["pythonPackagesPlan"]:
        fail("pythonPackages differ from the plan")
    if entry["versionTarget"] != manifest["version"]:
        fail("versionTarget mismatch")

    # ---- canonical package shape ----
    refs = [k for k in files if k.startswith("references/engine-data/reference/")
            and k.endswith(".md")]
    if len(refs) != EXPECTED_REFS:
        fail(f"expected {EXPECTED_REFS} engine-data references, found {len(refs)}")
    try:
        metadata = json.loads(files["references/engine-data/scripts/command-metadata.json"])
    except KeyError:
        fail("references/engine-data/scripts/command-metadata.json missing")
    if len(metadata) != EXPECTED_COMMANDS:
        fail(f"expected {EXPECTED_COMMANDS} commands, found {len(metadata)}")

    descriptor = files.get("references/engine-dependency.json")
    if descriptor is None:
        fail("embedded runtime descriptor missing")
    if len(descriptor) != DESCRIPTOR_BYTES or sha256_bytes(descriptor) != DESCRIPTOR_SHA:
        fail("embedded descriptor drifted from the frozen v1 descriptor")
    frozen_descriptor = hub / "engines/impeccable/runtime-dependency/descriptor.v1.json"
    if frozen_descriptor.is_file():
        if frozen_descriptor.read_bytes() != descriptor:
            fail("embedded descriptor is not byte-identical to the frozen hub descriptor")
    descriptor_value = json.loads(descriptor)
    if entry["minimumAppVersion"] != descriptor_value["minimumAppVersion"]:
        fail("registry minimumAppVersion is not bound to the frozen descriptor value")

    # ---- SKILL.md links resolve inside the package unless annotated ----
    skill_text = files["SKILL.md"].decode("utf-8")
    annotated = set(re.findall(r"\]\(([^)\s]+)\)(?:<!-- Floe: [^>]*is not shipped[^>]*-->)", skill_text))
    for target in re.findall(r"\]\(([^)\s]+)\)", skill_text):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        clean = target.split("#", 1)[0]
        if clean in annotated:
            continue
        if clean not in files:
            fail(f"SKILL.md link does not resolve: {target}")
    for name, data in files.items():
        if data.startswith(b"\x7fELF"):
            fail(f"ELF payload in package: {name}")

    # ---- deterministic ZIP + archive round trip + content digest ----
    data1 = hubcore.make_zip(files)
    data2 = hubcore.make_zip(dict(sorted(files.items())))
    if data1 != data2:
        fail("zip construction is not deterministic")
    repacked = hubcore.check_archive_bytes(data1, require_notice=True)
    if {k: sha256_bytes(v) for k, v in repacked.items()} != \
       {k: sha256_bytes(v) for k, v in files.items()}:
        fail("archive round-trip drift")
    digest = hubcore.content_digest(files)
    total = sum(len(v) for v in files.values())
    biggest = max(files.items(), key=lambda kv: len(kv[1]))

    # ---- authoritative builder in the isolated mirror (both planned channels) ----
    out = subprocess.run([sys.executable, str(scripts_mirror / "build_packages.py")],
                         capture_output=True, text=True, cwd=isolated)
    if out.returncode != 0:
        fail(f"build_packages failed: {out.stdout}{out.stderr}")
    channel_shas = {}
    for channel in plan["installPlatforms"]:
        rel = hubcore.package_path_for("impeccable", EXPECTED_VERSION, channel)
        arc = isolated / rel
        if not arc.is_file():
            fail(f"builder produced no archive at {rel}")
        channel_shas[channel] = {"path": rel,
                                 "sha256": sha256_bytes(arc.read_bytes()),
                                 "bytes": arc.stat().st_size}
    recheck = subprocess.run([sys.executable, str(scripts_mirror / "build_packages.py"), "--check"],
                             capture_output=True, text=True, cwd=isolated)
    if recheck.returncode != 0:
        fail(f"--check rebuild not immutable: {recheck.stdout}{recheck.stderr}")

    print(json.dumps({
        "ok": True,
        "files": len(files),
        "totalBytes": total,
        "largestFile": {"path": biggest[0], "bytes": len(biggest[1])},
        "acceptedReferences": len(refs),
        "commands": len(metadata),
        "contentDigest": digest,
        "archives": channel_shas,
        "builderOutput": out.stdout.strip(),
        "descriptorSha": sha256_bytes(descriptor),
        "descriptorBytes": len(descriptor),
        "helperSource": {
            "hubHead": git(hub, "rev-parse", "HEAD"),
            "hubHelperDirtyPaths": git(hub, "status", "--porcelain", "--", "scripts", "catalog"),
            "mirroredHelperSha256": helper_sha,
            "stagedEngineSubtrees": staged_engine_files,
            "note": "helpers mirrored byte-for-byte from the hub root at run time; "
                    "hubHead identifies the checked-out commit, hubHelperDirtyPaths "
                    "discloses uncommitted helper drift (coordinator integrates with H6 latest)",
        },
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
