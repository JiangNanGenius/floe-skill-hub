# Expected output — audit-support (synthetic)

Workpaper draft — nothing tested by the guide, no conclusion reached, no compliance asserted. Built only from the supplied control and population facts. Synthetic data; no real audit engagement.

## 1. Workpaper header

Control P2P-TWM-04 (synthetic) | Period 2026-01-01 to 2026-06-30 | Tester: ______ (blank) | Reviewer: ______ (blank).

## 2. Control identification

Three-way match verification (PO, receipt, invoice) before payment release. Type: automated with IT-dependent manual review of exceptions. Frequency: per-transaction (large population). Assertion: accuracy and existence of accounts payable. Risk rating: moderate (supplied by the org).

## 3. Test design

Objective: determine whether the control operated effectively for the period. Procedures: (1) inspect the match record for each selected event; (2) for exceptions, confirm the manual review was performed and documented; (3) re-perform the match for a selected item and compare results. Expected evidence: match records, dated and attributable exception approvals, audit logs.

## 4. Sample selection (arithmetic shown)

Method: systematic. Population: 1,000 payment-release events (supplied listing, sequentially numbered 1-1000; completeness reported by the process owner and not independently verified). Size table lookup: per-transaction (large pop.) + moderate risk → 40; the table is illustrative guidance, not a statistically derived or assurance-backed justification, and the applied size is capped at the population (min(40, 1000) = 40). Interval = population / sample = 1000 / 40 = **25**. Supplied random start: **11** (within the first interval - valid). Selected items: 11, 36, 61, 86, 111, 136, 161, 186, 211, 236, 261, 286, 311, 336, 361, 386, 411, 436, 461, 486, 511, 536, 561, 586, 611, 636, 661, 686, 711, 736, 761, 786, 811, 836, 861, 886, 911, 936, 961, 986 (**40 items**; first 11, last 986, step 25). The guide verified the arithmetic; the tester pulls the items from the system of record.

## 5. Test execution table

| Item | Result | Exception | Evidence examined |
| --- | --- | --- | --- |
| 1-40 (from the selection) | UNKNOWN | UNKNOWN | to be filled by the tester |

Conclusion: **pending - tester completes per-item results and sign-off.**

## 6. Evidence structural-completeness table

| Item | Class | Basis |
| --- | --- | --- |
| E1 | **structurally complete** | dated 2026-02-10, attributable (system admin role recorded), specific config screenshot |
| E2 | **structurally incomplete** | undated; "finance team" mailbox is not an identifiable approver |
| E3 | **structurally complete** | dated 2026-03-31, system-generated, item-range specific |
| E4 | **structurally incomplete** | verbal only; no corroboration, date or attribution |

Counts: 2 structurally complete, 2 structurally incomplete. Structural completeness is not authenticity, is not proof the control operated, and is not auditor sufficiency: the tester authenticates each item and determines sufficiency. E2 needs an identifiable approver and date; E4 needs corroborating documentation. Population completeness is reported as supplied, not independently verified.

## 7. Deficiency evaluation (indicators only)

Supplied indicators: structurally incomplete exception-review evidence for the sampled period (E2, E4) and a prior-period deficiency in the same control. Classification: **deficiency** — indicators support a control gap, not (on the supplied facts) a significant deficiency or material weakness. A qualified reviewer makes the final call.

## 8. Aggregation analysis

One other minor documentation gap was noted in the same cycle. Combined effect: documented and evaluated on the supplied facts as not more than inconsequential. If further gaps surface, re-evaluate in combination.

## 9. Remediation plan (proposals)

Re-obtain the exception approvals with dates and named approvers; document the manual review; re-test after remediation. Owner roles: AP process owner with the control owner. Target dates: to be set by the owner — **UNKNOWN**.

## 10. Claim boundary

This draft does not test the control, does not pull samples from any system, does not conclude effective/deficient beyond the indicator-based draft, and does not assert or imply any real SOX or other compliance. Conclusions and sign-off belong to qualified professionals. Synthetic example — invented control, population and evidence.
