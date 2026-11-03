---
name: vendor-review
description: Evaluate a vendor proposal, renewal or comparison with a three-year total-cost model, must-have gates, an evidence-based weighted scorecard, risk and conflict-of-interest checks, and negotiation points. Guide-only; it does not approve, purchase, pay, sign, contact a vendor or make a procurement decision.
---

# Vendor Review

## Floe guide adaptation (read first)

- Adapted for Floe from the Apache-2.0 upstream skill recorded in `references/PROVENANCE.md`. The cost, risk, performance and comparison framework is retained and expanded into a deterministic evaluation method with explicit must-have gates, evidence labels, scoring coverage, conflict-of-interest handling and renewal/exit management.
- Bring the vendor material: proposals, quotes, contract terms, current spend, volumes, requirements, security reports, SLA history, references and any declared conflicts. Paste text or attach workspace files (Markdown, CSV, PDF export). No procurement system, contract repository, CRM, finance system or vendor portal is connected or implied.
- The output is a **decision-support draft**: a recommendation with conditions, a total-cost table, a scorecard, a risk register, an evidence ledger, open questions and negotiation points. The guide does not issue a purchase order, approve spend, sign or terminate a contract, pay an invoice, contact a vendor or change any procurement record.
- All spend is in the currency you supply. Do not convert currencies with an invented rate; if a rate is needed, require the rate and its date. All scores are judgments on supplied evidence, not verified vendor performance.
- Repository attention and repository-wide commits are not evidence about this skill's content freshness. The upstream path history is in `references/PROVENANCE.md`; no recent-content claim is made.

**Important**: A recommendation from this guide is not an approval, a legal opinion, a security certification or a financial commitment. The authorized procurement, finance, security and legal owners must review the evidence and make the decision.

## Input contract

Provide, or state that a value is missing:

| Input | Why it is needed |
| --- | --- |
| Decision and deadline | New vendor, renewal, replacement or comparison; when the decision is needed |
| Vendors and legal entities | Prevents comparing different affiliates or resellers |
| Proposal, quote and contract terms | The primary cost and obligation evidence |
| Currency, tax treatment and payment terms | Keeps totals comparable |
| Contract horizon and renewal/notice dates | Sets the TCO period and the auto-renewal risk |
| Current spend and incumbent terms | The baseline for a renewal or replacement |
| Seats, usage, volume and growth assumptions | Drives subscription, overage and true-up cost |
| Price escalation, discount expiry and minimum commitment | Prevents a misleading year-one price |
| Implementation, migration, training and internal labor | The costs most often omitted from a quote |
| Support tier, SLA, service credits and exclusions | Converts a promise into an enforceable term |
| Security and privacy evidence: reports, certifications, subprocessors, data residency | Distinguishes a claim from a verified control |
| Data-portability, export and termination assistance | The exit cost and lock-in risk |
| References and reference-check evidence | Distinguishes independent evidence from vendor marketing |
| Requirements, weights and must-haves | Makes the scorecard decision-relevant |
| Scoring anchors or a supplied rubric | Overrides the default anchors without silently changing the scale |
| Known conflicts of interest | Protects the integrity of the recommendation |
| Legal, regulatory or policy constraints | May disqualify a vendor regardless of score |
| Decision owner and approval path | Keeps the recommendation inside real authority |

If a value is missing, mark it **UNKNOWN**. Do not infer a discount, a usage tier, a security certification, a reference's independence or a renewal term.

## Evidence hierarchy

Label every material claim:

| Level | Evidence | How it may be used |
| --- | --- | --- |
| **E1 — Supplied primary document** | A contract, order form, audit report, certificate or system-generated SLA extract that the evaluator has read, with its stated scope and date | May support a score and a recommendation |
| **E2 — Vendor assertion** | Proposal, sales deck, security questionnaire response, case study, roadmap statement | May be reported as a vendor claim; cannot alone prove a control or a performance level |
| **E3 — Independent reference** | A reference the evaluator selected, with a documented conversation and no vendor payment | Supports a score with the reference's scope and date |
| **E4 — Evaluator judgment** | A reasoned estimate from comparable experience | Use only with an explicit label and never as a substitute for a must-have |
| **E5 — Unknown** | No evidence | Score `null`; do not impute a middle value |

Rules:

- **E1 means the document was supplied and read, not independently authenticated.** The guide does not verify a signature, validate an auditor, confirm that a certificate is current, or establish that a report covers the proposed service. Those remain reviewer checks; record what was and was not checked.
- A vendor's "SOC 2 Type II" statement is E2 until the report (scope, period, auditor, exceptions) is supplied. A bridge letter is not the report.
- A vendor-provided case study or a reference arranged by the vendor is E2, not E3.
- An SLA percentage in a proposal is E2 until the contract's service-credit and exclusions clauses are read.
- A "list price" without a quote is not a cost commitment.
- Absence of evidence is **UNKNOWN**, not a low score. Never turn missing evidence into a 1.

