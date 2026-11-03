---
name: ticket-triage
description: Triage an incoming support ticket from pasted or workspace text: categorize it, assess impact and urgency against a supplied SLA policy, assign a defensible P1-P4 priority with its clock, recommend a queue and flag duplicates, unknowns and escalation triggers. Guide-only; it does not open, edit, route or close tickets.
---

# Ticket Triage

## Floe guide adaptation (read first)

- Adapted for Floe from the Apache-2.0 upstream skill recorded in `references/PROVENANCE.md`. The category taxonomy, P1-P4 framework, routing rules, duplicate discipline and initial-response templates are retained; the live support-platform, knowledge-base and project-tracker lookups are removed.
- Bring the ticket text plus whatever context you have: received time, channel, plan tier, affected scope, workaround status, open-ticket list, known-issue list and the organization's SLA and routing policy. You can paste text or attach a workspace Markdown/CSV file. No support platform, CRM, email, knowledge base or project tracker is connected or implied.
- The output is a workspace triage note and a **draft** first response. The guide does not create, assign, tag, merge, close or reply to a ticket, and it does not contact the customer. A human agent owns the queue and sends any reply.
- This is an operational aid, not a security, legal, medical or financial determination. Security incidents, data-loss reports and regulated complaints must follow the organization's incident and compliance process; the guide only flags them and recommends a route.
- Repository attention and repository-wide commit activity are not evidence about this skill's content freshness. The upstream path history is recorded in `references/PROVENANCE.md`; no recent-content claim is made.

**Important**: Priority and SLA output is a recommendation based on the evidence supplied. A named human must confirm the priority, apply any account-specific contractual SLA and decide whether to escalate or notify.

## Input contract

Provide, or state that a value is missing:

| Input | Why it is needed |
| --- | --- |
| Ticket text, in the customer's words | The primary evidence; do not paraphrase away the exact symptom |
| Received timestamp and time zone | Anchors the SLA clock; without it the clock cannot be computed |
| Channel (email, chat, portal, phone note) | Sets response expectations and what "received" means |
| Customer or account reference, minimized | Distinguishes this report from another customer's report |
| Plan, contract tier and any contractual SLA | May override the default priority clock |
| Product area, version, environment and region | Narrows duplicate candidates and routing |
| Affected users and scope (one user, one team, one organization, many organizations) | The main input to impact |
| Business impact and time sensitivity in the customer's terms | Separates inconvenience from a blocked business process |
| Workaround status (available / not available / unknown) | Changes priority and the first response |
| Security, privacy or data-loss signals | Triggers a mandatory route and priority floor |
| Open-ticket list with id, symptom, status and affected count | Supports duplicate and pattern checks without a live search |
| Known-issue list with status, scope and workaround | Prevents rediscovering a documented issue |
| SLA policy: P1-P4 response, update and resolution targets | Converts priority into actual deadlines |
| Business-hours calendar, holidays and time zone, if the SLA uses business hours | Prevents inventing a calendar |
| Routing map: queue names and what each queue owns | Makes the recommendation actionable |
| Escalation rules: triggers, approvers and notification path | Keeps escalation inside real authority |
| Required output language and tone constraints | Keeps the draft usable without rewriting |

If an input is absent, write **UNKNOWN** in the output and say what changing it would change. Do not infer plan tier from domain name, urgency from exclamation marks, or impact from the customer's seniority. A customer's statement about the cause is a **claim**, not a verified root cause.

## Privacy and evidence rules

1. Use the minimum personal data needed. Replace names with a customer reference or initials, redact email addresses, phone numbers, access tokens, full card numbers, government identifiers, health information and any secret pasted into the ticket.
2. Quote only the fragment that carries the symptom (for example, the exact error text). Do not reproduce an entire email thread in the internal note.
3. Separate four evidence classes in your working notes:
   - **Observed**: supplied by a monitored system or a named human who checked it.
   - **Reported**: what the customer says happened.
   - **Inferred**: your hypothesis; label it and do not present it as fact.
   - **Unknown**: not supplied.
4. Never claim you searched a support platform, knowledge base, project tracker or CRM. Duplicate and known-issue checks use only the lists supplied in the input.
5. Never state that a ticket was created, routed, merged, escalated, closed or answered. The output is a recommendation and a draft.

## Step 1 — Normalize the ticket

Write a short evidence table before categorizing:

| Field | Value | Class |
| --- | --- | --- |
| Reported symptom | Exact observable behaviour or error | Reported / Observed |
| First seen | Timestamp and time zone, if supplied | Reported / Unknown |
| Scope | Users, organizations, regions, environments | Reported / Unknown |
| Business process affected | What the customer cannot do | Reported / Unknown |
| Workaround | Available / not available / unknown, with steps if supplied | Reported / Unknown |
| Claimed cause | What the customer believes caused it | Claim |
| Requested outcome | Fix, answer, refund, call, feature, explanation | Reported |
| Security / privacy / data-loss signal | Yes / no / unclear, with the exact words | Reported |
| Material unknowns | What could change category or priority | Unknown |

Then write a one-line issue summary that contains the symptom and scope, not the customer's theory: "Import jobs fail with HTTP 502 for three scheduled feeds in the EU region", not "customer says the vendor broke the API".

## Step 2 — Categorize by root-cause evidence

Assign one primary category and, only when useful, one secondary category.

| Category | Use when | Boundary rules |
| --- | --- | --- |
| **Security** | Unauthorized access, suspected breach, vulnerability report, data exposure, credential compromise, abuse | Security outranks every other category. Do not ask the reporter to send secrets or proof-of-exploit in the ticket; preserve what exists and route to the security process. |
| **Data** | Missing, corrupted, duplicated, mis-migrated or wrongly exported data | If the report also alleges data loss, treat the loss as Security until the security process rules it out. |
| **Bug** | The product behaves differently from its documented or reasonably expected behaviour | "It used to work and now does not" is a Bug. If a login failure is caused by a product defect, Bug outranks Account. |
| **Account** | Access, permissions, SSO configuration, user management, lockout where no product defect is evident | If the root cause is a defect, use Bug as primary and Account as secondary. |
| **Billing** | Charges, invoices, tax lines, plan changes, refunds, contract questions | A refund request is Billing even when the customer is angry. Never imply a refund was approved. |
| **Integration** | Third-party connection, webhook, OAuth callback, API authentication or sync failure | If the failure is inside the product's own connector code, Bug may be primary. |
| **Performance** | Latency, timeouts, throughput, availability or degradation without a known defect | If the service is fully down, use Bug or Security as appropriate; Performance is for degradation. |
| **How-to** | The customer needs guidance, configuration steps or documentation | A documented limitation is How-to only if the answer is genuinely "this is how it works"; otherwise use Bug or Feature request. |
| **Feature request** | The customer asks for a capability that does not exist | A defect that prevents an existing capability is not a feature request. If both are present, the defect is primary. |

Determination rules:

- Root cause drives the category, not the channel or the customer's emotion.
- A bug plus a feature request: Bug is primary.
- Security plus anything: Security is primary and gets the priority floor below.
- Unknown root cause with a production symptom: use the symptom category (Bug, Performance, Integration or Data), not "Other".
- One ticket may carry a secondary category; do not create a third.

## Step 3 — Assess impact and urgency

Score the two dimensions separately before choosing a priority.

### Impact

| Level | Evidence |
| --- | --- |
| **Critical** | Data loss, corruption or exposure; security incident in progress; production unavailable for all or most users of an organization or multiple organizations |
| **High** | A core workflow is blocked for multiple users or a key account, with no reasonable workaround |
| **Medium** | A feature is partly broken, or one user/small team is affected, with a workaround |
| **Low** | Cosmetic issue, general question, documentation gap, feature idea |

### Urgency

| Level | Evidence |
| --- | --- |
| **Immediate** | Active loss, active exposure, safety/regulatory deadline, or the customer cannot operate at all |
| **Time-sensitive** | A dated business event is blocked (payroll, month-end, launch, regulatory filing) |
| **Normal** | Work continues with inconvenience or a workaround |
| **Whenever** | No date-bound consequence is supplied |

**Do not use as impact evidence:** the customer's title, executive sponsorship, capitalized words, threat to churn, or the length of the message. Record those separately as **relationship/escalation signals**. They may change the communication path, not the technical severity. A calm report of data loss is still Critical; an angry report of a typo is still Low.

## Step 4 — Assign priority with an explicit decision order

Apply these gates in order and stop at the first one that matches:

1. **P1** — Active security incident, suspected breach, active data loss/exposure, or production unavailable for all or most users of an organization (or multiple organizations), with no workaround.
2. **P2** — Major feature or core workflow broken for multiple users or a key account, no reasonable workaround; or a production incident contained to one tenant with a workaround that still leaves the main process blocked.
3. **P3** — Feature partly broken, single user or small team, reasonable workaround available; or a time-sensitive how-to with a documented answer.
4. **P4** — Cosmetic issue, general question, feature request, or a documented simple solution.

