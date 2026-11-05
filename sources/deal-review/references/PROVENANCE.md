# Provenance — deal-review

- Upstream repository: https://github.com/anthropics/knowledge-work-plugins
- Pinned commit: `2574e29377c7173d0cecffef29a6ecbd7f8ccb5d`
- Upstream path: `sales/skills/deal-review`
- Upstream file: `sales/skills/deal-review/SKILL.md` (sha256 `a78f8382d1f65ae57f8468bd4c76c2ccfec2a7d0f47ac15db44b31aa53568700`, 9,676 bytes)
- Last upstream content commit for this exact path: `2d97716bce` on 2026-10-21 (`feat(sales): show the source of every line with a link to check it (2.1.0) (#1351)`). Two commits were observed; the 2026-10-21 change is genuine (small) content maintenance — the shared "Links to check the work" rule — not a bulk migration or a description-only edit.
- License: Apache-2.0; exact applicable bytes from `sales/LICENSE` are preserved in `references/licenses/UPSTREAM-LICENSE.txt`. No `NOTICE` file exists at this path, at `sales/NOTICE`, or at the repository root at this pin. See `references/licenses/LICENSE-NOTE.md`.
- Fetch method: individual raw-file retrieval at the pinned commit on 2026-11-03 plus GitHub metadata/path-history APIs. No full-repository clone, no vendoring and no dependency installation.

## Adaptation

The upstream deep-dive structure — ground, gather signals, qualification gap check, signal adjustment, stage reality check and recommendations — is retained. The live CRM, email, transcript and chat pulls and the `update-opportunity` handoff are removed. Floe adds an input contract, evidence classes, an explicit rule that the signal-adjusted probability starts only from a supplied base (CRM probability or an explicitly stated stage default) and never invents one, skipped-signal discipline, a suggested-update checklist a human applies, privacy minimization and a claim boundary. Input is a workspace file or pasted opportunity material; the output is a workspace review.

## File mapping

- `SKILL.md` ← upstream `sales/skills/deal-review/SKILL.md`, adapted as described above. The upstream original is not shipped byte-for-byte; original and adapted variants remain separate.
- `references/licenses/UPSTREAM-LICENSE.txt` ← upstream `sales/LICENSE`, exact bytes.
- `floe.json` is the Floe package manifest, authored for this package.
- `assets/examples/input.md`, `assets/examples/expected-output.md` and `assets/examples/figures.json` are synthetic fixtures authored for this package; they are not upstream files.
- No other upstream file was present in the pinned skill directory. The plugin README, connector documentation and marketplace metadata are not copied and no connector is activated.

## Package file hashes

- `SKILL.md` sha256 `4dc4edf418008ea0c3d1e9cb5381c2820302745394bb9acf7151814a819a7aa8`
- `assets/examples/expected-output.md` sha256 `f5e0205dddd84d65902c1e19a9d3c822f986d132e9142f8032ccff93f8264b14`
- `assets/examples/figures.json` sha256 `67f946b28afe4b41d13e2e0ff4ac4c1e5708062f068415086fc04f36591265c4`
- `assets/examples/input.md` sha256 `8f23621fffea57cb276f7b68e9785a5d8875682b0cef091404b896ec5d662485`
- `floe.json` sha256 `e2b15561af685c7e901e2e628ff6a239c225b6e0c38d1c41a404719ee6b0398c`
- `references/licenses/LICENSE-NOTE.md` sha256 `53a8c7f0bab43c5b74d4252edb2c0d457b8b7c865283f3a294ea3fe356bd9219`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`

## Notes

- The synthetic fixtures use invented accounts, contacts and figures. No real opportunity or personal data is included.
- The package is a guide only: no script, dependency, connector, native payload or execution claim is present.
- PROVENANCE.md intentionally omits its own hash.
- No private path, credential, server address or raw private evidence is included.
