---
name: financial-statements
description: Prepare income statement, balance sheet and cash-flow views from supplied trial-balance data, with period comparisons, variance analysis, presentation notes and proof checks. Guide-only; no ERP connection, no filing and not financial advice.
---

# Financial Statements

## Floe guide adaptation (read first)

- Adapted for Floe from the Apache-2.0 upstream skill recorded in `references/PROVENANCE.md`; the statement layouts, variance method, GAAP presentation notes and period-end adjustment checklist are retained.
- Bring a workspace file or pasted tables: trial balance or account-level actuals, prior-period comparatives, budget/forecast if required, entity and period, reporting basis, currency and units. No ERP or data-warehouse connection is used or implied.
- The output is a workspace document: a three-statement draft, period comparisons, variance commentary, key metrics, presentation notes, proof checks and open questions. The guide does not file, certify, distribute or approve anything.
- This is a preparation aid, not financial advice, an audit opinion or a filing. A qualified finance professional must review every statement, note and variance explanation before use in reporting or filings.

**Important**: This guide assists with financial statement workflows but does not provide financial advice. All statements should be reviewed by qualified financial professionals before use in reporting or filings.

Generate financial statements with period-over-period comparison and variance analysis. The workflow below walks through income statement generation; balance sheet and cash flow statement reference formats, GAAP presentation requirements (ASC 220/210/230), and common period-end adjustments are included as supporting reference material.

## Input contract

| Input | Required | Notes |
| --- | --- | --- |
| Entity, period and period type | Yes | Monthly, quarterly, annual or year-to-date |
| Reporting basis | Yes | US GAAP, IFRS, local GAAP or management basis; do not infer |
| Currency and units | Yes | e.g. USD thousands; keep one unit throughout |
| Trial balance or account-level actuals | Yes | Account code, name, current amount, prior amount |
| Mapping to statement lines | Yes | Or supply a mapping rule; do not invent one silently |
| Comparison data | Yes | Prior period, prior year and/or budget |
| Materiality thresholds | Yes | Dollar and percentage basis |
| Known adjustments and reclassifications | If applicable | With support and period |
| Contingent or unusual items | If applicable | Flag, do not estimate |
| Prior-period statements | Optional | For consistency and restatement checks |

If the mapping is missing, state the proposed mapping as an assumption and list every account whose classification is uncertain. Never force the balance sheet to balance with a plug; an unbalanced draft is a finding.

## Workflow

### 1. Establish the reported basis

Before calculating anything, record:

- Entity and consolidation level.
- Period and period type.
- Reporting basis (US GAAP, IFRS, local GAAP or management accounts). The presentation rules differ; do not mix frameworks.
- Currency, units and rounding.
- Whether the statements are consolidated, stand-alone or a segment view.
- Whether the figures are audited, reviewed, management-prepared or draft.

If the user does not state the basis, ask. A statement prepared under an unstated basis is not comparable to a filed statement.

### 2. Gather financial data

Ask for, or locate in the workspace:

- Trial balance or income statement data for the period.
- Comparison period data (prior period, prior year, budget/forecast).
- Account hierarchy and groupings used for presentation.
- Any known adjustments or reclassifications.

If data is supplied only as an income statement, the guide can prepare the income statement and variance analysis but must not invent the balance sheet or cash flow. Mark missing statements as not prepared.

### 3. Generate the income statement

Present a multi-column format:

