#!/usr/bin/env python3
"""Inspect figure/image metadata and screen it against explicit constraints.

The tool is network-free. Pillow is loaded only for raster inputs and pypdf is
loaded only for PDF inputs. A successful screen is not a journal-compliance
claim.

PNG density note: per the W3C PNG specification
(https://www.w3.org/TR/png-3/#11pHYs) the pHYs chunk stores density as an
INTEGER number of pixels per unit (unit byte 0 = unknown, 1 = metre). A metric
pHYs PNG therefore represents only densities k * 0.0254 dpi; writers round a
requested dpi to the nearest integer (matplotlib/Pillow write 300 dpi as
pHYs 11811 px/m, which decodes to the raw value 299.9994 dpi). When screening
a PNG whose decoded density is proven to be exactly such an integer-metric
pHYs value, DPI thresholds are compared in that same integer domain so this
encoding quantisation (at most half a step, 0.0127 dpi) is not reported as a
real density shortfall. A min threshold binds the lower of the two axes and a
max threshold the higher one. Proof requires a completed bounded scan to a
whole IDAT/IEND chunk with exactly one CRC-valid pHYs; a truncated or
budget-limited scan grants nothing. The reported dpi_x/dpi_y stay the raw
decoded values; everything else — effective DPI at an explicit target width,
non-PNG rasters, PNGs without proven integer-metric pHYs, absent/unknown-unit/
invalid metadata — keeps the previous strict comparison behaviour.
"""

from __future__ import annotations

import argparse
import math
import re
import struct
import sys
import warnings
import xml.etree.ElementTree as ET
import zlib
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

from _common import (
    MAX_INPUT_BYTES,
    CliError,
    checked_input_file,
    emit_json,
    positive_float,
    positive_int,
)

SCHEMA_VERSION = "1.0"
DEFAULT_MAX_PIXELS = 100_000_000
MAX_XML_ELEMENTS = 100_000
MAX_SVG_BYTES = 20 * 1024 * 1024
FORMAT_ALIASES = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "tif": "TIFF",
    "tiff": "TIFF",
    "svg": "SVG",
    "pdf": "PDF",
    "eps": "EPS",
    "ps": "PS",
    "png": "PNG",
    "webp": "WEBP",
}
VECTOR_SUFFIXES = {".svg", ".pdf", ".eps", ".ps"}
LENGTH_RE = re.compile(
    r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)"
    r"\s*(px|pt|pc|in|cm|mm)?\s*$"
)

# PNG pHYs density quantisation constants (exact rationals, no float drift).
# W3C PNG 11.4.3.6: pHYs is pixels per unit, unit byte 0 = unknown, 1 = metre;
# pixel counts are positive integers up to 2^31 - 1.
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_PHYS_LENGTH = 9
PNG_MAX_PX_PER_UNIT = 2**31 - 1
PNG_PHYS_SCAN_LIMIT_BYTES = 1 << 20
PX_PER_METRE_PER_DPI = Fraction(5000, 127)   # 1 dpi = 1/0.0254 px/m exactly
DPI_STEP_PER_PX_PER_METRE = Fraction(127, 5000)  # 1 px/m = 0.0254 dpi exactly


def quantise_dpi_to_pixels_per_metre(dpi: float) -> int:
    """Return the nearest integer pixels-per-metre for a DPI value.

    The comparison is exact: ``dpi`` enters as its precise IEEE-754 rational
    value. Ties round away from zero, matching the writer convention that
    produced real pHYs PNGs (Pillow encodes ``int(dpi / 0.0254 + 0.5)`` and
    matplotlib writes 300 dpi as pHYs 11811).
    """
    if not (math.isfinite(dpi) and dpi > 0):
        raise CliError("DPI value must be finite and greater than zero")
    return math.floor(Fraction(dpi) * PX_PER_METRE_PER_DPI + Fraction(1, 2))


