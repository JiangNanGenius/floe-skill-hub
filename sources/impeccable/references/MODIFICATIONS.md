# Modification record — canonical Floe Impeccable package

Stage 1 (normalize) records are embedded verbatim in `MODIFICATIONS.json`
(`skillFile`, `commandMetadata`, `acceptedReferences`, `excludedReferences`).
Stage 2 (canonicalize) changed, per file counts in `canonicalization`:

- SKILL.md: 5 explicit launcher-path tokens renamed to
  `floe-impeccable.sh`; 32 accepted `reference/*.md` links rewritten to
  `references/engine-data/reference/*.md`; 3 excluded-reference
  links annotated in place; 0 bare dangling links annotated; two
  prose corrections applied; the installed-layout mapping inserted; the
  frontmatter reduced to `name` + `description` (provider `allowed-tools`,
  `argument-hint`, `user-invocable`, `license` removed).
- `references/engine-data/`: read-only mirror the unchanged engine expects
  (`SKILL.md`, `VERSION`, 36 `reference/*.md`, `scripts/command-metadata.json`
  with 23 commands). Per-file stage-2 counts in `MODIFICATIONS.json`.
- Launcher `scripts/floe-impeccable.sh` (227161bd43a09b05cb949e5750c1037ca34e06968f9ed3979052bbb1d3f8a1b8):
  default `IMPECCABLE_SKILL_DIR` is now the engine-data root (explicit value
  wins; dev-checkout fallback). Resolution, digest gate and no-download
  behaviour are unchanged (b317617bb9f473a4d80b3477543d015f8d7d2645f63f0998acbce43bcbf58cc4 was the parent bytes).
  The same transform applies the Floe default scan policy: `snapshot-scan`
  gains `--no-timeout` only when the caller chose no timeout flag; explicit
  `--timeout-ms` (including `0`), the `--timeout-ms=` form and explicit
  `--no-timeout` pass through, the engine keeps refusing the mutual exclusion,
  and the raw CLI default and all caps are unchanged.
- Moved below `references/`: upstream `LICENSE`, `NOTICE.md`, the source lock,
  the modification record, a Floe license note, and the new
  `PROVENANCE.md`. The maintenance normalizer left the installed package.
- Added `references/engine-dependency.json`: byte-identical copy of the frozen
  managed runtime artifact descriptor v1 (e7c7984a573b5ac9a1447bcc4285d9b1ba09458033f8468f5c86961965e57233).

Upstream pin: `4fc2f83e1c8710dba772bfd4523d0efab57737b6` / `1363fadfb2141db1cf22b4ba171d6fc4dbf5cd72`; engine `0.1.17`;
upstream package `4.7.1`. Five references remain excluded by
design (live, live-setup, hooks, component-review, doctor) and one command
(`live`) dropped from the metadata — see `MODIFICATIONS.json`.
