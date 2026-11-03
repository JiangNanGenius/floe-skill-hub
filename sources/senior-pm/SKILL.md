---
name: senior-pm
description: Run portfolio health reviews, quantitative risk analysis, capacity planning and executive reporting for multi-project programs using deterministic scoring and templates.
---

# Senior Project Management Guide

## Floe guide adaptation (read first)

- Adapted for Floe from the MIT-licensed upstream skill recorded in `references/PROVENANCE.md`; the portfolio, risk, prioritization and executive-reporting frameworks are retained, and the templates under `assets/` are preserved.
- This is a guide-only package. The upstream Python helpers are not shipped and are not executed. The deterministic scoring and formulas they implemented are restated below for manual application from a project table.
- Inputs are a project portfolio table, risk register and capacity table in the workspace, or pasted equivalents. Outputs are a health dashboard, risk register, capacity view and executive report in the workspace.
- Monte Carlo simulation is not executed in guide-only mode. Use the three-point estimate and scenario range described below; if a formal simulation is required, that is a separate execution request with real tooling.
- No Jira, Confluence, financial-system or MCP connector is used. Exported data must be provided by the user.

## Overview

Strategic project management for enterprise software, SaaS and digital transformation initiatives. The guide provides portfolio management, quantitative risk analysis and executive reporting frameworks for complex, multi-project portfolios.

### Core expertise areas

**Portfolio management and strategic alignment**

- Multi-project portfolio optimization using WSJF, RICE, ICE, MoSCoW and multi-criteria decision analysis
- Strategic roadmap development aligned to business objectives
- Resource capacity planning and allocation
- Portfolio health monitoring with multi-dimensional scoring

**Quantitative risk management**

- Expected Monetary Value (EMV) analysis
- Three-point estimation and scenario ranges
- Risk appetite thresholds and contingency reserves
- Portfolio risk correlation and concentration

**Executive communication and governance**

- Board-ready reports with RAG status and recommendations
- Stakeholder alignment through RACI matrices and escalation paths
- Financial performance tracking with risk-adjusted ROI and NPV
- Change management for large transformations

## Three-tier analysis

### Tier 1 — Portfolio health assessment

Score each active project across five dimensions. Use the thresholds below and interpolate a 0–100 score within each band.

| Dimension | Weight | Green | Amber | Red |
|---|---:|---|---|---|
| Timeline | 25% | ≤5% delay | 5–15% delay | >15% delay |
| Budget | 25% | ≤5% over | 5–15% over | >15% over |
| Scope | 20% | ≥90% delivered | 75–90% delivered | <75% delivered |
| Quality | 20% | ≥95% quality score | 85–95% | <85% |
| Risk | 10% | risk score ≤15 | 15–25 | >25 |

**Scoring bands**

- Green band: 90–100 points
- Amber band: 60–89 points
- Red band: 10–59 points

Within a band, interpolate linearly and report a whole-point score rounded down. For example, a 10% budget overrun is halfway through the 5–15% amber band, so the budget score is 75 (60 + 15), not 70.

**Composite**

```
composite = 0.25×timeline + 0.25×budget + 0.20×scope + 0.20×quality + 0.10×risk
RAG: green ≥80, amber ≥60, red <60
Intervention: immediate ≤30, urgent ≤50, monitor ≤70, none >70
```

Priority weighting may be shown separately (`critical` 1.5, `high` 1.2, `medium` 1.0, `low` 0.8) but the RAG status uses the unadjusted composite so a high-priority project is not made to look healthy by its priority.

**Timeline variance**

```
delay = max(0, forecast_end - planned_end) / planned_duration
```

Use the actual start and forecast end when available. If a project is completed or cancelled, use zero.

**Budget variance**

```
overrun = max(0, forecast_total_cost - planned_budget) / planned_budget
```

Use the forecast total cost when available; otherwise use spend to date and say so.

**Scope completion**

```
effective_plan = planned_features + added_features - descoped_features
scope_completion = completed_features / effective_plan
```

If there are no planned features, treat scope as complete and note the assumption.

**Quality score**

```
resolution_rate = resolved_defects / total_defects
critical_penalty = critical_defects / total_defects
defect_score = resolution_rate × (1 - 0.5 × critical_penalty)
quality = 0.7 × defect_score + 0.3 × test_coverage
```

If there are no defects, use 1.0 for the defect component. Use the resulting quality score against the quality thresholds; do not use test coverage alone. State what "test coverage" means for the project; if it is not measurable, mark the quality dimension as partial rather than inventing a number.

