#!/usr/bin/env python3
# Floe first-party (MPL-2.0). Adaptation workflow derives from
# anthropics/skills@dbd4588 canvas-design (Apache-2.0; see references/licenses/).
"""make_poster.py — deterministic poster SVG/HTML generator for the canvas-design skill.

Runs only in the task's resolved Linux guest via exec.shell (python3 stdlib).

Input: a poster spec JSON (see references/poster-spec-format.md). Output, written
atomically into the chosen workspace-relative out directory:
  <prefix>.svg            editable vector source: text references font families
                          BY NAME; a viewer without the families substitutes, so
                          for render-portability ship the .html artifact
  <prefix>.html           self-contained renderable artifact: inline SVG plus
                           base64 @font-face for every bundled font actually used,
                           an explicit declared-size PNG export button, readable
                           font/code license disclosures, and the declared system
                           fallback stack for CJK text (device fonts, never
                           claimed as embedded)
  <prefix>.coverage.json  audit report: declared units, pixel dimensions,
                          per-element glyph coverage split into embedded /
                          fallback / unsupported, notice metadata

Guarantees checked before any byte is written:
  * canvas dimensions are declared with explicit units (px or mm at a declared dpi);
  * every element lies inside the canvas bounds, no two text boxes overlap and
    maxWidth holds. These are ADVANCE-METRIC estimates: widths sum real advance
    widths from assets/fonts/fonts.json (v2 registry, CoreText per-codepoint
    cross-checked on the exact TTF bytes); the vertical box is a nominal
    ascent/descent estimate. They are NOT ink/shaping bounds and are never
    claimed as pixel-perfect collision proofs — kerning, ligatures and real
    glyph outlines can differ, so visual QA stays required.
  * glyph coverage: text is either covered by the selected bundled font, or is
    routed to the declared fallback stack and reported, or the run fails with the
    exact codepoint list (no missing-glyph false success). --require-embedded
    makes fallback use a hard failure: it guarantees every glyph resolves to a
    BUNDLED FACE, not that the standalone .svg carries the fonts (it does not —
    only the .html embeds them).
  * render/export truth: a browser.screenshot of the HTML is a VIEWPORT-bounded
    preview, never the declared full-size raster. The HTML offers an in-page
    "Export PNG" at the declared pixel size using the loaded fonts; engines with
    canvas limits (iOS WKWebView caps very large canvases) must fail with an
    actionable message — the page never silently downscales.

Exit codes: 0 success, 2 invalid spec, 3 output guard (use --overwrite), 4 unsupported.
"""
import argparse
import base64
import hashlib
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE_ROOT = os.path.dirname(HERE)
FONTS_JSON = os.path.join(PACKAGE_ROOT, "assets", "fonts", "fonts.json")

MAX_SPEC_BYTES = 262144
MAX_ELEMENTS = 512
MAX_TEXT_TOTAL_CHARS = 8192
MAX_PATH_BYTES = 4096
MIN_CANVAS_PX, MAX_CANVAS_PX = 64, 8192
MIN_FONT_PX, MAX_FONT_PX = 4, 2048
# Text considered CJK falls back to the device system stack (iOS: PingFang SC).
FALLBACK_STACK = '"PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", sans-serif'

