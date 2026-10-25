#!/usr/bin/env python3
"""Drive the Needs -> facts -> re-run fixpoint with a reference hit-test answerer.

This is the reference implementation of the native side's job, written against
the frozen contract so A2 has an executable specification rather than prose:

  1. run `floe-impeccable snapshot-scan` on a snapshot + identity;
  2. when the engine comes back `needs-facts`, answer every requested point with
     a geometric hit test over the same snapshot (`elementFromPoint` /
     `elementsFromPoint` semantics: the deepest painted element whose box
     contains the point, then its ancestor chain front to back);
  3. echo the exact double bits the engine asked for, carry the full binding,
     and re-run with `--facts` and `--round 2`;
  4. record the observed round-1 and round-2 documents under `expected/`.

A point that no element box contains is answered `top: 0, stack: []` exactly as
a browser would answer "nothing there". A point the caller knows it cannot
answer should instead be marked `"unanswerable": true`, which the engine reports
rather than treating as clean.

Usage:
  observe_and_complete.py --engine <binary> --contract <contract-dir> \
      --out <expected-dir> [--case name=snapshot.json,identity.json] ...
"""

from __future__ import annotations

import argparse
import json
import struct
import subprocess
import sys
from pathlib import Path


def bits(value: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", float(value)))[0]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class ReferenceHitTester:
    """`elementFromPoint` / `elementsFromPoint` over a snapshot document.

    Deliberately simple and deterministic: it knows nothing the snapshot does
    not carry. The real native producer answers from WebKit itself; this exists
    so fixtures and integration tests can complete the fixpoint without a
    browser, and so the expected element-id mapping is written down once.
    """

    def __init__(self, snapshot: dict):
        self.els = snapshot["els"]
        self.strings = snapshot["strings"]
        self.style_props = snapshot["styleProps"]
        self.style_index = {name: i for i, name in enumerate(self.style_props)}

    def style(self, el: dict, prop: str) -> str:
        col = self.style_index.get(prop)
        if col is None or col >= len(el.get("s", [])):
            return ""
        idx = el["s"][col]
        return self.strings[idx] if idx < len(self.strings) else ""

    def is_hit_testable(self, el: dict) -> bool:
        rect = el.get("r")
        if not rect or len(rect) < 4:
            return False
        w, h = rect[2], rect[3]
        if not (w > 0 and h > 0):
            return False
        if el.get("v", 1) == 0:
            return False
        if self.style(el, "display") == "none":
            return False
        if self.style(el, "visibility") == "hidden":
            return False
        return True

    def contains(self, el: dict, x: float, y: float) -> bool:
        rx, ry, rw, rh = el["r"]
        return rx <= x <= rx + rw and ry <= y <= ry + rh

    def ancestors(self, element_id: int) -> list[int]:
        chain = [element_id]
        current = element_id
        while True:
            parent = self.els[current - 1].get("p")
            if not parent:
                break
            chain.append(parent)
            current = parent
        return chain

    def answer(self, x: float, y: float) -> tuple[int, list[int]]:
        candidates = [
            i + 1 for i, el in enumerate(self.els)
            if self.is_hit_testable(el) and self.contains(el, x, y)
        ]
        if not candidates:
            return 0, []
        # Paint order for a page without stacking-context surprises: the last
        # element in document order that contains the point is on top.
        top = candidates[-1]
        return top, self.ancestors(top)


def scan(engine: Path, args: list[str]) -> tuple[int, dict | None, str]:
    out_path = None
    if "--out" in args:
        out_path = Path(args[args.index("--out") + 1])
    proc = subprocess.run([str(engine), "snapshot-scan", *args], capture_output=True, text=True)
    document = None
    if out_path and out_path.is_file():
        document = load(out_path)
    elif proc.stdout.strip():
        try:
            document = json.loads(proc.stdout)
        except json.JSONDecodeError:
            document = None
    return proc.returncode, document, proc.stderr


def build_facts(needs: dict, snapshot: dict, identity: dict, tester: ReferenceHitTester) -> dict:
    hits = []
    for point, point_bits in zip(needs.get("hitTests") or [], needs.get("hitTestsBits") or []):
        x, y = float(point[0]), float(point[1])
        top, stack = tester.answer(x, y)
        hits.append({
            "x": x,
            "y": y,
            "xBits": int(point_bits[0]),
            "yBits": int(point_bits[1]),
            "top": top,
            "stack": stack,
            "unanswerable": False,
        })
    return {
        "taskId": identity["taskId"],
        "sessionId": identity["sessionId"],
        "tabId": identity["tabId"],
        "documentId": identity["documentId"],
        "captureId": identity["captureId"],
        "documentGeneration": identity["documentGeneration"],
        "fenced": False,
        "hits": hits,
        "shownOnScroll": [{"el": el, "shown": False} for el in (needs.get("scrollProbes") or [])],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True, type=Path)
    ap.add_argument("--contract", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--case", action="append", default=[],
                    help="name=snapshot.json,identity.json")
    ap.add_argument("--max-rounds", type=int, default=4)
    args = ap.parse_args()

    if not args.engine.is_file():
        print(json.dumps({"ok": False, "error": "engine binary not found", "engine": str(args.engine)}))
        return 2
    args.out.mkdir(parents=True, exist_ok=True)

    cases = []
    for entry in args.case:
        name, rest = entry.split("=", 1)
        snapshot_name, identity_name = rest.split(",")
        cases.append((name, args.contract / snapshot_name, args.contract / identity_name))

    report = {"engine": str(args.engine), "cases": []}
    exit_code = 0
    for name, snapshot_path, identity_path in cases:
        snapshot = load(snapshot_path)
        identity = load(identity_path)
        tester = ReferenceHitTester(snapshot)
        case: dict = {"name": name, "snapshot": snapshot_path.name, "identity": identity_path.name}

        round1_out = args.out / f"{name}-round1-needs.v1.json"
        code1, doc1, err1 = scan(args.engine, [
            "--snapshot", str(snapshot_path), "--identity", str(identity_path),
            "--out", str(round1_out), "--round", "1",
        ])
        if doc1 is None:
            case.update({"ok": False, "stage": "round1", "exit": code1, "stderr": err1[-500:]})
            report["cases"].append(case)
            exit_code = 1
            continue
        case["round1"] = {
            "exit": code1,
            "status": doc1.get("status"),
            "verdict": doc1.get("verdict"),
            "hitTestsAsked": len((doc1.get("needs") or {}).get("hitTests") or []),
            "scrollProbes": len((doc1.get("needs") or {}).get("scrollProbes") or []),
        }
        if doc1.get("status") != "needs-facts":
            case.update({"ok": False, "stage": "round1", "reason": "expected needs-facts"})
            report["cases"].append(case)
            exit_code = 1
            continue

        facts = build_facts(doc1["needs"], snapshot, identity, tester)
        facts_path = args.out / f"{name}-facts-round2.v1.json"
        facts_path.write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8")

        round2_out = args.out / f"{name}-round2-result.v1.json"
        code2, doc2, err2 = scan(args.engine, [
            "--snapshot", str(snapshot_path), "--identity", str(identity_path),
            "--facts", str(facts_path), "--out", str(round2_out), "--round", "2",
        ])
        if doc2 is None:
            case.update({"ok": False, "stage": "round2", "exit": code2, "stderr": err2[-500:]})
            report["cases"].append(case)
            exit_code = 1
            continue
        coverage = doc2.get("coverage") or {}
        counts = ((doc2.get("findings") or {}).get("counts") or {})
        case["round2"] = {
            "exit": code2,
            "status": doc2.get("status"),
            "verdict": doc2.get("verdict"),
            "findingsTotal": counts.get("total"),
            "byRule": counts.get("byRule"),
            "uncoveredRequired": coverage.get("uncoveredRequired"),
            "unknownStyleProps": coverage.get("unknownStyleProps"),
            "needs": (doc2.get("needs") or {}).get("hitTests"),
        }
        case["facts"] = {
            "path": facts_path.name,
            "answered": sum(1 for h in facts["hits"] if not h.get("unanswerable")),
            "distinctTopElements": sorted({h["top"] for h in facts["hits"]}),
        }
        # A completed round must not still be asking, and must not claim clean.
        if doc2.get("status") == "needs-facts":
            case["ok"] = False
            case["reason"] = "the fixpoint did not converge after the facts round"
            exit_code = 1
        elif doc2.get("verdict") == "clean":
            case["ok"] = False
            case["reason"] = "v1 must never report a clean verdict while required passes are uncovered"
            exit_code = 1
        else:
            case["ok"] = True
        report["cases"].append(case)

    (args.out / "fixpoint-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
