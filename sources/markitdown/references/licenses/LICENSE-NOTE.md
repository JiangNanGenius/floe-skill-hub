# Upstream license note — markitdown

- Repository: https://github.com/K-Dense-AI/scientific-agent-skills
- Pinned commit: `593377bb048752abb0152deab9fbb1083a6087df` (skill subtree tree `7d881600bf4569374b505d3dd70ded616cafde19`)
- License file at pin: `LICENSE.md`
- Summary: MIT License (root LICENSE.md at the pinned commit), Copyright (c) 2025 K-Dense Inc.
- `UPSTREAM-LICENSE.txt` carries the full text byte-identical from that commit.
- Per-file audit result: the pinned subtree contains the upstream SKILL.md, six reference documents and three scripts, all covered by the single root MIT license; no embedded datasets, fonts or binary assets. NO upstream file bytes are shipped in this Floe package: all upstream scripts import the Microsoft markitdown package (not provisionable here) and all upstream references document that package's API. The upstream MIT material is used as GUIDANCE — its routing-table presentation, quality-check discipline and security model are restated first-party in SKILL.md and references/conversion-security.md, and the batch safety skeleton is re-implemented in scripts/md_batch.py — with attribution kept in SKILL.md, references/ADAPTATION-NOTES.md and references/PROVENANCE.md as MIT requires.
- Third-party marks: "MarkItDown" is a Microsoft project name referenced descriptively; this package neither bundles nor depends on Microsoft code, and no Microsoft license applies to these first-party files.
- First-party content by the Floe project (all scripts, references, assets/fixtures): MIT (c) Floe project; fixtures are synthetic with no third-party data; the encrypted fixture's password is public fixture material.