# In-page full-size PNG export (Floe first-party, MPL-2.0; runs only in the
# viewer's own browser — the file itself still performs zero network I/O).
# Uses the page's ALREADY-LOADED @font-face data and the inline SVG; rasterizes
# artwork only (never the chrome/notices). Engines that clamp the canvas must
# report failure with real numbers — no silent downscale.
EXPORT_JS = r"""
(function () {
  "use strict";
  var W = @W@, H = @H@, PREFIX = "@PREFIX@";
  var svg = document.getElementById("art");
  var btn = document.getElementById("export-png");
  var status = document.getElementById("export-status");
  function say(m) { status.textContent = m; }
  btn.addEventListener("click", function () {
    say("Rasterizing " + W + "x" + H + " with the page's loaded fonts...");
    var faces = document.getElementById("faces").textContent;
    var clone = svg.cloneNode(true);
    clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    var st = document.createElementNS("http://www.w3.org/2000/svg", "style");
    st.appendChild(document.createTextNode(faces));
    clone.insertBefore(st, clone.firstChild);
    var xml = new XMLSerializer().serializeToString(clone);
    var img = new Image();
    img.onload = function () {
      var c = document.createElement("canvas");
      c.width = W; c.height = H;
      if (c.width !== W || c.height !== H) {
        say("FAILED: this engine clamped the canvas to " + c.width + "x" + c.height +
            "; full-size " + W + "x" + H + " raster is NOT supported here. Deliver the SVG/HTML" +
            " or a clearly-labeled viewport preview. Nothing was downscaled.");
        return;
      }
      try {
        c.getContext("2d").drawImage(img, 0, 0, W, H);
        var url = c.toDataURL("image/png");
        if (!url || url === "data:,") { throw new Error("empty data url"); }
        var a = document.createElement("a");
        a.download = PREFIX + "-" + W + "x" + H + ".png";
        a.href = url;
        a.click();
        say("Exported " + W + "x" + H + " PNG (artwork only, fonts as loaded on this page).");
      } catch (err) {
        say("FAILED: canvas export blocked (" + err.name + "). This engine does not allow the" +
            " full-size raster; deliver SVG/HTML or a clearly-labeled viewport preview instead.");
      }
    };
    img.onerror = function () {
      say("FAILED: this engine could not rasterize the embedded SVG with its inline fonts." +
          " Deliver the SVG/HTML or a clearly-labeled viewport preview.");
    };
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(xml);
  });
})();
"""

# Page chrome: explicit declared size, fit-to-view stage, artwork-only print
# export, license disclosures. Token replacement order in main() guarantees
# user-controlled content (@SVG@) is injected LAST and never sees remaining
# tokens. Zero external resources: every src/url() in this page is a data:
# payload defined inline.
HTML_TEMPLATE = """<!DOCTYPE html><html lang="@LANG@"><head><meta charset="utf-8">\
<meta name="viewport" content="width=device-width,initial-scale=1">\
<title>@TITLE@</title>\
<style id="layout">*{box-sizing:border-box}html,body{margin:0;padding:0;background:#@BG@}\
body{display:flex;flex-direction:column;align-items:center;gap:10px;padding:10px;box-sizing:border-box;\
font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Helvetica Neue",Arial,sans-serif;\
font-size:12px;line-height:1.5;color:#1c1d1f}\
.chrome{width:min(100%,860px);background:#fbfaf7;border:1px solid #d8d5cc;border-radius:10px;padding:8px 12px}\
.chrome .row{display:flex;gap:8px;align-items:center;margin-top:6px;flex-wrap:wrap}\
button{font:inherit;padding:6px 10px;border:1px solid #b9b5aa;border-radius:7px;background:#fff;cursor:pointer}\
#export-status{color:#8a3b12;overflow-wrap:anywhere}\
.stage{width:min(100%,calc((100vh - 220px) * @RATIO@));aspect-ratio:@W@ / @H@}\
.stage svg{display:block;width:100%;height:100%}\
.notices{width:min(100%,860px);background:#fbfaf7;border:1px solid #d8d5cc;border-radius:10px;padding:8px 12px}\
.notices summary{cursor:pointer;font-weight:600}\
.notices p{margin:8px 0}\
.oftext{white-space:pre-wrap;word-break:break-word;\
font:10px/1.45 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:#f3f1ea;padding:8px;\
max-height:220px;overflow:auto}\
@media print{.chrome,.notices{display:none}body{padding:0;gap:0}\
.stage{width:100%;aspect-ratio:auto}.stage svg{width:100%;height:auto}}</style>\
<style id="faces">@FACECSS@</style>\
</head><body>\
<div class="chrome" id="artifact-chrome"><span id="decl">@DECL@</span>\
<div class="row"><button id="export-png">Export PNG @W@×@H@</button>\
<span id="export-status" role="status"></span></div></div>\
<div class="stage">@SVG@</div>\
@NOTICES_HTML@\
<script type="application/json" id="artifact-notices">@NOTICE_JSON@</script>\
<script>@EXPORT_JS@</script>\
</body></html>"""

def die(code, msg):
    sys.stderr.write("make_poster: %s\n" % msg)
    sys.exit(code)

