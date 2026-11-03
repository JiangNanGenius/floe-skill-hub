# Provenance — proposal-builder

- Upstream repository: https://github.com/anthropics/knowledge-work-plugins
- Pinned commit: `2574e29377c7173d0cecffef29a6ecbd7f8ccb5d`
- Upstream path: `small-business/skills/proposal-builder`
- License: see `references/licenses/LICENSE-NOTE.md`; full upstream text is in `references/licenses/UPSTREAM-LICENSE.txt`.
- Fetch method: individual file retrieval from the pinned commit on 2026-10-31; no full-repository clone or vendoring.
- Variant: this is an adapted guide-only package. The upstream original is not shipped here; original and adapted variants remain separate.
- Execution status: guide-only; static package validation only. Nothing in this package was executed to claim runtime qualification.

## Adaptations

Frontmatter normalized; connector-specific discovery, ledger/payments pricing, cloud-template, DocuSign and invoice/payment paths removed or replaced with workspace-file equivalents. Core discovery, comparable-pricing, scope, exclusion and owner-risk workflow retained. Added voice/output rules and synthetic fixture.

## File mapping and hashes

- `SKILL.md` ← upstream `SKILL.md` (upstream sha256 `e558016c080898debf1e4e944826a562861c724144101cbc9ab6b99c0d362d0b`)
- `references/discovery_extraction.md` ← upstream `reference/discovery_extraction.md` (upstream sha256 `29517a931060b9487c921d0371832173c0cc87520ec49e6966663e410fbac772`)
- `references/gotchas.md` ← upstream `reference/gotchas.md` (upstream sha256 `4d359e80b8b26ae012e80cad84a09488af5e28643f28c9c784ac3dfe3093b13e`)
- `references/output_template.md` ← upstream `reference/output_template.md` (upstream sha256 `347dbe087f605497194059350e8c660a2ceb898be7c8820069b6b3c1d65a8e9e`)
- `references/pricing_method.md` ← upstream `reference/pricing_method.md` (upstream sha256 `3d17766897dff029c196a9a1fcf29dc20b7978f3cdcb31d3e3ec773d2a11963f`)
- `references/proposal_structure.md` ← upstream `reference/proposal_structure.md` (upstream sha256 `40010ac2e54737c8c53ecca8ee4b4bfe6ad606be2feabc4ac2401bee8cbc4a5d`)

## Package file hashes

- `SKILL.md` sha256 `e989975afb141be01538565e40c2269dce7f485276dff4e91e69bfa3e72a6ef8`
- `assets/examples/expected-output.md` sha256 `c7bd913ddeae89ec8ac0ee89c39cf3a2aa34af383efb38cd65519c3971bbe7a2`
- `assets/examples/input.md` sha256 `2b6c726cd3f6be11d013e7a58480a767e25e998ed41ec04fa4ef7080e4749c19`
- `floe.json` sha256 `2f525b610953e5fb476c936fcfde1efd20fc1d79df3c472ca32aa560c376065d`
- `references/discovery_extraction.md` sha256 `2e4637b9ff08844793ae85ee04282fed24928bc75eceac9bf98554e2e444f2a9`
- `references/gotchas.md` sha256 `fc01552630d7e37ddb38bcc65c1c084f482b74435c4f34281c695e7ae917bec6`
- `references/licenses/LICENSE-NOTE.md` sha256 `3ea48bf70c4d53262e8d4bee5d004c9fb714674f2a521f7d1b40a709227574ed`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `a6946284993aeec75c7d75906064b66210c46051e562077efb30eb6dcfe72e26`
- `references/output_template.md` sha256 `826243210dea1bfbe330e806dce4cd93e1c1a81cebcf8468d4410878267ec4e3`
- `references/pricing_method.md` sha256 `c9cca778f8d3ba1ad77398e18479c2e587ca136f1c2f6e159595aa39e4bf0544`
- `references/proposal_structure.md` sha256 `e3612a09c2c4b8c5964fa879aa704d7896f2bcf0b69b1893b7ddf6f36969d17e`
- `references/voice-and-output.md` sha256 `436226287d37aac8cb835565499669f9d0dafe90488e9c9a87895dd9d676bca3`

## Audit repairs (2026-10-31)

- Removed the invented USD 1,800 crane/lift price and the 10-business-day start commitment from the synthetic expected output; replaced them with a requirement for an actual quote and an owner-confirmed start date. Added an explicit haul-away assumption and retained every input/rate-card number.
- Added illustrative-number caveats to the pricing/output references so the example figures are not treated as live rates. Root license copy is unchanged and byte-identical; the note now records the upstream trailing fragment.

## Notes

- Upstream license/NOTICE: the repository root license file is preserved byte-for-byte, including its unrelated trailing fragment; only the Apache-2.0 text is relied on. No upstream NOTICE file was present at the pin.
- The synthetic fixtures under `assets/examples/` are authored for this package, not upstream files.
- PROVENANCE.md intentionally omits its own hash.
- No private path, credential, server address or raw private evidence is included.
