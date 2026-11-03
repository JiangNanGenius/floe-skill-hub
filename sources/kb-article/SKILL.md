---
name: kb-article
description: Turn a resolved support issue or recurring question into a structured, searchable knowledge-base draft with accurate metadata, verified steps, known limitations and a review date. Guide-only; it does not publish, unpublish, edit a live knowledge base, or claim that steps were tested.
---

# Knowledge Base Article

## Floe guide adaptation (read first)

- Adapted for Floe from the Apache-2.0 upstream skill recorded in `references/PROVENANCE.md`. The article types, structure standards, searchability guidance, known-issue lifecycle and maintenance cadence are retained; the live support-platform, knowledge-base and project-tracker lookups are removed.
- Bring the source material: the resolved ticket or question, the verified resolution or workaround, the exact error text, the product version, the audience, any related articles and the review cadence. Paste text or attach workspace files. No support platform, knowledge base, CMS, analytics tool or project tracker is connected or implied.
- The output is a **draft article** plus metadata and publishing notes. The guide does not publish, schedule, unpublish, archive, redirect or edit a live article, and it does not send anything to customers. A human editor and, for technical content, a subject-matter reviewer approve publication.
- This is not a marketing-content or long-form editorial guide. Its job is self-service support accuracy: a customer with a problem should find the article, recognize the symptom and complete a verified resolution or workaround.
- Repository attention and repository-wide commits are not evidence about this skill's content freshness. The upstream path history is in `references/PROVENANCE.md`; no recent-content claim is made.

**Important**: A resolution is not verified because a customer said it worked, because a colleague suggested it, or because the model can describe it. Record who verified it and when, or label the article as an unverified draft. Never claim the model tested the steps.

## Input contract

Provide, or state that a value is missing:

| Input | Why it is needed |
| --- | --- |
| Source ticket, question or conversation (redacted) | Establishes the real symptom and the resolution history |
| Exact error message or observed behaviour | Drives the title, search terms and troubleshooting structure |
| Product, version, plan and environment | Scopes the article and prevents overgeneralization |
| Audience (end user, admin, developer, specific plan) | Sets prerequisites, permissions and depth |
| Verified resolution or workaround, with who verified it and when | Separates a supported answer from a guess |
| Root cause, if known and shareable | Explains the fix without exposing internals |
| Fix status and expected availability, if committed | Prevents a stale or invented timeline |
| Steps taken and their observed results | Supports a reproducible how-to or troubleshooting article |
| Prerequisites, permissions and plan limits | Prevents a step that the audience cannot perform |
| Known limitations, side effects and data impact | Keeps the article honest |
| Related article ids or topics | Enables cross-linking without inventing URLs |
| Existing article list and owners | Supports update-vs-create and duplicate checks |
| Review cadence and last-reviewed date | Computes the next review date |
| Localization and terminology constraints | Keeps the article usable in the target language |
| Publication target and approval path | Makes the handoff actionable without connecting to it |
| Privacy constraints and redaction evidence | Prevents customer data entering the article |

If an input is missing, write **UNKNOWN** in the metadata or body. Do not infer a plan limit, a fix date, a reviewer's identity or a test result.

## Evidence gate

Before drafting, classify the source:

| Evidence class | Meaning | Use in the article |
| --- | --- | --- |
| **Verified resolution** | A named support engineer, SME or reproducible test confirmed the steps and the outcome | May be presented as the recommended solution, with the verifier recorded |
| **Verified workaround** | The workaround is confirmed but the underlying defect remains | Present as a workaround, with its limits and the unresolved status |
| **Reported fix** | The customer says it worked, with no independent verification | Label as customer-reported; do not present as the official fix |
| **Hypothesis** | A plausible cause or step that has not been confirmed | Put in internal notes, not in the customer-facing solution |
| **Unknown** | No evidence | Say so; do not fill the gap with confident prose |

Rules:

- A ticket being closed is not proof that the resolution worked. Record the closure reason and the evidence.
- A workaround is not a fix. Say which one the article provides.
- If the root cause is unknown, write "Cause: under investigation" or omit the cause section; never invent a technical explanation.
- If the fix date is not approved, do not write one. "No fix date is confirmed" is a valid, useful statement.
- If the resolution depends on a permission, plan or region, state it before the steps.
- If the source contains another customer's data, a secret, an internal hostname or an employee name, redact it before drafting.

## Step 1 — Choose the article type

| Type | Choose when | Primary reader question |
| --- | --- | --- |
| **How-to** | The reader needs to accomplish a task | "How do I do X?" |
| **Troubleshooting** | The reader sees a symptom or error and needs a fix | "Why is X broken and how do I fix it?" |
| **FAQ** | A short, stable answer to a common question | "Does X work this way?" |
| **Known issue** | A defect or limitation is active, with or without a workaround | "Is this a known problem, and what do I do now?" |
| **Reference** | The reader needs lookup data: limits, fields, compatibility | "What are the values or constraints?" |

