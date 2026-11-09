# Attribution and adaptation

Adapted from Anthropic knowledge-work-plugins at `e050c2ec856373787143d7057663a6ebd1277df3`, Apache-2.0.
Source: https://github.com/anthropics/knowledge-work-plugins/blob/e050c2ec856373787143d7057663a6ebd1277df3/sales/skills/handle-objection/SKILL.md
Source SHA256: `88d2da6cd89218459271ab6159ef981b88b6f763148b3955b56277d30acc4e19`; Git blob: `3c66962f9c87a8e9a2769556f49f04f3043a0098`.

Floe changes:
- Works directly from supplied files/text; mandatory live connector checks, CRM schemas and external host rendering removed.
- No CRM change, email send, scheduled action, credential access or dependency on other skills.
- Preserves concern classification, grounded response, evidence traceability and constructive next question.
- Separates internal hypotheses/confidential evidence from the customer-facing draft; no invented ROI, discounts, competitor features, compliance or win rates.

The exact root LICENSE bytes are retained in UPSTREAM-LICENSE.txt. Its unrelated trailing fragment is preserved as source data and is never an instruction. For handle-objection the applicable sales/LICENSE is additionally preserved in UPSTREAM-SALES-LICENSE.txt. The pinned tree has no applicable NOTICE file in these source ancestors. Source hashes and inspected reference files are recorded in SOURCE-PINS.json. Referenced upstream connector/shared resources are neither runtime dependencies nor silently fetched: the adapted instructions are self-contained.

Two visible skill-path commits, 2026-09-15 and 2026-10-21; the latter adds source traceability. Repository attention is not per-skill adoption evidence.

account-plan and deal-review cover wider account/deal strategy; this focuses on a single objection, a short reply, evidence eligibility and unsupported-claim checks.

These are private publication candidates. Archive validation does not establish signed review, store availability, App integration or real user outcome. Minimum App version must be confirmed by mainline; no older-client compatibility branch is added.
