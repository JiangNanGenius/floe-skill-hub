#!/usr/bin/env python3
"""Generate the rule-pass limiter regression fixtures (adapter-owned).

Two synthetic snapshot/identity pairs, derived from the frozen contract
generator (never from private capture packets):

  snapshot-large-shape.v1.json    ~2000 sections x (short h2 + long p),
                                  980x735 viewport, ~124k px page, all-static
                                  styles, hits=[] — mimics the *shape* of the
                                  diagnostic31 layout (public structure only;
                                  no private bytes). Exercises the memo and
                                  order-preservation paths while every
                                  conditional quadratic stays gated off.

  snapshot-admission.v1.json      a dense grid of small visible text boxes
                                  fully inside the viewport, hits=[] — the
                                  unique probe misses cross the per-round cap
                                  so the four admission edges are reachable
                                  from the CLI (--max-hit-tests M / M-1).

Both bind to their own identity documents (hostname/viewport/scroll equality)
and parse under the frozen strict schema (the generator owns the 138-column
style table).

  make_regression_fixtures.py --upstream <pinned-source-dir> \
      --out <adapter/tests/data>
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


def make_identity(module, *, capture_id: str, hostname: str, width: float, height: float) -> dict:
    return {
        "taskId": f"task-{capture_id}",
        "sessionId": f"session-{capture_id}",
        "tabId": f"tab-{capture_id}",
        "documentId": f"doc-{capture_id}",
        "captureId": capture_id,
        "documentGeneration": 1,
        "url": f"https://{hostname}/",
        "hostname": hostname,
        "viewport": {"width": width, "height": height},
        "scroll": {"x": 0.0, "y": 0.0},
        "capturedAtMs": 0,
        "producerTrust": "native-fixed-script",
        "producer": {
            "name": "FloeWebkitDesignCapture",
            "version": "0.0.0-fixture",
            "engine": "WebKit",
            "scriptDigest": "0" * 64,
        },
        "redaction": {
            "policy": "floe.impeccable.redaction.v1",
            "applied": True,
            "passwordInputs": 0,
            "formValues": 0,
            "credentialAttributes": [],
            "textRuns": 0,
        },
    }


def skeleton(module, lists, *, hostname: str, width: float, height: float, title: str):
    """The 7-element document skeleton the large captures share."""
    b = module.SnapshotBuilder(
        lists,
        hostname=hostname,
        inner_width=width,
        inner_height=height,
        linked_css="",
    )
    page_height = height  # replaced by the caller's scrollHeight
    html = b.add(tag="HTML", rect=[0.0, 0.0, width, height],
                 metrics=module._metrics([0, 0, width, height], scroll_height=page_height))
    head = b.add(tag="HEAD", parent=html, rect=[0.0, 0.0, 0.0, 0.0])
    meta = b.add(tag="META", parent=head, rect=[0.0, 0.0, 0.0, 0.0])
    title_el = b.add(tag="TITLE", parent=head, children_text=[title], rect=[0.0, 0.0, 0.0, 0.0])
    style = b.add(tag="STYLE", parent=head, rect=[0.0, 0.0, 0.0, 0.0])
    b.els[head - 1]["c"] = [meta, title_el, style]
    return b, html, head


def build_large_shape(module, lists) -> dict:
    """~2000 sections x (h2 short + p long); 99%+ offscreen; all static."""
    width, height = 980.0, 735.0
    sections = 2000
    section_h = 49.0
    gap = 13.0
    step = section_h + gap
    page_bottom = 60.0 + sections * step + 400.0  # ~124k px, like the real layout
    b, html, head = skeleton(module, lists, hostname="large-shape.fixture.local",
                             width=width, height=height, title="Large shape")
    b.els[html - 1]["m"] = module._metrics([0, 0, width, height], scroll_height=page_bottom)
    body = b.add(tag="BODY", parent=html, rect=[0.0, 0.0, width, height],
                 metrics=module._metrics([0, 0, width, height], scroll_height=page_bottom),
                 style={"marginTop": "0px", "marginBottom": "0px"})
    b.els[html - 1]["c"] = [head, body]
    h1 = b.add(tag="H1", parent=body, rect=[16.0, 12.0, 948.0, 36.0],
               metrics=module._metrics([16, 12, 948, 36]),
               children_text=["Large shape index"],
               direct_text_rect=[16.0, 12.0, 948.0, 36.0],
               text_rects=[[16.0, 12.0, 948.0, 36.0]],
               style={"fontSize": "30px", "lineHeight": "36px", "fontWeight": "700"})
    heading = "Section heading"          # 17 utf16 chars, <= 48
    paragraph = ("Body copy that runs well past forty-eight characters so the "
                 "paragraph rules have real text to measure and wrap.")  # > 48
    body_children = [h1]
    for i in range(sections):
        top = 60.0 + i * step
        sec = b.add(tag="SECTION", parent=body,
                    rect=[16.0, top, 916.0, section_h],
                    metrics=module._metrics([16, top, 916, section_h]))
        h2 = b.add(tag="H2", parent=sec,
                   rect=[24.0, top + 4.0, 900.0, 19.0],
                   metrics=module._metrics([24, top + 4, 900, 19]),
                   children_text=[heading],
                   direct_text_rect=[24.0, top + 4.0, 900.0, 19.0],
                   text_rects=[[24.0, top + 4.0, 900.0, 19.0]],
                   style={"fontSize": "17px", "lineHeight": "19px", "fontWeight": "600"})
        p = b.add(tag="P", parent=sec,
                  rect=[24.0, top + 25.0, 900.0, 19.0],
                  metrics=module._metrics([24, top + 25, 900, 19]),
                  children_text=[paragraph],
                  direct_text_rect=[24.0, top + 25.0, 900.0, 19.0],
                  text_rects=[[24.0, top + 25.0, 900.0, 19.0]],
                  style={"fontSize": "15px", "lineHeight": "19px"})
        b.els[sec - 1]["c"] = [h2, p]
        body_children.append(sec)
    b.els[body - 1]["c"] = body_children
    b.body_inner_text = "\n".join([heading, paragraph] * sections)
    doc = b.document(document_element=html, body=body)
    doc["hits"] = []
    return doc


def build_admission(module, lists) -> dict:
    """A dense grid of small visible text boxes inside the viewport, hits=[]."""
    width, height = 980.0, 735.0
    cols, rows = 18, 46
    cell_w, cell_h = 50.0, 14.0
    pitch_x, pitch_y = 54.0, 16.0
    page_bottom = rows * pitch_y + 40.0
    b, html, head = skeleton(module, lists, hostname="admission.fixture.local",
                             width=width, height=height, title="Admission grid")
    b.els[html - 1]["m"] = module._metrics([0, 0, width, height], scroll_height=page_bottom)
    body = b.add(tag="BODY", parent=html, rect=[0.0, 0.0, width, height],
                 metrics=module._metrics([0, 0, width, height], scroll_height=page_bottom),
                 style={"marginTop": "0px", "marginBottom": "0px"})
    b.els[html - 1]["c"] = [head, body]
    text = "Grid cell text"  # 14 utf16 chars, alpha, in 4..=48
    spans = []
    for r in range(rows):
        for c in range(cols):
            left = 8.0 + c * pitch_x
            top = 8.0 + r * pitch_y
            el = b.add(tag="SPAN", parent=body,
                       rect=[left, top, cell_w, cell_h],
                       metrics=module._metrics([left, top, cell_w, cell_h]),
                       children_text=[text],
                       direct_text_rect=[left, top, cell_w, cell_h],
                       text_rects=[[left, top, cell_w, cell_h]],
                       style={"display": "inline-block", "fontSize": "11px",
                              "lineHeight": "14px"})
            spans.append(el)
    b.els[body - 1]["c"] = spans
    b.body_inner_text = " ".join([text] * (cols * rows))
    doc = b.document(document_element=html, body=body)
    doc["hits"] = []
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=ADAPTER / "tests" / "data")
    args = ap.parse_args()

    generator = load_module("make_contract_fixtures", CONTRACT / "tools/make_contract_fixtures.py")
    lists = generator.load_upstream_lists(args.upstream)
    args.out.mkdir(parents=True, exist_ok=True)

    large = build_large_shape(generator, lists)
    (args.out / "snapshot-large-shape.v1.json").write_text(
        json.dumps(large, indent=1) + "\n", encoding="utf-8")
    (args.out / "identity-large-shape.v1.json").write_text(
        json.dumps(make_identity(generator, capture_id="cap-large-shape-0001",
                                 hostname="large-shape.fixture.local",
                                 width=980.0, height=735.0), indent=2) + "\n",
        encoding="utf-8")

    admission = build_admission(generator, lists)
    (args.out / "snapshot-admission.v1.json").write_text(
        json.dumps(admission, indent=1) + "\n", encoding="utf-8")
    (args.out / "identity-admission.v1.json").write_text(
        json.dumps(make_identity(generator, capture_id="cap-admission-0001",
                                 hostname="admission.fixture.local",
                                 width=980.0, height=735.0), indent=2) + "\n",
        encoding="utf-8")

    print(f"large-shape: {len(large['els'])} els, {len(json.dumps(large))} bytes")
    print(f"admission:   {len(admission['els'])} els, {len(json.dumps(admission))} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
