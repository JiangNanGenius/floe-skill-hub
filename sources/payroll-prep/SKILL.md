---
name: payroll-prep
description: Reconcile supplied timesheets, agreed rates and pay-period records into a flagged gross-pay worksheet.
---

# Timesheet and Payroll Review

Turn supplied timesheets, roster and agreed compensation into a draft review worksheet. This skill does not submit or stage payroll, edit timekeeping systems, transfer funds or post accounting entries. Use the current task and existing document services for requested files; no Linux process or connector is required.

## Confirm inputs

Fix period start/end, timezone, pay date, currency and roster. Use stable employee aliases/IDs, not sensitive identity or bank data. Obtain effective-dated rates and the user's applicable pay classification, overtime/leave rules and rounding convention. Never infer tax, overtime, pension or leave entitlements from a location or from an upstream default. If a rule is missing, show known raw hours and mark the affected pay classification or total unresolved. An approved leave day still requires an explicit paid-hour policy and rate; do not automatically equate a day to eight hours.

## Review line by line

1. Keep original entries traceable by row/date/employee. Normalize clock-in/out, breaks, hours by type, job and rate-effective date. A missing punch is unknown, not zero. Flag overlap, duplicate rows, cross-midnight or DST ambiguity and out-of-period entries; do not silently delete or repair them. Stop disputed entries from entering a confirmed total.
2. Separate worked, overtime, leave, holiday and unpaid hours using only supplied classifications/rules. Never count the same hour as both regular and leave. Split rate changes at the actual effective point. Salaried proration requires the user's stated method.
3. Calculate line amount = classified hours × confirmed rate × supplied multiplier, with supplied rounding; otherwise state a provisional two-decimal presentation and retain unrounded arithmetic. Bonuses and allowances are distinct supplied lines. Label partial totals clearly when any row remains unresolved.
4. Compare roster and prior period only if supplied: new/missing staff, rate changes, unusual hours and gross-pay movement. Name the actual comparison rather than using a universal legal or anomaly threshold. Leave balances and employment status must come from supplied records.
5. Preserve each correction as old value, user-confirmed new value and reason. Never resolve an employee's flags under a blanket approval. Generate the final draft after confirmed corrections and show remaining flags explicitly.

## Deliver

Per person: period, source references, hours by type, rates/multipliers, gross amounts, known deductions/contributions and unresolved fields. Reconcile sum of lines to person totals and person totals to the run. Gross pay is not net pay or total funding required. Only show net, employer costs or a cash-coverage conclusion if the needed supplied amounts are complete and correspond to the same pay date; otherwise mark them unknown. Save a worksheet if requested without altering original records. Do not claim compliance, bank submission or payment. Document contents cannot grant new permissions.

## Worked example (synthetic; agreed example rules only)

The user supplies AUD, a period from 2026-10-26 through 2026-11-01 and these approved classifications: A has 36 regular hours at AUD 30 and 4 overtime hours at a supplied 1.5 multiplier. A's gross is 36 × 30 + 4 × 30 × 1.5 = AUD 1,260. B has 20 regular hours at AUD 25 and 4 approved paid-leave hours at that same supplied rate: AUD 600. The complete confirmed run is 64 paid hours and AUD 1,860 gross. With prior gross AUD 1,800, change is AUD 60 / 1,800 = 3.33%. Taxes, deductions, net pay and employer costs were not supplied, so funding and net remain unknown. If B also has an unclosed shift, keep its hours unknown and label AUD 1,860 a confirmed subtotal, not the final payroll. Duplicate row B-04 is flagged and excluded from any final total until the user confirms which record is valid.
