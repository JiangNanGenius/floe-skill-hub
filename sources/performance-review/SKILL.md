---
name: performance-review
description: Structure a performance-review cycle with self-assessment, evidence-based manager review, calibration prep and development plans. Guide-only; no HRIS connection, no rating or pay decision and not legal advice.
---

# Performance Review

## Floe guide adaptation (read first)

- Adapted for Floe from the Apache-2.0 upstream skill recorded in `references/PROVENANCE.md`; the self-assessment, manager-review and calibration templates, the feedback tips and the rating-distribution discussion are retained.
- Bring the role, review period, rating framework, goals and evidence, plus team-level rating proposals if calibration is requested. No HRIS, project tracker, compensation tool or email connection is used or implied.
- The output is a workspace document: review templates, a calibration pack, development plans and a review-quality check. It is not a rating decision, a pay decision, a promotion decision or legal advice.
- Ratings, promotion, pay and employment decisions belong to the authorized managers, HR and compensation owners and are subject to the organization's policy and local law. This guide prepares evidence and questions; it does not decide, approve or communicate any outcome.

Generate performance review templates and help structure feedback.

## Input contract

| Input | Required | Notes |
| --- | --- | --- |
| Employee role, level and review period | Yes | Use role identifiers, not unnecessary personal data |
| Rating framework and scale | Yes | Do not invent a scale |
| Goals and success measures | Yes | Or mark as not supplied |
| Evidence of outcomes and behaviours | Yes | Specific examples, dates, results, stakeholders |
| Feedback from others | If used | Attribute only where the organization permits |
| Team calibration data | For calibration | Proposed ratings, roles, levels; no protected attributes |
| Promotion or compensation process | If applicable | State the authorized process; do not decide |
| Policy reference distribution | Optional | A reference, not a quota |
| Accommodation, leave or role-change context | If relevant and lawful to record | Do not infer or request health information |

If evidence is thin, the correct output is a review marked "insufficient evidence", not a rating invented to fill the template.

## Modes

The guide supports three modes. Ask which one is needed if it is not stated.

1. **Self-assessment:** a template and prompts for the employee's own evidence.
2. **Manager review:** a structured draft for a specific employee, based on supplied evidence.
3. **Calibration:** a team-level pack for comparing proposed ratings against the framework and the evidence.

The guide never sends a review to an employee, submits a rating, or triggers a pay or promotion action.

## Output — self-assessment template

```markdown
## Self-assessment: [review period]

### Key accomplishments
[List 3-5 accomplishments. For each: situation, your contribution, the impact, and the evidence.]

1. **[Accomplishment]**
   - Situation: [context]
   - Contribution: [what you did]
   - Impact: [measurable result]
   - Evidence: [metric, document, stakeholder confirmation]

### Goals review
| Goal | Status | Evidence |
| --- | --- | --- |
| [Goal from last period] | Met / Exceeded / Not met / Changed | [How you know] |

### Growth areas
[Where did you grow? New skills, expanded scope, leadership moments.]

### Challenges
[What was hard? What would you do differently?]

### Goals for next period
1. [Goal - specific and measurable]
2. [Goal]
3. [Goal]

### Support requested
[How can your manager or the organization support you? Keep it job-related.]
```

## Output — manager review template

```markdown
## Performance review: [employee role/identifier]
**Period:** [date range] | **Manager:** [role or name as permitted]

### Overall assessment
[2-3 sentences summarising the evidence. Use the organization's rating labels only if they are supplied.]

### Rating proposal
[Rating label from the supplied framework, or "not proposed - insufficient evidence".]

### Key strengths
- [Strength with a specific example and outcome]
- [Strength with a specific example and outcome]

### Areas for development
- [Area with specific, actionable guidance and a suggested support]
- [Area with specific, actionable guidance and a suggested support]

### Goal achievement
| Goal | Rating | Evidence | Comment |
| --- | --- | --- | --- |
| [Goal] | [rating or "not assessed"] | [specific observation] | [context] |

### Impact and contributions
[Describe the biggest contributions and their impact on the team or organization, with evidence.]

### Development plan
| Skill | Current | Target | Actions | Support | Review date |
| --- | --- | --- | --- | --- | --- |
| [Skill] | [level] | [level] | [how to get there] | [manager/org support] | [date] |

### Compensation input (optional)
[If the organization's process asks managers for an input, state "input to the authorized compensation process" and do not state a final pay outcome. Do not invent budget, equity or market data.]
```

The manager template is a draft. The manager owns the conversation and the final wording; the authorized rating owner approves the rating under the organization's process.

## Output — calibration template

```markdown
## Calibration prep: [review cycle]
**Manager:** [role] | **Team:** [team] | **Period:** [date range]

### Team overview
| Employee (role/identifier) | Role | Level | Tenure band | Proposed rating | Evidence strength | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| [identifier] | [role] | [level] | [band] | [rating] | Strong / Adequate / Thin | [context] |

### Rating distribution
| Rating | Count | % of team | Policy reference (if any) |
| --- | ---: | ---: | --- |
| Exceeds expectations | [X] | [X]% | [reference band, if supplied] |
| Meets expectations | [X] | [X]% | [reference band, if supplied] |
| Below expectations | [X] | [X]% | [reference band, if supplied] |
| **Total** | **[X]** | **100%** |  |

A policy reference band is a comparison point, not a quota. Do not force a distribution the policy does not require.

### Calibration discussion points
1. **[Employee]** - [why the rating may need discussion: borderline, first review at level, recent role change, thin evidence]
2. **[Employee]** - [discussion point]

### Promotion candidates
| Employee | Current level | Proposed level | Evidence of next-level scope | Open questions |
| --- | --- | --- | --- | --- |
| [identifier] | [current] | [proposed] | [specific evidence] | [what is missing] |

### Compensation actions
[Do not decide pay here. List the inputs the authorized compensation process needs and the questions it must answer.]

### Manager notes
[Context the calibration group should know: team changes, org shifts, project impacts, leave or role changes where lawful and relevant.]
```