Decision rules:

- If the answer is a single fact or a short policy statement, use **FAQ**, not a padded how-to.
- If the reader must perform steps, use **how-to**.
- If the reader is diagnosing an error, use **troubleshooting**; put the exact error in the title.
- If the product is currently wrong and the fix is not available, use **known issue**, even if a workaround exists.
- If the article mixes a task and a defect, split it: a how-to for the task and a known issue for the defect.

## Step 2 — Build the article skeleton

Every article includes:

1. **Title** — the symptom or task in the reader's words.
2. **Overview** — one or two sentences: what the article covers, who it is for, and what outcome it produces.
3. **Prerequisites** — plan, role, permission, version, region or data needed.
4. **Body** — type-specific sections below.
5. **Verification** — how the reader knows it worked.
6. **Related articles** — only supplied or clearly labeled placeholders.
7. **Metadata** — type, category, tags, audience, product/version, owner, reviewer, last reviewed, next review, status.

### How-to skeleton

```
# How to [accomplish the task]

[Overview: what this covers and when to use it]

## Before you start
- [Prerequisite]
- [Permission or plan requirement]

## Steps
### 1. [Action]
[Instruction with the exact UI path or value.]
You should see [expected result].

### 2. [Action]
[Instruction.]
You should see [expected result].

## Verify it worked
[Observable check.]

## Common problems
- [Symptom]: [Cause if known] / [Fix or workaround]

## Related articles
- [Supplied related article]
```

### Troubleshooting skeleton

```
# Fix: "[exact error or symptom]"

## Symptoms
- [What the reader sees]
- [Where and when it happens]

## Cause
[Verified cause, or "Under investigation."]

## Solution
### Option 1: [Most likely fix]
1. [Step]
2. [Step]
You should see [expected result].

### Option 2: [Alternative, if supplied and verified]
[Steps]

## If it still fails
[What to collect and where to get help, using the supplied support path.]

## Related articles
- [Supplied related article]
```

### FAQ skeleton

```
# [Question in the reader's words]

[Direct answer in 1-3 sentences.]

## Details
[Only the nuance the reader needs.]

## Related questions
- [Supplied related article]
```

### Known-issue skeleton

```
# Known issue: [symptom]

**Status:** [Investigating / Workaround available / Fix in progress / Resolved]
**Affected:** [Plans, versions, regions, roles]
**Last updated:** [YYYY-MM-DD]
**Next update:** [Only if an update cadence is supplied]

## Symptoms
[What the reader sees.]

## Workaround
[Verified steps, or "No workaround is available."]

## Fix status
[What is known; no invented date.]

## Updates
- [YYYY-MM-DD]: [Verified update.]
```

### Reference skeleton

```
# [Topic] reference

[Scope and source of the values.]

| Item | Value | Notes |
| --- | --- | --- |
| [Item] | [Value] | [Constraint or caveat] |

## Related articles
- [Supplied related article]
```

## Step 3 — Write for search and recognition

### Title rules

- Put the reader's symptom or task first; keep it specific.
- For troubleshooting, include the exact error text if it is short: `Fix: "Export limit exceeded (EXP-413)" when exporting more than 10,000 rows`.
- Avoid internal codenames unless customers use them.
- Avoid "Issue", "Problem" or "Information" as the only differentiator.
- Keep the title under about 70 characters where the publication target allows; if the exact error is longer, put the error in the first body line instead.
- Do not use a question title for a how-to; use an action title.

### Searchability rules

- Include the exact error string, the visible UI label and the customer's likely synonyms ("export/download", "sign in/log in", "delete/remove").
- Use the customer's language in the first sentence, then the product term.
- Name the product area, plan and version in the metadata, not as keyword stuffing.
- Add alternate phrasings in the overview only when they are natural.
- Do not add hidden keywords, unrelated tags or competitor names.
- If the article is a known issue, include the status and the affected scope so search results do not overpromise.

### Writing rules

- Address the reader as "you"; use imperative steps.
- One idea per section; split an article that covers two problems.
- Put the action first in each step; put the expected result after it.
- Use exact UI paths: **Settings > Integrations > API keys**.
- Use code formatting for commands, error strings, field names and literal values.
- Use tables for limits, compatibility and options, not for narrative.
- Use notes for a warning or a prerequisite that could cause data loss; use a warning label for destructive actions.
- Keep paragraphs to 2-4 sentences.
- Use absolute dates (`2026-11-01`), not "recently", "soon" or "last week".
- Do not use marketing claims, superlatives or unverified security/compliance statements.
- Do not include customer names, email addresses, account ids, access tokens, internal hostnames, employee names or screenshots containing customer data.
- Use descriptive link text; do not use "click here".
- Do not promise a support response time unless the supplied policy provides one.

