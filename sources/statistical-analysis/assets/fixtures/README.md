# Bundled fixtures — statistical-analysis (Floe adaptation)

All files here are SMALL SYNTHETIC fixtures authored for this Floe release
(first-party, MIT (c) Floe project). No real subjects, no third-party data.
Every embedded golden in `scripts/stats_verify.py` is hand-computable from
these bytes (exact rational arithmetic was used during adaptation and the
derivations are recorded in the verifier comments and PROVENANCE).

- `groups_fixture.csv` — 18 rows: groups A [10,12,14,16,18,19],
  B [21,22,24,26,28,30] (complete separation → Mann-Whitney exact
  p = 2/C(12,6)), C with one deliberately blank score (pairwise omission
  proof), plus pre/post columns with three zero differences (Wilcoxon).
- `relation_fixture.csv` — 10 rows: x = 1..10, y (nonlinear-free design),
  z = pi digits (deliberately NON-collinear with x; a collinear design is a
  negative test inside stats_verify), condition/response forming a 2×2 with
  hand-computable chi-square (5/3 uncorrected) and Fisher p = 11/21.
- `groups_spec.json`, `relation_spec.json` — working analysis specs driving
  `scripts/stats_run.py` over the two fixtures.
