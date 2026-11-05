# Provenance — account-plan

- Upstream repository: https://github.com/anthropics/knowledge-work-plugins
- Pinned commit: `2574e29377c7173d0cecffef29a6ecbd7f8ccb5d`
- Upstream path: `sales/skills/account-plan`
- Upstream file: `sales/skills/account-plan/SKILL.md` (sha256 `b9facd0dfe322873e43757167b93bf3a312f0d0629c4cb9afa031912b64f5162`, 10,000 bytes)
- Last upstream content commit for this exact path: `2d97716bce` on 2026-10-21 (`feat(sales): show the source of every line with a link to check it (2.1.0) (#1351)`). Two commits were observed for this path; the earlier was the 2026-09-15 sales 2.0.0 rebuild. The 2026-10-21 change is genuine (small) content maintenance — it added the shared "Links to check the work" rule to every sales skill — not a bulk migration or a description-only edit.
- License: Apache-2.0; exact applicable bytes from `sales/LICENSE` are preserved in `references/licenses/UPSTREAM-LICENSE.txt`. No `NOTICE` file exists at this path, at `sales/NOTICE`, or at the repository root at this pin. See `references/licenses/LICENSE-NOTE.md`.
- Fetch method: individual raw-file retrieval at the pinned commit on 2026-11-03 plus GitHub metadata/path-history APIs. No full-repository clone, no vendoring and no dependency installation.

## Adaptation

The upstream account-plan structure — snapshot, goals, relationship state, stakeholder coverage, opportunity map, risks and dated action plan — is retained. The live CRM, docs, email, transcripts and enrichment pulls, the connector write/sync paths, the artifact/Page rendering rules and the "links to check the work" link machinery are removed. Floe adds an input contract, evidence classes (observed / reported / unknown), a generic stakeholder-coverage map with explicit uncovered functions and coverage math, refresh-mode change listing, a suggested-update checklist that a human applies, privacy minimization and a claim boundary. Input is a workspace file or pasted account material; the output is a workspace plan and coverage map.

## File mapping

- `SKILL.md` ← upstream `sales/skills/account-plan/SKILL.md`, adapted as described above. The upstream original is not shipped byte-for-byte; original and adapted variants remain separate.
- `references/licenses/UPSTREAM-LICENSE.txt` ← upstream `sales/LICENSE`, exact bytes.
- `floe.json` is the Floe package manifest, authored for this package.
- `assets/examples/input.md`, `assets/examples/expected-output.md` and `assets/examples/figures.json` are synthetic fixtures authored for this package; they are not upstream files.
- No other upstream file was present in the pinned skill directory. The plugin README, connector documentation and marketplace metadata are not copied and no connector is activated.

## Package file hashes

- `SKILL.md` sha256 `9100b108907642e844e30d6bfd1c28c2e0d82c5ebd07d7c2277c0e47b9f5247b`
- `assets/examples/expected-output.md` sha256 `ce6ea02235af3b3759322a03f5829e2cb4f88fed0934bf17225b93da1347276d`
- `assets/examples/figures.json` sha256 `610e58957682528e0ff5e14cce59a365e6b4988d83af3e52cbe5606c6c5e92bd`
- `assets/examples/input.md` sha256 `da9a60bcb27bd7412061cedaab96e3c216a09482ddcaa8b1d4163ab9510e58e4`
- `floe.json` sha256 `47f25d4ec9d9e4c8eec306265f251f16e20d8fb44202b82c0241a48907bf7fcb`
- `references/licenses/LICENSE-NOTE.md` sha256 `12018c4b660d8d2d167b6d68cd87ad6267b868804fbcc1e873ebae24e3bccd67`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`

## Notes

- The synthetic fixtures use invented accounts, contacts and figures. No real account or personal data is included.
- The package is a guide only: no script, dependency, connector, native payload or execution claim is present.
- PROVENANCE.md intentionally omits its own hash.
- No private path, credential, server address or raw private evidence is included.
