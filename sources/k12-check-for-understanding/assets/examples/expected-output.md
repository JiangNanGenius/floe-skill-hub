# Expected output shape and acceptance notes

Two Markdown documents are produced:

1. `cfu_ratio-language_student.md` — name/date line, two items with prompts and choices only, no key and no source label.
2. `cfu_ratio-language_teacher.md` — meta block, focus/progression note, the same two items, correct answers, an interpretation table for every choice, and a what-to-look-for summary.

The teacher guide ends with: *"The standard, progression, and common errors here reflect general best practice."* because no Learning Commons connector was used. It does not mention a failed lookup.

Acceptance checks:

- Exactly two items; each has one defensible answer after Gate A.
- At least one distractor is a prerequisite gap and one is an on-grade confusion; every distractor is reachable by the reasoning named in the guide.
- Item text and choice order are identical in both files.
- Student-facing language stays within the grade band; no "weak", "struggling" or similar labels.
- Both files exist and are non-trivial, and the verification gates were run after writing, not before.
