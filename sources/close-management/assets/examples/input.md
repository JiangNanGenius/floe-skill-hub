# Synthetic month-end close status input

> Synthetic fixture. Entity, people roles, dates and statuses are invented for acceptance testing. Not financial advice and not a real close.

## Request

Entity **Northwind Components Ltd (synthetic)**, period **October 2026** (period end 2026-10-31), management accounts under the entity's local GAAP, currency USD. The close target is **T+5 business days**. The status snapshot is **09:00 local on T+2 (2026-11-03)**. The calendar is Monday-Friday with no public holidays in the window.

Produce a status dashboard, dependency-gate view, blocker impact and a remaining close calendar. Do not claim the period is closed or the statements are final.

## Task list

| ID | Task | Owner (role) | Day | Depends on | Status | Blocker / note |
| --- | --- | --- | ---: | --- | --- | --- |
| T01 | Cash receipts and disbursements posted | Staff accountant - cash | T+1 | - | Complete |  |
| T02 | Final bank statement obtained | Treasury analyst | T+1 | - | Complete |  |
| T03 | Payroll posted | Payroll specialist | T+1 | - | Complete |  |
| T04 | Depreciation run | Fixed-asset accountant | T+1 | - | Complete |  |
| T05 | Prepaid amortization posted | Staff accountant - expenses | T+1 | - | Complete |  |
| T06 | AP accrual prepared | AP supervisor | T+1 | - | Blocked | Two department spend confirmations outstanding; expected T+3 |
| T07 | Intercompany transactions posted | Intercompany accountant | T+1 | - | Complete |  |
| T08 | Bank reconciliation | Staff accountant - cash | T+2 | T01, T02 | In Progress | 40% complete |
| T09 | Revenue recognition entries | Revenue accountant | T+2 | T01, T03 | Complete |  |
| T10 | AR subledger reconciliation | AR supervisor | T+2 | T09 | Blocked | Billing system period close delayed to start of T+3 |
| T11 | AP subledger reconciliation | AP accountant | T+2 | T06 | Not Started | Waiting on T06 |
| T12 | FX revaluation | Treasury analyst | T+2 | T01, T06 | At Risk | Month-end FX rates not yet received; expected end of T+2 |
| T13 | Remaining accrual journal entries | GL accountant | T+2 | T06, T12 | Not Started | Waiting on T06 and T12 |
| T14 | Fixed-asset register reconciliation | Fixed-asset accountant | T+2 | T04 | Complete |  |
| T15 | Balance sheet reconciliations | Accounting team | T+3 | T08, T10, T11, T13, T14 | Not Started | Gate |
| T16 | Intercompany reconciliation | Intercompany accountant | T+3 | T07 | Not Started |  |
| T17 | Adjusting journal entries from reconciliations | GL accountant | T+3 | T15, T16 | Not Started |  |
| T18 | Preliminary trial balance | Controller | T+3 | T17 | Not Started | Gate |
| T19 | Tax provision | Tax accountant | T+4 | T18 | Not Started |  |
| T20 | Equity roll-forward | GL accountant | T+4 | T18 | Not Started |  |
| T21 | Consolidation and eliminations | Consolidation accountant | T+4 | T16, T18 | Not Started |  |
| T22 | Draft financial statements | Controller | T+5 | T18, T19, T20, T21 | Not Started |  |
| T23 | Flux analysis and variance explanations | FP&A analyst | T+5 | T22 | Not Started |  |
| T24 | Management review | Finance director | T+5 | T23 | Not Started | Gate |

## External constraints

| ID | Constraint | Available | Note |
| --- | --- | --- | --- |
| X1 | Bank statement | T+1 | Received |
| X2 | FX rates | T+2, end of day | At risk |
| X3 | Billing system close | T+3, start of day | Delayed |

## Requested analysis

- Status counts and completion at the snapshot, measured against tasks that were due by T+2.
- Every blocker and the exact action that would clear it.
- Whether the three blockers add up or converge; show the path.
- Any dependency that is scheduled in the same day as its predecessor.
- A remaining close calendar, with assumptions stated.
- No invented approval, sign-off or period-lock claim.
