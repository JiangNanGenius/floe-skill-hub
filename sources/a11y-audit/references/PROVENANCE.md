# Provenance — a11y-audit

- Upstream repository: https://github.com/alirezarezvani/claude-skills
- Pinned commit: `6d2f02ea077eead1bee5411a31bcc6db5a11a70c` (tree `01b7452240fff76a37f7952ecf22cef153a10f8e` verified at fetch)
- Upstream path: `engineering-team/a11y-audit/skills/a11y-audit`
- License: MIT (root `LICENSE` at the pinned commit, Copyright (c) 2025 Alireza Rezvani) — full text at references/licenses/UPSTREAM-LICENSE.txt
- Subtree-only fetch into task scratch on 2026-10-26; no full-repo vendoring.
- Kept upstream content: SKILL.md methodology body (with the adaptations listed below) and the reference/asset documents under references/ and assets/ (copied verbatim except where listed as edited).
- Excluded (audited, reason): scripts/*.py (audited: stdlib-only, no network/subprocess/destructive defaults; folded into procedure per planned guide-only runtime)
- Adaptations: frontmatter normalized; scanner/contrast CLI sections rewritten to workspace/guest-readonly/browser procedure; Scripts section replaced by audit note; slash-command block removed
- Execution status: guide-only package; host static validation only. Nothing in this package was executed to claim verification.

- Post-build correction: Tools Reference CLI blocks rewritten to a capability requirements list (scanner/contrast CLIs audited, not shipped; behavior preserved as procedure requirements).

## File inventory (sha256, this checkout; PROVENANCE.md self-hash intentionally omitted)
- `SKILL.md` sha256 `40cd4aa96bc33c8daf77d1c7650c15e99fa073b8c87ba002fa3398464771a864`
- `assets/sample-component.tsx` sha256 `0f53c44479b30d15a587daefc481ef3667c8adacde1afbbf763cb364509b8725`
- `floe.json` sha256 `d96d8115822455a140a3d3d4b4e768e02a75f696838560262c2dd22427a83b80`
- `references/aria-patterns.md` sha256 `00770605444696d7a55aa52438ec7947e256c450440b21f12f5fa954a79ebbad`
- `references/audit-report-template.md` sha256 `db9203c5119d3e020d40914b38dfaae5289ad955ef07e4d97a4c5dce5691c7c2`
- `references/ci-cd-integration.md` sha256 `b1c25d7792173520ed25d4da741f445d05c771f9772256b8cf77e910b762692c`
- `references/color-contrast-guide.md` sha256 `5cae29f643f7e064a36b4b8e8ca2ca5d62db5c5d7861571e9e4e95d77b273cea`
- `references/examples-by-framework.md` sha256 `50c1ba5a69ce4312f86b9161b7f0c3774f025a3ddf7214dce8b8aee35d9c8a02`
- `references/expected-outputs/sample-contrast-output.txt` sha256 `a1a85615056be8eee26ad44e24cd68d11440baac5acdc6eec706194e92b5d30a`
- `references/expected-outputs/sample-scan-output.json` sha256 `d1ad2d313baea83b9213c2ab5e82eec70be95cdf552392b79796abea389a54b5`
- `references/expected-outputs/sample-scan-report.md` sha256 `377daf3d66dca0c9134ccf10ea76fd4c561f7989d0d8ff5c8984baf79fe11902`
- `references/framework-a11y-patterns.md` sha256 `e2694afd26dc7e0e1cc4f4b47571268c2a213e830159e83d050fb9b926193274`
- `references/licenses/LICENSE-NOTE.md` sha256 `ed859c9e5971a027a2fb0452022bdb389615997f0941c7313143ac4130ae9490`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `a20126646f93d32a8989c3cf4772d59194f405034f7babe7daebeac22b8ab151`
- `references/testing-checklist.md` sha256 `5bf71ecc3ed2e080ec37e62460863539e886981cf864466000fa72d2acfbae47`
- `references/wcag-22-new-criteria.md` sha256 `4aa02091a952ed22c9e5baf7a97598632164f7cd5a37a3c588482ec3e187051f`
- `references/wcag-quick-ref.md` sha256 `481b32dc92e7bd5286795fff1cde31bea4936451bd15b8b812be3fc76d549b6e`
