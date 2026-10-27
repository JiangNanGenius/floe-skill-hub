# Provenance — scientific-visualization (Floe adaptation, 1.0.0)

- Upstream repository: https://github.com/K-Dense-AI/scientific-agent-skills
- Pinned commit: `593377bb048752abb0152deab9fbb1083a6087df` (repository tree `d4d202beb151c1f1c6c15738be0692d65e0447af`; skill subtree `skills/scientific-visualization` tree `292eaa2adb46c1ee678f090efec7780c50b91419`, verified at fetch on 2026-10-26)
- Upstream path: `skills/scientific-visualization`
- License: MIT (root `LICENSE.md` at the pinned commit, Copyright (c) 2025 K-Dense Inc.) — full text at references/licenses/UPSTREAM-LICENSE.txt; per-file audit (incl. the Okabe-Ito/Paul Tol/Nature attributions carried inside assets) in references/licenses/LICENSE-NOTE.md
- Retrieval: sparse subtree fetch into task scratch; no full-repo vendoring.
- Adaptation record: references/ADAPTATION-NOTES.md.
- Declared dependency layer (floe.json): matplotlib==3.10.1, numpy==2.2.4, pillow==11.1.0, pypdf==5.4.0 — the exact versions the resolved Debian 13 (trixie) riscv64 guest provides as python3-matplotlib (3.10.1+dfsg1-4), python3-numpy (1:2.2.4+ds-1), python3-pil (11.1.0-5+deb13u4), python3-pypdf (5.4.0-1). Upstream pins matplotlib 3.11.2 / pillow 12.3.0 / pypdf 6.19.0 were replaced by the guest-available versions (delta recorded in ADAPTATION-NOTES, not silently ignored). Seaborn/Plotly/Kaleido are NOT declared (guidance-only / prohibited defaults).
- CJK rendering depends on an environment-provisioned font (guest option: `fonts-noto-cjk`, 1:20240730+repack1-1 in trixie); no font binaries are bundled.
- First-release version: 1.0.0 (no previously published id/version exists for this skill; registry versionTarget 1.0.0).

## Golden provenance (content-level output verification)

The coordinate-mapping golden is computed by hand from the fully specified page geometry shipped in the fixture README: axes rect [0.1, 0.1, 0.85, 0.8] on a 6×4 in page (432×288 pt), xlim (0,5), ylim (0,100) ⇒ data (2, 20.0) must render at x = (0.1 + 0.85·2/5)·432 = 190.08 pt, y = 288 − (0.1 + 0.8·20/100)·288 = 213.12 pt (SVG top-left origin), tolerance 1.0 pt. WCAG contrast goldens use a second independent implementation (exact rational coefficients) inside the verifier plus the spec anchor contrast(black, white) = 21. The suite was mutation-tested during adaptation: shifting the coordinate golden by one data unit (2.30 pt on the page) and weakening the missing-value gap check each produced `ok: false` with targeted failure messages, proving the checks can fail.

## Host development evidence (NOT guest execution evidence)

Executed 2026-10-26 by the H4 lane, labeled by environment:

1. Debian trixie arm64 dev container (docker `floe-data-five-dev`; same distro release, Python 3.13.5, matplotlib 3.10.1+dfsg1 / numpy 2.2.4 / pillow 11.1.0 / pypdf 5.4.0 / fonts-noto-cjk — identical package identities to the guest pins; NOT the riscv64 guest, NOT the 4.15 TinyEMU kernel): `python3 scripts/viz_verify.py --require-layer --require-cjk` → exit 0, `"ok": true`, all checks pass (pins, dual-implementation palette contrast, CJK font probe discovering Noto Sans/Serif CJK JP, golden render with PNG IHDR/CRC/pixel-color checks, SVG label/gap/coordinate goldens with CJK title searchable and zero findfont/glyph warnings, PDF page-geometry/font checks, 4 CLIs + style_preview end-to-end, export negatives).
2. Mutation runs (container): coordinate-golden mutant → ok:false ("nearest series vertex is 2.30 pt away"); gap-check mutant → ok:false ("found 4 move commands"). Original failure outputs preserved in the lane evidence directory.

## GUEST-PENDING handoff for Main (exact steps; do not flip evidence without a real passing run)

In a task workspace in the resolved Linux environment, with this package installed/staged:

1. Provision through the existing environment/package flow (guest apt identities): `python3-matplotlib`, `python3-numpy`, `python3-pil`, `python3-pypdf`, and for CJK acceptance `fonts-noto-cjk`. No chat-time pip/uv.
2. `exec.shell`: `python3 scripts/viz_verify.py --require-layer --require-cjk --output verify.json` → must exit 0 with `"ok": true`; verify.json records installed versions and the discovered CJK fonts. (Without font provisioning run `--require-layer` only and expect the honest `skipped-no-cjk-font` status.)
3. Real workload: render one figure from authorized task data with `style_context` + `export_figure` (PNG+PDF+SVG, dpi ≥ 300, provenance + manifest), inspect it with `python3 scripts/image_metadata.py <file>` and `python3 scripts/palette_audit.py`, and read the deliverables back with the workspace tools; keep the actual output files as acceptance evidence.
4. Only after 2–3 pass in the actual guest may `plannedRuntime.execution.evidence` become `guest-verified` and `status.executionVerified` flip.

