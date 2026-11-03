# Synthetic triage batch — 2026-11-01

All organizations, people, systems and identifiers below are invented for this fixture. No real ticket, account or personal data is used. Triage time is **2026-11-01T09:20:00Z**.

## Organization policy supplied with the batch

- Clock: calendar hours for all priorities (no business-hours pause).
- P1 first response 45 minutes; status update every 90 minutes.
- P2 first response 3 hours; status update every 6 hours.
- P3 first response 24 hours; status update at each material change.
- P4 first response 48 hours; status update on resolution or request.
- Security floor: any credible security or data-exposure signal is P1 until the security process classifies it.
- Pattern threshold: three independent reports of the same symptom.
- Routing queues: Security, Tier 1, Tier 2, Engineering, Product, Billing, Account.
- The customer contract may override these targets; no contract override is supplied in this batch.
- Output language: English. PII must be minimized.

## Open tickets supplied

| Id | Status | Symptom | Product area | Affected | Opened |
| --- | --- | --- | --- | ---: | --- |
| T-0998 | Open | Dashboard returns HTTP 500 for EU users | Dashboard / EU | 3 users | 2026-11-01T09:05:00Z |
| T-1001 | Open | SSO callback returns 403 for a different organization | Authentication / SSO | 14 users | 2026-11-01T08:50:00Z |
| T-0977 | Waiting on customer | Invoice PDF logo is low resolution | Billing documents | 1 user | 2026-10-28T11:00:00Z |
| T-0988 | Resolved | Import API 502 for a 30 MB file | Import API | 1 user | 2026-10-30T16:00:00Z |

## Known issues supplied

| Id | Status | Scope | Workaround |
| --- | --- | --- | --- |
| KI-77 | Investigating | Import API may return 502 for files over 20 MB | Split the file below 20 MB; retry with backoff |
| KI-81 | Workaround available | Invoice PDF logo may look soft at 150 dpi | Re-download at 300 dpi from Billing settings |

No other known issues were supplied. The guide must not claim a live knowledge-base search.

## Ticket T-1042

- Received: 2026-11-01T09:12:00Z
- Channel: portal
- Account: `ACME-8842` (Enterprise, EU region)
- Reporter: `ops-lead` (name withheld)
- Text:

> Since about 09:05 UTC our whole EU team gets a blank dashboard with HTTP 500. About 240 users are affected. It started right after your 08:55 deploy. We are closing month-end and cannot pull any reports. Is our data safe? This is unacceptable — please escalate to your management.

- Affected: about 240 users, one organization, EU region.
- Workaround: none supplied. The reporter says individual report URLs also fail.
- Security/data-loss signal: asks "Is our data safe?" but reports no evidence of loss or unauthorized access.
- Business impact: month-end reporting blocked.
- Requested outcome: restore access and confirm data safety.

## Ticket T-1043

- Received: 2026-10-31T23:10:00Z
- Channel: email
- Account: `ACME-8842`
- Reporter: `jane.doe@example.com` (synthetic; minimize in output)
- Text:

> I was charged twice this month. The card ending 4242 shows two charges of $1,250.00 on 30 October. Please refund the duplicate immediately. Our invoice number is INV-5591.

- Affected: one user/account; product access unaffected.
- Workaround: not applicable.
- Security/data-loss signal: none.
- Requested outcome: refund the duplicate charge.
- Note: no refund authorization or payment record was supplied.

## Ticket T-1044

- Received: 2026-11-01T08:40:00Z
- Channel: chat
- Account: `BOREAL-2210` (Business, AU region)
- Reporter: `it-admin` (name withheld)
- Text:

> Nobody in our company can sign in through SSO. The callback returns 403. We have 60 staff and all of them are locked out. Individual admin password login still works for two IT admins. We changed nothing on our side. Other companies must be seeing this too.

- Affected: 60 users, one organization; two admins have a direct-login workaround.
- Workaround: admin direct login only; end users have none.
- Security/data-loss signal: none stated; access failure only.
- Business impact: staff cannot start work.
- Requested outcome: restore SSO.

## Ticket T-1045

- Received: 2026-10-31T22:00:00Z
- Channel: security contact form
- Account: `DELTA-3301` (Enterprise)
- Reporter: `security-researcher` (name withheld)
- Text:

> I found that a support export link I was given still works after I removed the workspace member who created it. I downloaded a CSV containing another workspace's rows. I have not shared it. The link is `https://exports.example.invalid/e/FAKE-ONLY-1234`. My API key is `demo-key-0000` — please rotate it. This looks like an access-control bug.

- Affected: unclear; at least one export link and possibly one other workspace.
- Workaround: none.
- Security/data-loss signal: unauthorized access to another workspace's data via a still-valid export link.
- Requested outcome: security review and key rotation.

## Ticket T-1046

- Received: 2026-10-30T14:00:00Z
- Channel: email
- Account: `ACME-8842`
- Reporter: `CFO office` (name withheld)
- Text:

> Our CFO wants a native PowerPoint export with speaker notes by next quarter. This is an executive priority. Please confirm the date.

- Affected: one organization; no current workflow blocked (they export PDF today).
- Workaround: PDF export works.
- Security/data-loss signal: none.
- Requested outcome: committed delivery date for a feature that does not exist.

## Ticket T-1047

- Received: 2026-11-01T09:00:00Z
- Channel: portal
- Account: `FERN-5502` (Standard)
- Reporter: `billing-user` (name withheld)
- Text:

> URGENT!!! The logo on our invoice PDF is slightly pixelated. This is embarrassing. Fix it immediately or we will leave a bad review.

- Affected: one user; no workflow blocked.
- Workaround: KI-81 says re-download at 300 dpi.
- Security/data-loss signal: none.
- Requested outcome: cosmetic fix.

## Ticket T-1048

- Received: unknown (forwarded without headers)
- Channel: email forward
- Account: `GALE-7710` (Business)
- Reporter: `integrations-dev` (name withheld)
- Text:

> Our order webhooks have been failing since yesterday afternoon. We see 401s on every retry. One team of 8 cannot process orders. We did not change the signing secret. Please help.

- Affected: 8 users, one organization; order processing blocked.
- Workaround: none supplied.
- Security/data-loss signal: none stated; repeated 401s may be a credential/configuration issue, not confirmed.
- Requested outcome: restore webhooks.
