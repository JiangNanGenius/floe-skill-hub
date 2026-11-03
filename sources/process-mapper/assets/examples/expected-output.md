# Expected output — process-mapper synthetic fixture

> Expected calculation and output shape, not a recorded execution result.

## Cycle time

| Metric | Value |
|---|---:|
| Stage count | 6 |
| Sum of stage P50 (screening) | 1,365 minutes |
| Sum of stage P90 (screening) | 4,795 minutes |
| Value-add P50 | 45 minutes |
| Wait P50 | 1,200 minutes |
| Rework P50 | 120 minutes |
| VA% | 3.3% |
| Wait% | 87.9% |
| Rework% | 8.8% |
| WIP | 12 |
| Throughput (Little's Law) | Not calculated: long-run means not supplied |
| Verdict (saas) | WASTE-HEAVY |

Calculation: 45 ÷ 1,365 = 3.3%; 1,200 ÷ 1,365 = 87.9%. The arithmetic proxy 12 ÷ (1,365 ÷ 60) = 0.5275 is not a Little's-Law throughput measurement: the fixture provides stage medians and a WIP value, not matching long-run means.

The stage quantile sums and derived shares are screening indicators. They do not establish end-to-end P50/P90 quantiles, process variability, or measured throughput.

## Ranked findings

| Rank | Rule | Severity | Finding | Evidence | Action | Impact (P50 min) |
|---:|---|---|---|---|---|---:|
| 1 | R2 | CRITICAL | Process dominated by wait time | 87.9% wait vs 40% saas threshold (≥2× threshold) | Remove or unbatch the manager/finance approval queues; apply a WIP limit upstream | 1,200 |
| 2 | R1 | CRITICAL | Slow stage: Wait for finance | 720 min vs value-add mean 15 min (48×; ≥3× multiplier) | Decompose the finance queue; move budget validation to a self-service check or parallel approval | 720 |
| 3 | R1 | CRITICAL | Slow stage: Wait for manager | 480 min vs value-add mean 15 min (32×; ≥3× multiplier) | Replace batched manager review with a conditional/continuous approval; set a decision SLA | 480 |
| 4 | R1 | CRITICAL | Slow stage: Rework — missing W-9 | 120 min vs 15 min mean (8×; ≥3× multiplier) | Add a W-9 check at request submission (poka-yoke); do not add downstream inspection | 120 |

**Impact overlap:** R2's 1,200 minutes is the combined wait time that is also attributed to the two R1 wait-stage findings. R1 and R2 impacts are not additive; do not sum the impact column. The R1 rework impact of 120 minutes is a separate stage and can be added to a stage-level remediation estimate, but not to the process-wide wait total.

R3 does not fire: 8.8% rework is below the 15% saas threshold. It is still a signal worth a preventive check.

## Swimlane (text)

```
Requestor lane:  [Submit request] --> [Rework: missing W-9]
Manager lane:    [Wait for manager approval queue] --> [Manager approves]
Finance lane:    [Wait for finance review] --> [Finance validates budget code]
```

## Recommendation

The constraint is the approval queue, not the value-add work. Remove or unbatch the manager and finance handoffs first; do not add headcount to a wait-bound process. Measure the change by total P50 and wait% after four weeks, not by stage-level utilization.

## Data-quality notes

- Durations are synthetic estimates, not measured; replace them with real timestamps before a change decision.
- Stage types are assumed honest. If the manager's queue includes real review work, split the review time from the wait time.
- WIP was supplied; without it, the throughput estimate would be omitted.

## Acceptance checks

- P50/P90 totals and ratios tie to the stage table.
- R1 and R2 findings are ranked by severity, then impact.
- R3 is evaluated and explicitly not triggered.
- The recommendation names one constraint, not a list of local optimizations.
- The output labels the data as estimated and states the measurement needed to verify improvement.
- R1 and R2 impacts are explicitly marked as overlapping and are not summed.
