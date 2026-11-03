# Expected response draft — synthetic case 2026-11-01

This is the expected shape for [`input.md`](input.md), not a real customer reply. Drafting time is 2026-11-01T10:30:00Z.

## Draft header

- Status: **Draft — not sent**
- To: Dana Patel, Operations Manager (customer reference `NW-2044`)
- Subject: Import failures — update and next steps (next update 14:00 UTC)
- Channel: email
- Tone: accountable, factual, calm
- Target length: 220-320 words

## Draft body

> Hi Dana,
>
> I am sorry we missed the 09:00 UTC update we promised. That delay is on us, and I am sorry it added uncertainty to your close.
>
> Here is what I can confirm now:
>
> - Between 22:10 UTC on 30 October and 06:00 UTC on 1 November, 3 of your 40 scheduled import jobs failed.
> - Our status page has shown "Import processing degraded" since 23:00 UTC on 31 October.
> - Engineering has found no evidence of data loss so far. The integrity check is still running, so I cannot yet confirm that your data is intact. I will not give you an assurance I cannot support.
> - A fix is being tested in staging. It has not been deployed, and there is no confirmed ETA.
> - A workaround works for two of the three failed files: retry files under 5,000 rows. Your 12,000-row file is still failing, so this does not fully unblock you.
>
> I will ask our account team to review your credit request and will confirm their decision by 3 November. I cannot approve or promise a credit myself, and I do not want to imply otherwise.
>
> Would a 30-minute call with our support lead on 2 November between 09:00 and 11:00 UTC be useful? I can arrange it if you reply with a time that works.
>
> I will update you by 14:00 UTC today, even if there is no new information. If you can send the failed file name and the exact error text with customer data removed — and without credentials — that will help us check your remaining file.
>
> Thank you for your patience. I know this is landing in the middle of your close.
>
> Regards,
> [Sender]

The draft is 286 words in this example. It does not contain a cause, a fix date, a data guarantee, a credit amount or another customer's name.

## Fact ledger

| Statement in the draft | Class | Source | Allowed? |
| --- | --- | --- | --- |
| 3 of 40 scheduled import jobs failed between 22:10Z on 30 October and 06:00Z on 1 November | Verified | Incident lead | Yes |
| Status page has shown "Import processing degraded" since 23:00Z on 31 October | Verified | Status-page note | Yes |
| Engineering has found no evidence of data loss so far | Verified | Incident lead | Yes, with the explicit limit |
| Integrity check is still running; data intactness not confirmed | Verified / Unknown | Incident lead | Yes, stated as unresolved |
| Fix is in staging; not deployed; no confirmed ETA | Verified | Incident lead | Yes |
| Retry under 5,000 rows works for two of three files; the 12,000-row file still fails | Verified | Incident lead | Yes |
| "Second time this quarter" | Customer claim | Customer email | Not stated as fact; not needed in this draft |
| "Upstream storage vendor" is the cause | Customer claim | Customer email | Omitted; not confirmed |
| Credit request outcome | Not authorized | Policy input | Only the review process is promised; no amount or approval |
| Data-loss guarantee | Not authorized | Integrity check incomplete | Refused explicitly |
| Another customer's report | Third-party data | Thread excerpt | Omitted |

## Commitment ledger

| Commitment in the draft | Approver | Owner | Due | Notes |
| --- | --- | --- | --- | --- |
| Update by 14:00 UTC today | Support lead | Sender | 2026-11-01T14:00:00Z | 3.5 hours after drafting |
| Offer a 30-minute call on 2 November, 09:00-11:00 UTC | Support lead | Sender | 2026-11-02T11:00:00Z | Conditional on the customer choosing a time |
| Ask the account team to review the credit request and confirm by 3 November | Account lead | Sender | 2026-11-03 | Review promise only; no credit outcome |
| No fix ETA | — | — | — | Explicitly withheld |
| No data-safety guarantee | — | — | — | Explicitly withheld |

The draft does **not** say the credit is approved, the fix will ship on a date, the cause is known, or the data is intact.

## Pre-send checks