## Step 1 — Define the decision and must-haves

Write:

1. **Decision:** new vendor / renewal / replacement / comparison; the business outcome; the decision date.
2. **Scope:** products, entities, regions, users and data in scope; what is explicitly out of scope.
3. **Must-haves:** requirements that disqualify a vendor if failed. Each must have a test, an evidence source and a pass/fail/unknown rule. Examples: data residency in a named region; a current SOC 2 Type II report; a specific integration; a regulatory approval; a maximum implementation date.
4. **Weighted criteria:** functional fit, cost, reliability, security, support, exit/portability, or a supplied rubric.
5. **Decision owner and approvers:** roles only; do not invent names.
6. **Constraints:** budget ceiling, headcount, migration window, legal or policy constraints.

A must-have is not "important"; it is a gate with a defined failure. If everything is a must-have, the evaluation cannot differentiate vendors.

## Step 2 — Build the total cost of ownership

Use the supplied horizon (default three years if the decision is multi-year). Show every assumption.

### Cost categories

| Category | What to include | One-time / recurring |
| --- | --- | --- |
| License / subscription | Base seats, tiers, platform fee, minimum commitment | Recurring |
| Usage / overage | Per-transaction, per-API-call, storage, egress, true-up | Recurring |
| Implementation | Professional services, configuration, data load | One-time |
| Migration | Source extraction, transformation, validation, parallel run | One-time |
| Training | Admin and end-user training, documentation | One-time or recurring |
| Support | Support tier, premium SLA, named contact | Recurring |
| Add-ons | Modules, connectors, sandbox, additional environments | Recurring |
| Integration | Middleware, licenses, internal engineering time (if supplied) | One-time or recurring |
| Internal labor | Only the supplied, quantified estimate; do not invent a rate | One-time or recurring |
| Price escalation | Contractual uplift, CPI clause, discount expiry | Recurring |
| Exit | Data export, deletion, termination assistance, parallel running | End of horizon |

### Method

1. State currency, tax treatment, payment terms and the FX rate/date if more than one currency is supplied.
2. Build a year-by-year table for the horizon: year 1, year 2, year 3 (or the supplied horizon).
3. Apply the contractual escalation to the recurring base; do not apply an assumed market increase.
4. Put one-time costs in the year they are incurred.
5. Keep optional modules and unapproved scope separate; show "base" and "with options" totals.
6. Show the exit cost separately and also in a total including exit if the decision could end at the horizon.
7. Label every unknown as **UNKNOWN** and quantify its effect if a range is supplied. Do not insert a plausible number.
8. Report **cost coverage**: known cost as a percentage of the estimated total. If known cost is below 90% of the total, the TCO is **provisional**.
9. Do not treat a year-one discount as a permanent price. Show the cliff.
10. Do not compare totals in different currencies without the supplied rate and date.

### Formula

```
Year n recurring = (license + usage + support + add-ons + integration recurring)
                   × (1 + escalation)^(n-1)
Year n total     = Year n recurring + one-time costs in year n
Horizon total    = sum(Year 1..N totals)
Total incl. exit = Horizon total + exit cost at end of horizon
```

Show the arithmetic for at least the first year and the horizon total. Round to the currency's minor unit and state the rounding.

## Step 3 — Score the criteria

### Default weights and anchors

Use the supplied weights if provided. Otherwise use:

| Criterion | Weight | What it covers |
| --- | ---: | --- |
| Cost and commercial terms | 25 | TCO, price predictability, escalation, payment terms, discount cliff |
| Functional fit | 20 | Requirements coverage, workflow fit, configuration vs customization |
| Reliability and SLA | 20 | Uptime evidence, credit mechanics, exclusions, incident history |
| Security and compliance | 15 | Verified reports, data residency, access control, subprocessors, privacy terms |
| Support and services | 10 | Support tier, response evidence, implementation capability, escalation path |
| Exit and portability | 10 | Data export, deletion, termination assistance, lock-in |
| **Total** | **100** | |

Anchors (use the same anchors for every vendor in the comparison):

| Score | Meaning |
| ---: | --- |
| **5** | Exceeds the requirement with supplied primary-document evidence and a material advantage |
| **4** | Meets the requirement with supplied primary-document evidence and no material gap |
| **3** | Meets the requirement with a minor gap or a documented mitigation |
| **2** | Partially meets with a material gap that needs a mitigation plan |
| **1** | Fails the requirement |
| **null** | Insufficient evidence; do not score |

