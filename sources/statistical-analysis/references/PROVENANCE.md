# Provenance — statistical-analysis (Floe adaptation, 1.0.0)

- Upstream repository: https://github.com/K-Dense-AI/scientific-agent-skills
- Pinned commit: `593377bb048752abb0152deab9fbb1083a6087df` (repository tree `d4d202beb151c1f1c6c15738be0692d65e0447af`; skill subtree `skills/statistical-analysis` tree `d952f1decb93143a120f963d95fdd210a8a681d1`, verified at fetch on 2026-10-26)
- Upstream path: `skills/statistical-analysis`
- License: MIT (root `LICENSE.md` at the pinned commit, Copyright (c) 2025 K-Dense Inc.) — full text at references/licenses/UPSTREAM-LICENSE.txt; per-file audit in references/licenses/LICENSE-NOTE.md
- Retrieval: sparse subtree fetch into task scratch; no full-repo vendoring.
- Adaptation record: references/ADAPTATION-NOTES.md (kept-verbatim / modified / added / excluded, each with reasons).
- Declared dependency layer (floe.json + references/dependencies.json): numpy==2.2.4, scipy==1.15.3, pandas==2.2.3, statsmodels==0.14.4, matplotlib==3.10.1 — the exact versions the resolved Debian 13 (trixie) riscv64 guest provides as python3-numpy (1:2.2.4+ds-1), python3-scipy (1.15.3-1), python3-pandas (2.2.3+dfsg-9), python3-statsmodels (0.14.4+dfsg-1), python3-matplotlib (3.10.1+dfsg1-4). Upstream's Pingouin/PyMC/ArviZ layer is NOT declared (unavailable/prohibited scope; boundaries in SKILL.md). The matplotlib pin was added as an in-place 1.1.0 closure correction on 2026-10-27 after a real guest audit showed the golden verifier unconditionally exercises headless Agg plots (see references/ADAPTATION-NOTES.md).
- First-release version: 1.0.0 (no previously published id/version exists for this skill; registry versionTarget 1.0.0).

## Golden provenance (numerical correctness)

Every embedded golden in `scripts/stats_verify.py` was computed TWICE during adaptation (2026-10-26): once by independent closed-form arithmetic (exact rational normal equations via Fractions giving OLS betas 2294/2235, 789/745, −52/1341 and R² ; textbook Welch t/df; chi-square Σ(O−E)²/E = 5/3 uncorrected and Yates 0.41667; Fisher 2×2 hypergeometric p = 11/21; Mann-Whitney exact p = 2/C(12,6) for the fully separated fixture; hand-counted Wilcoxon zeros and tied-rank W = 4.0) and once by the pinned reference engines (scipy 1.15.3 / statsmodels 0.14.4 on Python 3.13.5, Debian trixie container). Agreement was ≤1e-12 relative before embedding; runtime float comparisons use 1e-8 relative tolerance for cross-architecture ulp noise, counts/df/tables compare exactly. Two initial golden errors introduced by the adapter (kruskal ε² using n=18 instead of the analyzed n=17; a collinear OLS fixture) were caught by the verifier itself and fixed at the source (fixture de-collinearized; rank-deficiency refusal added as a permanent negative test).

## Host development evidence (NOT guest execution evidence)

Executed 2026-10-26 by the H4 lane, labeled by environment:

1. Debian trixie arm64 dev container (docker `floe-data-five-dev`; same distro release, Python 3.13.5 and identical package versions to the guest pins; NOT the riscv64 guest, NOT the 4.15 TinyEMU kernel): `python3 scripts/stats_verify.py --require-layer` → exit 0, `"ok": true`, 9/9 checks (runtime, stdlib descriptives goldens, input-validation negatives, layer pins, group goldens, relation goldens, rank-deficiency refusal, reproducibility digests, assumption screens incl. headless Agg plot files).
2. Bare macOS venv (Python 3.12.13, stdlib only): `stats_verify.py` → exit 0, ok:true, layer honestly `missing`, golden battery `skipped (missing layer)`; `--require-layer` → exit 1 (fail, not pass). `stats_run.py` on the groups spec → exit 3 with descriptives `ok` (stdlib) and every test fail-closed with the explicit provisioning message — no silent substitute.
3. `assumption_checks.py` adaptation smoke (container): numeric-only default, plot=True writes PNG files headless, plot-without-output_dir rejected.

## GUEST-PENDING handoff for Main (exact steps; do not flip evidence without a real passing run)

