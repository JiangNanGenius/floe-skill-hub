---
name: close-management
description: Plan and track a month-end close with a task calendar, dependencies, owners, blockers and close metrics. Guide-only; no ERP connection, no posting and no financial advice.
---

# Close Management

## Floe guide adaptation (read first)

- Adapted for Floe from the Apache-2.0 upstream skill recorded in `references/PROVENANCE.md`; the day-by-day checklist, dependency levels, status model and close metrics are retained.
- Bring a workspace file or pasted table with the entity, period, close target, task list, owners, due days, dependencies and current status. No ERP, payroll, banking, HRIS or project-tracker connection is used or implied.
- The output is a workspace document: a sequenced close plan, dependency and gate view, status dashboard, blocker list, projected impact and a review summary. The guide does not post entries, lock a period, approve a close or assign work to a named person without the user's supplied data.
- This is a planning aid, not financial advice or a statement that the close is complete. A qualified finance professional owns the close calendar, the control decisions and the final close.

**Important**: This skill assists with close management workflows but does not provide financial advice. All close activities should be reviewed by qualified financial professionals.

Month-end close checklist, task sequencing and dependencies, status tracking, and common close activities organized by day.

## Input contract

| Input | Required | Notes |
| --- | --- | --- |
| Entity and reporting period | Yes | State the legal entity and period end |
| Reporting basis and currency | Yes | Local GAAP, US GAAP, IFRS or management basis; do not infer it |
| Close target | Yes | e.g. hard close by T+5 business days |
| Task list | Yes | Task ID, name, owner role, due day, dependencies, status |
| Status snapshot time | Yes | Needed to interpret "complete" and "blocked" |
| Dependency rules | Yes | Finish-to-start unless the user states otherwise |
| Materiality and escalation policy | If applicable | Do not invent approval authority |
| Period calendar and holidays | If applicable | Business-day counts change the projection |
| Prior-close metrics | Optional | Baseline for trend comparison |

If the task list is incomplete, produce a plan with explicit gaps and do not invent missing tasks, owners or dates.

## Month-end close checklist

### Pre-close (last 2-3 business days of the month)

- [ ] Send the close calendar and deadline reminders to all contributors.
- [ ] Confirm cut-off procedures with AP, AR, payroll and treasury.
- [ ] Verify all sub-systems are processing normally (ERP, payroll, banking).
- [ ] Complete the preliminary bank reconciliation for all but the last day's activity.
- [ ] Review open purchase orders for potential accrual needs.
- [ ] Confirm the payroll processing schedule aligns with the close timeline.
- [ ] Collect information for any known unusual transactions.

### Close day 1 (T+1: first business day after month-end)

- [ ] Confirm all subledger modules have completed period-end processing.
- [ ] Run AP accruals for goods/services received but not invoiced.
- [ ] Post payroll entries and payroll accrual if the pay period straddles month-end.
- [ ] Record cash receipts and disbursements through month-end.
- [ ] Post intercompany transactions and confirm with counterparties.
- [ ] Complete the bank reconciliation with the final bank statement.
- [ ] Run fixed-asset depreciation.
- [ ] Post prepaid expense amortization.

### Close day 2 (T+2)

- [ ] Complete revenue recognition entries and deferred revenue adjustments.
- [ ] Post all remaining accrual journal entries.
- [ ] Complete the AR subledger reconciliation.
- [ ] Complete the AP subledger reconciliation.
- [ ] Record inventory adjustments (if applicable).
- [ ] Post FX revaluation entries for foreign-currency balances.
- [ ] Begin balance sheet account reconciliations.

### Close day 3 (T+3)

- [ ] Complete all balance sheet reconciliations.
- [ ] Post any adjusting journal entries identified during reconciliation.
- [ ] Complete intercompany reconciliation and elimination entries.
- [ ] Run the preliminary trial balance and income statement.
- [ ] Perform preliminary flux analysis on the income statement.
- [ ] Investigate and resolve material variances.

### Close day 4 (T+4)

- [ ] Post tax provision entries (income tax, sales tax, property tax), subject to the organization's tax process.
- [ ] Complete the equity roll-forward (stock compensation, treasury stock).
- [ ] Finalize journal entries for the soft close.
- [ ] Generate draft financial statements (P&L, balance sheet, cash flow).
- [ ] Perform detailed flux analysis and prepare variance explanations.
- [ ] Management review of financial statements and key metrics.

### Close day 5 (T+5)

