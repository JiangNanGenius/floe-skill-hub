# Adaptation notes — markitdown 1.0.0 (Floe)

Upstream: K-Dense-AI/scientific-agent-skills `skills/markitdown` at commit
`593377bb048752abb0152deab9fbb1083a6087df` (MIT). This is the deepest
re-implementation of the five H4 skills: the upstream skill documents and
scripts against the Microsoft MarkItDown pip package (0.1.8) plus Azure/
OpenAI/Google external services, none of which is provisionable in the
Debian 13 riscv64 guest through the sanctioned environment/package flow,
and paid/provider-specific services are prohibited for this release.

## What was kept from upstream (ideas and safety patterns, with attribution)

- The routing-table presentation ("choose the right path"), the quality-check
  discipline (non-empty UTF-8, compare structure against source, record
  provenance, keep the original authoritative), the troubleshooting stance
  (explicit failure classes instead of silent fallbacks), and the untrusted-
  converted-text security model — restated in SKILL.md and
  references/conversion-security.md with attribution.
- The upstream MIT `batch_convert.py` SAFETY SKELETON: skip symlinks,
  preserve relative directories, `<source-name>.md` output naming, manifest
  with per-file status records, `--overwrite` protection, `--fail-fast`,
  byte caps and external-service refusal. Re-implemented first-party as
  `scripts/md_batch.py` around Floe's routing semantics (the upstream script
  imports the markitdown package at module top and cannot run here).

## Added (first-party Floe, MIT (c) Floe project)

- `scripts/md_converters.py` — bounded conversion core: stdlib CSV/TSV/JSON/
  TXT and PPTX (zipfile+ElementTree OOXML walk in true presentation order
  with tables and speaker notes), openpyxl XLSX (read-only, data_only plus a
  formula-presence honesty pass), pdfminer.six PDF text with page-accurate
  markers; full safety contract (root confinement, symlink/traversal/URL
  rejection, hard byte caps, zip-bomb preflight, strict JSON, atomic writes,
  overwrite refusal); refusal routing for protected PDFs (native
  `document.pdf.unlock`/PDFKitGate), text-less PDFs (native OCR flow),
  DOCX/HTML/RTF/images (native `document.convert`/`image.ocr`), audio
  (unsupported, never transcribed), macros (never opened); truthful receipts
  with recomputed digests and source-preservation flags.
- `scripts/md_convert.py` — single-file CLI with receipt (exit codes:
  0 converted / 4 native-route / 3 unsupported / 1 failed / 2 usage).
- `scripts/md_batch.py` — batch CLI with deterministic manifest.
- `scripts/md_verify.py` — golden verifier: exact-output goldens for every
  bundled fixture, refusal-path goldens (OCR routing, unlock routing with
  no password echo, NaN-JSON strictness), native-route receipt assertions,
  safety negatives, CLI exit codes, batch-manifest digest recomputation and
  a whole-run source-preservation re-hash. Declared-pin mismatch fails the
  receipt; missing layer skips honestly and `--require-layer` requires it.
- `assets/fixtures/*` + README — nine small synthetic fixtures (incl. a
  handcrafted PPTX, handcrafted PDFs and a pypdf-encrypted PDF whose
  password is public fixture material).
- `references/format-routing.md` — routing table grounded in the ACTIVE
  native source registrations (document.convert / document.pdf.convert /
  document.pdf.unlock / searchableOCR / image.ocr / readSheet /
  excel.recalculate), verified during adaptation, not invented.
- `references/conversion-security.md` — trust boundaries adapted from the
  upstream security guidance into Floe runtime terms.

## Excluded (audited, with reasons — recorded, not silently dropped)

- Upstream `scripts/batch_convert.py`, `scripts/convert_literature.py`,
  `scripts/inspect_installation.py` — all import the markitdown package
  (`from markitdown import MarkItDown`, `importlib.metadata.version("markitdown")`);
  unrunnable and misleading without it. Their durable value (batch safety
  skeleton, provenance-front-matter idea, installation inspection) is
  re-implemented or superseded by md_batch.py / receipts / md_verify.py.
  The literature-collection workflow lives in the literature-review skill.
- Upstream references `api_reference.md`, `file_formats.md`,
  `cloud_and_ocr.md`, `mcp_and_plugins.md`, `migration.md`, `workflows.md`,
  `security.md` — they document the Microsoft package's API, extras, plugin
  system, MCP server, Azure services and version migrations; shipping them
  would advertise interfaces this release does not have. Their security
  substance is restated first-party in conversion-security.md; format
  limits are restated in SKILL.md/format-routing.md.
- Microsoft MarkItDown `[all]`/per-format extras, `markitdown-ocr` plugin,
  `markitdown-mcp` server, Azure Document Intelligence / Content
  Understanding, OpenAI-compatible captioning, Google Web Speech audio
  transcription, YouTube transcription — prohibited or unprovisionable in
  this release; every one is explicitly listed as NOT provided.
