# Provenance — markitdown (Floe adaptation, 1.0.0)

- Upstream repository: https://github.com/K-Dense-AI/scientific-agent-skills
- Pinned commit: `593377bb048752abb0152deab9fbb1083a6087df` (repository tree `d4d202beb151c1f1c6c15738be0692d65e0447af`; skill subtree `skills/markitdown` tree `7d881600bf4569374b505d3dd70ded616cafde19`, verified at fetch on 2026-10-26)
- Upstream path: `skills/markitdown`
- License: MIT (root `LICENSE.md` at the pinned commit, Copyright (c) 2025 K-Dense Inc.) — full text at references/licenses/UPSTREAM-LICENSE.txt; per-file audit in references/licenses/LICENSE-NOTE.md
- IMPORTANT character of this adaptation: NO upstream file bytes are shipped. The upstream skill documents and scripts target the Microsoft MarkItDown pip package (0.1.8) plus Azure/OpenAI/Google external services — none provisionable or permitted here. The upstream MIT material is used as GUIDANCE (routing-table presentation, quality-check discipline, untrusted-text security model, batch safety skeleton), restated/re-implemented first-party with attribution per MIT terms. Full reasoning per file in references/ADAPTATION-NOTES.md.
- Declared dependency layer (floe.json): openpyxl==3.1.5, pdfminer.six==20221105 — the exact versions the resolved Debian 13 (trixie) riscv64 guest provides as python3-openpyxl (3.1.5+dfsg-2) and python3-pdfminer (20221105+dfsg-1.1~deb13u1). Microsoft markitdown is NOT packaged in trixie and ad-hoc pip at chat time is prohibited; PPTX/CSV/TSV/JSON/TXT paths are pure stdlib.
- Native routing basis: tool names/semantics resolved from the ACTIVE native source (Local/Worktrees/ios-pencil-live-20261019: FloeAgent/FloeApp/Files/DocumentConversionTool.swift `DocumentConvertTool`/`PDFConvertTool` registrations and the bundled floe-pdf/floe-office contracts) on 2026-10-26 — recorded in references/format-routing.md.
- First-release version: 1.0.0 (no previously published id/version exists for this skill; registry versionTarget 1.0.0. The id `markitdown` is kept from the frozen registry row; the SKILL.md states plainly that the Microsoft package is not bundled).

## Host development evidence (NOT guest execution evidence)

Executed 2026-10-26 by the H4 lane, labeled by environment:

1. Debian trixie arm64 dev container (docker `floe-data-five-dev`; Python 3.13.5, openpyxl 3.1.5, pdfminer.six 20221105, pypdf 5.4.0 — identical package identities/versions to the guest pins; NOT the riscv64 guest): `python3 scripts/md_verify.py --require-layer` → exit 0, `"ok": true`, 9/9 checks: exact-output goldens for all seven convertible fixtures, refusal goldens (text-less PDF → native OCR routing; pypdf-encrypted PDF → native unlock routing with NO password echo; NaN JSON → strict rejection), native-route receipts (docx/html/rtf/png/mp3/unknown), safety negatives (symlink/out-of-root/byte-cap/overwrite), CLI exit codes (0/4/1/2), batch manifest digest recomputation + rerun skip semantics, whole-run fixture preservation re-hash.
2. Bare macOS venv (Python 3.12.13, stdlib only): `md_verify.py` → exit 0 ok:true with layer honestly `missing` and xlsx/pdf goldens `skipped (missing layer)` — stdlib PPTX/CSV/TSV/JSON/TXT/batch/CLI/safety checks all still ran and passed.
3. Fixtures were generated inside the same container by the task-owned generator (recipe exported to the lane evidence directory) using the pinned library versions, so fixture bytes are reproducible.

Two real converter bugs found and fixed by these goldens during adaptation: pdfminer's `PDFPasswordIncorrect` initially surfaced through the generic corrupt-PDF branch (now mapped to the protected-PDF native-unlock routing message at BOTH the page-count and extraction stages), and pdfminer's trailing form-feed initially produced a phantom extra `<!-- page N -->` marker (now clamped to the real page count). PPTX table cells initially duplicated as bullets (paragraph collection is now shape-scoped with tables excluded).

## GUEST-PENDING handoff for Main (exact steps; do not flip evidence without a real passing run)

In a task workspace in the resolved Linux environment, with this package installed/staged:

1. Provision through the existing environment/package flow (guest apt identities): `python3-openpyxl`, `python3-pdfminer`. No chat-time pip/uv.
2. `exec.shell`: `python3 scripts/md_verify.py --require-layer --output verify.json` → must exit 0 with `"ok": true`; verify.json records openpyxl 3.1.5 and pdfminer 20221105 base versions.
3. Real guest workload: stage one authorized XLSX and one extractable PDF, run
   `python3 scripts/md_convert.py data.xlsx --root . --output data.xlsx.md --receipt r1.json` and
   `python3 scripts/md_convert.py paper.pdf --root . --output paper.pdf.md --receipt r2.json` → both exit 0 with `source_preserved: true`; read outputs back with the workspace tools.