Mandatory refinements:

- **Security floor:** any credible security or data-exposure signal is at least P1 until the security process classifies it. Do not downgrade because the reporter is unsure or because the claim is unverified.
- **Data-loss floor:** alleged loss or corruption is at least P2; active loss is P1.
- **Unknown material fact:** if an unknown could move the ticket from P2 to P1 (for example, whether other tenants are affected), mark the priority **P2 (provisional)** and state the exact question that would raise it. Do not silently choose the lower level.
- **VIP does not outrank impact:** an executive request for a cosmetic change is still P4; route it through the account/communication path and say so.
- **No downgrade for calm tone:** tone is not severity evidence.
- **Contractual SLA:** if the customer's contract supplies a shorter response target for a category, use the shorter target and say which policy controlled.

### Default SLA table (replace with the supplied policy)

| Priority | First response | Status updates | Resolution target |
| --- | --- | --- | --- |
| P1 | 1 hour | Every 2 hours until mitigated | Continuous work; no fixed resolution time |
| P2 | 4 hours | Every 4 hours | Same business day for active work |
| P3 | 1 business day | At each material change | 3 business days |
| P4 | 2 business days | On resolution or request | Normal backlog |

If the organization's policy differs, the supplied policy wins. If no policy is supplied, label the table as **default, unconfirmed** and do not present the deadlines as contractual.

## Step 5 — Compute the SLA clock

Show the arithmetic, not just the deadline.

1. Convert the received timestamp to a single time zone (UTC is preferred for the calculation).
2. Add the first-response target for the chosen priority.
3. If the policy uses business hours, apply the supplied business-hours calendar, time zone and holiday list. If any of those is missing, compute elapsed clock time and mark the business-hours deadline **UNKNOWN**; never invent a holiday calendar.
4. If the policy pauses the clock while waiting on the customer, state the pause start and the evidence for it. Do not pause the clock merely because a question was asked.
5. Report:
   - received at,
   - target duration,
   - computed first-response deadline,
   - whether the deadline has already passed at the triage time,
   - next update deadline,
   - the policy source (default or customer contract).

If the received timestamp is unknown, the clock is **UNKNOWN** and the first response should ask for it rather than inventing one.

## Step 6 — Check duplicates and known issues from supplied lists

Compare the new report with each supplied open ticket and known issue on four keys:

1. Same or near-identical symptom or exact error string.
2. Same product area, environment and region.
3. Overlapping time window.
4. Same or related customer/organization.

Classify each candidate:

- **Duplicate**: same symptom, same product area and same root-cause hypothesis, with enough evidence to treat them as one investigation. Link the new report to the existing one, add the new evidence and do **not** close or merge anything. If the new report adds affected users or a failed workaround, raise the pattern flag.
- **Related**: same product area or error family but a different symptom, scope or timeframe. Cross-reference it; do not call it a duplicate.
- **Pattern**: three or more independent reports of the same symptom in the supplied list, or a clear increase in affected users. Escalate the pattern even when each individual ticket is low priority; say how many records support the pattern.
- **Not a duplicate**: no supplied record matches. Absence of a match is not proof that no duplicate exists elsewhere.

Never claim to have searched beyond the supplied list. State "checked against the N open tickets and M known issues supplied" and list the ids.

## Step 7 — Recommend a route (do not route)

Use the supplied routing map first. If none is supplied, use the generic mapping below and mark it **generic, unconfirmed**.

| Route | Use for |
| --- | --- |
| **Security / incident response** | Any security, privacy or data-exposure signal; follow the organization's incident process |
| **Tier 1 frontline** | How-to, documented limitation, password/access basics, simple billing questions |
| **Tier 2 support** | Bugs needing reproduction, complex configuration, integration troubleshooting, account/permission investigation |
| **Engineering** | Confirmed or strongly suspected product defect, infrastructure fault, performance regression |
| **Product** | Feature requests with evidence of demand, workflow gaps, design decisions |
| **Billing / finance** | Refund requests, invoice disputes, contract and tax questions; approval stays with finance |
| **Account / success** | Relationship risk, renewal risk, executive communication, adoption help |

Routing rules:

- The route is a **recommendation**. Do not say "routed", "assigned", "escalated" or "notified".
- Do not name an individual unless the routing map supplies that person's role and the policy says to name them. Prefer a queue.
- Security always goes to the security process first, even if engineering also needs to fix the defect.
- If the ticket spans two queues, name the primary queue and the consulting queue; do not create two owners.
- If the routing map is absent or ambiguous, say which decision the human must make.

