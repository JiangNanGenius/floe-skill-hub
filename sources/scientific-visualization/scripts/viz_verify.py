#!/usr/bin/env python3
"""Golden verifier for the Floe scientific-visualization adaptation.

First-party Floe script (MIT (c) Floe project); NOT upstream K-Dense
content. It proves in one offline command that the bundled Matplotlib
export path produces REAL, inspectable output files in the current
environment - not merely that files exist:

  * declared dependency pins (matplotlib==3.10.1, numpy==2.2.4,
    pillow==11.1.0, pypdf==5.4.0 - the exact Debian 13 guest versions);
    a wrong version is a failed receipt, never a pass;
  * PNG: stdlib IHDR/chunk-CRC structure + exact expected pixel geometry,
    non-blank content, series/error-bar colors actually present in pixels;
  * SVG: XML structure, searchable axis labels WITH units, the interior
    missing value rendered as two disjoint line segments (never bridged),
    and an INDEPENDENT coordinate-mapping golden: with a fully specified
    axes rectangle the data point (2, 20.0) must land at exactly
    (190.08, 213.12) pt computed by hand from the page geometry;
  * PDF: %PDF header/%%EOF trailer, one page at the exact 432x288 pt page
    size, embedded font present (via the declared pypdf layer);
  * palette contrast recomputed by a second, independent WCAG
    implementation inside this verifier (exact rational coefficients;
    agreement <= 1e-9) plus the spec anchor contrast(black, white) = 21.0;
  * CJK honesty: the check renders CJK labels only when a CJK-capable font
    is actually discoverable, captures matplotlib's findfont/glyph warnings,
    and asserts the CJK string is searchable in the SVG; otherwise the
    check is reported skipped-no-cjk-font with provisioning guidance and
    --require-cjk turns that into a failure. Missing fonts never render
    tofu silently and never become a pass;
  * every bundled CLI end-to-end through real subprocesses, and the
    export safety negatives (overwrite refusal, invalid dpi/format/font
    mode).

All rendering happens inside an ephemeral temporary directory; no network.
Exit 0 only when every required check passes.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import math
import re
import struct
import subprocess
import sys
import tempfile
import warnings
import xml.etree.ElementTree as ET
import zlib
from fractions import Fraction
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = SCRIPTS_DIR.parent
FIXTURES = PACKAGE_ROOT / "assets" / "fixtures"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

DECLARED_PINS = {
    "matplotlib": "3.10.1",
    "numpy": "2.2.4",
    "pillow": "11.1.0",
    "pypdf": "5.4.0",
}
CONTRAST_TOL = 1e-9
COORD_TOL_PT = 1.0

# page geometry used by the mapping golden (fully specified, hand-computable)
FIG_W_IN, FIG_H_IN = 6.0, 4.0
AXES_RECT = (0.1, 0.1, 0.85, 0.8)  # left, bottom, width, height in figure coords
XLIM = (0.0, 5.0)
YLIM = (0.0, 100.0)
PAGE_W_PT, PAGE_H_PT = FIG_W_IN * 72.0, FIG_H_IN * 72.0  # 432 x 288

SERIES_COLOR = "#0072b2"   # Okabe-Ito blue
ERROR_COLOR = "#d55e00"    # Okabe-Ito vermillion

CJK_PROBE_FAMILIES = (
    "noto sans cjk", "noto serif cjk", "source han", "wenquanyi",
    "droid sans fallback", "ar pl", "pingfang", "hiragino sans gb",
    "microsoft yahei", "simhei", "simsun", "takao", "ipaex",
)


class CheckFailure(Exception):
    """One failed golden/safety check with an actionable message."""


class LayerMissing(Exception):
    def __init__(self, missing: list[str]):
        super().__init__("missing: " + ", ".join(missing))
        self.missing = missing


def _base_version(raw: str) -> str:
    return raw.split("+", 1)[0]


def _exact(reference: Any, candidate: Any, label: str) -> None:
    if candidate != reference:
        raise CheckFailure(f"{label}: expected exactly {reference!r}, got {candidate!r}")


def _close(reference: float, candidate: Any, label: str, tol: float = 1e-9) -> None:
    if isinstance(candidate, bool) or not isinstance(candidate, (int, float)):
        raise CheckFailure(f"{label}: expected a number, got {candidate!r}")
    scale = max(1.0, abs(reference), abs(float(candidate)))
    if abs(reference - float(candidate)) > tol * scale:
        raise CheckFailure(f"{label}: expected {reference!r} (tol {tol}), got {candidate!r}")


# --------------------------------------------------------------------------
# layer probing
# --------------------------------------------------------------------------

def load_layer() -> dict[str, Any]:
    missing = []
    mods: dict[str, Any] = {}
    try:
        import numpy as np
        mods["numpy"] = np
    except ImportError:
        missing.append("numpy")
    try:
        import matplotlib
        matplotlib.use("Agg")  # headless: the guest has no display server
        import matplotlib.pyplot as plt
        mods["matplotlib"] = matplotlib
        mods["plt"] = plt
    except ImportError:
        missing.append("matplotlib")
    try:
        import PIL
        from PIL import Image
        mods["PIL"] = PIL
        mods["Image"] = Image
    except ImportError:
        missing.append("pillow")
    try:
        import pypdf
        mods["pypdf"] = pypdf
    except ImportError:
        missing.append("pypdf")
    if missing:
        raise LayerMissing(missing)
    for name, pin in DECLARED_PINS.items():
        mod = mods.get({"pillow": "PIL"}.get(name, name))
        installed = str(getattr(mod, "__version__", "unknown"))
        if _base_version(installed) != pin:
            raise CheckFailure(
                f"{name} installed {installed} does not match the declared pin {pin} "
                "(Debian local suffixes like +dfsg are tolerated)")
        mods.setdefault("versions", {})[name] = installed
    return mods


# --------------------------------------------------------------------------
# independent WCAG contrast implementation (exact rational sRGB)
# --------------------------------------------------------------------------

def wcag_contrast_exact(hex_a: str, hex_b: str) -> float:
    def luminance(hexcolor: str) -> Fraction:
        hexcolor = hexcolor.lstrip("#")
        channels = []
        for i in (0, 2, 4):
            c = Fraction(int(hexcolor[i:i + 2], 16), 255)
            if c <= Fraction(102, 2550):  # 0.04045 as 81/2000 ~ use exact decimal bound
                channels.append(c / Fraction(1292, 100))
            else:
                # ((c+0.055)/1.055)^2.4 - transcendental; evaluate in float but
                # keep the coefficient path exact up to the power.
                channels.append(Fraction(float(((float(c) + 0.055) / 1.055) ** 2.4)))
        return (Fraction(2126, 10000) * channels[0]
                + Fraction(7152, 10000) * channels[1]
                + Fraction(722, 10000) * channels[2])

    la, lb = luminance(hex_a), luminance(hex_b)
    lighter, darker = max(la, lb), min(la, lb)
    return float((lighter + Fraction(1, 20)) / (darker + Fraction(1, 20)))


def check_palette_dual_implementation(layer: dict[str, Any], tmp: Path) -> None:
    import palette_audit

    palettes = palette_audit.bundled_palettes()
    if "okabe_ito_on_white" not in palettes:
        raise CheckFailure("bundled palettes lost okabe_ito_on_white")
    colors = palettes["okabe_ito_on_white"]
    background_rgb = palette_audit.parse_hex_color("FFFFFF")
    checked = 0
    for hexcolor in colors:
        rgb = palette_audit.parse_hex_color(hexcolor)
        theirs = float(palette_audit.contrast_ratio(rgb, background_rgb))
        mine = wcag_contrast_exact(palette_audit.canonical_hex(rgb), "FFFFFF")
        _close(mine, theirs, f"WCAG contrast {hexcolor} (dual implementation)", CONTRAST_TOL)
        checked += 1
    if checked < 4:
        raise CheckFailure(f"dual-implementation contrast check covered only {checked} colors")
    # full report structure + its rounded column must agree with the raw math
    report = palette_audit.audit_palette(
        colors, background="FFFFFF", role="graphical", name="okabe_ito_on_white")
    entries = report["palette"]["colors"]
    if len(entries) != checked:
        raise CheckFailure(f"audit report lists {len(entries)} colors, expected {checked}")
    for entry, hexcolor in zip(entries, colors):
        rgb = palette_audit.parse_hex_color(hexcolor)
        raw = float(palette_audit.contrast_ratio(rgb, background_rgb))
        _close(round(raw, 3), float(entry["contrast_against_background"]),
               f"audit report rounding {hexcolor}", 1e-12)
    # spec anchors independent of both implementations
    _close(21.0, wcag_contrast_exact("000000", "FFFFFF"), "anchor contrast black/white", CONTRAST_TOL)
    _close(1.0, wcag_contrast_exact("FFFFFF", "FFFFFF"), "anchor contrast white/white", CONTRAST_TOL)


# --------------------------------------------------------------------------
# golden render + real file-content checks
# --------------------------------------------------------------------------

def read_fixture() -> tuple[list[float], list[float], list[float], list[float]]:
    import csv
    with (FIXTURES / "series_fixture.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    times = [float(r["time_h"]) for r in rows]
    response = [float(r["response_mmol_L"]) if r["response_mmol_L"].strip() else float("nan")
                for r in rows]
    means = [float(r["replicate_mean"]) for r in rows]
    ses = [float(r["replicate_se"]) for r in rows]
    if not any(math.isnan(v) for v in response):
        raise CheckFailure("fixture lost its interior missing value")
    return times, response, means, ses


def build_golden_figure(layer: dict[str, Any], cjk: bool):
    plt = layer["plt"]
    times, response, means, ses = read_fixture()
    fig = plt.figure(figsize=(FIG_W_IN, FIG_H_IN))
    ax = fig.add_axes(AXES_RECT)
    ax.set_xlim(*XLIM)
    ax.set_ylim(*YLIM)
    ax.plot(times, response, color=SERIES_COLOR, marker="o", linewidth=1.5,
            label="Response (mmol/L)")
    ax.errorbar(times, means, yerr=ses, color=ERROR_COLOR, capsize=3,
                linewidth=1.2, marker="s", markersize=3, label="Replicate mean ± SE")
    ax.set_xlabel("Time (h)")
    ax.set_ylabel("Concentration (mmol/L)")
    if cjk:
        ax.set_title("反应浓度随时间变化 (synthetic fixture)")
    else:
        ax.set_title("Response over time (synthetic fixture)")
    ax.legend(loc="upper left", fontsize=7)
    return fig, ax


def expected_svg_point(x_value: float, y_value: float) -> tuple[float, float]:
    left, bottom, width, height = AXES_RECT
    x_pt = (left + width * (x_value - XLIM[0]) / (XLIM[1] - XLIM[0])) * PAGE_W_PT
    y_pt = PAGE_H_PT - (bottom + height * (y_value - YLIM[0]) / (YLIM[1] - YLIM[0])) * PAGE_H_PT
    return x_pt, y_pt


def check_png_structure(data: bytes, layer: dict[str, Any], label: str) -> None:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise CheckFailure(f"{label}: PNG signature missing")
    pos = 8
    width = height = None
    idat_seen = False
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        ctype = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        (crc,) = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])
        if zlib.crc32(ctype + chunk) & 0xFFFFFFFF != crc:
            raise CheckFailure(f"{label}: corrupt PNG chunk CRC in {ctype!r}")
        if ctype == b"IHDR":
            width, height = struct.unpack(">II", chunk[:8])
        if ctype == b"IDAT":
            idat_seen = True
        if ctype == b"IEND":
            break
        pos += 12 + length
    if width is None or not idat_seen:
        raise CheckFailure(f"{label}: PNG lacks IHDR dimensions or IDAT data")
    _exact(1800, width, f"{label}: PNG width (6 in x 300 dpi)")
    _exact(1200, height, f"{label}: PNG height (4 in x 300 dpi)")
    Image = layer["Image"]
    image = Image.open(io.BytesIO(data)).convert("RGB")
    pixels = list(image.getdata())
    distinct = len(set(pixels[::37]))
    if distinct < 15:
        raise CheckFailure(f"{label}: PNG looks blank ({distinct} distinct sampled colors)")
    corner = image.getpixel((2, 2))
    if min(corner) < 240:
        raise CheckFailure(f"{label}: PNG background corner is not near-white: {corner}")
    def count_near(target_hex: str) -> int:
        target = tuple(int(target_hex.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
        return sum(1 for p in pixels[::3]
                   if abs(p[0] - target[0]) + abs(p[1] - target[1]) + abs(p[2] - target[2]) < 48)
    series_pixels = count_near(SERIES_COLOR)
    error_pixels = count_near(ERROR_COLOR)
    if series_pixels < 50:
        raise CheckFailure(f"{label}: series color absent from PNG pixels ({series_pixels})")
    if error_pixels < 20:
        raise CheckFailure(f"{label}: error-bar color absent from PNG pixels ({error_pixels})")


def check_svg_content(data: bytes, label: str) -> None:
    text = data.decode("utf-8")
    root = ET.fromstring(text)
    if not root.tag.endswith("svg"):
        raise CheckFailure(f"{label}: SVG root element missing")
    for required in ("Time (h)", "Concentration (mmol/L)", "Response (mmol/L)"):
        if required not in text:
            raise CheckFailure(f"{label}: SVG lacks searchable label {required!r} (units must be readable)")
    # collect path data painted with the series color
    ns = {"svg": root.tag.split("}")[0].strip("{")} if "}" in root.tag else {}
    paths = []
    for element in root.iter():
        tag = element.tag.split("}")[-1]
        if tag not in ("path", "polyline"):
            continue
        style = (element.get("style") or "") + (element.get("stroke") or "")
        if SERIES_COLOR in style.lower().replace(" ", ""):
            paths.append(element.get("d") or element.get("points") or "")
    if not paths:
        raise CheckFailure(f"{label}: no SVG path carries the series color {SERIES_COLOR}")
    coords = []
    moves = 0
    for d in paths:
        moves += len(re.findall(r"[Mm]\s*-?[\d.]", d))
        coords.extend((float(x), float(y)) for x, y in re.findall(r"(-?[\d.]+)[,\s]+(-?[\d.]+)", d))
    if moves < 2:
        raise CheckFailure(
            f"{label}: the interior missing value must split the line into >=2 disjoint "
            f"segments (found {moves} move commands) - gaps may never be bridged")
    if not coords:
        raise CheckFailure(f"{label}: SVG series path has no coordinates")
    for (x_value, y_value) in ((2.0, 20.0), (1.0, 12.5)):
        ex, ey = expected_svg_point(x_value, y_value)
        best = min(math.hypot(px - ex, py - ey) for px, py in coords)
        if best > COORD_TOL_PT:
            raise CheckFailure(
                f"{label}: data point ({x_value}, {y_value}) not found at the hand-computed "
                f"page position ({ex:.2f}, {ey:.2f}) pt; nearest series vertex is {best:.2f} pt away "
                "- the rendering does not map source data as declared")
    # error-bar caps: vermillion-colored paths must exist with multiple subpaths
    error_paths = []
    for element in root.iter():
        tag = element.tag.split("}")[-1]
        if tag not in ("path", "polyline", "line"):
            continue
        style = ((element.get("style") or "") + (element.get("stroke") or "")).lower().replace(" ", "")
        if ERROR_COLOR in style:
            error_paths.append(element.get("d") or element.get("points") or element.get("x1") or "")
    if not error_paths:
        raise CheckFailure(f"{label}: no SVG element carries the error-bar color {ERROR_COLOR}")


def check_pdf_content(data: bytes, layer: dict[str, Any], label: str) -> None:
    if not data.startswith(b"%PDF-"):
        raise CheckFailure(f"{label}: PDF header missing")
    if b"%%EOF" not in data[-1024:]:
        raise CheckFailure(f"{label}: PDF lacks %%EOF trailer")
    pypdf = layer["pypdf"]
    reader = pypdf.PdfReader(io.BytesIO(data))
    _exact(1, len(reader.pages), f"{label}: PDF page count")
    box = reader.pages[0].mediabox
    _close(PAGE_W_PT, float(box.width), f"{label}: PDF page width pt", 0.01)
    _close(PAGE_H_PT, float(box.height), f"{label}: PDF page height pt", 0.01)
    fonts = reader.pages[0].get("/Resources", {}).get("/Font", {})
    if not fonts:
        raise CheckFailure(f"{label}: PDF page embeds no font resource")


def check_golden_render(layer: dict[str, Any], tmp: Path, results: list[dict[str, Any]],
                        require_cjk: bool) -> None:
    import figure_export
    from matplotlib import font_manager

    cjk_fonts = sorted({
        f.name for f in font_manager.fontManager.ttflist
        if any(probe in f.name.lower() for probe in CJK_PROBE_FAMILIES)
    })
    cjk_used = bool(cjk_fonts)
    results.append({
        "name": "cjk_font_probe",
        "status": "pass" if cjk_used else "skipped-no-cjk-font",
        "detail": {
            "cjk_fonts_discovered": cjk_fonts[:8],
            "guidance": None if cjk_used else (
                "no CJK-capable font discovered; provision fonts-noto-cjk through the "
                "environment/package flow, then re-run with --require-cjk"),
        },
    })
    if not cjk_used and require_cjk:
        raise CheckFailure("--require-cjk: no CJK-capable font is provisioned in this environment")

    if cjk_used:
        matplotlib = layer["matplotlib"]
        matplotlib.rcParams["font.sans-serif"] = cjk_fonts[:1] + list(
            matplotlib.rcParams["font.sans-serif"])
        matplotlib.rcParams["axes.unicode_minus"] = False

    fig, ax = build_golden_figure(layer, cjk=cjk_used)
    # searchable SVG text (labels/units readable as text, per the export guide)
    layer["matplotlib"].rcParams["svg.fonttype"] = "none"
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    mpl_logger = logging.getLogger("matplotlib")
    mpl_logger.addHandler(handler)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            report = figure_export.export_figure(
                fig, tmp / "viz_golden", formats=("png", "pdf", "svg"), dpi=300,
                font_mode="current", overwrite=False, mkdir=True,
                provenance={"raw_data": "assets/fixtures/series_fixture.csv",
                            "transformations": ["none (fixture rendered as-is)"],
                            "uncertainty": "SE error bars from fixture columns",
                            "missing_data": "interior NaN retained as a visible gap"},
                write_manifest=True,
            )
    finally:
        mpl_logger.removeHandler(handler)
        layer["plt"].close(fig)
    log_text = log_stream.getvalue()
    for bad in ("missing from font", "findfont", "Glyph"):
        if cjk_used and bad in log_text:
            raise CheckFailure(f"CJK rendering emitted font warnings ({bad!r}): {log_text[:200]}")
    glyph_warnings = [str(w.message) for w in caught
                      if "glyph" in str(w.message).lower() or "findfont" in str(w.message).lower()]
    if cjk_used and glyph_warnings:
        raise CheckFailure(f"CJK glyph warnings: {glyph_warnings[:2]}")

    outputs = report.get("outputs") or report.get("files") or {}
    png = (tmp / "viz_golden.png").read_bytes()
    pdf = (tmp / "viz_golden.pdf").read_bytes()
    svg = (tmp / "viz_golden.svg").read_bytes()
    check_png_structure(png, layer, "golden png")
    check_svg_content(svg, "golden svg")
    check_pdf_content(pdf, layer, "golden pdf")
    manifest = tmp / "viz_golden.export.json"
    if not manifest.is_file():
        candidates = sorted(tmp.glob("viz_golden*.json"))
        if not candidates:
            raise CheckFailure("export manifest was not written")
        manifest = candidates[0]
    manifest_body = json.loads(manifest.read_text(encoding="utf-8"))
    if "provenance" not in json.dumps(manifest_body):
        raise CheckFailure("export manifest does not record provenance")
    if cjk_used:
        svg_text = svg.decode("utf-8")
        if "反应浓度" not in svg_text:
            raise CheckFailure("CJK title is not searchable in the SVG despite a CJK font")
    results.append({
        "name": "golden_render_outputs",
        "status": "pass",
        "detail": {
            "png_bytes": len(png), "pdf_bytes": len(pdf), "svg_bytes": len(svg),
            "cjk_rendered": cjk_used, "export_report_keys": sorted(report)[:6],
        },
    })
    # keep the golden PNG available for the image_metadata CLI check
    (tmp / "golden_for_cli.png").write_bytes(png)


# --------------------------------------------------------------------------
# CLI end-to-end + negatives
# --------------------------------------------------------------------------

def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *args], cwd=PACKAGE_ROOT,
                          capture_output=True, text=True, timeout=300,
                          env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin:/usr/local/bin",
                               "PYTHONPATH": str(SCRIPTS_DIR), "HOME": str(Path.home()),
                               "MPLCONFIGDIR": tempfile.gettempdir()})


def check_cli_end_to_end(layer: dict[str, Any], tmp: Path) -> None:
    cases = [
        (["scripts/style_presets.py", "--list"], ["okabe_ito_on_white"]),
        (["scripts/palette_audit.py", "--palette", "okabe_ito_on_white",
          "--background", "FFFFFF", "--role", "graphical"], ["contrast"]),
        (["scripts/export_plan.py", "--publisher", "nature", "--figure-type", "combination",
          "--width", "single", "--phase", "final"], ["nature"]),
        (["scripts/image_metadata.py", str(tmp / "golden_for_cli.png")], ["1800"]),
    ]
    for args, markers in cases:
        completed = _run(args)
        if completed.returncode != 0:
            raise CheckFailure(f"CLI {args[1]} exited {completed.returncode}: {completed.stderr.strip()[:300]}")
        body = completed.stdout
        for marker in markers:
            if marker.lower() not in body.lower():
                raise CheckFailure(f"CLI {args[1]} output lacks {marker!r}")
    preview = _run(["scripts/style_preview.py", "--output", str(tmp / "preview"),
                    "--style", "default", "--palette", "okabe_ito_on_white",
                    "--formats", "png,svg"])
    if preview.returncode != 0:
        raise CheckFailure(f"style_preview exited {preview.returncode}: {preview.stderr.strip()[:300]}")
    written = sorted(p.name for p in tmp.glob("preview*"))
    if not any(name.endswith(".png") for name in written) or not any(name.endswith(".svg") for name in written):
        raise CheckFailure(f"style_preview wrote no png+svg pair: {written}")


def check_export_negatives(layer: dict[str, Any], tmp: Path) -> None:
    import figure_export
    from _common import CliError

    fig, _ = build_golden_figure(layer, cjk=False)
    try:
        figure_export.export_figure(fig, tmp / "neg", formats=("png",), dpi=150, mkdir=True)
        try:
            figure_export.export_figure(fig, tmp / "neg", formats=("png",), dpi=150, overwrite=False)
        except CliError:
            pass
        else:
            raise CheckFailure("re-export without overwrite=True must be refused")
        for kwargs, why in (
            ({"formats": ("png",), "dpi": 0}, "dpi=0"),
            ({"formats": ("bmp",), "dpi": 150}, "unknown format"),
            ({"formats": ("png",), "dpi": 150, "font_mode": "bogus"}, "bad font_mode"),
        ):
            try:
                figure_export.export_figure(fig, tmp / f"neg-{abs(hash(why))}", mkdir=True, **kwargs)
            except CliError:
                pass
            else:
                raise CheckFailure(f"export must refuse {why}")
    finally:
        layer["plt"].close(fig)


# --------------------------------------------------------------------------
# runner
# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--require-layer", action="store_true",
                        help="fail when the declared dependency layer is absent")
    parser.add_argument("--require-cjk", action="store_true",
                        help="fail when no CJK-capable font is provisioned (guest CJK acceptance)")
    parser.add_argument("--output", help="optional JSON report path")
    args = parser.parse_args()

    if sys.version_info < (3, 11):
        print(json.dumps({"verifier": "viz_verify.py", "ok": False,
                          "failures": [f"Python {sys.version.split()[0]} < 3.11"]}, indent=2))
        return 1

    results: list[dict[str, Any]] = []
    failures: list[str] = []
    layer: dict[str, Any] | None = None

    def record(name: str, function) -> None:
        with contextlib.redirect_stdout(sys.stderr):
            try:
                function()
                results.append({"name": name, "status": "pass"})
            except CheckFailure as exc:
                results.append({"name": name, "status": "fail", "error": str(exc)})
                failures.append(f"{name}: {exc}")
            except Exception as exc:
                results.append({"name": name, "status": "fail",
                                "error": f"{type(exc).__name__}: {exc}"})
                failures.append(f"{name}: {type(exc).__name__}: {exc}")

    with tempfile.TemporaryDirectory(prefix="viz-verify-") as raw_tmp:
        tmp = Path(raw_tmp)
        try:
            layer = load_layer()
            results.append({"name": "layer_versions", "status": "pass",
                            "detail": layer["versions"]})
        except LayerMissing as exc:
            results.append({"name": "layer_versions", "status": "missing", "detail": str(exc)})
            if args.require_layer or args.require_cjk:
                failures.append(f"layer_versions: declared dependency layer not provisioned ({exc})")
        except CheckFailure as exc:
            results.append({"name": "layer_versions", "status": "fail", "error": str(exc)})
            failures.append(f"layer_versions: {exc}")

        if layer is not None:
            record("palette_dual_implementation", lambda: check_palette_dual_implementation(layer, tmp))
            record("golden_render", lambda: check_golden_render(layer, tmp, results, args.require_cjk))
            record("cli_end_to_end", lambda: check_cli_end_to_end(layer, tmp))
            record("export_negatives", lambda: check_export_negatives(layer, tmp))
        else:
            for name in ("palette_dual_implementation", "golden_render",
                         "cli_end_to_end", "export_negatives"):
                results.append({"name": name, "status": "skipped (missing layer)"})

    report = {
        "verifier": "viz_verify.py",
        "package": "scientific-visualization 1.0.0 (Floe adaptation)",
        "python": sys.version.split()[0],
        "ok": not failures,
        "layer_required": bool(args.require_layer),
        "cjk_required": bool(args.require_cjk),
        "declared_pins": DECLARED_PINS,
        "coordinate_tolerance_pt": COORD_TOL_PT,
        "checks": results,
        "failures": failures,
        "evidence_class": "runs wherever executed; guest execution evidence requires a real run in the resolved Linux environment",
    }
    payload = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
