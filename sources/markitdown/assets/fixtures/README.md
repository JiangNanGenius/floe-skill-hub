# Bundled fixtures — markitdown (Floe adaptation)

All files here are SMALL SYNTHETIC fixtures authored for this Floe release
(first-party, MIT (c) Floe project). No third-party documents, no real
content. They were generated inside the Debian trixie development container
by the task-owned generator (exported to the lane evidence directory) using
openpyxl 3.1.5 / pypdf 5.4.0 and stdlib OOXML/PDF writers, so every byte is
reproducible from the recorded recipe.

- `sample.xlsx` — two sheets (`Data` with CJK header/cells, `测量` with
  numeric rows) and one formula cell (`=SUM(B2:B3)`) that openpyxl writes
  WITHOUT a cached value, exercising the honest empty-render + warning path.
- `sample.pptx` — handcrafted minimal-but-representative OOXML package:
  presentation.xml sldIdLst order, two slides (CJK title + bullets, an
  `a:tbl` table on slide 1, ASCII slide 2) and one speaker-notes part.
- `sample.pdf` — handcrafted 1-page PDF (Helvetica text "Floe synthetic PDF
  fixture 42" + second line), exercising pdfminer extraction and
  page-accurate markers.
- `notext.pdf` — same structure with an empty content stream: the
  scanned/image-only detection must refuse it and route to native OCR.
- `encrypted.pdf` — `sample.pdf` encrypted with pypdf (AES-256, user
  password `floe-fixture`; this password is PUBLIC fixture material, asserts
  the protected-PDF refusal path and that receipts never echo it).
- `sample.csv` / `sample.tsv` — CJK + numeric cells for table goldens.
- `sample.json` — nested strict-JSON document.
- `sample.txt` — UTF-8 plain text with a CJK line (passthrough golden).

Expected exact Markdown outputs for every fixture are embedded in
`scripts/md_verify.py`; native-route acceptance fixtures (DOCX etc.) ship
with the lane handoff instead, because those paths belong to the native
tools, not this package.
