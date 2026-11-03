# Synthetic vendor review — 2026-11-01

All vendors, prices, terms, people and references below are invented for this fixture. No real proposal, contract or vendor performance data is used.

## Decision

- Decision: renew or replace the customer-support platform.
- Scope: 120 seats, one legal entity, global support team; data includes customer ticket content and contact details.
- Decision date: 2026-12-15. Contract start: 2027-01-15. Horizon: 3 years.
- Budget ceiling: USD 90,000 per year, excluding tax.
- Current spend: USD 78,000 per year with the incumbent (not one of the two candidates).
- Currency: USD. Tax excluded. Payment terms: net 30.
- Decision owner: Head of Support (role). Approvals: Finance and Security (roles). No approval has been given.
- Evaluation team: one support operations lead. A conflict declaration is included below.

## Requirements and must-haves

| Id | Requirement | Test | Weight |
| --- | --- | --- | ---: |
| M1 | Customer data stored and processed in Australia | Contractual region and subprocessor list name an AU region | must-have |
| M2 | Current SOC 2 Type II report covering the production service | Report supplied with scope, period, auditor and exceptions | must-have |
| M3 | API integration with the current ticketing system | Documented API and a tested sandbox integration | must-have |
| M4 | Implementation complete by 2027-03-01 | Vendor plan and resourcing show completion by that date | must-have |
| C1 | Cost and commercial terms | Three-year TCO, escalation, payment terms | 25 |
| C2 | Functional fit | Requirements coverage and workflow fit | 20 |
| C3 | Reliability and SLA | Uptime evidence, credits, exclusions | 20 |
| C4 | Security and compliance | Verified reports, residency, access, subprocessors | 15 |
| C5 | Support and services | Tier, response evidence, implementation capability | 10 |
| C6 | Exit and portability | Export, deletion, termination assistance, lock-in | 10 |

## Vendor A — HelpDeskOne (synthetic)

### Commercial terms

- Annual license: USD 72,000 for 120 seats in year 1.
- Price escalation: 5% at each anniversary; the quote's price lock applies to year 1 only.
- Implementation: USD 15,000 one-time.
- Support: 20% of the annual license, billed annually (year 1: USD 14,400).
- Add-ons: none required.
- Exit: standard data export included at no charge; no termination assistance fee stated.
- Auto-renewal: 60 days' notice; the quote does not remove auto-renewal.
- Payment: net 30; tax excluded.

### Must-haves

| Id | Result | Evidence |
| --- | --- | --- |
| M1 | **FAIL** | Proposal states US-only hosting; no AU region and no AU roadmap commitment |
| M2 | **PASS** | SOC 2 Type II report supplied: period 2025-07-01 to 2026-06-30, auditor named, one minor exception with remediation evidence |
| M3 | **PASS** | REST API and webhook documentation supplied; sandbox test completed by the evaluation team |
| M4 | **FAIL** | 8-week implementation plan starting at the 2027-01-15 contract start finishes around 2027-03-12, after the 2027-03-01 deadline |

### Other evidence

- SLA: 99.9% monthly uptime. Service credits up to 10% of the monthly fee. Scheduled maintenance up to 4 hours per month is excluded.
- References: two vendor-arranged calls; one paid case study. No independently selected reference.
- Security: the report's one exception concerns a legacy subsystem outside the proposed scope; the vendor supplied a remediation date.
- Data deletion: 30 days after termination; deletion certificate available on request.

## Vendor B — SupportHub (synthetic)

### Commercial terms

- Annual license: USD 84,000 for 120 seats in year 1.
- Price escalation: 3% at each anniversary, capped for the 3-year term.
- Implementation: USD 8,000 one-time.
- Support: included in the license.
- Usage: "unlimited" API calls subject to a fair-use limit of 1,000,000 calls per month; overage USD 0.50 per 1,000 calls above the limit. Current volume is 800,000 calls per month.
- Add-ons: none required.
- Exit: USD 12,000 data-migration assistance at the end of the term; CSV and JSON export included.
- Auto-renewal: 30 days' notice; the quote does not remove auto-renewal.
- Payment: net 30; tax excluded.

### Must-haves

| Id | Result | Evidence |
| --- | --- | --- |
| M1 | **PASS** | Contract draft names an AU region and lists AU subprocessors |
| M2 | **UNKNOWN** | Vendor states "SOC 2 Type II" in the proposal, but the report is only "available under NDA after contract"; no scope, period, auditor or exceptions were supplied |
| M3 | **PASS** | REST API and webhook documentation supplied; sandbox test completed by the evaluation team |
| M4 | **PASS** | 6-week implementation plan with named roles; completion before 2027-03-01 |

### Other evidence

- SLA: 99.95% monthly uptime. Service credits are the sole remedy, capped at 5% of the monthly fee, and exclude "third-party outages and events outside the vendor's reasonable control." No historical SLA report was supplied.
- References: one independently selected reference (`R. Okafor`, `r.okafor@example.com`; do not include the contact details in the output) and one vendor case study. The independent reference reported a 4-hour outage during onboarding but said support responded well.
- Security: AU residency is stated in the contract draft. The SOC 2 report is not supplied. The subprocessor list is current as of 2026-09-30.
- Data deletion: 30 days after termination; export in CSV/JSON; migration assistance is chargeable.

## Conflict-of-interest declaration

- The support operations lead declares **shares in Vendor B** held through a managed brokerage account. The value is below the organization's disclosure threshold, but the lead describes it as potentially material to a reasonable observer.
- No other financial, employment, family, gift or advisory relationship is declared.
- The lead has not worked for either vendor.
- The declaration is recorded here; the guide must assess its effect on the recommendation and must not ignore it.

## Adversarial terms to handle

1. Vendor A's quote is lower in year 1 but excludes the 20% support fee and applies 5% escalation after year 1. The TCO must include both.
2. Vendor B says "unlimited" API calls but has a 1,000,000-call fair-use cap and an overage rate. The output must not describe the plan as unlimited without the cap.
3. Vendor B's SLA credit is the sole remedy and capped at 5%; the proposal also excludes third-party outages. The score must reflect the limited remedy, not only the 99.95% headline.
4. Vendor A fails the AU residency must-have. No price discount can cure a must-have failure.
5. Vendor B's SOC 2 report is unavailable before contract. Absence of evidence is UNKNOWN, not a pass and not a score of 1.
6. The evaluation lead has a declared financial interest in Vendor B. The recommendation must not present Vendor B as a clean winner.
7. The vendor-provided case studies are marketing, not independent references.
8. No purchase order, contract signature, vendor contact or payment is authorized.