- [ ] Post any final adjustments from management review.
- [ ] Finalize financial statements for the hard close.
- [ ] Lock the period in the ERP/GL system (performed by an authorized system owner, outside this guide).
- [ ] Distribute the financial reporting package to the approved recipients.
- [ ] Update forecasts/projections based on actual results.
- [ ] Conduct a close retrospective and identify process improvements.

This calendar is illustrative. Many organizations use a different day count, a softer close, or additional statutory steps; use the user's calendar rather than forcing this one.

## Task sequencing and dependencies

### Dependency map

Organize tasks by what must finish before the next task can start:

```
LEVEL 1 (no dependencies; can start at T+1):
├── Cash receipts/disbursements recording
├── Bank statement retrieval
├── Payroll processing/accrual
├── Fixed-asset depreciation run
├── Prepaid amortization
├── AP accrual preparation
└── Intercompany transaction posting

LEVEL 2 (depends on Level 1):
├── Bank reconciliation (needs cash entries + bank statement)
├── Revenue recognition (needs billing/delivery data finalized)
├── AR subledger reconciliation (needs revenue/cash entries)
├── AP subledger reconciliation (needs AP entries/accruals)
├── FX revaluation (needs foreign-currency entries posted)
└── Remaining accrual JEs (needs source data reviewed)

LEVEL 3 (depends on Level 2):
├── Balance sheet reconciliations (needs all JEs posted)
├── Intercompany reconciliation (needs both sides posted)
├── Adjusting entries from reconciliations
└── Preliminary trial balance

LEVEL 4 (depends on Level 3):
├── Tax provision (needs pre-tax income finalized)
├── Equity roll-forward
├── Consolidation and eliminations
├── Draft financial statements
└── Preliminary flux analysis

LEVEL 5 (depends on Level 4):
├── Management review
├── Final adjustments
├── Hard close / period lock
├── Financial reporting package
└── Forecast updates
```

### Sequencing checks

Before trusting a close plan, check it mechanically:

1. **Every dependency exists** and has an owner.
2. **Finish-to-start:** a successor starts strictly after its predecessor finishes. If the organization uses same-day handoffs, make that explicit and require the predecessor to be marked complete by a named cut-off time; do not assume it.
3. **Gates:** identify the tasks that many other tasks depend on (for example, the trial balance, the balance sheet reconciliation gate and management review). These are the gates to protect.
4. **Converging delays are not additive:** when several blockers feed the same gate, the gate slips by the largest blocker slip, not by the sum. Compute the maximum along each path.
5. **Parallel work:** tasks with no dependency can run concurrently; use that to compress the calendar.
6. **External inputs:** bank statements, FX rates, vendor confirmations and system closes have availability dates. Treat them as constraints, not tasks.
7. **Holidays and time zones:** count business days on the entity's calendar and state the cut-off time zone.

### Critical path

The critical path determines the minimum close duration. A typical path is:

```
Cash/AP/AR entries → Subledger reconciliations → Balance sheet recs →
  Tax provision → Draft financials → Management review → Hard close
```

To shorten the close:

- Automate Level 1 entries (depreciation, prepaid amortization, standard accruals).
- Pre-reconcile accounts during the month (continuous reconciliation).
- Parallel-process independent reconciliations.
- Set clear cut-off times and escalate late submissions.
- Use standardized templates to reduce reconciliation preparation time.

## Status tracking and reporting

### Close status dashboard

Track each close task with the following attributes:

| Task ID | Task | Owner (role) | Due (T+N) | Status | Blocker | Last update |
| --- | --- | --- | --- | --- | --- | --- |
| [ID] | [Task name] | [Role] | [Day] | Not Started / In Progress / Complete / Blocked / At Risk | [What is blocking] | [Date/time] |

### Status definitions

- **Not Started:** the task has not begun, possibly because a dependency is open.
- **In Progress:** actively being worked.
- **Complete:** finished and reviewed under the organization's control; say who reviewed it if the input provides that.
- **Blocked:** cannot proceed because of a dependency, missing data or an issue.
- **At Risk:** in progress but may miss its deadline.

Do not mark a task Complete only because someone said it was done; require the evidence stated in the input.

### Daily close status meeting (recommended)

During the close period, hold a brief (about 15-minute) daily stand-up:

1. Review the status board and flag tasks behind their due day.
2. Surface blockers and the exact decision or data needed to clear them.
3. Reassign or escalate only within the authority the organization has given; the guide cannot grant authority.
4. Update the projection if a gate is at risk, and state the affected downstream tasks.

### Close metrics

