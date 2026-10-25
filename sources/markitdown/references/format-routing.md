# Format routing and native-service basis (Floe markitdown adaptation)

First-party Floe reference. Tool names and semantics below were resolved from
the ACTIVE native source (Local/Worktrees/ios-pencil-live-20261019,
FloeAgent/FloeApp/Files/DocumentConversionTool.swift registrations and the
bundled floe-pdf/floe-office skill contracts) during adaptation on 2026-10-26 —
not invented. Verify against the current build before relying on details.

## Native surfaces (authoritative for their formats)

| Tool | Verified behavior at adaptation time |
|---|---|
| `document.convert` | Converts an existing workspace file between Markdown, DOCX, HTML, RTF and plain text using bundled offline libraries; inputs `.md/.markdown/.docx/.html/.rtf/.txt`; preserves semantic headings/lists/tables/emphasis/links and supported local images; writes a NEW file, never overwrites; reports conversion limitations; legacy `.doc` unsupported. |
| `document.pdf.convert` | MD/DOCX/XLSX/PPTX/HTML/RTF/TXT → paginated PDF (Office inputs via the shared pinned Office engine; optional `pages`, `includeInk`), and copy-permitted TEXT PDF → Markdown/DOCX/HTML/RTF/text. Extraction retains page order and searchable text, not layout/tables/images; image-only/scanned pages fail with an OCR-required message instead of silently disappearing. |
| `document.pdf.export` | Real searchable text (`text` or page-structured `json`) — prefer for text dumps; not a Word-layout conversion. |
| `document.pdf.inspect` / `document.pdf.render` | Page count/metadata/text queries; page images (`png`/`jpeg`) for visual verification. |
| `document.pdf.unlock` | Creates a new decrypted copy using a SAVED credential reference (`passwordRef`), verified by reopening; rejects signed files; plaintext passwords never enter arguments. This is the PDFKitGate-protected path. |
| `document.pdf.edit` `searchableOCR` | On-device Vision OCR rebuilding pages with a searchable text layer; requires the user's explicit rasterization consent; text may contain recognition errors. |
| `image.ocr` | OCR for images/photos (scans routed here). |
| `document.readSheet` | Read-only XLSX values as TSV for conversation use (not a Markdown-file producer). |
| `document.office.edit` `excel.recalculate` | Bounded verified recalculation of cached formula values (SUM/MIN/MAX/COUNT/AVERAGE, bounded IF/ROUND, cross-sheet refs, constant arithmetic) — the native way to materialize formula caches before guest XLSX extraction. |

## Guest surfaces (this package)

| Format | Engine | Declared pin (Debian 13 riscv64 apt identity) |
|---|---|---|
| `.xlsx` | openpyxl read-only, `data_only=True` + formula-presence cross-check | `openpyxl==3.1.5` (`python3-openpyxl` 3.1.5+dfsg) |
| `.pptx` | stdlib `zipfile` + `xml.etree` (presentation-order walk, tables, notes) | — (stdlib) |
| `.csv`/`.tsv` | stdlib `csv` strict | — |
| `.json` | stdlib `json` strict (NaN/Infinity rejected) | — |
| `.pdf` (extractable text) | pdfminer.six `extract_text`, page-accurate markers | `pdfminer.six==20221105` (`python3-pdfminer` 20221105+dfsg) |
| `.txt`/`.md` | byte-faithful passthrough | — |

Why the guest PDF path exists at all: native `document.pdf.convert` is the
recommended single-file route, but bounded batch/corpus work (e.g. the
literature-review workflow) runs entirely inside the task's Linux environment,
where a guest-side extractor keeps the pipeline in one write layer. The guest
path defers to native authority for everything it must not decide itself:
protection (refuse → `document.pdf.unlock`), scans (refuse → OCR flow), and
layout-faithful Office conversion (route → `document.convert`).

## Refusal semantics (receipt statuses)

- `converted` — Markdown written; digests + character count recorded; source re-hashed unchanged.
- `native-route` — guest declined; receipt names the exact native tool (DOCX/HTML/RTF via `document.convert`; PNG/JPEG/GIF via `image.ocr`; etc.). No guest output file is written.
- `unsupported` — no route in this release (audio/video, EPUB/MSG, legacy `.doc`/`.xls`, `.pptm`, unknown extensions). Fail closed; ask for a supported re-save.
- `failed` — bounded refusal with an actionable message (encrypted PDF, text-less PDF, corrupt bytes, strict-JSON violation, empty output). The exact failure type is recorded; content is never guessed.

## Explicitly NOT provided (first release)

- Microsoft MarkItDown package features we do not bundle: Outlook MSG, EPUB,
  Jupyter IPYNB, XLS (legacy), image LLM captioning, audio transcription
  (Google Web Speech), YouTube transcripts, Azure Document Intelligence /
  Content Understanding, plugins, MCP server.
- Any provider API key, paid service or network egress from guest scripts.
- Any bypass of document protection, encryption or consent-gated OCR.
- Layout-faithful Markdown (tables/columns from PDFs can interleave; verify
  against the source for critical structure).
