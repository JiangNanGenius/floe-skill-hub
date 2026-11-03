# Provenance — variance-analysis

- Upstream repository: https://github.com/anthropics/knowledge-work-plugins
- Pinned commit: `2574e29377c7173d0cecffef29a6ecbd7f8ccb5d`
- Upstream path: `finance/skills/variance-analysis`
- License: see `references/licenses/LICENSE-NOTE.md`; full upstream text is in `references/licenses/UPSTREAM-LICENSE.txt`.
- Fetch method: individual file retrieval from the pinned commit on 2026-10-31; no full-repository clone or vendoring.
- Variant: this is an adapted guide-only package. The upstream original is not shipped here; original and adapted variants remain separate.
- Execution status: guide-only; static package validation only. Nothing in this package was executed to claim runtime qualification.

## Adaptations

Frontmatter normalized; Floe guide-only adaptation header and input/output contract added. Upstream methodology body retained. No scripts or connectors existed.

## File mapping and hashes

- `SKILL.md` ← upstream `SKILL.md` (upstream sha256 `467db7de3fb118550d013409254e2d4a9f87385a661e154655bf3431919b0ba1`)

## Package file hashes

- `SKILL.md` sha256 `7f38e06883f8c434f11a5a08f70e7430bbab3402bdecd2eb4b350ccae31982a4`
- `assets/examples/expected-output.md` sha256 `5240135ab2d7332d33ae1df146974d4ddb783f7808290e7eaf02f0a6c59b2e0d`
- `assets/examples/input.md` sha256 `fbce0b23f350bd7216317b6e47d0b286ef2c66afe8ddc6361e05996f88da858a`
- `floe.json` sha256 `f44c3f6a09c557fc2c851440b87dd9ffd9af09964020a28f11cd1242ed35c422`
- `references/licenses/LICENSE-NOTE.md` sha256 `20d30660c3a18da6b32a4228b4eb73953c790286539bcaa844a809460d9f7803`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`

## Audit repairs (2026-10-31)

- Replaced the copied root `LICENSE` with the exact bytes of `finance/LICENSE` at the pinned commit (sha256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`) and updated the license pointer/note. The registry proposal already named `finance/LICENSE`; the prepared copy was the different root file.
- Corrected the three-way price/volume/mix formulas to use actual volume in the price and mix terms so the decomposition reconciles exactly, and corrected the rate variance to use actual headcount. The synthetic fixture was not changed and still ties.
- Reordered the synthetic investigation list to follow the output contract's absolute line-variance order and removed the ambiguous "drivers are independently material" claim for the below-threshold revenue line.
- Added the qualified-finance-professional review disclaimer to the expected output so its acceptance check is true.

## Notes

- Upstream license/NOTICE: the exact `finance/LICENSE` bytes are preserved; no upstream NOTICE file was present at the pin. The copied license was corrected from the different root `LICENSE` during this audit.
- The synthetic fixtures under `assets/examples/` are authored for this package, not upstream files.
- PROVENANCE.md intentionally omits its own hash.
- No private path, credential, server address or raw private evidence is included.
