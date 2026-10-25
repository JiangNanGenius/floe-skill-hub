#!/usr/bin/env python3
"""Bounded local document -> Markdown extraction for the Floe markitdown skill.

First-party Floe code (MIT (c) Floe project). The Microsoft MarkItDown pip
package is NOT bundled and NOT provisioned in the Floe guest; this module
implements the same goal (documents to Markdown for analysis/indexing) from
audited building blocks:

  * Python standard library for CSV/TSV/JSON/PPTX (zipfile + XML) and plain
    text passthrough;
  * openpyxl (declared pin 3.1.5) for XLSX;
  * pdfminer.six (declared pin 20221105) for extractable PDF text, with
    encrypted and text-less PDFs refused and routed to the existing NATIVE
    Floe surfaces (PDFKitGate-backed document.pdf tools, consented OCR) -
    protection is never bypassed here;
  * native-route refusals for DOCX/HTML/RTF (document.convert) so this skill
    never becomes a second converter stack competing with the app's own
    verified conversion services.

Safety contract: bounded bytes/rows/members, root confinement, symlink and
traversal rejection, strict JSON (NaN/Infinity rejected), no network, no
macros, no plugins, no external services, atomic writes, overwrite refusal.
Converted content is untrusted data: it is returned/written as text and is
never executed or interpreted as instructions.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import stat
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path, PurePath
from typing import Any

MIB = 1024 * 1024
DEFAULT_MAX_BYTES = 64 * MIB
HARD_MAX_BYTES = 512 * MIB
MAX_MD_ROWS = 2_000          # markdown table row bound per sheet/file
MAX_MD_COLS = 256
MAX_JSON_BYTES = 16 * MIB
MAX_ZIP_MEMBERS = 4_096
MAX_ZIP_RATIO = 100.0
MAX_ZIP_UNCOMPRESSED = 256 * MIB
MAX_PDF_PAGES = 500
SCANNED_PDF_CHARS_PER_PAGE = 20   # below this average -> probable scan
MAX_CELL_CHARS = 100_000

NATIVE_ROUTES = {
    ".docx": "document.convert (input .docx -> markdown/docx/html/rtf/text); legacy .doc is unsupported natively too",
    ".html": "document.convert (input .html -> markdown/...)",
    ".htm": "document.convert (input .htm -> markdown/...)",
    ".rtf": "document.convert (input .rtf -> markdown/...)",
    ".doc": "NOT supported: legacy .doc has no native or guest route; ask the user for a .docx/.pdf export",
    ".xls": "NOT supported in the guest layer; native document.pdf.convert accepts .xlsx only - ask for an .xlsx re-save",
    ".epub": "NOT supported in this release",
    ".msg": "NOT supported in this release",
    ".ipynb": "NOT supported in this release (JSON source; read it as .json via the workspace tools if needed)",
}
IMAGE_ROUTE = ("images are not document-converted; use the native image.ocr / image.inspect "
               "tools for text extraction instead")
AUDIO_ROUTE = "audio/video transcription is NOT supported; no external transcription service is ever invoked"

SUPPORTED_GUEST_FORMATS = (".csv", ".tsv", ".json", ".xlsx", ".pptx", ".pdf", ".txt", ".md", ".markdown")


class ConversionError(ValueError):
    """An expected conversion refusal with an actionable, value-free message."""


# --------------------------------------------------------------------------
# safety helpers (same contract family as the bundled EDA core)
# --------------------------------------------------------------------------

def _reject_url_and_traversal(value: str) -> None:
    stripped = value.strip()
    lowered = stripped.lower()
    if not stripped:
        raise ConversionError("path must not be empty")
    if "\x00" in value:
        raise ConversionError("path must not contain a NUL byte")
    if "://" in lowered or lowered.startswith(
            ("http:", "https:", "ftp:", "s3:", "gs:", "file:", "data:")):
        raise ConversionError("URLs are not accepted; provide a local workspace path")
    if stripped.startswith("~"):
        raise ConversionError("home-directory expansion is not accepted")
    if ".." in PurePath(stripped).parts:
        raise ConversionError("parent-directory traversal is not accepted")


def checked_root(value: str | os.PathLike[str]) -> Path:
    raw = os.fspath(value)
    _reject_url_and_traversal(raw)
    supplied = Path(os.path.abspath(raw))
    if supplied.is_symlink():
        raise ConversionError("the root directory must not be a symlink")
    try:
        root = supplied.resolve(strict=True)
        info = root.stat()
    except OSError as exc:
        raise ConversionError("the root directory is not accessible") from exc
    if not stat.S_ISDIR(info.st_mode):
        raise ConversionError("the root must be an existing directory")
    return root


def checked_input_file(value: str | os.PathLike[str], *, root: str | os.PathLike[str],
                       max_bytes: int = DEFAULT_MAX_BYTES,
                       suffixes: tuple[str, ...] | None = None) -> Path:
    max_bytes = min(int(max_bytes), HARD_MAX_BYTES)
    raw = os.fspath(value)
    _reject_url_and_traversal(raw)
    root_path = checked_root(root)
    path = Path(raw)
    if not path.is_absolute():
        path = root_path / path
    path = Path(os.path.abspath(os.fspath(path)))
    if path.is_symlink():
        raise ConversionError("the input must not be a symlink")
    try:
        resolved = path.resolve(strict=True)
        info = resolved.stat()
    except OSError as exc:
        raise ConversionError("the input file is not accessible") from exc
    try:
        resolved.relative_to(root_path)
    except ValueError as exc:
        raise ConversionError("path escapes the declared root directory") from exc
    if not stat.S_ISREG(info.st_mode):
        raise ConversionError("the input must be a regular file")
    if info.st_nlink != 1:
        raise ConversionError("multiply linked input files are not accepted")
    if info.st_size > max_bytes:
        raise ConversionError(
            f"the input is {info.st_size} bytes; the configured limit is {max_bytes}")
    if suffixes is not None and not resolved.name.lower().endswith(suffixes):
        raise ConversionError(f"the input suffix must be one of: {', '.join(sorted(suffixes))}")
    return resolved


def checked_output_file(value: str | os.PathLike[str], *, root: str | os.PathLike[str],
                        force: bool = False) -> Path:
    raw = os.fspath(value)
    _reject_url_and_traversal(raw)
    root_path = checked_root(root)
    path = Path(raw)
    if not path.is_absolute():
        path = root_path / path
    path = Path(os.path.abspath(os.fspath(path)))
    if path.is_symlink():
        raise ConversionError("output symlinks are not accepted")
    try:
        parent = path.parent.resolve(strict=True)
    except OSError as exc:
        raise ConversionError("the output parent is not accessible") from exc
    try:
        parent.relative_to(root_path)
    except ValueError as exc:
        raise ConversionError("output escapes the declared root directory") from exc
    destination = parent / path.name
    if destination.exists():
        if destination.is_symlink() or not destination.is_file():
            raise ConversionError("the output exists but is not a regular file")
        if not force:
            raise ConversionError("refusing to overwrite an existing output (use --force)")
    return destination


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp",
                                         delete=False) as handle:
            handle.write(content)
            temporary = Path(handle.name)
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


# --------------------------------------------------------------------------
# markdown rendering helpers
# --------------------------------------------------------------------------

def _md_cell(value: Any, max_chars: int = 2000) -> str:
    if value is None:
        return ""
    text = str(value)
    if len(text) > max_chars:
        text = text[:max_chars] + "…[truncated]"
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", "<br>")


def render_markdown_table(header: list[str], rows: list[list[Any]], *,
                          truncated_note: str | None = None) -> str:
    lines = ["| " + " | ".join(_md_cell(h) for h in header) + " |",
             "| " + " | ".join("---" for _ in header) + " |"]
    for row in rows:
        cells = list(row) + [""] * (len(header) - len(row))
        lines.append("| " + " | ".join(_md_cell(c) for c in cells[:len(header)]) + " |")
    if truncated_note:
        lines.append("")
        lines.append(f"> {truncated_note}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# converters (each returns markdown text + warnings; never touches network)
# --------------------------------------------------------------------------

def convert_csv(path: Path, *, delimiter: str | None = None,
                max_rows: int = MAX_MD_ROWS) -> tuple[str, list[str]]:
    warnings: list[str] = []
    if delimiter is None:
        delimiter = "\t" if path.name.lower().endswith(".tsv") else ","
    previous = csv.field_size_limit()
    csv.field_size_limit(MAX_CELL_CHARS)
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle, delimiter=delimiter, strict=True)
            try:
                header = next(reader)
            except StopIteration:
                raise ConversionError("the table is empty") from None
            if len(header) > MAX_MD_COLS:
                raise ConversionError(f"the table exceeds the {MAX_MD_COLS}-column bound")
            rows: list[list[str]] = []
            truncated = False
            for index, row in enumerate(reader):
                if index >= max_rows:
                    truncated = True
                    break
                rows.append(row)
    except UnicodeError as exc:
        raise ConversionError("the file is not valid UTF-8 text") from exc
    except csv.Error as exc:
        raise ConversionError(f"the delimited text could not be parsed safely: {exc}") from exc
    finally:
        csv.field_size_limit(previous)
    if truncated:
        warnings.append(f"only the first {max_rows} data rows were converted (bounded prefix, not a sample)")
    note = warnings[-1] if truncated else None
    return render_markdown_table(header, rows, truncated_note=note), warnings


def convert_json(path: Path) -> tuple[str, list[str]]:
    size = path.stat().st_size
    if size > MAX_JSON_BYTES:
        raise ConversionError(f"JSON input exceeds the {MAX_JSON_BYTES}-byte bound")
    try:
        document = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_constant)
    except UnicodeError as exc:
        raise ConversionError("the file is not valid UTF-8 text") from exc
    except json.JSONDecodeError as exc:
        raise ConversionError(f"strict JSON parsing failed: {exc}") from exc
    rendered = json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False)
    return f"```json\n{rendered}\n```\n", []


def _reject_constant(name: str) -> float:
    raise ConversionError(f"JSON constant {name} is rejected (strict finite JSON only)")


def convert_txt(path: Path) -> tuple[str, list[str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeError as exc:
        raise ConversionError("the file is not valid UTF-8 text") from exc
    return text, ["plain-text passthrough: content copied unchanged, no conversion applied"]


def convert_xlsx(path: Path, *, max_rows: int = MAX_MD_ROWS) -> tuple[str, list[str]]:
    try:
        import openpyxl
    except ImportError as exc:
        raise ConversionError(
            "XLSX conversion needs the declared openpyxl layer (openpyxl==3.1.5, "
            "Debian guest package python3-openpyxl) provisioned through the Floe "
            "environment/package flow") from exc
    warnings: list[str] = []
    try:
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except zipfile.BadZipFile as exc:
        raise ConversionError("the file is not a valid XLSX (OOXML zip) package") from exc
    except Exception as exc:
        raise ConversionError(f"the workbook could not be opened safely: {type(exc).__name__}") from exc
    parts: list[str] = []
    formula_cells_without_cached_value = 0
    try:
        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
            parts.append(f"## Sheet: {sheet_name}")
            parts.append("")
            rows: list[list[Any]] = []
            truncated = False
            for row_index, row in enumerate(sheet.iter_rows(values_only=True)):
                if row_index >= max_rows + 1:
                    truncated = True
                    break
                values = list(row)
                rows.append(values)
            if not rows or all(all(v is None for v in r) for r in rows):
                parts.append("_(sheet is empty or its cells carry no readable values)_")
                parts.append("")
                continue
            header = [_md_cell(v) if v is not None else f"column_{i + 1}"
                      for i, v in enumerate(rows[0])]
            body = rows[1:]
            note = None
            if truncated:
                note = f"only the first {max_rows} data rows were converted (bounded prefix)"
                warnings.append(f"sheet {sheet_name!r}: {note}")
            parts.append(render_markdown_table(header, body, truncated_note=note))
            parts.append("")
    finally:
        workbook.close()
    # honesty pass: count formula cells whose cached value is absent (data_only
    # reads return None for them; they are NOT silently rendered as empty data)
    try:
        formulas_wb = openpyxl.load_workbook(path, read_only=True, data_only=False)
        try:
            values_wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            try:
                for sheet_name in formulas_wb.sheetnames:
                    f_sheet = formulas_wb[sheet_name]
                    v_sheet = values_wb[sheet_name]
                    v_iter = v_sheet.iter_rows(values_only=True)
                    for f_row in f_sheet.iter_rows(values_only=True):
                        v_row = next(v_iter, None)
                        for index, cell in enumerate(f_row):
                            if isinstance(cell, str) and cell.startswith("="):
                                cached = v_row[index] if v_row and index < len(v_row) else None
                                if cached is None:
                                    formula_cells_without_cached_value += 1
            finally:
                values_wb.close()
        finally:
            formulas_wb.close()
    except Exception:
        warnings.append("formula-presence cross-check could not run; empty cells may hide uncached formulas")
    if formula_cells_without_cached_value:
        warnings.append(
            f"{formula_cells_without_cached_value} formula cell(s) carry no cached value and render "
            "empty (data_only read); materialize values first (open in a spreadsheet app or use "
            "the native document.office.edit excel.recalculate flow)")
    if not parts:
        raise ConversionError("the workbook contains no sheets")
    return "\n".join(parts), warnings


_P_CONTENT_TYPES = "{http://schemas.openxmlformats.org/package/2006/content-types}"
_A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_P_NS = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
_R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def _zip_preflight(path: Path) -> None:
    """Reject encrypted, traversing, oversized or high-ratio OOXML members."""
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ConversionError("the file is not a valid bounded ZIP (OOXML) package") from exc
    if not members or len(members) > MAX_ZIP_MEMBERS:
        raise ConversionError(f"the package member count must be between 1 and {MAX_ZIP_MEMBERS}")
    total = 0
    for member in members:
        normalized = member.filename.replace("\\", "/")
        parts = PurePath(normalized).parts
        if (member.is_dir() or PurePath(normalized).is_absolute()
                or normalized.startswith("/") or ":" in normalized or ".." in parts):
            raise ConversionError("the package contains an invalid member path")
        if member.flag_bits & 0x1:
            raise ConversionError("encrypted package members are not accepted")
        total += member.file_size
        if total > MAX_ZIP_UNCOMPRESSED:
            raise ConversionError("the package declares too much uncompressed data")
        denominator = max(member.compress_size, 1)
        if member.file_size / denominator > MAX_ZIP_RATIO:
            raise ConversionError("the package compression ratio exceeds the safety limit")


def _slide_order_and_paths(archive: zipfile.ZipFile) -> list[tuple[str, str | None]]:
    """Return [(slide part, notes part or None)] in presentation order."""
    try:
        presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
        rels = ET.fromstring(archive.read("ppt/_rels/presentation.xml.rels"))
    except (KeyError, ET.ParseError) as exc:
        raise ConversionError("the PPTX lacks a readable presentation part") from exc
    rid_to_target = {}
    for relationship in rels.findall(f"{_REL_NS}Relationship"):
        rid = relationship.get("Id")
        target = relationship.get("Target")
        if rid and target:
            rid_to_target[rid] = target

    def normalize(target: str) -> str:
        target = target.lstrip("/")
        if not target.startswith("ppt/"):
            target = "ppt/" + target
        return target

    ordered: list[tuple[str, str | None]] = []
    sld_id_lst = presentation.find(f"{_P_NS}sldIdLst")
    if sld_id_lst is not None:
        for sld_id in sld_id_lst.findall(f"{_P_NS}sldId"):
            rid = sld_id.get(f"{_R_NS}id")
            target = rid_to_target.get(rid or "")
            if target:
                ordered.append((normalize(target), None))
    if not ordered:
        names = sorted(
            (n for n in archive.namelist()
             if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
            key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[-1]).group(1)))
        ordered = [(n, None) for n in names]
    if not ordered:
        raise ConversionError("the PPTX contains no slides")
    # attach notes slides through each slide's relationships
    resolved: list[tuple[str, str | None]] = []
    for slide_part, _ in ordered:
        notes_part = None
        rel_path = f"ppt/slides/_rels/{slide_part.rsplit('/', 1)[-1]}.rels"
        try:
            slide_rels = ET.fromstring(archive.read(rel_path))
            for relationship in slide_rels.findall(f"{_REL_NS}Relationship"):
                target = relationship.get("Target") or ""
                if "notesSlide" in target:
                    notes_part = "ppt/slides/" + target if not target.startswith("ppt/") else target
                    notes_part = os.path.normpath(notes_part).replace("\\", "/")
                    break
        except (KeyError, ET.ParseError):
            notes_part = None
        resolved.append((slide_part, notes_part))
    return resolved


def _paragraphs_of(root: ET.Element, *, exclude_tables: bool = False) -> list[str]:
    """Collect paragraph text; with exclude_tables, paragraphs inside a:tbl
    are skipped so table cells are rendered only by _tables_of (no duplicates)."""
    paragraphs: list[str] = []
    if exclude_tables:
        table_nodes = {id(t) for t in root.iter(f"{_A_NS}tbl")}
        for shape in root.iter(f"{_P_NS}sp"):
            for paragraph in shape.iter(f"{_A_NS}p"):
                runs = [t.text or "" for t in paragraph.iter(f"{_A_NS}t")]
                text = "".join(runs).strip()
                if text:
                    paragraphs.append(text)
        # sp-scoped iteration already excludes graphicFrame tables
        _ = table_nodes
        return paragraphs
    for paragraph in root.iter(f"{_A_NS}p"):
        runs = [t.text or "" for t in paragraph.iter(f"{_A_NS}t")]
        text = "".join(runs).strip()
        if text:
            paragraphs.append(text)
    return paragraphs


def _tables_of(root: ET.Element) -> list[str]:
    tables: list[str] = []
    for table in root.iter(f"{_A_NS}tbl"):
        rows: list[list[str]] = []
        for row in table.findall(f"{_A_NS}tr"):
            cells = []
            for cell in row.findall(f"{_A_NS}tc"):
                cells.append(" ".join(_paragraphs_of(cell)))
            rows.append(cells)
        if not rows:
            continue
        width = max(len(r) for r in rows)
        header = rows[0] + [""] * (width - len(rows[0]))
        tables.append(render_markdown_table(header, [r + [""] * (width - len(r)) for r in rows[1:]]))
    return tables


def convert_pptx(path: Path) -> tuple[str, list[str]]:
    if path.name.lower().endswith(".pptm"):
        raise ConversionError("macro-enabled presentations (.pptm) are never opened; macros are not executed")
    _zip_preflight(path)
    warnings: list[str] = []
    parts: list[str] = []
    with zipfile.ZipFile(path) as archive:
        for index, (slide_part, notes_part) in enumerate(_slide_order_and_paths(archive), start=1):
            try:
                slide_root = ET.fromstring(archive.read(slide_part))
            except (KeyError, ET.ParseError) as exc:
                warnings.append(f"slide {index}: unreadable part skipped ({slide_part})")
                continue
            parts.append(f"## Slide {index}")
            parts.append("")
            paragraphs = _paragraphs_of(slide_root, exclude_tables=True)
            if paragraphs:
                parts.append(paragraphs[0])
                parts.append("")
                for paragraph in paragraphs[1:]:
                    parts.append(f"- {paragraph}")
                parts.append("")
            else:
                parts.append("_(no extractable text on this slide; images and shapes are not described)_")
                parts.append("")
            for table in _tables_of(slide_root):
                parts.append(table)
                parts.append("")
            if notes_part:
                try:
                    notes_root = ET.fromstring(archive.read(notes_part))
                    notes = _paragraphs_of(notes_root)
                    # the notes placeholder often repeats the slide number field
                    notes = [n for n in notes if n.strip()]
                    if notes:
                        parts.append("**Speaker notes:**")
                        parts.append("")
                        parts.extend(f"> {n}" for n in notes)
                        parts.append("")
                except (KeyError, ET.ParseError):
                    warnings.append(f"slide {index}: notes part unreadable, skipped")
    return "\n".join(parts), warnings


def convert_pdf(path: Path, *, max_pages: int = MAX_PDF_PAGES) -> tuple[str, list[str]]:
    try:
        from pdfminer.high_level import extract_text
        from pdfminer.pdfpage import PDFPage
        from pdfminer.psparser import PSException
    except ImportError as exc:
        raise ConversionError(
            "PDF text extraction needs the declared pdfminer layer (pdfminer.six==20221105, "
            "Debian guest package python3-pdfminer) provisioned through the Floe "
            "environment/package flow; single PDFs can also use the NATIVE "
            "document.pdf.convert tool instead") from exc
    from pdfminer.pdfdocument import PDFEncryptionError
    from pdfminer.pdfparser import PDFSyntaxError

    protected_message = (
        "the PDF is encrypted/protected: guest extraction refuses it. Protected PDFs "
        "are handled ONLY by the existing native PDFKit surfaces (document.pdf.unlock "
        "with a saved credential reference, then document.pdf.convert); document "
        "protection is never bypassed here")
    warnings: list[str] = []
    try:
        with path.open("rb") as handle:
            page_count = sum(1 for _ in PDFPage.get_pages(handle, maxpages=max_pages + 1))
    except PDFEncryptionError as exc:
        raise ConversionError(protected_message) from exc
    except (PDFSyntaxError, PSException, OSError, ValueError) as exc:
        raise ConversionError(
            f"the file is not a readable PDF ({type(exc).__name__}); corrupted or "
            "non-PDF bytes are refused, never guessed") from exc
    if page_count == 0:
        raise ConversionError("the PDF contains no pages")
    if page_count > max_pages:
        raise ConversionError(f"the PDF exceeds the {max_pages}-page bound; split it first")
    try:
        text = extract_text(str(path), maxpages=max_pages)
    except PDFEncryptionError as exc:
        raise ConversionError(protected_message) from exc
    except (PDFSyntaxError, PSException, ValueError) as exc:
        raise ConversionError(f"PDF text extraction failed ({type(exc).__name__})") from exc
    pages = re.split(r"\f", text)
    # pdfminer terminates the last page with a form feed: keep exactly the
    # real page count so the receipt markers never invent an extra page
    if len(pages) > page_count and not pages[-1].strip():
        pages = pages[:page_count]
    parts: list[str] = []
    for number, page_text in enumerate(pages, start=1):
        parts.append(f"<!-- page {number} -->")
        parts.append("")
        parts.append(page_text.strip())
        parts.append("")
    body = "\n".join(parts).strip() + "\n"
    characters = sum(len(p.strip()) for p in pages)
    if page_count > 0 and characters / page_count < SCANNED_PDF_CHARS_PER_PAGE:
        raise ConversionError(
            f"the PDF yields almost no extractable text ({characters} chars over {page_count} "
            "page(s)): it is probably scanned/image-only. Scans route to the existing NATIVE "
            "OCR workflow (image.ocr, or document.pdf.edit searchableOCR with the user's "
            "explicit rasterization consent) - guest extraction never invents text")
    return body, warnings


# --------------------------------------------------------------------------
# routing
# --------------------------------------------------------------------------

@dataclass
class ConversionReceipt:
    source: str
    status: str                       # converted | native-route | unsupported | failed
    converter: str | None = None
    output: str | None = None
    source_sha256: str | None = None
    source_bytes: int | None = None
    output_sha256: str | None = None
    characters: int = 0
    source_preserved: bool | None = None
    native_route: str | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "status": self.status,
            "converter": self.converter,
            "output": self.output,
            "source_sha256": self.source_sha256,
            "source_bytes": self.source_bytes,
            "output_sha256": self.output_sha256,
            "characters": self.characters,
            "source_preserved": self.source_preserved,
            "native_route": self.native_route,
            "warnings": self.warnings,
            "error": self.error,
        }


def suffix_of(path: Path) -> str:
    name = path.name.lower()
    for suffix in sorted(SUPPORTED_GUEST_FORMATS + tuple(NATIVE_ROUTES) +
                         (".pptm", ".doc", ".xls", ".epub", ".msg", ".ipynb",
                          ".png", ".jpg", ".jpeg", ".gif", ".mp3", ".wav", ".mp4", ".m4a"),
                         key=len, reverse=True):
        if name.endswith(suffix):
            return suffix
    return ""


def engine_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    try:
        import openpyxl
        versions["openpyxl"] = str(openpyxl.__version__)
    except ImportError:
        versions["openpyxl"] = None
    try:
        import pdfminer
        versions["pdfminer.six"] = str(getattr(pdfminer, "__version__", "unknown"))
    except ImportError:
        versions["pdfminer.six"] = None
    return versions


def convert_file(input_path: Path, output_path: Path, *, max_rows: int = MAX_MD_ROWS) -> ConversionReceipt:
    """Convert one checked local file to Markdown; honest receipt, no guessing."""
    suffix = suffix_of(input_path)
    receipt = ConversionReceipt(source=input_path.name, status="failed")
    receipt.source_bytes = input_path.stat().st_size
    receipt.source_sha256 = sha256_file(input_path)
    try:
        if suffix in NATIVE_ROUTES:
            receipt.status = "native-route"
            receipt.native_route = NATIVE_ROUTES[suffix]
            receipt.error = None
            return receipt
        if suffix in (".png", ".jpg", ".jpeg", ".gif"):
            receipt.status = "native-route"
            receipt.native_route = IMAGE_ROUTE
            return receipt
        if suffix in (".mp3", ".wav", ".mp4", ".m4a"):
            receipt.status = "unsupported"
            receipt.native_route = AUDIO_ROUTE
            receipt.error = AUDIO_ROUTE
            return receipt
        if suffix == ".csv":
            markdown, warnings = convert_csv(input_path)
            converter = "stdlib csv"
        elif suffix == ".tsv":
            markdown, warnings = convert_csv(input_path, delimiter="\t")
            converter = "stdlib csv (tsv)"
        elif suffix == ".json":
            markdown, warnings = convert_json(input_path)
            converter = "stdlib json (strict)"
        elif suffix in (".txt", ".md", ".markdown"):
            markdown, warnings = convert_txt(input_path)
            converter = "plain-text passthrough"
        elif suffix == ".xlsx":
            markdown, warnings = convert_xlsx(input_path, max_rows=max_rows)
            converter = f"openpyxl {engine_versions().get('openpyxl')}"
        elif suffix == ".pptx":
            markdown, warnings = convert_pptx(input_path)
            converter = "stdlib zipfile+XML (OOXML pptx)"
        elif suffix == ".pdf":
            markdown, warnings = convert_pdf(input_path)
            converter = f"pdfminer.six {engine_versions().get('pdfminer.six')}"
        else:
            receipt.status = "unsupported"
            receipt.error = ("unsupported format; fail closed. Ask for the format/specification "
                             "or use the matching native Floe tool")
            return receipt
        if not markdown.strip():
            receipt.status = "failed"
            receipt.error = "conversion produced empty Markdown; the source may be image-only or corrupt"
            return receipt
        atomic_write_text(output_path, markdown)
        receipt.status = "converted"
        receipt.converter = converter
        receipt.output = output_path.name
        receipt.output_sha256 = sha256_file(output_path)
        receipt.characters = len(markdown)
        receipt.warnings = warnings
        receipt.source_preserved = sha256_file(input_path) == receipt.source_sha256
        receipt.error = None
        return receipt
    except ConversionError as exc:
        receipt.status = "failed"
        receipt.error = str(exc)
        receipt.source_preserved = sha256_file(input_path) == receipt.source_sha256
        return receipt
    except Exception as exc:  # keep batch semantics; record the exact failure type
        receipt.status = "failed"
        receipt.error = f"{type(exc).__name__}: unexpected conversion failure"
        receipt.source_preserved = sha256_file(input_path) == receipt.source_sha256
        return receipt
