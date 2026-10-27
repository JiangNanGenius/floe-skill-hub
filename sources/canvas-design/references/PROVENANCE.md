# Provenance — canvas-design

- Upstream repository: https://github.com/anthropics/skills
- Pinned commit: `dbd4588f9e1033efb41dad4bef2f7947c8993d44`
  (subtree `skills/canvas-design`, git tree `95095faaee2ea943e85a5d1d562fde06841e835e`, 83 files;
  proof recorded with the lane evidence)
- Upstream license: Apache-2.0 per-skill `LICENSE.txt`, preserved byte-identical at
  `references/licenses/UPSTREAM-LICENSE.txt` (`cmp`-verified against the pinned checkout)
- Fetch mode: sparse subtree clone into task scratch (blob-filtered); no full-repo vendoring.
- Upstream content kept: the design-philosophy workflow, the subtle-reference deduction
  step, the canvas-expression guidance, the final-refinement pass and the multi-page option,
  all re-expressed for the Floe runtime (not copied wholesale). The upstream font catalog
  was audited in full; 4 families / 7 faces (SIL OFL 1.1, license texts beside each face)
  are bundled; the remainder is documented by name only in `references/FONTS-LICENSE.md`.
- Adaptations:
  1. Output contract `.pdf/.png only` → editable SVG + self-contained HTML sources plus an
     honest export chain (`exec.localService` + `browser.navigate` + `browser.screenshot`
     for pixels; `scripts/png_to_pdf.py` wraps verified PNGs only). No unrendered file is
     ever renamed as PNG/PDF.
  2. "Download whatever fonts are needed" (network) → audited bundled set + declared device
     CJK fallback stack; the generator's coverage gate fails unsupported glyphs with exact
     codepoints (no missing-glyph false success); `--require-embedded` exposes the
     actionable unsupported case for standalone SVG.
  3. Free-form model-side drawing → deterministic spec-driven generator
     (`scripts/make_poster.py`) with real advance metrics enforcing "nothing falls off the
     page / no text overlaps" (bounds + text-box collision + maxWidth checks, computed
     from `assets/fonts/fonts.json`).
  4. Claude/claude.ai platform bindings removed; execution is the task Linux guest via
     `exec.shell`; all outputs atomic, bounded, task-owned, never silently overwritten.
- Excluded upstream files (with reason):
  * 47 of 54 upstream `.ttf` + their OFL texts: not needed for the minimal viable type
    system (payload limit + audit surface); families documented instead.
  * `IBMPlexSerif` / `InstrumentSerif` binaries: no license text at the pinned commit —
    excluded until per-asset provenance is verifiable.
- First-party additions (MPL-2.0): `scripts/make_poster.py`, `scripts/png_to_pdf.py`,
  `assets/fonts/fonts.json` (coverage/advance tables), `assets/examples/*.json`,
  `references/FONTS-LICENSE.md`, `references/poster-spec-format.md`, `floe.json`.
- Verification status: source-complete; host dev-smokes executed (make_poster positive/
  negative suites, metrics-driven failure cases, font hash re-verification, XML-only SVG
  checks, QuickLook host render of sample SVG labeled host-only, png_to_pdf round-trip +
  independent CoreGraphics read-back). Font-audit verification history, stated honestly:
  the ORIGINAL CoreText cross-check validated GLYPH COVERAGE only; the advance values in
  the first registry were wrong (cmap format-4 reservedPad double-count in the scratch
  generator). The closure stage (2026-10-26) fixed the generator, regenerated the v2
  registry, and re-verified EVERY covered codepoint's glyph id + advance against CoreText
  (ctypes on the exact bundled TTF bytes, no font registration) — root cause, repro, the
  original wrong registry and the crosscheck results are preserved in the lane evidence
  (`skill-hub-20261026/visual-two/evidence/closure20261026/`). Guest (`exec.shell` on
  riscv64) and App (WebKit preview/export-button, CJK device fallback visual QA) remain
  PENDING — see the lane GUEST-PENDING runbook. Nothing here claims execution
  verification.


## 1.1.0 local change record (private candidate, job-c988e0c9de8a459d, 2026-10-27)

First-party changes only; the upstream workflow pin (anthropics/skills@dbd4588),
Apache-2.0 notice, all bundled OFL fonts, the fonts.json advance/coverage registry,
example specs and every generator guarantee (bounds, overlap, coverage, exit codes,
determinism, no external resources) are untouched. The 1.1.0 tree closes the poster
file-DELIVERY gap proven by the held qualification evidence: the in-page export
rasterized real bytes but a data-URL click materializes no file in the app's
WKWebView (zero download handoff in the browser layer at the frozen source).

1. scripts/make_poster.py EXPORT_JS — after a successful full-size raster the page
   stages the exact bytes (window.__posterExport: name, W×H, byte length, SHA-256
   via WebCrypto when available), delivers them through the app `floeExport`
   message bridge when installed (bounded base64 chunks + declared total/sha),
   and always replaces the interim success line with the terminal delivery truth;
   an engine that saves no click downloads is stated as NOT delivering a file.
   Frozen test surface preserved: same `id="export-png"` button and
   `Export PNG W×H` labels, same declared-size chrome line, success lines keep
   the exact `Exported WxH PNG` prefix, failure lines keep the `FAILED` prefix,
   no resource-bearing field references anything but inline data, bytes stay
   deterministic across runs.
