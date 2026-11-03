# Provenance — review-contract

- Upstream repository: https://github.com/anthropics/knowledge-work-plugins
- Pinned commit: `2574e29377c7173d0cecffef29a6ecbd7f8ccb5d`
- Upstream path: `legal/skills/review-contract`
- License: see `references/licenses/LICENSE-NOTE.md`; full upstream text is in `references/licenses/UPSTREAM-LICENSE.txt`.
- Fetch method: individual file retrieval from the pinned commit on 2026-10-31; no full-repository clone or vendoring.
- Variant: this is an adapted guide-only package. The upstream original is not shipped here; original and adapted variants remain separate.
- Execution status: guide-only; static package validation only. Nothing in this package was executed to claim runtime qualification.

## Adaptations

Frontmatter normalized; slash-command invocation replaced with workspace-file/paste input; CONNECTORS link and CLM routing replaced with a workspace playbook and a routing recommendation only. Clause checklist, classification and redline guidance retained.

## File mapping and hashes

- `SKILL.md` ← upstream `SKILL.md` (upstream sha256 `3a6413475f51adedbff130f4d5aabbeeacfb2abd323e0338bc91c21937fbfb76`)

## Package file hashes

- `SKILL.md` sha256 `8550142b6a868fd1b82d339106d5bd90cd2b24aeaf8e9ced9a503c296e0848ac`
- `assets/examples/expected-output.md` sha256 `15b4a5c67a8c2d61b3b7df24a705650a48e3dfce75170f44b45b1417a4b2d1b7`
- `assets/examples/input.md` sha256 `d194592674df572a1289ee4d8410c12e9b9b16e000c6aa620bf1910cf81f69ab`
- `floe.json` sha256 `2f5c732882acdbf3083635e16234f14fece3255517faf17ba99afb15e2b89af6`
- `references/licenses/LICENSE-NOTE.md` sha256 `e66283209cc8dd7a5598fed2909b6c89811fb7f34395efb98eb6e25bae31a064`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`


## Audit repairs (2026-10-31)

- Replaced the copied root `LICENSE` with the exact bytes of `legal/LICENSE` at the pinned commit (sha256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`) and updated the license pointer/note. The registry proposal already named `legal/LICENSE`; the prepared copy was the different root file.
- Expanded the synthetic expected output to cover all 12 upstream clause categories: six are analysed from the excerpt and six are explicitly marked as not present in the excerpt, with a request for the full contract. Added a priority column and corrected the acceptance claim.

## Notes

- Upstream license/NOTICE: the exact `legal/LICENSE` bytes are preserved; no upstream NOTICE file was present at the pin. The copied license was corrected from the different root `LICENSE` during this audit.
- The synthetic fixtures under `assets/examples/` are authored for this package, not upstream files.
- PROVENANCE.md intentionally omits its own hash.
- No private path, credential, server address or raw private evidence is included.
