---
name: triage-nda
description: Screen an incoming NDA against a supplied playbook; classify GREEN, YELLOW or RED with clause reasons, missing facts and a routing recommendation. Guide-only; not legal advice and no signature authority.
---

# NDA Triage

## Floe guide adaptation (read first)

- Adapted for Floe from the Apache-2.0 upstream skill recorded in `references/PROVENANCE.md`; the screening criteria, GREEN/YELLOW/RED model, issue library and report shape are retained.
- Bring the NDA as a workspace file (PDF, DOCX, Markdown or plain text) or pasted text, plus the organization's NDA playbook if available. No e-signature, CLM, CRM, cloud-storage or email connection is used or implied.
- The output is a workspace document: a triage report with a classification, criterion-level results, issues, suggested fixes and a routing **recommendation**. It is not an approval, a legal opinion, a signature or a routing action.
- This is a legal workflow aid, not legal advice. A qualified legal professional must review the analysis before reliance, negotiation or signature. The user's organization decides who may approve or sign an NDA; this guide never assumes or grants that authority.

**Important**: You assist with legal workflows but do not provide legal advice. All analysis should be reviewed by qualified legal professionals before being relied upon.

Rapidly triage incoming NDAs against standard screening criteria. Classify the NDA for the user's routing decision: standard-approval candidate, counsel review, or full legal review.

## Input contract

| Input | Required | Notes |
| --- | --- | --- |
| NDA text or file | Yes | Workspace file or pasted text; a link is not fetched by this guide |
| User's side | Yes | Disclosing, receiving, mutual, or not yet known |
| Business context | If available | Exploratory discussion, vendor onboarding, M&A, employment, etc. |
| Organization playbook | Recommended | Standard positions, carveouts, prohibited terms, approval matrix |
| Governing-law expectations | If available | Preferred and acceptable jurisdictions |
| Deadline | If available | Affects escalation, not the legal analysis |
| Approver / routing rules | If available | Names or roles, not inferred |

If the NDA is embedded in a larger agreement, say so. If only part of the document is supplied, mark the analysis as partial and request the complete agreement.

## Workflow

### Step 1: Accept the NDA

Accept the NDA as:

- A workspace file already attached to the task (PDF, DOCX, Markdown or plain text).
- Pasted text.

If no NDA is provided, ask for it. Do not fetch an external URL, open a cloud-storage link, or read outside the task workspace; ask the user to attach or paste the relevant text instead.

### Step 2: Load the NDA playbook

Look for the NDA screening criteria in the task workspace: a file the user names, or `nda-playbook.md`. The playbook should define:

- Mutual vs unilateral requirements.
- Acceptable agreement term and survival periods.
- Required carveouts.
- Prohibited provisions.
- Organization-specific requirements.
- Approval and escalation rules, including who may sign.

**If no NDA playbook is configured:**

- Proceed with market-standard defaults and say so.
- Do not describe the defaults as the organization's policy or as legal advice.
- Defaults applied:
  - Mutual obligations are preferred unless the organization is only disclosing.
  - Term: 2-3 years is common; up to 5 years may be appropriate for trade secrets.
  - Standard carveouts: independently developed, publicly available, rightfully received from a third party, required by law.
  - No non-solicitation or non-compete provisions.
  - No residuals clause, or one narrowly scoped to unaided memory and excluding trade secrets and patentable information.
  - Governing law in a reasonable commercial jurisdiction.
- State every default used and mark it as a default rather than a policy position.

### Step 3: Quick screen

Evaluate the NDA against each criterion. Use PASS, FLAG or FAIL, and quote the clause or state "not present in the supplied text".

#### 1. Agreement structure

- [ ] **Type identified:** mutual NDA, unilateral (disclosing party), or unilateral (receiving party).
- [ ] **Appropriate for context:** mutual for exploratory discussions; unilateral for one-way disclosures.
- [ ] **Standalone agreement:** confirm the NDA is a standalone agreement, not a confidentiality section embedded in a larger commercial agreement.

#### 2. Definition of confidential information

- [ ] **Reasonable scope:** not overbroad (avoid "all information of any kind whether or not marked as confidential").
- [ ] **Marking requirements:** if marking is required, is it workable? Written marking within 30 days of oral disclosure is common.
- [ ] **Exclusions present:** standard exclusions defined (see step 4).
- [ ] **No problematic inclusions:** public information or independently developed materials are not defined as confidential.

