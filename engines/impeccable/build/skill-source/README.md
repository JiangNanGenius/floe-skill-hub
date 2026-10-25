# Canonical Impeccable skill-source regeneration — public maintenance tooling

Committed maintenance tooling for the Hub package `sources/impeccable/`
(skill `impeccable` 1.0.0, derived from `pbakaus/impeccable` commit
`4fc2f83e1c8710dba772bfd4523d0efab57737b6` / tree
`1363fadfb2141db1cf22b4ba171d6fc4dbf5cd72`, engine `0.1.17+floe.1.0.0`).
None of this code ships inside the installed package, and no tool here ever
writes into the hub; the hub tree is read strictly read-only.

## The regeneration command

    sh <hub>/engines/impeccable/build/skill-source/run_pipeline.sh \
       <pinned-upstream-clone-dir> <hub-root> <new-empty-work-root>

* `<pinned-upstream-clone-dir>` — clean git checkout at exactly the pinned
  commit AND tree above, with no tracked or untracked drift (verified
  fail-closed before anything is written).
* `<hub-root>` — floe-skill-hub root. Required inputs:
  `engines/impeccable/ENGINE-LOCK.json`,
  `engines/impeccable/runtime-dependency/descriptor.v1.json`,
  `catalog/skills.json`, `scripts/hubcore.py`, `scripts/build_packages.py`.
* `<new-empty-work-root>` — a fresh, caller-owned output directory outside
  the hub and outside the clone. Created if absent.

Outputs under the work root: `staging/sources/impeccable` (stage 1),
`canonical/` (the candidate `sources/impeccable` bytes — 50 files),
`gate/` (isolated helper gate mirror), `report-stage1.json`,
`report-stage2.json`, `report-gate.json`, `pipeline-summary.json` and the
`FLOE-IMPECCABLE-WORKROOT.json` ownership sentinel.

Adoption into `<hub>/sources/impeccable` is deliberately manual: review with
`diff -r <hub>/sources/impeccable <work-root>/canonical`, then copy by hand
if accepted. The command never performs that copy and never touches
`<hub>/packages`.

## Non-destructive guarantees

* An existing non-empty work root without the sentinel is REFUSED — foreign
  content is never overwritten or deleted.
* Re-running into a previously claimed root is REFUSED until the sentinel is
  modified (`"allowReplace": true`); even then only the sentinel's own
  fixed owned children (`staging`, `canonical`, `gate`, the three reports and
  `pipeline-summary.json`) are replaced — and the acknowledgement is one-time
  (the driver re-arms the sentinel).
* Stage tools independently refuse a non-empty `--out`; none of them deletes
  existing output. The gate refuses a non-empty `<work>/gate/ziproot`.
* A work root resolving inside the hub tree or the clone is refused; symlink
  roots are refused; symlinks inside the candidate package are refused.
* No tool reads or writes any location outside the three explicit arguments.

## Files

| File | Role |
| --- | --- |
| `run_pipeline.sh` | the public regeneration driver (stage1 → stage2 → gate → summary) |
| `stage1_normalize_skill_source.py` | stage 1 normalizer of the pinned upstream `skill/` tree |
| `build_canonical_package.py` | stage 2 canonicalizer producing the exact package bytes, including `SOURCE-LOCK.json` / `MODIFICATIONS.{json,md}` / `PROVENANCE.md` |
| `gate_check.py` | authoritative Hub consumer gate: mirrors `<hub>/scripts` and `<hub>/catalog` byte-for-byte into an isolated mirror and runs `hubcore.validate_package_files` / `check_archive_bytes` / `make_zip` / `content_digest` plus `build_packages.py` (build + `--check`) unchanged |
| `impeccable-launcher-parent` | frozen launcher build input (sha256 `b317617bb9f473a4d80b3477543d015f8d7d2645f63f0998acbce43bcbf58cc4`) consumed by stage 2; the canonical launcher bytes in the package are its documented rewrite output |

## Gate authority notes

* The gate never re-implements package limits: the unchanged 128-file /
  2 MiB / 8 MiB limits, require-notice licensing, frontmatter/manifest
  contract, script-runtime rules, path safety and native-payload rejection
  all come from the copied authoritative helpers.
* When the mirrored helper set contains `runtime_dependency.py` (the H6
  known-component same-tree binding), the gate also mirrors
  `engines/impeccable/runtime-dependency` and `engines/impeccable/dist` into
  the isolated root so `build_packages.py` binds the embedded descriptor
  against the same tree — still read-only over the hub.
* `registry minimumAppVersion` is cross-checked against the frozen
  descriptor value (data-driven), not a hardcoded literal.
* `gate_result`/`report-gate.json` discloses `helperSource` (hub HEAD commit,
  uncommitted helper drift, per-helper SHA-256) so a validation run can be
  attributed to an exact helper snapshot. The frozen committed-snapshot
  validation used hub HEAD `09143b2`; final integration re-runs against H6
  latest.

## Reproducibility

Two fresh work roots against the same pin produce byte-identical `canonical/`
output (per-file SHA-256 inventories in `pipeline-summary.json`). The
package-internal provenance (`references/SOURCE-LOCK.json` `regenerate`,
`MODIFICATIONS.json`, `PROVENANCE.md`) points at exactly the command above.
No native binary is ever executed by these tools on the host, and none enters
the package.
