# Expected output — review-contract synthetic fixture

> Expected analysis shape, not a recorded execution result and not legal advice.

## Review basis

Playbook: the synthetic organization playbook above. Contract: synthetic Helio Cloud Systems vendor paper. User side: customer/buyer. No CLM or connector was used.

## Key findings

1. **RED — no data processing agreement.** The contract permits processing of personal data with only "commercially reasonable security measures" and no DPA, sub-processor terms, breach-notification timeline or cross-border mechanism. The playbook requires a DPA and 72-hour breach notification.
2. **RED — unilateral "any breach" indemnity.** Clause 3 is one-way in Customer's favour (which helps this buyer) but covers "any breach," making it uncapped and disconnected from the liability cap. The playbook requires mutual IP/data-breach indemnity and excludes "any breach."
3. **YELLOW — liability cap at 3 months.** The cap is below the 12-month playbook standard. The carveout is narrow, which is good, but the cap amount is materially lower than standard.
4. **YELLOW — 60-day auto-renewal notice.** The playbook requires 90 days. A 60-day window creates a renewal trap.
5. **YELLOW — net 45 payment.** The playbook standard is net 30; confirm whether the extra 15 days is intentional.
6. **YELLOW — no termination for convenience.** The playbook allows either party to terminate on 60 days' notice; the contract only allows termination for material breach.

## Clause table (provided excerpt)

| Clause | Contract says | Playbook position | Rating | Priority | Business impact | Redline direction |
|---|---|---|---|---|---|---|
| Limitation of liability | Cap = 3 months of fees; narrow carveouts | 12 months; fraud/wilful misconduct/injury only | YELLOW | Should-have | Lower recovery if vendor causes a material incident | Raise cap to 12 months; keep mutual |
| Indemnification | Vendor indemnifies Customer for "any breach" | Mutual IP infringement and data breach; no "any breach" | RED | Must-have | Broad but one-sided; may be rejected or litigated; does not cure data-protection gap | Make mutual; limit to third-party IP/data-breach claims; tie to cap |
| Data protection | No DPA; reasonable security only | DPA required; 72-hour breach notice | RED | Must-have | Regulatory and customer-notification exposure | Add DPA with breach notice, sub-processors, deletion and transfer terms |
| Auto-renewal | 60 days' notice | 90 days | YELLOW | Nice-to-have | Missed window locks in another 12 months | Change to 90 days; add renewal reminder |
| Payment | Net 45 | Net 30 | YELLOW | Nice-to-have | 15 days of extra working capital for vendor | Confirm intent; negotiate net 30 or a price offset |
| Termination | Material breach only, 30-day cure | Convenience on 60 days | YELLOW | Should-have | Customer cannot exit without cause | Add termination for convenience on 60 days |
| Governing law | Delaware | Delaware acceptable | GREEN | None | No action | None |

Auto-renewal and termination are two sub-issues of the single **Term & Termination** category, so these seven rows cover six of the twelve categories.

## Categories not present in the provided excerpt

The input is a contract excerpt, so the following six upstream checklist categories are not in the supplied text. Request the full agreement before treating any of them as absent from the actual contract. They are listed here so the review covers all 12 categories rather than silently skipping them.

| Clause | Provided excerpt | Playbook position | Rating | Priority | Business impact | Redline direction |
|---|---|---|---|---|---|---|
| IP ownership | Not in excerpt | No playbook position supplied | ABSENT FROM EXCERPT | Must-have (define) | Pre-existing and developed IP rights are unallocated in the text provided | Request the full contract; define ownership, licence scope and feedback rights |
| Confidentiality | Not in excerpt | No playbook position supplied | ABSENT FROM EXCERPT | Should-have | Confidential information handling is unaddressed in the text provided | Request the full contract; add mutual confidentiality, term and return/destruction terms |
| Representations & warranties | Not in excerpt | No playbook position supplied | ABSENT FROM EXCERPT | Should-have | No stated basis for contractual assurances or their survival | Request the full contract; add scoped reps, disclaimers and survival |
| Insurance | Not in excerpt | No playbook position supplied | ABSENT FROM EXCERPT | Nice-to-have | No coverage requirement or evidence obligation in the text provided | Request the full contract; add coverage minimums and certificates |
| Assignment | Not in excerpt | No playbook position supplied | ABSENT FROM EXCERPT | Should-have | Change-of-control and assignment consent are unresolved in the text provided | Request the full contract; add consent and change-of-control terms |
| Force majeure | Not in excerpt | No playbook position supplied | ABSENT FROM EXCERPT | Should-have | Excused-performance scope, notice and termination rights are unknown | Request the full contract; add scope, notice and long-stop termination |

## Negotiation strategy

- **Tier 1 (must-have):** DPA and data-breach terms; clarify that the "any breach" indemnity does not create an uncapped exposure the business cannot accept.
- **Tier 2 (should-have):** liability cap at 12 months; termination for convenience.
- **Tier 3 (concession candidates):** payment terms and renewal notice, if the vendor trades something material.

## Next steps

1. Obtain the vendor's DPA or ask for one; do not process personal data without it.
2. Ask counsel to review the indemnity and liability interaction before signature.
3. Confirm the business owner accepts the renewal and payment positions.
4. Do not sign, send or route anything from this guide.

## Acceptance checks

- All 12 upstream clause categories are addressed: six are analysed from the excerpt and six are explicitly marked as not present in the excerpt, with a request for the full contract.
- Every YELLOW/RED has current language, a proposed direction and a priority.
- The review basis and "not legal advice" disclaimer are visible.
- No claim that the contract is approved or executable.