4. NATIVE acceptance (App side, Main-owned; fixtures in the lane evidence directory `native-fixtures/`):
   a. `document.convert` sample.docx → markdown: output must contain the fixture's exact heading/paragraph strings (incl. the CJK line); source unchanged.
   b. `document.pdf.convert` sample_native.pdf (extractable text) → markdown: contains "Floe native acceptance fixture 7"; scanned-page behavior verified with any image-only PDF → OCR-required failure, never invented text.
   c. Protected-PDF behavior: any password-protected PDF → the existing PDFKitGate/unlock flow (document.pdf.unlock with a saved credential reference), never a guest bypass.
5. Only after 2–4 pass in the actual guest/App may `plannedRuntime.execution.evidence` become `guest-verified` and `status.executionVerified` flip.

## File inventory (sha256, this checkout; PROVENANCE.md self-hash intentionally omitted)

- `SKILL.md` sha256 `d84d17a721acd293c5dc16662bd7e0f14a91aa417ab947be98fae02cc176813a` (10480 bytes)
- `assets/fixtures/README.md` sha256 `0829f754500485303d69f135e5592eb2abbc665ae00355fb24ad2df4f9c0f9b9` (1866 bytes)
- `assets/fixtures/encrypted.pdf` sha256 `a39c78aa39bd87e292e53e5a9cde8b9c0a4d960c75c620109e49aabf307a7ee4` (1530 bytes)
- `assets/fixtures/notext.pdf` sha256 `49567e9841ba9fa48a127403b4264d1eb7a45b7e14bed61cd5490e5002560ba2` (575 bytes)
- `assets/fixtures/sample.csv` sha256 `bc62aaeb878c38bb51791d70498db907596eab8f84cb1a0722547ae097a38514` (50 bytes)
- `assets/fixtures/sample.json` sha256 `3d1a20bae9a0eb3f6173df210e98dd5fddb099c130f45de742dd934ddb805560` (117 bytes)
- `assets/fixtures/sample.pdf` sha256 `905be5dd10bd92fa12beb6f732ac0523e052c4127a04383d7ab9f5fb88b6bd5f` (626 bytes)
- `assets/fixtures/sample.pptx` sha256 `2164afe1f08c384a02bb47e9f9c51cb6dd717a35fe47153c351ba6e0adad2be5` (2857 bytes)
- `assets/fixtures/sample.tsv` sha256 `44ff898b44d9418b89a1df222795421e2cb16ee3cf12571ff93bdbf087c2d447` (22 bytes)
- `assets/fixtures/sample.txt` sha256 `41c5be5a8f82b480b02d2a5116706606cca1f57be7f840457c91a34b680f04d3` (55 bytes)
- `assets/fixtures/sample.xlsx` sha256 `42138518ac486a56634edbbe864341dbcaa066c00c2af359e44df4f9d5566ad1` (5509 bytes)
- `floe.json` sha256 `cb6b681fbf1e195a35e9ebdb2b738b07db51d0034761b2ae33525b83e391d221` (758 bytes)
- `references/ADAPTATION-NOTES.md` sha256 `1ecf3bb0421137856a5be8a858e783689d109da089fff6f31f4559af51fe0a4e` (5014 bytes)
- `references/conversion-security.md` sha256 `08bef51e2216e2d243db22e7a2a824b17c77a7e75b4167430357333a0aa40f89` (3641 bytes)
- `references/format-routing.md` sha256 `77c4c8fa91e4ef2e96f29c0cb9f8cdc43c7460970e80640c963b42fa2149be8a` (4935 bytes)
- `references/licenses/LICENSE-NOTE.md` sha256 `b3752c0c3055974a8881c138d3f4aa0a0dace836e850195368878125db2177ee` (1668 bytes)
- `scripts/md_batch.py` sha256 `3e166da89d61b4f8d353b36d8c1f8e5680c2f679ef52d8636a5a004eae7efa2e` (6782 bytes)
- `scripts/md_convert.py` sha256 `aceff58f75dadd3bfeba1518472ba8dff26a6d0b61680d54bb2898c0f9cd9a95` (3513 bytes)
- `scripts/md_converters.py` sha256 `45c586dc03ed2d8962e34193a4475bbcfdc11dae1f20e620494a5fce1b997234` (32676 bytes)
- `scripts/md_verify.py` sha256 `b91a63c6e81644764b4c2581a260ca4b309504ff774b80d39b1c3802e2fbb7c8` (19761 bytes)

TOTAL 20 files, 102435 bytes
