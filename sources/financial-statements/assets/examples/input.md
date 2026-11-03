# Synthetic financial-statement input

> Synthetic fixture. Company, accounts and amounts are invented for acceptance testing. Not financial advice, not a filing and not an audited statement.

## Request

Prepare a **Q3 2026** (quarter ending 2026-09-30) management draft for **Cedarline Analytics, Inc. (synthetic)** under a **US GAAP-style** basis, in **USD thousands**, with prior-year quarter comparison. Budget/forecast was not supplied, so do not invent a budget column. Present the income statement, balance sheet and cash flow only to the extent the data supports them, and show the proofs.

## Income statement data

### Current quarter (2026-Q3)

| Account | Amount |
| --- | ---: |
| Product revenue | 4,820 |
| Service revenue | 1,930 |
| Other revenue | 250 |
| Cost of product revenue | 2,150 |
| Cost of service revenue | 780 |
| Cost of other revenue | 90 |
| Research & development | 1,240 |
| Sales & marketing | 1,410 |
| General & administrative | 690 |
| Interest income | 35 |
| Interest expense | (120) |
| Other income (expense), net | (15) |
| Income tax expense | 135 |

### Prior-year quarter (2025-Q3)

| Account | Amount |
| --- | ---: |
| Product revenue | 4,100 |
| Service revenue | 1,520 |
| Other revenue | 180 |
| Cost of product revenue | 1,950 |
| Cost of service revenue | 620 |
| Cost of other revenue | 70 |
| Research & development | 1,050 |
| Sales & marketing | 1,180 |
| General & administrative | 640 |
| Interest income | 18 |
| Interest expense | (95) |
| Other income (expense), net | 5 |
| Income tax expense | 55 |

Materiality: flag a line when the absolute variance is at least **150** (USD thousands) **or** the percentage variance is at least **10.0%**, using the absolute prior value as the denominator.

## Balance sheet data at 2026-09-30

| Line | Amount |
| --- | ---: |
| Cash and cash equivalents | 2,150 |
| Short-term investments | 800 |
| Accounts receivable, net | 1,450 |
| Inventory | 620 |
| Prepaid expenses and other current assets | 180 |
| Property and equipment, net | 3,300 |
| Operating lease right-of-use assets | 900 |
| Goodwill | 2,400 |
| Intangible assets, net | 350 |
| Other non-current assets | 150 |
| Accounts payable | 720 |
| Accrued liabilities | 640 |
| Deferred revenue, current | 520 |
| Current portion of long-term debt | 300 |
| Operating lease liabilities, current | 210 |
| Other current liabilities | 110 |
| Long-term debt | 2,800 |
| Deferred revenue, non-current | 380 |
| Operating lease liabilities, non-current | 690 |
| Other non-current liabilities | 130 |
| Common stock | 10 |
| Additional paid-in capital | 4,200 |
| Retained earnings | 1,615 |
| Accumulated other comprehensive income (loss) | (25) |
| Treasury stock | 0 |

Retained-earnings roll-forward: opening 1,290 + net income 405 - dividends 80 = closing 1,615.

## Cash flow data for 2026-Q3

| Line | Amount |
| --- | ---: |
| Net income | 405 |
| Depreciation and amortization | 210 |
| Stock-based compensation | 95 |
| Deferred income taxes | 10 |
| Decrease/(increase) in accounts receivable | (60) |
| Decrease/(increase) in inventory | 30 |
| Decrease/(increase) in prepaid and other | (10) |
| Increase/(decrease) in accounts payable | 30 |
| Increase/(decrease) in accrued liabilities | (40) |
| Increase/(decrease) in deferred revenue | 20 |
| Increase/(decrease) in other liabilities | 5 |
| Purchases of property and equipment | (180) |
| Purchases of investments | (100) |
| Proceeds from sale/maturity of investments | 50 |
| Repayment of debt | (150) |
| Effect of exchange rate changes on cash | 5 |
| Cash and cash equivalents, beginning of period | 1,830 |
| Cash and cash equivalents, end of period | 2,150 |

## Constraints

- Do not invent a budget column or an opening balance sheet that was not supplied.
- If a statement does not articulate, report the exact difference; do not add a plug.
- Do not state that the statements are final, filed, audited or approved.
- State the reporting basis and the jurisdiction/framework assumptions.