| Check | Result | Detail |
| --- | --- | --- |
| Facts traceable | Pass | Every factual bullet maps to the fact ledger |
| Claims attributed or omitted | Pass | The customer's vendor theory and prior-incident claim are omitted |
| Commitments approved | Pass | All three promises have an approver, owner and date |
| No unauthorized outcome | Pass | No credit amount, refund, ETA, root cause or guarantee |
| No action claimed by the model | Pass | The draft says "I will ask"; it does not say "I have escalated" or "I have refunded" |
| Prior commitment handled | Pass | The missed 09:00Z update is acknowledged with a new 14:00Z commitment |
| Privacy minimized | Pass | No email, phone number, card digits or other customer name appear |
| Channel and length | Pass | 264 words, email-appropriate, specific subject |
| Consistency | Pass | The draft does not contradict the status page or the prior promise |
| Accessibility | Pass | Short sentences, no jargon, no ALL CAPS, one link-free body |
| Approval and send authority | Pass | No credit outcome is claimed; sending remains subject to the sender's actual authority and current policy |

## Internal notes

- **Why this approach:** the customer needs an honest status update and a path to a decision, not a polished excuse. The draft leads with the missed update because pretending it did not happen would damage trust. It gives the verified scope, states the workaround's limit, refuses the guarantee, separates the credit review from the credit decision, and offers a call.
- **Verify before sending:** that the 14:00Z update is still achievable; that the account team can respond by 3 November; that the 12,000-row file is still failing at send time; that the status page wording is current.
- **Sender actions required:** actually ask the account team to review the credit request; book the call if the customer accepts; send the 14:00Z update even if nothing changes; do not send the draft until the sender can meet those commitments.
- **Risk:** the customer may read "no evidence of data loss" as a guarantee despite the qualification. The draft immediately limits it. The credit request may be declined; the draft does not imply otherwise. The customer may escalate to procurement or legal; keep the tone factual and do not discuss liability.
- **Approval required:** any credit, refund, contract change or legal statement requires the authorized approver. The draft only promises a review.
- **Follow-up:** check for a reply before 14:00Z; if the customer accepts the call, confirm the time; after 3 November, record the credit decision and communicate it separately.
- **Deliberately omitted:** the upstream-vendor theory, the other customer's report, the customer's phone and card details, the internal incident id, the engineering ticket, and any speculation about the fix date.

## Approval and send-authority note

**No approval is needed for the draft's credit language** because it promises a review, not a credit. That is not permission to send. Sending requires the sender's actual authority and the current Floe, user and organization communication policy; the guide does not grant, replace or override that permission. If policy requires review of external customer communications, that review still applies. The sender must also have approval before making any credit offer, and must actually route the request. If the account team authorizes a specific credit, a new draft must state the approved amount and terms; this draft must not be edited to imply approval retroactively.

## Adversarial follow-up — refused delivery date

**Requested:** "Tell them SSO SCIM will ship by Friday and say it is committed."

**Refusal:** No roadmap approval, engineering commitment or delivery date exists. The draft cannot state a Friday date, call the feature committed, or imply that a date is being withheld for commercial reasons.

**Honest alternative (draft):**

> Hi [name],
>
> I cannot confirm a Friday date for SSO SCIM. I do not have an approved delivery commitment, and I will not create one in writing. I can confirm that I will check with our product team whether an approved timeline exists and reply by [named date the sender can meet]. If there is no approved timeline, I will tell you that directly.
>
> I understand the renewal timing matters. If it would help, I can set up a short call to walk through what is available today and what would need to change.
>
> Regards,
> [Sender]

The alternative contains no delivery date, no "committed" status and no "will ship" statement. The sender must still obtain the product team's answer before naming a confirmation date.

## Claim boundary

This draft is a communication aid built from supplied facts. It does not establish root cause, data integrity, credit eligibility, a fix date, a contractual position or a security conclusion. It is not sent, scheduled or recorded anywhere, and it neither grants nor overrides permission to send. The sender must verify every fact and commitment, obtain any required approval, perform the promised actions and send the message through the organization's normal channel and current tool, user and organization policy.
