# Expected output — reconciliation synthetic fixture

> Expected output shape. The arithmetic below was computed from the fixture, but no model run, connector or production system was used. This is not a signed reconciliation and not financial advice.

## Reconciliation summary

| Field | Value |
| --- | --- |
| Account | Operating cash - USD account 1002 (synthetic) |
| Type | Bank reconciliation |
| Period end | 2026-09-30 |
| Currency / rounding | USD, two decimals |
| Tolerance | 0.00 |
| Bank source | Synthetic statement ending balance 128,450.20 |
| GL source | Synthetic account 1002 balance 122,000.75 |
| Review basis | Supplied workspace data and the stated organization thresholds |

## Reconciliation

| Line | Amount (USD) |
| --- | ---: |
| Balance per bank statement | 128,450.20 |
| Add: deposits in transit (D-0918 3,200.00 + D-0929 1,300.00) | 4,500.00 |
| Less: outstanding checks (1042 7,420.00 + 1051 1,580.00 + 1055 860.00) | (9,860.00) |
| Add/Less: bank errors | 0.00 |
| **Adjusted bank balance** | **123,090.20** |
|  |  |
| Balance per general ledger | 122,000.75 |
| Add: unrecorded credits (INT-09 120.45 + ACH-4471 1,054.00) | 1,174.45 |
| Less: unrecorded debits (BF-09 85.00) | (85.00) |
| Add/Less: GL errors | 0.00 |
| **Adjusted GL balance** | **123,090.20** |
| **Difference** | **0.00** |

**Proof.**

No plug or forced balance was used. The zero difference is the arithmetic result of the two-sided reconciliation; the proposed entries are not posted.

- Bank side: 128,450.20 + 4,500.00 - 9,860.00 = 123,090.20.
- GL side: 122,000.75 + 1,174.45 - 85.00 = 123,090.20.
- Difference: 123,090.20 - 123,090.20 = 0.00.
- Total reconciling items across both sides: 14,360.00 (bank side) + 1,259.45 (GL side) = 15,619.45, which equals the aging total below.

## Reconciling items

| # | Item | Amount (USD) | Category | Treatment | Owner (role) | Status |
| --- | --- | ---: | --- | --- | --- | --- |
| 1 | Check 1042, issued 2026-07-15 | 7,420.00 | Timing | Confirm whether the check is still outstanding, stale or should be stopped/reissued; no entry until confirmed | AP supervisor | Overdue: escalate (77 days) |
| 2 | Check 1051, issued 2026-09-24 | 1,580.00 | Timing | Monitor for clearing | AP | Current |
| 3 | Check 1055, issued 2026-09-29 | 860.00 | Timing | Monitor for clearing | AP | Current |
| 4 | Deposit D-0918, recorded 2026-09-30 | 3,200.00 | Timing | Confirm bank credit on the next statement | AR | Current |
| 5 | Deposit D-0929, recorded 2026-09-30 | 1,300.00 | Timing | Confirm bank credit on the next statement | AR | Current |
| 6 | ACH-4471 customer receipt credited by bank, missing from GL | 1,054.00 | Adjustment required | Proposed entry: Dr cash 1,054.00 / Cr accounts receivable 1,054.00; support is the bank remittance line | GL accountant | Open |
| 7 | BF-09 bank service fees | 85.00 | Adjustment required | Proposed entry: Dr bank fees 85.00 / Cr cash 85.00; support is the bank statement | GL accountant | Open |
| 8 | INT-09 interest credited by bank | 120.45 | Adjustment required | Proposed entry: Dr cash 120.45 / Cr interest income 120.45; support is the bank statement | GL accountant | Open |

The proposed entries total a net **+1,089.45** to GL cash (1,174.45 credits - 85.00 debits). Applying them would bring the unadjusted GL balance of 122,000.75 to 123,090.20.

## Aging

