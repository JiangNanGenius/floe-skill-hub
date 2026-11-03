---
name: process-mapper
description: Document a business process as a BPMN-style swimlane, compute cycle time and value-add ratio, and rank bottlenecks with deterministic rules and constraint-focused actions.
---

# Process Mapper

## Floe guide adaptation (read first)

- Adapted for Floe from the MIT-licensed upstream skill recorded in `references/PROVENANCE.md`; the BPMN-style mapping, Lean/Six Sigma/Theory-of-Constraints canon and deterministic analysis rules are retained.
- This is a guide-only package. The upstream Python helpers are not shipped and are not executed. Their screening rules are restated below, with statistical limitations made explicit for summed stage quantiles and Little's Law.
- Inputs are a process table, JSON skeleton or pasted stage data in the workspace. Outputs are a workspace process map, a cycle-time table, a ranked bottleneck list and one constraint-focused recommendation.
- No connector, script runtime or network access is used. If the user needs repeatable automation or a large measured dataset, that is a separate execution request, not this guide.

## Purpose

Internal-operations work suffers from three recurring failure modes:

1. **Implicit process** — the steps exist only in tribal knowledge, so handoffs drop and onboarding takes weeks.
2. **Invisible waiting** — most of the elapsed time on any business process is queue / wait / approval time, not actual work; teams optimize the wrong stage.
3. **Local optimization** — Goldratt's Theory of Constraints is ignored; resources are added to non-constraint stages, gaining nothing.

This skill produces a documented process map, identifies where work waits, and points the constraint out by name with deterministic logic — not model intuition.

## When to use

- Documenting a new business process (employee onboarding, incident handoff, expense reimbursement, customer onboarding, vendor intake or a similar internal workflow).
- An existing process is "too slow" but nobody can name the bottleneck.
- Cycle time is being measured but value-add ratio is not — so the team cannot tell whether the process is healthy or waste-heavy.
- Cross-functional handoffs are dropping work and root cause is unclear.

Do not use it for a one-off project, a sales pipeline, system-reliability SLOs or strategic prioritization. Those are different instruments.

## Workflow

Five steps. Do them in order; do not jump to a recommendation before the measurements exist.

1. **Intake.** Capture the process as a table or JSON file with one entry per stage: `name`, `owner`, `type` (`value-add` | `wait` | `rework`), `duration_minutes_p50`, `duration_minutes_p90`. Also record `process_name`, `owner role`, `frequency`, `trigger event`, `end state` and `wip` (items in process at once). Use `assets/process_template.md` and its JSON skeleton.
2. **Map stages.** Produce a text swim-lane diagram grouped by owner, with each stage annotated by type and P50/P90 duration. Separate lanes by owner so cross-functional handoffs are visible.
3. **Measure cycle time.** Compute summed-stage P50/P90 screening totals and value-add/wait/rework shares. Calculate Little's-Law throughput only when matching long-run mean WIP and mean end-to-end cycle time are supplied.
4. **Detect bottlenecks.** Apply rules R1-R3 below with the chosen profile. Rank findings by severity, then by impact.
5. **Recommend.** Pair the bottleneck list with the cycle-time verdict; recommend a single constraint-focused intervention per Goldratt's "subordinate everything to the constraint" rule. Do not recommend optimizing a non-constraint stage.

## Deterministic analysis

### Profile thresholds

| Profile | Healthy VA% | Typical VA% | R1 stage multiplier | R2 wait-share max | R3 rework-share max |
|---|---:|---:|---:|---:|---:|
| saas | ≥25% | 10–25% | 2.0× | 40% | 15% |
| services | ≥20% | 8–20% | 2.5× | 50% | 15% |
| manufacturing | ≥35% | 15–35% | 1.8× | 30% | 10% |
| healthcare | ≥20% | 8–20% | 2.5× | 55% | 12% |

If the profile is not specified, use `saas` and say so.

### Cycle-time formulas

Let each stage have a P50 and P90 duration in minutes.