def hex_color(v, field):
    if not isinstance(v, str) or not v.startswith("#"):
        die(2, "%s: color must be #RGB or #RRGGBB, got %r" % (field, v))
    h = v[1:]
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6 or any(c not in "0123456789abcdefABCDEF" for c in h):
        die(2, "%s: invalid hex color %r" % (field, v))
    return "#" + h.lower()

def num(v, field, lo=None, hi=None):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        die(2, "%s: must be a finite number, got %r" % (field, v))
    if lo is not None and v < lo:
        die(2, "%s: %r below minimum %r" % (field, v, lo))
    if hi is not None and v > hi:
        die(2, "%s: %r above maximum %r" % (field, v, hi))
    return float(v)

def dim_to_px(obj, field, dpi):
    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
        return num(obj, field, 1, 100000)
    if not isinstance(obj, dict) or set(obj) != {"unit", "value"}:
        die(2, "%s: dimensions must be a number (px) or {\"unit\":\"px|mm\",\"value\":N}" % field)
    unit = obj["unit"]
    val = num(obj["value"], field + ".value", 0.01, 100000)
    if unit == "px":
        return val
    if unit == "mm":
        return val * dpi / 25.4
    die(2, "%s: unknown unit %r (px or mm)" % (field, unit))

class FontLib(object):
    def __init__(self, path):
        try:
            with open(path, "rb") as fh:
                raw = fh.read()
            data = json.loads(raw.decode("utf-8"))
        except Exception as e:
            die(4, "cannot load %s: %s" % (path, e))
        self.by_key = {}
        for f in data["fonts"]:
            key = (f["family"].lower(), f["style"].lower())
            ranges = []
            for s, e in f["coverage"]:
                ranges.append((s, e))
            adv = []
            for s, e, v in f["advances"]:
                adv.append((s, e, v))
            self.by_key[key] = {"file": f["file"], "family": f["family"], "style": f["style"],
                                "unitsPerEm": f["unitsPerEm"], "sha256": f["sha256"],
                                "licenseFile": f["licenseFile"], "coverage": ranges,
                                "advances": adv, "path": os.path.join(os.path.dirname(path), f["file"])}

    def pick(self, family, style):
        f = self.by_key.get((str(family).lower(), str(style).lower()))
        if f is None:
            die(2, "font %r/%r is not bundled; available: %s" % (
                family, style, ", ".join(sorted("%s/%s" % (v["family"], v["style"]) for v in self.by_key.values()))))
        return f

    @staticmethod
    def covers(font, cp):
        lo, hi = 0, len(font["coverage"]) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            s, e = font["coverage"][mid]
            if cp < s:
                hi = mid - 1
            elif cp > e:
                lo = mid + 1
            else:
                return True
        return False

    @staticmethod
    def advance_units(font, cp):
        for s, e, v in font["advances"]:
            if s <= cp <= e:
                return v
        return 0

def is_cjk_range(cp):
    return (0x3000 <= cp <= 0x303F or 0x3040 <= cp <= 0x30FF or 0x3400 <= cp <= 0x4DBF
            or 0x4E00 <= cp <= 0x9FFF or 0xF900 <= cp <= 0xFAFF
            or 0xFF00 <= cp <= 0xFF60 or 0xFF66 <= cp <= 0xFFDC
            or 0x20000 <= cp <= 0x2FA1F)

def text_metrics(font, text, size_px):
    """Advance sum in px. Characters routed to the CJK fallback stack are
    estimated at a full em (CJK glyphs are square on all target systems), so
    bounds/overlap checks stay meaningful for fallback text."""
    total = 0.0
    for ch in text:
        cp = ord(ch)
        if ch != " " and not FontLib.covers(font, cp):
            total += font["unitsPerEm"] if is_cjk_range(cp) else 0
            continue
        total += FontLib.advance_units(font, cp if cp <= 0x10FFFF else 0x20)
    return total / float(font["unitsPerEm"]) * size_px

def load_fonts():
    return FontLib(FONTS_JSON)

