# Provenance — triage-nda

- Upstream repository: https://github.com/anthropics/knowledge-work-plugins
- Pinned commit: `2574e29377c7173d0cecffef29a6ecbd7f8ccb5d`
- Upstream path: `legal/skills/triage-nda`
- License: see `references/licenses/LICENSE-NOTE.md`; the full upstream text is in `references/licenses/UPSTREAM-LICENSE.txt`.
- Fetch method: individual raw-file retrieval at the pinned commit on 2026-11-01; no full-repository clone or vendoring.
- Variant: adapted guide-only package. The upstream original is not shipped here; original and adapted variants remain separate.
- Execution status: guide-only; static package validation only. Nothing in this package was executed to claim runtime qualification.

## Adaptations

Frontmatter normalized; the `/triage-nda` command, `@$1` invocation and URL ingestion were removed. The NDA is supplied as a workspace file or pasted text, and `legal.local.md` became a user-named workspace playbook. The screening criteria, GREEN/YELLOW/RED model and issue library are retained. The upstream "standard delegation of authority" approval language was removed: the guide only recommends routing, and approval/signature authority remains with the organization. Floe adds jurisdiction assumptions and a no-authority claim boundary.

## File mapping and hashes

- `SKILL.md` ← upstream `legal/skills/triage-nda/SKILL.md` (upstream sha256 `767a8f6759268e003ee882af8dfb56579aca2121b9dc49a2c65c4e77de93f768`)
- No other upstream files were present in the pinned skill directory; the upstream skill has one file.
- `assets/examples/input.md`, `assets/examples/expected-output.md` and `assets/examples/figures.json` are synthetic fixtures authored for this package, not upstream files.
- `floe.json` is the Floe package manifest, authored for this package.
- `references/licenses/UPSTREAM-LICENSE.txt` ← upstream `legal/LICENSE` (exact bytes; hash in the license note and package list below).

## Package file hashes

- `SKILL.md` sha256 `0c5aa3bdcc0827a4734174a10e8376c46dfa9a328a1b881d2bc904474ce321f1`
- `assets/examples/expected-output.md` sha256 `2278f13da1550b6ffd76dc256780a0cb8114fce27f0b02c96ed5797a9e4a7501`
- `assets/examples/figures.json` sha256 `d16ae4c04aef6e78f6e73024d5044a826012afaa3898f30d5c10914fd75b55b8`
- `assets/examples/input.md` sha256 `69d09de7e19f7d032e234e0d74e9c9a1d06f16d86ac1524c6d2eb8d67b65628e`
- `floe.json` sha256 `c2d3930d445a48af88981acf336a6abcaa70850e791f3d137518964afa0ae3fb`
- `references/licenses/LICENSE-NOTE.md` sha256 `ac16bc92fc5b83c7737f7ad56ecb80eae8b88db11aa2a7aa1bcbf8f2cb718775`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`

## Notes

- Upstream license/NOTICE: the exact applicable upstream license bytes are preserved; no upstream NOTICE file was present at the pin. See the license note for the evidence path and any root-file caveat.
- The synthetic fixtures are authored for this package, not upstream files.
- PROVENANCE.md intentionally omits its own hash.
- No private path, credential, server address or raw private evidence is included.
