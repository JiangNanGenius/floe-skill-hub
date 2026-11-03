---
name: draft-response
description: Draft a customer-facing support response for an incident, escalation, bad-news update, billing question or declined request using only supplied facts and approved commitments. Guide-only; it never sends a reply, writes to a CRM or support tool, grants a refund or invents a cause, ETA or roadmap date.
---

# Customer Response Draft

## Floe guide adaptation (read first)

- Adapted for Floe from the Apache-2.0 upstream skill recorded in `references/PROVENANCE.md`. The situation templates, tone guidance, response structure and follow-up discipline are retained; the automatic email, chat, CRM, support-platform and knowledge-base research is removed.
- This is a **support-response** guide, not a general email-style or marketing-copy guide. It is built for a live customer issue where status, ownership, SLA, prior commitments and authorization boundaries matter.
- Bring the situation and the facts: what happened, what is verified, what the customer was previously told, what the sender is authorized to offer, the channel, the audience and the deadline. Paste text or attach workspace files. No mailbox, CRM, support platform, chat, calendar or knowledge base is connected or implied.
- The output is a **draft** plus internal notes. The guide never sends, schedules, queues, logs or records anything, and it never changes a CRM, ticket, account or billing state. A named human reviews and sends the message.
- Do not treat a customer's account of the cause, a vendor's assertion or an internal rumor as verified fact. Do not make a commitment that is not in the supplied commitment ledger.
- Repository attention and repository-wide commits are not evidence about this skill's content freshness. The upstream path history is in `references/PROVENANCE.md`; no recent-content claim is made.

**Important**: The draft is not legal, financial, security or contractual advice. Refunds, credits, contract exceptions, liability admissions and security disclosures require the organization's authorized approver. The guide cannot approve, promise or execute them. Nothing in this guide authorizes outbound sending or overrides the current Floe, user or organization communication policy; the draft is not a send permission.

## Input contract

Provide, or state that a value is missing:

| Input | Why it is needed |
| --- | --- |
| Situation type and one-line summary | Selects the structure and tone |
| Channel (email, ticket, chat, status update) | Sets length, formality and what a "reply" means |
| Recipient role and stakeholder level | Adjusts detail and decision framing |
| Relationship stage (new, established, escalated) | Adjusts warmth and context, not facts |
| Redacted thread excerpt or prior messages | Preserves continuity and avoids contradicting an earlier statement |
| Verified facts with source and timestamp | The only material that may be stated as fact |
| Customer claims and requested outcome | Must be attributed, not adopted |
| Current status and workaround, if verified | Sets expectations honestly |
| Prior commitments: who, what, when, and whether kept | Prevents silent contradiction and repeat promises |
| Approved next actions with owner and date | The only commitments the draft may make |
| Policy limits: what may be offered, what needs approval | Prevents unauthorized refunds, credits, exceptions and dates |
| Forbidden topics or wording | Legal, security, privacy or commercial constraints |
| Approval requirement and approver role | Decides which approvals or reviews apply before the sender may send; this guide never grants send permission |
| Desired outcome and relationship risk | Keeps the draft purposeful |
| Response deadline and SLA | Sets the next-update promise |
| Language, locale, date format and time zone | Prevents ambiguous dates |
| Length or formatting constraint | Keeps the draft usable in the channel |

If any input is missing, mark it **UNKNOWN** in the internal notes and avoid building a promise on it. Never infer authorization from the customer's request, the sender's seniority or the urgency of the situation.

## Privacy and evidence rules

1. Use the minimum personal data necessary. Do not repeat full names, email addresses, phone numbers, card numbers, government identifiers, health information, credentials, access tokens or another customer's data.
2. If the thread contains a secret, do not reproduce it. Say that the secret was removed and must be rotated through the proper channel.
3. Classify every sentence before drafting:
   - **Verified** — supplied with a source and timestamp.
   - **Customer claim** — what the customer says; attribute it.
   - **Internal claim** — supplied by a colleague but not verified; do not present it as fact.
   - **Policy** — a supplied rule that may be stated.
   - **Unknown** — not supplied; say so or omit.
   - **Not authorized** — supplied as prohibited; do not include it.
4. Do not claim a live lookup. If the input contains no prior thread, say the draft cannot reference prior messages.
5. Do not state or imply that a reply was sent, a ticket updated, a CRM note written, a call booked, a refund issued or an escalation performed. Those are actions for the human sender.

## Step 1 — Build the fact and commitment ledgers

Before writing prose, build two short tables.

### Fact ledger

| Statement | Class | Source / timestamp | May appear as fact? |
| --- | --- | --- | --- |
| Example: import failures began 22:10 UTC | Verified | Monitoring note, 06:40Z | Yes |
| Example: "your vendor broke the API" | Customer claim | Customer email | Only attributed |
| Example: "fix is nearly done" | Internal claim | Chat, no owner | No; mark unverified |
| Example: data loss | Unknown | Not supplied | No; say it is being checked |

