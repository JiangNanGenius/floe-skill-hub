#!/usr/bin/env python3
"""Deterministic package builder for staged sources/{id}/ directories.

sources/{id}/ belongs to the content lanes (H2/H3/H4/H5 and the builtin
migration); this builder only validates and packages what is already staged
and fails closed on any gate violation. No source code is ever executed.
Each staged version is immutable: rebuilding the same id+version must produce
byte-identical archives or the build refuses.

python3 scripts/build_packages.py            # build every staged source
python3 scripts/build_packages.py --check    # read-only rebuild comparison
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import hubcore

REPO = pathlib.Path(__file__).resolve().parents[1]


def registry_by_id():
    registry = json.loads((REPO / "catalog" / "skills.json").read_bytes())
    hubcore.validate_registry(registry)
    return {e["id"]: e for e in registry["skills"]}


def build_one(skill_id, entry, check, root=None):
    root = root or REPO
    folder = root / "sources" / skill_id
    files = {}
    for path in sorted(folder.rglob("*")):
        rel = path.relative_to(folder).as_posix()
        if path.is_symlink():
            raise hubcore.HubError(f"symlink in skill source: {rel}")
        if path.is_dir():
            continue
        if path.name == "release.json":
            continue  # release metadata lives in the registry, not the archive
        files[rel] = path.read_bytes()
    require_notice = entry["upstream"] is not None
    hubcore.validate_package_files(files, require_notice=require_notice)
    manifest, _ = hubcore.validate_package_files(files, require_notice=require_notice)
    if manifest["id"] != skill_id:
        raise hubcore.HubError(f"{skill_id}: floe.json id mismatch")
    if entry["versionTarget"] != manifest["version"]:
        raise hubcore.HubError(f"{skill_id}: staged version differs from the registry target")
    data = hubcore.make_zip(files)
    written = []
    for channel in entry["plannedRuntime"]["installPlatforms"]:
        rel = hubcore.package_path_for(skill_id, manifest["version"], channel)
        target = root / rel
        if target.exists():
            if target.read_bytes() != data:
                raise hubcore.HubError(
                    f"immutable version changed: {rel}; bump the version")
            continue
        if check:
            written.append(rel + " (would create)")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        written.append(rel)
    return written


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    entries = registry_by_id()
    sources = REPO / "sources"
    built = []
    count = 0
    pending = []
    if sources.is_dir():
        for folder in sorted(sources.iterdir()):
            if not folder.is_dir():
                continue
            skill_id = folder.name
            has_manifest = (folder / "SKILL.md").exists()
            has_any_file = any(path.is_file() for path in folder.rglob("*"))
            if not has_manifest and not has_any_file:
                pending.append(skill_id)   # owner lane placeholder, nothing staged yet
                continue
            if not has_manifest:
                raise hubcore.HubError(
                    f"sources/{skill_id} has staged files but no SKILL.md; complete or remove")
            if skill_id not in entries:
                raise hubcore.HubError(
                    f"staged source {skill_id} has no registry entry; register it first")
            built.extend(build_one(skill_id, entries[skill_id], args.check))
            count += 1
    if pending:
        print("pending placeholders (no files staged): " + ", ".join(pending))
    verb = "checked" if args.check else "built"
    print(f"packages {verb}: {count} staged source(s); artifacts: "
          + (", ".join(built) if built else "none new (immutable archives unchanged)"))


if __name__ == "__main__":
    main()