```
total_p50 = sum(stage.p50)
total_p90 = sum(stage.p90)
value_add_p50 = sum(stage.p50 where type == "value-add")
wait_p50     = sum(stage.p50 where type == "wait")
rework_p50   = sum(stage.p50 where type == "rework")

VA%     = value_add_p50 / total_p50
wait%   = wait_p50 / total_p50
rework% = rework_p50 / total_p50

throughput_per_hour = mean_wip / (mean_end_to_end_cycle_minutes / 60)
# Little's Law needs means for the same stable process/window, not medians.
```

Verdict:

- `HEALTHY` when VA% ≥ the profile's healthy threshold
- `TYPICAL` when VA% ≥ the profile's typical threshold but below healthy
- `WASTE-HEAVY` when VA% < the profile's typical threshold

The variables total_p50 and total_p90 above are sums of stage quantiles for a sequential screening model; they are not measured end-to-end P50/P90 quantiles. Stage percentiles are not generally additive. Report the values as summed-stage screening totals, and use observed end-to-end distributions for real process quantiles. Their ratio is a screening indicator only. Parallel branches, conditional paths and repeated rework need an explicit path/frequency model before totals are useful.

Little's Law uses long-run mean WIP and mean end-to-end cycle time for the same stable process boundary and observation period. If only P50/P90 or a single WIP snapshot is available, leave throughput uncalculated and ask for the missing mean measurements. Do not substitute summed medians for a mean.

### Bottleneck rules

**R1 — slow stage.** Compute the mean P50 of all `value-add` stages. A stage whose P50 exceeds `multiplier × value-add mean` is a finding. Severity:

- `CRITICAL` when the stage's ratio to the value-add mean is ≥ 3 × the profile multiplier
- `HIGH` when the ratio is ≥ 2 × the profile multiplier
- `MEDIUM` otherwise

**R2 — wait-dominated process.** If `wait%` exceeds the profile's wait-share maximum, the process is wait-bound. Severity:

- `CRITICAL` when wait% ≥ 2 × the threshold
- `HIGH` when wait% ≥ 1.5 × the threshold
- `MEDIUM` otherwise

**R3 — excessive rework.** If `rework%` exceeds the profile's rework-share maximum, the process has a quality problem. Severity uses the same 2× / 1.5× rule against the rework threshold.

For each finding, give:

- rule ID and title
- severity
- detail with the measured value and threshold
- root-cause hypothesis (batched approvals, single approver, missing self-service, unclear acceptance criteria, upstream defect, handoff queue)
- one recommended action
- impact in P50 minutes

Rank findings by severity (`CRITICAL` → `HIGH` → `MEDIUM`), then by impact minutes descending.

### Reading the result

- If R2 is the dominant finding, adding people to a wait-bound process usually makes it worse. Remove the handoff, unbatch the approval, or apply a WIP limit.
- If R3 is present, fix the earliest stage that can detect the defect; do not add downstream inspection.
- If R1 identifies a stage that is not the constraint, do not optimize it. Subordinate it to the constraint first.
- Recommend one intervention, not a list of ten.

## Worked calculation

```
Stages (P50 minutes):
  Submit request        value-add   15
  Wait for manager      wait       480
  Manager approves      value-add   10
  Wait for finance      wait       720
  Finance validates     value-add   20
  Rework: missing W-9   rework     120

total_p50 = 1,365
VA% = (15 + 10 + 20) / 1,365 = 3.3%   -> WASTE-HEAVY for every profile
wait% = (480 + 720) / 1,365 = 87.9%   -> R2 CRITICAL (≥2 × 40%)
rework% = 120 / 1,365 = 8.8%          -> below the 15% saas threshold; no R3
value-add mean = 15; R1 threshold = 30; the wait stages are also caught by R2, and the 120-minute rework stage is an R1 finding. R1 and R2 impacts overlap; do not add them together.
```

The constraint is the approval queue, not the value-add work. The recommendation is to remove or unbatch the manager/finance handoffs, not to speed up the 15-minute request submission.

## Output contract

Produce one workspace document containing:

1. Process metadata and the stage table used (with assumptions marked).
2. The swim-lane map grouped by owner.
3. A cycle-time table: summed-stage P50/P90 screening totals, value-add/wait/rework screening shares, measured end-to-end quantiles if supplied, throughput only with the required means, and the screening verdict.
4. The ranked bottleneck list with rule, severity, evidence, hypothesis, action and impact.
5. One recommended constraint-focused intervention and the measurement that would prove it worked.
6. Data-quality notes: estimated vs measured durations, missing WIP, mislabeled stage types, any stage excluded.

If the user cannot supply stage-level durations, say that the first step is instrumentation, not mapping. Do not invent measurements.

## Assumptions

1. The user can provide stage-level cycle-time data (even rough P50/P90 estimates). If they cannot, the first step is to instrument the process — not to map it.
2. "Process" means a repeatable business workflow with discrete stages, not a one-off project.
3. The user has authority to act on bottlenecks (or can route findings to someone who does). Without that, the output is academic.
4. Stage `type` is honest: a "value-add" stage labeled as such by the user really does change the work product from the customer's perspective. Mislabeling waiting as value-add is the most common data-quality failure.

## Anti-patterns

- **Mapping every process at once.** Pick one. Goldratt: the constraint is a single point.
- **Optimizing the non-constraint.** If stage 4 is the bottleneck, speeding up stage 2 just builds inventory in front of stage 4. Subordinate everything to the constraint.
- **Mistaking total cycle time for processing time.** They are almost never the same; VA% reveals the gap.
- **Adding people to a wait-bound process.** Wait time is not solved by more headcount; it is solved by removing the handoff or batch.
- **Treating rework as a separate problem.** Rework loops belong in the process map. Hiding them understates true cycle time.
- **Automating a broken process.** Map the value stream, remove wait and rework, then consider automation.

## Distinct from

- **Sales operations** — external sales motion, lead-funnel conversion, customer-success retention. Process-mapper is internal operations.
- **System reliability** — SLOs, error budgets and burn-rate alerts. Process-mapper is business-process cycle time, not system uptime.
- **Executive strategy** — which processes to fix. Process-mapper is the tactical instrument used after that prioritization decision.
- **Project management** — ticket workflow tooling. Process-mapper is process design, not ticket tracking.

## Forcing questions

Walk these one at a time before calculating. Never bundle them.

1. **"Do you have measured cycle times for the top-3 longest stages, or only estimates?"** Insist on measured data where possible. Goldratt: optimizing estimated bottlenecks reliably attacks the wrong constraint.
2. **"Are you mapping the current process or the intended process?"** Map as-is first. Rother & Shook: value-stream mapping starts with the current state.
3. **"Where do handoffs occur between teams, and how long does each handoff wait?"** Log every handoff with median wait time. Reinertsen: wait at handoffs is the largest invisible cost.
4. **"What is your batch size at each stage?"** Drive batch size toward one where possible. Anderson: batch size correlates with cycle-time variance.
5. **"What is the rework rate per stage?"** Surface it explicitly. Pyzdek: hidden rework drives a large share of service-process cycle time.

## References

- [`references/lean_six_sigma_canon.md`](references/lean_six_sigma_canon.md) — TIMWOOD wastes, value-stream mapping, Theory of Constraints, Kanban WIP, Little's Law
- [`references/bpmn_essentials.md`](references/bpmn_essentials.md) — pools, lanes, gateways, events, message flows, common notation mistakes
- [`references/bottleneck_anti_patterns.md`](references/bottleneck_anti_patterns.md) — nine anti-patterns drawn from Goldratt, Deming, Spear, DORA and process-mining research
- [`assets/process_template.md`](assets/process_template.md) — stage table and JSON skeleton

## Floe inputs and outputs
A synthetic input is in [`assets/examples/input.md`](assets/examples/input.md) and the expected output shape is in [`assets/examples/expected-output.md`](assets/examples/expected-output.md); both are test fixtures, not executed results.


**Minimum input:** one process, stage names, owners, stage types, P50/P90 durations, WIP, frequency, trigger and end state.

**Output:** one process-mapping document with the swimlane, cycle-time table, ranked bottlenecks and one recommended intervention. No external execution, no invented durations.
