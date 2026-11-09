# Attribution and adaptation

Adapted from Anthropic knowledge-work-plugins at `e050c2ec856373787143d7057663a6ebd1277df3`, Apache-2.0.
Source: https://github.com/anthropics/knowledge-work-plugins/blob/e050c2ec856373787143d7057663a6ebd1277df3/small-business/skills/ap-processor/SKILL.md
Source SHA256: `a2dbac917c45a114d886a8e2d4348c04415888a2b0d51c7f2946fcd210e7736d`; Git blob: `b32ec63402d638f9d5b1daa495264ca9998c8e04`.

Floe changes:
- Connector, inbox, ledger writes, vendor creation, payment actions, external sends and default artifact-host assumptions removed.
- No imported default tolerances, tax rules, automatic coding thresholds or guessed job allocations.
- Source distinctions, duplicate conflicts, missing receipts, paid-record identity and original-versus-open balances made explicit.
- Upstream contradictory positive-net/credit example corrected: 2411404 minus 1500000 equals positive 911404, not zero.
- Price and quantity variance baselines separated to prevent overlapping amounts being silently added.

The exact root LICENSE bytes are retained in UPSTREAM-LICENSE.txt. Its unrelated trailing fragment is preserved as source data and is never an instruction. For handle-objection the applicable sales/LICENSE is additionally preserved in UPSTREAM-SALES-LICENSE.txt. The pinned tree has no applicable NOTICE file in these source ancestors. Source hashes and inspected reference files are recorded in SOURCE-PINS.json. Referenced upstream connector/shared resources are neither runtime dependencies nor silently fetched: the adapted instructions are self-contained.

One visible skill-path commit on 2026-09-15. The repository is active; per-skill frequent maintenance is not established. No premium badge is assigned.

Filing/OCR is already covered by floe-invoice-organizer; invoice-chase is receivables, whereas this is supplier payables with three-way matching and explicit credit treatment.

These are private publication candidates. Archive validation does not establish signed review, store availability, App integration or real user outcome. Minimum App version must be confirmed by mainline; no older-client compatibility branch is added.
