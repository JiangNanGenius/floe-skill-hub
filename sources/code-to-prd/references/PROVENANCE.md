# Provenance — code-to-prd

- Upstream repository: https://github.com/alirezarezvani/claude-skills
- Pinned commit: `6d2f02ea077eead1bee5411a31bcc6db5a11a70c` (tree `01b7452240fff76a37f7952ecf22cef153a10f8e` verified at fetch)
- Upstream path: `product-team/code-to-prd/skills/code-to-prd`
- License: MIT (root `LICENSE` at the pinned commit, Copyright (c) 2025 Alireza Rezvani) — full text at references/licenses/UPSTREAM-LICENSE.txt
- Subtree-only fetch into task scratch on 2026-10-26; no full-repo vendoring.
- Kept upstream content: SKILL.md methodology body (with the adaptations listed below) and the reference/asset documents under references/ and assets/ (copied verbatim except where listed as edited).
- Excluded (audited, reason): scripts/*.py (audited: stdlib-only, no network/subprocess/destructive defaults; folded into procedure per planned guide-only runtime)
- Adaptations: frontmatter normalized; Usage/Tooling script sections rewritten to Floe surfaces; sample fixtures kept under references/expected-outputs and assets
- Execution status: guide-only package; host static validation only. Nothing in this package was executed to claim verification.

- Post-build correction: example PRD page-index link converted to a `generated:` code span; expected-outputs sample header annotates illustrative generated paths.

## File inventory (sha256, this checkout; PROVENANCE.md self-hash intentionally omitted)
- `SKILL.md` sha256 `db3360a3cad5f4f0f2fe64a0d307452549017c78ae3b7e849bb101e500b668e8`
- `assets/sample-analysis.json` sha256 `db88ba2cb560173db5d83155ee9a064e70154248407ee0d2d10e14a87f873016`
- `floe.json` sha256 `3a7d6196e4b6f680928073de985f55ba5cdf743dbebccf95b7fc7376d4d7158d`
- `references/expected-outputs/sample-enum-dictionary.md` sha256 `f759eef6b45bae256573c6eafaec83a3f0891e720ac3139e4ecd843d125b6247`
- `references/expected-outputs/sample-page-user-list.md` sha256 `5f3395e50379d75ed857815684005ed1bb5d37c6edcf1aabc466a29037a37ae5`
- `references/expected-outputs/sample-prd-readme.md` sha256 `f1f3cf262125da73c8530d427a3c7f3ac85875d6787f139b8760ee99714b08e1`
- `references/framework-patterns.md` sha256 `d8884d2fb08712a72978f40e31dc57ee9d5d0408b066041c8a47d4f82515fef1`
- `references/licenses/LICENSE-NOTE.md` sha256 `fa63a3b4228c0e748d521ba41c04b0f5ff5581fd1fc597426a94ff6396783b56`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `a20126646f93d32a8989c3cf4772d59194f405034f7babe7daebeac22b8ab151`
- `references/prd-quality-checklist.md` sha256 `97a2cbc04b4a19b218433e9e1ea4e59575461a3895a53b88f67bcaa8cdb4ef24`