In a task workspace in the resolved Linux environment, with this package installed/staged:

1. Provision through the existing environment/package flow (guest apt identities): `python3-numpy` (2.2.4), `python3-scipy` (1.15.3), `python3-pandas` (2.2.3), `python3-statsmodels` (0.14.4), `python3-matplotlib` (3.10.1+dfsg1-4) — the full declared required closure; the assumption-screen golden writes headless PNGs and fails honestly without matplotlib. No chat-time pip/uv.
2. `exec.shell`: `python3 scripts/stats_verify.py --require-layer --output verify.json` → must exit 0 with `"ok": true` and every check `pass`; verify.json records installed versions with `pin_matches_base_version: true` (Debian `+dfsg` suffixes tolerated by base comparison).
3. Real workload: stage one authorized task CSV, write an analysis spec (see assets/fixtures/*_spec.json for shape), run `python3 scripts/stats_run.py data.csv --spec spec.json --output results.json --report report.md` → exit 0, results.json carries spec/input sha256 + engine versions; read both back with the workspace tools.
4. Only after 2–3 pass in the actual guest may `plannedRuntime.execution.evidence` become `guest-verified` and `status.executionVerified` flip.

## File inventory (sha256, this checkout; PROVENANCE.md self-hash intentionally omitted)

Historical note: this inventory records the 1.0.0-era checkout; the later `scripts/stats_verify.py` entry (24135 bytes) predates the 1.1.0 receipt change that reads the package version from floe.json (24328 bytes), and the 1.1.0 sidecar `references/dependencies.json` is absent here. The authoritative current-bytes inventory follows the "1.1.0 closure-correction inventory" section at the end of this file.

- `SKILL.md` sha256 `e64ad0cd3d701db35dca4e89b87f21f2f8c4c8eb7b4473a816924dce4b34524a` (12403 bytes)
- `assets/fixtures/README.md` sha256 `a26761fb61c5675f758c52e64fd808cd28145e1956a26ede619322efbb4b948c` (1134 bytes)
- `assets/fixtures/groups_fixture.csv` sha256 `ef585bf562df3f929eb072a2a4f3f37bb8158ae074b6091f480c6a2ad747e3ab` (353 bytes)
- `assets/fixtures/groups_spec.json` sha256 `764edf6b4dcc55a7ee97499ef41fa0c66c9069815abe64d3de3229fd6510f2ab` (875 bytes)
- `assets/fixtures/relation_fixture.csv` sha256 `76bc2175b73423ac2d4fb359b22778073fa118ce99ea8259ddb9e356d58cb140` (184 bytes)
- `assets/fixtures/relation_spec.json` sha256 `77903211a979c96ca5605d2232cd10c996ae8f77646a53d2be2ab6ebca487b7a` (920 bytes)
- `floe.json` sha256 `93ac15b63fb4c6815a770745d85cbe19d051f2d2803091415219803fa667175d` (1199 bytes)
- `references/ADAPTATION-NOTES.md` sha256 `30f4a1172adf6ff61ac87a543d33750ff074505307155785802aa1c50d191e88` (4966 bytes)
- `references/assumptions_and_diagnostics.md` sha256 `6e1ebc110c092845b93e5c6d28f38c8a990780105ba1865f0bd47c007620b073` (14654 bytes)
- `references/bayesian_statistics.md` sha256 `34d62e1b20dd82a11497be40e07c93e4fdb555d56e4944e200f881c1b7629cbf` (14557 bytes)
- `references/effect_sizes_and_power.md` sha256 `5e1321c9058b2931a1bd2a753c7a8f4295f58274412d62e99a34eabd478e42b2` (20907 bytes)
- `references/licenses/LICENSE-NOTE.md` sha256 `f6792e435d45d328e096f6634d0a7807fbe136601b088c3b6f76472e6565fb0a` (979 bytes)
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `09b02a3c9df3053c55531d503357a9c7cde275970e6c3ceaa1ddf5f0e90b40c1` (1068 bytes)
- `references/reporting_standards.md` sha256 `0a30a1bec63231c94c9c285977acaa4218c50a34c8385857d18f62c61ac817b7` (21469 bytes)
- `references/test_selection_guide.md` sha256 `e72e00b6ebe9450e5e84849503db223c4908a8d9a68c3b87cf0ab8ec3254fe83` (6950 bytes)
- `scripts/assumption_checks.py` sha256 `261c377cf32222c292d42e6f5679cb41b822a4716affa5ff9ec9403875ca59fa` (20884 bytes)
- `scripts/stats_run.py` sha256 `57e87c1d24a496bb9d3d4d6f4edfb210bfea5a70d9e52d4207f51220d975a227` (42948 bytes)
- `scripts/stats_verify.py` sha256 `fe299f3a86dde563c2988fa5ac15952106af83301238af9ed3acbbec7a3b317c` (24135 bytes)

TOTAL 18 files, 190585 bytes

## 1.1.0 closure-correction inventory (current checkout, 2026-10-27, stats-closure-final lane)

Complete current file set of this staged source after declaring `python3-matplotlib` as a required pin. Changed vs the original 1.1.0 candidate: `SKILL.md`, `floe.json`, `references/dependencies.json`, `references/ADAPTATION-NOTES.md`, `references/PROVENANCE.md` (this file). All scripts, fixtures, goldens and reviewed guidance references are byte-identical to that candidate. PROVENANCE.md self-hash intentionally omitted.

- `SKILL.md` sha256 `02c2b2f0272da8928d50fb3a163be861609fd7ec6ce118ea2cb227ba179f0e67` (13070 bytes)
- `assets/fixtures/README.md` sha256 `a26761fb61c5675f758c52e64fd808cd28145e1956a26ede619322efbb4b948c` (1134 bytes)
- `assets/fixtures/groups_fixture.csv` sha256 `ef585bf562df3f929eb072a2a4f3f37bb8158ae074b6091f480c6a2ad747e3ab` (353 bytes)
- `assets/fixtures/groups_spec.json` sha256 `764edf6b4dcc55a7ee97499ef41fa0c66c9069815abe64d3de3229fd6510f2ab` (875 bytes)
- `assets/fixtures/relation_fixture.csv` sha256 `76bc2175b73423ac2d4fb359b22778073fa118ce99ea8259ddb9e356d58cb140` (184 bytes)
- `assets/fixtures/relation_spec.json` sha256 `77903211a979c96ca5605d2232cd10c996ae8f77646a53d2be2ab6ebca487b7a` (920 bytes)
- `floe.json` sha256 `b9f98de469d75f1b622e9ea83f5d3fa38cd560544237f7b768cae8151e43e1c0` (1513 bytes)
- `references/ADAPTATION-NOTES.md` sha256 `e4a5648a19964c9270c6ca18cc2790ff6270ad6c5bd20d152491fa469c38e57b` (9429 bytes)
- `references/assumptions_and_diagnostics.md` sha256 `6e1ebc110c092845b93e5c6d28f38c8a990780105ba1865f0bd47c007620b073` (14654 bytes)
- `references/bayesian_statistics.md` sha256 `34d62e1b20dd82a11497be40e07c93e4fdb555d56e4944e200f881c1b7629cbf` (14557 bytes)
- `references/dependencies.json` sha256 `66c63eebd64a27283003b4f25d9886be7e10b1f11336ccc367eddf09b1890bcf` (1519 bytes)
- `references/effect_sizes_and_power.md` sha256 `5e1321c9058b2931a1bd2a753c7a8f4295f58274412d62e99a34eabd478e42b2` (20907 bytes)
- `references/licenses/LICENSE-NOTE.md` sha256 `f6792e435d45d328e096f6634d0a7807fbe136601b088c3b6f76472e6565fb0a` (979 bytes)
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `09b02a3c9df3053c55531d503357a9c7cde275970e6c3ceaa1ddf5f0e90b40c1` (1068 bytes)
- `references/reporting_standards.md` sha256 `0a30a1bec63231c94c9c285977acaa4218c50a34c8385857d18f62c61ac817b7` (21469 bytes)
- `references/test_selection_guide.md` sha256 `e72e00b6ebe9450e5e84849503db223c4908a8d9a68c3b87cf0ab8ec3254fe83` (6950 bytes)
- `scripts/assumption_checks.py` sha256 `261c377cf32222c292d42e6f5679cb41b822a4716affa5ff9ec9403875ca59fa` (20884 bytes)
- `scripts/stats_run.py` sha256 `57e87c1d24a496bb9d3d4d6f4edfb210bfea5a70d9e52d4207f51220d975a227` (42948 bytes)
- `scripts/stats_verify.py` sha256 `cfc92b5feda5c6fd1e88545b45be3b5dc1bef62fe91de7562173aaf9198bcf2f` (24328 bytes)

TOTAL 20 files (PROVENANCE.md itself omitted by policy); scripts/fixtures/goldens byte-identical to the immutable original candidate.
