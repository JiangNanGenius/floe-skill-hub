# Provenance — construction-estimate-builder

- Upstream repository: https://github.com/datadrivenconstruction/DDC_Skills_for_AI_Agents_in_Construction
- Pinned commit: `410ed1e71e4a5c6fd231afd0c8d1e586a9f546e8`
- Upstream path: `2_DDC_Book/3.1-Cost-Estimation/estimate-builder`
- Licence: MIT for the SKILL.md instructions (root LICENSE); NOTICE.md excludes the book and the CC BY-NC CWICR compilation; full text at `references/licenses/UPSTREAM-LICENSE.txt`
- Upstream notice: `references/licenses/UPSTREAM-NOTICE.md` (byte-identical)
- Retrieval: subtree-only fetch at the pinned commit on 2026-10-31; no full-repository vendoring. Public upstream only; no private path is recorded here.

## What was kept and mapped

| Upstream file | Floe package file | Treatment |
| --- | --- | --- |
| `SKILL.md` | `SKILL.md` | Rewritten as a guide-only procedure; business case, data model, formulas, defaults, validation and output fields preserved |
| `instructions.md` | `references/UPSTREAM-METHOD.md` | Input/output constraints and defaults folded into the method extraction; upstream code not copied |
| `LICENSE` | `references/licenses/UPSTREAM-LICENSE.txt` | Byte-identical |
| `NOTICE.md` | `references/licenses/UPSTREAM-NOTICE.md` | Byte-identical |

## Excluded (audited)

- `SKILL.md Python code blocks` — Not shipped as executable code; the model/formulas are preserved in the guide and UPSTREAM-METHOD.md

## Adaptations

- Replaced the Python class implementation with a deterministic line-item/estimate procedure and explicit markup formulas.
- Added basis, currency/tax, source-note and validation rules; clarified compounding and rounding.
- Added a worked synthetic example and expected totals; labelled the 15/10/5 defaults as examples, not market rates.
- Added Floe runtime boundaries, reviewer checklist and synthetic CSV input.
- No dependency (pandas/openpyxl), script, API or network capability is shipped.

## Auditor review (2026-10-31)

- `SKILL.md`: made optional XLSX output conditional on the App's Office tools being available.
- `assets/examples/expected-totals.md`: added the explicit "estimate, not a tender/fixed quote/final account" label to match the guide's boundary.
- `references/UPSTREAM-METHOD.md`: corrected the output description to a WBS-coded line-item table; grouping is optional.
- The line-item, category and markup arithmetic was independently recomputed; no rates, totals or source text were changed beyond the localized wording repairs above.

## Execution status

- Guide-only package. No upstream script, dependency, model or API was executed to claim verification. Host checks cover JSON/schema shape, file hashes, absence of binaries/scripts and text consistency only.
- No execution-verified or guest-verified claim is made. App rendering and real user acceptance remain with the coordinator.

## Notes

- The upstream skill is code-first. This package preserves the method but does not ship or execute the upstream Python. The synthetic unit rates are illustrative, not market data.

## File inventory (sha256, this checkout; PROVENANCE.md self-hash intentionally omitted)

- `SKILL.md` sha256 `aca3b34f93bf81126ecdfacaba7c902e762ec25afcec20a58cab9ed651e927ce`
- `floe.json` sha256 `ad359c4a764fdfa52859e5298de492a7759dd5754ad390c42e9fc4a233d2dc3d`
- `assets/examples/estimate-lines.csv` sha256 `f4c2da6c5a2f298c4915d0a398486844c586b3329a81cb39fd51c9ec1cff013a`
- `assets/examples/expected-totals.md` sha256 `3bbe72553f8d1d324136232ef59f4787764f74a1c2b5b6dfc747950f23472dea`
- `references/ESTIMATE-REVIEW.md` sha256 `eed87c3e3893f6bd37025cfaa0c8a7236afe6ea83d632588531e33af272043f0`
- `references/UPSTREAM-METHOD.md` sha256 `4b179ce231878921b3cd3851224f0947aeb002dc43c99edf94bf3f80b75afe59`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `b3942ae24f8a53f13fc75541877d4167014f201efd4eb1b62efd083e6352d500`
- `references/licenses/UPSTREAM-NOTICE.md` sha256 `5be09965b6c608dc55ce878b2b2ae0f43b3248326f309931fc83faa2b41d517e`
