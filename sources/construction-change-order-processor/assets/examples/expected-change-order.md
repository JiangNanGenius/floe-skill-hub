# Expected output — synthetic change order

> **Synthetic acceptance example.** USD, tax excluded, pricing date 2026-10-31, original contract USD 50,000,000.00.

## Cost detail

| Description | Qty | Unit | Unit cost | Item markup | Item total | Category |
| --- | --- | --- | --- | --- | --- | --- |
| Electrical outlets | 50 | EA | 150.00 | 0% | 7,500.00 | material |
| Installation labour | 25 | HR | 85.00 | 0% | 2,125.00 | labor |

## Totals

| Metric | Amount |
| --- | --- |
| Direct cost | 9,625.00 |
| Overhead (10% on direct) | 962.50 |
| Profit (10% on 10,587.50) | 1,058.75 |
| **Total change** | **11,646.25** |
| Schedule impact | 5 days |

## Approval history

| Approver | Role | Action | Date | Comments |
| --- | --- | --- | --- | --- |
| Design Manager (fictional) | Reviewer | reviewed | 2026-10-20 | Scope and quantities checked |
| Owner's Representative (fictional) | Approver | approved | 2026-10-22 | Approved per owner request |

Status: `approved`. Approved date: 2026-10-22. Approved by: Owner's Representative (fictional).

## Contract summary

| Metric | Amount |
| --- | --- |
| Original contract | 50,000,000.00 |
| Approved changes | 11,646.25 |
| Current contract | 50,011,646.25 |
| Pending changes | 0.00 |
| Potential contract | 50,011,646.25 |
| Change percent | 0.0% (0.0233% unrounded) |
| Total schedule impact (approved) | 5 days |

## Acceptance checks

- [ ] Direct cost = 7,500.00 + 2,125.00 = 9,625.00.
- [ ] Overhead = 9,625.00 × 10% = 962.50.
- [ ] Profit = (9,625.00 + 962.50) × 10% = 1,058.75.
- [ ] Total = 9,625.00 + 962.50 + 1,058.75 = 11,646.25.
- [ ] Status transitions `draft → pending_review → pending_approval → approved` only.
- [ ] Approval records a named approver, role and date.
- [ ] The approval is transcribed from the supplied scenario record; the guide did not decide or create it.
- [ ] Current contract = original + approved = 50,011,646.25.
- [ ] Change percent uses the original contract as denominator and is shown unrounded too.
- [ ] Schedule impact is 5 days with activity EL-03.
- [ ] The output does not claim contractual entitlement or legal approval.
