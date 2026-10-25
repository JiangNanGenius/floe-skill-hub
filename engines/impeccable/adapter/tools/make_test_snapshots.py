#!/usr/bin/env python3
"""Generate the adapter's own test data from the frozen contract fixtures.

The contract fixtures under `engines/impeccable/contract/fixtures/` are frozen
and are the artifacts native (A2) codes against, so the adapter's Rust tests
must not need new files there. This script derives test-only snapshots into
`adapter/tests/data/` instead:

  snapshot-no-findings.v1.json   the positive fixture page with body copy at a
                                 normal text size, used to prove that an empty
                                 finding list is `inconclusive` and never `clean`
                                 while required passes are uncovered;
  snapshot-media-intrinsics.v1.json  the same page with an <img> that carries
                                 media intrinsics, used for the media coverage
                                 state;
  facts-unanswerable-template.v1.json  a shape example with every point marked
                                 unanswerable (the tests fill the real points
                                 from an observed Needs).

It imports the frozen generator and the reference hit-tester rather than
duplicating them, so a contract change shows up here immediately.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ADAPTER = HERE.parent
CONTRACT = ADAPTER.parent / "contract"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=ADAPTER / "tests" / "data")
    args = ap.parse_args()

    generator = load_module("make_contract_fixtures", CONTRACT / "tools/make_contract_fixtures.py")
    lists = generator.load_upstream_lists(args.upstream)
    args.out.mkdir(parents=True, exist_ok=True)

    positive = generator.build_positive_fixture(lists)

    # 1. A page whose body copy is a normal size: the tiny-text finding goes
    #    away, so the run has nothing to report and the verdict rule is what is
    #    under test.
    strings = positive["strings"]
    replacements = {"9px": "16px", "12px": "24px"}
    for old, new in replacements.items():
        if old in strings and new not in strings:
            strings.append(new)
    remap = {}
    for old, new in replacements.items():
        if old in strings:
            remap[strings.index(old)] = strings.index(new)
    for el in positive["els"]:
        el["s"] = [remap.get(idx, idx) for idx in el["s"]]
    (args.out / "snapshot-no-findings.v1.json").write_text(
        json.dumps(positive, indent=1) + "\n", encoding="utf-8")

    # 2. The same page with an <img> that carries media intrinsics, so the
    #    media-intrinsics coverage pass has something to observe.
    with_media = generator.build_positive_fixture(lists)
    img = {
        "t": "IMG",
        "p": 4,
        "a": [["src", "/fixture.png"], ["alt", "Fixture image"], ["width", "120"], ["height", "80"]],
        "r": [24.0, 160.0, 120.0, 80.0],
        "m": [120.0, 80.0, 0.0, 120.0, 0.0, 120.0, 80.0, 80.0],
        "v": 1,
        "md": {"nw": 240.0, "nh": 160.0, "vw": 0.0, "vh": 0.0, "w": 120.0, "h": 80.0,
               "cur": "https://fixture.local/fixture.png", "src": "/fixture.png", "cp": True},
    }
    # Reuse the paragraph's style column so the image inherits plausible values.
    img["s"] = list(with_media["els"][5]["s"])
    with_media["els"].append(img)
    img_id = len(with_media["els"])
    with_media["els"][3]["c"] = list(with_media["els"][3].get("c", [])) + [img_id]
    with_media["html"] = with_media["html"].replace(
        "</body>", '<img src="/fixture.png" alt="Fixture image" width="120" height="80"></body>')
    (args.out / "snapshot-media-intrinsics.v1.json").write_text(
        json.dumps(with_media, indent=1) + "\n", encoding="utf-8")

    # 3. Identity documents bound to the derived snapshots (same viewport and
    #    hostname, distinct capture ids).
    base_identity = json.loads((CONTRACT / "fixtures/identity-positive.v1.json").read_text(encoding="utf-8"))
    for name, capture in (("identity-no-findings.v1.json", "cap-test-no-findings-0001"),
                          ("identity-media.v1.json", "cap-test-media-0001")):
        identity = dict(base_identity, captureId=capture, documentId=f"doc-{capture}")
        (args.out / name).write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")

    # 4. The unanswerable facts shape.
    (args.out / "facts-unanswerable-template.v1.json").write_text(json.dumps({
        "_note": "shape only: the tests fill x/y/xBits/yBits from an observed Needs",
        "taskId": base_identity["taskId"],
        "sessionId": base_identity["sessionId"],
        "tabId": base_identity["tabId"],
        "documentId": base_identity["documentId"],
        "captureId": base_identity["captureId"],
        "documentGeneration": base_identity["documentGeneration"],
        "hits": [{"x": 0.0, "y": 0.0, "xBits": 0, "yBits": 0, "top": 0, "stack": [],
                  "unanswerable": True, "reason": "template"}],
        "shownOnScroll": [],
    }, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "written": sorted(p.name for p in args.out.glob("*.json")),
        "noFindingsElements": len(positive["els"]),
        "mediaElements": len(with_media["els"]),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
