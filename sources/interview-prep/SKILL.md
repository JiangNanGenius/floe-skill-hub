---
name: interview-prep
description: Build a structured, job-related interview plan with competencies, behavioral and situational questions, anchored scorecards and a bias-aware debrief. Guide-only; no hiring decision, no ATS connection and not legal advice.
---

# Interview Prep

## Floe guide adaptation (read first)

- Adapted for Floe from the Apache-2.0 upstream skill recorded in `references/PROVENANCE.md`. The upstream source is brief: it supplies the five design principles, the list of interview-plan components and the expected output kit. Floe adds the detailed workflow, question-bank structure, scorecard anchors, debrief method and bias safeguards; those additions are marked as adaptation in the provenance record.
- Bring the role description, level, must-have requirements, competencies, interview format, panel and time budget. No ATS, HRIS, calendar, email or video-interview connection is used or implied.
- The output is a workspace document: a structured interview kit, scorecard and debrief template. The guide does not screen candidates, schedule interviews, contact anyone, make a hiring decision or assess a real person unless the user supplies a real, authorized interview record.
- This is an interview-design aid, not legal advice and not a hiring decision. The hiring manager and the organization's authorized decision-makers own the decision; local employment law, accommodations and record-keeping rules apply.

Create structured interview plans to evaluate candidates consistently and fairly.

## Input contract

| Input | Required | Notes |
| --- | --- | --- |
| Role title, level and team | Yes | Keep the plan job-related |
| Role description and must-have requirements | Yes | Separate must-haves from nice-to-haves |
| 4-6 competencies | Yes | Or derive a proposed set from the role description and mark it as a proposal |
| Interview format and time | Yes | Number of stages, minutes per interview, panel size |
| Panel and roles | Yes | Who covers which competency; avoid asking the same thing twice |
| Scoring scale and decision rule | Yes | For example, 1-4 anchored scale and a must-have gate |
| Accommodation needs | If known | The plan must not assume a candidate's needs |
| Local legal or policy constraints | If applicable | Do not invent them |
| Candidate information | Only if authorized | No names or personal data in the plan template |

If the role description or formal evaluation criteria are missing, the guide can draft a plan from a supplied competency list but must mark the job-relatedness as unverified and list the missing fields as unknown. Do not invent requirements, weights or must-haves.

## Interview design principles

1. **Structured:** the same core questions and scoring anchors for every candidate for the role.
2. **Competency-based:** map every question to a specific skill or behaviour required by the role.
3. **Evidence-based:** use behavioural and situational questions, and record what the candidate actually said.
4. **Multiple perspectives:** a panel reduces individual bias only when members score independently before discussion.
5. **Scored:** use an anchored rubric, not gut feeling or "culture fit".

Structured interviews improve consistency; they do not by themselves prove a candidate's ability or eliminate bias. Treat the interview as one source of evidence among work samples, references (where lawful) and other job-related assessments.

## Interview plan components

### 1. Role competencies

Define 4-6 competencies that are clearly required by the role. For each, state:

- The competency name and a one-sentence definition.
- Why it is required (link to a role responsibility).
- What distinguishes strong from weak evidence.
- Weight, if the organization uses a weighted score. Weights must sum to 100%.

Example competency set for a senior individual-contributor analytics role:

| Competency | Weight | Why it matters |
| --- | ---: | --- |
| SQL and data modelling | 30% | The role owns analysis on production data |
| Experimentation and statistics | 25% | The role designs and interprets tests |
| Stakeholder communication | 20% | The role presents decisions to non-specialists |
| Data pipeline reliability | 15% | The role is accountable for trustworthy inputs |
| Business judgement | 10% | The role prioritizes among competing questions |

Do not copy this set to a different role without checking the role description.

### 2. Must-haves and gates

Separate:

- **Must-have:** a requirement without which the candidate cannot perform the role (for example, a required licence or a non-negotiable technical skill). A failed must-have is a gate, not a low score to be averaged away.
- **Nice-to-have:** differentiates candidates but is not disqualifying.

