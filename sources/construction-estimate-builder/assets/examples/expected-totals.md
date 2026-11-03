# Expected totals — synthetic estimate

> **Synthetic acceptance example.** USD, tax excluded, estimate date 2026-10-31. Unit costs are illustrative and are not market rates. This is an estimate example, not a tender, fixed quote or final account.

## Line totals

| Line | Description | Qty | Unit | Unit cost | Line total | Category |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Site preparation | 5,000 | SF | 2.50 | 12,500.00 | other |
| 2 | Concrete foundation | 200 | CY | 350.00 | 70,000.00 | material |
| 3 | Foundation formwork | 1,500 | SF | 8.50 | 12,750.00 | labor |
| 4 | Structural steel | 50 | TON | 4,500.00 | 225,000.00 | subcontractor |

## Category summary

| Category | Amount | % of direct |
| --- | --- | --- |
| Labor | 12,750.00 | 4.0% |
| Material | 70,000.00 | 21.9% |
| Equipment | 0.00 | 0.0% |
| Subcontractor | 225,000.00 | 70.3% |
| Other | 12,500.00 | 3.9% |
| **Direct cost** | **320,250.00** | **100.0%** |

The displayed percentages are rounded and sum to 100.1%; the amounts are exact.

## Markups

| Markup | Rate | Base | Base amount | Markup amount | Running subtotal |
| --- | --- | --- | --- | --- | --- |
| Overhead | 15% | direct | 320,250.00 | 48,037.50 | 368,287.50 |
| Profit | 10% | subtotal | 368,287.50 | 36,828.75 | 405,116.25 |
| Contingency | 5% | subtotal | 405,116.25 | 20,255.81 | 425,372.06 |

## Grand total

**USD 425,372.06**, tax excluded, estimate date 2026-10-31.

Recompute check: 320,250.00 + 48,037.50 + 36,828.75 + 20,255.81 = 425,372.06.

## Acceptance checks

- [ ] Four line items; each quantity > 0 and each unit cost >= 0.
- [ ] Direct cost = 320,250.00 and equals the sum of line totals.
- [ ] Overhead uses the direct base; profit and contingency use the running subtotal.
- [ ] Grand total = 425,372.06 with the displayed rounded markup amounts.
- [ ] The rates 15/10/5 are labelled as illustrative defaults, not mandated or market rates.
- [ ] The source note on every line says the rate is synthetic.
- [ ] No currency, tax basis or date is missing.
- [ ] The output is labelled an estimate, not a tender or fixed quote.
