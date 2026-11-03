# Expected triage output — synthetic batch 2026-11-01

This is the expected **shape and reasoning** for the example in [`input.md`](input.md), not a real triage result. Triage time is 2026-11-01T09:20:00Z. All counts and deadlines are computed from the supplied policy, which uses calendar hours.

## Triage summary

| Id | Primary / secondary | Priority | Status | Deciding gate | Route recommendation |
| --- | --- | --- | --- | --- | --- |
| T-1042 | Bug / Performance | **P1** | Confirmed (report-based) | Reported production unavailable for about 240 users in one organization; no workaround | Engineering |
| T-1043 | Billing / — | **P3** | Confirmed | Single account, money question, access unaffected | Billing |
| T-1044 | Bug / Account | **P2** | **Provisional** | Core workflow blocked for 60 users in one organization; P1 only if other organizations are confirmed affected | Tier 2 |
| T-1045 | Security / Data | **P1** | Confirmed (security floor) | Credible unauthorized access to another workspace's data; security floor | Security |
| T-1046 | Feature request / — | **P4** | Confirmed | Capability does not exist; PDF workaround; executive sponsorship is not impact evidence | Product |
| T-1047 | Bug / — | **P4** | Confirmed | Cosmetic defect, one user, documented workaround | Tier 1 |
| T-1048 | Integration / — | **P2** | **Provisional** | Order workflow blocked for 8 users, no workaround; clock and secret state unknown | Tier 2 |

Counts: **P1 = 2, P2 = 2, P3 = 1, P4 = 2**; **2 provisional**; **1 deadline already missed**; **1 unknown clock**.

The batch contains no contract-specific SLA override, so the organization policy above controls. The default table in the guide is not used.

## T-1042 — full triage

### Evidence table

| Field | Value | Class |
| --- | --- | --- |
| Reported symptom | EU dashboard shows a blank page with HTTP 500 | Reported |
| First seen | About 09:05 UTC on 2026-11-01 | Reported |
| Scope | About 240 users, one organization, EU region | Reported |
| Business process | Month-end reporting blocked; individual report URLs also fail | Reported |
| Workaround | None supplied | Reported |
| Claimed cause | "Started right after your 08:55 deploy" | Claim; not verified |
| Data-safety question | "Is our data safe?" with no evidence of loss or unauthorized access | Reported |
| Requested outcome | Restore access and confirm data safety | Reported |
| Material unknowns | Whether any data was corrupted or exposed; whether other organizations are affected; whether the deploy is causal | Unknown |

### Impact and urgency

- Impact: **Critical** — production surface unavailable for all reporting users in one organization, with no workaround, during a dated month-end process.
- Urgency: **Immediate** — the customer cannot perform the month-end close now.
- Relationship signal: the reporter asks for management escalation and calls the situation unacceptable. This is recorded but does not change the technical assessment; P1 is already justified by impact.

### Priority

**P1 — confirmed.** Gate 1 applies: production unavailable for all or most users of an organization, no workaround. The data-safety question is not itself a security finding, but if any evidence of loss or exposure appears, the Security category and security process take over; priority remains at least P1.

### SLA clock

- Received: 2026-11-01T09:12:00Z.
- First-response target: 45 minutes (P1, organization policy).
- Deadline: 09:12 + 00:45 = **2026-11-01T09:57:00Z**.
- At triage 09:20:00Z, elapsed = 8 minutes; **37 minutes remain**; deadline not passed.
- Next status update: 09:12 + 01:30 = **2026-11-01T10:42:00Z**.

### Duplicate / known-issue check

- Compared against four open tickets and two known issues.
- **Candidate duplicate of T-0998** (`Dashboard returns HTTP 500 for EU users`, opened 09:05Z, 3 users): same symptom, product area and overlapping window. Recommend linking this report to T-0998 so the investigating team sees the larger reported scope; do **not** merge, close or reassign either ticket without the queue owner's action.
- **Pattern count: 2** independent reports. The policy threshold is 3, so this is not yet a pattern escalation; watch for a third report and for any non-EU report.
- KI-77 is about import 502s for large files and is **not** a match. No known issue covers the dashboard 500.

### Routing recommendation

- Primary: **Engineering** — production defect with a deploy correlation and no workaround.
- Consulting: **Security** only if data loss or exposure is confirmed. The customer's data-safety question alone does not establish a security incident.
- Human confirmation needed: whether an incident owner has been assigned; the guide cannot assign one.
- Do not state that the ticket was routed or merged. The recommendation and the duplicate link are for the human to apply.

