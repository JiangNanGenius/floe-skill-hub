# Provenance: Floe Impeccable canonical skill package

Derived from `pbakaus/impeccable` commit `4fc2f83e1c8710dba772bfd4523d0efab57737b6` (tree `1363fadfb2141db1cf22b4ba171d6fc4dbf5cd72`),
engine version `0.1.17`, upstream skill package version
`4.7.1`; Apache-2.0 (see `licenses/`). Pin authority: hub
`docs/UPSTREAM-PINS.json`. Two reproducible stages produce every byte (the
maintenance tooling is committed Hub code under
`engines/impeccable/build/skill-source/`; `SOURCE-LOCK.json` records the
exact public regeneration command; nothing here was hand-edited):

1. **normalize** (`engines/impeccable/build/skill-source/stage1_normalize_skill_source.py`,
   the parent-lane normalizer with portability fixes): resolves upstream template
   placeholders for the Floe provider, rewrites `impeccable`/`npx impeccable`
   invocations to the Floe launcher, adds the per-file Floe surface notes,
   accepts 36 references, excludes 5 (live, live-setup, hooks, component-review,
   doctor), keeps the 23 engine-carriable commands in `command-metadata.json`.
2. **canonicalize** (this pipeline): normalizes the SKILL.md frontmatter to
   `name`+`description` scalars, renames the launcher to
   `scripts/floe-impeccable.sh` (the remote-runtime script rule), points every
   explicit path at the canonical name, rewrites accepted `reference/*.md` links
   to `references/engine-data/reference/*.md` (the actual installed paths),
   annotates links to excluded references, inserts the installed-layout
   mapping, replaces the launcher sentence with the managed-provisioning truth,
   applies the Floe default scan policy to the launcher (`snapshot-scan` appends
   `--no-timeout` only when the caller chose no timeout flag; explicit timeout
   choices pass through untouched), mirrors the normalized corpus under
   `references/engine-data/` (the read-only skill dir the unchanged binary
   expects), and moves all audit data below `references/`. `MODIFICATIONS.json`
   records every count and digest.

Engine: `floe-impeccable` static riscv64 ELF, sha256 `774333d30d6e54604342182e49853851c7e0ebfa9e92fc4216f4a68872d00a1a`,
5594368 bytes — **never inside this package**. The binding is the frozen
managed runtime artifact descriptor `references/engine-dependency.json`
(sha256 `e7c7984a573b5ac9a1447bcc4285d9b1ba09458033f8468f5c86961965e57233`, 563 bytes, seven fields, no URLs, no
commands). Capture contract digest: `099cd85703a5ec7b7f8bd1d13e091421a09e4faf40a42240138cba9cbbc75bac`.

Verified boundaries: exactly ONE observed 1.1.1 engine binary exists — no
two-build byte-equality is claimed for it (the build recipe documents the
toolchain and flag requirements for a byte-stable rebuild without asserting
one). What IS deterministic here is the skill source and the canonical package
bytes: two fresh runs of this pinned two-stage pipeline produce byte-identical
output. Component qualification to date covers reference riscv64 emulation and
host parity, the contract read-back against the shipped binary and selected
TinyEMU guest legs accepted by the release owner; the full native matrix (real
WebKit capture loop, launcher default route, cooperative cancellation), App
acceptance and publication remain pending and owned by the release owner. This
package is regenerated candidate content: no review, qualification or
publication claim.
