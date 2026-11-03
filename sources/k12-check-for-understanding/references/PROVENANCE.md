# Provenance — k12-check-for-understanding

- Upstream title: K-12 Check for Understanding
- Upstream repository: https://github.com/anthropics/k12-teacher-skills
- Pinned commit: `31fd6dbb0c07cb50bb3ce7f62a4135a393bd0e8c`
- Upstream skill path: `plugin/skills/k12-check-for-understanding`
- Retrieved: 2026-10-31
- Upstream license: Apache-2.0 (root LICENSE and per-skill LICENSE/NOTICE; co-developed by Anthropic and Learning Commons)

## Adaptation

The diagnostic design, learning-component focus, misconception mapping, asset-based language, two-document separation and verification gates are preserved. Floe adaptation replaces Claude-artifact/HTML output with two workspace Markdown files plus optional native rendering, and removes platform-specific `$OUTPUT_DIR` and slide-artifact plumbing. The math build guidance and Learning Commons connector guidance are retained as references.

## File mapping

| Local file | Relationship to upstream |
|---|---|
| `SKILL.md` | Adapted |
| `references/math.md` | Adapted only to map the upstream HTML figure-field names to the Markdown text description |
| `references/output.md` | Adapted from upstream output.md |
| `references/verification.md` | Adapted from upstream verification.md |
| `references/learning-commons-kg.md` | Verbatim |
| `LICENSE` | Verbatim |
| `NOTICE` | Verbatim |

The exact upstream and local SHA-256 values and sizes are recorded in `references/SNAPSHOT-MANIFEST.json`. Upstream license and notice bytes are retained under `references/licenses/`.

## Not shipped

The upstream `rendering/claude-artifact.md` and `evals/` rubric CSV are not shipped because they are platform/eval-specific and not needed for this guide. No student data, curriculum text, fonts or images are redistributed.

## Synthetic examples

`assets/examples/example-input.md` and `assets/examples/expected-output.md` are Floe-authored synthetic fixtures. They contain no real student, customer, employee, patient or financial data, and they are not upstream content.

## Auditor review (2026-10-31)

- `references/verification.md`: kept scratch work inside the task workspace and replaced the upstream HTML `<title>/<desc>` field names with the Markdown figure text description used by this adaptation.
- `references/output.md`: aligned the output guidance with the Markdown figure text description; no HTML wrapper is required.
- `references/math.md`: replaced the upstream HTML figure-field names with the Markdown figure text description; the mathematics guidance is otherwise unchanged.
- No item, standard, misconception or student data was invented; the adapted verification and output rules were checked against the retained math/build guidance.

## Boundary

This package is a guide. It does not claim execution verification, App qualification, review, packaging or publication. It does not include private paths, credentials, operational addresses or raw private evidence.
