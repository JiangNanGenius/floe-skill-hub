# Four small-business guide adaptations

Reviewed on 2026-11-05: `inventory-planner`, `cash-flow-snapshot`,
`grant-rfp-writer` and `job-post-builder`, each version `1.0.0`.

## Source and license

Source: [Anthropic knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins),
at the existing Hub pin `2574e29377c7173d0cecffef29a6ecbd7f8ccb5d`.
Each exact upstream SKILL.md was also compared with observed default-branch
head `d900840716eb262e1feb17c6f4406c9ce0e06bcf` and matched. Per-package
`references/PROVENANCE.md` records source hashes and actual path history.
The last content change is not inferred from repository-wide activity.

Repository metadata observed on this date: 34,788 stars, not archived,
last pushed 2026-11-04. Attention and activity informed selection; they do
not authorize tools or establish the quality of an individual workflow.

The applicable root `LICENSE` is Apache-2.0, with an unrelated trailing
fragment. Complete exact bytes are preserved, SHA-256
`a6946284993aeec75c7d75906064b66210c46051e562077efb30eb6dcfe72e26`.
No directory-level `small-business/LICENSE` or applicable NOTICE exists at
this pin. Only the Apache-2.0 text is relied on; the trailing fragment is
not an operational instruction. Modifications are explicitly recorded.

## Adaptation and permission boundary

All four packages are instruction-only: `scriptRuntime=none`, no tools,
no Python packages, no scripts/binaries/dependency declarations. Their only
declared capabilities are `workspace.read` and `workspace.write`. Existing
task authorization and prior user choices remain authoritative.

- Inventory retains 7/28-day demand, dated arrivals, reorder arithmetic and
  slow-stock review. Unknown lead times remain unknown; MOQ does not force
  a zero-demand purchase. Supplier/PO outputs remain workspace drafts.
- Cash-flow periods reconcile and carry balances forward. Explicit dated
  scenarios replace the upstream percentage-on-net confidence-band heuristic.
  A synthetic case proves that positive period-end cash can coexist with
  earlier payroll/payment shortfalls. No opening balance means net change only.
- Tender/grant work keeps eligibility, evidence mapping and evaluation weights.
  Missing evidence differs from confirmed failure; no portal monitoring,
  account registration, signature, submission or calendar writes are included.
- Hiring keeps the job post, interview-stage ownership and role-specific
  blank rubrics. Default legal offer terms, browser/DocuSign flows, actual
  applicant assessment, publishing and candidate contact are removed.

Upstream shared-plugin and reference-file dependencies are not runtime
dependencies of these adaptations. `reference/` is intentionally excluded
from automatic copying. All four exact source paths remain tracked by the
existing offline GitHub Actions updater; upstream changes still pass its
ordinary conflict/review gates and do not grant a new permission.

Synthetic examples and arithmetic were checked separately from any model
run. Source/package readback, policy validation, showcase validation and all
16 Android portable-guide projection tests passed. The live set expands
from 57 to 61 portable guide IDs; scripted/native exclusions, capability
ceiling and historical-feed byte checks remain intact.

The four source folders contain no official image assets. Their covers are
Floe-original AI-assisted illustrations, explicitly credited in showcase
metadata. Detailed bilingual descriptions, use cases and example inputs/
outputs accompany every entry.

This is static-content approval. It is not model execution, guest execution,
App installation, device acceptance or publication. Signatures and the
separate catalog publication step establish the actual distribution state.