#### 3. Obligations of the receiving party

- [ ] **Standard of care:** reasonable care, or at least the same care as for its own confidential information.
- [ ] **Use restriction:** limited to the stated purpose.
- [ ] **Disclosure restriction:** limited to those with a need to know who are bound by similar obligations.
- [ ] **No onerous obligations:** no impractical requirements (for example, encrypting all communications or maintaining physical logs) unless the policy requires them.

#### 4. Standard carveouts

All of the following should be present:

- [ ] **Public knowledge:** information that is or becomes publicly available through no fault of the receiving party.
- [ ] **Prior possession:** information already known to the receiving party before disclosure.
- [ ] **Independent development:** information independently developed without use of or reference to the confidential information.
- [ ] **Third-party receipt:** information rightfully received from a third party without restriction.
- [ ] **Legal compulsion:** the right to disclose when required by law, regulation or legal process, with notice to the disclosing party where legally permitted.

#### 5. Permitted disclosures

- [ ] **Employees:** can share with employees who need to know.
- [ ] **Contractors/advisors:** can share with contractors, advisors and professional consultants under similar confidentiality obligations.
- [ ] **Affiliates:** can share with affiliates if needed for the business purpose.
- [ ] **Legal/regulatory:** can disclose as required by law or regulation.

#### 6. Term and duration

- [ ] **Agreement term:** reasonable for the business relationship (1-3 years is common).
- [ ] **Confidentiality survival:** obligations survive for a reasonable period after termination (2-5 years is common; trade secrets may be longer).
- [ ] **Not perpetual:** avoid indefinite or perpetual confidentiality obligations, except where a trade secret justifies longer protection.

#### 7. Return and destruction

- [ ] **Obligation triggered:** on termination or on request.
- [ ] **Reasonable scope:** return or destroy confidential information and all copies.
- [ ] **Retention exception:** allows retention of copies required by law, regulation or internal compliance/backup policy.
- [ ] **Certification:** certification of destruction may be reasonable; a sworn affidavit is onerous.

#### 8. Remedies

- [ ] **Injunctive relief:** acknowledgment that breach may cause irreparable harm and equitable relief may be appropriate is common.
- [ ] **No pre-determined damages:** avoid liquidated-damages clauses in NDAs.
- [ ] **Not one-sided:** remedies apply equally in a mutual NDA.

#### 9. Problematic provisions to flag

- [ ] **No non-solicitation:** the NDA should not contain employee non-solicitation provisions.
- [ ] **No non-compete:** the NDA should not contain non-compete provisions.
- [ ] **No exclusivity:** the NDA should not restrict either party from entering similar discussions with others.
- [ ] **No standstill:** no standstill or similar restrictive provision unless the M&A context justifies it.
- [ ] **No residuals clause, or narrowly scoped:** if present, limit it to information retained in the unaided memory of individuals and exclude trade secrets and patentable information.
- [ ] **No IP assignment or license:** the NDA should not grant intellectual-property rights.
- [ ] **No audit rights:** unusual in a standard NDA.

#### 10. Governing law and jurisdiction

- [ ] **Reasonable jurisdiction:** a well-established commercial jurisdiction.
- [ ] **Consistent:** governing law and jurisdiction are in the same or related jurisdictions.
- [ ] **No mandatory arbitration in a standard NDA:** litigation is commonly preferred for NDA disputes, but this is a policy choice, not a legal rule.

### Step 4: Classify

The classification is a recommendation against the supplied playbook or stated defaults. It is not an approval decision.

#### GREEN — standard-approval candidate

All of the following are true:

- The NDA is mutual, or unilateral in the appropriate direction.
- All standard carveouts are present.
- The term is within the standard range (1-3 years, survival 2-5 years), or the playbook allows the stated term.
- No non-solicitation, non-compete or exclusivity provisions.
- No residuals clause, or the residuals clause is narrowly scoped.
- A reasonable governing-law jurisdiction.
- Standard remedies (no liquidated damages).
- Permitted disclosures include employees, contractors and advisors.
- Return/destruction includes a retention exception for legal/compliance.
- The definition of confidential information is reasonably scoped.

