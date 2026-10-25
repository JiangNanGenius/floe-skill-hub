# Bundled fixtures — scientific-visualization (Floe adaptation)

SMALL SYNTHETIC fixture authored for this Floe release (first-party,
MIT (c) Floe project). No third-party or real measurement data.

`series_fixture.csv` — 6 time points (h) of a response concentration
(mmol/L) with replicate means and standard errors. Deliberate features
exercised by `scripts/viz_verify.py` goldens:

- an INTERIOR missing value (`response_mmol_L` at t=3) that must render as
  a visible gap (two disjoint line segments), never a silent bridge;
- standard-error values for honest error-bar rendering with caps;
- hand-computable coordinate mappings: with axes rect [0.1, 0.1, 0.85, 0.8]
  on a 6×4 in page, xlim (0,5), ylim (0,100), the point (t=2, 20.0) must
  land at exactly x = (0.1 + 0.85·2/5)·432 pt = 190.08 pt,
  y = 288 − (0.1 + 0.8·20/100)·288 pt = 213.12 pt (SVG top-left origin).