### Draft first response

**Draft — not sent**

> Subject: EU dashboard HTTP 500 — next update by 10:42 UTC
>
> Hi [name],
>
> Thank you for reporting this. I understand the EU dashboard is returning HTTP 500 for your team and that this is blocking month-end reporting for about 240 users. I also understand your concern about data safety.
>
> The timing and scope in your report — failures from around 09:05 UTC affecting about 240 EU users — have not yet been independently verified by us. I cannot yet confirm the root cause, and I cannot yet confirm whether any data was affected. I will not speculate about the 08:55 deploy until engineering has checked it.
>
> Your report appears to match an existing ticket. We recommend linking the reports; no merge has been made. There is no verified workaround at this time.
>
> I will update you by **10:42 UTC today**, even if there is no resolution. If you can share one failed report URL or a screenshot with account and customer details removed, that would help; please do not send credentials or customer data.
>
> I am sorry for the disruption to your close.
>
> [Sender]

The draft contains no cause, no fix ETA, no data-safety guarantee, no refund or credit, and no claim that anything has been fixed or escalated.

### Internal notes

- Reproduction hint: EU region, authenticated dashboard, HTTP 500 on initial load and on direct report URLs; correlate with the 08:55 deploy and T-0998.
- Already ruled out: nothing is confirmed; do not record the deploy as the cause.
- Escalation: if a third independent report arrives, or any data-loss/exposure evidence appears, raise the pattern/security flag immediately.
- PII: reporter name withheld; no customer data is reproduced.

## T-1043 — billing duplicate charge

- Evidence: one account reports two charges of $1,250.00 on 30 October; product access is unaffected; no payment record or refund authorization was supplied.
- Category: **Billing**. Priority: **P3 confirmed** (single account, money question, no blocked workflow).
- SLA: received 2026-10-31T23:10:00Z + 24 hours = **2026-11-01T23:10:00Z**; 13 hours 50 minutes remain at triage.
- Duplicate: none of the supplied records match. Known issues: none.
- Route recommendation: **Billing / finance**; refund approval remains with finance.
- Draft direction: acknowledge the duplicate-charge report; say the billing team will review it; ask for a redacted invoice or charge reference; commit only to confirming the outcome by a named date. Do **not** say the charge will be refunded or that a refund has been issued.
- Privacy: omit the email address and the card digits from the output; refer to "the card on file" and the account reference. The invoice number may be retained because it is needed for the review.

## T-1044 — SSO 403, one organization

- Evidence: 60 users in one organization cannot sign in through SSO; the callback returns 403; two IT admins can still use direct password login; the customer says no configuration changed.
- Category: **Bug** (root cause is a product/authentication failure, not merely an account request) with secondary **Account**.
- Priority: **P2 provisional**. Gate 2 applies for one organization with a blocked core workflow and no end-user workaround. It becomes P1 if another organization is confirmed affected or if the 403 indicates a platform-wide authentication fault. The supplied open ticket T-1001 is another organization with the same symptom; that is **related**, not yet proof of a platform-wide outage.
- SLA: 08:40 + 3 hours = **2026-11-01T11:40:00Z**; next update 14:40Z.
- Pattern count: 2; threshold 3. Watch for a third organization.
- Route recommendation: **Tier 2** for reproduction and IdP/callback diagnosis; Engineering if the defect is confirmed.
- Draft direction: acknowledge the lockout, give the admin direct-login workaround, ask for the exact callback error and a redacted HAR/trace, and give the 14:40Z update. Do not claim other companies are affected.

## T-1045 — security report

- Evidence: a support export link remained usable after the member who created it was removed; the reporter downloaded a CSV containing another workspace's rows; the reporter supplied an export URL and an API key. Both are secrets and must not be repeated.
- Category: **Security** (primary), **Data** (secondary).
- Priority: **P1 confirmed** by the security floor. This is not downgraded because the scope is unclear or the reporter is external.
- SLA: received 2026-10-31T22:00:00Z + 45 minutes = **2026-10-31T22:45:00Z**. At triage 2026-11-01T09:20:00Z the first response is **10 hours 35 minutes late (635 minutes)**. The scheduled 23:30Z update is also overdue. This is an **SLA breach** and an escalation flag.
- Route recommendation: **Security / incident response**. Do not route to Tier 1 first, do not ask for more secrets, and do not confirm a breach.
- Draft direction: apologize for the delayed response; confirm the report is being treated as a security matter; ask the reporter to stop accessing or sharing the link; say the exposed link and key must be rotated by the responsible team; give an immediate recovery update time (recommended within 30 minutes of triage); do not repeat the URL or key; do not name other workspaces.
- Privacy: remove the export URL, the API key and the reporter's identity from the triage note. Preserve only "a support export link and a credential were disclosed" and a reference to the secure evidence location.

