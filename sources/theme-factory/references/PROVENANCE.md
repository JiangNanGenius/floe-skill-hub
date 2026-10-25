# Provenance — theme-factory

- Upstream repository: https://github.com/anthropics/skills
- Pinned commit: `dbd4588f9e1033efb41dad4bef2f7947c8993d44` (tree verified at fetch; see the hub docs/UPSTREAM-PINS.json)
- Upstream path: `anthropics_skills/skills/theme-factory`
- License: Apache License 2.0 (per-skill LICENSE.txt at the pinned commit) — full text preserved at references/licenses/UPSTREAM-LICENSE.txt (copied byte-identical from the pinned checkout)
- Subtree-only fetch into task scratch on 2026-10-26; no full-repo vendoring.
- Kept upstream content: SKILL.md methodology body (with the adaptations below) plus reference/asset files copied verbatim unless listed as edited.
- Adaptations: frontmatter normalized; showcase display + theme paths rebound to the Floe package layout; theme presets name fonts rather than installing them; coordinator inspection found six embedded font subsets in the original PDF and added their actual copyright/license notices plus the GNU font-embedding exception (references/font-asset-audit.md). The earlier no-embedded-fonts assertion was incorrect and is superseded.
- Execution status: guide-only package; host static validation only. Nothing executed against a guest; no verification claimed.

- Coordinator asset audit (2026-10-26): PDF bytes unchanged, SHA256 `3e126eca9fe99088051f7cb984c97cedb31c7d9e09ce0ba5d61bd01e70a0d253`; six embedded TrueType subsets independently identified by pdffonts and direct name-table parsing. No standalone font extraction is distributed.

## File inventory (sha256, this checkout; PROVENANCE.md self-hash intentionally omitted)
- `SKILL.md` sha256 `040553dfc6a077c174d555a37fae91da985a33e4b00fa2b40c47cd896f698831`
- `assets/theme-showcase.pdf` sha256 `3e126eca9fe99088051f7cb984c97cedb31c7d9e09ce0ba5d61bd01e70a0d253`
- `floe.json` sha256 `4820528e519994d672cb65e1fd868b192083deb3b5624e774524c4e5694d01dc`
- `references/font-asset-audit.md` sha256 `ccacdc7660daf97ff155d331cd119475a32c84bd2715d50b3e48009fa9633387`
- `references/licenses/EMBEDDED-FONT-NOTICES.txt` sha256 `b343f62f5a07acf29f2e454865ec219cc6a8f6813359439b2a270d56882ff4c8`
- `references/licenses/GPL-3.0.txt` sha256 `3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986`
- `references/licenses/LICENSE-NOTE.md` sha256 `08bf35a2a98e8170802978bb07498a78ff64c5cbda20bdfca6d2c544f0a1a899`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `bc6b3af2f331cbc7fb0da1344efb2cbe5877a31498b4d70dbc7000f3405a1362`
- `references/themes/arctic-frost.md` sha256 `868a75a8fb5b2a61d0f0ab87c437fe632d3cbab6371c418f06aa2816ac109ae0`
- `references/themes/botanical-garden.md` sha256 `222cb8e7496abc9b75b29453c809fb9839e7e4b01fa45deecdd896b38d087765`
- `references/themes/desert-rose.md` sha256 `bd065b8629be3b64655183927e248e3d892a27b8d184b009cfba89c96102744f`
- `references/themes/forest-canopy.md` sha256 `ecb722efa24688e808b5bf323c334ca2349e989cfddd72ce8400ce5d4c4bd3e7`
- `references/themes/golden-hour.md` sha256 `3444a00df971d3c2f06b665e21a2e9eb5d7d7d6f6281f2758773b8345776a139`
- `references/themes/midnight-galaxy.md` sha256 `0e134c4c0324df41e34ac314269aa6829cd378cf3c304b31858d0cd158d2f944`
- `references/themes/modern-minimalist.md` sha256 `b8bc572b75948d4df69c401af703b9262ed6820a3ceb270da30a529e92763614`
- `references/themes/ocean-depths.md` sha256 `a7ad8eec85341dbfcb2665da827a4b6a4baee08ab3335ac02421f18e6b46b2e2`
- `references/themes/sunset-boulevard.md` sha256 `658af11ab04be4923692571081ffb42a428141ae537703117b9236d9f8ee22a3`
- `references/themes/tech-innovation.md` sha256 `183648163026dd5eeba3df5effa335b55ba333c3ee1fe215278605e55f40a52a`