def analyze_text(font, text, require_embedded, allow_unsupported):
    embedded, fallback, unsupported = 0, 0, []
    for ch in text:
        cp = ord(ch)
        if cp in (0x09, 0x0A, 0x0D):
            die(2, "text must not contain tabs/newlines (use separate elements)")
        if ch == " " or FontLib.covers(font, cp):
            embedded += 1
        elif is_cjk_range(cp):
            fallback += 1
        else:
            unsupported.append("U+%04X" % cp)
    if unsupported:
        if not allow_unsupported:
            die(2, "characters not covered by any bundled font or the CJK fallback: %s "
                   "(pick a covering family per assets/fonts/fonts.json, or pass "
                   "--allow-unsupported only if the viewer substitutes them)" % ", ".join(sorted(set(unsupported))))
        fallback += len(unsupported)
        unsupported = []
    if fallback and require_embedded:
        die(4, "--require-embedded: %d fallback-only characters (no bundled font covers "
               "them; the CJK system stack is a device font and is NOT embedded anywhere — "
               "the standalone .svg never carries fonts and the .html embeds only bundled "
               "faces); drop the flag and render the HTML on device, or replace the text "
               "with Latin covered by assets/fonts" % fallback)
    return embedded, fallback

def atomic_write(outdir, name, data_bytes, overwrite):
    path = os.path.join(outdir, name)
    if os.path.exists(path) and not overwrite:
        die(3, "refusing to overwrite existing %s (pass --overwrite)" % path)
    tmp = path + ".tmp-%05d" % (os.getpid() & 0xFFFF)
    with open(tmp, "wb") as fh:
        fh.write(data_bytes)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    return path

def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))

