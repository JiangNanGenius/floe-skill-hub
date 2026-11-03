# Expected vendor review — synthetic case 2026-11-01

**Draft — not an approval.** This is the expected shape for [`input.md`](input.md), not a real procurement decision.

## Decision summary

- **Decision:** renew or replace the customer-support platform; 120 seats; 3-year horizon; decision by 2026-12-15; contract start 2027-01-15.
- **Recommendation: HOLD.** No vendor is awardable on the supplied evidence.
  - **HelpDeskOne is disqualified**: it fails must-have M1 (AU data residency) and M4 (implementation by 2027-03-01).
  - **SupportHub is the only vendor that passes M1, M3 and M4**, but M2 (current SOC 2 Type II report) is **UNKNOWN**, and the evaluator has a declared material financial interest in SupportHub. It cannot be presented as an unqualified winner.
- **Required next step:** an independent reviewer must take over the evaluation, obtain SupportHub's SOC 2 Type II report and assess it, and confirm the conflict handling. Only then can the decision move to Negotiate or Proceed.
- **Decision owner:** Head of Support (role). **Approvals outstanding:** Finance and Security. No approval, purchase, payment, signature or vendor contact has occurred.

## Requirements and must-haves

| Id | Requirement | HelpDeskOne | SupportHub | Evidence |
| --- | --- | --- | --- | --- |
| M1 | AU data residency | **FAIL** — proposal states US-only hosting, no AU region or AU roadmap | **PASS** — contract draft names an AU region and AU subprocessors | Vendor A proposal; Vendor B contract draft |
| M2 | Current SOC 2 Type II report with scope, period, auditor, exceptions | **PASS** — report supplied for 2025-07-01 to 2026-06-30 with one minor exception and remediation | **UNKNOWN** — "available under NDA after contract"; no report supplied | Vendor A report; Vendor B proposal statement |
| M3 | API integration with the current ticketing system | **PASS** — documented API; sandbox test completed | **PASS** — documented API; sandbox test completed | Evaluation-team test notes |
| M4 | Implementation complete by 2027-03-01 | **FAIL** — 8 weeks from the 2027-01-15 start is 2027-03-12, 11 days late | **PASS** — 6 weeks from 2027-01-15 is 2027-02-26 | Vendor plans; date arithmetic |

A must-have failure is not offset by a good score or a lower price. HelpDeskOne is removed from the award comparison before scoring is considered.

SupportHub's M2 is **UNKNOWN**, not a pass and not a failure. The guide does not convert missing evidence into a score of 1 or a middle value.

## Total cost of ownership

Currency: USD. Tax excluded. Payment terms: net 30. Three-year horizon. No FX conversion is required. All supplied cost components are known, so **cost coverage is 100%** for both vendors.

### Year-by-year

| Vendor | Year 1 | Year 2 | Year 3 | 3-year operating total | Exit at end | Total including exit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| HelpDeskOne | 101,400 | 90,720 | 95,256 | **287,376** | 0 | **287,376** |
| SupportHub | 92,000 | 86,520 | 89,116 | **267,636** | 12,000 | **279,636** |

### Arithmetic

**HelpDeskOne**

- Year 1: license 72,000 + support 14,400 (20% of license) + implementation 15,000 = **101,400**.
- Year 2: license 72,000 × 1.05 = 75,600; support 75,600 × 20% = 15,120; total **90,720**.
- Year 3: license 75,600 × 1.05 = 79,380; support 79,380 × 20% = 15,876; total **95,256**.
- 3-year operating total: 101,400 + 90,720 + 95,256 = **287,376**. Exit is 0. Total including exit: **287,376**.

**SupportHub**

- Year 1: license 84,000 + implementation 8,000 = **92,000** (support included).
- Year 2: 84,000 × 1.03 = **86,520**.
- Year 3: 86,520 × 1.03 = **89,116** (rounded from 89,115.60).
- 3-year operating total: 92,000 + 86,520 + 89,116 = **267,636**. Exit at end: 12,000. Total including exit: **279,636**.

**Comparison**

- SupportHub is **19,740** cheaper on the 3-year operating total and **7,740** cheaper including the 12,000 exit cost.
- SupportHub's year-1 cost is **92,000**, which is **2,000 above** the 90,000 annual budget ceiling; HelpDeskOne's year 1 is **11,400 above** the ceiling.
- HelpDeskOne's 3-year average is **95,792** per year, above the ceiling; SupportHub's operating average is **89,212**, within the ceiling. SupportHub's total including exit averages **93,212** over the horizon, above the ceiling if the exit is treated as an annual-equivalent cost.
- A budget exception or a negotiated year-1 reduction is required for SupportHub. No exception has been approved.

