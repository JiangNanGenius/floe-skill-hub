# Provenance — content-production

- Upstream repository: https://github.com/alirezarezvani/claude-skills
- Pinned commit: `6d2f02ea077eead1bee5411a31bcc6db5a11a70c` (tree `01b7452240fff76a37f7952ecf22cef153a10f8e` verified at fetch)
- Upstream path: `alirezarezvani_claude_skills/marketing-skill/skills/content-production`
- License: MIT (root `LICENSE` at the pinned commit, Copyright (c) 2025 Alireza Rezvani) — full text preserved at references/licenses/UPSTREAM-LICENSE.txt
- Retrieved into task scratch on 2026-10-26; subtree-only fetch (no full-repo vendoring).
- Kept upstream content: references/ai-citation-readiness.md, references/content-brief-guide.md, references/content-templates.md, references/optimization-checklist.md, references/templates/content-brief-template.md (moved from upstream templates/ — top level `templates/` is not an allowed package path)
- Excluded from the package (audited, reason recorded): scripts/seo_optimizer.py, scripts/content_scorer.py, scripts/brand_voice_analyzer.py, scripts/content_quality_gates.py (all audited stdlib-only; methodology folded into SKILL.md; guide-only per planned runtime)
- Adaptations: frontmatter normalized; bundled-script steps -> deterministic rubric procedure; `.claude/` paths rewritten; templates moved under references/
- Execution status: guide-only package; nothing executed for qualification. Host-side static checks only (validator + link check).

- Post-build correction: optimization-checklist.md scorer line rewritten to the rubric procedure.

## File inventory (sha256, this checkout; PROVENANCE.md self-hash intentionally omitted)
- `SKILL.md` sha256 `f4a633642157eec0fb138f3c0bb2c2e0409a422b28406acdfdd852ae8d0011f9`
- `floe.json` sha256 `6f0d8b5f4ee683b7f68b6faa1170c75af7c4343a4e8e4fc4463212378c50d0fd`
- `references/ai-citation-readiness.md` sha256 `6fa6b6e18aab4331bd4bb2351504f689c74edefcc1327c191ae2d6cc5af96829`
- `references/content-brief-guide.md` sha256 `06dadeb490dbf1df46884cad543e39ed30191ebaafe5c7844324e50c05452a74`
- `references/content-templates.md` sha256 `f0b049f34289ab71e488da3821b2c91c98b7e071283d186eaab4d89988a5e99d`
- `references/licenses/LICENSE-NOTE.md` sha256 `f7e123b1f48a8132f6a94644c0428c97e011d5a637545b51d0334411f9fbcc64`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `a20126646f93d32a8989c3cf4772d59194f405034f7babe7daebeac22b8ab151`
- `references/optimization-checklist.md` sha256 `4d6c6706cfeea7dd88ecc9f0c9f423d6404d8fe7b42d9a3fbb7e170ec5f4926d`
- `references/templates/content-brief-template.md` sha256 `2ca82bc462e7e6caa7bf799a7e7d3ed305124371b39ba4a6252decc983248120`
