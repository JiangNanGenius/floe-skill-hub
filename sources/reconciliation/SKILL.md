---
name: reconciliation
description: Reconcile GL balances to subledgers, bank statements or third-party data; categorize reconciling items, age outstanding balances and prepare a review-ready reconciliation. Guide-only; not financial advice and no ERP connection.
---

# Reconciliation

## Floe guide adaptation (read first)

- Adapted for Floe from the Apache-2.0 upstream skill recorded in `references/PROVENANCE.md`; the reconciliation types, item categories, aging model and escalation discipline are retained.
- Bring a workspace file (CSV, Markdown table, spreadsheet export or pasted tables) with the balances and transaction detail. You supply the period end, currency, comparison source and materiality/tolerance thresholds. No ERP, bank feed, subledger or third-party connection is used or implied.
- The output is a workspace document: a reconciliation table that proves the adjusted balances, categorized reconciling items, an aging table, an investigation list and a review summary. The guide does not post entries, lock a period, approve a reconciliation or sign anything.
- This is a financial workflow aid, not financial advice, an audit opinion or a certification. A qualified finance professional must review the reconciliation, supporting detail and any proposed adjustment before reliance or sign-off.

**Important**: This skill assists with reconciliation workflows but does not provide financial advice. All reconciliations should be reviewed by qualified financial professionals before sign-off.

Methodology and best practices for account reconciliation, including GL-to-subledger, bank reconciliations, and intercompany. Covers reconciling item categorization, aging analysis, and escalation.

## Input contract

Provide, or state that a value is missing:

| Input | Why it is needed |
| --- | --- |
| Account name, identifier and reconciliation type | Selects the method and the expected sources |
| Period end and the "as of" time for each source | Prevents comparing different cut-offs |
| Currency and rounding unit | Keeps every total internally consistent |
| Balance per source A and source B (with source names) | The two sides being reconciled |
| Transaction-level detail for both sides | Explains every difference at item level |
| Tolerance and materiality thresholds | Decides what needs investigation and escalation |
| Organization escalation rules | Determines who reviews what, without inventing authority |
| Prior-period reconciliation and open items | Distinguishes new items from carried-forward items |

If only summary balances are supplied, the guide can still structure the reconciliation but must mark every unexplained amount as unresolved rather than inventing detail.

## Reconciliation types

### GL to subledger reconciliation

Compare the general ledger control account balance to the detailed subledger balance.

**Common accounts:**
- Accounts receivable (GL control vs AR subledger aging)
- Accounts payable (GL control vs AP subledger aging)
- Fixed assets (GL control vs fixed asset register)
- Inventory (GL control vs inventory valuation report)
- Prepaid expenses (GL control vs prepaid amortization schedule)
- Accrued liabilities (GL control vs accrual detail schedules)

**Process:**
1. Pull the GL balance for the control account as of period end.
2. Pull the subledger trial balance or detail report as of the same date.
3. Compare totals; they should match if posting is real-time.
4. Investigate any difference (posting timing, manual entries not reflected, interface errors).

**Common causes of differences:**
- Manual journal entries posted to the control account but not reflected in the subledger
- Subledger transactions not yet interfaced to the GL
- Timing differences in batch posting
- Reclassification entries in the GL without a subledger adjustment
- System interface errors or failed postings

### Bank reconciliation

Compare the GL cash balance to the bank statement balance.

**Process:**
1. Obtain the bank statement balance as of period end.
2. Pull the GL cash account balance as of the same date.
3. Identify outstanding checks (issued and recorded, not yet cleared by the bank).
4. Identify deposits in transit (recorded in the GL, not yet credited by the bank).
5. Identify bank charges, interest or adjustments not yet recorded in the GL.
6. Reconcile both sides to the same adjusted balance.

**Standard format:**