**Recommended routing:** present it to the approver the playbook designates, under those delegation rules. This guide does not approve, sign or route it. If the playbook says counsel must review a GREEN NDA, follow the playbook.

#### YELLOW — counsel review recommended

One or more of the following are present, but the NDA is not fundamentally problematic:

- The definition of confidential information is broader than preferred but not unreasonable.
- The term is longer than standard but within the market range (for example, 5 years for the agreement term, 7 years for survival).
- One standard carveout is missing but could be added without difficulty.
- A residuals clause is present but narrowly scoped to unaided memory.
- Governing law is in an acceptable but non-preferred jurisdiction.
- Minor asymmetry in a mutual NDA.
- Marking requirements are present but workable.
- Return/destruction lacks an explicit retention exception (it may be implied, but should be added).
- Unusual but non-harmful provisions (for example, a duty to notify of a potential breach).

**Recommended routing:** flag the specific issues for counsel review; counsel can likely resolve them in one review pass. The guide does not contact counsel or send anything.

#### RED — significant issues

One or more of the following are present:

- Unilateral when mutual is required, or the wrong direction for the relationship.
- Missing critical carveouts (especially independent development or legal compulsion).
- Non-solicitation or non-compete provisions embedded in the NDA.
- Exclusivity or standstill provisions without appropriate business context.
- Unreasonable term (10+ years, or perpetual without a trade-secret justification).
- Overbroad definition that could capture public information or independently developed materials.
- Broad residuals clause that effectively creates a licence to use confidential information.
- IP assignment or licence grant hidden in the NDA.
- Liquidated damages or penalty provisions.
- Audit rights without a reasonable scope or notice requirement.
- A highly unfavourable jurisdiction with mandatory arbitration.
- The document is not actually an NDA (it contains substantive commercial terms, exclusivity or other obligations beyond confidentiality).

**Recommended routing:** full legal review. Do not sign. The authorized business and legal owners decide whether to negotiate, send the organization's standard form or reject. The guide does not make that decision.

### Step 5: Generate the triage report

```
## NDA Triage Report

**Classification**: [GREEN / YELLOW / RED]
**Parties**: [party names]
**Type**: [Mutual / Unilateral (disclosing) / Unilateral (receiving)]
**Term**: [duration]
**Governing law**: [jurisdiction]
**Review basis**: [Playbook file / Default standards]
**Your side**: [disclosing / receiving / mutual / not stated]

## Screening results

| Criterion | Status | Notes |
| --- | --- | --- |
| Mutual obligations | PASS/FLAG/FAIL | [details] |
| Definition scope | PASS/FLAG/FAIL | [details] |
| Term | PASS/FLAG/FAIL | [details] |
| Standard carveouts | PASS/FLAG/FAIL | [details] |
| [etc.] |  |  |

## Issues found

### [Issue 1 — YELLOW/RED]
**What**: [description]
**Risk**: [what could go wrong]
**Suggested fix**: [specific language or approach]

[Repeat for each issue]

## Recommendation

[Specific next step: present to the approver the playbook designates, send for counsel review, or recommend full review/counterproposal. State that the decision and signature belong to the authorized person.]

## Next steps

1. [Action item]
2. [Action item]
```

### Step 6: Routing recommendation (not routing)

| Classification | Recommended action | Typical timeline (information only) |
| --- | --- | --- |
| GREEN | Present to the approver the playbook designates | Same day, if the playbook allows |
| YELLOW | Send to the designated reviewer with specific issues flagged | 1-2 business days |
| RED | Full legal review; prepare a counterproposal or use the standard form | 3-5 business days |

For YELLOW and RED:

- Identify the role that should review, only if the playbook supplies it.
- Summarize the issues so the reviewer can see the key points quickly.
- If the organization has a standard-form NDA, recommend it as a counterproposal option; do not send it yourself.

**Do not** state that an NDA is approved, signed, executed, routed or cleared because of this guide. Do not fill in an approver name that was not supplied. Do not imply that a GREEN classification permits signature.

## Jurisdiction and framework assumptions

NDA law and enforceability vary by jurisdiction. This guide screens commercial terms; it does not determine legal validity. State these assumptions in the report:

- **Governing law stated in the NDA** and the **forum** for disputes. If they differ, flag it.
- **Party locations and applicable mandatory law.** For example, employees in the EU/UK may have mandatory rights that override confidentiality wording; local employment or data-protection law may require additional terms.
- **Data protection:** if personal data is disclosed, a data-processing agreement or addendum may be required under GDPR, UK GDPR or other regimes. The NDA alone may not be sufficient.
- **Trade secrets:** trade-secret protection may be perpetual or longer than the general survival period, depending on the jurisdiction and the measures taken.
- **Restrictive covenants:** non-solicitation and non-compete enforceability varies widely; flag them rather than assuming they are valid or void.
- **Sanctions, export control and anti-bribery:** out of scope; flag if the counterparty or subject matter raises them.
- **Signature authority:** governed by the organization's delegation policy and the signatory's actual authority, not by this guide.

If the NDA chooses a jurisdiction the reviewer does not know, recommend local counsel rather than guessing.

## Common NDA issues and standard positions

### Issue: overbroad definition of confidential information

**Standard position:** confidential information should be limited to non-public information disclosed in connection with the stated purpose, with clear exclusions.
**Redline approach:** narrow the definition to information that is marked or identified as confidential, or that a reasonable person would understand to be confidential given the nature of the information and the circumstances of disclosure.

### Issue: missing independent-development carveout

**Standard position:** include a carveout for information independently developed without reference to or use of the disclosing party's confidential information.
**Risk if missing:** could create claims that internally developed products or features were derived from the counterparty's confidential information.
**Redline approach:** add the standard independent-development carveout.

### Issue: non-solicitation of employees

**Standard position:** non-solicitation provisions do not belong in NDAs; they are appropriate, if at all, in employment, M&A or specific commercial agreements.
**Redline approach:** delete the provision. If the counterparty insists, limit it to targeted solicitation (not general recruitment) and a short term (for example, 12 months), subject to local law.

### Issue: broad residuals clause

**Standard position:** resist residuals clauses. If required, limit them to general ideas, concepts, know-how or techniques retained in the unaided memory of individuals who had authorized access; exclude trade secrets and patentable information; do not grant an IP licence.
**Risk if too broad:** effectively grants a licence to use the disclosing party's confidential information for any purpose.

### Issue: perpetual confidentiality obligation

**Standard position:** 2-5 years from disclosure or termination, whichever is later; trade secrets may warrant protection for as long as they remain trade secrets.
**Redline approach:** replace the perpetual obligation with a defined term and add a trade-secret carveout where appropriate.

## Floe output contract

A synthetic input is in [`assets/examples/input.md`](assets/examples/input.md), its machine-readable screening data is in [`assets/examples/figures.json`](assets/examples/figures.json), and the expected output shape is in [`assets/examples/expected-output.md`](assets/examples/expected-output.md); all are test fixtures, not executed results and not legal advice.

1. State the parties, the user's side, the document type, the governing law, the forum, the signature status, the review basis (named playbook or defaults) and any missing document sections. If governing law, forum or signature status is absent, record UNKNOWN; do not infer it.
2. Apply all 10 screening criteria; mark absent clauses as "not present in the supplied text", not as compliant.
3. Classify GREEN, YELLOW or RED using the stated decision rule, and show which criteria drove the result.
4. For each YELLOW or RED issue, quote the clause, explain the risk and give a specific suggested fix.
5. Provide a routing recommendation naming a role only when the playbook supplies it. Do not invent an approver, a delegation of authority or a signature.
6. State the jurisdiction and framework assumptions that could change the analysis.
7. End with the questions a qualified lawyer must answer before reliance.
8. Never state that the NDA is approved, signed, executed, standard, compliant or safe to sign.

## Scope and limitations

- Works only from the supplied NDA and playbook; it does not search a CLM, e-signature system, CRM, email or cloud storage.
- Does not provide legal advice, a legal opinion or a validity/enforceability conclusion.
- Does not negotiate, redline the actual document, send anything or route anything.
- Does not assess tax, sanctions, export control, anti-bribery, data-protection compliance or corporate authority.
- If the document is incomplete or the user's side is unknown, the output must say so; a classification on incomplete facts is provisional.