## Step 4 — Handle known issues and active incidents

- Use the **known issue** type while the defect or limitation is active, even if a workaround exists.
- State the status from the supplied evidence: Investigating / Workaround available / Fix in progress / Resolved.
- State the affected scope: plans, versions, regions, roles and whether data is affected.
- If a workaround exists, give verified steps and say what it does not fix.
- If no workaround exists, say "No workaround is available" rather than offering a guess.
- Do not invent a fix date or a "next update" date. Use a cadence only if the incident policy supplies one.
- When the issue is resolved, update the status and keep the article available for readers still searching the old symptom for the period the retention policy specifies.
- If the issue is urgent or expanding, link to the status page **only if a URL is supplied**; otherwise say where the reader should check.
- Never describe an active incident as resolved because a workaround exists or because the ticket was closed.

## Step 5 — Review, metadata and maintenance

### Metadata

Record:

- article id or slug (supplied or `UNKNOWN`);
- title;
- type;
- category and tags;
- audience and plan;
- product and version;
- owner (role or team, not an invented person);
- technical reviewer (supplied or `UNKNOWN`);
- editorial reviewer (supplied or `UNKNOWN`);
- source ticket/reference (minimized);
- last reviewed date;
- next review date, computed from the supplied cadence;
- status (`Draft`, `In review`, `Published`, `Needs update`, `Archived` — the output itself is always `Draft`);
- related articles.

### Review and maintenance

| Activity | Cadence | Output |
| --- | --- | --- |
| Technical accuracy review | Before publication and on product change | Reviewer recorded; unresolved claims listed |
| Editorial review | Before publication | Clarity, structure, terminology and accessibility |
| Stale-content check | Per supplied cadence (for example, every 90 or 180 days) | Next review date and a flag if the last review is older |
| Known-issue update | Per incident cadence | Status and date updated; no invented ETA |
| Analytics/feedback review | Per supplied cadence | Topics with low helpfulness or high search-with-no-click |
| Gap analysis | Per supplied cadence | Recurring ticket topics without an article |

### Update or create?

- **Update** when the product changed, the article is mostly correct but missing a detail, feedback shows confusion, or a better verified workaround exists.
- **Create** when a new feature or product area needs coverage, a resolved ticket reveals a gap, the existing article mixes too many topics, or a different audience needs a different depth.
- Do not create a near-duplicate because the title is different. Check the supplied existing-article list first; if the list is absent, say the duplicate check is `UNKNOWN`.

## Floe output contract

A synthetic example is in [`assets/examples/input.md`](assets/examples/input.md), its machine-readable facts are in [`assets/examples/figures.json`](assets/examples/figures.json), and the expected output shape is in [`assets/examples/expected-output.md`](assets/examples/expected-output.md). They are synthetic examples, not executed results.

Produce these sections in order:

1. **Draft status** — `Draft — not published`; article type; confidence and what is still unverified.
2. **Metadata block** — all fields above; use `UNKNOWN` rather than blank or guessed values.
3. **Article body** — using the chosen type's skeleton; no internal notes inside the customer body.
4. **Publishing notes** — source, evidence class, verifier, existing article to update, reviewer needed, open questions, redactions.
5. **Review plan** — technical and editorial review, next review date and its arithmetic, status/update cadence for a known issue.
6. **Searchability check** — exact error, synonyms, audience terms and title length; note any missing term.
7. **Claim boundary** — what the article does not establish (root cause, fix date, tested-by-model, publication).

If a section cannot be completed, keep it and write **UNKNOWN** or **not supplied**. Do not omit it.

## Quality checks before returning

- The type matches the reader's question and the evidence status.
- The exact error or symptom appears in the title or first body lines when applicable.
- Every step has an action and an expected result; prerequisites and permissions are stated.
- The resolution is labelled verified, workaround, customer-reported or unverified.
- No root cause, fix date, plan limit, support SLA or test result is invented.
- The article contains no customer data, secret, internal hostname or unnecessary employee name.
- Related-article references are supplied or clearly marked as placeholders; no invented URLs.
- Metadata is complete, the next review date is computed, and the status is `Draft`.
- The article is clearly labeled `Draft — not published`; no publish action is claimed.
- The language is plain, scannable and accessible; no marketing copy.

## Scope and limitations

- Works only from supplied text and files; it does not search a live knowledge base, support platform, CMS, analytics tool or project tracker.
- Does not publish, edit, unpublish, archive, redirect or translate a live article, and does not send customer notifications.
- Does not verify a fix, test the steps, confirm a root cause or establish a fix date.
- Does not replace a subject-matter expert's technical review or an editor's publication approval.
- Searchability guidance cannot guarantee ranking or search-volume outcomes.
- Review dates are arithmetic from a supplied cadence, not a promise that the content will still be correct then.
- Synthetic examples use invented customers, products, errors and limits. No real article, ticket or customer data is included.
