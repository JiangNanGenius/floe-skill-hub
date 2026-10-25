# Adaptation notes — scientific-visualization 1.0.0 (Floe)

Upstream: K-Dense-AI/scientific-agent-skills `skills/scientific-visualization`
at commit `593377bb048752abb0152deab9fbb1083a6087df` (MIT).

## Shipped verbatim (audited: no network, no subprocess, lazy imports, bounded I/O, symlink rejection, overwrite protection)

- `scripts/_common.py`, `scripts/figure_export.py`, `scripts/style_presets.py`, `scripts/palette_audit.py`, `scripts/export_plan.py`, `scripts/image_metadata.py`, `scripts/style_preview.py` — the complete upstream CLI/API set for the Matplotlib path.
- `assets/color_palettes.py`, `assets/nature.mplstyle`, `assets/presentation.mplstyle`, `assets/publication.mplstyle`, `assets/publisher_profiles.json` — palette values carry their own upstream source attributions (Okabe-Ito/Nature methods DOI, Paul Tol SRON pages); mplstyle files and publisher snapshots are upstream MIT content; no fonts or images are embedded.
- `references/publication_guidelines.md`, `references/color_palettes.md`, `references/journal_requirements.md`, `references/matplotlib_examples.md`, `references/sources.md` — preserved unchanged, including their Seaborn/Plotly sections, which are now GUIDANCE ONLY (see boundary below). Their `uv run --with ...` example invocations describe the upstream host workflow; in Floe every command runs through `exec.shell` in the resolved Linux environment with the declared pins (SKILL.md shows the Floe command forms).

## Modified (upstream MIT content, changes recorded)

- `scripts/style_preview.py`, `scripts/style_presets.py`, `scripts/figure_export.py`, `scripts/image_metadata.py` — 9 missing-dependency messages re-bound from upstream `uv ... --with 'matplotlib==3.11.2' / 'pillow==12.3.0' / 'pypdf==6.19.0'` snippets to the Floe environment/package-flow wording with the DECLARED pins (matplotlib==3.10.1, pillow==11.1.0, pypdf==5.4.0 — the exact Debian 13 guest package versions). No logic changed.
- `SKILL.md` — rewritten around the Floe runtime: headless Agg execution through `exec.shell`/`jobs.submit`, declared pins, matplotlib-only first-release scope, prohibited Kaleido/Chromium, CJK honesty policy, content-level verification section, native scalar frontmatter; upstream guardrails/workflow/asset/checklist substance preserved; K-Dense attribution preserved.

## Added (first-party Floe, MIT (c) Floe project)

- `scripts/viz_verify.py` — golden verifier rendering the bundled fixture through the bundled exporter and validating the ACTUAL output bytes: PNG IHDR/chunk-CRC/geometry (1800×1200 @300dpi)/pixel-color presence, SVG XML + searchable labels-with-units + disjoint segments across the fixture's interior missing value + an INDEPENDENT hand-computed data→page coordinate mapping golden ((2, 20.0) → (190.08, 213.12) pt ±1.0 from the fixed axes rect/page size), PDF header/EOF/page-size/embedded-font via the declared pypdf layer, palette contrast equality against a second independent WCAG implementation (exact rational coefficients, ≤1e-9) with the black/white=21 spec anchor, honest CJK font discovery + missing-glyph/findfont warning capture + SVG-searchable CJK assertion (`--require-cjk` for guest acceptance), CLI end-to-end subprocess runs, and export safety negatives (overwrite refusal, dpi=0, unknown format, bad font_mode). Declared-pin mismatch fails the receipt. Mutation-tested during adaptation: a shifted coordinate golden and a weakened gap check each produced ok=false with targeted messages.
- `assets/fixtures/series_fixture.csv` + `assets/fixtures/README.md` — small synthetic fixture (interior NaN, SE columns, hand-computable geometry); no third-party data.
- `references/PROVENANCE.md`, `references/ADAPTATION-NOTES.md`, `references/licenses/*`.

## Excluded / out of declared scope (audited, with reasons)

- Seaborn (`seaborn==0.13.2`) and Plotly (`plotly==7.1.0`) runtime paths — NOT declared dependencies of this release; Debian trixie packages both for riscv64 (python3-seaborn 0.13.2, python3-plotly 5.20.0), so a future release may add a separately reviewed optional layer. Until then figure code must not import them, and the upstream reference sections describing them are guidance only.
- Kaleido (`kaleido==1.4.0`) / Chrome-Chromium static export and interactive HTML deliverables — prohibited as a default dependency by the implementation plan; no browser engine is provisioned in the guest. Interactive HTML is separately accepted future scope.
- Upstream `uv run --isolated` snapshot pins (matplotlib 3.11.2, pillow 12.3.0, pypdf 6.19.0) — replaced by the exact versions the resolved Debian 13 guest provides (matplotlib 3.10.1, pillow 11.1.0, pypdf 5.4.0); the version delta is recorded here rather than silently ignored.
- EPS-only workflows (Kaleido v0) — EPS inspection remains in `image_metadata.py` (stdlib parsing), but no EPS production path is claimed.
- CJK font binaries — never bundled (licensing); CJK rendering depends on environment-provisioned fonts (`fonts-noto-cjk` in the guest flow), detected honestly at runtime.