```
INCOME STATEMENT
Period: [Period description]
(in thousands, unless otherwise noted)

                              Current    Prior      Variance   Variance   Budget    Budget
                              Period     Period     ($)        (%)        Amount    Var ($)
                              --------   --------   --------   --------   --------  --------
REVENUE
  Product revenue             $XX,XXX    $XX,XXX    $X,XXX     X.X%       $XX,XXX   $X,XXX
  Service revenue             $XX,XXX    $XX,XXX    $X,XXX     X.X%       $XX,XXX   $X,XXX
  Other revenue               $XX,XXX    $XX,XXX    $X,XXX     X.X%       $XX,XXX   $X,XXX
                              --------   --------   --------              --------  --------
TOTAL REVENUE                 $XX,XXX    $XX,XXX    $X,XXX     X.X%       $XX,XXX   $X,XXX

COST OF REVENUE
  [Cost items]                $XX,XXX    $XX,XXX    $X,XXX     X.X%       $XX,XXX   $X,XXX
                              --------   --------   --------              --------  --------
GROSS PROFIT                  $XX,XXX    $XX,XXX    $X,XXX     X.X%       $XX,XXX   $X,XXX
  Gross Margin                XX.X%      XX.X%

OPERATING EXPENSES
  Research & development      $XX,XXX    $XX,XXX    $X,XXX     X.X%       $XX,XXX   $X,XXX
  Sales & marketing           $XX,XXX    $XX,XXX    $X,XXX     X.X%       $XX,XXX   $X,XXX
  General & administrative    $XX,XXX    $XX,XXX    $X,XXX     X.X%       $XX,XXX   $X,XXX
                              --------   --------   --------              --------  --------
TOTAL OPERATING EXPENSES      $XX,XXX    $XX,XXX    $X,XXX     X.X%       $XX,XXX   $X,XXX

OPERATING INCOME (LOSS)       $XX,XXX    $XX,XXX    $X,XXX     X.X%       $XX,XXX   $X,XXX
  Operating Margin            XX.X%      XX.X%

OTHER INCOME (EXPENSE)
  Interest income             $XX,XXX    $XX,XXX    $X,XXX     X.X%
  Interest expense           ($XX,XXX)  ($XX,XXX)   $X,XXX     X.X%
  Other, net                  $XX,XXX    $XX,XXX    $X,XXX     X.X%
                              --------   --------   --------
TOTAL OTHER INCOME (EXPENSE)  $XX,XXX    $XX,XXX    $X,XXX     X.X%

INCOME BEFORE TAXES           $XX,XXX    $XX,XXX    $X,XXX     X.X%
  Income tax expense          $XX,XXX    $XX,XXX    $X,XXX     X.X%
                              --------   --------   --------
NET INCOME (LOSS)             $XX,XXX    $XX,XXX    $X,XXX     X.X%       $XX,XXX   $X,XXX
  Net Margin                  XX.X%      XX.X%
```

### 4. Variance analysis

For each line item, calculate and flag material variances.

#### Variance calculation

- **Dollar variance:** current period - comparison period (or current - budget).
- **Percentage variance:** (current - comparison) / |comparison| × 100. If the comparison is zero, report "n/a (comparison is zero)" and give the dollar amount; never divide by zero or report an infinite percentage.
- **If the comparison is negative** (for example, a prior-period loss), the sign of a percentage change can mislead. State the formula and show the dollar change; consider a "change in margin" measure instead of a percentage on a negative base.
- **Basis-point change:** for margins and ratios, express the change in basis points (1 bp = 0.01 percentage point). Do not mix percentage change and percentage-point change.

#### Materiality thresholds

Define what constitutes a material variance requiring investigation. Common approaches:

- **Fixed dollar threshold:** variances exceeding a set amount (for example, USD 50,000 or 100,000).
- **Percentage threshold:** variances exceeding a set percentage (for example, 10% or 15%).
- **Combined:** either the dollar OR percentage threshold is exceeded.
- **Scaled:** different thresholds for different line items based on size and volatility.

*Example thresholds (adjust for the organization):*

| Line item size | Dollar threshold | Percentage threshold |
| --- | ---: | ---: |
| > 10M | 500K | 5% |
| 1M - 10M | 100K | 10% |
| < 1M | 50K | 15% |

State the currency and whether the test is "either" or "both". A threshold is not a substitute for judgement; a small balance can still be material for qualitative reasons.

#### Variance decomposition

Break total variance into component drivers:

- **Volume/quantity effect:** change in volume at prior-period rates.
- **Rate/price effect:** change in rate/price at current-period volume.
- **Mix effect:** shift in composition between items with different rates or margins.
- **New/discontinued items:** items present in one period but not the other.
- **One-time/non-recurring items:** items not expected to repeat.
- **Timing effect:** items shifting between periods (not a true change in run rate).
- **Currency effect:** impact of FX rate changes on translated results.

Show the arithmetic. Do not present a driver as the explanation unless the decomposition ties to the reported variance.

#### Investigation and narrative

For each material variance:

1. Quantify the variance in dollars and percent.
2. Identify whether it is favourable or unfavourable for the relevant measure.
3. Decompose it into drivers using the categories above.
4. Provide a narrative explanation of the business reason, or state that the reason is unknown.
5. Assess whether the variance is temporary or a trend change.
6. Note any action required (further investigation, forecast update, process change).

### 5. Key metrics summary

```
KEY METRICS
                              Current    Prior      Change
Revenue growth (%)                                  X.X%
Gross margin (%)              XX.X%      XX.X%      X.X pp
Operating margin (%)          XX.X%      XX.X%      X.X pp
Net margin (%)                XX.X%      XX.X%      X.X pp
OpEx as % of revenue          XX.X%      XX.X%      X.X pp
Effective tax rate (%)        XX.X%      XX.X%      X.X pp
```

Define each denominator. For example, "operating margin" is operating income divided by total revenue for the same period; do not mix a quarterly numerator with an annual denominator.

### 6. Material variance summary

| Line item | Variance ($) | Variance (%) | Direction | Preliminary driver | Action |
| --- | ---: | ---: | --- | --- | --- |
| [Item] | X,XXX | X.X% | Favourable / Unfavourable | [If known] | Investigate |

### 7. Output

Provide:

1. A formatted income statement with comparisons and the calculation basis.
2. A key-metrics summary with definitions.
3. A material variance listing with investigation flags.
4. Suggested follow-up questions for unexplained variances.
5. A statement of which statements were prepared and which could not be prepared from the supplied data.

Do not offer a `/flux` command; this guide has no command runtime. Do not imply that a deeper analysis was already performed.

## Balance sheet and cash flow

### Balance sheet (ASC 210 / IAS 1)

- Distinguish current and non-current assets and liabilities.
- Current: expected to be realized, consumed or settled within 12 months (or the operating cycle if longer).
- Present assets in order of liquidity (most liquid first) if that is the organization's convention.
- Accounts receivable shown net of allowance for credit losses (ASC 326 under US GAAP; expected credit losses under IFRS 9).
- Property and equipment shown net of accumulated depreciation.
- Goodwill is not amortized under US GAAP; it is tested for impairment. Under IFRS, goodwill is also not amortized but is tested for impairment. Do not apply one framework's rule while labelling the statement under the other.
- Leases: recognize right-of-use assets and lease liabilities under ASC 842 or IFRS 16, subject to the applicable policy and practical expedients.

**Proof:**

- Total assets = total liabilities + total equity.
- Current assets + non-current assets = total assets.
- The retained-earnings roll-forward must tie opening retained earnings + net income - dividends ± other equity movements to closing retained earnings.
- If the balance sheet does not balance, report the exact difference and the accounts that may explain it; do not insert a suspense or "other" line to force it.

### Cash flow statement (ASC 230 / IAS 7)

- The indirect method is most common (start with net income, adjust for non-cash items).
- The direct method is permitted but requires a supplemental indirect reconciliation.
- Interest paid and income taxes paid must be disclosed (on the face or in the notes) where the framework requires it.
- Non-cash investing and financing activities are disclosed separately.
- Cash equivalents: short-term, highly liquid investments with original maturities of three months or less, subject to the organization's policy.

**Proof:**

- Net cash from operating + investing + financing activities ± FX effect = net change in cash.
- Opening cash + net change = closing cash.
- Closing cash must equal the cash and cash equivalents line on the balance sheet for the same date and scope.
- If the cash flow does not articulate, report the difference and the likely classification issue; do not plug it.

