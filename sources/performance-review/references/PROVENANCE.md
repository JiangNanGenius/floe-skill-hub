# Provenance — performance-review

- Upstream repository: https://github.com/anthropics/knowledge-work-plugins
- Pinned commit: `2574e29377c7173d0cecffef29a6ecbd7f8ccb5d`
- Upstream path: `human-resources/skills/performance-review`
- License: see `references/licenses/LICENSE-NOTE.md`; the full upstream text is in `references/licenses/UPSTREAM-LICENSE.txt`.
- Fetch method: individual raw-file retrieval at the pinned commit on 2026-11-01; no full-repository clone or vendoring.
- Variant: adapted guide-only package. The upstream original is not shipped here; original and adapted variants remain separate.
- Execution status: guide-only; static package validation only. Nothing in this package was executed to claim runtime qualification.

## Adaptations

Frontmatter normalized; the `/performance-review` modes and the HRIS/project-tracker connector block were removed. The self-assessment, manager-review and calibration templates and the feedback tips are retained. The compensation line was reframed as an input to the authorized compensation process, and the illustrative rating-distribution targets were reframed as a reference band, not a quota. Floe adds evidence-quality checks, bias controls, distribution arithmetic and the decision-ownership boundary.

## File mapping and hashes

- `SKILL.md` ← upstream `human-resources/skills/performance-review/SKILL.md` (upstream sha256 `a34e3f49e7c8619f07fd218cb2b6a6d57572dd7a0a78c72977dcd1739578e588`)
- No other upstream files were present in the pinned skill directory; the upstream skill has one file.
- `assets/examples/input.md`, `assets/examples/expected-output.md` and `assets/examples/figures.json` are synthetic fixtures authored for this package, not upstream files.
- `floe.json` is the Floe package manifest, authored for this package.
- `references/licenses/UPSTREAM-LICENSE.txt` ← upstream `LICENSE` (exact bytes; hash in the license note and package list below).

## Package file hashes

- `SKILL.md` sha256 `d49cc35263cfc68689bd0427651cff5ff2d284f237d045496d2e7113b61e329b`
- `assets/examples/expected-output.md` sha256 `de3dc5ec14f2e4230cd0fb1f914b7bcb09c0e8e732c4b884b3b82fd782c16d0c`
- `assets/examples/figures.json` sha256 `83661a38eeee18be121828cc1fab3a795756f961ddfc2bdd9ce6d5f0f8ad34f6`
- `assets/examples/input.md` sha256 `87cfec0e4f071cb6f36c90af41084c934215e97473922a2e7f71c60f8a4af99a`
- `floe.json` sha256 `6075522f1f6de28f20f5e4a86e2bd5a49b30fdfe25b47c78e3fec07f0659fdd3`
- `references/licenses/LICENSE-NOTE.md` sha256 `b18dc91447bcc7045acca23429bbf709942c67619609182b92bc02806e07973b`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `a6946284993aeec75c7d75906064b66210c46051e562077efb30eb6dcfe72e26`

## Notes

- Upstream license/NOTICE: the exact applicable upstream license bytes are preserved; no upstream NOTICE file was present at the pin. See the license note for the evidence path and any root-file caveat.
- The synthetic fixtures are authored for this package, not upstream files.
- PROVENANCE.md intentionally omits its own hash.
- No private path, credential, server address or raw private evidence is included.