**Risk score**

Use the risk register's probability × impact scores (1–5 scale) with category weights below. Report the portfolio risk score and the individual project risk score separately.

### Tier 2 — Risk matrix and mitigation

**Risk register fields:** description, category, probability (1–5), impact (1–5), financial impact, owner, mitigation, status.

**Score and EMV**

```
risk_score = probability_1_to_5 × impact_1_to_5 × category_weight
EMV = (probability_1_to_5 / 5) × financial_impact
```

Use the 1–5 rating for the risk score and convert it to a 0–1 decimal for EMV. State the convention next to the table.

Default category weights:

| Category | Weight |
|---|---:|
| Technical | 1.2 |
| Resource | 1.1 |
| Financial | 1.4 |
| Schedule | 1.0 |
| Business | 1.3 |
| Regulatory | 1.5 |
| External | 1.0 |

**Response thresholds by score**

- Avoid (>18): eliminate through scope or approach change
- Mitigate (12–18): reduce probability or impact
- Transfer (8–12): insurance, contract, partnership
- Accept (<8): monitor with contingency

These are the written response bands retained from the upstream guide. Use the higher-severity response at an exact boundary: 8 → Transfer, 12 → Mitigate, 18 → Avoid. The excluded helper used a different internal tolerance label set (low/medium/high/critical); do not mix the two schemes. This guide uses the response bands above and reports the numeric score alongside them.

**Risk appetite**

| Appetite | Risk score range | Contingency reserve |
|---|---|---:|
| Conservative | 0–8 | 25–30% |
| Moderate | 8–15 | 15–20% |
| Aggressive | 15+ | 10–15% |

**Portfolio risk aggregation**

Expected losses are additive: report the sum of the individual EMVs, the largest single exposure and concentration by category. Correlation does not change the sum of expected losses; it affects the dispersion and tail risk. The sum of EMVs is not an upper bound or a worst-case loss.

Only when loss standard deviations and pairwise correlations are supplied, calculate portfolio standard deviation in the same monetary units:

```
portfolio_std_dev = sqrt(sum(sigma_i²) + 2 × sum(correlation_ij × sigma_i × sigma_j for each distinct pair i < j))
```

Do not substitute EMVs, ordinal risk scores or financial impacts for standard deviations. If dispersion or correlation inputs are missing, leave portfolio standard deviation and probability quantiles uncalculated and report the expected-loss sum and concentration separately.

**Three-point estimate**

```
expected = (optimistic + 4×most_likely + pessimistic) / 6
std_dev  = (pessimistic - optimistic) / 6
```

Use this for three-point schedule or cost estimates and clearly labelled optimistic/base/pessimistic scenarios. These formulas alone do not establish P50/P90 quantiles or confidence intervals. A formal Monte Carlo simulation is outside this guide; do not label scenario endpoints as probability quantiles.

### Tier 3 — Resource capacity

**Utilization bands**

| Utilization | Interpretation |
|---|---|
| <60% | Under-utilized — check for partial allocation or missing work |
| 60–85% | Sustainable range |
| 85–95% | Over-utilized — queue risk and burnout risk |
| >95% | Critical — reallocate before committing more work |

**Capacity calculation**

```
available_hours = headcount × hours_per_week × (1 - capacity_factor_total)
demand_hours = sum(project allocations × complexity_factor)
utilization = demand_hours / available_hours
```

Default capacity factors: meetings 15%, learning 5%, administrative 10%, context switching 5%, vacation/sick 12%. Sum the applicable factors and deduct the total from gross hours (the worked example uses 0.47); use the organization's actual figures when available.

Complexity factors: simple 1.0, moderate 1.2, complex 1.5, very complex 2.0.

**Rules**

- Flag any team above 90% or below 60% for a reallocation discussion.
- Do not add people to a wait-bound process; check the process constraint first.
- Skill matching is a judgment call, not an algorithmic output. Show the gap and let the owner decide.

## Advanced prioritization models

Apply each model where it provides the most signal.

**WSJF** — resource-constrained agile portfolios with quantifiable cost of delay:

```
WSJF = (user_value + time_criticality + risk_reduction) / job_size
```

**RICE** — customer-facing initiatives with reach metrics:

```
RICE = (reach × impact × confidence%) / effort_person_months
```

**ICE** — rapid prioritization:

```
ICE = (impact + confidence + ease) / 3
```