### Balance sheet reference format

```
ASSETS
Current Assets
  Cash and cash equivalents
  Short-term investments
  Accounts receivable, net
  Inventory
  Prepaid expenses and other current assets
Total Current Assets

Non-Current Assets
  Property and equipment, net
  Operating lease right-of-use assets
  Goodwill
  Intangible assets, net
  Long-term investments
  Other non-current assets
Total Non-Current Assets

TOTAL ASSETS

LIABILITIES AND STOCKHOLDERS' EQUITY
Current Liabilities
  Accounts payable
  Accrued liabilities
  Deferred revenue, current portion
  Current portion of long-term debt
  Operating lease liabilities, current portion
  Other current liabilities
Total Current Liabilities

Non-Current Liabilities
  Long-term debt
  Deferred revenue, non-current
  Operating lease liabilities, non-current
  Other non-current liabilities
Total Non-Current Liabilities

Total Liabilities

Stockholders' Equity
  Common stock
  Additional paid-in capital
  Retained earnings (accumulated deficit)
  Accumulated other comprehensive income (loss)
  Treasury stock
Total Stockholders' Equity

TOTAL LIABILITIES AND STOCKHOLDERS' EQUITY
```

### Cash flow statement reference format (indirect method)

```
CASH FLOWS FROM OPERATING ACTIVITIES
Net income (loss)
Adjustments to reconcile net income to net cash from operations:
  Depreciation and amortization
  Stock-based compensation
  Amortization of debt issuance costs
  Deferred income taxes
  Loss (gain) on disposal of assets
  Impairment charges
  Other non-cash items
Changes in operating assets and liabilities:
  Accounts receivable
  Inventory
  Prepaid expenses and other assets
  Accounts payable
  Accrued liabilities
  Deferred revenue
  Other liabilities
Net Cash Provided by (Used in) Operating Activities

CASH FLOWS FROM INVESTING ACTIVITIES
  Purchases of property and equipment
  Purchases of investments
  Proceeds from sale/maturity of investments
  Acquisitions, net of cash acquired
  Other investing activities
Net Cash Provided by (Used in) Investing Activities

CASH FLOWS FROM FINANCING ACTIVITIES
  Proceeds from issuance of debt
  Repayment of debt
  Proceeds from issuance of common stock
  Repurchases of common stock
  Dividends paid
  Payment of debt issuance costs
  Other financing activities
Net Cash Provided by (Used in) Financing Activities

Effect of exchange rate changes on cash

Net Increase (Decrease) in Cash and Cash Equivalents
Cash and cash equivalents, beginning of period
Cash and cash equivalents, end of period
```

## GAAP presentation requirements

### Income statement (ASC 220 / IAS 1)

- Present all items of income and expense recognized in a period.
- Classify expenses either by nature (materials, labour, depreciation) or by function (COGS, R&D, S&M, G&A). Function is more common for US companies.
- If classified by function, disclose depreciation, amortization and employee-benefit costs by nature in the notes where the framework requires it.
- Present operating and non-operating items separately.
- Show income tax expense as a separate line.
- Extraordinary items are prohibited under both US GAAP and IFRS.
- Discontinued operations are presented separately, net of tax.
- Revenue disaggregation (ASC 606 / IFRS 15) should depict how the nature, amount, timing and uncertainty of revenue are affected by economic factors.
- Stock-based compensation is classified within functional expense categories with the total disclosed in the notes where required.
- Restructuring charges are presented separately if material, or within operating expenses with note disclosure.
- Non-GAAP measures, if shown, must be clearly labelled and reconciled to the most directly comparable GAAP measure.

### Jurisdiction and framework assumptions

