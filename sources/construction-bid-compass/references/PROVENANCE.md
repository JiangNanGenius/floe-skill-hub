# Provenance — construction-bid-compass

- Upstream repository: https://github.com/Maxbase91/procurement-skills
- Pinned commit: `d0dda5b201df30bc714520b2cee6f39038f1a1b6`
- Upstream path: `bid-compass`
- Licence: MIT (root LICENSE); NOTICE preserves the author copyright and authorship marks; full text at `references/licenses/UPSTREAM-LICENSE.txt`
- Upstream notice: `references/licenses/UPSTREAM-NOTICE.txt` (byte-identical)
- Retrieval: subtree-only fetch at the pinned commit on 2026-10-31; no full-repository vendoring. Public upstream only; no private path is recorded here.

## What was kept and mapped

| Upstream file | Floe package file | Treatment |
| --- | --- | --- |
| `SKILL.md` | `SKILL.md` | Adapted guide; frontmatter, activation and platform-specific output wording changed |
| `config.yaml` | `references/config.yaml` | Upstream configuration with a Floe note appended at the end |
| `references/category-advice.md` | `references/category-advice.md` | Byte-identical |
| `examples/sample-rfp-generation.md` | `assets/examples/sample-rfp-generation.md` | Upstream anonymised example with a Floe output-format note added; scenario content unchanged |
| `examples/sample-evaluation.md` | `assets/examples/sample-evaluation.md` | Upstream anonymised example; one upstream absolute output path replaced with a workspace-relative filename and a Floe output-format note added. Scoring text unchanged. |
| `LICENSE` | `references/licenses/UPSTREAM-LICENSE.txt` | Byte-identical |
| `NOTICE` | `references/licenses/UPSTREAM-NOTICE.txt` | Byte-identical |

## Adaptations

- Frontmatter reduced to Floe name/description; argument-hint and vendor-specific activation tag removed.
- DOCX/XLSX output instructions replaced by Markdown/CSV workspace outputs, with App document tools as the optional Office path; absolute output paths and present_files removed.
- Added the Floe runtime adaptation, untrusted-input and no-auto-send boundaries, evidence/arithmetic rules and acceptance examples.
- Added Floe synthetic input/expected output for a low-voltage cabling RFP; upstream anonymised examples retained.
- No script, API, dependency or network capability is shipped.

## Auditor review (2026-10-31)

- `SKILL.md`: clarified the weighted-score formula as `score × (weight ÷ 100)` and made DOCX/XLSX output conditional on the App's document tools being available.
- `assets/examples/sample-evaluation.md`: removed the upstream absolute output path and replaced it with a workspace-relative matrix filename.
- Both upstream examples: added a Floe output-format note so the upstream DOCX/XLSX illustration cannot be mistaken for the guide's default Markdown/CSV path.
- `assets/examples/expected-low-voltage-rfp.md`: recorded the proposed scoring weights as an open gate pending buyer confirmation, added an explicit draft/not-issued statement and aligned the acceptance checks.
- No scoring weights, mandatory gates, prices or source text were invented. The upstream license and notice remain byte-identical.

## Execution status

- Guide-only package. No upstream script, dependency, model or API was executed to claim verification. Host checks cover JSON/schema shape, file hashes, absence of binaries/scripts and text consistency only.
- No execution-verified or guest-verified claim is made. App rendering and real user acceptance remain with the coordinator.

## Notes

- No executable scripts were present in the upstream skill directory. The upstream examples are anonymised and fictional; they are retained as examples, not market evidence.

## File inventory (sha256, this checkout; PROVENANCE.md self-hash intentionally omitted)

- `SKILL.md` sha256 `51f83e07bca58dc879939daa62eb5e76bd5c80c7d4652cd38911320a3390365c`
- `floe.json` sha256 `7cdae8fcb50832a9650d09217e8603164ac381ef60bc2084f25a1cf84476b84a`
- `assets/examples/expected-low-voltage-rfp.md` sha256 `30301f929fcf020d6f9632973048660218baf9f9af8e3c27c2f584ec459e6ddc`
- `assets/examples/input-low-voltage-rfp.md` sha256 `165df9fe8931a969cfc61e383b7f0d509de0fb372ed907ae4caaaab0aa08a5f1`
- `assets/examples/sample-evaluation.md` sha256 `249af2b8d5dfd9d84d2e895c2055451db53423b62c19036d3c383ec5a5df6604`
- `assets/examples/sample-rfp-generation.md` sha256 `5a54e075b7dd6f35d42c0af40070dad728654344983559df7125ca7b907d359d`
- `references/category-advice.md` sha256 `16176fbdc568785d013d323ebb758da21b42c11043a90a940b8b784b134d63b3`
- `references/config.yaml` sha256 `9d0bf3410366aa1d5c88d40a5a8115629f7a61975af4b1e95d274b4d25488c94`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `4588d1c986df6acb12c3dfbfbbb38456a10d34b60362998d8e69b1c532c027d2`
- `references/licenses/UPSTREAM-NOTICE.txt` sha256 `98e9378d91d4c78e7aaaa15a7b824286bffb7bc8b93d777a5b77cb19057da42e`
