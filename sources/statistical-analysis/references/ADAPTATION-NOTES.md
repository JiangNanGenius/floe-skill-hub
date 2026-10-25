# Adaptation notes — statistical-analysis 1.0.0 (Floe)

Upstream: K-Dense-AI/scientific-agent-skills `skills/statistical-analysis`
at commit `593377bb048752abb0152deab9fbb1083a6087df` (MIT).

## Shipped verbatim (audited)

- `references/test_selection_guide.md`, `references/assumptions_and_diagnostics.md`, `references/effect_sizes_and_power.md`, `references/reporting_standards.md`, `references/bayesian_statistics.md` — upstream guidance preserved unchanged. Scope note: `bayesian_statistics.md` and the Bayesian report template are GUIDANCE ONLY in this release — PyMC/ArviZ are not provisioned in the declared layer and Bayesian requests must be declined or routed to a separately reviewed layer, never approximated. The upstream installation section's `uv venv`/`uv pip` flow does not apply in Floe (see SKILL.md).

## Modified (upstream MIT content, changes recorded)

- `scripts/assumption_checks.py` — statistical logic, guards and honest non-rejection semantics preserved 1:1. Floe changes: (1) module-level `import matplotlib.pyplot` replaced by a lazy `_require_plt()` that forces the headless Agg backend and raises an explicit "optional layer not provisioned" ValueError — matplotlib is NOT in this skill's declared pins; (2) `_finish_plot()` never calls `plt.show()`; plots are opt-in FILES saved into a caller-owned `output_dir` with deterministic names; (3) all public `plot` defaults flipped True→False and `output_dir` parameters added (`plot=True` without `output_dir` is rejected); (4) `check_normality_per_group`/`comprehensive_assumption_check` pass the new parameters through; (5) header docstring records the adaptation; (6) the `__main__` demo is headless.
- `SKILL.md` — rewritten around the Floe runtime and the declared layer; upstream methodology (workflow, test-selection semantics, assumption interpretation, effect-size/power rules, APA reporting requirements) preserved in substance; Pingouin-specific API guidance replaced by the exact scipy/statsmodels equivalents this release actually runs; upstream frontmatter replaced by the native scalar name/description contract; K-Dense attribution preserved.

## Added (first-party Floe, MIT (c) Floe project)

- `scripts/stats_run.py` — prespecified, fail-closed analysis runner over bounded CSV: 14 analysis types, pairwise missing omission with counts, infinity/rank-deficiency/degeneracy refusal, assumption screens attached to parametric tests, effect sizes with CIs, APA line rendering, spec/input SHA-256 + engine-version reproducibility records, atomic outputs with overwrite protection. Stdlib-only `descriptives` path works without the declared layer; every test refuses honestly when the layer is missing (never substitutes a quieter algorithm).
- `scripts/stats_verify.py` — golden verifier. Embedded goldens were computed twice during adaptation (independent closed-form arithmetic — exact rational normal equations giving OLS betas 2294/2235, 789/745, −52/1341, hand-enumerable Fisher p = 11/21 and Mann-Whitney exact p = 2/C(12,6) — and the pinned reference engines scipy 1.15.3 / statsmodels 0.14.4), agreeing ≤1e-12 before embedding. Runtime tolerance 1e-8 relative for floats; exact for counts/df/tables. Includes negative fixtures: non-rectangular input, infinities, unknown analysis type, unknown column (fail-closed record + exit 3), collinear-design refusal, overwrite protection, plot-without-output_dir rejection. Version pins that do not match fail the receipt (a wrong-version layer can never become a passing result).
- `assets/fixtures/` — small synthetic fixtures + spec files (first-party; no third-party or real-subject data): `groups_fixture.csv` (3 groups; one deliberately blank score proving pairwise omission; pre/post pair columns with three zero differences), `relation_fixture.csv` (x, y and a NON-collinear z = pi digits, condition/response 2×2), `groups_spec.json`, `relation_spec.json`, `README.md`.

## Excluded (audited, with reasons)

- Pingouin (`pingouin==0.7.0`) dependency and all `pg.*` API paths — not packaged for the Debian 13 riscv64 guest; replaced by scipy/statsmodels reference implementations of the same standard algorithms (documented per analysis in stats_run.py output `engine` fields). This is a declared reduction, not silent substitution.
- PyMC 6.3.2 / ArviZ 1.3.0 optional Bayesian layer — out of first-release scope per the implementation plan; guidance reference retained, execution declined.
- seaborn/matplotlib as declared dependencies of THIS skill — diagnostic plots are optional file outputs that require the environment to provide matplotlib (declared by the scientific-visualization skill); not silently required here.
- Upstream `uv venv`/`uv pip install` provisioning — the Floe guest provisions the declared pins through the existing environment/package flow (apt identities: python3-numpy 2.2.4, python3-scipy 1.15.3, python3-pandas 2.2.3, python3-statsmodels 0.14.4).