- **US GAAP:** ASC 220 (income statement), ASC 210 (balance sheet), ASC 230 (cash flow), ASC 326 (credit losses), ASC 350 (goodwill), ASC 842 (leases), ASC 606 (revenue).
- **IFRS:** IAS 1 (presentation), IAS 7 (cash flow), IFRS 9 (financial instruments and expected credit losses), IAS 36 (impairment), IFRS 16 (leases), IFRS 15 (revenue).
- **Local GAAP:** presentation, tax and statutory formats may differ; do not map a local filing format onto US GAAP without saying so.
- **Tax:** the tax provision depends on the entity's jurisdiction, tax elections and current law. This guide does not compute a tax liability; it checks that the supplied tax line and effective rate are internally consistent and flags open questions.
- **Currency translation:** state the functional currency, presentation currency and the rates used. Do not silently translate.
- **Filing:** nothing here is a filing, a securities disclosure or a statutory report. A qualified accountant and, where required, an auditor must review the output.

## Common adjustments and reclassifications

### Period-end adjustments

1. **Accruals:** record expenses incurred but not yet paid (AP accruals, payroll accruals, interest accruals).
2. **Deferrals:** adjust prepaid expenses, deferred revenue and deferred costs for the period.
3. **Depreciation and amortization:** book periodic depreciation/amortization from fixed-asset and intangible schedules.
4. **Bad-debt provision:** adjust the allowance for credit losses based on aging and historical loss rates; under IFRS use the expected-credit-loss model required by IFRS 9.
5. **Inventory adjustments:** record write-downs for obsolete, slow-moving or impaired inventory.
6. **FX revaluation:** revalue foreign-currency monetary assets and liabilities at period-end rates.
7. **Tax provision:** record current and deferred income tax expense under the applicable framework.
8. **Fair-value adjustments:** mark-to-market investments, derivatives and other fair-value items under the applicable policy.

### Reclassifications

1. **Current/non-current reclassification:** reclassify long-term debt maturing within 12 months to current.
2. **Contra-account netting:** net allowances against gross receivables; accumulated depreciation against gross assets.
3. **Intercompany elimination:** eliminate intercompany balances and transactions in consolidation.
4. **Discontinued operations:** reclassify results of discontinued operations to a separate line item.
5. **Equity-method adjustments:** record the share of investee income/loss for equity-method investments.
6. **Segment reclassifications:** ensure transactions are classified by operating segment consistently.

## Floe output contract

A synthetic input is in [`assets/examples/input.md`](assets/examples/input.md), its machine-readable figures are in [`assets/examples/figures.json`](assets/examples/figures.json), and the expected output shape is in [`assets/examples/expected-output.md`](assets/examples/expected-output.md); all are test fixtures, not executed results.

1. State the entity, period, basis, currency, units and whether the figures are audited, reviewed, management-prepared or draft. If the period, basis, currency or units are missing, mark them UNKNOWN and do not aggregate or compare.
2. Present each statement that the supplied data supports; mark unsupported statements as not prepared instead of inventing them.
3. Show every subtotal and margin calculation; keep one unit and one rounding convention.
4. Show the balance-sheet proof (assets = liabilities + equity) and the cash-flow articulation (operating + investing + financing ± FX = net change; opening + net change = closing = balance-sheet cash). Never present net income as operating cash flow or vice versa; show the reconciliation between them.
5. Calculate variances with the stated formula and thresholds; handle zero and negative comparatives explicitly.
6. Separate known drivers from hypotheses; never present an unverified cause as fact.
7. List the adjustments and reclassifications that were applied, with support; list those that remain open.
8. End with the questions a qualified accountant must resolve and the decisions that belong to management.
9. Never state that the statements are final, filed, approved, audited or free of error. The guide prepares a draft for human review.

## Scope and limitations

- Works only from supplied data; it does not query an ERP, warehouse, bank or tax system.
- Does not post entries, lock a period, file a return, distribute statements or provide an audit opinion.
- Does not compute jurisdiction-specific tax, statutory reserves or regulatory capital.
- Does not replace a reconciliation, a close checklist or a controller's review.
- Where the data is insufficient, the correct output is a partial draft with explicit gaps, not a complete-looking statement built on assumptions.
