# Adaptation notes — pricing-strategist 1.0.0 (Floe)

Upstream: `alirezarezvani/claude-skills` at `6d2f02ea077eead1bee5411a31bcc6db5a11a70c`,
path `commercial/skills/pricing-strategist`. The pin is immutable; the upstream license and
the three reference documents are preserved byte-for-byte; the brief template differs only in one example command.

## Kept unchanged

- The five pricing models, industry profile biases and additive score rules in
  `pricing_model_picker.py`.
- The Good/Better/Best assignment rules and the seven anti-pattern detectors in
  `packaging_designer.py`.
- The four Van Westendorp questions, cumulative-curve definitions, densified price grid,
  linear interpolation and the four intersection definitions in `wtp_analyzer.py`.
- The three reference documents.
- Upstream MIT license text under `references/licenses/UPSTREAM-LICENSE.txt`.

The three `--sample` JSON reports are byte-identical to the pinned upstream scripts on
Python 3.9.6 and 3.12 (host evidence, retained under `tests/golden/`).

## Modified (with the original failure observed before the fix)

1. **Strict Hub frontmatter.** The upstream frontmatter contains a nested `metadata:` block.
   The Hub's strict `parse_frontmatter` rejects a line with an empty value:
   `HubError: SKILL.md frontmatter empty key or value`. The Floe copy keeps only scalar
   `name` and `description`; version, author, tags and compatible-tool claims moved to this
   provenance/adaptation record.
2. **Bounded, root-confined input.** The pinned scripts used `Path.read_text()` with no
   root, size, encoding, symlink, hard-link, duplicate-key or non-finite-number checks.
   Observed on the host before patching: a symlink input was accepted, a 3,000,037-byte
   brief was accepted, `Infinity` produced `inf` in the report, duplicate JSON keys were
   silently last-wins, and a directory produced a traceback. The Floe copy refuses all of
   these with exit code 2 and a concise `error:` line.
3. **Schema validation instead of tracebacks.** Observed before patching: a list brief
   raised `AttributeError`, `customer_count: "many"` raised `ValueError`, a missing feature
   name raised `KeyError`, and a string feature raised `TypeError`. The Floe copy validates
   known fields and bounds their sizes/ranges; unknown top-level keys are preserved in the
   JSON echo but cannot change the scoring.
4. **Complete PSM rows.** The pinned `wtp_analyzer.py` divided every cumulative count by the
   total respondent count even when a question was missing, which biased all four curves.
   The Floe copy requires all four finite, non-negative answers per respondent; a partial row
   is refused. Inconsistent ordering remains a warning, as upstream intended.
5. **Count-preserving PSM speed-up.** The pinned curves scanned every respondent for every
   grid point. Measured on the same host with 2,000 synthetic rows: 5.74–6.36 s pinned vs
   0.06 s adapted; 20,000 rows complete in 0.15 s. The adaptation replaces the nested scan
   with sorted arrays and `bisect` (`>=` via `bisect_left`, `<=` via `bisect_right`). The
   verifier and tests compare every intersection against an independent naive reference at
   1e-12 tolerance, and the 2,000-row JSON report is byte-identical to the pinned script.
6. **Explicit zero Best price.** The pinned `price_tiers` used truthiness, so
   `current_pricing.best = 0` was treated as missing, replaced by a computed ratio, and the
   documented "Enterprise — call us with no anchor" anti-pattern could never fire for that
   case. The Floe copy uses key presence: an explicit `0` is preserved and the flag is
   emitted; `good`/`better` must be positive, and an explicitly negative price is refused.
   This intentionally differs from the pinned output for the `best: 0` edge case; the normal
   sample and all positive-price cases remain identical.
7. **Markdown output is sanitized.** The pinned tool printed input strings directly. A
   feature name containing ESC, a newline and a heading marker injected terminal/Markdown
   structure. The Floe copy rejects control characters at input and escapes Markdown
   metacharacters in displayed feature and segment names.
8. **Brief template command.** The upstream example used `python` (not present on every
   Debian 13 guest) and no workspace root. The Floe copy changes only that command line to
   `python3 ... --root .`; the rest of the template is unchanged.
9. **Stdout-only and deterministic errors.** All three CLIs print reports to stdout; none
   creates or overwrites a file. Expected errors exit 2 with `error:` and no traceback;
   `KeyboardInterrupt` exits 130. Both `--sample` and `--input` together is refused rather
   than silently preferring the sample.

## Added by Floe

- `scripts/_pricing_io.py` — shared bounded JSON/path/validation/stdout helpers.
- `scripts/verify_pricing_skills.py` — deterministic offline self-check (12 checks).
- `assets/fixtures/*.json` — synthetic, non-market fixtures with a README.
- This adaptation record, `PROVENANCE.md`, `FLOE-ADAPTATION.md` and the license note.

## Excluded or not claimed

- No network, provider, model, SaaS, paid-data or web-fetch path exists in the package.
- No native host interpreter, language alias or self-install path exists; execution is only
  the declared remote Linux `exec.shell` route.
- No upstream `metadata:`/compatible-tool claim is inherited; Floe does not claim the
  upstream list of host tools.
- No Monte Carlo, conjoint, NMS or market experiment is added or implied.
- The pinned `find_intersection` interpolation is retained unchanged. When cumulative curves
  coincide at sampled points the routine returns a grid point rather than a unique crossing;
  the package adds a warning only for the fully degenerate all-identical-respondent case.
  This is a known upstream limitation, not a hidden correction.