## Step 8 — Draft the first response (not sent)

The draft must:

- acknowledge the specific impact in the customer's terms;
- state only what is **Observed** or **Reported**; attribute claims ("you reported that...");
- give the verified workaround, if one exists, with the caveat that it is a workaround;
- avoid a root-cause claim, a fix ETA, a refund/credit promise or a roadmap commitment unless the input supplies that exact approved statement;
- ask only the questions that materially change triage, and explain why each is needed;
- give the next update time computed from the SLA, with time zone;
- use the customer's language and avoid internal queue names, stack traces and ticket ids that mean nothing to them;
- end with a clear owner of the next action ("our support team will...") without naming a person who has not been assigned.

Label it exactly **Draft — not sent**. If the customer asked for something the guide cannot authorize (refund, exception, legal commitment), say that it will be reviewed by the responsible team and give a date by which the sender will confirm the outcome; do not imply the outcome.

## Floe output contract

A synthetic example is in [`assets/examples/input.md`](assets/examples/input.md), its machine-readable facts are in [`assets/examples/figures.json`](assets/examples/figures.json), and the expected output shape is in [`assets/examples/expected-output.md`](assets/examples/expected-output.md). They are synthetic examples, not executed results.

Produce these sections in order:

1. **Triage summary** — one-line issue summary; primary/secondary category; priority with **confirmed** or **provisional**; the gate that decided it; confidence and the fact that would change it.
2. **Evidence table** — observed, reported, inferred and unknown, with the minimum necessary personal data.
3. **Impact and urgency** — the two assessments separately, including the scope, workaround and time sensitivity actually supplied.
4. **SLA clock** — received time, target, deadline arithmetic, next update, policy source, and whether the first-response deadline has passed.
5. **Duplicate and known-issue check** — records compared, classification per candidate, pattern count, and what was not checked.
6. **Routing recommendation** — primary queue, consulting queue if any, why, and what the human must confirm.
7. **Draft first response** — labeled **Draft — not sent**.
8. **Internal notes** — reproduction hints, what has already been ruled out, escalation triggers, PII handling, and the open questions.
9. **Escalation flags** — each trigger with the evidence and the recommended notification path; distinguish priority change from communication escalation.
10. **Claim boundary** — what this triage does not prove, and what a human must verify before acting.

If a section cannot be completed from the input, write the section with **UNKNOWN** and the missing input. Do not omit the section.

## Escalation triggers

Flag, with evidence, when any of these is true:

- the first-response or next-update deadline has passed;
- the customer has waited longer than the supplied SLA;
- three or more independent reports match the same symptom;
- a workaround that previously worked has stopped working;
- the scope expands (more users, regions, organizations or data);
- a security, privacy or data-loss signal is present;
- a regulatory, legal, safety or contractual deadline is named;
- the customer explicitly asks for a manager, executive, legal review or regulator;
- a public status page, press inquiry or social post is mentioned.

For each flag, state whether it changes **priority**, **route**, **communication** or only **record-keeping**. Do not raise priority solely because the customer is upset or senior; raise it only when an impact/urgency criterion is met. An executive mention can still require a communication path even when technical priority stays P4.

## Quality checks before returning

- The category follows the root-cause rules; security/data-loss floors were applied.
- The priority follows the gate order; any provisional label names the fact that would change it.
- The SLA arithmetic is internally consistent and the policy source is named.
- Every duplicate/pattern claim cites a supplied record; no live lookup is implied.
- The route is phrased as a recommendation, and no ticket action is claimed.
- The draft response contains no unapproved ETA, cause, refund, credit, legal or roadmap commitment.
- Personal data is minimized and secret material is absent.
- Unknowns are visible rather than filled with plausible guesses.

## Scope and limitations

- Works only from user-supplied text and lists; it does not connect to a support platform, CRM, knowledge base, email, chat, project tracker or status page.
- Does not create, assign, tag, merge, close, reply to or escalate a ticket, and does not notify anyone.
- Does not determine root cause, contractual liability, refund eligibility, security severity or legal obligations.
- Business-hours deadlines require a supplied calendar, time zone and holiday list; without them only elapsed clock time is computed.
- The default SLA table is illustrative, not a contractual commitment.
- Duplicate detection is limited to the records supplied; absence of a match is not proof of uniqueness.
- Synthetic examples use invented customers, systems and timestamps. No real ticket, account or personal data is included.