def png_phys_pixels_per_metre(path: Path) -> tuple[int, int] | None:
    """Prove a PNG carries exactly one valid integer-metric pHYs chunk.

    Reads only bounded chunk headers/data before the first IDAT (or IEND) and
    verifies the pHYs CRC. Returns ``(px_x, px_y)`` only when the bounded scan
    reaches a whole IDAT/IEND chunk and exactly one well-formed pHYs chunk
    with length 9, unit byte 1 (metre) and both counts in 1..2^31-1 was seen.
    Any other case — not a PNG, missing pHYs, unknown unit, zero/huge counts,
    a duplicate later in the scan, truncated data, a chunk that does not fit
    the scan budget or the file, or a CRC mismatch — returns None, which
    leaves density screening on the previous strict path. Stopping early
    never proves the absence of a later duplicate, so an incomplete bounded
    scan grants nothing. This never raises.
    """
    try:
        with path.open("rb") as handle:
            if handle.read(8) != PNG_SIGNATURE:
                return None
            size = handle.seek(0, 2)
            handle.seek(8)
            scanned = 8
            found: tuple[int, int] | None = None
            while True:
                if scanned + 8 > size:
                    return None  # truncated before a complete next header
                header = handle.read(8)
                if len(header) != 8:
                    return None
                length = int.from_bytes(header[:4], "big")
                kind = header[4:8]
                chunk_bytes = 8 + length + 4
                if kind in {b"IDAT", b"IEND"}:
                    # pHYs is only defined before the first IDAT; only a whole
                    # terminator chunk proves the pre-IDAT region was scanned.
                    if scanned + chunk_bytes > size:
                        return None
                    return found
                # A chunk that exceeds the bound (or the file) before a whole
                # terminator leaves "exactly one pHYs" unproven, even if a
                # reading was already seen: a later duplicate could be in the
                # unexamined remainder.
                if (
                    scanned + chunk_bytes > PNG_PHYS_SCAN_LIMIT_BYTES
                    or length > PNG_PHYS_SCAN_LIMIT_BYTES
                    or scanned + chunk_bytes > size
                ):
                    return None
                if kind == b"pHYs":
                    if found is not None or length != PNG_PHYS_LENGTH:
                        return None  # duplicate or malformed pHYs: unproven
                    body = handle.read(length)
                    crc = handle.read(4)
                    if len(body) != length or len(crc) != 4:
                        return None
                    if zlib.crc32(kind + body) & 0xFFFFFFFF != int.from_bytes(crc, "big"):
                        return None  # CRC mismatch: corrupt metadata, unproven
                    px_x, px_y = struct.unpack(">II", body[0:8])
                    if body[8] != 1:
                        return None  # unit 0 (unknown) or reserved: unproven
                    if not (1 <= px_x <= PNG_MAX_PX_PER_UNIT and 1 <= px_y <= PNG_MAX_PX_PER_UNIT):
                        return None
                    found = (px_x, px_y)
                    scanned += chunk_bytes
                    continue
                # Any other pre-IDAT chunk: skip without buffering its body,
                # but keep the whole scan bounded.
                handle.seek(length + 4, 1)
                scanned += chunk_bytes
    except (OSError, ValueError, struct.error):
        return None


