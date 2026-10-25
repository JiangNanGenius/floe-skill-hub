#!/usr/bin/env python3
"""Single-file local document -> Markdown conversion with an honest receipt.

First-party Floe script (MIT (c) Floe project). Wraps md_converters with the
bounded-CLI contract: --root confinement, symlink/traversal rejection, byte
caps, atomic writes, overwrite protection, and a JSON receipt (stdout or
--receipt file) that records the converter, engine versions, source/output
digests, warnings and source preservation. Native-route formats (DOCX/HTML/
RTF, images, protected or scanned PDFs) are refused with the exact Floe
native tool to use instead - this script never bypasses document protection
and never calls an external service.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from md_converters import (  # noqa: E402
    DEFAULT_MAX_BYTES,
    ConversionError,
    checked_input_file,
    checked_output_file,
    convert_file,
    engine_versions,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", help="local file inside --root")
    parser.add_argument("--root", default=".", help="existing directory bounding all paths")
    parser.add_argument("--output", required=True, help="new .md output path inside --root")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument("--max-rows", type=int, default=2000,
                        help="markdown table row bound per sheet/file")
    parser.add_argument("--receipt", help="optional path for the JSON receipt (else stdout)")
    parser.add_argument("--force", action="store_true", help="allow replacing an existing output")
    args = parser.parse_args(argv)
    try:
        source = checked_input_file(args.input, root=args.root, max_bytes=args.max_bytes)
        output = checked_output_file(args.output, root=args.root, force=args.force)
    except ConversionError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 2
    receipt = convert_file(source, output, max_rows=args.max_rows)
    payload = {
        "schema_version": "1.0",
        "receipt": receipt.as_dict(),
        "engine_versions": engine_versions(),
        "evidence_class": "guest conversion receipt; native-route items must be completed with the named native tool",
    }
    body = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
    if args.receipt:
        try:
            receipt_path = checked_output_file(args.receipt, root=args.root, force=args.force)
        except ConversionError as exc:
            print(f"[FAIL] {exc}", file=sys.stderr)
            return 2
        receipt_path.write_text(body + "\n", encoding="utf-8")
    if receipt.status == "converted":
        print(f"[OK] {receipt.source} -> {receipt.output} ({receipt.characters} chars)")
        for warning in receipt.warnings:
            print(f"[WARN] {warning}")
        if not args.receipt:
            print(body)
        return 0
    if receipt.status == "native-route":
        print(f"[NATIVE-ROUTE] {receipt.source}: use {receipt.native_route}", file=sys.stderr)
        if not args.receipt:
            print(body)
        return 4
    print(f"[FAIL] {receipt.source}: {receipt.error}", file=sys.stderr)
    if not args.receipt:
        print(body)
    return 1 if receipt.status == "failed" else 3


if __name__ == "__main__":
    raise SystemExit(main())
