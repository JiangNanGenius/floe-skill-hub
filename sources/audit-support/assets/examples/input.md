# Synthetic input — audit-support

All controls, populations and evidence are invented for this fixture. No real audit data is included, and nothing here asserts any real compliance.

## Control (from the controls team)

| Field | Value |
| --- | --- |
| Control ID | P2P-TWM-04 (synthetic) |
| Description | Three-way match verification (PO, receipt, invoice) before payment release |
| Type | Automated with IT-dependent manual review of exceptions |
| Frequency | Per-transaction (large population) |
| Assertion addressed | Accuracy and existence of accounts payable |
| Risk rating assigned by the org | Moderate |

## Population (supplied by the process owner)

All payment-release events for the period 2026-01-01 to 2026-06-30: 1,000 events, sequentially numbered 1-1000 in the supplied listing.

## Sampling approach (chosen by the tester; supplied here)

Systematic selection. Random start supplied by the tester: 11.

## Test procedures (supplied)

1. Inspect the match record for each selected event.
2. For exceptions, confirm the manual review was performed and documented.
3. Re-perform the match for a selected item and compare results.

## Evidence already gathered (supplied)

| Item | What | Date | Performer |
| --- | --- | --- | --- |
| E1 | Screenshot of the match enforcement config | 2026-02-10 | System admin (role recorded) |
| E2 | Email approval of an exception write-off | undated | "Finance team" mailbox |
| E3 | Audit log extract for matched items 500-520 | 2026-03-31 | System |
| E4 | Verbal note from the AP supervisor that reviews happened | none | — |

## Prior-period context

One deficiency noted last period in the manual exception review (supplied).