def _finite_number(value: Any) -> float | None:
    """Convert a scalar or rational-like value to a finite float."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _dpi_pair(value: Any) -> tuple[float | None, float | None]:
    """Normalize common Pillow DPI metadata representations."""
    if isinstance(value, (tuple, list)) and len(value) >= 2:
        return _finite_number(value[0]), _finite_number(value[1])
    scalar = _finite_number(value)
    return scalar, scalar


def _length_to_inches(value: str | None) -> tuple[float | None, str | None]:
    """Parse an SVG/CSS absolute length using the CSS 96 px/in convention."""
    if value is None:
        return None, None
    match = LENGTH_RE.match(value)
    if not match:
        return None, None
    number = float(match.group(1))
    unit = (match.group(2) or "px").lower()
    factors = {
        "px": 1.0 / 96.0,
        "pt": 1.0 / 72.0,
        "pc": 1.0 / 6.0,
        "in": 1.0,
        "cm": 1.0 / 2.54,
        "mm": 1.0 / 25.4,
    }
    if not math.isfinite(number) or number <= 0:
        raise CliError("SVG dimensions must be finite and greater than zero")
    return number * factors[unit], unit


def _base_metadata(path: Path) -> dict[str, Any]:
    info = path.stat()
    return {
        "path": str(path),
        "name": path.name,
        "suffix": path.suffix.lower(),
        "size_bytes": info.st_size,
    }


def inspect_raster(path: Path, *, max_pixels: int) -> dict[str, Any]:
    """Inspect a raster image with Pillow without decoding all pixel data."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise CliError(
            "Pillow is required for raster metadata; "
            "Pillow is provisioned through the Floe environment/package flow (declared pin pillow==11.1.0; Debian guest package python3-pil)"
        ) from exc

    previous_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = max_pixels
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                width, height = image.size
                if width * height > max_pixels:
                    raise CliError(
                        f"image has {width * height} pixels; "
                        f"limit is {max_pixels}"
                    )
                dpi_x, dpi_y = _dpi_pair(image.info.get("dpi"))
                icc = image.info.get("icc_profile")
                format_name = (image.format or path.suffix.lstrip(".")).upper()
                density_provenance: dict[str, Any] | None = None
                if (
                    format_name == "PNG"
                    and dpi_x is not None
                    and dpi_y is not None
                    and dpi_x > 0
                    and dpi_y > 0
                ):
                    phys = png_phys_pixels_per_metre(path)
                    if phys is not None:
                        px_x, px_y = phys
                        # Prove the decoded floats are exactly this integer
                        # metric encoding (Pillow computes px * 0.0254).
                        # Any mismatch (e.g. eXIf-linked density) leaves the
                        # density unproven and screening stays strict.
                        if float(dpi_x) == px_x * 0.0254 and float(dpi_y) == px_y * 0.0254:
                            density_provenance = {
                                "pixels_per_metre_x": px_x,
                                "pixels_per_metre_y": px_y,
                                "quantisation_step_dpi": float(DPI_STEP_PER_PX_PER_METRE),
                                "source": "png_pHYs_integer_metre",
                            }
                metadata = {
                    "format": format_name,
                    "kind": "raster",
                    "width_px": int(width),
                    "height_px": int(height),
                    "pixel_count": int(width * height),
                    "mode": image.mode,
                    "bands": list(image.getbands()),
                    "has_alpha": "A" in image.getbands()
                    or "transparency" in image.info,
                    "frames": int(getattr(image, "n_frames", 1)),
                    "dpi_x": dpi_x,
                    "dpi_y": dpi_y,
                    "density_provenance": density_provenance,
                    "width_mm_from_metadata": (
                        width / dpi_x * 25.4 if dpi_x and dpi_x > 0 else None
                    ),
                    "height_mm_from_metadata": (
                        height / dpi_y * 25.4 if dpi_y and dpi_y > 0 else None
                    ),
                    "icc_profile_present": bool(icc),
                    "icc_profile_bytes": len(icc) if isinstance(icc, bytes) else 0,
                    "compression": image.info.get("compression"),
                    "exif_present": bool(image.info.get("exif")),
                }
                image.verify()
                return metadata
    except Image.DecompressionBombWarning as exc:
        raise CliError(f"image exceeds safe pixel limits: {exc}") from exc
    except Image.DecompressionBombError as exc:
        raise CliError(f"image exceeds safe pixel limits: {exc}") from exc
    except OSError as exc:
        raise CliError(f"Pillow could not inspect {path}: {exc}") from exc
    finally:
        Image.MAX_IMAGE_PIXELS = previous_limit