## Evidence and feedback method

Use specific, job-related evidence. A useful structure is **situation - behaviour - impact**:

- **Situation:** when and where, without unnecessary personal detail.
- **Behaviour:** what the person actually did, observable and job-related.
- **Impact:** the result for the team, customer, project or organization.

Examples:

- Weak: "Great attitude and very helpful."
- Stronger: "During the October migration (situation), you documented the rollback steps and ran the rehearsal with two engineers (behaviour), which cut the cutover window from four hours to ninety minutes (impact)."

Avoid:

- Personality labels ("careless", "not strategic") without observable behaviour.
- Vague praise ("great job") without evidence.
- Feedback based only on the last few weeks (recency).
- One incident generalised to the whole year (halo or horns).
- Comparisons to other employees instead of the role expectations.
- Protected characteristics, health, family plans, age, religion, disability or other non-job-related matters.

## Rating and calibration integrity

### Evidence quality

For each proposed rating, record:

- The goal or expectation.
- The evidence (result, date, source).
- The employee's contribution versus the team's.
- Whether the evidence is sufficient. "Thin" is a legitimate finding.

A rating without evidence is not made more reliable by being repeated in calibration.

### Distribution checks

If the organization supplies a reference distribution:

- Compute the actual counts and percentages.
- Compare, but do not treat the reference as a quota unless policy says it is.
- Discuss clusters: a team where everyone "exceeds" may indicate lenient anchors, unclear expectations or genuinely strong performance. Investigate the cause.
- Discuss a single "below" rating with extra care: is the evidence specific, was the employee given feedback and support, and is the process consistent?

### Common rating biases

| Bias | What it looks like | Control |
| --- | --- | --- |
| Recency | Only the last month is considered | Require evidence across the whole period |
| Halo / horns | One strong or weak trait colours everything | Rate each expectation separately |
| Similarity | Preference for people like the manager | Use job-related criteria and calibration review |
| Proximity | Remote or less-visible work is undervalued | Require output evidence, not visibility |
| Leniency / severity | Everyone is rated high or low | Calibrate anchors and compare evidence |
| Central tendency | Everyone is rated "meets" | Distinguish evidence levels explicitly |
| Confirmation bias | Only evidence matching an early impression is collected | Ask for disconfirming evidence |
| Idiosyncratic rater | One manager's scale differs from others | Calibrate with examples, not just labels |

### Protected characteristics and privacy

- Do not collect or discuss protected characteristics in a review or calibration pack.
- Do not use leave, accommodation, part-time status or caring responsibilities as a negative performance signal.
- If the employee volunteers personal information, do not record it unless the organization's policy requires a lawful, job-related record.
- Keep review records under the organization's retention and access policy.
- Local law may give employees rights to access, correct or contest review records; route those requests to the appropriate owner.

## Development planning

A development plan should be:

- **Specific:** a skill or behaviour, not "improve communication".
- **Actionable:** a concrete action the employee can take.
- **Supported:** what the manager or organization will provide.
- **Measured:** how progress will be observed.
- **Time-bound:** a review date.

Example: "Present the monthly analysis to the commercial team twice in Q1, with the manager reviewing the first deck; success is a decision-ready narrative and clear questions." This is more useful than "build executive presence".

## Floe output contract

A synthetic input is in [`assets/examples/input.md`](assets/examples/input.md), its machine-readable calibration data is in [`assets/examples/figures.json`](assets/examples/figures.json), and the expected output shape is in [`assets/examples/expected-output.md`](assets/examples/expected-output.md); all are test fixtures, not executed results and not real employee reviews.

1. State the cycle, rating framework, team scope and the source of the evidence.
2. Produce the requested mode (self-assessment, manager review or calibration) without mixing in decisions the guide cannot make.
3. Require specific evidence for each rating, keep the provided evidence separate from the interpretation, and mark thin evidence and "not assessed" explicitly.
4. For calibration, compute counts and percentages, compare with any policy reference, and frame differences as discussion points, not violations.
5. Check for recency, halo, similarity, proximity, leniency/severity and confirmation bias; list the evidence gaps.
6. Provide development actions that are specific, supported and measurable.
7. State that ratings, promotion, pay and employment outcomes are decided by the authorized humans under policy and local law. Do not rank employees against each other beyond the defined rating framework or make unsupported comparative claims.
8. Never state that a rating, promotion, pay change or termination is approved, final or communicated.

## Scope and limitations

- Works only from supplied documents and figures; it does not access an HRIS, project tracker, compensation tool or email.
- Does not decide ratings, promotions, pay, performance-improvement plans or terminations.
- Does not provide legal advice on employment, privacy, accommodations or record retention.
- Does not validate the organization's rating framework or its compliance with local law.
- If the evidence is insufficient or the framework is unknown, the correct output is an incomplete review with open questions, not a confident rating.
