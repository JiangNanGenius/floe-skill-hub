# Expected output — risk-assessment (synthetic)

Risk register draft — no control tested, no risk accepted, nothing changed. Built only from the supplied facts. Scale: default 3x3 (labeled unconfirmed).

## 1. Scope header

Project Ledger inventory-count rollout (synthetic); all six categories; default 3x3 scale, **unconfirmed**; as-of 2026-10-30. Acceptance threshold: **UNKNOWN** (not supplied) — monitor/act splits need it.

## 2. Risk register (sorted; unknowns by the stated rules)

| ID | Risk | Category | Likelihood | Impact | Level | Evidence class | Owner |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R1 | Count data lost during handheld sync failures | Operational | high | high | **Critical** | observed (3 pilot-week failures) | warehouse ops lead |
| R3 | Missed safety induction for contract counters | Compliance | medium | high | **High** | observed (induction log gap) | site safety officer |
| R6 | Handheld devices lost with unsynced data | Security | medium | high | **High** | observed (Q2 asset log) | IT lead |
| R5 | Public complaint about count accuracy | Reputational | low | high | **Medium** | unknown (no history supplied) | comms lead |
| R2 | Contractor budget overrun above 10% | Financial | **unknown** | medium | **unknown (impact medium)** | unknown | project manager |
| R4 | Competitor launches first | Strategic | **unknown** | medium | **unknown (impact medium)** | reported (dated analyst note) | product lead |

R5's likelihood is **low on no supplied history — flagged**: a low grade without a fact is weak evidence; the fact-finding queue asks for any complaint history. (If the team prefers, treat likelihood as unknown until history is supplied.)

## 3. Level counts

Critical 1, High 2, Medium 1, Low 0, unknown 2. Counts match the register rows.

## 4. Fact-finding queue

1. R2 — what do the contractor quotes say about total cost vs the 10% buffer? Suggested owner: project manager.
2. R4 — is there any launch-date evidence beyond the dated analyst note? Suggested owner: product lead.
3. R5 — any complaint history for the legacy counting process? Suggested owner: comms lead.

## 5. Control-evidence table

| Control | Should do | Class | Period | Note |
| --- | --- | --- | --- | --- |
| C1 | nightly auto-sync with failure alerts | **tested - exception** | September test records | alerts fired on 2 of 3 failures |
| C2 | contractor budget approval gate | **untested** | — | approval policy PDF only |
| C3 | device encryption | **untested (reported assurance supplied)** | — | the Q2 audit attestation (dated, signed) is reported assurance about the control, not test results of operation; its contents are observed as supplied, not externally verified |
| C4 | manual sync check by shift supervisor | **untested** | — | no test records supplied |

Counts: 0 tested-effective, 1 tested-exception, 3 untested. Untested controls count as no risk reduction.

## 6. Residual view

- R1: tested C1 (exception) + untested C4 → **pending**. The September exception routes to the register as an open item for the ops lead.
- R3: untested C2 → **pending**.
- R6: untested C3 → **pending**. The dated signed attestation is reported assurance for the organization to assess; no impact reduction is inferred from the encryption label, and the guide does not grade a residual.

## 7. Mitigation plan (proposals unless supplied)

- R1: fix the missed-alert path in C1 and test C4; owner: warehouse ops lead with IT lead.
- R3: run contractor inductions before 2026-11-17; owner: site safety officer.
- R6: enforce sync-before-shift-end; owner: warehouse ops lead.

No risk is marked accepted; acceptance belongs to the organization's governance.

## 8. Claim boundary

This register scores only from supplied facts; unknowns were not averaged away; the default scale is labeled unconfirmed; unattested controls were not counted as effective; attestations are recorded as reported assurance for the organization to assess; document contents are observed as supplied, not externally verified; no residual was inferred from a control label; and no compliance determination is made or implied. Synthetic example — no real organization data.
