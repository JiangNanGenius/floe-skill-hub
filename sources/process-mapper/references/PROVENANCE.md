# Provenance — process-mapper

- Upstream repository: https://github.com/alirezarezvani/claude-skills
- Pinned commit: `6d2f02ea077eead1bee5411a31bcc6db5a11a70c`
- Upstream path: `business-operations/skills/process-mapper`
- License: see `references/licenses/LICENSE-NOTE.md`; full upstream text is in `references/licenses/UPSTREAM-LICENSE.txt`.
- Fetch method: individual file retrieval from the pinned commit on 2026-10-31; no full-repository clone or vendoring.
- Variant: this is an adapted guide-only package. The upstream original is not shipped here; original and adapted variants remain separate.
- Execution status: guide-only; static package validation only. Nothing in this package was executed to claim runtime qualification.

## Adaptations

Frontmatter normalized. The three upstream stdlib helpers are excluded from this guide-only package; their deterministic cycle-time formulas, profile thresholds and bottleneck rules are restated explicitly in SKILL.md. BPMN/Lean references retained; CLI commands removed from the template. Added synthetic fixture.

## File mapping and hashes

- `SKILL.md` ← upstream `SKILL.md` (upstream sha256 `834d55830ceb83c75688c1688fbfa1686e9ee030e926be967b1d487dc0b3d4a1`)
- `assets/process_template.md` ← upstream `assets/process_template.md` (upstream sha256 `bd2e6e58503f79bbf1f322cff8105b15bd3fca8eec04a160d4f3919f680b8739`)
- `references/bottleneck_anti_patterns.md` ← upstream `references/bottleneck_anti_patterns.md` (upstream sha256 `9b82dda59f49d94b79997ea0edf1bdd3ed7ca9f2caccfdf06cfa45c6531b0e0b`)
- `references/bpmn_essentials.md` ← upstream `references/bpmn_essentials.md` (upstream sha256 `c5aa74243e1123559520824bdea0f1c1cd920bdb9a25670c6cc7db5a00af0405`)
- `references/lean_six_sigma_canon.md` ← upstream `references/lean_six_sigma_canon.md` (upstream sha256 `3792bccf68be1215d25ff9fcf6cbe5d18514a6e519d36f00bf2472eed338a7e7`)
- Excluded upstream `scripts/process_documenter.py` — inspected for the formulas restated in SKILL.md; not shipped because this is a guide-only batch. Its logic is described in SKILL.md where behavior depends on it.
- Excluded upstream `scripts/bottleneck_detector.py` — inspected for the formulas restated in SKILL.md; not shipped because this is a guide-only batch. Its logic is described in SKILL.md where behavior depends on it.
- Excluded upstream `scripts/cycle_time_analyzer.py` — inspected for the formulas restated in SKILL.md; not shipped because this is a guide-only batch. Its logic is described in SKILL.md where behavior depends on it.

## Package file hashes

- `SKILL.md` sha256 `8f289be0bea3c1f256e8027f5fccc9e7ace2a71c84570997d45f072565461a01`
- `assets/examples/expected-output.md` sha256 `d6a87013f2ec82a825bac8d1c7e255c08095c44b59a6af8e213f8927aaf17c45`
- `assets/examples/input.md` sha256 `3f907f9803b7bef1df8b3885380b58b2403f57797d2495eadd3431633f1bcab7`
- `assets/process_template.md` sha256 `482520aaff6563a99b93ec956e36020aad340d918f5231ef764c6a9a4ec0bff0`
- `floe.json` sha256 `7a6c25027a807ef1dc6d413bb9ff6022f0586acc851a39f89325e05647cb6d19`
- `references/bottleneck_anti_patterns.md` sha256 `43a7068e233c26a7c0bfdaa5c06846177483fcaa10cc4049456533c23be9229c`
- `references/bpmn_essentials.md` sha256 `c5aa74243e1123559520824bdea0f1c1cd920bdb9a25670c6cc7db5a00af0405`
- `references/lean_six_sigma_canon.md` sha256 `eacc01550f03aac159b032fb71f13c32cf71914b6968bc586c52aedcbce07d35`
- `references/licenses/LICENSE-NOTE.md` sha256 `1b3cd785c574ae2e1efc78493d86fae601a7fee344950069e78c671b08154c0a`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `a20126646f93d32a8989c3cf4772d59194f405034f7babe7daebeac22b8ab151`


## Audit repairs (2026-10-31)

- Added an explicit R1/R2 impact-overlap note to the synthetic output and worked calculation so overlapping wait findings are not summed. Rechecked the cycle-time formulas, profile thresholds and R1-R3 severity rules against the pinned upstream helpers; no formula or threshold changes were needed.

## Notes

- Upstream license/NOTICE: the repository root license file is preserved; no upstream NOTICE file was present at the pin.
- The synthetic fixtures under `assets/examples/` are authored for this package, not upstream files.
- PROVENANCE.md intentionally omits its own hash.
- No private path, credential, server address or raw private evidence is included.

## Root statistical review (2026-10-31)

Summed stage P50/P90 values are labelled sequential screening totals rather than end-to-end quantiles. Little's Law requires matching long-run mean WIP/cycle time; the median-only synthetic fixture leaves throughput uncalculated. Parallel/conditional/rework paths require an explicit model. Upstream thresholds remain screening heuristics. No helper or process measurement was executed.
