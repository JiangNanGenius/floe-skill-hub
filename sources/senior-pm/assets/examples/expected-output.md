# Expected output — senior-pm synthetic fixture

> Expected calculations and report shape, not a recorded execution result. Monte Carlo is not run.

## Project health

### Project A — Customer portal migration

| Dimension | Input | Score | Weight | Contribution |
|---|---|---:|---:|---:|
| Timeline | 31 days late / 364 planned = 8.5% (amber) | 79 | 25% | 19.75 |
| Budget | 120,000 over / 1,000,000 = 12.0% (amber) | 69 | 25% | 17.25 |
| Scope | 16 / (20 + 2 − 1) = 76.2% (amber) | 62 | 20% | 12.40 |
| Quality | 0.7 × (0.8 × (1 − 0.5 × 0.2)) + 0.3 × 0.80 = 74.4% (red) | 52 | 20% | 10.40 |
| Risk | risk score 20 (amber) | 75 | 10% | 7.50 |
| **Composite** | | | | **67.3 → AMBER** |

Intervention level: **monitor** (composite ≤70 but >50). Priority-weighted score may be shown separately; it does not change the RAG.

### Project B — Billing reconciliation automation

| Dimension | Input | Score | Weight | Contribution |
|---|---|---:|---:|---:|
| Timeline | 0% delay | 100 | 25% | 25.00 |
| Budget | 2% under | 100 | 25% | 25.00 |
| Scope | 95% delivered | 95 | 20% | 19.00 |
| Quality | 0.7 × 1.0 + 0.3 × 0.97 = 99.1% (green) | 98 | 20% | 19.60 |
| Risk | risk score 8 (green) | 94 | 10% | 9.40 |
| **Composite** | | | | **98.0 → GREEN** |

Intervention level: **none**.

## Portfolio summary

- 2 active projects: 1 green, 1 amber, 0 red.
- Weakest dimension across the portfolio: quality (Project A at 52).
- Strongest dimension: timeline (average 89.5; Project B at 100, Project A at 79).
- Priority action: Project A's quality is red (52) and its timeline is amber (79); resolve the integration test environment before committing the January date.

## Risk register (ranked)

| Rank | Risk | Score | EMV | Response |
|---:|---|---:|---:|---|
| 1 | Portal integration slips again | 4 × 4 × 1.0 = 16.0 | 96,000 | Mitigate: freeze scope, add integration environment, weekly dependency review |
| 2 | Vendor API changes without notice | 3 × 4 × 1.0 = 12.0 | 48,000 | Mitigate: contract notice clause, adapter layer |
| 3 | Billing reconciliation misses edge cases | 2 × 3 × 1.2 = 7.2 | 10,000 | Accept with parallel-run monitoring |

Portfolio EMV sum: 154,000. This uses probability normalized from the 1–5 scale to 0–1 (4 → 0.8, 3 → 0.6, 2 → 0.4). This is an undiversified sum, not a single-point forecast; correlations were not supplied. Largest single exposure: 96,000. Concentration: schedule/external.

## Capacity

```
available = 8 × 40 × (1 − (0.15 + 0.05 + 0.10 + 0.05 + 0.12))
          = 320 × 0.53
          = 169.6 hours/week
utilization = 150 / 169.6 = 88.4%
```

Utilization is above the 85% sustainable band but below 95%; flag for reallocation discussion and protect the remaining capacity for unplanned work.

## Three-point scenario (no Monte Carlo)

If the integration work is estimated optimistic 6 weeks, most likely 9 weeks, pessimistic 16 weeks:

```
expected = (6 + 4×9 + 16) / 6 = 9.67 weeks
std_dev  = (16 − 6) / 6 = 1.67 weeks
```

Present this as a scenario range, not a simulated confidence interval. A formal Monte Carlo simulation is outside this guide.

## Executive summary (excerpt)

Portfolio is 1 green / 1 amber. Project B is on plan. Project A is amber: 8.5% late, 12% over budget, 76% scope complete and quality below the green band. The binding issue is integration testing, not feature work. Recommend freezing scope, standing up the integration environment this week, and re-baselining the January date after the next dependency review. No red projects.

## Acceptance checks

- Dimension scores tie to the stated inputs and weights.
- Composite/RAG/intervention use the documented thresholds.
- Risk score and EMV are shown separately.
- The portfolio EMV is labeled undiversified; no fake correlation.
- Capacity math shows the capacity factors and the utilization band.
- Monte Carlo is explicitly not run.
- No connector or script is used; the three-point scenario is explicitly illustrative, not measured data.
