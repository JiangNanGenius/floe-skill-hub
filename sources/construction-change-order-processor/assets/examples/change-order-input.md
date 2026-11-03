# Synthetic change order input

> **Synthetic example.** Fictional project, quantities, rates and people. Not market data and not a contractual entitlement determination.

## Project

- Project: Harbourview Office Tower (fictional)
- Original contract: USD 50,000,000.00
- Currency: USD
- Tax: excluded
- Pricing date: 2026-10-31
- Overhead rate: 10% on direct
- Profit rate: 10% on (direct + overhead)
- Contract form: fictitious short-form construction contract
- Approval authority: owner's representative (fictional)

## Change order

- Number: CO-0001
- Title: Additional electrical outlets
- Description: Add 50 electrical outlets on Level 3 east per owner request.
- Type: owner_requested
- Created by: Project Manager (fictional)
- References: RFI-014; Division 26; drawing E-201; Level 3 east
- Status at input: pending_approval (draft and review steps already completed)

## Cost items

| Description | Qty | Unit | Unit cost | Item markup | Category | Source |
| --- | --- | --- | --- | --- | --- | --- |
| Electrical outlets | 50 | EA | 150.00 | 0% | material | Fictional supplier quote |
| Installation labour | 25 | HR | 85.00 | 0% | labor | Fictional labour rate |

## Schedule

- Impact: 5 days
- Affected activities: EL-03

## Routing

- Reviewer: Design Manager (fictional), action reviewed, date 2026-10-20, comment "Scope and quantities checked."
- Approver decision (record supplied for transcription): the Owner's Representative (fictional) approved this synthetic change on 2026-10-22 with the comment "Approved per owner request." This is an existing scenario record, not an instruction for the guide to decide or create an approval.

## What to produce

1. Recompute the direct cost, overhead, profit and total.
2. Confirm the `pending_approval → approved` transition is legal and preserve the prior review record.
3. Produce the approval history and contract summary.
4. Show the change percent against the original contract.
