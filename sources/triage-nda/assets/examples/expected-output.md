# Expected output — triage-nda synthetic fixture

> Expected output shape. Based only on the supplied synthetic NDA and stated defaults; no model run, CLM or e-signature system was used. This is not legal advice and not an approval.

## NDA triage report

| Field | Value |
| --- | --- |
| Classification | **RED — significant issues** |
| Parties | Aster Bioworks, Inc. (synthetic, Delaware, US) and Kestrel Data Systems Ltd (synthetic, England, UK) |
| Type | Mutual NDA, standalone |
| Purpose | Evaluation of a potential data collaboration |
| Term | 3 years; confidentiality survives 7 years |
| Governing law / forum | New York law; courts in New York County, New York |
| User's side | Mutual (both disclosing and receiving) |
| Review basis | Market-standard defaults; no organization playbook was supplied |
| Signature block | Not supplied |
| Approver / delegation | Not supplied; not inferred |

## Screening results

| # | Criterion | Status | Clause | Note |
| ---: | --- | --- | --- | --- |
| 1 | Agreement structure | PASS | Preamble, clause 1 | Mutual, standalone agreement for a stated purpose |
| 2 | Definition of confidential information | **FAIL** | Clause 2.1 | Captures all information of any kind, marked or unmarked, including information that is or becomes public through no fault of the recipient |
| 3 | Obligations of the receiving party | PASS | Clauses 3.1-3.3 | Reasonable care, purpose limitation, need-to-know disclosure |
| 4 | Standard carveouts | **FAIL** | Clause 2.2 | Public knowledge, prior possession, third-party receipt and legal compulsion are present; independent development is missing |
| 5 | Permitted disclosures | PASS | Clause 3.3 | Employees, contractors, advisors and affiliates under similar obligations |
| 6 | Term and duration | FLAG | Clauses 5 and 8 | 3-year term is acceptable; 7-year survival is longer than the 5-year default but within a common market range |
| 7 | Return and destruction | FLAG | Clause 7 | Return/destroy on request; no retention exception for legal, regulatory or backup copies |
| 8 | Remedies | PASS | Clause 9 | Mutual equitable-relief acknowledgment; no liquidated damages |
| 9 | Problematic provisions | **FAIL** | Clauses 6 and 10 | 12-month employee non-solicitation; broad residuals clause permitting use for any purpose, including in products, with no trade-secret or patentable-information exclusion |
| 10 | Governing law and jurisdiction | PASS | Clause 11 | New York law and New York courts, consistently stated; no mandatory arbitration |

**Classification rule applied:** any FAIL → RED; otherwise any FLAG → YELLOW; otherwise GREEN. Three FAIL criteria are present, so the classification is **RED**.

## Issues found

### Issue 1 — RED: overbroad definition of confidential information

**Clause 2.1:** "Confidential Information means all information of any kind ... whether or not marked or identified as confidential, including information that is or becomes publicly available through no fault of the receiving Party."

**Risk:** The definition captures information the recipient cannot reasonably identify as confidential and even information that has become public. It could support a claim over independently developed or publicly known material and makes compliance difficult to evidence.

**Suggested fix:** Limit the definition to non-public information disclosed for the Purpose that is marked or identified as confidential at disclosure, or that a reasonable person would understand to be confidential from its nature and the circumstances. Keep the standard exclusions. If oral disclosures are included, allow written confirmation within a stated period (for example, 30 days).

### Issue 2 — RED: missing independent-development carveout

**Clause 2.2:** the carveouts cover public knowledge, prior possession, third-party receipt and legal compulsion, but not independent development.

**Risk:** The recipient may be unable to show that its own products, models or features were developed without reference to the discloser's information. This is especially material for a data-collaboration evaluation.

**Suggested fix:** Add: "information independently developed by the receiving Party without use of or reference to the disclosing Party's Confidential Information, as evidenced by written records."

### Issue 3 — RED: employee non-solicitation

**Clause 6:** "During the term and for twelve (12) months afterwards, neither Party will solicit for employment any employee of the other Party who was involved in the Purpose."

**Risk:** This is a restrictive covenant in an NDA. It restricts ordinary hiring, may be unenforceable or require jurisdiction-specific consideration, and does not belong in a confidentiality instrument under the default position.

**Suggested fix:** Delete clause 6. If the counterparty insists, narrow it to targeted solicitation (not general recruitment advertising), limit it to employees directly involved, set a short term (for example, 12 months), and have local counsel confirm enforceability.

### Issue 4 — RED: broad residuals clause

**Clause 10:** "Each Party may use for any purpose, including in its products and services, any general ideas, concepts, know-how or techniques retained in the unaided memory ... and nothing in this Agreement restricts that use or grants the other Party any right in it."

