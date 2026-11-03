# Expected output — interview-prep synthetic fixture

> Expected output shape. Computed from the supplied synthetic scorecards; no model run, ATS or real candidate was involved. This is not a hiring decision and not legal advice.

## Interview kit

| Field | Value |
| --- | --- |
| Role | Senior Data Analyst (synthetic) |
| Company | Meridian Retail Group (synthetic) |
| Level | Senior individual contributor |
| Format | Two 45-minute structured interviews plus a take-home work sample |
| Panel | Hiring manager; senior analyst; data engineer |
| Scoring | Anchored 1-4 scale |
| Decision rule | Weighted average at least 3.0 AND all must-haves pass |
| Decision owner | Hiring manager and the organization's authorized decision-makers; this guide only prepares the evidence |
| Accommodation | Candidate B requested extra time for the work sample; granted under the organization's process |

## Competencies and panel assignment

| Competency | Weight | Role link | Primary assessor |
| --- | ---: | --- | --- |
| SQL and data modelling | 30% | Owns analysis on production data | Senior analyst |
| Experimentation and statistics | 25% | Designs and interprets tests | Senior analyst |
| Stakeholder communication | 20% | Presents decisions to non-specialists | Hiring manager |
| Data pipeline reliability | 15% | Accountable for trustworthy inputs | Data engineer |
| Business judgement | 10% | Prioritizes among competing questions | Hiring manager |
| **Total** | **100%** |  |  |

Every competency is assigned to a primary assessor; no competency is left to an unstructured conversation.

## Must-haves

| ID | Must-have | Evidence required | A | B | C |
| --- | --- | --- | --- | --- | --- |
| M1 | Work sample: correct SQL join and grain | Reviewed work sample with the join and grain explained | Pass | Pass | **Fail** |
| M2 | Work sample: reproducible analysis notes | Notes sufficient for another analyst to rerun | Pass | Pass | Pass |

A failed must-have is a gate. It is not averaged into the weighted score, and passing the other must-have does not offset it.

## Question bank

The same core questions are asked of every candidate. Probes may follow the candidate's answers.

| Competency | Behavioural questions | Situational question | Evidence to listen for |
| --- | --- | --- | --- |
| SQL and data modelling | 1. "Describe a complex data model or query you designed. What problem did it solve?" 2. "Tell me about a time you found a data-quality bug in your own analysis." | "You receive two tables with different grains and a request for a single metric. How do you proceed?" | Requirements, grain/join reasoning, correctness tests, performance, how the bug was found and fixed |
| Experimentation and statistics | 1. "Tell me about an experiment you designed or analysed." 2. "Describe a result that surprised you and how you investigated it." | "A test is underpowered but the business wants a decision. What do you do?" | Hypothesis, power/sample size, guardrails, uncertainty, decision framing, refusal to overclaim |
| Stakeholder communication | 1. "Tell me about explaining a technical finding to a non-technical decision-maker." 2. "Tell me about a time a stakeholder disagreed with your conclusion." | "You have five minutes with an executive who wants one number. How do you present the uncertainty?" | Audience, plain language, decision impact, handling challenge, honesty about limits |
| Data pipeline reliability | 1. "Describe an incident where data was late or wrong." 2. "Tell me about a monitoring or check you added after a failure." | "A daily table is two hours late and a dashboard is live. What do you do first?" | Detection, blast radius, root cause, ownership, prevention, communication |
| Business judgement | 1. "How do you decide which analysis questions to prioritize?" 2. "Tell me about an analysis you stopped." | "Two teams want conflicting metrics by Friday. How do you choose?" | Criteria, cost/benefit, stakeholder input, saying no, decision record |

Question rules for the plan: no questions about protected characteristics, family plans, health, disability, religion, age, nationality or other non-job-related matters. The process record shows one deviation, flagged below. The work sample is job-related and is reviewed under the organization's policy.

## Scorecard anchors

| Score | Anchor | Evidence standard |
| ---: | --- | --- |
| 1 | No evidence or contrary evidence | No job-related example, or the example contradicts the competency |
| 2 | Partial | Some relevant evidence, with gaps in depth, ownership or outcome |
| 3 | Meets | Clear, specific, job-related evidence with a credible outcome |
| 4 | Strong | Specific evidence of scope, judgement and impact beyond the minimum, with the candidate's own contribution clear |

A score requires at least one specific evidence note. A competency that was not assessed is "not assessed", not 1.

## Candidate scoring

