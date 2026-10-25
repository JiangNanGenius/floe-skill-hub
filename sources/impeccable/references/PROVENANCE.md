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
   mirrors the normalized corpus under `references/engine-data/` (the read-only
   skill dir the unchanged binary expects), and moves all audit data below
   `references/`. `MODIFICATIONS.json` records every count and digest.

Engine: `floe-impeccable` static riscv64 ELF, sha256 `af8795bf9636e763541c58ef90ee889941e468f453ec6580c32a89a5a758b87b`,
5579704 bytes — **never inside this package**. The binding is the frozen
managed runtime artifact descriptor `references/engine-dependency.json`
(sha256 `cec4a7fade52f6383f74bc9e15972b911552b2672eada138d890e353899be50a`, 563 bytes, seven fields, no URLs, no
commands). Capture contract digest: `baf2453164be6162703af9d671be16da152fa874db53ce95ad5b3516d40de4a3`.

Verified boundaries: the artifact is verified under reference riscv64 emulation
and on host parity only (see `engines/impeccable/HANDOFF.md` in the hub); the
Floe TinyEMU guest run, the native probe, App acceptance and publication are
pending and owned by the release owner. This package is staged candidate
content: no review, qualification or publication claim.