def inspect_svg(path: Path) -> dict[str, Any]:
    """Inspect SVG dimensions and resource types with bounded XML parsing."""
    if path.stat().st_size > MAX_SVG_BYTES:
        raise CliError(
            f"SVG is {path.stat().st_size} bytes; limit is {MAX_SVG_BYTES} bytes"
        )
    try:
        payload = path.read_bytes()
        if re.search(br"<!ENTITY\b", payload, flags=re.IGNORECASE) or re.search(
            br"<!DOCTYPE[^>]*\[", payload, flags=re.IGNORECASE | re.DOTALL
        ):
            raise CliError("SVG internal DTD/entity declarations are not allowed")
        root = ET.fromstring(payload)
    except (ET.ParseError, OSError) as exc:
        raise CliError(f"invalid SVG/XML input: {exc}") from exc

    if root.tag not in {"svg", "{http://www.w3.org/2000/svg}svg"}:
        raise CliError("XML root must be an SVG element")
    width_raw = root.get("width")
    height_raw = root.get("height")
    width_in, width_unit = _length_to_inches(width_raw)
    height_in, height_unit = _length_to_inches(height_raw)
    viewbox_raw = root.get("viewBox")
    viewbox: list[float] | None = None
    if viewbox_raw:
        try:
            values = [float(item) for item in re.split(r"[\s,]+", viewbox_raw.strip())]
        except ValueError:
            values = []
        if len(values) == 4 and all(math.isfinite(item) for item in values):
            viewbox = values

    element_count = 0
    text_count = 0
    image_count = 0
    external_images = 0
    for element in root.iter():
        element_count += 1
        if element_count > MAX_XML_ELEMENTS:
            raise CliError(
                f"SVG has more than {MAX_XML_ELEMENTS} elements; refusing input"
            )
        local_name = element.tag.rsplit("}", 1)[-1].lower()
        if local_name == "text":
            text_count += 1
        elif local_name == "image":
            image_count += 1
            href = (
                element.get("href")
                or element.get("{http://www.w3.org/1999/xlink}href")
                or ""
            )
            if href and not href.startswith("data:"):
                external_images += 1

    return {
        "format": "SVG",
        "kind": "vector",
        "width_raw": width_raw,
        "height_raw": height_raw,
        "width_unit": width_unit,
        "height_unit": height_unit,
        "width_mm": width_in * 25.4 if width_in is not None else None,
        "height_mm": height_in * 25.4 if height_in is not None else None,
        "viewbox": viewbox,
        "dpi_x": None,
        "dpi_y": None,
        "mode": None,
        "element_count": element_count,
        "text_element_count": text_count,
        "image_element_count": image_count,
        "external_image_count": external_images,
        "note": (
            "SVG is resolution-independent except for embedded raster images; "
            "external image resources were counted but not fetched."
        ),
    }


def _pdf_font_report(page: Any) -> dict[str, Any]:
    """Return a conservative first-page PDF font resource report."""
    try:
        resources = page.get("/Resources")
        resources = resources.get_object() if resources else None
        fonts = resources.get("/Font") if resources else None
        fonts = fonts.get_object() if fonts else None
    except Exception:
        fonts = None
    if not fonts:
        return {
            "resource_count": 0,
            "embedded_count": 0,
            "unembedded_count": 0,
            "unknown_count": 0,
            "all_embedded": None,
            "fonts": [],
        }

    def embedded_status(font: Any) -> bool | None:
        try:
            subtype = str(font.get("/Subtype", ""))
            if subtype == "/Type3":
                # Type 3 glyph programs live in the PDF CharProcs dictionary.
                return True if font.get("/CharProcs") else None
            candidates = [font]
            descendants = font.get("/DescendantFonts")
            if descendants:
                candidates.extend(
                    reference.get_object() for reference in descendants
                )
            saw_descriptor = False
            for candidate in candidates:
                descriptor = candidate.get("/FontDescriptor")
                descriptor = descriptor.get_object() if descriptor else None
                if descriptor:
                    saw_descriptor = True
                    if any(
                        descriptor.get(key)
                        for key in ("/FontFile", "/FontFile2", "/FontFile3")
                    ):
                        return True
            return False if saw_descriptor else None
        except Exception:
            return None

    records: list[dict[str, Any]] = []
    for resource_name, reference in fonts.items():
        try:
            font = reference.get_object()
            embedded = embedded_status(font)
            records.append(
                {
                    "resource": str(resource_name),
                    "base_font": str(font.get("/BaseFont", "")),
                    "subtype": str(font.get("/Subtype", "")),
                    "embedded": embedded,
                }
            )
        except Exception:
            records.append(
                {
                    "resource": str(resource_name),
                    "base_font": "",
                    "subtype": "",
                    "embedded": None,
                }
            )
    definite = [item["embedded"] for item in records if item["embedded"] is not None]
    unknown_count = sum(item["embedded"] is None for item in records)
    return {
        "resource_count": len(records),
        "embedded_count": sum(item is True for item in definite),
        "unembedded_count": sum(item is False for item in definite),
        "unknown_count": unknown_count,
        "all_embedded": (
            None
            if not definite or unknown_count
            else all(item is True for item in definite)
        ),
        "fonts": records,
        "scope": "first page resource dictionary only",
    }


