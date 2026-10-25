# Font license & coverage audit — canvas-design

Pinned upstream: `anthropics/skills@dbd4588f9e1033efb41dad4bef2f7947c8993d44`,
`skills/canvas-design/canvas-fonts` (subtree fetch 2026-10-26, task scratch; no
full-repo vendoring).

## Upstream inventory (54 `.ttf` files, 29 families, 5,412,104 bytes total)

All 29 families were parsed with a pure-stdlib cmap/hmtx audit tool, and the
**coverage** results (which codepoints resolve to glyphs) were cross-verified
against macOS CoreText for sampled codepoints. Correction recorded 2026-10-26:
the original audit's *advance values* were never cross-checked and were wrong —
its format-4 cmap parser double-counted the reservedPad, shifting idDelta /
idRangeOffset by one slot and mapping nearly every codepoint to another
glyph's hmtx. The bundled registry `assets/fonts/fonts.json` is now the v2
output of the fixed generator, and EVERY covered codepoint's advance and glyph
id on the exact TTF bytes re-matches CoreText
(per-face ctypes probe; root cause, repro and the original wrong registry are
preserved in the lane evidence `closure20261026/`). **Every family is
Latin-script only: 0 CJK ideograph, kana or Hangul codepoints in any font.** The
upstream instruction to "download whatever fonts are needed" is therefore
replaced by the audited local rules below — the Floe skill never instructs
downloads.

Families (Regular/Bold/Italic variants per upstream tree): ArsenalSC,
BigShoulders, Boldonse, BricolageGrotesque, CrimsonPro, DMMono, EricaOne,
GeistMono, Gloock, IBMPlexMono, IBMPlexSerif, InstrumentSans, InstrumentSerif,
Italiana, JetBrainsMono, Jura, LibreBaskerville, Lora, NationalPark,
NothingYouCouldDo, Outfit, PixelifySans, PoiretOne, RedHatMono, Silkscreen,
SmoochSans, Tektur, WorkSans, YoungSerif.

## License findings

- 27 of 29 families carry their own `<Family>-OFL.txt` (SIL Open Font License
  1.1) beside the binaries at the pinned commit.
- **`IBMPlexSerif` and `InstrumentSerif` ship binaries with no license text at
  the pinned commit.** They are excluded from the Floe bundle (and from any
  download instruction); names may only be mentioned as unavailable. Their
  upstream project licenses are not restated here because per-asset
  provenance at this pin is unverified — exactly the case the catalog note
  anticipated.

## Bundled in this package (4 families, 7 faces, each with its OFL text)

| File | Family (name table ID1) | Style | Bytes | License file |
| --- | --- | --- | --- | --- |
| BigShoulders-Regular.ttf | Big Shoulders | Regular | 94,396 | BigShoulders-OFL.txt |
| BigShoulders-Bold.ttf | Big Shoulders | Bold | 94,528 | BigShoulders-OFL.txt |
| Outfit-Regular.ttf | Outfit | Regular | 54,912 | Outfit-OFL.txt |
| Outfit-Bold.ttf | Outfit | Bold | 55,392 | Outfit-OFL.txt |
| Italiana-Regular.ttf | Italiana | Regular | 27,184 | Italiana-OFL.txt |
| RedHatMono-Regular.ttf | Red Hat Mono | Regular | 34,488 | RedHatMono-OFL.txt |
| RedHatMono-Bold.ttf | Red Hat Mono | Bold | 34,420 | RedHatMono-OFL.txt |

Selection rule: one condensed monumental display, one geometric sans, one thin
serif display, one clinical mono — enough for the poster workflow at the
smallest licensed payload. SHA-256 of every bundled face is pinned in
`assets/fonts/fonts.json` and re-checked by `scripts/make_poster.py` before
embedding; coverage + advance metrics live in the same file.

## Chinese / CJK policy (no false success)

No bundled font covers CJK. The generator routes CJK characters to the device
fallback stack `"PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC",
sans-serif` (iOS ships PingFang SC; the HTML artifact renders them through
WebKit on the device), estimates each at one em for bounds/overlap checks, and
records the embedded/fallback split per element in `*.coverage.json`.
Standalone `*.svg` is an editable source: off-device rasterizers without CJK
fonts would substitute, which is why `--require-embedded` exists (fails with an
actionable message for CJK instead of pretending) and why export goes through
the HTML + WebKit capture path. Characters covered by neither the bundled
fonts nor the CJK range fail the run with the exact codepoint list;
`--allow-unsupported` is only for viewer-substituted deliverables and is
disclosed in the coverage report.