| Metric | Definition | Direction |
| --- | --- | --- |
| Close duration | Business days from period end to hard close | Reduce over time |
| Adjusting entries after soft close | Entries posted during management review | Minimize |
| Late tasks | Tasks completed after their deadline | Zero target |
| Reconciliation exceptions | Reconciling items requiring investigation | Reduce over time |
| Restatements / corrections | Errors found after close | Zero target |
| On-time completion at snapshot | Tasks due by the snapshot that are complete | Compare period to period |

State the snapshot time with every metric. A completion percentage without a due-date basis is not a performance measure.

## Common close activities by day

### Typical 5-day close calendar

| Day | Key activities | Typical owner roles |
| --- | --- | --- |
| **T+1** | Cash entries, payroll, AP accruals, depreciation, prepaid amortization, intercompany posting | Staff accountants, payroll |
| **T+2** | Revenue recognition, remaining accruals, subledger reconciliations (AR, AP, FA), FX revaluation | Revenue accountant, AP/AR, treasury |
| **T+3** | Balance sheet reconciliations, intercompany reconciliation, eliminations, preliminary trial balance, preliminary flux | Accounting team, consolidation |
| **T+4** | Tax provision, equity roll-forward, draft financial statements, detailed flux, management review | Tax, controller, FP&A |
| **T+5** | Final adjustments, hard close, period lock, reporting package, forecast update, retrospective | Controller, FP&A, finance leadership |

### Accelerated close (3-day target)

| Day | Key activities |
| --- | --- |
| **T+1** | All JEs posted (automated + manual), all subledger reconciliations, bank reconciliation, intercompany reconciliation, preliminary trial balance |
| **T+2** | All balance sheet reconciliations, tax provision, consolidation, draft financial statements, flux analysis, management review |
| **T+3** | Final adjustments, hard close, reporting package, forecast update |

**Prerequisites for a 3-day close:**

- Automated recurring journal entries (depreciation, amortization, standard accruals)
- Continuous reconciliation during the month, not all at month-end
- Automated intercompany elimination
- Pre-close activities completed before month-end (cut-off, accrual estimates)
- Empowered team with clear ownership and minimal handoffs
- Real-time or near-real-time sub-system integration
- A control framework that still permits the required review and segregation

These are prerequisites, not claims that any particular organization can achieve a 3-day close.

## Close process improvement

### Common bottlenecks and solutions

| Bottleneck | Root cause | Solution |
| --- | --- | --- |
| Late AP accruals | Waiting for department spend confirmation | Continuous accrual estimation; earlier cut-off |
| Manual journal entries | Recurring entries prepared manually each month | Automate standard recurring entries in the ERP |
| Slow reconciliations | Starting from scratch each month | Continuous/rolling reconciliation |
| Intercompany delays | Waiting for counterparty confirmation | Automate matching; stricter cut-off |
| Management review changes | Large adjustments found during review | Improve the preliminary review; catch issues earlier |
| Missing supporting documents | Scrambling for documentation at close | Maintain documentation throughout the month |

### Close retrospective questions

1. What went well that we should continue?
2. What took longer than expected, and why?
3. What blockers occurred, and how can they be prevented?
4. Were there surprises in the results that should have been caught earlier?
5. What can be automated or streamlined next month?

## Floe output contract

A synthetic input is in [`assets/examples/input.md`](assets/examples/input.md), its machine-readable task table is in [`assets/examples/figures.json`](assets/examples/figures.json), and the expected output shape is in [`assets/examples/expected-output.md`](assets/examples/expected-output.md); all are test fixtures, not executed results.

1. State the entity, period, reporting basis, close target, snapshot time and currency.
2. Produce a sequenced task list with owners, due days, dependencies and status; mark missing owners or dates as open and keep any unowned task visible for escalation. Never invent an owner or a completion date.
3. Show the dependency gates and identify the tasks whose delay affects the most downstream work.
4. Report status counts, completion against tasks due by the snapshot, and every blocker with the exact unblocking action.
5. Compute the projected impact of blockers without adding converging delays; show the path used.
6. Flag any finish-to-start sequencing violation instead of silently accepting it.
7. Provide a close calendar for the remaining days, a metrics table and a retrospective checklist.
8. Never state that the period is closed, the ledger is locked, the statements are final or the close is approved. Those are human and system actions outside this guide.

## Scope and limitations

- Works only from supplied task and status data; it does not query an ERP, payroll, bank or project tracker.
- Does not post, reverse or approve journal entries; does not lock a period; does not distribute reports.
- Does not decide materiality, escalation authority or control design for the organization.
- Business-day calculations depend on the supplied calendar, holidays and cut-off times; state assumptions.
- A plan that satisfies dependencies can still fail for capacity, reviewer availability or system downtime; those are not modelled unless supplied.