## File inventory (sha256, frozen 1.0.0 checkout; historical, self-hash intentionally omitted)

> Superseded for current bytes by the dated inventory at the end of this file; kept verbatim as the
> 1.0.0 freeze record. Later increments (1.1.0 dependency sidecar + verifier floe.json read-back,
> and the private 1.1.0 PNG density quantisation repair) changed specific files listed there.

- `SKILL.md` sha256 `8d556e6a2326bc73c337eddd01ebe2dfd1680218d1d909ae68822595f51aca80` (12523 bytes)
- `assets/color_palettes.py` sha256 `98ee4aa4b9bbb010996d55144ea6bf45a0ab294009b9bb0ef6d9c5ec9fed5154` (6756 bytes)
- `assets/fixtures/README.md` sha256 `0ab3d26fd21b8b06f53fd3a2d73f21cdb69003758830ed8cc569c47dfa45e43a` (888 bytes)
- `assets/fixtures/series_fixture.csv` sha256 `3e1313e7d89aa79c795d7da58dc2bb2d101cd81d2b6c86e84657183b425a52bc` (141 bytes)
- `assets/nature.mplstyle` sha256 `f37a361cdda8846da0794fd879cc8173402094f110239d57e0227fdd8299a4f6` (1624 bytes)
- `assets/presentation.mplstyle` sha256 `d0e5a768e5965aa3893b12c0f7decd4c3b09502044391a840ebdee37dfea44da` (1465 bytes)
- `assets/publication.mplstyle` sha256 `eba3001f346649a9e41d9ac1d56101abbae10aefecdad3be9530f4c9cd9269b3` (1822 bytes)
- `assets/publisher_profiles.json` sha256 `1e1b1b5a4e0e3dfc57877f2abf1e96888fe6b65617234b078f193b8f76e0ebe9` (10870 bytes)
- `floe.json` sha256 `5d90c69f67fe25679a28b9c3cd0548dd3006eee33202a54332dbe7f8ed12e933` (1097 bytes)
- `references/ADAPTATION-NOTES.md` sha256 `a2057ced134199cc61db71b039f1900029340198b94ef191875f7fbbe07da602` (5076 bytes)
- `references/color_palettes.md` sha256 `c9b6a596dd1dd1e08050fdcbb304a0268ee515bce2120a9bbd3fba31cd7fa119` (9094 bytes)
- `references/journal_requirements.md` sha256 `f7c4b6660eb70f7c5778d13908409e1dc690f00e3dfc8314f430feb89781740c` (11200 bytes)
- `references/licenses/LICENSE-NOTE.md` sha256 `0ec052eb23d8dcb07fb7866bf3cf1b1af76c2c1341b97b604187ff3bf902a58b` (1458 bytes)
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `09b02a3c9df3053c55531d503357a9c7cde275970e6c3ceaa1ddf5f0e90b40c1` (1068 bytes)
- `references/matplotlib_examples.md` sha256 `74fd5977ce57b09b476285309559bbcbe3b1748943b719844b28a6b61378c041` (12165 bytes)
- `references/publication_guidelines.md` sha256 `5f70c6b22dbb5e0fae18b0f1197b8794896bf7afc059874bcf7afbd5aa86bbe5` (12853 bytes)
- `references/sources.md` sha256 `3ff34759c0fed3baf33286a8005fd81f0c3466a554c8b0d45f43ad30b1e5b505` (10697 bytes)
- `scripts/_common.py` sha256 `e4eea2c2e5f5d8cfa544c6bed152cdb88a3d7c7952df99bcd74b45077fd6f707` (4618 bytes)
- `scripts/export_plan.py` sha256 `c20962bf4c624b9939c80bd16815fc0a18fe2be285f0654a6a53704c663add0e` (19682 bytes)
- `scripts/figure_export.py` sha256 `ec19530a179c3b1cf1c1b5bb340f14d613b06711ba2cea74369e1fc9bda7c902` (23864 bytes)
- `scripts/image_metadata.py` sha256 `77fbbfaa1929e24c6117a8f5d4227c874dc91d2ce9a26e09f6a6481ddc0b29f8` (26786 bytes)
- `scripts/palette_audit.py` sha256 `3a90b3c9a4a39dde6a341dc3de7b99cd2bca4773c66564fc90cdc2706a5a8165` (11654 bytes)
- `scripts/style_presets.py` sha256 `a2ad002eb962294db5a0cecf0ea62b8537930ee49909b834d6192a6531948bd5` (16597 bytes)
- `scripts/style_preview.py` sha256 `9f83fce33a78d3794b9116ca58b2e58124f1395abd9192e1e98fecf953a2909c` (7868 bytes)
- `scripts/viz_verify.py` sha256 `42f5914017f3f9a2dc48847f908a8dcb023cc39afd236cc3fc11be306b930c08` (27789 bytes)