The proposal's "unlimited" API label is subject to a 1,000,000-call-per-month fair-use cap and a 0.50 per 1,000-call overage rate. At the supplied 800,000 calls per month, no overage is projected in year 1, but the cap is a commercial term and must not be described as unlimited.

## Scorecard

Weights: cost 25, functional fit 20, reliability/SLA 20, security/compliance 15, support 10, exit/portability 10.

| Criterion | Weight | HelpDeskOne score | Weighted points | SupportHub score | Weighted points |
| --- | ---: | ---: | ---: | ---: | ---: |
| Cost and commercial terms | 25 | 4 | 100 | 5 | 125 |
| Functional fit | 20 | 4 | 80 | 5 | 100 |
| Reliability and SLA | 20 | 4 | 80 | 3 | 60 |
| Security and compliance | 15 | 4 | 60 | **null** | — |
| Support and services | 10 | 3 | 30 | 4 | 40 |
| Exit and portability | 10 | 5 | 50 | 3 | 30 |
| **Weighted score** | | | **4.00** | | **4.18** |
| **Score coverage** | | | **100%** | | **85%** |

- HelpDeskOne: 400 / 100 = **4.00**, full coverage. It is still disqualified by M1 and M4.
- SupportHub: 355 / 85 = **4.18**, but only **85%** of the weight is scored. The result is **provisional** and is not directly comparable to a 100%-coverage score.
- Missing security score is not a pass. If SupportHub's security score were 1, 3 or 5, with all else equal, the weighted score would be **3.70**, **4.00** or **4.30** respectively. The 4.18 is therefore not a settled advantage.
- Do not rank HelpDeskOne and SupportHub as if 4.00 and 4.18 were the same measurement. One is disqualified; the other is incomplete.

## Risk register

| Risk | Vendor | Likelihood | Impact | Evidence | Mitigation | Residual |
| --- | --- | --- | --- | --- | --- | --- |
| No AU data residency | HelpDeskOne | Certain | High | Proposal E2 | None available; must-have failure | Disqualified |
| Implementation misses 2027-03-01 | HelpDeskOne | High | High | 8-week plan from 2027-01-15; derived from E1 dates | No accelerated plan supplied | Disqualified |
| 5% annual escalation and year-1 budget overrun | HelpDeskOne | Medium | Medium | Quote E2 | Negotiate cap; not reached because disqualified | Not assessed |
| SOC 2 report unavailable before contract | SupportHub | High | High | Proposal E2; report not supplied | Obtain report and exceptions before decision; hold | Open |
| SLA credits are sole remedy, capped at 5%, third-party exclusion | SupportHub | Medium | High | Proposal E2 | Negotiate higher credit, remove sole-remedy cap, narrow exclusion | Open |
| Year-1 cost above budget ceiling | SupportHub | Certain | Medium | 92,000 vs 90,000; E1 budget and derived arithmetic | Budget exception or year-1 reduction; no approval | Open |
| Exit cost and 30-day deletion | SupportHub | Medium | Medium | Contract draft E1 | Negotiate exit assistance and deletion certificate | Open |
| Declared financial interest in SupportHub | SupportHub | Certain | High (integrity) | Conflict declaration | Independent reviewer/recusal; no sole-author recommendation | Open |
| Vendor case studies treated as independent evidence | Both | Medium | Medium | Vendor-provided E2 | Use only evaluator-selected references; label case studies | Mitigated by labeling |
| One independent reference reports a 4-hour onboarding outage | SupportHub | Medium | Medium | Reference E3 | Ask for incident and remediation detail; check SLA history | Open |

## Conflict-of-interest record

- **Declaration:** the support operations lead holds shares in SupportHub through a managed brokerage account. The value is below the organization's disclosure threshold but is described as potentially material to a reasonable observer.
- **Materiality:** material for this decision. A reasonable observer could question whether the lead can objectively recommend SupportHub.
- **Effect:** SupportHub is **not** an unqualified winner. The lead may supply factual analysis but cannot be the sole author of a Proceed recommendation. An independent reviewer must re-check the scoring and the recommendation, or the lead must recuse.
- **Other relationships:** no employment, family, gift, advisory or reseller relationship is declared. "No other relationship declared" is not proof that none exists.
- **Vendor references:** the vendor-arranged calls and paid case study are marketing evidence, not independent references. The one independently selected reference is E3 and its contact details are omitted from this output.
- **If the conflict is resolved:** the independent reviewer should document the basis, re-score the affected criteria and record whether the recommendation changes.

## Evidence ledger

**E1 here means a supplied primary document that the evaluator read, not a document the model independently authenticated.** The guide did not verify a signature, validate an auditor, confirm that a certificate is current, or establish that a report covers the proposed service; Security and Legal must do those checks. E2 is a vendor assertion, E3 an independent reference, E4 evaluator judgment and E5 unknown.