### Scoring rules

- Score each criterion once per vendor; record the evidence id and a one-sentence rationale.
- A must-have is **PASS**, **FAIL** or **UNKNOWN**; it is not averaged into the score.
- Compute the weighted score only over criteria with a numeric score:

```
weighted score = sum(weight_i × score_i) / sum(weight_i for scored criteria)
coverage       = sum(weight_i for scored criteria) / 100
```

- Report the score to two decimals and the coverage as a percentage.
- If coverage is below 80%, mark the result **provisional** and do not present it as a complete ranking.
- Do not compare two vendors with materially different coverage as if the scores were equivalent. State the missing criteria and the effect.
- Ties: compare must-have coverage first, then the risk profile, then TCO. Never break a tie on price alone.
- Do not use a score to override a must-have FAIL or UNKNOWN.
- Do not let a vendor's self-score or a sales narrative set the evidence level.

## Step 4 — Assess risk

Build a risk register with:

- **Risk** in concrete terms (not "security risk").
- **Likelihood** High / Medium / Low, with the basis.
- **Impact** High / Medium / Low, in business terms.
- **Evidence** and its level.
- **Mitigation** with an owner role and a trigger.
- **Residual risk** after mitigation.

Cover at least:

| Area | Questions |
| --- | --- |
| Financial | Vendor viability, funding, ownership change, minimum commitment, currency exposure |
| Security | Verified attestations, scope, exceptions, incident history, access model, subprocessors |
| Privacy | Data residency, processor terms, retention, deletion, cross-border transfer, subprocessor notice |
| Compliance | Required certifications, audit rights, records retention, regulated data |
| Concentration | Single-vendor dependency, critical path, replaceability, skills concentration |
| Continuity | RTO/RPO, disaster recovery evidence, exit and termination assistance |
| Contractual | Auto-renewal, unilateral change, price escalation, SLA exclusions, limitation of liability, indemnity |
| Delivery | Implementation track record, resourcing, roadmap dependency, change control |
| Geopolitical / regulatory | Sanctions, local-content rules, government access, data-localization changes |

Red flags that require explicit treatment:

- auto-renewal with a short notice window;
- a price increase that starts after year one;
- "unlimited" usage with a fair-use or hidden cap;
- SLA credits that are the sole remedy and are capped below the business impact;
- data ownership or deletion terms that are unclear;
- termination assistance not priced or not committed;
- a security claim without a report, scope or date;
- a reference that is paid, vendor-selected or undisclosed.

## Step 5 — Check conflicts of interest

Before scoring, require a written declaration from each evaluator:

- current or former employment or contracting with the vendor (state the dates);
- equity, options, debt or other financial interest;
- family or close personal relationship with a vendor employee or owner;
- gifts, hospitality, travel or entertainment above the organization's threshold;
- paid advisory, speaking or advocacy relationship;
- a competitive or reseller relationship;
- involvement in building or selling the evaluated solution;
- any other interest a reasonable observer would consider relevant.

Rules:

- A **material conflict** means the evaluator cannot be the sole author of the recommendation. Record it and require an independent reviewer or recusal.
- If the conflict affects only one vendor, that vendor's evaluation is tainted; do not rank it as the winner from that evaluator.
- If the conflict is declared late or discovered after the recommendation, pause the decision and re-run the affected scoring with an independent reviewer.
- Vendor-provided references, case studies and paid analysts are not independent evidence; label them.
- The output must state the declaration status and the effect on the recommendation. "No conflict declared" is not proof that none exists.

## Step 6 — Check references and vendor claims

- Use references the evaluator selected, not only the vendor's list.
- Record the reference's role, company size, deployment scope, date and whether the vendor arranged the call.
- Ask about implementation effort, support responsiveness, outage handling, hidden costs, exit and what they would change.
- A reference that cannot discuss a failure or a limitation is weak evidence; note it.
- Do not treat a public case study as an independent reference.
- Do not contact a reference or vendor from this guide; the output is a script and a record for the human.

## Step 7 — Recommend and prepare negotiation points

Choose one recommendation:

- **Proceed** — the vendor passes every must-have, the evidence supports the weighted result, the conflicts are cleared, and the remaining conditions are listed.
- **Negotiate** — the vendor is viable but the commercial, SLA, security or exit terms need a specific change before approval.
- **Hold** — a must-have is UNKNOWN, evidence coverage is too low, a material conflict is unresolved, or a critical risk has no mitigation.
- **Do not proceed** — a must-have FAILs, a legal/regulatory constraint is violated, or the risk is unacceptable.

The recommendation must state:

- the decision and date;
- the must-have results;
- the TCO and its coverage;
- the weighted score and coverage;
- the top risks and mitigations;
- the conflict declaration and its effect;
- the conditions or open questions;
- the decision owner (role) and the approvals still required.

### Negotiation points

Prioritize terms that change the economics or the exit:

- price cap and escalation schedule;
- discount cliff and multi-year protection;
- usage tiers, overage rate and true-up mechanics;
- SLA definition, measurement, exclusions and credits;
- support response and escalation path;
- implementation milestones and acceptance;
- data residency, subprocessor notice and audit rights;
- termination for convenience, notice period and termination assistance;
- data export format, frequency and deletion certification;
- limitation of liability, indemnity and security obligations;
- renewal notice and auto-renewal removal;
- reference and benchmark evidence.

Do not invent market benchmarks, competitor prices or "standard" discounts. Label an assumption as an assumption.

## Managing an existing vendor

Evaluation continues after signature. For a renewal or an incumbent review:

1. **Performance evidence:** compare actual availability, response times, incident duration and credit claims against the contract. Use system-generated data where supplied; do not rely on the vendor's quarterly narrative alone.
2. **Commercial drift:** compare current spend, seats and usage with the contract; identify true-ups, unused licenses, add-ons and price escalation.
3. **Security currency:** check attestation dates, scope, exceptions, subprocessor changes and open remediation.
4. **Relationship and risk:** record escalations, roadmap dependency, concentration and any change of ownership.
5. **Exit readiness:** test whether the data can be exported in a usable format, how long it takes, what it costs and what would break.
6. **Renewal calendar:** record notice dates, auto-renewal, price-change notice and decision milestones.
7. **Improvement plan:** for a underperforming but retained vendor, set measurable targets, an owner and a review date; do not call a plan a resolution.

## Floe output contract

A synthetic example is in [`assets/examples/input.md`](assets/examples/input.md), its machine-readable facts are in [`assets/examples/figures.json`](assets/examples/figures.json), and the expected output shape is in [`assets/examples/expected-output.md`](assets/examples/expected-output.md). They are synthetic examples, not executed results.

Produce these sections in order:

1. **Decision summary** — decision type, date, recommendation, conditions, must-have results, conflict status, decision owner and approvals outstanding.
2. **Requirements and must-haves** — each test, evidence and PASS/FAIL/UNKNOWN.
3. **TCO** — assumptions, year-by-year table, horizon total, exit cost, total including exit, coverage and unknowns.
4. **Scorecard** — weights, scores, evidence ids, rationale, weighted score, coverage and provisional flag.
5. **Risk register** — risk, likelihood, impact, evidence, mitigation, owner role and residual risk.
6. **Conflict-of-interest record** — declarations, materiality, effect and independent-review requirement.
7. **Evidence ledger** — id, claim, source, level, date and what it does not prove.
8. **Negotiation plan** — priority terms, target, fallback and rationale; no invented benchmark.
9. **Open questions** — the exact fact needed, who can supply it and how it changes the decision.
10. **Claim boundary** — no approval, purchase, payment, signature, vendor contact or verified performance claim.

If a section cannot be completed, keep it and write **UNKNOWN** or **not supplied**. Do not omit it.

## Quality checks before returning

- Every must-have has a test and a PASS/FAIL/UNKNOWN result; no must-have is averaged into the score.
- The TCO includes implementation, migration, support, escalation, add-ons and exit; unknowns are labeled; coverage is reported.
- The weighted score uses only scored criteria; the denominator and coverage are shown.
- No missing score is replaced with a middle value.
- Every material claim has an evidence level; vendor assertions are not presented as verified.
- Conflicts are declared, assessed and reflected in the recommendation.
- The recommendation is one of Proceed / Negotiate / Hold / Do not proceed, with conditions.
- No purchase, payment, signature, vendor contact, approval or contract action is claimed.
- Currency, tax treatment and FX date are explicit.
- The output contains no invented benchmark, discount, certification or reference.

## Scope and limitations

- Works only from supplied documents and data; it does not query procurement, finance, legal, security, CRM or vendor systems.
- Does not approve spend, issue a purchase order, pay an invoice, sign or terminate a contract, contact a vendor or change a procurement record.
- Does not validate a security certification, audit opinion, reference or financial statement; it records the evidence level and the gap.
- The weighted score is a structured judgment, not an objective measurement. Different evidence coverage changes the result.
- TCO is only as complete as the supplied costs; unknown costs make it provisional.
- Conflict handling depends on honest declaration; the guide cannot detect an undisclosed interest.
- Synthetic examples use invented vendors, prices and terms. No real proposal, contract or vendor performance data is included.
