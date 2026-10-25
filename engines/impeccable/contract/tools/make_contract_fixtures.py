#!/usr/bin/env python3
"""Generate the Floe/Impeccable v1 snapshot-facts contract artifacts.

Everything the native (A2) measurement producer and the Floe engine adapter
agree on is emitted from this one script so the wire schema, the property
lists, the capture limits, the JSON Schemas and the fixtures can never drift
apart:

  * the computed-style property columns are parsed out of the PINNED upstream
    source (Rust `STYLE_PROPS` / `PSEUDO_PROPS` and the JS producer's
    `__SNAP_STYLE_PROPS` / `__SNAP_PSEUDO_PROPS` / `__SNAP_STATE_PSEUDOS`) and
    the two spellings are asserted to agree, exactly as the upstream bundle
    build does;
  * the fixtures are real snapshot documents built from that same column list,
    so they parse with the pinned engine rather than being hand-waved JSON.

Usage:
  make_contract_fixtures.py --upstream <pinned-source-dir> --out <contract-dir> \
      [--engine-version 0.1.17] [--upstream-commit <sha>] [--contract-version 1]

The script only writes inside --out. It never touches the upstream tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

CONTRACT_NAME = "floe.impeccable.snapshot"

# A fixture identity must still satisfy the frozen schema, which binds the
# exact producer script bytes. The real digest is the sha256 of the fixed
# native measurement script; this placeholder is a clearly synthetic fixture
# value and is never accepted as a real capture.
FIXTURE_SCRIPT_DIGEST = "0" * 64

# --------------------------------------------------------------------------
# pinned-source parsing
# --------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rust_string_list(text: str, const_name: str) -> list[str]:
    """Parse `pub const NAME: &[&str] = &[ "a", "b", ];`."""
    m = re.search(
        r"pub\s+const\s+" + re.escape(const_name) + r"\s*:\s*&\[&str\]\s*=\s*&\[(?P<body>.*?)\];",
        text,
        re.DOTALL,
    )
    if not m:
        raise SystemExit(f"could not find Rust const {const_name}")
    body = m.group("body")
    # Drop comments so a trailing note cannot inject a value.
    body = re.sub(r"//[^\n]*", "", body)
    return re.findall(r'"((?:[^"\\]|\\.)*)"', body)


def _js_string_list(text: str, const_name: str) -> list[str]:
    """Parse `const NAME = [ "a", "b", ];`."""
    m = re.search(
        r"const\s+" + re.escape(const_name) + r"\s*=\s*\[(?P<body>.*?)\];",
        text,
        re.DOTALL,
    )
    if not m:
        raise SystemExit(f"could not find JS const {const_name}")
    body = re.sub(r"//[^\n]*", "", m.group("body"))
    return re.findall(r'"((?:[^"\\]|\\.)*)"', body)


def _js_int_const(text: str, name: str) -> int:
    m = re.search(r"const\s+" + re.escape(name) + r"\s*=\s*([^;]+);", text)
    if not m:
        raise SystemExit(f"could not find JS const {name}")
    return int(eval(m.group(1).strip(), {"__builtins__": {}}, {}))


def load_upstream_lists(upstream: Path) -> dict:
    rust_path = upstream / "crates/foundation/src/browser/snapshot.rs"
    js_path = upstream / "browser-bundle/15-snapshot.js"
    for p in (rust_path, js_path):
        if not p.is_file():
            raise SystemExit(f"missing pinned source file: {p}")
    rust = rust_path.read_text(encoding="utf-8")
    js = js_path.read_text(encoding="utf-8")

    style_props = _rust_string_list(rust, "STYLE_PROPS")
    pseudo_props = _rust_string_list(rust, "PSEUDO_PROPS")
    js_style = _js_string_list(js, "__SNAP_STYLE_PROPS")
    js_pseudo = _js_string_list(js, "__SNAP_PSEUDO_PROPS")
    state_pseudos = _js_string_list(js, "__SNAP_STATE_PSEUDOS")

    if style_props != js_style:
        raise SystemExit(
            "STYLE_PROPS disagreement between the pinned Rust core and the JS "
            f"producer ({len(style_props)} vs {len(js_style)} entries); refusing "
            "to publish a contract the two sides do not share"
        )
    if pseudo_props != js_pseudo:
        raise SystemExit(
            "PSEUDO_PROPS disagreement between the pinned Rust core and the JS "
            f"producer ({len(pseudo_props)} vs {len(js_pseudo)} entries)"
        )

    engine_version = (upstream / "ENGINE_VERSION").read_text(encoding="utf-8").strip()
    return {
        "styleProps": style_props,
        "pseudoProps": pseudo_props,
        "statePseudos": state_pseudos,
        "maxElements": _js_int_const(js, "__SNAP_DEFAULT_MAX_ELEMENTS"),
        "maxBytes": _js_int_const(js, "__SNAP_DEFAULT_MAX_BYTES"),
        "engineVersion": engine_version,
        "sources": {
            "crates/foundation/src/browser/snapshot.rs": _sha256(rust_path),
            "browser-bundle/15-snapshot.js": _sha256(js_path),
            "ENGINE_VERSION": _sha256(upstream / "ENGINE_VERSION"),
        },
        "namespaces": {
            "http://www.w3.org/1999/xhtml": 0,
            "http://www.w3.org/1999/xhtml ": 0,
        },
    }


# --------------------------------------------------------------------------
# fixture page construction
# --------------------------------------------------------------------------

# Realistic computed-style defaults for a plain block element in a light-mode
# page. The columns the rules actually read are set explicitly; the long tail
# keeps the empty string a real capture would intern for a property with no
# used value. Values are Chrome/WebKit `getComputedStyle` spellings.
STYLE_DEFAULTS: dict[str, str] = {
    "display": "block",
    "position": "static",
    "visibility": "visible",
    "opacity": "1",
    "color": "rgb(17, 24, 39)",
    "backgroundColor": "rgba(0, 0, 0, 0)",
    "backgroundImage": "none",
    "background": "rgba(0, 0, 0, 0) none repeat scroll 0% 0% / auto padding-box border-box",
    "backgroundClip": "border-box",
    "backgroundPosition": "0% 0%",
    "backgroundRepeat": "repeat",
    "backgroundSize": "auto",
    "fontSize": "16px",
    "fontFamily": 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
    "fontWeight": "400",
    "fontStyle": "normal",
    "fontVariant": "normal",
    "fontVariantCaps": "normal",
    "fontStretch": "normal",
    "fontFeatureSettings": "normal",
    "lineHeight": "24px",
    "letterSpacing": "normal",
    "wordSpacing": "0px",
    "textAlign": "start",
    "textTransform": "none",
    "textDecoration": "none solid rgb(17, 24, 39)",
    "textDecorationLine": "none",
    "textIndent": "0px",
    "textOverflow": "clip",
    "textShadow": "none",
    "textWrap": "wrap",
    "textWrapStyle": "auto",
    "whiteSpace": "normal",
    "wordBreak": "normal",
    "hyphens": "manual",
    "unicodeBidi": "normal",
    "direction": "ltr",
    "writingMode": "horizontal-tb",
    "width": "auto",
    "height": "auto",
    "minWidth": "0px",
    "minHeight": "0px",
    "maxWidth": "none",
    "maxHeight": "none",
    "blockSize": "auto",
    "inlineSize": "auto",
    "aspectRatio": "auto",
    "marginTop": "0px",
    "marginRight": "0px",
    "marginBottom": "0px",
    "marginLeft": "0px",
    "paddingTop": "0px",
    "paddingRight": "0px",
    "paddingBottom": "0px",
    "paddingLeft": "0px",
    "borderTopWidth": "0px",
    "borderRightWidth": "0px",
    "borderBottomWidth": "0px",
    "borderLeftWidth": "0px",
    "borderTopStyle": "none",
    "borderRightStyle": "none",
    "borderBottomStyle": "none",
    "borderLeftStyle": "none",
    "borderTopColor": "rgb(17, 24, 39)",
    "borderRightColor": "rgb(17, 24, 39)",
    "borderBottomColor": "rgb(17, 24, 39)",
    "borderLeftColor": "rgb(17, 24, 39)",
    "borderRadius": "0px",
    "boxShadow": "none",
    "outline": "rgb(17, 24, 39) none 0px",
    "outlineColor": "rgb(17, 24, 39)",
    "outlineStyle": "none",
    "outlineWidth": "0px",
    "outlineOffset": "0px",
    "overflow": "visible",
    "overflowX": "visible",
    "overflowY": "visible",
    "overflowClipMargin": "0px",
    "transform": "none",
    "translate": "none",
    "rotate": "none",
    "scale": "none",
    "transitionProperty": "all",
    "transitionDuration": "0s",
    "transitionTimingFunction": "ease",
    "animationName": "none",
    "animationDuration": "0s",
    "animationDelay": "0s",
    "animationDirection": "normal",
    "animationFillMode": "none",
    "animationIterationCount": "1",
    "animationPlayState": "running",
    "animationTimingFunction": "ease",
    "animationComposition": "replace",
    "animationTimeline": "auto",
    "zIndex": "auto",
    "isolation": "auto",
    "mixBlendMode": "normal",
    "filter": "none",
    "backdropFilter": "none",
    "clip": "auto",
    "clipPath": "none",
    "clip-path": "none",
    "maskImage": "none",
    "contentVisibility": "visible",
    "contain": "none",
    "cssFloat": "none",
    "float": "none",
    "clear": "none",
    "flexWrap": "nowrap",
    "order": "0",
    "cursor": "auto",
    "pointerEvents": "auto",
    "verticalAlign": "baseline",
    "content": "none",
    "colorScheme": "normal",
    "willChange": "auto",
    "backfaceVisibility": "visible",
    "objectFit": "fill",
    "objectPosition": "50% 50%",
    "top": "auto",
    "right": "auto",
    "bottom": "auto",
    "left": "auto",
    "inset": "auto",
    "insetBlock": "auto",
    "insetBlockEnd": "auto",
    "insetBlockStart": "auto",
    "insetInline": "auto",
    "insetInlineEnd": "auto",
    "insetInlineStart": "auto",
    "webkitBackgroundClip": "border-box",
    "webkitClipPath": "none",
    "webkitHyphens": "manual",
    "webkitLineClamp": "none",
    "webkitMaskImage": "none",
    "webkitTextFillColor": "rgb(17, 24, 39)",
    "webkitTextStrokeColor": "rgb(17, 24, 39)",
    "webkitTextStrokeWidth": "0px",
}

PSEUDO_DEFAULTS: dict[str, str] = {
    "content": "none",
    "position": "static",
    "opacity": "1",
    "display": "block",
    "width": "auto",
    "height": "auto",
    "top": "auto",
    "right": "auto",
    "bottom": "auto",
    "left": "auto",
    "backgroundColor": "rgba(0, 0, 0, 0)",
    "backgroundImage": "none",
    "background": "rgba(0, 0, 0, 0) none repeat scroll 0% 0% / auto padding-box border-box",
    "borderRadius": "0px",
    "transform": "none",
    "visibility": "visible",
    "zIndex": "auto",
    "translate": "none",
    "scale": "none",
    "rotate": "none",
    "filter": "none",
    "fontSize": "16px",
    "maskImage": "none",
}


class SnapshotBuilder:
    """Builds a v1 snapshot document from a small element table."""

    def __init__(self, lists: dict, *, hostname: str, inner_width: float, inner_height: float,
                 scroll_x: float = 0.0, scroll_y: float = 0.0, quirks: bool = False,
                 text_lines: bool = True, animations_recorded: bool = True,
                 shadow_trees_recorded: bool = True, linked_css: str = ""):
        self.lists = lists
        self.strings: list[str] = []
        self.index: dict[str, int] = {}
        self.els: list[dict] = []
        self.hostname = hostname
        self.inner_width = inner_width
        self.inner_height = inner_height
        self.scroll_x = scroll_x
        self.scroll_y = scroll_y
        self.quirks = quirks
        self.text_lines = text_lines
        self.animations_recorded = animations_recorded
        self.shadow_trees_recorded = shadow_trees_recorded
        self.linked_css = linked_css
        self.html_text = ""
        self.body_inner_text: str | None = None
        self.hits: list[dict] = []

    def intern(self, value: str) -> int:
        if value is None:
            value = ""
        value = str(value)
        i = self.index.get(value)
        if i is None:
            i = len(self.strings)
            self.strings.append(value)
            self.index[value] = i
        return i

    def _style_column(self, overrides: dict[str, str]) -> list[int]:
        values = []
        for prop in self.lists["styleProps"]:
            values.append(overrides.get(prop, STYLE_DEFAULTS.get(prop, "")))
        return [self.intern(v) for v in values]

    def _pseudo_column(self, overrides: dict[str, str] | None) -> list[int] | None:
        if overrides is None:
            return None
        values = [overrides.get(p, PSEUDO_DEFAULTS.get(p, "")) for p in self.lists["pseudoProps"]]
        return [self.intern(v) for v in values]

    def add(self, *, tag: str, style: dict[str, str] | None = None, attrs: list[tuple[str, str]] | None = None,
            children_text: list[object] | None = None, rect: list[float] | None = None,
            metrics: list[float | None] | None = None, visibility: int = 1,
            direct_text_rect: list[float] | None = None, text_rects: list[list[float]] | None = None,
            last_word_rects: list[list[float]] | None = None, states: list[str] | None = None,
            before: dict[str, str] | None = None, after: dict[str, str] | None = None,
            placeholder_color: str | None = None, media: dict | None = None,
            animations: list[str] | None = None, content_editable: bool = False,
            hidden: bool = False, parent: int | None = None) -> int:
        rec: dict = {"t": tag}
        if parent:
            rec["p"] = parent
        child_nodes: list = []
        for child in children_text or []:
            child_nodes.append(child)
        if child_nodes:
            rec["c"] = child_nodes
        if attrs:
            rec["a"] = [[k, v] for k, v in attrs]
        rec["s"] = self._style_column(style or {})
        before_col = self._pseudo_column(before)
        if before_col is not None:
            rec["b"] = before_col
        after_col = self._pseudo_column(after)
        if after_col is not None:
            rec["f"] = after_col
        if placeholder_color is not None:
            rec["ph"] = self.intern(placeholder_color)
        if rect is not None:
            rec["r"] = rect
        rec["m"] = metrics if metrics is not None else [0, 0, 0, 0, 0, 0, 0, 0]
        rec["v"] = visibility
        if direct_text_rect is not None:
            rec["d"] = direct_text_rect
        if text_rects:
            rec["dl"] = text_rects
        if last_word_rects:
            rec["lw"] = last_word_rects
        if content_editable:
            rec["e"] = True
        if hidden:
            rec["h"] = True
        if states:
            rec["st"] = states
        if media is not None:
            rec["md"] = media
        if animations:
            rec["an"] = animations
        self.els.append(rec)
        return len(self.els)  # element id = index + 1

    def document(self, *, document_element: int, body: int, keyframes: list | None = None,
                 keyframe_keys: list | None = None) -> dict:
        snap = {
            "v": 1,
            "textLines": self.text_lines,
            "hostname": self.hostname,
            "quirks": self.quirks,
            "innerWidth": self.inner_width,
            "innerHeight": self.inner_height,
            "scrollX": self.scroll_x,
            "scrollY": self.scroll_y,
            "html": self.html_text,
            "keyframes": keyframes or [],
            "keyframeKeys": keyframe_keys or [],
            "linkedCss": self.linked_css,
            "styleProps": self.lists["styleProps"],
            "pseudoProps": self.lists["pseudoProps"],
            "strings": self.strings,
            "els": self.els,
            "documentElement": document_element,
            "body": body,
            "bodyInnerText": self.body_inner_text,
            "hits": self.hits,
        }
        if self.animations_recorded:
            snap["anim"] = True
        if self.shadow_trees_recorded:
            snap["shadow"] = True
        return snap


def _metrics(rect: list[float], *, scroll_width: float | None = None,
             scroll_height: float | None = None) -> list[float | None]:
    """[clientWidth, clientHeight, clientLeft, scrollWidth, scrollLeft,
    offsetWidth, offsetHeight, scrollHeight]"""
    w = rect[2] if rect else 0.0
    h = rect[3] if rect else 0.0
    return [
        w, h, 0.0,
        scroll_width if scroll_width is not None else w,
        0.0,
        w, h,
        scroll_height if scroll_height is not None else h,
    ]


def build_positive_fixture(lists: dict) -> dict:
    """A small light-mode page with one measured paragraph of running text.

    Nothing overlaps it and every hit-test-free rule can answer from the
    capture, so the run completes in one round. It carries a deliberately
    small body font size so the core rule pass has something real to report.
    """
    b = SnapshotBuilder(
        lists,
        hostname="fixture.local",
        inner_width=1280.0,
        inner_height=800.0,
        linked_css="",
    )
    html = b.add(tag="HTML", rect=[0.0, 0.0, 1280.0, 800.0], metrics=_metrics([0, 0, 1280, 800], scroll_height=800))
    head = b.add(tag="HEAD", parent=html, rect=[0.0, 0.0, 0.0, 0.0], visibility=1)
    title = b.add(tag="TITLE", parent=head, children_text=["Floe fixture page"],
                  rect=[0.0, 0.0, 0.0, 0.0])
    b.els[html - 1]["c"] = [head, 3]
    b.els[head - 1]["c"] = [title]
    body_rect = [0.0, 0.0, 1280.0, 800.0]
    body = b.add(tag="BODY", parent=html, rect=body_rect, metrics=_metrics(body_rect, scroll_height=800),
                 style={"marginTop": "0px", "marginBottom": "0px"})
    b.els[html - 1]["c"] = [head, body]
    heading_rect = [24.0, 24.0, 1232.0, 40.0]
    heading = b.add(tag="H1", parent=body, children_text=["Floe fixture heading"],
                    rect=heading_rect, metrics=_metrics(heading_rect),
                    direct_text_rect=heading_rect, text_rects=[heading_rect],
                    style={"fontSize": "32px", "lineHeight": "40px", "fontWeight": "700"})
    para_rect = [24.0, 88.0, 720.0, 48.0]
    line1 = [24.0, 88.0, 700.0, 24.0]
    line2 = [24.0, 112.0, 430.0, 24.0]
    para = b.add(tag="P", parent=body,
                 children_text=["Body copy that the rule pass measures line by line."],
                 rect=para_rect, metrics=_metrics(para_rect),
                 direct_text_rect=para_rect, text_rects=[line1, line2],
                 last_word_rects=[[394.0, 112.0, 60.0, 24.0], [454.0, 112.0, 0.0, 24.0]],
                 style={"fontSize": "9px", "lineHeight": "12px", "color": "rgb(17, 24, 39)"})
    b.els[body - 1]["c"] = [heading, para]
    b.html_text = (
        "<html><head><title>Floe fixture page</title></head><body>"
        "<h1>Floe fixture heading</h1>"
        "<p>Body copy that the rule pass measures line by line.</p>"
        "</body></html>"
    )
    b.body_inner_text = "Floe fixture heading\nBody copy that the rule pass measures line by line."
    return b.document(document_element=html, body=body)


def build_needs_fixture(lists: dict) -> dict:
    """The same page with an opaque overlay covering the paragraph.

    `text-occlusion` decides from `elementFromPoint` / `elementsFromPoint` at a
    grid of points over the text run, and a snapshot cannot answer those up
    front, so the first run must come back as Needs rather than as findings.
    """
    b = SnapshotBuilder(
        lists,
        hostname="fixture.local",
        inner_width=1280.0,
        inner_height=800.0,
    )
    html = b.add(tag="HTML", rect=[0.0, 0.0, 1280.0, 800.0], metrics=_metrics([0, 0, 1280, 800], scroll_height=800))
    head = b.add(tag="HEAD", parent=html, rect=[0.0, 0.0, 0.0, 0.0])
    title = b.add(tag="TITLE", parent=head, children_text=["Floe fixture page"], rect=[0.0, 0.0, 0.0, 0.0])
    b.els[head - 1]["c"] = [title]
    body_rect = [0.0, 0.0, 1280.0, 800.0]
    body = b.add(tag="BODY", parent=html, rect=body_rect, metrics=_metrics(body_rect, scroll_height=800))
    heading_rect = [24.0, 24.0, 1232.0, 40.0]
    heading = b.add(tag="H1", parent=body, children_text=["Floe fixture heading"],
                    rect=heading_rect, metrics=_metrics(heading_rect),
                    direct_text_rect=heading_rect, text_rects=[heading_rect],
                    style={"fontSize": "32px", "lineHeight": "40px", "fontWeight": "700"})
    para_rect = [24.0, 88.0, 720.0, 48.0]
    line1 = [24.0, 88.0, 700.0, 24.0]
    line2 = [24.0, 112.0, 430.0, 24.0]
    para = b.add(tag="P", parent=body,
                 children_text=["Body copy that an overlay covers, so the run must ask for hit tests."],
                 rect=para_rect, metrics=_metrics(para_rect),
                 direct_text_rect=para_rect, text_rects=[line1, line2],
                 style={"fontSize": "16px", "lineHeight": "24px"})
    overlay_rect = [24.0, 88.0, 720.0, 48.0]
    overlay = b.add(tag="DIV", parent=body, attrs=[["class", "fixture-overlay"]],
                    rect=overlay_rect, metrics=_metrics(overlay_rect),
                    style={
                        "position": "absolute",
                        "top": "88px",
                        "left": "24px",
                        "width": "720px",
                        "height": "48px",
                        "backgroundColor": "rgb(255, 255, 255)",
                        "zIndex": "5",
                    })
    b.els[body - 1]["c"] = [heading, para, overlay]
    b.els[html - 1]["c"] = [head, body]
    b.html_text = (
        "<html><head><title>Floe fixture page</title></head><body>"
        "<h1>Floe fixture heading</h1>"
        "<p>Body copy that an overlay covers, so the run must ask for hit tests.</p>"
        '<div class="fixture-overlay"></div>'
        "</body></html>"
    )
    b.body_inner_text = "Floe fixture heading\nBody copy that an overlay covers, so the run must ask for hit tests."
    return b.document(document_element=html, body=body)


# --------------------------------------------------------------------------
# coverage pass registry
# --------------------------------------------------------------------------


def coverage_passes() -> list[dict]:
    """Every pass a v1 result must account for.

    `requiredForCleanVerdict` passes decide whether an empty finding list may
    be reported as clean. A pass Floe has not implemented is `uncovered` and
    keeps the verdict `inconclusive`; it never turns into a silent pass.
    """
    return [
        {
            "id": "core-rule-pass",
            "title": "Snapshot rule pass (impeccable-core over SnapshotDom)",
            "implemented": True,
            "requiredForCleanVerdict": True,
            "states": ["covered", "needs-facts", "failed"],
        },
        {
            "id": "hit-test-fixpoint",
            "title": "elementFromPoint/elementsFromPoint answers for rule-decided points",
            "implemented": True,
            "requiredForCleanVerdict": True,
            "states": ["covered", "needs-facts", "unanswered", "failed"],
            "notes": "Answered by the native producer on the same document identity; exact f64 bits must round-trip.",
        },
        {
            "id": "style-parity",
            "title": "Computed-style property parity (unknown_style_props)",
            "implemented": True,
            "requiredForCleanVerdict": True,
            "states": ["complete", "partial"],
            "notes": "A property the rules read but the capture did not record makes the run partial, never clean.",
        },
        {
            "id": "scroll-probes",
            "title": "shown_when_scrolled_to answers (content hidden at rest)",
            "implemented": True,
            "requiredForCleanVerdict": True,
            "states": ["covered", "needs-facts", "unanswered", "not-asked"],
            "notes": "Unanswered probes count as hidden upstream; Floe reports them as unanswered instead of clean.",
        },
        {
            "id": "static-html-source-scan",
            "title": "Static markup/source scan (impeccable-html + impeccable-detect)",
            "implemented": True,
            "requiredForCleanVerdict": False,
            "states": ["covered", "not-run", "failed"],
            "notes": "Separate verb; a snapshot scan never claims it ran.",
        },
        {
            "id": "pixel-contrast",
            "title": "Pixel-sampled contrast and routed low-contrast verdicts",
            "implemented": False,
            "requiredForCleanVerdict": True,
            "states": ["uncovered"],
            "reason": "Needs loadImage/readPixel or the PNG two-shot diff of the upstream URL engine; the v1 native capture has no pixel source.",
        },
        {
            "id": "screenshot-diff",
            "title": "Two-shot screenshot hiding/diff evidence",
            "implemented": False,
            "requiredForCleanVerdict": False,
            "states": ["uncovered"],
            "reason": "URL-engine evidence pass; not part of the snapshot contract.",
        },
        {
            "id": "reveal-sweep",
            "title": "Pre-capture scroll/reveal sweep and overlay settling",
            "implemented": False,
            "requiredForCleanVerdict": True,
            "states": ["uncovered"],
            "reason": "Content revealed only by scrolling is not measured; reveal-on-scroll findings cannot be produced or excluded.",
        },
        {
            "id": "content-hidden-at-rest-measure",
            "title": "Hidden-text measurement with scroll probes (URL engine step)",
            "implemented": False,
            "requiredForCleanVerdict": True,
            "states": ["uncovered"],
            "reason": "The URL engine's hidden-text step is not ported; scroll-probe needs are surfaced but never answered by Floe v1.",
        },
        {
            "id": "consent-overlay-hiding",
            "title": "Consent banner / page overlay hiding before capture",
            "implemented": False,
            "requiredForCleanVerdict": False,
            "states": ["uncovered"],
            "reason": "Requires live page mutation; Floe keeps the page untouched.",
        },
        {
            "id": "script-errors",
            "title": "Console/script error capture",
            "implemented": False,
            "requiredForCleanVerdict": True,
            "states": ["uncovered"],
            "reason": "Needs a console channel; not part of the fixed measurement contract.",
        },
        {
            "id": "cross-origin-iframe",
            "title": "Cross-origin frame content",
            "implemented": False,
            "requiredForCleanVerdict": True,
            "states": ["uncovered"],
            "reason": "SnapshotDom carries no frame content and WebKit isolation forbids cross-origin reads.",
        },
        {
            "id": "same-origin-iframe",
            "title": "Same-origin frame content",
            "implemented": False,
            "requiredForCleanVerdict": True,
            "states": ["uncovered"],
            "reason": "The upstream capture producer never traverses iframes; rules inside frames are lost, not passed.",
        },
        {
            "id": "media-intrinsics",
            "title": "Image/video natural size and load state",
            "implemented": True,
            "requiredForCleanVerdict": False,
            "states": ["covered", "unrecorded"],
            "notes": "Carried per element as `md`; visual verdicts still need the uncovered pixel pass.",
        },
        {
            "id": "animations",
            "title": "Running animation/transition properties",
            "implemented": True,
            "requiredForCleanVerdict": False,
            "states": ["covered", "unrecorded"],
            "notes": "Driven by the snapshot `anim` flag.",
        },
        {
            "id": "shadow-trees",
            "title": "Open shadow tree flat walk",
            "implemented": True,
            "requiredForCleanVerdict": False,
            "states": ["covered", "unrecorded"],
            "notes": "Driven by the snapshot `shadow` flag.",
        },
        {
            "id": "text-lines",
            "title": "Per-line rendered text rects",
            "implemented": True,
            "requiredForCleanVerdict": True,
            "states": ["covered", "unrecorded"],
            "notes": "Without `textLines` the line-level rules stand down; that is a coverage loss, not a pass.",
        },
        {
            "id": "keyframes-and-linked-css",
            "title": "@keyframes rules and readable linked stylesheet corpus",
            "implemented": True,
            "requiredForCleanVerdict": False,
            "states": ["covered", "partial", "unrecorded"],
        },
    ]


# --------------------------------------------------------------------------
# contract document
# --------------------------------------------------------------------------


def contract_document(lists: dict, args) -> dict:
    engine_version = args.engine_version or lists["engineVersion"]
    return {
        "contract": CONTRACT_NAME,
        "contractVersion": args.contract_version,
        "schemaStatus": "frozen-v1",
        "schemaStatusNote": (
            "The wire schema, protocol fields, binding/fencing rules, error semantics and fixture set are "
            "frozen at v1: native (A2) may implement against them now. What is still pending is the engine "
            "side, not the contract."
        ),
        "engineValidation": {
            "status": "pending",
            "reason": (
                "Golden outputs under contract/expected/ are produced by the built engine (host arm64 and "
                "riscv64) in this same lane; until then the fixtures are schema-validated inputs, not "
                "engine-observed results."
            ),
            "blocksNativeImplementation": False,
        },
        "engine": {
            "binary": "floe-impeccable",
            "upstreamProject": "pbakaus/impeccable",
            "upstreamEngineVersion": engine_version,
            "upstreamCommit": args.upstream_commit,
            "upstreamTree": args.upstream_tree,
            "pinAuthority": "floe-skill-hub docs/UPSTREAM-PINS.json (reviewBaselineDate 2026-10-26)",
            "floeAdapterVersion": args.adapter_version,
            "engineId": f"impeccable-{engine_version}+floe.{args.adapter_version}",
            "targetTriple": "riscv64gc-unknown-linux-musl",
            "abi": "static ELF, no dynamic loader dependency",
        },
        "transport": {
            "kind": "file",
            "encoding": "utf-8 JSON",
            "direction": "native producer -> task-owned file bridge -> engine -> result file",
            "network": "none; the engine never fetches",
            "evaluate": "none; the engine never asks for arbitrary JavaScript",
            "cdp": "none; no DevTools protocol endpoint is opened or emulated",
        },
        "snapshot": {
            "version": 1,
            "producer": "fixed, audited native WebKit measurement in an isolated content world",
            "maxElements": lists["maxElements"],
            "maxBytes": lists["maxBytes"],
            "floeMaxBytes": args.max_snapshot_bytes,
            "styleProps": lists["styleProps"],
            "pseudoProps": lists["pseudoProps"],
            "statePseudos": lists["statePseudos"],
            "elementIdRule": "document-order index + 1; open shadow trees are appended after every light-DOM element so light ids never move",
            "hitTestKey": "exact IEEE-754 double bits of (x, y); decimal text must round-trip",
        },
        "verbs": [
            {
                "name": "engine-probe",
                "purpose": "launcher handshake",
                "stdout": f"impeccable-engine {engine_version}+floe.{args.adapter_version}\n",
                "exit": 0,
            },
            {
                "name": "contract",
                "purpose": "print this machine-readable contract",
                "stdout": "contract JSON",
                "exit": 0,
            },
            {
                "name": "snapshot-schema",
                "purpose": "print the producer-facing capture contract (property columns, limits, shapes)",
                "stdout": "schema JSON",
                "exit": 0,
            },
            {
                "name": "snapshot-scan",
                "purpose": "run the rule pass over a snapshot and answer needs from supplied facts",
                "args": [
                    "--snapshot <path> (required)",
                    "--facts <path> (repeatable; pre-answered hit tests / scroll probes)",
                    "--config <path> (BrowserConfig JSON; optional)",
                    "--identity <path> (required in strict mode; document/session/viewport binding)",
                    "--out <path> (result document; stdout when omitted)",
                    "--max-rounds <n> (default 4)",
                    "--max-hit-tests <n> (default 4096 per round, 16384 total)",
                    "--max-snapshot-bytes <n> (default 48 MiB, hard floor 1 MiB)",
                    "--timeout-ms <n> (default 120000; cancellation leaves an explicit failed result)",
                    "--strict-schema (reject unknown snapshot fields; default on for v1)",
                ],
                "exit": {
                    "0": "complete and clean (verdict clean)",
                    "2": "complete with findings",
                    "3": "incomplete: needs facts (never a clean result)",
                    "4": "ran but coverage incomplete: verdict inconclusive",
                    "1": "usage error, invalid input, identity mismatch, budget exceeded or cancelled",
                },
            },
            {
                "name": "detect",
                "purpose": "upstream static source/markup scan passthrough",
                "exit": "upstream semantics: 0 clean, 2 findings, 1 operational failure",
            },
            {
                "name": "context",
                "purpose": "upstream project context brief passthrough (offline)",
                "exit": "upstream semantics",
            },
            {
                "name": "ignores",
                "purpose": "upstream ignore management passthrough",
                "exit": "upstream semantics",
            },
        ],
        "excludedUpstreamPaths": [
            {"path": "skills install/update/check/link", "owner": "Floe Skill Hub", "reason": "installation and updates are Hub-owned and digest-bound; the engine never downloads"},
            {"path": "telemetry", "owner": "Floe", "reason": "no upstream telemetry endpoint from a Floe guest"},
            {"path": "generate-image / concept-seed / serve-question", "owner": "Floe", "reason": "network or local-server verbs outside v1"},
            {"path": "live* / hook*", "owner": "Floe", "reason": "live rewrite server and editor hooks are not part of the Floe v1 flow"},
            {"path": "capture-server / component-review / font-match / build-phase", "owner": "Floe", "reason": "Chromium/CDP capture; forbidden by the integration contract"},
            {"path": "URL scan (--cdp, http targets)", "owner": "Floe", "reason": "no Chromium dependency for a native page scan"},
        ],
        "needs": {
            "shape": {"hitTests": [[0.0, 0.0]]},
            "extra": {
                "hitTestsBits": [["<u64 x bits>", "<u64 y bits>"]],
                "scrollProbes": ["<elementId>"],
            },
            "semantics": "Needs is a real answer, not an error and never a clean scan. Points must be answered on the same document identity, then the scan re-run.",
        },
        "facts": {
            "shape": {
                "hits": [{"x": 0.0, "y": 0.0, "top": 0, "stack": [0]}],
                "shownOnScroll": [{"el": 0, "shown": False}],
            },
            "floeExtensions": {
                "captureId": "must equal the identity the needs were issued for",
                "documentId": "must equal the snapshot's document identity",
                "xBits": "optional u64 verification of x",
                "yBits": "optional u64 verification of y",
            },
            "rules": [
                "top is the snapshot element id of document.elementFromPoint(x, y), 0 when nothing",
                "stack is document.elementsFromPoint(x, y) mapped to snapshot ids, front to back, zeros dropped",
                "an unanswerable point must be reported as top 0 with an empty stack, and the run then reports it as unanswered rather than clean",
                "facts for a superseded captureId/documentId are rejected",
            ],
        },
        "identity": {
            "requiredFields": [
                "taskId", "sessionId", "tabId", "documentId", "captureId", "documentGeneration",
                "url", "hostname", "viewport.width", "viewport.height", "scroll.x", "scroll.y",
                "capturedAtMs", "producerTrust", "producer.name", "producer.version",
                "producer.engine", "producer.scriptDigest",
                "redaction.policy", "redaction.applied", "redaction.passwordInputs",
                "redaction.formValues", "redaction.credentialAttributes", "redaction.textRuns",
            ],
            "shape": {
                "taskId": "string, the Floe task/conversation that owns this capture",
                "sessionId": "string, native browser session",
                "tabId": "string, native browser tab/page",
                "documentId": "string, stable for the document the snapshot measured",
                "captureId": "string, unique per capture",
                "documentGeneration": "integer, monotonic per tab; bumps on navigation, reload or a document swap",
                "url": "string, the document URL at capture",
                "hostname": "string, must equal snapshot.hostname",
                "viewport": {"width": 0.0, "height": 0.0},
                "scroll": {"x": 0.0, "y": 0.0},
                "capturedAtMs": 0,
                "producerTrust": "native-fixed-script",
                "producer": {
                    "name": "string", "version": "string", "engine": "WebKit",
                    "scriptDigest": "sha256 of the exact fixed measurement script bytes",
                },
                "redaction": {
                    "policy": "floe.impeccable.redaction.v1",
                    "applied": True,
                    "passwordInputs": 0,
                    "formValues": 0,
                    "credentialAttributes": [],
                    "textRuns": 0,
                },
            },
            "bindingRules": [
                "the snapshot, every needs document and every facts document carry the same taskId/sessionId/tabId/documentId/captureId",
                "hostname, viewport and scroll in the identity must equal the snapshot's own values",
                "a facts file whose binding differs from the loaded snapshot is rejected, not merged",
            ],
            "fencing": [
                "navigation, reload, a documentGeneration bump, a viewport change or a scroll change invalidates the snapshot and every needs/facts pair issued for it",
                "the native side fences the capture at the moment of navigation or view change; a late answer for a fenced capture must be refused",
                "the engine reports identityCheck.state as verified | absent | mismatch | superseded and never treats a mismatch as a scan result",
            ],
            "privacy": [
                "the producer is a fixed, audited native script; no arbitrary or model-authored JavaScript and no model-declared trust",
                "producer.scriptDigest binds the exact script bytes that ran",
                "password input values, form control values and credential-bearing attributes are redacted before the snapshot leaves the device",
                "a snapshot whose identity does not claim an applied redaction policy is rejected in strict mode",
            ],
        },
        "budgets": {
            "maxSnapshotBytes": args.max_snapshot_bytes,
            "maxElements": lists["maxElements"],
            "maxRounds": args.max_rounds,
            "maxHitTestsPerRound": args.max_hit_tests_per_round,
            "maxHitTestsTotal": args.max_hit_tests_total,
            "timeoutMs": args.timeout_ms,
            "onExceeded": "fail closed: status failed, explicit reason, no findings presented as a scan result",
        },
        "result": {
            "topLevelKeys": [
                "contract", "contractVersion", "status", "verdict", "engine", "identity",
                "budget", "coverage", "needs", "findings", "diagnostics",
            ],
            "status": ["complete", "needs-facts", "inconclusive", "failed"],
            "verdict": ["clean", "findings", "inconclusive", "none"],
            "cleanVerdictRequires": [
                "status == complete",
                "needs empty (no hit tests, no scroll probes)",
                "every pass with requiredForCleanVerdict == true is covered/complete",
                "style-parity complete (no unknown style properties)",
                "identity verified and not superseded",
                "no budget exceeded and no cancellation",
            ],
        },
        "coveragePasses": coverage_passes(),
        "fixtures": {
            "positive": "fixtures/snapshot-positive.v1.json",
            "needs": "fixtures/snapshot-needs-hit-tests.v1.json",
            "factsTemplate": "fixtures/facts-hit-tests.v1.json",
            "scrollFacts": "fixtures/facts-shown-on-scroll.v1.json",
            "config": "fixtures/config-default.v1.json",
            "identity": "fixtures/identity-positive.v1.json",
            "invalid": [
                "fixtures/invalid/snapshot-truncated.v1.json",
                "fixtures/invalid/snapshot-bad-version.v1.json",
                "fixtures/invalid/snapshot-style-column-mismatch.v1.json",
                "fixtures/invalid/identity-mismatch.v1.json",
                "fixtures/invalid/identity-missing-session-binding.v1.json",
                "fixtures/invalid/identity-redaction-not-applied.v1.json",
                "fixtures/invalid/identity-model-declared-trust.v1.json",
                "fixtures/invalid/identity-fenced.v1.json",
                "fixtures/invalid/facts-bits-mismatch.v1.json",
                "fixtures/invalid/facts-stale-capture.v1.json",
                "fixtures/invalid/facts-other-tab.v1.json",
            ],
        },
        "provenance": {
            "upstreamCommit": args.upstream_commit,
            "upstreamTree": args.upstream_tree,
            "engineVersionFile": lists["engineVersion"],
            "pinnedSourceDigests": lists["sources"],
            "generatedBy": "engines/impeccable/contract/tools/make_contract_fixtures.py",
        },
    }


def producer_schema(lists: dict) -> dict:
    style_col = {
        "type": "array",
        "minItems": len(lists["styleProps"]),
        "maxItems": len(lists["styleProps"]),
        "items": {"type": "integer", "minimum": 0},
        "description": "One interned string index per styleProps column, in column order.",
    }
    rect4 = {
        "type": "array", "minItems": 4, "maxItems": 4,
        "items": {"type": "number"},
        "description": "[x, y, width, height] in CSS pixels, viewport coordinate space.",
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://floe-agent.com/schemas/impeccable/snapshot.v1.json",
        "title": "Floe Impeccable snapshot v1 (native WebKit measurement capture)",
        "type": "object",
        "required": ["v", "els", "strings", "styleProps", "documentElement", "body"],
        "properties": {
            "v": {"const": 1},
            "hostname": {"type": "string"},
            "quirks": {"type": "boolean"},
            "innerWidth": {"type": "number"},
            "innerHeight": {"type": "number"},
            "scrollX": {"type": "number"},
            "scrollY": {"type": "number"},
            "html": {"type": "string", "description": "document.documentElement.outerHTML with tool-injected nodes removed"},
            "keyframes": {"type": "array"},
            "keyframeKeys": {"type": "array"},
            "linkedCss": {"type": "string", "description": "same-origin or CORS-readable linked stylesheet text"},
            "styleProps": {"type": "array", "items": {"type": "string"}, "minItems": len(lists["styleProps"])},
            "pseudoProps": {"type": "array", "items": {"type": "string"}},
            "strings": {"type": "array", "items": {"type": "string"}},
            "els": {
                "type": "array",
                "maxItems": lists["maxElements"],
                "items": {
                    "type": "object",
                    "required": ["t", "s"],
                    "properties": {
                        "t": {"type": "string", "description": "tagName, uppercase"},
                        "n": {"type": "integer", "minimum": 0, "maximum": 3},
                        "nu": {"type": "string"},
                        "p": {"type": "integer", "minimum": 0},
                        "c": {"type": "array", "description": "childNodes: element id (number), text data (string) or CDATA ([string])"},
                        "a": {"type": "array", "items": {"type": "array", "minItems": 2, "maxItems": 2}},
                        "s": style_col,
                        "b": {"type": ["array", "null"], "items": {"type": "integer"}},
                        "f": {"type": ["array", "null"], "items": {"type": "integer"}},
                        "ph": {"type": ["integer", "null"]},
                        "r": {"type": ["array", "null"], "minItems": 4, "maxItems": 4, "items": {"type": "number"}},
                        "m": {"type": "array", "minItems": 7, "maxItems": 8, "items": {"type": ["number", "null"]}},
                        "v": {"type": "integer", "minimum": -1, "maximum": 1},
                        "d": {"type": ["array", "null"], "minItems": 4, "maxItems": 4, "items": {"type": "number"}},
                        "dl": {"type": "array", "items": rect4},
                        "lw": {"type": ["array", "null"], "minItems": 2, "maxItems": 2, "items": rect4},
                        "e": {"type": "boolean"},
                        "h": {"type": "boolean"},
                        "i": {"type": "boolean"},
                        "k": {"type": "boolean"},
                        "st": {"type": "array", "items": {"type": "string", "enum": lists["statePseudos"] + ["undefined"]}},
                        "md": {"type": ["object", "null"]},
                        "an": {"type": ["array", "null"], "items": {"type": "string"}},
                        "sh": {"type": ["integer", "null"]},
                        "as": {"type": ["integer", "null"]},
                        "ts": {"type": ["integer", "null"]},
                    },
                },
            },
            "documentElement": {"type": "integer", "minimum": 0},
            "body": {"type": ["integer", "null"], "minimum": 0},
            "bodyInnerText": {"type": ["string", "null"]},
            "textLines": {"type": "boolean"},
            "hits": {"type": "array"},
            "anim": {"type": "boolean"},
            "shadow": {"type": "boolean"},
            "floe": {
                "type": "object",
                "description": "Optional Floe binding block; ignored by the upstream parser, cross-checked by the adapter.",
                "properties": {
                    "captureId": {"type": "string"},
                    "documentId": {"type": "string"},
                    "contractVersion": {"type": "integer"},
                    "redaction": {"type": "object"},
                },
            },
        },
    }


def facts_schema(lists: dict) -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://floe-agent.com/schemas/impeccable/facts.v1.json",
        "title": "Floe Impeccable facts v1 (answers to an engine Needs)",
        "type": "object",
        "required": ["hits", "captureId", "documentId", "sessionId", "tabId", "taskId"],
        "properties": {
            "hits": {
                "type": "array",
                "maxItems": args_max_hit_tests_total(lists),
                "items": {
                    "type": "object",
                    "required": ["x", "y"],
                    "properties": {
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                        "xBits": {"type": ["integer", "string"], "description": "u64 to_bits of x; verified against the needs that asked for the point"},
                        "yBits": {"type": ["integer", "string"]},
                        "top": {"type": "integer", "minimum": 0, "description": "elementFromPoint as a snapshot id; 0 when nothing"},
                        "stack": {"type": "array", "items": {"type": "integer", "minimum": 0},
                                   "description": "elementsFromPoint as snapshot ids, front to back"},
                        "unanswerable": {"type": "boolean", "description": "the native side could not answer this point; the run must report it, not pass"},
                        "reason": {"type": "string"},
                    },
                },
            },
            "shownOnScroll": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["el", "shown"],
                    "properties": {"el": {"type": "integer", "minimum": 1}, "shown": {"type": "boolean"}},
                },
            },
            "taskId": {"type": "string", "minLength": 1},
            "sessionId": {"type": "string", "minLength": 1},
            "tabId": {"type": "string", "minLength": 1},
            "captureId": {"type": "string", "minLength": 1},
            "documentId": {"type": "string", "minLength": 1},
            "documentGeneration": {"type": "integer", "minimum": 0},
            "fenced": {"type": "boolean", "description": "the native side fenced this capture (navigation/view change); the engine must refuse it"},
        },
    }


def args_max_hit_tests_total(lists: dict) -> int:
    return 16384


def identity_schema() -> dict:
    redaction = {
        "type": "object",
        "required": ["policy", "applied", "passwordInputs", "formValues", "credentialAttributes", "textRuns"],
        "properties": {
            "policy": {"const": "floe.impeccable.redaction.v1"},
            "applied": {"const": True},
            "passwordInputs": {"type": "integer", "minimum": 0},
            "formValues": {"type": "integer", "minimum": 0},
            "credentialAttributes": {"type": "array", "items": {"type": "string"}},
            "textRuns": {"type": "integer", "minimum": 0},
        },
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://floe-agent.com/schemas/impeccable/identity.v1.json",
        "title": "Floe Impeccable capture identity v1",
        "type": "object",
        "required": [
            "taskId", "sessionId", "tabId", "documentId", "captureId", "documentGeneration",
            "url", "hostname", "viewport", "scroll", "capturedAtMs",
            "producerTrust", "producer", "redaction",
        ],
        "properties": {
            "taskId": {"type": "string", "minLength": 1},
            "captureId": {"type": "string", "minLength": 1},
            "documentId": {"type": "string", "minLength": 1},
            "documentGeneration": {"type": "integer", "minimum": 0},
            "sessionId": {"type": "string", "minLength": 1},
            "tabId": {"type": "string", "minLength": 1},
            "url": {"type": "string", "minLength": 1},
            "hostname": {"type": "string"},
            "viewport": {
                "type": "object",
                "required": ["width", "height"],
                "properties": {"width": {"type": "number"}, "height": {"type": "number"}},
            },
            "scroll": {
                "type": "object",
                "required": ["x", "y"],
                "properties": {"x": {"type": "number"}, "y": {"type": "number"}},
            },
            "capturedAtMs": {"type": "integer", "minimum": 0},
            "producerTrust": {
                "const": "native-fixed-script",
                "description": "Only a fixed, audited native producer is trusted. A model-declared or page-declared trust value is not accepted.",
            },
            "producer": {
                "type": "object",
                "required": ["name", "version", "engine", "scriptDigest"],
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "version": {"type": "string", "minLength": 1},
                    "engine": {"const": "WebKit"},
                    "scriptDigest": {
                        "type": "string",
                        "pattern": "^[0-9a-f]{64}$",
                        "description": "sha256 of the exact fixed measurement script bytes that produced this capture",
                    },
                },
            },
            "redaction": redaction,
            "fenced": {"type": "boolean"},
        },
    }


def result_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://floe-agent.com/schemas/impeccable/result.v1.json",
        "title": "Floe Impeccable scan result v1",
        "type": "object",
        "required": ["contract", "contractVersion", "status", "verdict", "engine", "coverage"],
        "properties": {
            "contract": {"const": CONTRACT_NAME},
            "contractVersion": {"type": "integer"},
            "status": {"enum": ["complete", "needs-facts", "inconclusive", "failed"]},
            "verdict": {"enum": ["clean", "findings", "inconclusive", "none"]},
            "engine": {
                "type": "object",
                "properties": {
                    "binary": {"type": "string"},
                    "upstreamEngineVersion": {"type": "string"},
                    "upstreamCommit": {"type": "string"},
                    "floeAdapterVersion": {"type": "string"},
                    "engineId": {"type": "string"},
                    "targetTriple": {"type": "string"},
                },
            },
            "identity": {"type": ["object", "null"]},
            "identityCheck": {
                "type": "object",
                "properties": {
                    "state": {"enum": ["verified", "absent", "mismatch", "superseded"]},
                    "mismatches": {"type": "array", "items": {"type": "string"}},
                },
            },
            "budget": {
                "type": "object",
                "properties": {
                    "snapshotBytes": {"type": "integer"},
                    "elements": {"type": "integer"},
                    "rounds": {"type": "integer"},
                    "hitTestsAsked": {"type": "integer"},
                    "hitTestsAnswered": {"type": "integer"},
                    "exceeded": {"type": "array", "items": {"type": "string"}},
                },
            },
            "coverage": {
                "type": "object",
                "required": ["passes", "uncoveredRequired"],
                "properties": {
                    "passes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["id", "state"],
                            "properties": {
                                "id": {"type": "string"},
                                "state": {"type": "string"},
                                "requiredForCleanVerdict": {"type": "boolean"},
                                "reason": {"type": "string"},
                                "detail": {"type": ["object", "array", "string", "null"]},
                            },
                        },
                    },
                    "uncoveredRequired": {"type": "array", "items": {"type": "string"}},
                    "unknownStyleProps": {"type": "array", "items": {"type": "string"}},
                },
            },
            "needs": {
                "type": ["object", "null"],
                "properties": {
                    "hitTests": {"type": "array", "items": {"type": "array", "minItems": 2, "maxItems": 2}},
                    "hitTestsBits": {"type": "array"},
                    "scrollProbes": {"type": "array", "items": {"type": "integer"}},
                    "round": {"type": "integer"},
                },
            },
            "findings": {
                "type": ["object", "null"],
                "properties": {
                    "groups": {"type": "array"},
                    "pageLevel": {"type": "array"},
                    "counts": {"type": "object"},
                },
            },
            "diagnostics": {"type": "object"},
            "error": {
                "type": ["object", "null"],
                "properties": {
                    "code": {"type": "string"},
                    "message": {"type": "string"},
                },
            },
        },
    }


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--engine-version", default=None)
    ap.add_argument("--upstream-commit", default="unspecified")
    ap.add_argument("--upstream-tree", default="unspecified")
    ap.add_argument("--adapter-version", default="1.0.0")
    ap.add_argument("--contract-version", type=int, default=1)
    ap.add_argument("--max-snapshot-bytes", type=int, default=48 * 1024 * 1024)
    ap.add_argument("--max-rounds", type=int, default=4)
    ap.add_argument("--max-hit-tests-per-round", type=int, default=4096)
    ap.add_argument("--max-hit-tests-total", type=int, default=16384)
    ap.add_argument("--timeout-ms", type=int, default=120000)
    args = ap.parse_args()

    lists = load_upstream_lists(args.upstream)
    out = args.out
    prod = out / "producer"
    fix = out / "fixtures"

    write_json(prod / "style-props.v1.json", {
        "contract": CONTRACT_NAME,
        "contractVersion": args.contract_version,
        "count": len(lists["styleProps"]),
        "columnOrder": "the exact order of SnapNode.s; a capture must send one interned index per column",
        "styleProps": lists["styleProps"],
        "provenance": lists["sources"],
    })
    write_json(prod / "pseudo-props.v1.json", {
        "contract": CONTRACT_NAME,
        "contractVersion": args.contract_version,
        "count": len(lists["pseudoProps"]),
        "pseudoProps": lists["pseudoProps"],
        "recordedWhen": "::before / ::after whose computed content is not none or empty",
        "provenance": lists["sources"],
    })
    write_json(prod / "state-pseudos.v1.json", {
        "contract": CONTRACT_NAME,
        "contractVersion": args.contract_version,
        "count": len(lists["statePseudos"]),
        "statePseudos": lists["statePseudos"],
        "extra": ["undefined (recorded for a custom element without a definition)"],
        "provenance": lists["sources"],
    })
    write_json(prod / "capture-limits.v1.json", {
        "contract": CONTRACT_NAME,
        "contractVersion": args.contract_version,
        "upstreamDefaults": {"maxElements": lists["maxElements"], "maxBytes": lists["maxBytes"]},
        "floeBudgets": {
            "maxSnapshotBytes": args.max_snapshot_bytes,
            "maxElements": lists["maxElements"],
            "maxRounds": args.max_rounds,
            "maxHitTestsPerRound": args.max_hit_tests_per_round,
            "maxHitTestsTotal": args.max_hit_tests_total,
            "timeoutMs": args.timeout_ms,
        },
        "namespaces": {"http://www.w3.org/1999/xhtml": 0, "http://www.w3.org/2000/svg": 1,
                        "http://www.w3.org/1998/Math/MathML": 2, "other": 3},
        "provenance": lists["sources"],
    })
    write_json(prod / "snapshot.schema.v1.json", producer_schema(lists))
    write_json(prod / "facts.schema.v1.json", facts_schema(lists))
    write_json(prod / "identity.schema.v1.json", identity_schema())
    write_json(prod / "result.schema.v1.json", result_schema())

    contract = contract_document(lists, args)
    write_json(out / "snapshot-contract.v1.json", contract)

    positive = build_positive_fixture(lists)
    needs = build_needs_fixture(lists)
    write_json(fix / "snapshot-positive.v1.json", positive)
    write_json(fix / "snapshot-needs-hit-tests.v1.json", needs)
    write_json(fix / "config-default.v1.json", {
        "extensionMode": False,
        "disabledRules": [],
        "disabledValues": [],
        "skipScan": False,
        "designSystem": None,
        "lineLengthMax": None,
        "unreportedRules": [],
    })
    identity_positive = {
        "taskId": "task-fixture-0001",
        "sessionId": "session-fixture-0001",
        "tabId": "tab-fixture-0001",
        "documentId": "doc-fixture-0001",
        "captureId": "cap-fixture-positive-0001",
        "documentGeneration": 1,
        "url": "https://fixture.local/",
        "hostname": positive["hostname"],
        "viewport": {"width": positive["innerWidth"], "height": positive["innerHeight"]},
        "scroll": {"x": positive["scrollX"], "y": positive["scrollY"]},
        "capturedAtMs": 0,
        "producerTrust": "native-fixed-script",
        "producer": {
            "name": "FloeWebkitDesignCapture",
            "version": "0.0.0-fixture",
            "engine": "WebKit",
            "scriptDigest": FIXTURE_SCRIPT_DIGEST,
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
    identity_needs = dict(
        identity_positive,
        captureId="cap-fixture-needs-0001",
        url="https://fixture.local/needs",
    )
    write_json(fix / "identity-positive.v1.json", identity_positive)
    write_json(fix / "identity-needs.v1.json", identity_needs)
    binding_needs = {
        "taskId": identity_needs["taskId"],
        "sessionId": identity_needs["sessionId"],
        "tabId": identity_needs["tabId"],
        "captureId": identity_needs["captureId"],
        "documentId": identity_needs["documentId"],
        "documentGeneration": identity_needs["documentGeneration"],
    }
    write_json(fix / "facts-hit-tests.v1.json", {
        "_note": (
            "Shape example only. The points are decided by the rules, so a real facts file must echo "
            "the exact needs points (and their bits) the engine asked for on the same binding. "
            "tools/fill_facts_from_needs.py turns an observed needs document into a valid facts file."
        ),
        **binding_needs,
        "hits": [],
        "shownOnScroll": [],
    })
    write_json(fix / "facts-shown-on-scroll.v1.json", {
        "_note": "Answers scroll probes (element ids from needs.scrollProbes). Unanswered probes are reported as unanswered, never as clean.",
        **binding_needs,
        "hits": [],
        "shownOnScroll": [{"el": 5, "shown": True}],
    })

    invalid = fix / "invalid"
    truncated = json.dumps(needs, ensure_ascii=False)
    (invalid / "snapshot-truncated.v1.json").parent.mkdir(parents=True, exist_ok=True)
    (invalid / "snapshot-truncated.v1.json").write_text(truncated[: len(truncated) // 2], encoding="utf-8")
    bad_version = json.loads(json.dumps(needs))
    bad_version["v"] = 99
    write_json(invalid / "snapshot-bad-version.v1.json", bad_version)
    column_mismatch = json.loads(json.dumps(needs))
    column_mismatch["styleProps"] = column_mismatch["styleProps"][:-3]
    write_json(invalid / "snapshot-style-column-mismatch.v1.json", column_mismatch)
    mismatch_identity = dict(identity_positive, hostname="other.example",
                             viewport={"width": 390.0, "height": 844.0})
    write_json(invalid / "identity-mismatch.v1.json", mismatch_identity)
    missing_session = {k: v for k, v in identity_positive.items() if k not in ("sessionId", "tabId")}
    write_json(invalid / "identity-missing-session-binding.v1.json", missing_session)
    no_redaction = json.loads(json.dumps(identity_positive))
    no_redaction["redaction"] = {"policy": "floe.impeccable.redaction.v1", "applied": False,
                                 "passwordInputs": 0, "formValues": 0,
                                 "credentialAttributes": [], "textRuns": 0}
    write_json(invalid / "identity-redaction-not-applied.v1.json", no_redaction)
    model_trust = dict(identity_positive, producerTrust="model-declared")
    write_json(invalid / "identity-model-declared-trust.v1.json", model_trust)
    fenced = dict(identity_positive, fenced=True, captureId="cap-fixture-fenced-0001")
    write_json(invalid / "identity-fenced.v1.json", fenced)
    write_json(invalid / "facts-bits-mismatch.v1.json", {
        **binding_needs,
        "hits": [{"x": 100.0, "y": 100.0, "xBits": 1, "yBits": 1, "top": 0, "stack": []}],
    })
    write_json(invalid / "facts-stale-capture.v1.json", {
        **dict(binding_needs, captureId="cap-superseded-0000", documentGeneration=0),
        "hits": [],
    })
    write_json(invalid / "facts-other-tab.v1.json", {
        **dict(binding_needs, tabId="tab-other-9999", sessionId="session-other-9999"),
        "hits": [],
    })

    print(json.dumps({
        "written": True,
        "engineVersion": lists["engineVersion"],
        "styleProps": len(lists["styleProps"]),
        "pseudoProps": len(lists["pseudoProps"]),
        "statePseudos": len(lists["statePseudos"]),
        "positiveElements": len(positive["els"]),
        "positiveBytes": len(json.dumps(positive)),
        "needsElements": len(needs["els"]),
        "needsBytes": len(json.dumps(needs)),
        "coveragePasses": len(contract["coveragePasses"]),
        "requiredForClean": sorted(p["id"] for p in contract["coveragePasses"] if p["requiredForCleanVerdict"]),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
