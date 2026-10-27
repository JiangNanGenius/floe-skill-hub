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

## 1.1.0 — dependency v1 declaration sidecar (2026-10-27)

- Added `references/dependencies.json` (schemaVersion 1, profile `debian13-riscv64`, architectures exactly riscv64): apt `python3-matplotlib=3.10.1+dfsg1-4`, `python3-numpy=1:2.2.4+ds-1`, `python3-pil=11.1.0-5+deb13u4`, `python3-pypdf=5.4.0-1` (all `required: true` — export and content-level inspection paths need them), apt `fontconfig=2.15.0-2.3` (`required: true` — font discovery plus the Debian FreeType library) and font `fonts-noto-cjk=1:20240730+repack1-1` (`required: false`, matching the skill's "CJK labels when provisioned" promise; `viz_verify.py --require-cjk` gates any CJK claim, and the fixed guest glyph-render probe must pass on top of the recorded versions before readiness is claimed).
- No pip requirements and no lockfile: matplotlib/Pillow ship compiled, so the Debian apt identities are the honest provisioning route.
- `floe.json` `pythonPackages` pins are unchanged and match the four module identities; only the package `version` moved 1.0.0 -> 1.1.0 because the file set changed.
- Scripts, styles and fixtures are byte-identical to the reviewed 1.0.0 staging.
Pin provenance: every version above is copied from the Debian trixie main binary-riscv64 Packages index retrieved 2026-10-27 from deb.debian.org, whose bytes are bound by the GPG-verified trixie InRelease (signed with the Debian 13/trixie archive key 225629DF75B188BD); exact per-package Version/Filename/Size/SHA256 are recorded in the Hub-lane evidence packet (MANIFEST.json of the all-seven-dependencies staging), not in this file.

## 1.1.0 private candidate — PNG density quantisation repair (lane job-d2c7b41f32434377, 2026-10-27)

- Confirmed defect (frozen guest evidence preserved verbatim): the guest `figure_export --dpi 300`
  wrote `demo.png` (sha256 `0b221f2896222e3d99e684a4089639f166f92315737e7104cc2c36c315cb5c75`,
  86587 B) carrying pHYs 11811 11811 1 (decodes to 299.9994 dpi), and the frozen 1.1.0
  `image_metadata.py --min-dpi 300` screened its own output as `fail` (exit 1). W3C PNG
  (https://www.w3.org/TR/png-3/#11pHYs) stores density as an INTEGER number of pixels per unit,
  so 300 dpi has no exact metric encoding; the previous tolerance (abs 1e-9) was far tighter
  than the format's own 0.0254 dpi quantum, turning an encoding artifact into a false rejection.
- `scripts/image_metadata.py` is the only script modified (a Floe repair on the upstream MIT
  file, recorded here). When a PNG's decoded density is proven to be exactly an integer-metric
  pHYs encoding, min/max DPI screening on the embedded-metadata basis now compares in that
  integer px/m domain: threshold T maps to floor(T/0.0254 + 1/2) via exact rational arithmetic
  (nearest integer, ties away from zero — the encoding convention PNG writers apply, so a file
  written "at" T always satisfies T), neutralising at most the 0.0127 dpi half-step of encoding
  quantisation and nothing else. Reported `dpi_x`/`dpi_y` and the dpi check's `actual` remain
  the raw decoded values; a min threshold binds the lower of the two axes and a max threshold the
  higher. The comparison domain is stated in the check detail and provenance is recorded as an
  additive `density_provenance` metadata field (single CRC-valid pHYs, length 9, unit byte 1,
  counts in 1..2^31-1, the complete pre-IDAT region scanned to a whole IDAT/IEND chunk within a
  1 MiB bound, and bit-exactly equal to `px * 0.0254` as reported by the decoder; a truncated or
  budget-limited scan grants nothing).
- Not weakened: effective-DPI screening at an explicit `--target-width-mm` stays the previous
  strict float comparison; non-PNG rasters, PNGs without proven integer-metric pHYs (absent,
  unknown unit, corrupt CRC, duplicate, malformed, partial/incomplete scan, beyond the scan
  bound, or not bit-exactly matching the decoder value) keep the previous strict behaviour;
  absent/invalid metadata stays `unknown`; genuinely lower/higher integer densities still fail
  on the binding axis; every safety limit (input byte cap, decompression-bomb pixel cap, symlink
  rejection, overwrite refusal, report cap) is unchanged. `SCHEMA_VERSION` stays "1.0" — the only
  report change is the additive field and the comparison detail text.
- `figure_export.py` and `viz_verify.py` are unchanged: the exporter writes spec-correct PNGs,
  so the repair belongs to the screener, not to the writer or to any golden quality assertion.
  `export_plan.py` (which screens effective DPI at the plan's physical width) is unchanged.
- `floe.json`, `references/dependencies.json`, dependency pins, capabilities/permissions and
  licenses are byte-identical to the accepted 1.1.0 packet; the package version stays 1.1.0 as a
  private, unpublished candidate by Root's allowance. Guest qualification of the changed screener
  (one focused CLI regression on the actual `demo.png` plus the exact own-closure denials) is
  Root's, through the existing real-guest owner; this lane ran host regressions only.
- Detailed validation, archive identities and guest handoff records are retained privately by Floe. The original guest failure and prior candidate remain unchanged.

### Root-review correction of the first private candidate (2026-10-27, lane job-da3aa42b630040c3)

Root review rejected the first candidate because two cases proved more than the code had
established. Both are corrected in `scripts/image_metadata.py` and covered by deterministic host
regressions built from Root's exact encoded repros (`evidence/root-repro/ROOT-REPRO.json` in the
private lane):

- Scan completeness: the first helper returned an already-seen pHYs when the bounded scan stopped
  at an oversized pre-IDAT chunk or truncated data. That cannot prove "exactly one pHYs": a
  valid first pHYs 11811, a 1 MiB+ `tEXt` gap and a duplicate identical pHYs still passed. A
  reading is now returned only when the bounded scan reaches a whole `IDAT`/`IEND` chunk with
  exactly one CRC-valid pHYs; budget exhaustion, truncation, a chunk that does not fit the file,
  a duplicate, or malformed/CRC-bad metadata yields no provenance and the previous strict
  comparison. A partial scan never grants provenance.
- Per-axis bounds: the first candidate used the lower px/m axis for both bounds, so a
  11811x11812 pHYs passed `--max-dpi 300` although 11812 px/m = 300.0248 dpi is genuinely above
  300. A min threshold is now compared with the lower axis and a max threshold with the higher
  axis; `dpi_x`/`dpi_y` and the dpi check's `actual` (the lower raw axis) stay unchanged.
- Both Root wrong-pass repros now fail with the expected status (anisotropic max: rc 1 fail with
  its provenance intact and both raw axes in the detail; scan gap: rc 1 fail with no
  provenance). The accepted 300 dpi guest PNG still passes with raw 299.9994, and 11810 at
  min 300 / 11812 at max 300 still fail. This remains host evidence only; the focused real-guest
  check is Root's.