The decision rule must say how a must-have is assessed (evidence required, who assesses it) and what happens if the evidence is incomplete. "Not assessed" is not the same as "failed".

### 3. Question bank

For each competency, prepare:

- 2-3 behavioural questions ("Tell me about a time...").
- 1-2 situational questions ("How would you approach...").
- Follow-up probes.
- What strong, adequate and weak evidence looks like.

Question rules:

- Ask about past behaviour or a realistic scenario, not about protected characteristics, family plans, health, religion, age, nationality, disability or other non-job-related matters.
- Keep the same core questions for all candidates; follow-ups may differ based on the candidate's answers.
- Do not ask a candidate to perform unpaid work that the organization would otherwise pay for, unless the organization has an approved, lawful work-sample policy.
- Do not ask for confidential information from a current employer.
- Give the candidate the structure and time to answer; do not turn the interview into a trivia quiz.

#### Example question set (illustrative, for the analytics role above)

| Competency | Question | Probe | Strong evidence includes |
| --- | --- | --- | --- |
| SQL and data modelling | "Describe a complex data model or query you designed. What problem did it solve?" | "How did you test correctness and performance?" | Requirements, schema choices, join/grain reasoning, tests, measured performance, trade-offs |
| Experimentation and statistics | "Tell me about an experiment you designed or analysed." | "How did you choose the sample size and interpret a non-significant result?" | Hypothesis, power/sample-size reasoning, guardrails, uncertainty, decision taken |
| Stakeholder communication | "Tell me about a time you had to explain a technical finding to a non-technical decision-maker." | "What did the audience do differently?" | Audience analysis, plain-language explanation, decision impact, handling challenge |
| Data pipeline reliability | "Describe an incident where data was late or wrong." | "How did you detect it and prevent recurrence?" | Detection, blast-radius assessment, root cause, monitoring, ownership |
| Business judgement | "How do you decide which analysis questions to prioritize?" | "Tell me about a time you stopped an analysis." | Criteria, cost/benefit, stakeholder input, evidence of saying no |

The expected-output fixture adapts this set to a synthetic candidate panel; it is not a real candidate assessment.

### 4. Scorecard

Use a small anchored scale, for example 1-4:

| Score | Anchor | What it means |
| ---: | --- | --- |
| 1 | No evidence / contrary evidence | The candidate did not demonstrate the competency, or the evidence contradicts it |
| 2 | Partial | Some relevant evidence, but gaps in depth, ownership or outcome |
| 3 | Meets | Clear, specific, job-related evidence with a credible outcome |
| 4 | Strong | Specific evidence of scope, judgement and impact beyond the minimum, with the candidate's own contribution clear |

Rules:

- Score each competency only after the interview, from written evidence notes.
- Require at least one quoted or paraphrased evidence note per score.
- Do not score a competency that was not assessed; mark it "not assessed".
- Do not convert a "not assessed" into a 1.
- Keep the scale consistent across the panel; calibrate anchors before the first interview.
- A score is not a hiring decision and not a probability of success.

### 5. Panel assignment

Assign each competency to a named interviewer role so every competency has a primary assessor and no competency is missed. Avoid:

- The same interviewer covering every competency while others only "chat".
- Two interviewers asking the same question in back-to-back sessions.
- A panel member with a conflict of interest or a prior relationship that was not disclosed under policy.

Diverse panels can add perspective, but diversity alone does not make a process unbiased. Independent scoring and job-related criteria matter more than the panel's composition.

### 6. Debrief and decision

The debrief is a structured evidence review, not a consensus meeting where the loudest voice wins.

1. Each interviewer records scores and evidence **before** the debrief.
2. The facilitator collects the scorecards.
3. For each competency, the primary assessor reads the evidence and score; others add evidence, not pressure to match.
4. Discuss discrepancies by returning to the evidence: what did the candidate actually say or do?
5. Re-score only if new evidence is presented; record the reason.
6. Check the must-have gates separately.
7. Record the panel's recommendation and the open questions.
8. The hiring manager and authorized decision-makers decide, subject to the organization's policy and local law.

