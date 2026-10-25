#!/usr/bin/env python3
"""Turn an observed `needs` document into a facts skeleton the native side fills.

The engine decides the hit-test points, so a facts file can only be authored
from a real `needs`. This keeps the round trip honest for fixture work and for
native (A2) integration tests:

  floe-impeccable snapshot-scan --snapshot S --out R      # status needs-facts
  fill_facts_from_needs.py --result R --out F --identity I

`F` then carries every requested point with its exact f64 bits, the binding
captureId/documentId and a `top`/`stack` pair the native producer has to
answer from the same document. Points the native side cannot answer must keep
`"unanswerable": true`; the engine reports them instead of passing them.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path


def bits(value: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", float(value)))[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", required=True, type=Path, help="scan result document with status needs-facts")
    ap.add_argument("--identity", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--answer", action="append", default=[],
                    help="optional preset answer x,y,top[,stack] for deterministic fixtures")
    args = ap.parse_args()

    result = json.loads(args.result.read_text(encoding="utf-8"))
    identity = json.loads(args.identity.read_text(encoding="utf-8"))
    needs = result.get("needs") or {}
    points = needs.get("hitTests") or []
    if not points:
        print(json.dumps({"error": "result carries no hit-test needs", "status": result.get("status")}, indent=2))
        return 2

    presets: dict[tuple[int, int], dict] = {}
    for entry in args.answer:
        parts = entry.split(",")
        if len(parts) < 3:
            raise SystemExit(f"--answer expects x,y,top[,stack]: {entry}")
        x, y, top = float(parts[0]), float(parts[1]), int(parts[2])
        stack = [int(v) for v in parts[3].split("|") if v] if len(parts) > 3 and parts[3] else []
        presets[(bits(x), bits(y))] = {"top": top, "stack": stack}

    hits = []
    for point in points:
        x, y = float(point[0]), float(point[1])
        hit = {
            "x": x,
            "y": y,
            "xBits": bits(x),
            "yBits": bits(y),
            "top": 0,
            "stack": [],
            "unanswerable": True,
            "reason": "awaiting native elementFromPoint/elementsFromPoint answer",
        }
        preset = presets.get((bits(x), bits(y)))
        if preset:
            hit.update({"top": preset["top"], "stack": preset["stack"], "unanswerable": False})
            hit.pop("reason", None)
        hits.append(hit)

    facts = {
        "captureId": identity.get("captureId"),
        "documentId": identity.get("documentId"),
        "hits": hits,
        "shownOnScroll": [{"el": el, "shown": False} for el in (needs.get("scrollProbes") or [])],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(facts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "written": str(args.out),
        "hitTests": len(hits),
        "answered": sum(1 for h in hits if not h.get("unanswerable")),
        "unanswered": sum(1 for h in hits if h.get("unanswerable")),
        "scrollProbes": len(facts["shownOnScroll"]),
        "captureId": facts["captureId"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
