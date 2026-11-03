# License note — pricing-strategist (Floe adaptation)

- Upstream repository: `https://github.com/alirezarezvani/claude-skills`
- Pinned commit: `6d2f02ea077eead1bee5411a31bcc6db5a11a70c`
- Upstream path: `commercial/skills/pricing-strategist`
- Upstream root license: MIT, Copyright (c) 2025 Alireza Rezvani
- Full upstream license text: `UPSTREAM-LICENSE.txt` (byte-identical to the pinned root `LICENSE`, sha256 `a20126646f93d32a8989c3cf4772d59194f405034f7babe7daebeac22b8ab151`).

## Per-file audit

| File | Origin | License treatment |
| --- | --- | --- |
| `SKILL.md` | Adapted from upstream; framework text retained, runtime/safety sections and CLI examples changed | MIT notice preserved through this package's license copy and provenance |
| `assets/pricing_brief_template.md` | Upstream text with only the example command changed to `python3 ... --root .` | MIT |
| `references/saas_pricing_canon.md` | Byte-identical upstream | MIT |
| `references/van_westendorp_methodology.md` | Byte-identical upstream | MIT |
| `references/packaging_anti_patterns.md` | Byte-identical upstream | MIT |
| `scripts/pricing_model_picker.py` | Upstream logic retained; bounded I/O and validation added | MIT |
| `scripts/wtp_analyzer.py` | Upstream logic retained; bounded I/O, strict rows and a count-preserving speed-up added | MIT |
| `scripts/packaging_designer.py` | Upstream logic retained; bounded I/O and explicit-zero anchor fix added | MIT |
| `scripts/_pricing_io.py` | Floe-added support module | MIT, Copyright (c) 2026 Floe project |
| `scripts/verify_pricing_skills.py` | Floe-added verifier | MIT, Copyright (c) 2026 Floe project |
| `references/*` Floe-added notes | Floe-authored | MIT, Copyright (c) 2026 Floe project |
| `assets/fixtures/*` | Floe-authored synthetic data | MIT, Copyright (c) 2026 Floe project |

No upstream image, font, dataset, model weight or third-party binary is shipped. The reference
documents mention external publications and websites; those are citations, not bundled assets,
and the scripts never fetch them. This note is a provenance record, not a per-file legal opinion.