```
Balance per bank statement:         $XX,XXX.XX
Add: Deposits in transit            $X,XXX.XX
Less: Outstanding checks           ($X,XXX.XX)
Add/Less: Bank errors               $X,XXX.XX
Adjusted bank balance:              $XX,XXX.XX

Balance per general ledger:         $XX,XXX.XX
Add: Interest/credits not recorded  $X,XXX.XX
Less: Bank fees not recorded       ($X,XXX.XX)
Add/Less: GL errors                 $X,XXX.XX
Adjusted GL balance:                $XX,XXX.XX

Difference:                         $0.00
```

### Intercompany reconciliation

Reconcile balances between related entities so they net to zero on consolidation.

**Process:**
1. Pull intercompany receivable/payable balances for each entity pair.
2. Compare Entity A's receivable from Entity B to Entity B's payable to Entity A.
3. Identify and resolve differences.
4. Confirm all intercompany transactions are recorded on both sides.
5. Verify elimination entries are correct for consolidation.

**Common causes of differences:**
- Transactions recorded by one entity but not the other (timing)
- Different FX rates used by each entity
- Misclassification (intercompany vs third-party)
- Disputed amounts or unapplied payments
- Different period-end cut-off practices across entities

## Reconciling item categorization

### Category 1: Timing differences

Items that exist because of normal processing timing and will clear without an adjusting entry:

- **Outstanding checks:** issued and recorded in the GL, pending bank clearance
- **Deposits in transit:** deposited and recorded in the GL, pending bank credit
- **In-transit transactions:** posted in one system, pending interface to the other
- **Pending approvals:** transactions awaiting approval to post in one system

**Expected resolution:** these items should clear within the normal processing cycle (typically 1-5 business days). No adjusting entry is normally required; confirm with the owning team if an item does not clear.

### Category 2: Adjustments required

Items that require a journal entry to correct:

- **Unrecorded bank charges:** bank fees, wire charges, returned-item fees
- **Unrecorded interest:** interest income or expense from a bank or lender
- **Recording errors:** wrong amount, wrong account, duplicates
- **Missing entries:** a transaction in one system with no corresponding entry in the other
- **Classification errors:** correctly recorded in the wrong account

**Action:** prepare a proposed adjusting journal entry with the amount, accounts, period and support. The guide drafts the proposal; an authorized person decides whether to post it.

### Category 3: Requires investigation

Items that cannot be immediately explained:

- **Unidentified differences:** variances with no obvious cause
- **Disputed items:** amounts contested between parties
- **Aged outstanding items:** items that have not cleared within expected timeframes
- **Recurring unexplained differences:** the same type of difference appearing each period

**Action:** investigate the root cause, document findings and escalate if unresolved. Do not force the reconciliation to zero with a plug.

## Arithmetic and proof

Every reconciliation must show the calculation, not only the final number:

1. **Adjusted bank balance** = bank statement balance + deposits in transit - outstanding checks ± bank errors.
2. **Adjusted GL balance** = GL balance + unrecorded credits - unrecorded debits ± GL errors.
3. **Difference** = adjusted bank balance - adjusted GL balance.
4. **Tolerance:** unless the organization states a different rounding convention, the difference must be exactly `0.00` in the reconciliation currency. A non-zero difference is an unresolved item, not a rounding plug.
5. **Cross-check:** the sum of all reconciling items on side A must equal the total adjustment from the reported balance to the adjusted balance on side A; the same must hold on side B.
6. **Aging cross-check:** the sum of item amounts in the aging table must equal the total reconciling items in the reconciliation table.

Show amounts with a consistent sign convention. For example, use positive numbers for additions to a balance and parentheses for deductions, and state the convention explicitly.

## Aging analysis for outstanding items

Track the age of reconciling items to identify stale items requiring escalation:

| Age bucket | Status | Action |
| --- | --- | --- |
| 0-30 days | Current | Monitor; within the normal processing cycle |
| 31-60 days | Aging | Investigate why the item has not cleared |
| 61-90 days | Overdue | Escalate to the named reviewer; document the investigation |
| 90+ days | Stale | Escalate to management; evaluate write-off or adjustment with the owner |

