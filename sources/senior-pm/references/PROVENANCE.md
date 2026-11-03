# Provenance — senior-pm

- Upstream repository: https://github.com/alirezarezvani/claude-skills
- Pinned commit: `6d2f02ea077eead1bee5411a31bcc6db5a11a70c`
- Upstream path: `project-management/skills/senior-pm`
- License: see `references/licenses/LICENSE-NOTE.md`; full upstream text is in `references/licenses/UPSTREAM-LICENSE.txt`.
- Fetch method: individual file retrieval from the pinned commit on 2026-10-31; no full-repository clone or vendoring.
- Variant: this is an adapted guide-only package. The upstream original is not shipped here; original and adapted variants remain separate.
- Execution status: guide-only; static package validation only. Nothing in this package was executed to claim runtime qualification.

## Adaptations

Frontmatter normalized. The three upstream Python helpers are excluded from this guide-only package; deterministic health scoring, RAG bands, EMV, three-point estimation and capacity formulas are restated in SKILL.md. Monte Carlo is explicitly not run. Templates and references retained; script invocations removed. Added synthetic fixture.

## File mapping and hashes

- `SKILL.md` ← upstream `SKILL.md` (upstream sha256 `60ae71507d3752a1c7504ae92e0a503a2c00cb57c1d1a025fcacdd6b9cb02a8f`)
- `references/portfolio-kpis.md` ← upstream `references/portfolio-kpis.md` (upstream sha256 `dcd60fff32fd510792178a983b5739d39f7fe9400b5b681cb685eeb55e0283a5`)
- `references/portfolio-prioritization-models.md` ← upstream `references/portfolio-prioritization-models.md` (upstream sha256 `f926f0231a48696f8d8dc5c08f531f19da6cc37d0193b8d381b8d187de759264`)
- `references/risk-management-framework.md` ← upstream `references/risk-management-framework.md` (upstream sha256 `326fdcf2826b7e44b196c261e6613f727a922f9e0f8e6e103809a49d962feb58`)
- `assets/project_charter_template.md` ← upstream `assets/project_charter_template.md` (upstream sha256 `a407af5150d5f5270708628fa66d06ae3dce705691cf7c3b125ea32b4661f45b`)
- `assets/executive_report_template.md` ← upstream `assets/executive_report_template.md` (upstream sha256 `dd97e08e464976ed98be38a1298429dd81e4a1873d05327942338f741ac92dd4`)
- `assets/raci_matrix_template.md` ← upstream `assets/raci_matrix_template.md` (upstream sha256 `5de71bc4511b3fb6ca2df714879a9fbd63b70917172569f7c00bcaf02e89f6a1`)
- `assets/sample_project_data.json` ← upstream `assets/sample_project_data.json` (upstream sha256 `6349aa9bdb2bae73480059b8189f3b6c87636a873ddebec0a40d403ef4c515f3`)
- `assets/expected_output.json` ← upstream `assets/expected_output.json` (upstream sha256 `93bc519bf88393b37235c6489ee3d945dc6f105855e1c268bbc581011e6fde1a`)
- Excluded upstream `scripts/project_health_dashboard.py` — inspected for the formulas restated in SKILL.md; not shipped because this is a guide-only batch. Its logic is described in SKILL.md where behavior depends on it.
- Excluded upstream `scripts/risk_matrix_analyzer.py` — inspected for the formulas restated in SKILL.md; not shipped because this is a guide-only batch. Its logic is described in SKILL.md where behavior depends on it.
- Excluded upstream `scripts/resource_capacity_planner.py` — inspected for the formulas restated in SKILL.md; not shipped because this is a guide-only batch. Its logic is described in SKILL.md where behavior depends on it.

## Package file hashes

- `SKILL.md` sha256 `26de54f0ce69becc6b31662a9685eeccc74bed7c59b1825c16d1564fc2f1e4b7`
- `assets/examples/expected-output.md` sha256 `b8dd8f8f75ce51f0109957e544f63903b6099cae0713152f2f5dff10953d8082`
- `assets/examples/input.md` sha256 `2c6b87bbce0fd5dd3fdecc65ace1084f8012df2a8f11f480074a008682455e91`
- `assets/executive_report_template.md` sha256 `dd97e08e464976ed98be38a1298429dd81e4a1873d05327942338f741ac92dd4`
- `assets/expected_output.json` sha256 `f4d2ff138f7e631cd7dec8284710211c169b747d950c3da28ce73657dd81da75`
- `assets/project_charter_template.md` sha256 `a407af5150d5f5270708628fa66d06ae3dce705691cf7c3b125ea32b4661f45b`
- `assets/raci_matrix_template.md` sha256 `5de71bc4511b3fb6ca2df714879a9fbd63b70917172569f7c00bcaf02e89f6a1`
- `assets/sample_project_data.json` sha256 `6349aa9bdb2bae73480059b8189f3b6c87636a873ddebec0a40d403ef4c515f3`
- `floe.json` sha256 `ac76fb9c1b2572aabb97de9b098997754c0c575f251a3ba50d757d64b0cb0276`
- `references/licenses/LICENSE-NOTE.md` sha256 `7d75bc63746541c432a663f28e1acc91d6b093ed0dd71285c369d6ff4084e939`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `a20126646f93d32a8989c3cf4772d59194f405034f7babe7daebeac22b8ab151`
- `references/portfolio-kpis.md` sha256 `dcd60fff32fd510792178a983b5739d39f7fe9400b5b681cb685eeb55e0283a5`
- `references/portfolio-prioritization-models.md` sha256 `f926f0231a48696f8d8dc5c08f531f19da6cc37d0193b8d381b8d187de759264`
- `references/risk-management-framework.md` sha256 `326fdcf2826b7e44b196c261e6613f727a922f9e0f8e6e103809a49d962feb58`

## Audit repairs (2026-10-31)

- Corrected the illustrative 10% budget-overrun score from about 70 to 75 (halfway through the 5-15% amber band), added the quality-score versus test-coverage clarification, and documented that the written risk-response bands differ from the excluded helper's internal tolerance labels.
- Corrected Project B quality to 99.1% / score 98 / contribution 19.60 / composite 98.0; corrected Project A's planned-duration denominator to 364 days; corrected the portfolio strongest dimension to timeline; changed the 12.0 risk response to Mitigate under the written bands.
- Removed the `usage_examples` command block from `assets/expected_output.json` and changed its description to a reference-only upstream shape, because the helper scripts are not shipped. No thresholds or formulas were changed.
- Added an explicit boundary rule for the overlapping written response bands (8 → Transfer, 12 → Mitigate, 18 → Avoid) so a score at a boundary has one deterministic response.
- Labeled the three-point scenario as illustrative in the acceptance check, because its 6/9/16-week inputs are hypothetical rather than measured portfolio data.
- The excluded health helper's float arithmetic truncates a 95% scope score to 94; the accepted expected output uses the mathematically correct 95 and the resulting 98.0 composite from the stated linear interpolation. No helper is shipped or claimed as executed.

## Notes

- Upstream license/NOTICE: the repository root license file is preserved; no upstream NOTICE file was present at the pin.
- The synthetic fixtures under `assets/examples/` are authored for this package, not upstream files.
- PROVENANCE.md intentionally omits its own hash.
- No private path, credential, server address or raw private evidence is included.

## Root statistical review (2026-10-31)

Corrected portfolio risk aggregation: EMVs add irrespective of correlation, while covariance uses supplied monetary standard deviations and each distinct pair once. Missing dispersion inputs stay uncalculated. Three-point scenario endpoints are not labelled P50/P90 quantiles. No simulation or external runtime is claimed.
