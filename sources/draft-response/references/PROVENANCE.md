# Provenance — draft-response

- Upstream repository: https://github.com/anthropics/knowledge-work-plugins
- Pinned commit: `2574e29377c7173d0cecffef29a6ecbd7f8ccb5d`
- Upstream path: `customer-support/skills/draft-response`
- Upstream file: `customer-support/skills/draft-response/SKILL.md` (sha256 `1a201228b75a98fc3b5d45090cb7443d50df204b2ee748bfc8970790a64f0026`, 14,581 bytes)
- Last upstream content commit for this exact path: `2d6f7e22dd25593f0f748010430ef86f19659735` on 2026-03-13. One commit was observed for this path. The plugin directory had later README and manifest commits, but this skill file did not change after that date.
- License: Apache-2.0; exact applicable bytes from `customer-support/LICENSE` are preserved in `references/licenses/UPSTREAM-LICENSE.txt`. No `NOTICE` file exists at this path or at the repository root at this pin. See `references/licenses/LICENSE-NOTE.md`.
- Fetch method: individual raw-file retrieval at the pinned commit on 2026-11-01; no full-repository clone, no vendoring and no dependency installation.

## Adaptation

The upstream guide's communication principles, situation-specific advice, response structure, tone spectrum, templates, follow-up cadence and escalation guidance are retained. The slash-command invocation, `CONNECTORS.md` reference and automatic email, chat, CRM, support-platform and knowledge-base research were removed. Floe adds a fact ledger, a commitment ledger, a no-send and no-write boundary, authorization and approval boundaries, privacy minimization, channel length targets, a pre-send audit and a complete draft-plus-notes output.

This is a support-response guide rather than a general email-style or marketing-copy guide. It is scoped to live customer issues where status, ownership, SLA, prior commitments and authorization boundaries matter.

## File mapping

- `SKILL.md` ← upstream `customer-support/skills/draft-response/SKILL.md`, adapted as described above. The upstream original is not shipped byte-for-byte; original and adapted variants remain separate.
- `references/licenses/UPSTREAM-LICENSE.txt` ← upstream `customer-support/LICENSE`, exact bytes.
- `floe.json` is the Floe package manifest, authored for this package.
- `assets/examples/input.md`, `assets/examples/expected-output.md` and `assets/examples/figures.json` are synthetic fixtures authored for this package; they are not upstream files.
- No other upstream file was present in the pinned skill directory. The plugin README and connector documentation are not copied and no connector is activated.

## Package file hashes

- `SKILL.md` sha256 `76c44907dc7195985671793db005886c011c5dccdad1027a31528153480d6762`
- `assets/examples/expected-output.md` sha256 `baf67bd8b255c393d2bd89ccaac226edb68f766abf47f616f5e651ef2754b56a`
- `assets/examples/figures.json` sha256 `44976883dc065387b283b4438d1c008b8611bf896ebfc9b4aecba675a2eea9ad`
- `assets/examples/input.md` sha256 `e831e377213a4e8a98918ddcae70e0202281a874730dec40af03f4d2ad98ad24`
- `floe.json` sha256 `77b07e303969ac420ae14ae82226f9b9fbad301fc90aa7456ca8dc885b7492bf`
- `references/licenses/LICENSE-NOTE.md` sha256 `50931d56bc67570e4cc4304e7d04d22ea9f7c780685bbbc126807dc6416a42c2`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`

## Notes

- The synthetic fixtures use invented customers, people and incidents. No real customer communication is included.
- The package is a guide only: no script, dependency, connector, native payload or execution claim is present.
- PROVENANCE.md intentionally omits its own hash.
- No private path, credential, server address or raw private evidence is included.
