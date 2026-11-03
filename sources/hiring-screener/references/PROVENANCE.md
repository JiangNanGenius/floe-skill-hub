# Provenance — hiring-screener

- Upstream repository: https://github.com/anthropics/knowledge-work-plugins
- Pinned commit: `2574e29377c7173d0cecffef29a6ecbd7f8ccb5d`
- Upstream path: `small-business/skills/hiring-screener`
- License: see `references/licenses/LICENSE-NOTE.md`; full upstream text is in `references/licenses/UPSTREAM-LICENSE.txt`.
- Fetch method: individual file retrieval from the pinned commit on 2026-10-31; no full-repository clone or vendoring.
- Variant: this is an adapted guide-only package. The upstream original is not shipped here; original and adapted variants remain separate.
- Execution status: guide-only; static package validation only. Nothing in this package was executed to claim runtime qualification.

## Adaptations

Frontmatter normalized; inbox/cloud/calendar/payroll/e-signature connector paths removed or replaced with workspace files and owner-performed actions. Rubric-first scoring, anonymization, evidence quotes, cannot-assess band and reply discipline retained. Added voice/output rules and synthetic fixture.

## File mapping and hashes

- `SKILL.md` ← upstream `SKILL.md` (upstream sha256 `0c08b3f5eb33f32ec1ad00ccddbd514d5318987aa70996742ad18bd2cf56221f`)
- `references/candidate_comms.md` ← upstream `reference/candidate_comms.md` (upstream sha256 `d53093d614e235ad1221651e570989ff3883c5a06311c03f05755273bf9b06e0`)
- `references/fair_screening.md` ← upstream `reference/fair_screening.md` (upstream sha256 `81d99b24c44c3a03aa9e2f5f08182de3b901edfae183c2df2a67cfa1a90b29d0`)
- `references/gotchas.md` ← upstream `reference/gotchas.md` (upstream sha256 `039b8ff1fc9726b01883382cb9fc3406c3b529cd0bf8f55bd97e408da7fb61cf`)
- `references/onboarding.md` ← upstream `reference/onboarding.md` (upstream sha256 `0bc9aca96ea88f8f621e76ad28c10bd0abdd96b80a57a6e896dd6f9dc5466916`)
- `references/rubric.md` ← upstream `reference/rubric.md` (upstream sha256 `9f3f799f4e4ccce4767112eb80455d3a69126a9dc124f16dcc6b9706ba7a1d79`)

## Package file hashes

- `SKILL.md` sha256 `d36c483a65c64f3e635e70e179deaae0e74999a2168ca8bcc3014a1dabd8bdbe`
- `assets/examples/expected-output.md` sha256 `180059bae6aaf7830d08174e91c3713090eaae15e94b7278090b32b8bb9f082f`
- `assets/examples/input.md` sha256 `86b33d345abf14bd8f713dfe9a9467d09b664e254a0aee18bff85b8a986ff7a7`
- `floe.json` sha256 `49d5bdefa9123b1e1298710b5eb0d53cbb06e661edf31f4327b488db1fa6b25a`
- `references/candidate_comms.md` sha256 `3045a5e2f9a1cb5dd5a2a5a9e085480c958acd45bdddb10239c531cbd2959536`
- `references/fair_screening.md` sha256 `81d99b24c44c3a03aa9e2f5f08182de3b901edfae183c2df2a67cfa1a90b29d0`
- `references/gotchas.md` sha256 `499ed5d18fbead7a538dfb9d9e2b67d700c56560faf5e0f268d9bb80de4c7f7f`
- `references/licenses/LICENSE-NOTE.md` sha256 `bc9882dac116326fa4c4c97d8ff19ff63b0bddc2fb7cdcc46bdcfaebff8f4e66`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `a6946284993aeec75c7d75906064b66210c46051e562077efb30eb6dcfe72e26`
- `references/onboarding.md` sha256 `e395ff47e73f9411483c571da220464d838fd58016a66d4ca2a209135375543c`
- `references/rubric.md` sha256 `e2548d019d9c71c4724928aa24e700c244b9a80c0a58288fd2cfe79591ad803e`
- `references/voice-and-output.md` sha256 `af6ea33d2a2bcb74f03040ae254da7b21341ebd634ad70ba2953102231c0f0f2`


## Audit repairs (2026-10-31)

- Corrected Morgan Silva's work-order score from 2 to 3 because the quoted evidence says work orders were documented, and corrected Riley Okafor's total from 41.8 to 41.7 by summing unrounded components. Updated the scoring check accordingly.
- Added a must-have status table and per-criterion quoted-evidence tables; marked the rubric order provisional while Morgan's EPA must-have is unresolved; replaced invented interview times, duration/location and hold date with owner-provided placeholders. Clarified that the fixture states licence but not the separate insurable-record condition, and that scoring was performed on anonymized summaries. The scoring method was not changed.

## Notes

- Upstream license/NOTICE: the repository root license file is preserved byte-for-byte, including its unrelated trailing fragment; only the Apache-2.0 text is relied on. No upstream NOTICE file was present at the pin.
- The synthetic fixtures under `assets/examples/` are authored for this package, not upstream files.
- PROVENANCE.md intentionally omits its own hash.
- No private path, credential, server address or raw private evidence is included.