def inspect_pdf(path: Path) -> dict[str, Any]:
    """Inspect PDF page dimensions and first-page font resources with pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise CliError(
            "pypdf is required for PDF metadata; "
            "pypdf is provisioned through the Floe environment/package flow (declared pin pypdf==5.4.0; Debian guest package python3-pypdf)"
        ) from exc
    try:
        reader = PdfReader(path, strict=False)
        if reader.is_encrypted:
            try:
                unlocked = reader.decrypt("")
            except Exception:
                unlocked = 0
            if not unlocked:
                return {
                    "format": "PDF",
                    "kind": "vector-container",
                    "encrypted": True,
                    "page_count": None,
                    "width_mm": None,
                    "height_mm": None,
                    "dpi_x": None,
                    "dpi_y": None,
                    "mode": None,
                    "font_resources": None,
                    "note": "Encrypted PDF could not be inspected without a password.",
                }
        page_count = len(reader.pages)
        if page_count < 1:
            raise CliError("PDF has no pages")
        page = reader.pages[0]
        width_pt = float(page.mediabox.width)
        height_pt = float(page.mediabox.height)
        user_unit = float(page.user_unit)
        rotation = int(page.rotation) % 360
        crop_width = float(page.cropbox.width)
        crop_height = float(page.cropbox.height)
        if rotation not in {0, 90, 180, 270} or not all(
            math.isfinite(value) and value > 0
            for value in (width_pt, height_pt, crop_width, crop_height, user_unit)
        ):
            raise CliError("PDF page dimensions, UserUnit, or rotation are invalid")
        display_width, display_height = width_pt * user_unit, height_pt * user_unit
        crop_width, crop_height = crop_width * user_unit, crop_height * user_unit
        if rotation in {90, 270}:
            display_width, display_height = display_height, display_width
            crop_width, crop_height = crop_height, crop_width
        return {
            "format": "PDF",
            "kind": "vector-container",
            "encrypted": bool(reader.is_encrypted),
            "page_count": page_count,
            "first_page_width_pt": width_pt,
            "first_page_height_pt": height_pt,
            "user_unit": user_unit,
            "rotation_degrees": rotation,
            "width_mm": display_width / 72.0 * 25.4,
            "height_mm": display_height / 72.0 * 25.4,
            "crop_width_mm": crop_width / 72.0 * 25.4,
            "crop_height_mm": crop_height / 72.0 * 25.4,
            "cropbox_differs_from_mediabox": list(page.cropbox) != list(page.mediabox),
            "dpi_x": None,
            "dpi_y": None,
            "mode": None,
            "font_resources": _pdf_font_report(page),
            "note": (
                "Dimensions use first-page MediaBox with UserUnit and rotation; "
                "CropBox dimensions are reported separately. Raw first_page_*_pt "
                "values are unscaled user coordinates. Page size and fonts do not establish the "
                "resolution of embedded raster images."
            ),
        }
    except CliError:
        raise
    except Exception as exc:
        raise CliError(f"pypdf could not inspect {path}: {exc}") from exc


def inspect_eps(path: Path) -> dict[str, Any]:
    """Inspect an EPS/PS bounding box without invoking PostScript."""
    size = path.stat().st_size
    with path.open("rb") as handle:
        prefix = handle.read(min(size, 128 * 1024))
        suffix = b""
        if size > len(prefix):
            handle.seek(max(0, size - 128 * 1024))
            suffix = handle.read(128 * 1024)
    text = (prefix + b"\n" + suffix).decode("latin-1", errors="replace")
    matches = re.findall(
        r"^%%(?:HiRes)?BoundingBox:\s+"
        r"([+-]?\d+(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)\s+"
        r"([+-]?\d+(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)\s*$",
        text,
        flags=re.MULTILINE,
    )
    bbox = [float(value) for value in matches[-1]] if matches else None
    width_pt = bbox[2] - bbox[0] if bbox else None
    height_pt = bbox[3] - bbox[1] if bbox else None
    return {
        "format": "EPS" if path.suffix.lower() == ".eps" else "PS",
        "kind": "vector-container",
        "bounding_box_pt": bbox,
        "width_mm": width_pt / 72.0 * 25.4 if width_pt is not None else None,
        "height_mm": (
            height_pt / 72.0 * 25.4 if height_pt is not None else None
        ),
        "dpi_x": None,
        "dpi_y": None,
        "mode": None,
        "note": "PostScript was not executed; only DSC bounding-box text was read.",
    }


def inspect_file(
    value: str | Path,
    *,
    max_bytes: int = MAX_INPUT_BYTES,
    max_pixels: int = DEFAULT_MAX_PIXELS,
) -> dict[str, Any]:
    """Inspect a supported local figure/image and return structured metadata."""
    path = checked_input_file(value, max_bytes=max_bytes)
    suffix = path.suffix.lower()
    if suffix == ".svg":
        metadata = inspect_svg(path)
    elif suffix == ".pdf":
        metadata = inspect_pdf(path)
    elif suffix in {".eps", ".ps"}:
        metadata = inspect_eps(path)
    else:
        metadata = inspect_raster(path, max_pixels=max_pixels)
    return {
        "schema_version": SCHEMA_VERSION,
        "input": _base_metadata(path),
        "metadata": metadata,
    }


def _normalize_formats(values: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        for item in value.split(","):
            name = item.strip().lower().lstrip(".")
            if not name:
                continue
            normalized.append(FORMAT_ALIASES.get(name, name.upper()))
    return sorted(set(normalized))


def _check(
    name: str,
    status: str,
    *,
    actual: Any,
    expected: Any,
    detail: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "actual": actual,
        "expected": expected,
        "detail": detail,
    }


def screen_metadata(
    report: dict[str, Any],
    *,
    expected_formats: Iterable[str] = (),
    expected_modes: Iterable[str] = (),
    min_dpi: float | None = None,
    max_dpi: float | None = None,
    min_width_px: int | None = None,
    max_width_px: int | None = None,
    min_height_px: int | None = None,
    max_height_px: int | None = None,
    max_file_bytes: int | None = None,
    target_width_mm: float | None = None,
    alpha_policy: str | None = None,
) -> dict[str, Any]:
    """Apply only caller-supplied constraints to an inspection report."""
    metadata = report["metadata"]
    checks: list[dict[str, Any]] = []

    formats = _normalize_formats(expected_formats)
    if formats:
        actual = str(metadata.get("format", "")).upper()
        checks.append(
            _check(
                "format",
                "pass" if actual in formats else "fail",
                actual=actual,
                expected=formats,
                detail="File format is compared with the explicit allow-list.",
            )
        )

    modes = sorted(
        {
            item.strip().upper()
            for value in expected_modes
            for item in value.split(",")
            if item.strip()
        }
    )
    if modes:
        actual_mode = metadata.get("mode")
        status = (
            "unknown"
            if actual_mode is None
            else ("pass" if str(actual_mode).upper() in modes else "fail")
        )
        checks.append(
            _check(
                "mode",
                status,
                actual=actual_mode,
                expected=modes,
                detail="Vector containers generally do not expose one image mode.",
            )
        )

    width_px = metadata.get("width_px")
    height_px = metadata.get("height_px")
    for name, actual, minimum, maximum in (
        ("width_px", width_px, min_width_px, max_width_px),
        ("height_px", height_px, min_height_px, max_height_px),
    ):
        if minimum is None and maximum is None:
            continue
        if actual is None:
            status = "unknown"
        elif minimum is not None and actual < minimum:
            status = "fail"
        elif maximum is not None and actual > maximum:
            status = "fail"
        else:
            status = "pass"
        checks.append(
            _check(
                name,
                status,
                actual=actual,
                expected={"min": minimum, "max": maximum},
                detail="Pixel dimensions are available for raster inputs.",
            )
        )

    dpi_x = metadata.get("dpi_x")
    dpi_y = metadata.get("dpi_y")
    effective_dpi = None
    if target_width_mm is not None and width_px is not None:
        effective_dpi = width_px / (target_width_mm / 25.4)
    actual_dpi = effective_dpi
    dpi_basis = "effective at target width"
    quantised_phys: tuple[int, int] | None = None
    if actual_dpi is None and dpi_x and dpi_y:
        actual_dpi = min(float(dpi_x), float(dpi_y))
        dpi_basis = "embedded metadata"
        provenance = metadata.get("density_provenance")
        if isinstance(provenance, dict) and provenance.get("source") == "png_pHYs_integer_metre":
            phys_x = provenance.get("pixels_per_metre_x")
            phys_y = provenance.get("pixels_per_metre_y")
            if (
                isinstance(phys_x, int)
                and isinstance(phys_y, int)
                and 1 <= phys_x <= PNG_MAX_PX_PER_UNIT
                and 1 <= phys_y <= PNG_MAX_PX_PER_UNIT
            ):
                quantised_phys = (phys_x, phys_y)
                dpi_basis = (
                    "embedded metadata (proven PNG integer-metric pHYs, "
                    "quantised integer comparison)"
                )
    if min_dpi is not None or max_dpi is not None:
        quantised_bounds: dict[str, Any] = {}
        if actual_dpi is None:
            status = "unknown"
        elif quantised_phys is not None:
            # PNG density is stored as integer pixels per metre, so the
            # representable densities are exactly the multiples of 0.0254 dpi.
            # Compare the proven integers: a min threshold is satisfied only
            # when BOTH axes are, so the lower axis binds it; a max threshold
            # is broken by EITHER axis, so the higher axis binds it. Relief is
            # exactly one half step (0.0127 dpi), never more; genuinely lower
            # or higher integer densities still fail. Effective DPI at an
            # explicit target width never takes this path.
            lower_px, upper_px = min(quantised_phys), max(quantised_phys)
            status = "pass"
            if min_dpi is not None:
                quantised_bounds["min"] = quantise_dpi_to_pixels_per_metre(min_dpi)
                if lower_px < quantised_bounds["min"]:
                    status = "fail"
            if max_dpi is not None:
                quantised_bounds["max"] = quantise_dpi_to_pixels_per_metre(max_dpi)
                if upper_px > quantised_bounds["max"]:
                    status = "fail"
        elif (
            min_dpi is not None
            and actual_dpi < min_dpi
            and not math.isclose(actual_dpi, min_dpi, rel_tol=1e-12, abs_tol=1e-9)
        ):
            status = "fail"
        elif (
            max_dpi is not None
            and actual_dpi > max_dpi
            and not math.isclose(actual_dpi, max_dpi, rel_tol=1e-12, abs_tol=1e-9)
        ):
            status = "fail"
        else:
            status = "pass"
        detail = (
            f"DPI basis: {dpi_basis}. Metadata DPI is not a quality "
            "measure; effective DPI depends on final physical size."
        )
        if quantised_phys is not None:
            px_x, px_y = quantised_phys
            detail = (
                f"DPI basis: {dpi_basis}. Reported dpi_x/dpi_y stay the raw "
                f"decoded values ({float(dpi_x)} / {float(dpi_y)}); the file "
                f"carries pHYs x={px_x}, y={px_y} integer pixels per metre "
                "(W3C PNG pHYs), so thresholds are compared in that exact "
                f"integer domain (threshold px/m: {quantised_bounds}); a min "
                "threshold binds the lower axis and a max threshold the higher "
                "axis. Relief equals the encoding half step (0.0127 dpi), not "
                "a quality tolerance; genuinely lower or higher densities "
                "still fail. Metadata DPI is not a quality measure; effective "
                "DPI depends on final physical size."
            )
        checks.append(
            _check(
                "dpi",
                status,
                actual=actual_dpi,
                expected={"min": min_dpi, "max": max_dpi},
                detail=detail,
            )
        )

    if max_file_bytes is not None:
        actual_bytes = report["input"]["size_bytes"]
        checks.append(
            _check(
                "file_size",
                "pass" if actual_bytes <= max_file_bytes else "fail",
                actual=actual_bytes,
                expected={"max": max_file_bytes},
                detail="File size is measured from the local input.",
            )
        )

    if alpha_policy is not None:
        if alpha_policy not in {"allow", "forbid", "require"}:
            raise CliError("alpha_policy must be allow, forbid, or require")
        has_alpha = metadata.get("has_alpha")
        if has_alpha is None:
            alpha_status = "unknown"
        elif alpha_policy == "allow":
            alpha_status = "pass"
        elif alpha_policy == "forbid":
            alpha_status = "pass" if not has_alpha else "fail"
        else:
            alpha_status = "pass" if has_alpha else "fail"
        checks.append(
            _check(
                "alpha",
                alpha_status,
                actual=has_alpha,
                expected=alpha_policy,
                detail=(
                    "Alpha is detected for raster modes/transparency metadata. "
                    "Vector transparency requires rendered-content inspection."
                ),
            )
        )

    counts = {
        status: sum(item["status"] == status for item in checks)
        for status in ("pass", "fail", "warning", "unknown")
    }
    screened = dict(report)
    screened["checks"] = checks
    screened["screening_summary"] = counts
    screened["notice"] = (
        "This deterministic metadata screen checks only the supplied constraints. "
        "It does not verify visual quality, scientific integrity, accessibility, "
        "embedded-raster resolution in vector files, or journal compliance."
    )
    return screened


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect local raster, SVG, PDF, EPS, or PS metadata and optionally "
            "screen it against explicit constraints. No network access is used."
        )
    )
    parser.add_argument("input", help="local figure/image file (symlinks rejected)")
    parser.add_argument(
        "--format",
        dest="formats",
        action="append",
        default=[],
        help="allowed format; repeat or use comma-separated values",
    )
    parser.add_argument(
        "--mode",
        dest="modes",
        action="append",
        default=[],
        help="allowed raster mode (for example RGB,L); repeat as needed",
    )
    parser.add_argument("--min-dpi", type=positive_float)
    parser.add_argument("--max-dpi", type=positive_float)
    parser.add_argument(
        "--target-width-mm",
        type=positive_float,
        help="calculate effective raster DPI at this final width",
    )
    parser.add_argument("--min-width-px", type=positive_int)
    parser.add_argument("--max-width-px", type=positive_int)
    parser.add_argument("--min-height-px", type=positive_int)
    parser.add_argument("--max-height-px", type=positive_int)
    parser.add_argument("--max-file-bytes", type=positive_int)
    parser.add_argument(
        "--alpha-policy",
        choices=("allow", "forbid", "require"),
        help="optional raster alpha/transparency screen",
    )
    parser.add_argument(
        "--max-input-bytes",
        type=positive_int,
        default=MAX_INPUT_BYTES,
        help=f"input byte limit (default: {MAX_INPUT_BYTES})",
    )
    parser.add_argument(
        "--max-pixels",
        type=positive_int,
        default=DEFAULT_MAX_PIXELS,
        help=f"raster pixel limit (default: {DEFAULT_MAX_PIXELS})",
    )
    parser.add_argument("--output", help="optional JSON report path")
    parser.add_argument(
        "--force", action="store_true", help="overwrite an existing JSON report"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        report = inspect_file(
            args.input,
            max_bytes=args.max_input_bytes,
            max_pixels=args.max_pixels,
        )
        report = screen_metadata(
            report,
            expected_formats=args.formats,
            expected_modes=args.modes,
            min_dpi=args.min_dpi,
            max_dpi=args.max_dpi,
            min_width_px=args.min_width_px,
            max_width_px=args.max_width_px,
            min_height_px=args.min_height_px,
            max_height_px=args.max_height_px,
            max_file_bytes=args.max_file_bytes,
            target_width_mm=args.target_width_mm,
            alpha_policy=args.alpha_policy,
        )
        emit_json(report, output=args.output, force=args.force)
        return 1 if report["screening_summary"]["fail"] else 0
    except CliError as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    sys.exit(main())
