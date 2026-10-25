#!/usr/bin/env python3
"""Export verification evidence into the tracked engine directory, redacted.

Raw evidence stays in the private lane scope. What the hub tracks must not carry
a private checkout path, a home directory, a build-cache location or the shared
build wrapper's path, so every string is rewritten to a neutral placeholder
before it is copied. Both spellings are scrubbed: the absolute path and its
checkout-relative form (`Local/Private/...`, `Local/Scratch/...`), because a
tool may record a path relative to the parent checkout and an absolute-prefix
substitution alone lets the relative form survive into the tracked evidence.
Digests, exit codes, check counts, uname output and the runner description are
preserved exactly: redaction changes where things live, never what was observed.

  export_evidence.py --from <raw-evidence-dir> --to <engines/impeccable/evidence> \
      [--file name.json]... [--repo <parent-checkout>] [--scratch <scratch-dir>] \
      [--cache <build-cache-dir>]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

PLACEHOLDERS = [
    ("<shared-build-wrapper>", "the serialized local build wrapper"),
]


def build_substitutions(args) -> list[tuple[str, str]]:
    home = str(Path.home())
    subs: list[tuple[str, str]] = []
    repo = Path(args.repo).expanduser().resolve() if args.repo else None

    def add(abs_path: Path, placeholder: str) -> None:
        """Map an absolute private path and, when it lives inside the parent
        checkout, its checkout-relative spelling to one placeholder. A tool
        that recorded `Local/Scratch/<lane>/...` verbatim would otherwise keep
        the private layout while the absolute form is already redacted."""
        subs.append((str(abs_path), placeholder))
        if repo is not None:
            try:
                rel = abs_path.relative_to(repo).as_posix()
            except ValueError:
                return
            if rel and rel != ".":
                subs.append((rel, placeholder))

    if args.wrapper:
        add(Path(args.wrapper).expanduser().resolve(), "<shared-build-wrapper>")
    if args.scratch:
        add(Path(args.scratch).expanduser().resolve(), "<scratch>")
    if args.cache:
        add(Path(args.cache).expanduser().resolve(), "<build-cache>")
    if repo is not None:
        add(repo / "Local/Private/floe-skill-hub", "<hub-root>")
        add(repo, "<parent-checkout>")
    subs += [
        (f"{home}/.cargo", "<home>/.cargo"),
        (f"{home}/.rustup", "<home>/.rustup"),
        (home, "<home>"),
        # A recorded stderr tail can start in the middle of a path, so the
        # absolute-prefix substitutions above miss it. Redact the recognizable
        # fragments too, or a truncated private path survives into the hub.
        ("Library/Caches/CodexBuild/floe-skill-hub-impeccable", "<build-cache>"),
        ("CodexBuild/floe-skill-hub-impeccable", "<build-cache>"),
        ("Library/Caches/CodexBuild", "<build-cache-root>"),
    ]
    # Longest first so a nested path is not partially rewritten.
    subs.sort(key=lambda pair: -len(pair[0]))
    return subs


def redact(node, subs: list[tuple[str, str]]):
    if isinstance(node, str):
        for src, dst in subs:
            node = node.replace(src, dst)
        return node
    if isinstance(node, dict):
        return {k: redact(v, subs) for k, v in node.items()}
    if isinstance(node, list):
        return [redact(v, subs) for v in node]
    return node


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="source", required=True, type=Path)
    ap.add_argument("--to", dest="target", required=True, type=Path)
    ap.add_argument("--file", action="append", default=[])
    ap.add_argument("--repo", default=None)
    ap.add_argument("--scratch", default=None)
    ap.add_argument("--cache", default=None)
    ap.add_argument("--wrapper", default=None)
    ap.add_argument("--fail-on", action="append",
                    default=["/Users/", "/Volumes/", "TECLAST", "ios-closure",
                             "CodexBuild", "Library/Caches", "jiangnangenius",
                             # Private-layout markers. Absolute and derived
                             # relative forms are scrubbed; any surviving
                             # spelling must fail the export closed, not ship.
                             "Local/Private", "Local/Scratch"],
                    help="substrings that must not survive redaction")
    args = ap.parse_args()

    subs = build_substitutions(args)
    args.target.mkdir(parents=True, exist_ok=True)
    names = args.file or sorted(p.name for p in args.source.glob("*.json"))
    exported = []
    leftovers = []
    for name in names:
        src = args.source / name
        if not src.is_file():
            continue
        raw = src.read_text(encoding="utf-8")
        try:
            doc = json.loads(raw)
            redacted = json.dumps(redact(doc, subs), indent=2, ensure_ascii=False) + "\n"
        except json.JSONDecodeError:
            text = raw
            for from_, to in subs:
                text = text.replace(from_, to)
            redacted = text
        for needle in args.fail_on:
            if needle in redacted:
                leftovers.append({"file": name, "needle": needle})
        (args.target / name).write_text(redacted, encoding="utf-8")
        exported.append(name)

    report = {
        "ok": not leftovers,
        "exported": exported,
        "leftovers": leftovers,
        "placeholders": sorted({dst for _, dst in subs}),
    }
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
