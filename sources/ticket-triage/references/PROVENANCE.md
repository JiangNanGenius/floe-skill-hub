# Provenance — ticket-triage

- Upstream repository: https://github.com/anthropics/knowledge-work-plugins
- Pinned commit: `2574e29377c7173d0cecffef29a6ecbd7f8ccb5d`
- Upstream path: `customer-support/skills/ticket-triage`
- Upstream file: `customer-support/skills/ticket-triage/SKILL.md` (sha256 `d0e5e95443e358ad2a74811b196071d10807ca95aa20351ab5760feeecee1294`, 11,276 bytes)
- Last upstream content commit for this exact path: `2d6f7e22dd25593f0f748010430ef86f19659735` on 2026-03-13 (`Migrate commands to skills across all plugins`). Two commits were observed for this path. The plugin directory had later README and manifest commits, but this skill file did not change after that date.
- License: Apache-2.0; exact applicable bytes from `customer-support/LICENSE` are preserved in `references/licenses/UPSTREAM-LICENSE.txt`. No `NOTICE` file exists at this path or at the repository root at this pin. See `references/licenses/LICENSE-NOTE.md`.
- Fetch method: individual raw-file retrieval at the pinned commit on 2026-11-01; no full-repository clone, no vendoring and no dependency installation.

## Adaptation

The upstream guide's category taxonomy, P1-P4 framework, routing rules, duplicate checks, initial-response templates and best practices are retained. The slash-command invocation, `@$1` argument handling, `CONNECTORS.md` reference and live support-platform, knowledge-base and project-tracker lookups were removed. Floe adds an input contract, evidence classes, an impact/urgency assessment, a priority decision order, SLA deadline arithmetic, a supplied-list-only duplicate and pattern check, privacy minimization, escalation flags, a complete output contract and an explicit human-confirmation boundary.

Input is now a workspace file or pasted ticket text plus the organization's SLA, routing and escalation policy. The output is a triage note and a draft first response. The guide does not create, assign, merge, close or reply to a ticket, and it does not contact the customer.

## File mapping

- `SKILL.md` ← upstream `customer-support/skills/ticket-triage/SKILL.md`, adapted as described above. The upstream original is not shipped byte-for-byte; original and adapted variants remain separate.
- `references/licenses/UPSTREAM-LICENSE.txt` ← upstream `customer-support/LICENSE`, exact bytes.
- `floe.json` is the Floe package manifest, authored for this package.
- `assets/examples/input.md`, `assets/examples/expected-output.md` and `assets/examples/figures.json` are synthetic fixtures authored for this package; they are not upstream files.
- No other upstream file was present in the pinned skill directory. The plugin README and connector documentation are not copied and no connector is activated.

## Package file hashes

- `SKILL.md` sha256 `a231d649b871e93c0e923b3c9bee2efe8575fe022464af53d578d60937288e5f`
- `assets/examples/expected-output.md` sha256 `47734973bb23eba4bf988716e7c062292d8b053a8ae1c20704cc942bcd5512c5`
- `assets/examples/figures.json` sha256 `48ebb47a7c9c435d82049ee6db2a8c3a73648551730c7f9973b7ecba9581d6f9`
- `assets/examples/input.md` sha256 `511ca60d24fbd1ff5fee57d6700a530acc22805aad14989baa32e402b9b8d1c5`
- `floe.json` sha256 `587b1e885478e642c51d20f5cc20b8fcc7b0db2090e4b870ad745d9dd9798f5c`
- `references/licenses/LICENSE-NOTE.md` sha256 `505aada486eb1925ee1564058a92779d79b187fcb720427a8f096bb2c3c2fa73`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`

## Notes

- The synthetic fixtures use invented tickets, customers and timestamps. No real ticket, account or personal data is included.
- The package is a guide only: no script, dependency, connector, native payload or execution claim is present.
- PROVENANCE.md intentionally omits its own hash.
- No private path, credential, server address or raw private evidence is included.
