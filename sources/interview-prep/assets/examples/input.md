# Synthetic interview-prep input

> Synthetic fixture. Company, role, panel and candidates are invented for acceptance testing. Not a real candidate assessment and not a hiring decision.

## Request

Build a structured interview kit for a **Senior Data Analyst (synthetic)** role at **Meridian Retail Group (synthetic)**. The format is two 45-minute structured interviews plus a take-home work sample. The panel roles are the hiring manager, a senior analyst and a data engineer.

The organization uses a 1-4 anchored scorecard and this decision rule: **weighted average at least 3.0 AND all must-haves pass**. The output is a recommendation to the hiring manager, not a hiring decision.

## Competencies and weights

| Competency | Weight | Role link |
| --- | ---: | --- |
| SQL and data modelling | 30% | Owns analysis on production data |
| Experimentation and statistics | 25% | Designs and interprets tests |
| Stakeholder communication | 20% | Presents decisions to non-specialists |
| Data pipeline reliability | 15% | Accountable for trustworthy inputs |
| Business judgement | 10% | Prioritizes among competing questions |

## Must-haves

| ID | Must-have | Assessed by | A | B | C |
| --- | --- | --- | --- | --- | --- |
| M1 | Work sample: correct SQL join and grain | Senior analyst | Pass | Pass | Fail |
| M2 | Work sample: reproducible analysis notes | Data engineer | Pass | Pass | Pass |

A failed must-have is a gate, not a low score to be averaged away.

## Candidate scorecards

Scores are on the anchored 1-4 scale. Each score should have at least one specific evidence note.

| Competency | Candidate A | Candidate B | Candidate C |
| --- | ---: | ---: | ---: |
| SQL and data modelling | 3 | 4 | 2 |
| Experimentation and statistics | 3 | 2 | 4 |
| Stakeholder communication | 4 | 3 | 3 |
| Data pipeline reliability | 3 | 4 | 2 |
| Business judgement | 3 | 2 | 4 |
| Evidence notes present | 5 of 5 | 4 of 5 | 5 of 5 |

Candidate B is marked **provisional**: the pipeline score of 4 is supported only by a description of a monitoring dashboard, not by an incident-ownership example.

## Process record

- The same core question set was used for all three candidates: the same behavioural and situational questions for each of the five competencies, with follow-up probes that differed based on answers.
- Interviewers recorded independent scores before the debrief.
- No protected characteristics were collected in the scorecard fields.
- Candidate B requested extra time for the work sample; it was granted under the organization's process.
- **Incident 1:** Panel member 2 asked Candidate A whether they planned to have children soon.
- **Incident 2:** Candidate B's pipeline score lacks the required evidence note.

## Constraints

- Do not record, repeat or use the answer to the family-plans question in scoring.
- Do not treat a "not assessed" competency as zero.
- Do not state that any candidate is hired, rejected or "a fit".
- Flag the incidents and the decisions that the organization must take.
