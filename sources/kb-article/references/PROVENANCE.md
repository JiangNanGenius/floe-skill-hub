# Provenance — kb-article

- Upstream repository: https://github.com/anthropics/knowledge-work-plugins
- Pinned commit: `2574e29377c7173d0cecffef29a6ecbd7f8ccb5d`
- Upstream path: `customer-support/skills/kb-article`
- Upstream file: `customer-support/skills/kb-article/SKILL.md` (sha256 `cfc300f5ecc5128910a8ff04514d565a45ca9178bf1dc2a40cc40e2ce4db9292`, 12,274 bytes)
- Last upstream content commit for this exact path: `2d6f7e22dd25593f0f748010430ef86f19659735` on 2026-03-13. One commit was observed for this path. The plugin directory had later README and manifest commits, but this skill file did not change after that date.
- License: Apache-2.0; exact applicable bytes from `customer-support/LICENSE` are preserved in `references/licenses/UPSTREAM-LICENSE.txt`. No `NOTICE` file exists at this path or at the repository root at this pin. See `references/licenses/LICENSE-NOTE.md`.
- Fetch method: individual raw-file retrieval at the pinned commit on 2026-11-01; no full-repository clone, no vendoring and no dependency installation.

## Adaptation

The upstream guide's article types, structure standards, searchability guidance, known-issue lifecycle, review cadence, linking taxonomy and maintenance practices are retained. The slash-command invocation, `CONNECTORS.md` reference and live support-platform, knowledge-base and project-tracker lookups were removed. Floe adds an evidence gate, a verified-versus-reported resolution distinction, a no-publish boundary, complete metadata, review-date arithmetic, an active-incident handling section, privacy minimization and a publishing handoff with named unknowns.

The guide is intentionally not a marketing-content or long-form editorial guide. It is scoped to self-service support accuracy: helping a customer with a problem find the article, recognize the symptom and complete a verified resolution or workaround.

## File mapping

- `SKILL.md` ← upstream `customer-support/skills/kb-article/SKILL.md`, adapted as described above. The upstream original is not shipped byte-for-byte; original and adapted variants remain separate.
- `references/licenses/UPSTREAM-LICENSE.txt` ← upstream `customer-support/LICENSE`, exact bytes.
- `floe.json` is the Floe package manifest, authored for this package.
- `assets/examples/input.md`, `assets/examples/expected-output.md` and `assets/examples/figures.json` are synthetic fixtures authored for this package; they are not upstream files.
- No other upstream file was present in the pinned skill directory. The plugin README and connector documentation are not copied and no connector is activated.

## Package file hashes

- `SKILL.md` sha256 `e7a75e9ce99e853a0a004532fc57212f485961281cf21ca202bf77bcd1d11bdf`
- `assets/examples/expected-output.md` sha256 `9bcffd2281b526501253c2293168dff9bcc838c47bf938b446704b0ffc1d7ee3`
- `assets/examples/figures.json` sha256 `cfefe4e21f3920d10481f4082067cc48baefaeb607725d4530080b2d077e9774`
- `assets/examples/input.md` sha256 `384da61854164bafbdd19dc177d9221efa8ab5ade1d5fae4ef775666cac03ef4`
- `floe.json` sha256 `e9c713526fc00e0df0ddeb2dbd21ed1fc9d65a2bbcc2eac38a821e610f38597e`
- `references/licenses/LICENSE-NOTE.md` sha256 `33f78d9e84cdcf4495cd36c6c52a515c006aaa5d95c981ab54ba45de3947ea44`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`

## Notes

- The synthetic fixtures use invented customers, products, errors and limits. No real article, ticket or customer data is included.
- The package is a guide only: no script, dependency, connector, native payload or execution claim is present.
- PROVENANCE.md intentionally omits its own hash.
- No private path, credential, server address or raw private evidence is included.