TOTAL 25 files, 239655 bytes

## Current file inventory (sha256, Floe 1.1.0 density repair, 2026-10-27; self-hash intentionally omitted)

Only image_metadata.py changes executable behavior; SKILL.md and reference notes document the repair. Dependency declarations, permissions, fixtures, licenses and all other scripts remain unchanged.

- `SKILL.md` sha256 `4c829067e757411ec49c64fe925e110742d1f53d4e8f18a1abb9087a72eda8d9` (13143 bytes)
- `assets/color_palettes.py` sha256 `98ee4aa4b9bbb010996d55144ea6bf45a0ab294009b9bb0ef6d9c5ec9fed5154` (6756 bytes)
- `assets/fixtures/README.md` sha256 `0ab3d26fd21b8b06f53fd3a2d73f21cdb69003758830ed8cc569c47dfa45e43a` (888 bytes)
- `assets/fixtures/series_fixture.csv` sha256 `3e1313e7d89aa79c795d7da58dc2bb2d101cd81d2b6c86e84657183b425a52bc` (141 bytes)
- `assets/nature.mplstyle` sha256 `f37a361cdda8846da0794fd879cc8173402094f110239d57e0227fdd8299a4f6` (1624 bytes)
- `assets/presentation.mplstyle` sha256 `d0e5a768e5965aa3893b12c0f7decd4c3b09502044391a840ebdee37dfea44da` (1465 bytes)
- `assets/publication.mplstyle` sha256 `eba3001f346649a9e41d9ac1d56101abbae10aefecdad3be9530f4c9cd9269b3` (1822 bytes)
- `assets/publisher_profiles.json` sha256 `1e1b1b5a4e0e3dfc57877f2abf1e96888fe6b65617234b078f193b8f76e0ebe9` (10870 bytes)
- `floe.json` sha256 `516dd116778953aa47d3c5cb269edadf65cd434196211f6cad54c85e3591450d` (1097 bytes)
- `references/ADAPTATION-NOTES.md` sha256 `24fe13b327d9865e1985c639d017dc8144d5e486f3a2662bf2bb57aba97554bf` (12029 bytes)
- `references/color_palettes.md` sha256 `c9b6a596dd1dd1e08050fdcbb304a0268ee515bce2120a9bbd3fba31cd7fa119` (9094 bytes)
- `references/dependencies.json` sha256 `19b34f714e806ad1eb4377f14b64251acd03069ebc2376e2c1692f7e4ea47af4` (1771 bytes)
- `references/journal_requirements.md` sha256 `f7c4b6660eb70f7c5778d13908409e1dc690f00e3dfc8314f430feb89781740c` (11200 bytes)
- `references/licenses/LICENSE-NOTE.md` sha256 `0ec052eb23d8dcb07fb7866bf3cf1b1af76c2c1341b97b604187ff3bf902a58b` (1458 bytes)
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `09b02a3c9df3053c55531d503357a9c7cde275970e6c3ceaa1ddf5f0e90b40c1` (1068 bytes)
- `references/matplotlib_examples.md` sha256 `74fd5977ce57b09b476285309559bbcbe3b1748943b719844b28a6b61378c041` (12165 bytes)
- `references/publication_guidelines.md` sha256 `5f70c6b22dbb5e0fae18b0f1197b8794896bf7afc059874bcf7afbd5aa86bbe5` (12853 bytes)
- `references/sources.md` sha256 `3ff34759c0fed3baf33286a8005fd81f0c3466a554c8b0d45f43ad30b1e5b505` (10697 bytes)
- `scripts/_common.py` sha256 `e4eea2c2e5f5d8cfa544c6bed152cdb88a3d7c7952df99bcd74b45077fd6f707` (4618 bytes)
- `scripts/export_plan.py` sha256 `c20962bf4c624b9939c80bd16815fc0a18fe2be285f0654a6a53704c663add0e` (19682 bytes)
- `scripts/figure_export.py` sha256 `ec19530a179c3b1cf1c1b5bb340f14d613b06711ba2cea74369e1fc9bda7c902` (23864 bytes)
- `scripts/image_metadata.py` sha256 `f295752b16ee0c87301607ee46b43a5814d23ab982df200a89647371313ccb8e` (36898 bytes)
- `scripts/palette_audit.py` sha256 `3a90b3c9a4a39dde6a341dc3de7b99cd2bca4773c66564fc90cdc2706a5a8165` (11654 bytes)
- `scripts/style_presets.py` sha256 `a2ad002eb962294db5a0cecf0ea62b8537930ee49909b834d6192a6531948bd5` (16597 bytes)
- `scripts/style_preview.py` sha256 `9f83fce33a78d3794b9116ca58b2e58124f1395abd9192e1e98fecf953a2909c` (7868 bytes)
- `scripts/viz_verify.py` sha256 `4c97fb17f24a5a0f7dc6a7132fba16b301761b9258d8eb5e292c08e5d89e5f34` (27978 bytes)

TOTAL 26 files listed + references/PROVENANCE.md = 27 archive members; 259300 bytes listed excluding this file.