### Commitment ledger

| Commitment | Approved by | Owner | Due | Evidence |
| --- | --- | --- | --- | --- |
| Next update by 14:00 UTC | Support policy | Sender | 2026-11-01T14:00Z | SLA table |
| Review credit request | Account lead | Sender to route | 2026-11-03 | Approved next action |
| Fix by Friday | — | — | — | **Not authorized; do not use** |

Rules:

- A **fact** may be stated only if it is Verified or Policy.
- A **customer claim** may be quoted or paraphrased with attribution ("you reported that...").
- A **commitment** may appear only if the ledger has an approver, an owner and a due date. If the date is not approved, write a process commitment ("I will confirm by...") instead of an outcome commitment ("it will be fixed by...").
- The model cannot perform actions. Never claim that the model or the draft sent, scheduled, escalated, refunded, fixed, updated or recorded anything. If the human sender already performed an action, the draft may say "our records show..." only when the input supplies the evidence; sending, CRM writes and ticket updates are always the sender's actions, not the guide's.
- Never invent a cause, an ETA, a roadmap quarter, a discount, a credit, a legal position or a security conclusion to make the message sound better.

## Step 2 — Choose the situation structure

| Situation | Tone | Must include | Must avoid |
| --- | --- | --- | --- |
| Product question | Helpful, direct | The answer, a documentation pointer if supplied, next step if unresolved | Guessing; a sales pitch |
| Bug or incident | Accountable, factual | Acknowledgment, verified status, impact, workaround, next update | Blame, unverified cause, invented ETA |
| Escalation | Composed, ownership-taking | Acknowledgment of impact, what is known, named accountable role, action plan, update cadence | Defensiveness, excuses, over-promising |
| Delay or bad news | Candid, respectful | The news early, reason if shareable, impact, alternatives, next step | Burying the news; false optimism |
| Won't-fix or decline | Direct, respectful | The decision, the honest reason if approved, alternatives, door for feedback | Dismissiveness; implying reconsideration |
| Billing or account | Precise, empathetic | What is verified, what is being reviewed, who decides, when the sender will confirm | Implying a refund/credit is approved |
| Security or privacy | Calm, controlled | Acknowledgment, immediate protective step, secure channel, no speculation | Confirming a breach; asking for secrets; naming other customers |
| Feature request | Appreciative, honest | That the request is recorded, the decision status, alternatives | A delivery date without approval |
| Good news | Warm, specific | The outcome, what it means for them, next step | Overclaiming; marketing language |
| Follow-up after silence | Brief, low-pressure | Context, the ask, an easy out | Guilt; repeated apology |

## Step 3 — Write the draft

Use this order unless the channel or culture requires a different one:

1. **Acknowledgment** (1-2 sentences): name the specific impact and the customer's situation. Do not open with "I hope this email finds you well" or a generic thank-you.
2. **What is known** (1-3 short paragraphs): verified status, scope, what is not known, and whether a workaround exists. Attribute claims. Do not explain internal architecture unless it changes what the customer must do.
3. **Action and ownership**: what will happen next, who owns it (role or team, not an invented name), and by when. If the action depends on another team, say so without blaming them.
4. **What the customer needs to do**: only the necessary steps, with a reason. Do not ask for secrets or unnecessary personal data.
5. **Next update**: a specific date and time with time zone, derived from the SLA or an approved commitment. If no date is approved, say when the sender will confirm the date.
6. **Close**: one short, warm sentence; no pressure and no excessive apology.

### Language rules

- Use active voice and plain words. "We will check" is better than "it will be investigated".
- Use the customer's terms for their product and process; avoid internal codenames and queue names.
- Use absolute dates and times with a time zone ("by 14:00 UTC on 1 November"), never "soon", "shortly" or "end of day" without a zone.
- Put the most important information first. Keep paragraphs to 2-4 sentences.
- Apologize once, specifically, for the impact; do not grovel or repeat the apology in every paragraph.
- Do not use exclamation marks, marketing superlatives or jargon such as "synergy", "leverage" or "circle back".
- Do not hide bad news in a long preamble. State it, then explain and offer a path.
- Use inclusive, neutral language; do not speculate about the recipient's identity, health, family or intentions.

### Channel and length

| Channel | Target |
| --- | --- |
| Chat / IM | 1-4 sentences; one action and one next step |
| Support ticket | 1-3 short paragraphs or a short structured block |
| Email | 3-5 short paragraphs; a scannable subject |
| Executive escalation | 2-4 paragraphs or a short brief; facts, impact, decision needed, date |
| Status/incident update | Timestamped facts, impact, workaround, next update; no blame |

If the supplied length limit conflicts with completeness, keep the facts and the next step; move detail to internal notes or an attachment the sender can choose to include.

## Step 4 — Run the commitment and privacy audit

Before presenting the draft, check every sentence:

- **Fact check:** every factual statement traces to the fact ledger. Customer claims are attributed. Unknowns are labeled.
- **Commitment check:** every promise traces to the commitment ledger with an approver, owner and date. No unauthorized ETA, refund, credit, exception, roadmap date, legal conclusion or security assurance.
- **Action check:** no sentence claims the model sent, scheduled, escalated, refunded, fixed, updated or recorded anything. Actions belong to the human sender and are phrased as what the sender will do.
- **Privacy check:** no unnecessary personal data, secret, credential, another customer's name, internal ID or confidential detail. Sensitive material goes through the approved secure channel, not the draft body.
- **Consistency check:** the draft does not contradict a prior commitment in the thread. If a prior commitment was missed, acknowledge it explicitly and give a new, approved update time.
- **Tone check:** the draft matches the situation and relationship without overpromising or blaming.
- **Channel check:** length and formatting fit the channel; the subject line is specific and contains no sensitive data.
- **Accessibility check:** short sentences, descriptive link text, no color-only meaning, no ALL CAPS, no unexplained abbreviations.

If any check fails, revise the draft rather than adding a disclaimer at the end.

## Step 5 — Prepare the internal notes

The internal notes are for the sender, not the customer:

- **Draft status:** `Draft — not sent`.
- **Why this approach:** the situation type, the chosen tone and the trade-off.
- **Facts used:** the verified statements and their sources.
- **Commitments used:** each promise and its approval.
- **Items to verify before sending:** every unresolved fact, date, entitlement or approval.
- **Risk:** legal, security, privacy, commercial or relationship exposure.
- **Approval required:** the role that must approve before sending, if any.
- **Sender actions required:** the actions the draft promises (route the credit request, book the call, rotate the key).
- **Follow-up:** the date to check for a reply or to send the next update.
- **What was deliberately omitted:** unauthorized offers, unverified causes, internal details.

Do not put internal notes in the customer body. Do not label the draft as approved or ready to send, and do not treat the absence of a required approval as permission to send.

## Floe output contract

A synthetic example is in [`assets/examples/input.md`](assets/examples/input.md), its machine-readable facts are in [`assets/examples/figures.json`](assets/examples/figures.json), and the expected output shape is in [`assets/examples/expected-output.md`](assets/examples/expected-output.md). They are synthetic examples, not executed results.

Produce these sections in order:

1. **Draft header** — `Draft — not sent`; to (role or minimized reference), subject/topic, channel, tone, requested send-by if supplied.
2. **Draft body** — the customer-facing text only.
3. **Fact ledger** — statement, class, source and whether it appears in the draft.
4. **Commitment ledger** — commitment, approver, owner, due date and where it appears.
5. **Pre-send checks** — fact, commitment, action, privacy, consistency, tone, channel and accessibility, each with pass/fail and the fix.
6. **Internal notes** — why this approach, what to verify, risk, approval, sender actions, follow-up, omissions.
7. **Escalation or approval note** — if the draft depends on an approval, the exact decision requested and the date needed; otherwise "none".
8. **Claim boundary** — what the draft does not establish and what the sender must confirm.

If a section cannot be completed, keep it and write **UNKNOWN** or **not supplied**. Do not omit the section.

## Approval and escalation boundaries

Escalate for approval before sending when the response would:

- offer or imply a refund, credit, discount, contract exception or waiver;
- admit liability, fault or a legal conclusion;
- disclose a security incident, personal-data breach or regulatory notification;
- commit to a product roadmap, delivery date or service level outside the contract;
- name another customer, reference or partner without consent;
- discuss litigation, a regulator, law enforcement or a subpoena;
- change account ownership, access or billing state.

The draft may prepare the request for the approver, but it must not present the unapproved outcome as decided. If the customer needs an immediate answer and approval is pending, say who is reviewing it and when the sender will confirm the decision.

## Quality checks before returning

- Every factual sentence is verifiable from the input; every claim is attributed.
- Every promise has an approver, owner and date; no unauthorized outcome appears.
- No action is claimed as performed by the model; no send, CRM write, ticket update or refund is implied.
- Prior commitments, including missed ones, are handled consistently.
- Personal data is minimized; secrets and other customers' data are absent.
- The next update is a specific date/time with a time zone.
- The tone matches the situation without blame, groveling or over-promising.
- The draft is clearly labeled as a draft and the internal notes are separate.

## Scope and limitations

- Works only from supplied text and files; it does not read email, chat, CRM, support tickets, calendars, status pages or knowledge bases.
- Does not send, schedule, queue, log, tag, update or record anything in any system.
- Does not approve refunds, credits, exceptions, liability positions, security disclosures or contract changes.
- Does not verify the truth of internal claims or customer claims; it only separates and attributes them.
- Cannot repair a missed prior commitment; it can only acknowledge it and propose a new approved update.
- Tone guidance is not a substitute for local language, culture, accessibility or legal review.
- Synthetic examples use invented companies, people and incidents. No real customer communication is included.