def main():
    ap = argparse.ArgumentParser(prog="make_poster", description=__doc__.splitlines()[2])
    ap.add_argument("--spec", required=True, help="workspace-relative poster spec JSON")
    ap.add_argument("--outdir", default="poster-out")
    ap.add_argument("--prefix", default="poster")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--require-embedded", action="store_true",
                    help="fail if any glyph must use the CJK/system fallback stack "
                         "(every glyph then resolves to a bundled face). Note: only the "
                         ".html artifact embeds the fonts; the standalone .svg still "
                         "references families by name")
    ap.add_argument("--allow-unsupported", action="store_true",
                    help="route characters outside every bundled font AND the CJK "
                         "fallback to the viewer default font (reported; only for "
                         "viewer-substituted deliverables)")
    ap.add_argument("--check-only", action="store_true",
                    help="validate and report without writing files")
    args = ap.parse_args()

    if args.prefix in ("", ".", "..") or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", args.prefix):
        die(2, "--prefix must match [A-Za-z0-9._-]{1,64} (it is embedded in the HTML export)")
    try:
        raw = open(args.spec, "rb").read()
    except OSError as e:
        die(2, "cannot read spec: %s" % e)
    if len(raw) > MAX_SPEC_BYTES:
        die(2, "spec exceeds %d bytes" % MAX_SPEC_BYTES)
    spec_sha = hashlib.sha256(raw).hexdigest()
    try:
        spec = json.loads(raw.decode("utf-8"))
    except Exception as e:
        die(2, "spec is not valid JSON: %s" % e)
    if not isinstance(spec, dict) or spec.get("schemaVersion") != 1:
        die(2, "spec.schemaVersion must be 1")

    canvas = spec.get("canvas")
    if not isinstance(canvas, dict):
        die(2, "spec.canvas is required")
    dpi = num(canvas.get("dpi", 300), "canvas.dpi", 72, 1440)
    w_px = dim_to_px(canvas.get("width"), "canvas.width", dpi)
    h_px = dim_to_px(canvas.get("height"), "canvas.height", dpi)
    if not (MIN_CANVAS_PX <= w_px <= MAX_CANVAS_PX and MIN_CANVAS_PX <= h_px <= MAX_CANVAS_PX):
        die(2, "canvas must be %d..%d px (got %.1f x %.1f)" % (MIN_CANVAS_PX, MAX_CANVAS_PX, w_px, h_px))
    bg = hex_color(canvas.get("background", "#ffffff"), "canvas.background")

    elements = spec.get("elements")
    if not isinstance(elements, list) or not 1 <= len(elements) <= MAX_ELEMENTS:
        die(2, "spec.elements must be a non-empty list of at most %d items" % MAX_ELEMENTS)
    libs = load_fonts()
    total_chars = 0
    text_boxes = []
    svg_parts = []
    fonts_used = {}
    report_texts = []

    for idx, el in enumerate(elements):
        if not isinstance(el, dict) or "type" not in el:
            die(2, "elements[%d]: must be an object with type" % idx)
        t = el["type"]
        where = "elements[%d] (%s)" % (idx, t)
        if t in ("rect", "circle", "line", "path", "text"):
            pass
        else:
            die(2, "%s: unknown type; supported: rect, circle, line, path, text" % where)
        opacity = el.get("opacity", 1.0)
        opacity_s = ""
        if opacity != 1.0:
            num(opacity, where + ".opacity", 0.02, 1.0)
            opacity_s = ' opacity="%.3f"' % opacity

        if t == "rect":
            x = num(el.get("x"), where + ".x"); y = num(el.get("y"), where + ".y")
            rw = num(el.get("w"), where + ".w", 0.5, 100000)
            rh = num(el.get("h"), where + ".h", 0.5, 100000)
            fill = hex_color(el.get("fill", "none"), where + ".fill") if el.get("fill") not in (None, "none") else "none"
            stroke = hex_color(el["stroke"], where + ".stroke") if el.get("stroke") else None
            if fill == "none" and not stroke:
                die(2, "%s: needs fill or stroke" % where)
            if x < 0 or y < 0 or x + rw > w_px + 0.01 or y + rh > h_px + 0.01:
                die(2, "%s: rect leaves the canvas (%.1f,%.1f %.1fx%.1f in %.1fx%.1f)" % (where, x, y, rw, rh, w_px, h_px))
            rx = num(el.get("rx", 0), where + ".rx", 0, min(rw, rh) / 2)
            s = '<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="%s"' % (x, y, rw, rh, fill)
            if rx:
                s += ' rx="%.2f"' % rx
            if stroke:
                s += ' stroke="%s" stroke-width="%.2f"' % (stroke, num(el.get("strokeWidth", 1), where + ".strokeWidth", 0.1, 512))
            svg_parts.append(s + opacity_s + "/>")

        elif t == "circle":
            cx = num(el.get("cx"), where + ".cx"); cy = num(el.get("cy"), where + ".cy")
            r = num(el.get("r"), where + ".r", 0.5, 100000)
            fill = hex_color(el.get("fill", "none"), where + ".fill") if el.get("fill") not in (None, "none") else "none"
            stroke = hex_color(el["stroke"], where + ".stroke") if el.get("stroke") else None
            if cx - r < -0.01 or cy - r < -0.01 or cx + r > w_px + 0.01 or cy + r > h_px + 0.01:
                die(2, "%s: circle leaves the canvas" % where)
            s = '<circle cx="%.2f" cy="%.2f" r="%.2f" fill="%s"' % (cx, cy, r, fill)
            if stroke:
                s += ' stroke="%s" stroke-width="%.2f"' % (stroke, num(el.get("strokeWidth", 1), where + ".strokeWidth", 0.1, 512))
            svg_parts.append(s + opacity_s + "/>")

        elif t == "line":
            x1 = num(el.get("x1"), where + ".x1"); y1 = num(el.get("y1"), where + ".y1")
            x2 = num(el.get("x2"), where + ".x2"); y2 = num(el.get("y2"), where + ".y2")
            for (px_, py_) in ((x1, y1), (x2, y2)):
                if px_ < 0 or py_ < 0 or px_ > w_px or py_ > h_px:
                    die(2, "%s: endpoint outside canvas" % where)
            stroke = hex_color(el.get("stroke"), where + ".stroke")
            sw = num(el.get("width", 1), where + ".width", 0.1, 512)
            svg_parts.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" stroke-width="%.2f"%s/>'
                             % (x1, y1, x2, y2, stroke, sw, opacity_s))

        elif t == "path":
            d = el.get("d")
            if not isinstance(d, str) or not 1 <= len(d) <= MAX_PATH_BYTES:
                die(2, "%s: d must be a string of 1..%d bytes" % (where, MAX_PATH_BYTES))
            if not re.fullmatch(r"[MmLlHhVvCcSsQqTtAaZz0-9eE.,+\- ]+", d.strip()):
                die(2, "%s: d contains characters outside SVG path grammar" % where)
            fill = hex_color(el.get("fill", "none"), where + ".fill") if el.get("fill") not in (None, "none") else "none"
            stroke = hex_color(el["stroke"], where + ".stroke") if el.get("stroke") else None
            if fill == "none" and not stroke:
                die(2, "%s: needs fill or stroke" % where)
            s = '<path d="%s" fill="%s"' % (d.strip(), fill)
            if stroke:
                s += ' stroke="%s" stroke-width="%.2f"' % (stroke, num(el.get("strokeWidth", 1), where + ".strokeWidth", 0.1, 512))
            svg_parts.append(s + opacity_s + "/>")

        else:  # text
            content = el.get("content")
            if not isinstance(content, str) or not 1 <= len(content) <= 512:
                die(2, "%s: content must be a string of 1..512 chars" % where)
            total_chars += len(content)
            if total_chars > MAX_TEXT_TOTAL_CHARS:
                die(2, "spec text exceeds %d characters in total" % MAX_TEXT_TOTAL_CHARS)
            font = libs.pick(el.get("family"), el.get("style", "Regular"))
            size_px = dim_to_px(el.get("size"), where + ".size", dpi)
            if not (MIN_FONT_PX <= size_px <= MAX_FONT_PX):
                die(2, "%s: font size must be %d..%d px" % (where, MIN_FONT_PX, MAX_FONT_PX))
            x = num(el.get("x"), where + ".x"); y = num(el.get("y"), where + ".y")
            anchor = el.get("anchor", "start")
            if anchor not in ("start", "middle", "end"):
                die(2, "%s: anchor must be start|middle|end" % where)
            fill = hex_color(el.get("fill"), where + ".fill")
            ls = el.get("letterSpacing", 0)
            ls = num(ls, where + ".letterSpacing", -50, 50)
            width = text_metrics(font, content, size_px) + ls * max(len(content) - 1, 0)
            if el.get("maxWidth") is not None:
                mw = dim_to_px(el["maxWidth"], where + ".maxWidth", dpi)
                if width > mw + 0.5:
                    die(2, "%s: estimated text width %.1fpx exceeds maxWidth %.1fpx (advance metrics from fonts.json)"
                        % (where, width, mw))
            bx = x if anchor == "start" else (x - width / 2 if anchor == "middle" else x - width)
            top, bot = y - size_px * 0.82, y + size_px * 0.25
            if bx < -0.01 or bx + width > w_px + 0.01 or top < -0.01 or bot > h_px + 0.01:
                die(2, "%s: text box (%.1f..%.1f, %.1f..%.1f) leaves the canvas; move/resize it or use a smaller size"
                    % (where, bx, bx + width, top, bot))
            for other in text_boxes:
                if not (bx + width <= other["x0"] + 0.5 or other["x1"] <= bx + 0.5
                        or bot <= other["y0"] + 0.5 or other["y1"] <= top + 0.5):
                    die(2, "%s overlaps text elements[%d] (both boxes must be separated; text collisions are never intended)"
                        % (where, other["idx"]))
            text_boxes.append({"idx": idx, "x0": bx, "x1": bx + width, "y0": top, "y1": bot})
            embedded, fallback = analyze_text(font, content, args.require_embedded, args.allow_unsupported)
            report_texts.append({"element": idx, "chars": len(content), "embedded": embedded,
                                 "fallback": fallback, "estimatedWidthPx": round(width, 2)})
            fonts_used[(font["family"], font["style"])] = font
            family_attr = '%s, %s' % (font["family"], FALLBACK_STACK) if fallback else font["family"]
            svg_parts.append('<text x="%.2f" y="%.2f" font-family="%s" font-size="%.2f" '
                             'font-style="normal" font-weight="%s" fill="%s" text-anchor="%s"%s>%s</text>'
                             % (x, y, esc(family_attr), size_px,
                                "700" if font["style"].lower().startswith("bold") else "400",
                                fill, anchor,
                                (' letter-spacing="%.2f"' % ls) if ls else "", esc(content)))

    svg = ('<svg id="art" xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
           'viewBox="0 0 %d %d" role="img">%s<title>%s</title><desc>Generated by canvas-design '
           'make_poster.py; units declared in coverage report; fonts referenced by family name '
           'with declared fallback stack (the .html artifact embeds the used faces).</desc>'
           '<rect x="0" y="0" width="%d" height="%d" fill="%s"/>%s</svg>'
           % (round(w_px), round(h_px), round(w_px), round(h_px), "",
              esc(str(spec.get("title", "poster"))), round(w_px), round(h_px), bg,
              "".join(svg_parts)))
    svg_bytes = svg.encode("utf-8")

    # gather the actually-used bundled faces + license entries (hash-verified)
    face_css, used, license_notes = [], [], {}
    for key in sorted(fonts_used):
        f = fonts_used[key]
        try:
            with open(f["path"], "rb") as fh:
                blob = fh.read()
        except OSError:
            die(4, "package font missing: %s" % f["path"])
        if hashlib.sha256(blob).hexdigest() != f["sha256"]:
            die(4, "bundled font hash drift for %s" % f["file"])
        face_css.append('@font-face{font-family:"%s";font-style:normal;font-weight:%d;'
                        'src:url(data:font/ttf;base64,%s) format("truetype");}'
                        % (f["family"], 700 if f["style"].lower().startswith("bold") else 400,
                           base64.b64encode(blob).decode("ascii")))
        used.append(f)
        lic_path = os.path.join(os.path.dirname(f["path"]), f["licenseFile"])
        if f["licenseFile"] not in license_notes:
            try:
                with open(lic_path, "rb") as fh:
                    lic = fh.read()
            except OSError:
                die(4, "package license text missing: %s" % lic_path)
            first = lic.decode("utf-8", "replace").split("\n", 1)[0].strip()
            license_notes[f["licenseFile"]] = {
                "text": lic.decode("utf-8", "replace"),
                "sha256": hashlib.sha256(lic).hexdigest(),
                "copyright": first if first.startswith("Copyright") else
                             "(see full license text below)"}
        f["_license"] = license_notes[f["licenseFile"]]

    notices = {
        "schemaVersion": 1,
        "generator": "canvas-design/make_poster.py",
        "code": {"license": "MPL-2.0",
                 "holders": "Floe Skill Hub authors (first-party generator and inline viewer code)",
                 "fullText": "https://www.mozilla.org/en-US/MPL/2.0/ and the LICENSE at the "
                             "floe-skill-hub repository root. This URL is plain text: the page "
                             "loads no external resources."},
        "upstream": {"derivation": "anthropics/skills@dbd4588f9e1033efb41dad4bef2f7947c8993d44 "
                                   "skills/canvas-design (workflow derivation; no upstream code "
                                   "in this page)", "license": "Apache-2.0"},
        "fonts": [{"family": f["family"], "style": f["style"], "file": f["file"],
                   "sha256": f["sha256"], "license": "SIL Open Font License 1.1",
                   "licenseFile": f["licenseFile"],
                   "licenseTextSha256": f["_license"]["sha256"],
                   "copyright": f["_license"]["copyright"]} for f in used],
        "artwork": "The poster content (text, shapes, colors) is the author's work. This tool "
                   "asserts no license over user content and invents none. The exported PNG "
                   "contains artwork only; notices live in the page chrome, not the image."
    }
    notices_json = json.dumps(notices, ensure_ascii=False, sort_keys=True).replace("</", "\\u003c")

    report = {
        "tool": "canvas-design/make_poster.py",
        "specSha256": spec_sha,
        "declaredCanvas": {"width": canvas.get("width"), "height": canvas.get("height"), "dpi": dpi},
        "canvasPx": {"width": round(w_px), "height": round(h_px)},
        "units": "positions in canvas px; sizes as declared (px or mm converted at dpi %g)" % dpi,
        "metricBasis": "advance widths from assets/fonts/fonts.json (v2 registry; per-codepoint "
                       "CoreText cross-checked on the exact TTF bytes) + nominal ascent/descent "
                       "box; these are ADVANCE ESTIMATES, not ink/shaping bounds — visual QA "
                       "still required",
        "artifactPolicy": {
            "svg": "editable vector source; text references families BY NAME (viewer needs the "
                   "fonts; use the html artifact for font-portable rendering)",
            "html": "self-contained: inline SVG + base64 @font-face for used faces + license "
                    "notices + declared-size PNG export (engine-canvas-limited; fails with an "
                    "actionable message, never downscales); CJK renders through the DEVICE "
                    "fallback stack declared here, which is not embedded anywhere",
            "browser.screenshot": "viewport-bounded PREVIEW only; never claim it as the declared "
                                  "full-size raster; record its real pixel dimensions",
            "pdf": "png_to_pdf.py wraps an existing verified PNG; page geometry follows the "
                   "PNG's actual pixels at the stated --dpi"},
        "fontsUsed": [{"file": v["file"], "family": v["family"], "style": v["style"], "sha256": v["sha256"],
                       "license": v["licenseFile"]} for _, v in sorted(fonts_used.items())],
        "fallbackStack": FALLBACK_STACK,
        "policy": {"requireEmbedded": args.require_embedded, "allowUnsupported": args.allow_unsupported},
        "texts": report_texts,
        "elementCount": len(elements),
        "notices": notices,
    }
    report_bytes = (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=1) + "\n").encode("utf-8")

    if args.check_only:
        sys.stdout.write(report_bytes.decode("utf-8"))
        return

    # self-contained HTML artifact: inline SVG + base64 @font-face for used
    # bundled fonts + explicit size chrome + license disclosures + export
    decl = "Declared size: %d × %d px (%g dpi on the declared physical page). This page scales " \
           "the artwork to fit the view; a viewport screenshot is a preview, not the full raster." \
           % (round(w_px), round(h_px), dpi)
    fam_blocks = []
    for lf in sorted(license_notes):
        n = license_notes[lf]
        faces_here = [f for f in used if f["licenseFile"] == lf]
        head = ", ".join("%s %s (%s, sha256 %s…)" % (f["family"], f["style"], f["file"],
                                                     f["sha256"][:16]) for f in faces_here)
        fam_blocks.append(
            "<p><strong>%s</strong> — faces used: %s.<br>Copyright notice: %s<br>"
            "The font software is redistributed inside this page as the base64 @font-face "
            "payloads; the SIL OFL 1.1 terms below apply to it.</p><pre class=\"oftext\">%s</pre>"
            % (esc(lf), esc(head), esc(n["copyright"]), esc(n["text"])))
    notices_html = (
        '<details class="notices"><summary>Licensing of this artifact — fonts: SIL OFL 1.1 · '
        'viewer code: MPL-2.0 · click to read</summary>'
        + "".join(fam_blocks) +
        '<p><strong>Page code and generator</strong>: Floe first-party under the Mozilla Public '
        'License 2.0 (full text: https://www.mozilla.org/en-US/MPL/2.0/ and the LICENSE at the '
        'floe-skill-hub repository root). The design workflow derives from anthropics/skills '
        'canvas-design (Apache-2.0); no upstream code is in this page.</p>'
        '<p><strong>Artwork</strong>: the poster content belongs to its author; this tool asserts '
        'no license over user content. The Export PNG file contains artwork only.</p>'
        '<p>This URL text is inert: the page references no external resources.</p></details>')
    export_js = EXPORT_JS.replace("@W@", str(round(w_px))).replace("@H@", str(round(h_px))) \
                         .replace("@PREFIX@", args.prefix)
    ratio = "%.6f" % (w_px / h_px)
    html = HTML_TEMPLATE
    for token, value in (
            ("@LANG@", esc(str(spec.get("lang", "en")))),
            ("@TITLE@", esc(str(spec.get("title", "poster")))),
            ("@BG@", bg[1:]),
            ("@W@", str(round(w_px))),
            ("@H@", str(round(h_px))),
            ("@RATIO@", ratio),
            ("@DECL@", esc(decl)),
            ("@NOTICE_JSON@", notices_json),
            ("@EXPORT_JS@", export_js),
            ("@FACECSS@", "".join(face_css)),
            ("@NOTICES_HTML@", notices_html),
            ("@SVG@", svg)):
        html = html.replace(token, value)
    html_bytes = html.encode("utf-8")

    if not os.path.isdir(args.outdir):
        try:
            os.makedirs(args.outdir)
        except OSError as e:
            die(2, "cannot create outdir: %s" % e)
    p1 = atomic_write(args.outdir, args.prefix + ".svg", svg_bytes, args.overwrite)
    p2 = atomic_write(args.outdir, args.prefix + ".html", html_bytes, args.overwrite)
    p3 = atomic_write(args.outdir, args.prefix + ".coverage.json", report_bytes, args.overwrite)
    sys.stdout.write(json.dumps({"written": [p1, p2, p3], "canvasPx": report["canvasPx"],
                                 "fontsUsed": [f["file"] for f in used],
                                 "fallbackChars": sum(t["fallback"] for t in report_texts)}) + "\n")

if __name__ == "__main__":
    main()
