# Expected output — variance-analysis synthetic fixture

> This is the expected shape and arithmetic, not a recorded execution result. It is an analysis aid; a qualified finance professional must review it before it is used in reporting.

## 1. Reconciliation

| Line | Actual | Budget | Variance | Favorable / (Unfavorable) |
|---|---:|---:|---:|---:|
| Subscription revenue | 1,463,200 | 1,440,000 | +23,200 | Favorable |
| Cost of revenue | 458,800 | 432,000 | +26,800 | Unfavorable |
| Gross profit | 1,004,400 | 1,008,000 | (3,600) | Unfavorable |
| Marketing | 214,000 | 180,000 | +34,000 | Unfavorable |
| R&D | 286,000 | 300,000 | (14,000) | Favorable |
| G&A | 101,500 | 95,000 | +6,500 | Unfavorable |
| Operating income | 402,900 | 433,000 | (30,100) | Unfavorable |

## 2. Revenue decomposition

- Volume effect: (12,400 − 12,000) × 120.00 = **+48,000 favorable**
- Price effect: (118.00 − 120.00) × 12,400 = **−24,800 unfavorable**
- Net: +48,000 − 24,800 = **+23,200 favorable** (ties to the table)

## 3. Cost of revenue decomposition

- Volume effect: (12,400 − 12,000) × 36.00 = **+14,400 unfavorable**
- Rate effect: (37.00 − 36.00) × 12,400 = **+12,400 unfavorable**
- Net: **+26,800 unfavorable** (ties)

## 4. Materiality selection

| Line | Absolute variance | Percent | Threshold crossed? | Why selected |
|---|---:|---:|---|---|
| Cost of revenue | 26,800 | 6.2% | Yes, both | Margin pressure; volume and rate both adverse |
| Marketing | 34,000 | 18.9% | Yes, both | Largest dollar overrun; needs a program/timing explanation |
| Operating income | 30,100 | 7.0% | Yes, both | Aggregate consequence of the above |
| Subscription revenue | 23,200 | 1.6% | Dollar threshold not crossed | The volume driver is material and the price offset is close to the threshold; explain both |
| R&D | 14,000 | 4.7% | No | Below both thresholds; note timing only |
| G&A | 6,500 | 6.8% | Percent only | Small dollar impact; monitoring note |

## 5. Narrative samples

**Cost of revenue — unfavorable USD 26,800 (6.2%) vs budget.** Volume added USD 14,400 of cost at the budget rate, and the actual unit cost of USD 37.00 versus USD 36.00 added a further USD 12,400. The rate increase is the item to investigate: it is not explained by volume and may reflect vendor price, mix or a one-time charge. Outlook: expected to continue until the rate driver is confirmed. Action: investigate the unit-cost increase and update the forecast.

**Marketing — unfavorable USD 34,000 (18.9%) vs budget.** Spend is USD 34,000 above plan. The input does not identify whether this is timing, a program overrun or a deliberate incremental investment. Action: obtain the program-level breakdown before attributing the variance. Do not describe it as "higher demand" without evidence.

**Subscription revenue — favorable USD 23,200 (1.6%) vs budget.** Volume was 400 units above plan (+USD 48,000), offset by a USD 2.00 lower realized price (−USD 24,800). The net is favorable but the price decline is material to the unit economics and should be explained separately from the volume win.

## 6. Investigation order

Ordered by absolute line variance, then by unexplained driver:

1. Marketing program breakdown (USD 34,000 adverse, 18.9%, cause unknown)
2. Cost of revenue (USD 26,800 adverse, 6.2%; the USD 12,400 rate component is unexplained)
3. Realized-price decline (USD 24,800 adverse, offset by volume)
4. R&D timing (USD 14,000 favorable; confirm it is timing, not under-spend)

## 7. Acceptance checks

- Every decomposition sums back to the total variance.
- No narrative claims a cause that is not in the input.
- Materiality decisions show both dollar and percentage tests.
- Operating income ties to revenue minus cost and opex.
- The output states that a qualified finance professional must review it.
