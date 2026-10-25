---
name: writing-guidelines
description: Deterministic style check over wording, formatting, readability and consistency (including English/Simplified Chinese pairing) with cited rule findings.
---


# Writing Guidelines — Style Check Pass (Floe original)

A deterministic pass over technical writing in the task workspace. It checks rules, not taste: every finding cites the rule and the exact location, and every fix preserves meaning.

## Rule groups

### W1 — Wording
- Prefer the concrete over the abstract: name the thing, the number, the actor.
- Verbs carry the sentence: cut "perform an update of" → "update". Nominalizations ("implementation of", "utilization") are a smell.
- One meaning per term: pick a canonical word per concept and use it everywhere (glossary in the consistency ledger, W4).
- Cut hedges that hide weakness ("somewhat", "basically", "very"); keep hedges that state real uncertainty and make them explicit about scope.
- Active voice by default; passive only when the actor is unknown or irrelevant.

### W2 — Formatting
- Heading hierarchy: exactly one H1; H2 for sections; never skip a level; heading case consistent per document.
- Lists: parallel construction across items (same grammatical shape); terminal punctuation consistent within a list.
- Code identifiers, file paths, tool names and literal values always in code spans; prose in normal text.
- One space after periods; no trailing whitespace; tables aligned; line length not a hard rule but long single paragraphs (>10 lines) get split at sentence boundaries.
- Numbers: digits for measurements and counts ≥10; words for one-nine in prose; never mix within a comparison list. Units get a space (12 GB, 30 s). Dates absolute (2026-10-26), not relative, in durable documents.

### W3 — Readability
- Sentence length distribution: average ≤ ~20 words; flag any sentence > ~35 words; flag three consecutive > ~25.
- Flesch reading ease (procedure in references/readability-procedure.md) — for general technical prose target ≥ 50; for user-facing app copy target ≥ 60.
- Paragraph = one idea; first sentence = the point of the paragraph.
- Unexplained acronyms on first use: flag every acronym absent from the document's expansion list.

### W4 — Consistency ledger
Before editing, extract: terms (canonical vs variants), numbers/versions/dates, named entities, cross-reference targets. Build the ledger as a table; every edit re-checks against it. Contradictions (two values for one version, a number that changed between sections, a section referencing a renamed heading) are findings even when each site reads fine alone.

### W5 — Bilingual documents (English + Simplified Chinese)
- Paired locales must carry the same claims, numbers and caveats; flag drift, missing sentences, or tone divergence beyond register.
- Never machine-normalize Chinese punctuation to ASCII; CJK full-width punctuation stays in CJK runs. Terms get their approved translation, first occurrence may show the English in parentheses.
- Units and formats follow each locale's convention (dates ISO in both; currency per locale).

## Pass procedure

1. Read the target file; build the consistency ledger (W4) first — it informs later rules.
2. Run W1–W3 rule checks mechanically; produce findings as a list: location, rule id, quote, suggested fix.
3. Report before rewriting unless the user asked for direct edits. Edits go into a copy or a tracked patch, never silent overwrite.
4. Re-run the mechanical checks after editing; a fix that introduces a new finding is a failed fix.

## Limits

- Style is checkable; truth is not. Unverifiable factual claims are flagged as "needs source", never "smoothed".
- The pass does not grade literature, marketing voice, or brand choices — it enforces the rules above and preserves intended voice unless asked to normalize.