**Risk:** Although framed as residuals, the clause permits use "for any purpose, including in its products and services" and contains no exclusion for trade secrets or patentable information. It can operate as a broad permission to use the discloser's confidential information, undermining the confidentiality obligations.

**Suggested fix:** Delete clause 10. If residuals must be addressed, limit them to general ideas, concepts, know-how or techniques retained in the unaided memory of individuals who had authorized access; expressly exclude trade secrets and patentable information; state that no IP licence is granted; and do not permit use of identifiable confidential information.

### Issue 5 — YELLOW: seven-year survival

**Clause 8:** obligations in clauses 3 and 7 survive for seven years.

**Risk:** Longer than the stated five-year default. It may be commercially acceptable, but it should be a conscious decision, particularly for information that is not a trade secret.

**Suggested fix:** Confirm the business need. Reduce to five years unless the information includes trade secrets that justify longer protection, and then carve out trade secrets specifically.

### Issue 6 — YELLOW: no retention exception

**Clause 7:** return or destroy all copies on termination or request, with written confirmation.

**Risk:** The obligation may conflict with legal, regulatory, litigation-hold or bona fide backup retention requirements.

**Suggested fix:** Add a retention exception for copies required by law, regulation, litigation hold or bona fide backup/compliance policy, provided those copies remain subject to confidentiality.

## Separate framework flag — personal data

The stated collaboration may involve personal data of customers and employees, but the NDA contains no data-processing terms, no international transfer mechanism and no allocation of controller/processor roles. The UK counterparty and EU/UK data-protection law may require a data-processing agreement, standard contractual clauses or an adequacy mechanism.

This is a **separate compliance question**, not one of the ten NDA criteria. Do not treat a GREEN NDA classification as data-protection compliance. Escalate the data-protection question to the appropriate privacy or legal owner.

## Jurisdiction assumptions

| Assumption | Effect on this triage |
| --- | --- |
| New York law and New York courts | Stated consistently; no mandatory arbitration. New York law is a commonly used commercial choice; whether it is acceptable depends on the playbook. Local counsel should still review the restrictive covenant. |
| UK counterparty | UK GDPR may apply to personal data; the NDA has no data-protection terms. Employment non-solicitation enforceability is jurisdiction-specific. |
| Mutual obligations | The NDA is mutual; no unilateral-direction issue. |
| Trade secrets | The seven-year survival may be shorter than the protection available for trade secrets; a specific trade-secret carveout may be appropriate. |
| Signature authority | Not established by the document. The organization's delegation policy and the signatory's actual authority govern. |
| Mandatory law | Local employment, data-protection or competition law may override or supplement the contract; this guide does not determine that. |

## Recommendation

**Full legal review. Do not sign on the basis of this triage.**

The document has three FAIL criteria (four RED issues) and two YELLOW issues. The recommended path is:

1. Ask counsel to review clauses 2.1, 2.2, 6, 7, 8 and 10.
2. Consider the organization's standard-form NDA as a counterproposal, if one exists.
3. Resolve the data-protection question separately before any personal data is shared.
4. Have the authorized business and legal owners decide whether to negotiate, counterpropose or decline.

This guide does not approve, sign, route, send or negotiate anything. The approver and the delegation of authority were not supplied; do not name one.

## What would change the classification

If the definition were narrowed, an independent-development carveout added, the non-solicitation deleted, the residuals clause removed or narrowed, the survival reduced to a justified period and a retention exception added, the NDA would meet the GREEN criteria on the face of the document — **provided** the organization's actual playbook agrees, the data-protection question is resolved, and the authorized approver makes the decision. A future version must be re-triaged; this report does not pre-approve it.

## Missing facts

1. The complete executed-form document, including the signature block and any annexes.
2. Whether the organization has an NDA playbook and what it says about survival, residuals, non-solicitation and approval.
3. The identity and authority of the proposed signatory.
4. Whether personal data will actually be shared, and under what transfer mechanism.
5. Whether either party is subject to additional sector regulation or mandatory local rules.
6. Whether the parties intend the NDA to cover affiliates and contractors, and which entities they are.

## Adversarial check

If the NDA has no governing law, no forum and no signature block, record **jurisdiction: unknown** and **signature status: unknown**. Do not infer a jurisdiction, do not assert enforceability or compliance, and do not treat an unsigned draft as executed. The clause classification can still be RED or YELLOW, but the missing facts remain open and must be listed.

## Claim boundary

- This is a screening recommendation, not legal advice or a legal opinion.
- No clause was negotiated, redlined in the document, sent or routed.
- No approval, signature or authority is granted or implied.
- The analysis is based only on the supplied excerpt and stated defaults; a complete document or a playbook could change the result.