| Id | Claim | Source | Level | Date | What it does not prove |
| --- | --- | --- | --- | --- | --- |
| E-01 | HelpDeskOne is US-only, no AU region | Vendor A proposal | E2 | 2026-11 | That no future AU option exists; no roadmap commitment was supplied |
| E-02 | HelpDeskOne SOC 2 Type II report covers 2025-07-01 to 2026-06-30 | Report supplied by Vendor A | E1 | 2026-06-30 | That the proposed configuration is in scope; read the scope and exceptions |
| E-03 | HelpDeskOne implementation takes 8 weeks | Vendor A plan | E2 | 2026-11 | That the start date can move earlier; contract starts 2027-01-15 |
| E-04 | SupportHub contract names an AU region and AU subprocessors | Contract draft | E1 | 2026-11 | That every subprocessor is disclosed or that support access is AU-only |
| E-05 | SupportHub has a SOC 2 Type II report | Vendor B proposal | E2 | 2026-11 | Scope, period, auditor, exceptions; report not supplied |
| E-06 | SupportHub implementation takes 6 weeks | Vendor B plan | E2 | 2026-11 | That resourcing is committed |
| E-07 | SupportHub SLA is 99.95%, credits sole remedy capped at 5%, third-party exclusion | Vendor B proposal | E2 | 2026-11 | Actual uptime; no historical SLA report supplied |
| E-08 | SupportHub is 19,740 cheaper operating / 7,740 cheaper including exit | Arithmetic on supplied costs | Derived from E1 | 2026-11 | Future price changes beyond the supplied escalation |
| E-09 | Independent reference reported a 4-hour onboarding outage | Evaluator-selected reference | E3 | 2026-11 | That the issue is representative or resolved |
| E-10 | Evaluator holds shares in SupportHub | Conflict declaration | E1 (declaration) | 2026-11 | The exact value or any undisclosed interest |

## Negotiation plan

If the independent reviewer confirms SupportHub's M2 and manages the conflict, negotiate before any approval:

| Priority | Term | Target | Fallback | Why |
| ---: | --- | --- | --- | --- |
| 1 | SOC 2 Type II report before signature | Full report with scope, period, auditor and exceptions; security review sign-off | No signature until supplied | M2 is a must-have; the proposal statement is not evidence |
| 2 | Year-1 price within 90,000 | Reduce year-1 license or implementation by at least 2,000 | One-time budget exception with Finance approval | Current year 1 is 2,000 over the ceiling |
| 3 | SLA remedy | Raise credit cap above 5%; remove "sole remedy"; narrow the third-party exclusion | Documented risk acceptance by Security and the business owner | The current remedy is weak relative to a support-platform outage |
| 4 | Exit and deletion | Waive or reduce the 12,000 exit assistance; deletion certificate within 30 days | Fixed-fee exit with a tested export | Lock-in and data-return risk |
| 5 | Auto-renewal | Remove auto-renewal or extend notice to at least 60 days | Calendar control with named owner | 30 days is short for a material renewal |
| 6 | Fair-use cap | Written definition, measurement method and overage cap | Monitor usage quarterly | "Unlimited" is not a commitment |

For HelpDeskOne, no commercial negotiation can cure M1 or M4. A future re-evaluation would need a contractual AU region and an implementation plan that finishes by 2027-03-01; neither is supplied.

## Open questions

1. Can SupportHub supply the SOC 2 Type II report, with scope, period, auditor and exceptions, before the decision date?
2. Does SupportHub's AU region cover support access and all subprocessors, or only storage?
3. How is the 1,000,000-call fair-use cap measured, and what happens on a disputed overage?
4. Will Finance approve a year-1 exception of 2,000, or must the vendor reduce the price?
5. Who is the independent reviewer, and will the conflicted lead recuse from the final recommendation?
6. Can the contract start move earlier, and would that change the M4 arithmetic? The current start is 2027-01-15.
7. Is the independent reference willing to discuss the 4-hour outage and its remediation in more detail?
8. Has either vendor had a ownership, subprocessor or data-residency change in the last 12 months?

No vendor was contacted to answer these questions; they are for the human evaluation team.

## Claim boundary

This is a decision-support draft, **not an approval**. It does not establish that either vendor is secure, compliant, financially stable or able to deliver; it records the supplied evidence and its limits. It does not authorize a purchase order, payment, contract signature, renewal, termination or vendor contact. The TCO is based on supplied costs and a 3-year horizon; unknown future usage, taxes, FX or scope changes could alter it. The scores are structured judgments, not measurements. The conflict declaration depends on the evaluator's honesty and does not replace an independent review. Finance, Security and the decision owner must make the actual decision.
