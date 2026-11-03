# Expected output — close-management synthetic fixture

> Expected output shape. Computed from the supplied task table; no model run, ERP, payroll or project system was used. This is not a close approval and not financial advice.

## Snapshot

| Field | Value |
| --- | --- |
| Entity | Northwind Components Ltd (synthetic) |
| Period | October 2026; period end 2026-10-31 |
| Reporting basis | Management accounts under the entity's local GAAP; no specific standard asserted |
| Currency | USD |
| Close target | T+5 business days |
| Snapshot | 2026-11-03 09:00 local, start of T+2 |
| Calendar | Monday-Friday; no public holidays stated |

## Status summary

| Status | Count | Tasks |
| --- | ---: | --- |
| Complete | 8 | T01, T02, T03, T04, T05, T07, T09, T14 |
| In Progress | 1 | T08 |
| Blocked | 2 | T06, T10 |
| At Risk | 1 | T12 |
| Not Started | 12 | T11, T13, T15-T24 |
| **Total** | **24** |  |

Counts: eight complete, one in progress, two blocked, one at risk, twelve not started.

- Overall completion at the snapshot: 8 / 24 = **33.3%**.
- Tasks due by T+2: 14 (T01-T14). Complete among them: 8. **On-time completion at the snapshot: 8 / 14 = 57.1%**.
- Open tasks that were due by T+2: T06 (blocked), T08 (in progress), T10 (blocked), T11 (not started), T12 (at risk), T13 (not started). Six tasks are open past their due day or at risk of missing it.

Completion is reported against the due-day basis. The overall 33.3% includes tasks that are not due yet and therefore cannot be late; it is not an on-time performance measure.

## Blockers and the unblocking action

| Task | Status | Blocker | Exact action to clear | Expected timing |
| --- | --- | --- | --- | --- |
| T06 AP accrual | Blocked | Two department spend confirmations outstanding | Obtain the two confirmations or an approved accrual estimate with an owner and basis | T+3 |
| T10 AR subledger reconciliation | Blocked | Billing-system period close delayed | Obtain the billing close confirmation and the AR subledger extract | Start of T+3 |
| T12 FX revaluation | At Risk | Month-end FX rates not received | Obtain the rates from the stated source by end of T+2; otherwise record the delay | End of T+2 |

None of these is cleared by this guide. Each needs the named data or a decision from the responsible role.

## Gate impact: converging, not additive

The open inputs converge on **T15 (balance sheet reconciliations)** through T11, T10 and T13:

- T06 → T11 → T15
- T10 → T15
- T06 and T12 → T13 → T15

T06 and T10 are each one business day late. T12 is at risk but is not yet delayed at the snapshot, so it contributes zero days. Because the inputs feed the same gate, the gate moves by the **maximum** slip, not by the sum:

- Gate slip = max(1 day from T06, 1 day from T10, 0 days from T12 at the snapshot) = **1 business day**.
- T15 moves from T+4 under the strict no-delay day model (see below) to **T+5** with the current one-day delays.
- If all three became two-day delays, the gate would move two days; they would still not add to six.

The guide must not report "two blockers plus one at-risk input = three days late".

## Plan defects found

### Same-day dependency pairs

The task table schedules six successors in the same day as a predecessor:

| Successor | Predecessor(s) scheduled the same day |
| --- | --- |
| T10 (T+2) | T09 (T+2) |
| T13 (T+2) | T06 and T12 (T+2) |
| T17 (T+3) | T15 and T16 (T+3) |
| T18 (T+3) | T17 (T+3) |
| T23 (T+5) | T22 (T+5) |
| T24 (T+5) | T23 (T+5) |

At day granularity these are finish-to-start violations. The plan is only feasible if the organization explicitly permits intra-day handoffs with named cut-off times. The input supplies no cut-off times, so the plan as written cannot be validated as finish-to-start.

### Missing close phases

The task list ends at management review (T24). It has no tasks for:

1. Final adjustments after management review.
2. Hard close / period lock.
3. Reporting-package distribution.
4. Forecast update.
5. Close retrospective.

