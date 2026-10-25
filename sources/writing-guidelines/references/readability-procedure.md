# Readability Procedure (deterministic)

Compute, per document, from the prose only (exclude code blocks, tables, headings):

1. **Syllables per word** — English: count vowel groups per word, minimum 1; subtract silent-e endings when the word ends in a consonant+e; Chinese prose is not scored with this metric — for zh-Hans use sentence-length distribution and character counts instead.
2. **Flesch Reading Ease** = 206.835 − 1.015 × (total words / total sentences) − 84.6 × (total syllables / total words). Round to one decimal.
3. **Flesch-Kincaid grade** = 0.39 × (words/sentences) + 11.8 × (syllables/words) − 15.59.
4. **Passive-voice proxy** — be-verb auxiliary (is/are/was/were/been/being) immediately followed by a past participle (including irregular forms); report count and percentage of sentences.
5. **Filler-word census** — a fixed list (very, really, basically, simply, actually, just, quite, rather, somewhat, in order to, at this point in time); report each hit with location.

## Running it

- Small documents: compute directly, sentence by sentence, and show the arithmetic summary (counts, not vibes).
- Authorized Linux environment available: a stdlib script may be staged in the workspace and run via `exec.shell` for reproducible counting; the formula above is the contract, any script is an optimization.
- Report the three numbers (FRE, grade, passive %), the filler table, and the sentences > 35 words. Never round findings into vagueness: "Flesch 44.2 (below the 50 target): the 12 flagged sentences in §2 are the cause".

## Interpretation guardrails

- Reading ease optimizes for processing effort, not intelligence. Technical docs with dense nouns score low for legitimate reasons — compare within the same genre, and fix structure (sentence length, nesting) before dumbing vocabulary.
- A metric drop after editing is a regression to investigate, not to explain away.
