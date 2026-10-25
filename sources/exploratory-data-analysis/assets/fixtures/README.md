# Bundled fixtures — exploratory-data-analysis (Floe adaptation)

All files in this directory are SMALL SYNTHETIC fixtures authored for this
Floe release (first-party, MIT (c) Floe project, same license as this
package). They contain no real subjects, no real measurements and no
third-party data. Expected aggregate values used by `scripts/eda_verify.py`
are hand-computable from these bytes and are cross-checked against the
stdlib profiler, the optional pandas engine, and (during adaptation) the
Debian-package development stack.

- `profile_fixture.csv` — 8 rows, 5 columns; `value` carries one explicit
  `NA` missing token and one deliberate outlier (100); `count` is 1..8.
- `leak_fixture.csv` — 6 rows with two subjects (`p1`, `p2`) appearing in
  both `train` and `test` splits and one empty `measurement` cell; used to
  prove the missingness/leakage audit detects entity overlap.
- `structure_fixture.json` — small nested document for the strict JSON
  structural profile (2 records, numeric/string/array/object mix).
