#!/usr/bin/env python3
"""Batch local document -> Markdown conversion with a truthful manifest.

First-party Floe script (MIT (c) Floe project), modeled on the safety
skeleton of the upstream MIT batch helper (see references/PROVENANCE.md):
skips symlinks, preserves relative directories, writes each result as
<source-name>.md to avoid basename collisions, refuses overwrite without
--overwrite, records a deterministic manifest with per-file status,
converter, digests and source-preservation flags.

Native-route formats are recorded as `native-route` manifest entries with
the exact Floe native tool to use - the batch never fakes their conversion.
No plugins, no network, no external services; audio/video extensions are
rejected outright.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from md_converters import (  # noqa: E402
    DEFAULT_MAX_BYTES,
    ConversionError,
    atomic_write_text,
    checked_root,
    convert_file,
    engine_versions,
)

DEFAULT_EXTENSIONS = (".csv", ".tsv", ".json", ".xlsx", ".pptx", ".pdf", ".txt", ".md",
                      ".docx", ".html", ".htm", ".rtf")
REJECTED_EXTENSIONS = {".m4a", ".mp3", ".mp4", ".wav", ".pptm", ".doc", ".xls"}


def normalize_extensions(values: list[str]) -> tuple[str, ...]:
    normalized: set[str] = set()
    for value in values:
        extension = value.strip().lower()
        if not extension:
            continue
        if not extension.startswith("."):
            extension = f".{extension}"
        if extension == ".":
            raise ConversionError("a file extension cannot be only '.'")
        normalized.add(extension)
    if not normalized:
        raise ConversionError("at least one file extension is required")
    rejected = sorted(normalized & REJECTED_EXTENSIONS)
    if rejected:
        raise ConversionError(
            f"these extensions are never processed in the guest ({', '.join(rejected)}); "
            "audio/video transcription is unsupported and macro/legacy formats are refused")
    return tuple(sorted(normalized))


def discover_files(input_dir: Path, extensions: tuple[str, ...], recursive: bool) -> list[Path]:
    iterator = input_dir.rglob("*") if recursive else input_dir.iterdir()
    return sorted(
        (path for path in iterator
         if path.suffix.lower() in extensions
         and path.name.lower().endswith(extensions)
         and (path.is_file() or path.is_symlink())),
        key=lambda path: path.as_posix())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--extensions", nargs="+", default=list(DEFAULT_EXTENSIONS), metavar="EXT")
    parser.add_argument("--recursive", "-r", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument("--max-rows", type=int, default=2000)
    parser.add_argument("--manifest", type=Path, help="JSON manifest path")
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args(argv)
    try:
        extensions = normalize_extensions(args.extensions)
        input_dir = checked_root(args.input_dir)
    except ConversionError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 2
    if args.max_bytes <= 0:
        print("[FAIL] --max-bytes must be positive", file=sys.stderr)
        return 2
    output_dir = Path(args.output_dir)
    if output_dir.is_symlink():
        print("[FAIL] output directory must not be a symlink", file=sys.stderr)
        return 2
    output_dir.mkdir(parents=True, exist_ok=True)

    candidates = discover_files(input_dir, extensions, args.recursive)
    records: list[dict] = []
    for source in candidates:
        relative = source.relative_to(input_dir).as_posix()
        if source.is_symlink():
            records.append({"source": relative, "status": "skipped",
                            "error": "symbolic links are disabled"})
            print(f"skipped   {relative} (symlink)")
            continue
        if source.stat().st_size > min(args.max_bytes, 512 * 1024 * 1024):
            records.append({"source": relative, "status": "skipped",
                            "error": f"source exceeds the byte limit ({args.max_bytes})"})
            print(f"skipped   {relative} (byte limit)")
            continue
        destination = output_dir / Path(relative).parent / f"{Path(relative).name}.md"
        if destination.exists() and not args.overwrite:
            records.append({"source": relative, "status": "skipped",
                            "output": destination.relative_to(output_dir).as_posix(),
                            "error": "output already exists"})
            print(f"skipped   {relative} (output exists)")
            continue
        try:
            receipt = convert_file(source, destination, max_rows=args.max_rows)
        except ConversionError as exc:
            receipt = None
            records.append({"source": relative, "status": "failed", "error": str(exc)})
            print(f"failed    {relative} {exc}")
            if args.fail_fast:
                break
            continue
        entry = receipt.as_dict()
        entry["source"] = relative
        if receipt.output:
            entry["output"] = str(destination.relative_to(output_dir))
        records.append(entry)
        detail = entry.get("output") or entry.get("native_route") or entry.get("error") or ""
        print(f"{receipt.status:12} {relative} {detail}"[:240])
        if args.fail_fast and receipt.status == "failed":
            break

    counts = {status: sum(r["status"] == status for r in records)
              for status in ("converted", "native-route", "skipped", "failed", "unsupported")}
    if args.manifest is not None:
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "input_dir": input_dir.name,
            "output_dir": output_dir.name,
            "engine_versions": engine_versions(),
            "counts": counts,
            "records": records,
        }
        atomic_write_text(Path(args.manifest), json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print("Summary: " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items()) if v))
    if not candidates:
        print(f"No matching files found for: {', '.join(extensions)}")
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
