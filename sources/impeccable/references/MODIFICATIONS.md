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
- Launcher `scripts/floe-impeccable.sh` (e1760fb8a6b75e63c33d26969ad799c4ae7143a88a582ae29cac5dcde4cb222f):
  default `IMPECCABLE_SKILL_DIR` is now the engine-data root (explicit value
  wins; dev-checkout fallback). Resolution, digest gate and no-download
  behaviour are unchanged (b317617bb9f473a4d80b3477543d015f8d7d2645f63f0998acbce43bcbf58cc4 was the parent bytes).
- Moved below `references/`: upstream `LICENSE`, `NOTICE.md`, the source lock,
  the modification record, a Floe license note, and the new
  `PROVENANCE.md`. The maintenance normalizer left the installed package.
- Added `references/engine-dependency.json`: byte-identical copy of the frozen
  managed runtime artifact descriptor v1 (cec4a7fade52f6383f74bc9e15972b911552b2672eada138d890e353899be50a).

Upstream pin: `4fc2f83e1c8710dba772bfd4523d0efab57737b6` / `1363fadfb2141db1cf22b4ba171d6fc4dbf5cd72`; engine `0.1.17`;
upstream package `4.7.1`. Five references remain excluded by
design (live, live-setup, hooks, component-review, doctor) and one command
(`live`) dropped from the metadata — see `MODIFICATIONS.json`.