| # | Item | Amount (USD) | Date originated | Age (calendar days) | Bucket | Status |
| --- | --- | ---: | --- | ---: | --- | --- |
| 1 | Check 1042 | 7,420.00 | 2026-07-15 | 77 | 61-90 | Overdue: escalate |
| 2 | Check 1051 | 1,580.00 | 2026-09-24 | 6 | 0-30 | Current |
| 3 | Check 1055 | 860.00 | 2026-09-29 | 1 | 0-30 | Current |
| 4 | Deposit D-0918 | 3,200.00 | 2026-09-30 | 0 | 0-30 | Current |
| 5 | Deposit D-0929 | 1,300.00 | 2026-09-30 | 0 | 0-30 | Current |
| 6 | ACH-4471 | 1,054.00 | 2026-09-30 | 0 | 0-30 | Current |
| 7 | BF-09 | 85.00 | 2026-09-30 | 0 | 0-30 | Current |
| 8 | INT-09 | 120.45 | 2026-09-30 | 0 | 0-30 | Current |
| **Total** |  | **15,619.45** |  |  |  |  |

Aging total ties to the combined reconciling items in the reconciliation above. Check 1042 is the only item crossing the stated 60-day escalation threshold; no item crosses the 90-day stale threshold and no individual item exceeds USD 10,000, so the age rule is the only escalated trigger.

## Investigation list

1. **Check 1042 (USD 7,420.00, 77 days).** Ask AP and the payee whether the check was received, lost or is intentionally still outstanding. If it is stale or lost, follow the organization's stop-payment/reissue control; do not simply remove it from the reconciliation.
2. **ACH-4471 (USD 1,054.00).** Obtain the bank remittance advice and identify the customer and invoice; record the receipt and clear the corresponding receivable.
3. **Deposits D-0918 and D-0929.** Confirm they appear on the next bank statement; if not, investigate before the next close.
4. **Completeness.** Confirm the statement covers 2026-09-01 to 2026-09-30 and that no bank account or sub-account is missing from the extract.
5. **Unrecorded items.** Confirm there are no other bank lines (fees, interest, returned items) that were omitted from the supplied extract.

## Review summary

| Field | Status |
| --- | --- |
| Difference | 0.00 on the reconciliation as presented; the proposed entries are not posted |
| Timing items | 5 items, USD 14,360.00; one item (check 1042) requires escalation |
| Proposed adjustments | 3 items, net +USD 1,089.45 to GL cash; not posted |
| Unresolved items | Check 1042 status; ACH-4471 customer/invoice identification; deposit clearing |
| Prepared by | [human preparer - blank] |
| Reviewed by | [human reviewer - blank] |
| Sign-off | Not provided. This guide does not approve, sign or close the reconciliation. |

## What a human reviewer must decide

1. Whether check 1042 remains a valid liability or should be handled under the stale-check control.
2. Whether the three proposed entries are complete and correctly classified.
3. Whether the evidence supports a zero difference at the stated tolerance.
4. Whether the account can be presented for sign-off under the organization's control framework.

## Adversarial check (separate from the bank reconciliation above)

Control account GL **1,000.00** vs subledger detail **970.00** at the same period end. Difference **30.00**; direction: the GL control is higher, so this is a debit-side difference. Source rows supplied:

| Source | Ref | Amount |
| --- | --- | ---: |
| GL control account | GL-1000 | 1,000.00 |
| Subledger detail | S1 | 600.00 |
| Subledger detail | S2 | 250.00 |
| Subledger detail | S3 | 120.00 |
| **Difference** |  | **30.00** |

The 30.00 is not allocated to a plug, suspense or "other" line. It remains an unresolved difference until the missing source row, interface timing or correcting entry is identified. This adversarial case is not signed, approved or included in the zero-difference bank reconciliation above.

## Limitations

- Synthetic data only; no bank, ERP or subledger was queried.
- No tax, statutory or local-GAAP conclusion is made.
- The reconciliation is prepared for human review and is not an approval or an audit procedure.