Do not decide by averaging away a failed must-have, by "gut feel", or by comparing candidates on attributes unrelated to the role.

## Bias and fairness safeguards

- **Job-relatedness:** every competency and question must trace to a role requirement. Remove questions that do not.
- **Consistent core questions:** ask the same core questions to every candidate for the role; document any deviation.
- **Independent scoring:** score before discussion. Group discussion before scoring increases conformity.
- **Evidence, not impressions:** write down what the candidate said. "Great culture fit" is not evidence; "described how they resolved a conflict with a peer by..." is.
- **Avoid proxy attributes:** do not score accent, likeability, "executive presence", school prestige or hobbies unless they are genuinely required by the role and lawful to assess.
- **Protected characteristics:** do not ask about or record age, gender, race, ethnicity, religion, disability, health, pregnancy or family plans, sexual orientation, national origin or other protected traits. If the candidate volunteers personal information, do not use it in scoring.
- **Accommodation:** if a candidate requests an accommodation, route it to the organization's process; do not ask about disability or health. Adjust the format where required.
- **Language and clarity:** use plain language; allow interpretation or extra time where the organization's process requires it.
- **Recency and halo effects:** assess the whole evidence set, not only the last answer; score competencies separately before forming an overall impression.
- **Similarity bias:** be cautious when a candidate reminds the panel of a previous successful hire; that is not job evidence.
- **Recordkeeping:** retain notes, scores and the decision rationale under the organization's retention and privacy policy; do not retain more personal data than necessary.
- **No automated decision:** this guide does not rank, reject or advance a real candidate. Any automated screening must be separately reviewed for legality, validity and bias.

## Scoring method

If the organization uses weights:

1. Score each competency on the 1-4 scale.
2. Compute the weighted score: sum(weight × score) for assessed competencies.
3. If a competency is not assessed, renormalize over the assessed weights **or** mark the result incomplete; do not treat it as zero. State which method was used.
4. Report the weighted score and the raw scores; do not hide a low score behind an average.
5. Apply must-have gates separately from the weighted score.
6. Never report a probability of hire or a "pass" that the organization's process does not define.

Example: weights 30/25/20/15/10 and scores 3/3/4/3/3 give 0.30×3 + 0.25×3 + 0.20×4 + 0.15×3 + 0.10×3 = 3.20 on the 1-4 scale. The decimal is a weighted average, not a percentage and not a hiring probability.

## Floe output contract

A synthetic input is in [`assets/examples/input.md`](assets/examples/input.md), its machine-readable scoring data is in [`assets/examples/figures.json`](assets/examples/figures.json), and the expected output shape is in [`assets/examples/expected-output.md`](assets/examples/expected-output.md); all are test fixtures, not executed results and not real candidate assessments.

1. State the role, level, interview format, panel roles and time budget.
2. List 4-6 competencies with definitions, weights that sum to 100%, and the role requirement each supports.
3. Separate must-haves from nice-to-haves and define the gate.
4. Provide behavioural and situational questions with probes and evidence anchors for each competency.
5. Provide the anchored scorecard and the debrief steps.
6. List the bias safeguards actually built into the plan, not generic aspirations.
7. Compute any weighted score transparently, with the formula, assessed weights and incomplete cases.
8. Record the decision as a recommendation for the authorized humans; never state that a candidate is hired, rejected, qualified or "a fit".
9. Note the local-law, accommodation and record-keeping questions the organization must resolve.

## Scope and limitations

- Works only from supplied role and process information; it does not access an ATS, calendar, email, video platform or candidate records.
- Does not conduct interviews, contact candidates, schedule anything or make a hiring decision.
- Does not provide legal advice on employment law, accommodations, background checks, work authorization or record retention.
- Does not validate psychometric properties or predict job performance.
- If the role requirements are vague, the plan is a proposal and must be reviewed by the hiring manager before use.
