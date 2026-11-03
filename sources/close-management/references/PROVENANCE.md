# Provenance — close-management

- Upstream repository: https://github.com/anthropics/knowledge-work-plugins
- Pinned commit: `2574e29377c7173d0cecffef29a6ecbd7f8ccb5d`
- Upstream path: `finance/skills/close-management`
- License: see `references/licenses/LICENSE-NOTE.md`; the full upstream text is in `references/licenses/UPSTREAM-LICENSE.txt`.
- Fetch method: individual raw-file retrieval at the pinned commit on 2026-11-01; no full-repository clone or vendoring.
- Variant: adapted guide-only package. The upstream original is not shipped here; original and adapted variants remain separate.
- Execution status: guide-only; static package validation only. Nothing in this package was executed to claim runtime qualification.

## Adaptations

Frontmatter normalized; the command invocation was removed. Input is now a workspace task table with a status snapshot. The day-by-day checklist, dependency levels, status model and close metrics are retained. Floe adds sequencing checks, the converging-delay rule, a metrics basis and an explicit boundary that period lock and close approval are human/system actions.

## File mapping and hashes

- `SKILL.md` ← upstream `finance/skills/close-management/SKILL.md` (upstream sha256 `6c2df93bcd15eddf65017445fa44f3eb0b16a755711a5e0602d73ca595e73732`)
- No other upstream files were present in the pinned skill directory; the upstream skill has one file.
- `assets/examples/input.md`, `assets/examples/expected-output.md` and `assets/examples/figures.json` are synthetic fixtures authored for this package, not upstream files.
- `floe.json` is the Floe package manifest, authored for this package.
- `references/licenses/UPSTREAM-LICENSE.txt` ← upstream `finance/LICENSE` (exact bytes; hash in the license note and package list below).

## Package file hashes

- `SKILL.md` sha256 `457d43a87520449c2383afc57f3def78f23e4d02c1fbe44ea70ed17ce2056ded`
- `assets/examples/expected-output.md` sha256 `fdc158f48046025f943c3ffa3230802122abfe00e71d640e2e5a153fc7c80ff2`
- `assets/examples/figures.json` sha256 `8b1f404bd9cc95b65c6ca7b47a3c7790d83c5fd49c313467e6f1d96485414dee`
- `assets/examples/input.md` sha256 `7325ae86692167f90162919bdde4966ada2473acf2280d9219467012406bae9a`
- `floe.json` sha256 `eebbb87c31756e14e8209f60fd4ac326f962f3e8eb44c26412768b7f810142a2`
- `references/licenses/LICENSE-NOTE.md` sha256 `cc1aa3cc04267a409395bb17baaf2245cad500225add9662e60324b2efc4db54`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`

## Notes

- Upstream license/NOTICE: the exact applicable upstream license bytes are preserved; no upstream NOTICE file was present at the pin. See the license note for the evidence path and any root-file caveat.
- The synthetic fixtures are authored for this package, not upstream files.
- PROVENANCE.md intentionally omits its own hash.
- No private path, credential, server address or raw private evidence is included.
