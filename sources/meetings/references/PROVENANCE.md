# Provenance — meetings

- Upstream repository: https://github.com/alirezarezvani/claude-skills
- Pinned commit: `6d2f02ea077eead1bee5411a31bcc6db5a11a70c` (tree `01b7452240fff76a37f7952ecf22cef153a10f8e` verified at fetch)
- Upstream path: `productivity/meetings/skills/meetings`
- License: MIT (root `LICENSE` at the pinned commit, Copyright (c) 2025 Alireza Rezvani) — full text at references/licenses/UPSTREAM-LICENSE.txt
- Subtree-only fetch into task scratch on 2026-10-26; no full-repo vendoring.
- Kept upstream content: SKILL.md methodology body (with the adaptations listed below) and the reference/asset documents under references/ and assets/ (copied verbatim except where listed as edited).
- Excluded (audited, reason): scripts/*.py (audited: stdlib-only, no network/subprocess/destructive defaults; folded into procedure per planned guide-only runtime)
- Adaptations: frontmatter normalized (slash-command triggers removed from description); scripts section -> deterministic procedures; hard no-auto-send boundary kept and restated
- Execution status: guide-only package; host static validation only. Nothing in this package was executed to claim verification.

- Post-build correction: meeting_gate_worksheet.md script invocations rewritten to the three SKILL.md procedures.

## File inventory (sha256, this checkout; PROVENANCE.md self-hash intentionally omitted)
- `SKILL.md` sha256 `663d75d43c459f2c4855193fa4a6967e228585c075436fe27ad32d0f73685737`
- `assets/example_agenda.md` sha256 `9da73554d7eae3c0391578be73c41cacfc659222f357efb992c3560bab5f4413`
- `assets/meeting_gate_worksheet.md` sha256 `e2c40fd1182fad5349b881ac5e6c6383c41aa3b227904501c128d24f7ad04371`
- `floe.json` sha256 `027373d8b13df643243ade133d11797fc3f7530c9ebfd92be33ea88e66a91ee7`
- `references/action_item_discipline.md` sha256 `8f2b7b1b9fd9395de930e71a78e77efba5094c33cea1cd5a0959ac762b5476a8`
- `references/agenda_discipline.md` sha256 `777b34f49d40cfc6c57bae88cbf4627e765d83ac26b3dd2d8f40aab11be7ff98`
- `references/licenses/LICENSE-NOTE.md` sha256 `7e45b4238fd2120a06fb95a079ade4337f1a42c44b9380134fc062abc9c3d600`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `a20126646f93d32a8989c3cf4772d59194f405034f7babe7daebeac22b8ab151`
- `references/meeting_cost_canon.md` sha256 `a2b60e785da23fdf6421b3d94a56141081455dcabad0dee103a9c674fe9447ac`