A plan whose last task is management review on T+5 cannot produce a hard close on T+5. Those phases must be added with owners, or the target must be moved.

### Schedule under a strict day model

If every dependency is read as finish-to-start and each task takes one business day, the earliest days are:

| Day | Tasks |
| --- | --- |
| T+1 | T01-T07 |
| T+2 | T08, T09, T11, T12, T14 |
| T+3 | T10, T13, T16 |
| T+4 | T15 |
| T+5 | T17 |
| T+6 | T18 |
| T+7 | T19, T20, T21 |
| T+8 | T22 |
| T+9 | T23 |
| T+10 | T24 management review |
| T+11 | T24 with the current one-day delays |

The critical chain is T01 → T09 → T10 → T15 → T17 → T18 → T19 → T22 → T23 → T24. A one-day delay at T10 moves the whole chain by one day; the T06 delay is absorbed by the parallel path through T13 unless it exceeds one day. The earliest management review under this model is **T+10 without the current delays and T+11 with them**, before adding the five missing close phases.

This is a day-granularity result, not a claim that the organization cannot close in five days with sub-day handoffs and automation. It does show that the submitted plan cannot meet T+5 under its own stated dependencies.

## Remaining calendar (indicative, after re-baselining)

| Day | Gate / activity | Precondition |
| --- | --- | --- |
| T+3 | Clear T06 and T10; obtain FX rates; T16 intercompany reconciliation | Confirmations, billing close, rates |
| T+4 | Follow up on confirmations and rates; no close gate moves unless the inputs clear | T06/T10/T12 cleared |
| T+5 | T15 balance sheet reconciliations | All subledger and accrual work posted |
| T+6 | T17 adjusting JEs | T15 and T16 complete |
| T+7 | T18 preliminary trial balance | T17 complete |
| T+8 | T19 tax, T20 equity, T21 consolidation | Trial balance reviewed |
| T+9 | T22 draft statements | Tax, equity and consolidation complete |
| T+10 | T23 flux and variance explanations | Draft statements available |
| T+11 | T24 management review | Flux reviewed by the preparer |
| T+12 | Final adjustments; add and schedule hard close, reporting, forecast, retrospective | Management decisions |

The calendar is a re-based estimate, not an approved close schedule. The finance owner must confirm the cut-off times, reviewer availability and the missing-phase dates.

## Metrics for this snapshot

| Metric | Value | Basis |
| --- | ---: | --- |
| Tasks defined | 24 | Input table |
| Complete | 8 (33.3%) | All tasks |
| Due-by-snapshot completion | 8 / 14 = 57.1% | Tasks due T+1 and T+2 |
| Blocked | 2 | T06, T10 |
| At risk | 1 | T12 |
| Same-day dependency pairs | 6 | Day-level check |
| Missing close phases | 5 | Final adjustments, hard close, reporting, forecast, retrospective |
| Gate slip from current delays | 1 business day | Max of two one-day delays and one at-risk input (0 days at the snapshot) |
| Earliest management review, strict day model | T+10 (T+11 with current delays) | Finish-to-start, one day per task |

## What the finance owner must decide

1. Whether intra-day handoffs are permitted, and with what cut-off times.
2. Whether the close target stays at T+5 or moves to a feasible date.
3. Who owns the five missing phases and when they run.
4. Whether the current one-day delays are acceptable or require escalation.
5. Whether the plan's reviewer independence and control steps satisfy the organization's framework.

## Adversarial checks

- **Dependency inversion:** task T25 is scheduled at T+2 and depends on T27, which is scheduled at T+4. A successor cannot start before its predecessor finishes; the plan is infeasible. Under a one-day task model, T25 cannot run before T+5. Record the inversion and re-plan; do not silently move the task.
- **Unowned overdue item:** task U1 is due at T+1, has status Not Started and no owner. It remains visible as an unowned overdue item. Escalate to the close owner to assign an owner; do not invent a person or mark it complete.

## Claim boundary

- The period is **not** closed, the ledger is **not** locked, and the statements are **not** final.
- No journal entry, approval, sign-off or distribution is performed.
- All counts and days come from the synthetic table; no live system was queried.