2. scripts/verify_png.py — NEW stdlib-only full PNG integrity + content verifier
   (signature, per-chunk CRC walk, IHDR sanity, IDAT inflate with exact
   unfiltered-length + zip-bomb bounds, IEND/tail policy, file SHA-256, optional
   decoded pixel SHA-256 and fail-closed expectations). SKILL.md now makes
   verify-before-publish mandatory, so a page status can never become a receipt.
3. SKILL.md Export section — delivery truth inserted (steps renumbered); the
   publish step must quote workspace.publishOutput receipts bound to real bytes.
4. floe.json version 1.1.0.

## File inventory (sha256 per file, this checkout; PROVENANCE.md self-hash intentionally omitted)

- `SKILL.md` sha256 `530810d17b4dc076dfa81bad28d50044a7b67dea2304873695d705f31bb1b9e6` (9870 bytes)
- `assets/examples/cjk-poster-spec.json` sha256 `6447888004d4660cd0c121cefde93c942cb5ada0f78f40fdbd536762eeb7c182` (1051 bytes)
- `assets/examples/hero-spec.json` sha256 `801ef7a34147bd99312c1e6042507cdcc40f4c283736ccb6131546b1421fb2b4` (2082 bytes)
- `assets/fonts/BigShoulders-Bold.ttf` sha256 `b43bcd198b9fdf717dd42aa61a34dba32e01aceaeae659d689afd0ca52c37ea2` (94528 bytes)
- `assets/fonts/BigShoulders-OFL.txt` sha256 `fbc746aabf0eb1847dfd92e2efc4596d79fa897d60b8e64062a22f585508fb3f` (4397 bytes)
- `assets/fonts/BigShoulders-Regular.ttf` sha256 `18a879fc71978a4447150705caf880a9da3860083c259fd29e6dc03057b6842a` (94396 bytes)
- `assets/fonts/Italiana-OFL.txt` sha256 `8373b11312ace78c4cec2e8f9f6aa9f2330601107dac7bcf899c6f2dbd40c5a5` (4394 bytes)
- `assets/fonts/Italiana-Regular.ttf` sha256 `15c4dd6ab8cf4a29ba8826f65edcbe2f6c266c557d34d081f25072dfd5605fd2` (27184 bytes)
- `assets/fonts/Outfit-Bold.ttf` sha256 `6654b93d21301ec61887d3cedd6c11d9df1b1dfb63f9cf45ac7995f6e2235ab1` (55392 bytes)
- `assets/fonts/Outfit-OFL.txt` sha256 `1945b62cd76da9a3051a1660dde72afaa64ffc2666d30e7a78356d651653ba2f` (4389 bytes)
- `assets/fonts/Outfit-Regular.ttf` sha256 `f24945365147c9e783e91d8649959b59be6b00c9ee4ecd2f6b33afbb2dd871fe` (54912 bytes)
- `assets/fonts/RedHatMono-Bold.ttf` sha256 `7ef48353f4be5ddb90f000f6fad48f2b62b3e8c27d9818d8d45ff46c201065e0` (34420 bytes)
- `assets/fonts/RedHatMono-OFL.txt` sha256 `435fbfb7e66988b2a06686a4cb966faec733f35d8fe100a1601573c27f3e0bb8` (4394 bytes)
- `assets/fonts/RedHatMono-Regular.ttf` sha256 `452fe826871b37539f5212b20c87cf30f82f58dd2741f1c96edd1dcbdc0db6b4` (34488 bytes)
- `assets/fonts/fonts.json` sha256 `6eed5d33896130b1064d19777077313deb47fe1c5c7d5b2a74f582aaa1a4d639` (38326 bytes)
- `floe.json` sha256 `8b91a5361070769a9687aafa4752628b4aa925e597897b123b243c6a99fd8a42` (218 bytes)
- `references/FONTS-LICENSE.md` sha256 `1e9223f6791c59da47a0784ab18749739cd320118bb759ac760a90cb8bbc3947` (4282 bytes)
- `references/licenses/LICENSE-NOTE.md` sha256 `ae69a7920087302756eb14464c1c8d8af27fc968487df7b478bd72ee51124e87` (1739 bytes)
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `bc6b3af2f331cbc7fb0da1344efb2cbe5877a31498b4d70dbc7000f3405a1362` (11345 bytes)
- `references/poster-spec-format.md` sha256 `5867560d29dda339abe753f846a8bfcb341aff70ebefc5fb7697156251a9301a` (3875 bytes)
- `scripts/make_poster.py` sha256 `26332e276835779a2c20cb70ba7a1c7cb643d945ef0a671510fb346e65d1b281` (38234 bytes)
- `scripts/png_to_pdf.py` sha256 `69f63ea5e0a4df3ee9974a2da999cf47e5c598121272e340ce09c114384514a2` (9429 bytes)
- `scripts/verify_png.py` sha256 `13a63e28f0bf2f8d66b68d8411837096445f5db82f519386d6d33b9b65b17614` (12713 bytes)