| Candidate | SQL 30% | Stats 25% | Comms 20% | Pipeline 15% | Judgement 10% | Weighted average (1-4) | Must-haves | Outcome |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| A | 3 | 3 | 4 | 3 | 3 | **3.20** | Pass | Meets the stated bar; recommend to the next stage |
| B | 4 | 2 | 3 | 4 | 2 | **3.10 provisional** | Pass | Above the bar, but provisional; evidence gap must be resolved |
| C | 2 | 4 | 3 | 2 | 4 | **2.90** | **Fail (M1)** | Below the bar and the must-have gate; do not advance |

### Calculation

- A: 0.30×3 + 0.25×3 + 0.20×4 + 0.15×3 + 0.10×3 = 0.90 + 0.75 + 0.80 + 0.45 + 0.30 = **3.20**.
- B: 0.30×4 + 0.25×2 + 0.20×3 + 0.15×4 + 0.10×2 = 1.20 + 0.50 + 0.60 + 0.60 + 0.20 = **3.10**.
- C: 0.30×2 + 0.25×4 + 0.20×3 + 0.15×2 + 0.10×4 = 0.60 + 1.00 + 0.60 + 0.30 + 0.40 = **2.90**.
- Weights: 30 + 25 + 20 + 15 + 10 = **100%**.
- No competency was "not assessed" in this fixture, so no renormalization was needed. If one had been missing, the result would be marked incomplete or renormalized over the assessed weights, and the method would be stated.

### Sensitivity

B's pipeline score of 4 is not supported by an incident-ownership example; only a monitoring dashboard was described. If that score is re-scored to 3, B's weighted average becomes:

0.30×4 + 0.25×2 + 0.20×3 + 0.15×3 + 0.10×2 = 1.20 + 0.50 + 0.60 + 0.45 + 0.20 = **2.95**, below the 3.0 bar.

B's result must therefore be treated as **provisional**. The panel should either obtain the missing evidence and re-score, or record the score as 3 and treat B as below the bar. It must not present 3.10 as a settled result.

## Debrief record

1. Scorecards were collected before discussion.
2. For each competency, the primary assessor read the evidence; others added evidence only.
3. Discrepancies were resolved by returning to the notes. A re-score is permitted only when new evidence is recorded, with the reason.
4. Must-have gates were checked separately: A pass/pass; B pass/pass; C fail/pass.
5. Open items: B's pipeline evidence; the protected-characteristic incident; the organization's decision on next steps.
6. Recommendation recorded, not a decision.

## Bias and process findings

| Check | Result | Action |
| --- | --- | --- |
| Same core questions for all candidates | Pass | Keep the record of any deviation |
| Independent scoring before debrief | Pass | Keep the separate scorecards |
| Evidence note per score | Partial | B's pipeline score has no incident-ownership evidence; resolve before decision |
| No protected characteristics collected | Pass on the scorecard fields | The interview incident below still requires action |
| Protected-characteristic question | **Fail** | Panel member 2 asked Candidate A about family plans. Do not record or use the answer; escalate to the organization's HR/legal process and provide retraining. The organization must decide whether the process for that candidate is tainted. |
| Accommodation | Handled | B's extra-time request was granted under the organization's process; do not ask about disability or health |
| "Culture fit" or personality scoring | Not used | Keep competency-based evidence |
| Automated ranking or rejection | Not used | No automated decision is made by this guide |

The panel's composition is as supplied. This guide makes no claim that the panel's composition eliminates bias; independent scoring and job-related evidence are the controls that matter here.

## Recommendation

- **A:** meets the stated bar and all must-haves; recommend to the next stage. The hiring manager decides.
- **B:** 3.10 is provisional because one score lacks evidence. Resolve the evidence gap before relying on the result; if re-scored to 3, B is at 2.95 and below the bar. Do not advance on a provisional score without the panel's documented resolution.
- **C:** below the bar and fails must-have M1; do not advance. The reason is the job-related work sample, not any personal characteristic.

These are recommendations for the authorized humans. The guide does not hire, reject, rank or "clear" any candidate.

## Decisions the organization must make

1. How to handle the protected-characteristic question, including whether the candidate's process is affected and what remediation is required.
2. Whether to obtain more evidence for B or accept the re-score.
3. Whether the role's must-haves and weights are correct and consistently applied.
4. Whether the interview records, scores and decision rationale meet the organization's retention and privacy policy.
5. Whether local employment law, accommodation or works-council requirements impose additional steps.

## Adversarial check

The job description and formal evaluation criteria were not supplied. The weights and must-haves above come from the request; the role links are a proposal and must be verified against the actual job description. Do not invent missing requirements, must-haves or candidate facts. If a panel asks about protected characteristics, do not record or use the answer (see the incident above).

## Claim boundary

- Synthetic candidates and scores; no real person was assessed.
- No ATS, calendar, email, video platform or background-check system was used.
- No hiring, rejection, offer or "fit" decision is made.
- No legal advice on employment law, accommodations or record retention is provided.
