# Poster spec format (schemaVersion 1)

`scripts/make_poster.py` consumes one JSON file and refuses anything outside
this contract. All positions are canvas pixels; declared units apply to canvas
size and font sizes.

```json
{
  "schemaVersion": 1,
  "title": "short artifact title",
  "lang": "en",
  "canvas": {
    "width":  {"unit": "mm", "value": 297},
    "height": {"unit": "mm", "value": 420},
    "dpi": 300,
    "background": "#f6f3ec"
  },
  "elements": [ { "type": "rect|circle|line|path|text", ... } ]
}
```

- `canvas.width/height`: number (px) or `{"unit":"px|mm","value":N}`; mm is
  converted at `dpi` (72–1440, default 300). Final canvas must land within
  64–8192 px per side.
- `canvas.background`: `#RGB` or `#RRGGBB`.
- `elements`: 1–512 objects; total text ≤ 8192 characters.

## Element types

- `rect`: `x, y, w, h` (px), `fill` or `stroke` (+`strokeWidth` 0.1–512),
  optional `rx` (≤ half of min(w,h)), `opacity` (0.02–1). Must stay inside the
  canvas.
- `circle`: `cx, cy, r` (+ same fill/stroke/opacity rules). Whole disc must
  stay inside the canvas.
- `line`: `x1, y1, x2, y2`, `stroke`, `width` (0.1–512). Both endpoints inside.
- `path`: `d` (1–4096 bytes, SVG path grammar characters only: commands
  `MmLlHhVvCcSsQqTtAaZz`, numbers, commas, spaces, dots, minus/plus),
  `fill`/`stroke`. Coordinates inside `d` are NOT bounds-checked — keep paths
  inside the canvas yourself (coverage report records the raw path).
- `text`: `content` (1–512 chars; no tabs/newlines), `family` + `style`
  (must exist in `assets/fonts/fonts.json`), `size` (number px or
  `{unit,value}`; 4–2048 px), `x`, `y` (baseline), `anchor`
  `start|middle|end` (default start), `fill`, optional `letterSpacing`
  (−50..50 px) and `maxWidth`. Width comes from real advance metrics of the
  selected face (v2 registry: per-codepoint CoreText cross-checked on the
  exact TTF bytes); fallback-routed CJK characters are estimated at 1 em.
  The computed box (advance width + nominal ascent/descent) is an estimate
  for gross overflow/collision prevention, not an ink bound. The box must be
  inside the canvas and must not overlap any other text box.

## Rules the generator enforces (and their failure semantics)

1. Unknown font family/style → error listing the bundled families.
2. Glyph not covered by the chosen face and not in the CJK fallback ranges →
   error with exact `U+XXXX` codepoints (unless `--allow-unsupported`, which is
   disclosed in the coverage report).
3. Fallback-routed text with `--require-embedded` → exit 4 with the remedy.
   The flag guarantees every glyph resolves to a BUNDLED FACE; it does not
   embed fonts into the standalone `.svg` (it never does — only `.html` does).
4. Bounds or text-text overlap violations → error with the actual numbers.
5. Text wider than `maxWidth` → error with both widths.
6. Existing outputs are never overwritten without `--overwrite`; writes are
   atomic (temp + fsync + rename).

## Outputs

`<prefix>.svg` (editable source; fonts by name + declared fallback stack —
NOT font-portable standalone), `<prefix>.html` (self-contained: inline SVG +
base64 @font-face for each used bundled face [font hashes re-verified before
embedding], readable SIL OFL 1.1 disclosures for the redistributed font
software, MPL-2.0/Apache-2.0 code notices, a declared-size bar and a
full-size artwork-only PNG export button that fails with an actionable
message on canvas-limited engines instead of downscaling), and
`<prefix>.coverage.json` (spec sha256, declared units/dpi, pixel canvas,
metric basis + artifact policy, fonts used with sha256, per-element
embedded/fallback split, policy flags, machine-readable notice metadata).
PNG/PDF production is a separate, honest step (see SKILL.md export order:
`browser.screenshot` is a viewport preview, never the declared raster).