### Aging report format

| Item # | Description | Amount | Date originated | Age (days) | Category | Status | Owner |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | [detail] | $X,XXX.XX | [date] | XX | [type] | [status] | [role] |

Age is measured from the item's origination date to the reconciliation period end, using calendar days and a stated day-count convention. If the organization uses business days, say so.

### Trending

Track reconciling item totals over time to identify growing balances:

- Compare total outstanding items to the prior period.
- Flag when total reconciling items exceed the stated materiality threshold.
- Flag when the number of items is growing period over period.
- Identify recurring items that appear every period; they may indicate a process issue.

## Escalation thresholds

Define escalation triggers from the organization's risk tolerance. The values below are illustrative, not defaults:

| Trigger | Example threshold | Escalation |
| --- | --- | --- |
| Individual item amount | > 10,000 | Supervisor review |
| Individual item amount | > 50,000 | Controller review |
| Total reconciling items | > 100,000 | Controller review |
| Item age | > 60 days | Supervisor follow-up |
| Item age | > 90 days | Controller or management review |
| Unreconciled difference | Any amount | Cannot close; resolve or document an approved treatment |
| Growing trend | 3+ consecutive periods | Process-improvement investigation |

State the currency with every threshold. Thresholds are not a substitute for professional judgement.

## Reconciliation best practices

1. **Timeliness:** complete reconciliations within the close calendar deadline (for example, T+3 to T+5 business days after period end, if that is the organization's policy).
2. **Completeness:** reconcile all balance sheet accounts on a defined frequency (monthly for material accounts, quarterly for immaterial ones).
3. **Documentation:** every reconciliation includes preparer, reviewer, date and a clear explanation of all reconciling items. Leave those fields for the humans who perform the roles; do not fill in a name.
4. **Segregation:** the person who reconciles should not be the same person who processes transactions in that account, where the organization's control framework requires separation.
5. **Follow-through:** track open items to resolution; do not carry items forward indefinitely.
6. **Root-cause analysis:** for recurring items, investigate and fix the underlying process issue.
7. **Standardization:** use consistent templates and procedures across accounts.
8. **Retention:** maintain reconciliations and supporting detail under the organization's document-retention policy.

## Floe output contract

A synthetic input is in [`assets/examples/input.md`](assets/examples/input.md), its machine-readable figures are in [`assets/examples/figures.json`](assets/examples/figures.json), and the expected output shape is in [`assets/examples/expected-output.md`](assets/examples/expected-output.md); all are test fixtures, not executed results.

1. State the account, period end, sources, currency, rounding unit and reconciliation type. If any of these is missing, mark it UNKNOWN and do not aggregate.
2. Show the full two-sided reconciliation with the arithmetic visible and the difference line, including the original source rows and the direction/sign of any difference (which side is higher and whether it is a debit or credit difference).
3. Categorize every reconciling item as timing, adjustment required or investigation, with an owner where known.
4. Provide the aging table and identify items crossing each stated escalation threshold.
5. Separate proposed adjustments (amount, accounts, period, support) from items requiring investigation.
6. Provide a review summary listing what the preparer checked, what remains unresolved and what the reviewer must decide.
7. Never state that the account is reconciled, approved, signed off or ready to close unless the supplied evidence proves a zero difference and a named human has performed the review role. The guide cannot grant that approval.

## Scope and limitations

- Works from user-supplied data; it does not fetch bank feeds, ERP balances or subledger reports.
- Does not post journal entries, change account balances, lock periods or file anything.
- Does not replace audit procedures, internal controls testing or a professional accountant's judgement.
- Currency translation, tax and statutory reporting questions are outside this guide unless the user supplies the applicable policy.
- If the data is incomplete, the correct output is a reconciliation with explicit unresolved items and missing-input requests, not a guessed plug.