## T-1046 — executive feature request

- Category: **Feature request**. Priority: **P4 confirmed**; the current PDF export is a workaround and no workflow is blocked.
- The CFO's sponsorship and the request to "confirm the date" do **not** raise priority and do **not** authorize a roadmap commitment. Record an executive communication signal and recommend the Product route.
- SLA: 2026-10-30T14:00:00Z + 48 hours = **2026-11-01T14:00:00Z**; not passed.
- Draft direction: thank the requester, say the request will be recorded for product review, state that no delivery date is confirmed, and offer to route the executive question through the account team. Do not invent a quarter or a date.

## T-1047 — cosmetic "urgent" request

- Category: **Bug** (cosmetic). Priority: **P4 confirmed**. One user, no workflow blocked, documented workaround KI-81 (re-download at 300 dpi).
- The capitalized "URGENT", the threat of a bad review and the demand to "fix immediately" are relationship/communication signals, not impact evidence. No priority change.
- SLA: 2026-11-01T09:00:00Z + 48 hours = **2026-11-03T09:00:00Z**.
- Route recommendation: **Tier 1** with the KI-81 workaround. Draft: acknowledge the cosmetic issue, give the 300 dpi workaround, and avoid promising a code change date.

## T-1048 — forwarded webhook failures, unknown clock

- Category: **Integration**. Priority: **P2 provisional**: 8 users cannot process orders and no workaround is supplied. Provisional because the received time is unknown and the repeated 401s may be a credential/configuration issue rather than a product defect.
- SLA clock: **UNKNOWN** — the forward has no headers. Do not fabricate a received time; ask the reporter for the original message headers or the first failure timestamp.
- Route recommendation: **Tier 2** for authentication/signature diagnosis; Engineering if a defect is confirmed.
- Draft direction: ask for the original timestamp, the exact 401 response with the signature and secret redacted, and whether any credential rotation occurred. Do not ask for the signing secret.

## Duplicate and pattern summary

| New ticket | Supplied record | Classification | Evidence |
| --- | --- | --- | --- |
| T-1042 | T-0998 | Candidate duplicate (not merged) | Same dashboard 500 symptom, EU, overlapping window; new report states about 240 affected users |
| T-1044 | T-1001 | Related | Same SSO 403 symptom, different organization; possible common cause, not yet proven |
| T-1047 | KI-81 | Known issue with workaround | Same invoice-logo softness; 300 dpi workaround supplied |
| Others | — | No match in the supplied lists | Absence of a match is not proof of uniqueness |

Pattern counts: T-1042 = 2 reports; T-1044 = 2 reports. Neither reaches the policy threshold of 3. No live search was performed.

## Escalation flags

| Flag | Evidence | Effect |
| --- | --- | --- |
| T-1045 first response breached | 635 minutes late at triage; update also overdue | Security incident path; immediate recovery update; record breach |
| T-1042 potential data-safety issue | Customer asks about data safety; no loss evidence supplied | Watch for evidence; if loss/exposure appears, add Security and follow the incident process |
| T-1044 possible multi-tenant authentication issue | Two organizations with SSO 403, two different tickets | Pattern watch; third report or confirmed platform fault raises to P1 |
| T-1043 refund request | Customer asks for an immediate refund | Billing approval path; no refund commitment |
| T-1046 executive request | CFO office asks for a date | Executive communication path; no priority or roadmap change |
| T-1047 churn/review threat | Customer threatens a bad review | Relationship handling; no priority change |

## Privacy handling

- Removed from the output: the reporter email address, the card digits, the export URL, the API key, and the reporter names.
- Kept: the account references, the invoice number (needed for billing review), the exact error strings, the affected counts and the product areas.
- The security note records that a link and a credential were disclosed, not their values. The receiving team must obtain them through the secure evidence channel.

## Claim boundary

This triage is a recommendation built only from the supplied text and lists. It does not prove root cause, data safety, a platform-wide outage, a duplicate beyond the supplied records, or entitlement to a refund. It did not create, route, merge, close, escalate or answer any ticket. A human must confirm the priority, apply any contract-specific SLA, assign the queue, handle the security evidence and send any reply.
