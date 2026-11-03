# Synthetic bank reconciliation input

> Synthetic fixture. The company, vendors, bank, balances and transaction references are invented for acceptance testing. Not financial advice and not a real reconciliation.

## Request

Reconcile the operating cash account **1002 (USD)** at **2026-09-30**. Currency USD, amounts to two decimals, tolerance 0.00. The organization's thresholds are: individual reconciling item above **USD 10,000** goes to supervisor review; total reconciling items above **USD 100,000** goes to controller review; items older than **60 days** are escalated and older than **90 days** are stale.

## Source A: bank statement

Synthetic statement for account ending 4417, statement period 2026-09-01 to 2026-09-30.

| Line | Date | Description | Amount |
| --- | --- | --- | ---: |
| Ending balance per bank statement | 2026-09-30 | Statement closing balance | 128,450.20 |

The statement does not list the outstanding checks or the deposits in transit below; they are known from the cash book and the bank's clearing data.

## Source B: general ledger extract

Synthetic GL extract for account 1002 at 2026-09-30.

| Item | Date | Description | Amount |
| --- | --- | --- | ---: |
| GL balance | 2026-09-30 | Account 1002 closing balance | 122,000.75 |

## Items known on the bank side

### Deposits in transit

| Ref | Recorded in GL | Amount |
| --- | --- | ---: |
| D-0918 | 2026-09-30 | 3,200.00 |
| D-0929 | 2026-09-30 | 1,300.00 |

### Outstanding checks

| Check | Issued | Payee | Amount |
| --- | --- | --- | ---: |
| 1042 | 2026-07-15 | Synthetic vendor A | 7,420.00 |
| 1051 | 2026-09-24 | Synthetic vendor B | 1,580.00 |
| 1055 | 2026-09-29 | Synthetic vendor C | 860.00 |

No bank errors are known.

## Items known on the GL side

| Ref | Date | Description | Amount | Direction |
| --- | --- | --- | ---: | --- |
| INT-09 | 2026-09-30 | Interest credited by the bank, not recorded in the GL | 120.45 | increases GL cash |
| ACH-4471 | 2026-09-30 | Customer receipt credited by the bank, missing from the GL | 1,054.00 | increases GL cash |
| BF-09 | 2026-09-30 | Bank service fees, not recorded in the GL | 85.00 | decreases GL cash |

No GL errors are known beyond these unrecorded items.

## Constraints

- Use calendar days for aging, measured from the item date to 2026-09-30.
- Do not invent a plug to force the difference to zero.
- Do not state that the reconciliation is approved or signed; the preparer and reviewer roles are human and are left blank.
