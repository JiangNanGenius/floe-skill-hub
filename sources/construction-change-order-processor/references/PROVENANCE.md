# Provenance — construction-change-order-processor

- Upstream repository: https://github.com/datadrivenconstruction/DDC_Skills_for_AI_Agents_in_Construction
- Pinned commit: `410ed1e71e4a5c6fd231afd0c8d1e586a9f546e8`
- Upstream path: `1_DDC_Toolkit/Cost-Management/change-order-processor`
- Licence: MIT for the SKILL.md instructions (root LICENSE); NOTICE.md excludes the book and the CC BY-NC CWICR compilation; full text at `references/licenses/UPSTREAM-LICENSE.txt`
- Upstream notice: `references/licenses/UPSTREAM-NOTICE.md` (byte-identical)
- Retrieval: subtree-only fetch at the pinned commit on 2026-10-31; no full-repository vendoring. Public upstream only; no private path is recorded here.

## What was kept and mapped

| Upstream file | Floe package file | Treatment |
| --- | --- | --- |
| `SKILL.md` | `SKILL.md` | Rewritten as a guide-only procedure; business case, enums, cost model, formulas, state machine, summary and log fields preserved |
| `instructions.md` | `references/UPSTREAM-METHOD.md` | Input/output constraints folded into the method extraction; upstream code not copied |
| `LICENSE` | `references/licenses/UPSTREAM-LICENSE.txt` | Byte-identical |
| `NOTICE.md` | `references/licenses/UPSTREAM-NOTICE.md` | Byte-identical |

## Excluded (audited)

- `SKILL.md Python code blocks` — Not shipped as executable code; formulas, state machine and summary rules are preserved in the guide and UPSTREAM-METHOD.md

## Adaptations

- Replaced the Python class implementation with a deterministic change-order procedure, state machine and explicit arithmetic.
- Added illegal-transition guards, named-approver requirements and history-preservation rules.
- Added a worked synthetic example and expected totals; labelled the 10/10 defaults as examples, not mandated rates.
- Added Floe runtime boundaries, change-order control checklist and synthetic input.
- No dependency (pandas/openpyxl), script, API or network capability is shipped.

## Auditor review (2026-10-31)

- `SKILL.md`: made optional XLSX output conditional on the App's Office tools being available.
- `assets/examples/change-order-input.md`: replaced the instruction to record a fictional approval with a supplied scenario record that the guide only transcribes.
- `assets/examples/expected-change-order.md`: added the matching acceptance check so the guide does not decide or create an approval.
- `references/UPSTREAM-METHOD.md`: clarified that the single-order output preserves the contract-value summary while the upstream multi-order aggregates remain derivable from the register.
- Arithmetic and the approval state machine were rechecked; no totals, rates or source text were changed beyond the localized wording repairs above.

## Execution status

- Guide-only package. No upstream script, dependency, model or API was executed to claim verification. Host checks cover JSON/schema shape, file hashes, absence of binaries/scripts and text consistency only.
- No execution-verified or guest-verified claim is made. App rendering and real user acceptance remain with the coordinator.

## Notes

- The upstream skill is code-first. This package preserves the method but does not ship or execute the upstream Python. AIA G701 is referenced only as an upstream form example; it is not reproduced.

## File inventory (sha256, this checkout; PROVENANCE.md self-hash intentionally omitted)

- `SKILL.md` sha256 `b715678a924308f9d1cce9f94aeb0ebda617338e62ddeb335f5955efbd3a03f5`
- `floe.json` sha256 `33925607c565f81ca76e218124bf9784a3d6ea8ed1eedb1ef66c59bb5e963040`
- `assets/examples/change-order-input.md` sha256 `b7383232260cd9564605c51db40997ea636a46b11daebcd5416294d518d7e4e7`
- `assets/examples/expected-change-order.md` sha256 `c9955a15e8c792e21860ffc764c90170d4079e6c387334586a17825be3cf8eed`
- `references/CHANGE-ORDER-CONTROL.md` sha256 `2a5d29e301608a54a404144b0631d69f56c9b1bc03ad4ce3e89265d846ec88e0`
- `references/UPSTREAM-METHOD.md` sha256 `4b657379e4eeaf06ea731e4fe058fb02fc92084f0af6636df344e73aacbdd468`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `b3942ae24f8a53f13fc75541877d4167014f201efd4eb1b62efd083e6352d500`
- `references/licenses/UPSTREAM-NOTICE.md` sha256 `5be09965b6c608dc55ce878b2b2ae0f43b3248326f309931fc83faa2b41d517e`