**MoSCoW** — multiple stakeholder groups with differing priorities.

**MCDA** — complex tradeoffs across incommensurable criteria.

**Model selection logic**

```
if resource_constrained and agile and cost_of_delay_quantifiable: WSJF
elif customer_facing and reach_metrics_available: RICE
elif quick_prioritization_needed: ICE
elif multiple_stakeholder_groups: MoSCoW
elif complex_incommensurable_tradeoffs: MCDA
```

State the model chosen and why. Do not average scores from different models into one number.

## Risk management framework

**Step 1 — Classify by category:** technical, resource, schedule, financial, business, regulatory, external.

**Step 2 — Assess probability and impact** on 1–5 scales, with a short evidence note for each. A score without evidence is an opinion.

**Step 3 — Prioritize** by risk score and EMV; show both because a high-probability, low-financial-impact risk and a low-probability, catastrophic risk need different responses.

**Step 4 — Plan responses:** avoid, mitigate, transfer or accept, with an owner and a trigger date.

**Step 5 — Monitor:** review at the portfolio cadence; update probability, impact and status. Retain closed risks for postmortems.

## Operating cadence

### Weekly portfolio health review

1. Validate the project table: status, dates, budget, scope, quality and risk fields.
2. Compute dimension scores and composite RAG for each active project.
3. Stop if any composite is below 60 or a critical field is missing; resolve data integrity before reporting.
4. Update the risk register; escalate any risk score above 18.
5. Review capacity: flag teams above 90% or below 60%.
6. Write the executive summary using `assets/executive_report_template.md`.

### Monthly strategic review

1. Re-score priorities with WSJF/RICE/ICE as appropriate.
2. Review risk appetite, concentration and mitigation investment.
3. Review capacity constraints for the next quarter and identify skill gaps.
4. Align stakeholders on the next quarter's priorities.

### Quarterly portfolio optimization

1. Assess strategic alignment and market changes.
2. Review risk-adjusted ROI and forecast accuracy.
3. Identify capability gaps and make/buy/partner options.
4. Rebalance the portfolio across horizons and risk-return.

## Assets and templates

- [`assets/project_charter_template.md`](assets/project_charter_template.md) — 12-section charter with success criteria, RACI, risk, budget, timeline and governance
- [`assets/executive_report_template.md`](assets/executive_report_template.md) — board-level RAG dashboard, financial performance, risk heat map and recommendations
- [`assets/raci_matrix_template.md`](assets/raci_matrix_template.md) — stakeholder roster, phase-based RACI and escalation paths
- [`assets/sample_project_data.json`](assets/sample_project_data.json) — synthetic multi-project portfolio input
- [`assets/expected_output.json`](assets/expected_output.json) — the output shape the upstream tools produced; use it as a structural reference, not as a result for a new portfolio

## Integration and handoff

- **Jira/Confluence or another tracker** — use a user-provided export or pasted table. Do not claim a live connection.
- **Financial systems** — use a user-provided budget/actual export. Do not claim real-time spend data.
- **Stakeholders** — executive dashboards, team scorecards and risk registers are workspace documents the owner can share through their normal channels.

**To a Scrum Master:** strategic priorities, success criteria, resource allocation, risk factors, quality standards and acceptance criteria.

**To a Product Owner:** market priorities, user-value framework, feature prioritization, resource and timeline constraints, ROI analysis and risk assessment.

**From the executive team:** business objectives, budget and resource decisions, risk appetite, market strategy and performance expectations.

## Limitations

- Monte Carlo simulation is not executed. Use three-point estimates and scenario ranges, and label them honestly.
- Capacity and financial figures depend on the quality of the user's table. Do not invent missing rates, utilization or budgets.
- A composite health score is a communication aid, not an audit opinion. Show the dimension scores so the owner can challenge the weighting.
- This guide does not replace project accounting, legal advice or a formal risk-management system.

## Floe inputs and outputs
A synthetic input is in [`assets/examples/input.md`](assets/examples/input.md) and the expected output shape is in [`assets/examples/expected-output.md`](assets/examples/expected-output.md); both are test fixtures, not executed results.


**Minimum input:** project list with status, planned/forecast dates, budget/actuals, scope counts, quality indicators and risk scores; a risk register; a capacity table; the review period and portfolio priorities.

**Output:** a portfolio health dashboard with dimension scores and RAG, a ranked risk register with EMV and responses, a capacity view with utilization flags, and an executive report. No external connector, script execution or invented data.
