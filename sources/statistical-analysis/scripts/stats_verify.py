#!/usr/bin/env python3
"""Golden verifier for the Floe statistical-analysis adaptation.

First-party Floe script (MIT (c) Floe project); NOT upstream K-Dense
content. One offline command proves numerical correctness of the bundled
runner and assumption screens in the CURRENT environment:

  * the stdlib-only descriptives path (no third-party package required);
  * the declared dependency layer (numpy==2.2.4, scipy==1.15.3,
    pandas==2.2.3, statsmodels==0.14.4 - the exact versions the Debian 13
    guest provisions) against EMBEDDED goldens for every supported method.

Golden provenance: every embedded constant was computed twice during
adaptation - once by independent closed-form arithmetic (exact rational /
textbook formulas, e.g. Welch t and df, chi-square sum (O-E)^2/E, Fisher
2x2 hypergeometric p = 11/21, Mann-Whitney exact p = 2/C(12,6) for the
fully-separated fixture, Pearson r from raw sums) and once by the pinned
reference engines (scipy 1.15.3 / statsmodels 0.14.4 on Python 3.13). The
two agreed to <=1e-12 relative before embedding. Float comparisons here use
1e-8 relative tolerance for cross-architecture ulp noise; counts, df and
table entries are compared exactly.

Fail-closed semantics and the missing-data policy of stats_run.py are
exercised through negative tests. The verifier writes only to an ephemeral
temp directory and makes no network calls. Exit 0 only when every required
check passes; the dependency-layer checks are skipped honestly (or required
via --require-layer) when the layer is absent.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = SCRIPTS_DIR.parent
FIXTURES = PACKAGE_ROOT / "assets" / "fixtures"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

REL_TOL = 1e-8
DECLARED_PINS = {
    "numpy": "2.2.4",
    "scipy": "1.15.3",
    "pandas": "2.2.3",
    "statsmodels": "0.14.4",
}


class CheckFailure(Exception):
    """One failed golden/safety check with an actionable message."""


def _close(reference: float, candidate: Any, label: str) -> None:
    if isinstance(candidate, bool) or not isinstance(candidate, (int, float)):
        raise CheckFailure(f"{label}: expected a number, got {candidate!r}")
    if not math.isfinite(float(candidate)):
        raise CheckFailure(f"{label}: non-finite candidate {candidate!r}")
    scale = max(1.0, abs(reference), abs(float(candidate)))
    if abs(reference - float(candidate)) > REL_TOL * scale:
        raise CheckFailure(f"{label}: expected {reference!r}, got {candidate!r}")


def _exact(reference: Any, candidate: Any, label: str) -> None:
    if candidate != reference:
        raise CheckFailure(f"{label}: expected exactly {reference!r}, got {candidate!r}")


# --------------------------------------------------------------------------
# mandatory: stdlib descriptives path + input validation negatives
# --------------------------------------------------------------------------

def check_runtime() -> None:
    if sys.version_info < (3, 11):
        raise CheckFailure(
            f"Python {sys.version_info.major}.{sys.version_info.minor} is below the "
            "required 3.11 (the resolved Floe Linux guest provides 3.13)")


def check_stdlib_descriptives() -> None:
    import stats_run

    header, rows = stats_run.read_table(FIXTURES / "groups_fixture.csv")
    result = stats_run.descriptives(header, rows, {"column": "score", "units": "points"})
    # group A + B + C values = 10,12,14,16,18,19,21,22,24,26,28,30,15,16,17,18,19
    # (s18 score blank -> omitted with count); n = 17, sum = 325; the mean and SD
    # were verified with exact rational (Fraction) arithmetic before embedding.
    _exact("python-stdlib(statistics)", result["engine"], "descriptives engine")
    _exact(17, result["n"], "descriptives n")
    _exact(1, result["n_missing_omitted"], "descriptives missing omitted")
    _close(325.0 / 17.0, result["mean"], "descriptives mean")
    _exact(18.0, result["median"], "descriptives median")
    _exact(10.0, result["minimum"], "descriptives min")
    _exact(30.0, result["maximum"], "descriptives max")
    _close(5.4986629390831965, result["sample_standard_deviation"], "descriptives sd")
    _close(16.0, result["q1"], "descriptives q1")
    _close(22.0, result["q3"], "descriptives q3")


def check_input_validation(tmp: Path) -> None:
    import stats_run

    # non-rectangular table rejected
    ragged = tmp / "ragged.csv"
    ragged.write_text("a,b\n1,2\n3\n", encoding="utf-8")
    try:
        stats_run.read_table(ragged)
    except stats_run.StatsError:
        pass
    else:
        raise CheckFailure("non-rectangular tables must be rejected")
    # infinities rejected
    infinite = tmp / "inf.csv"
    infinite.write_text("a,b\n1,2\ninf,3\n", encoding="utf-8")
    header, rows = stats_run.read_table(infinite)
    try:
        stats_run.numeric_column(header, rows, "a")
    except stats_run.StatsError:
        pass
    else:
        raise CheckFailure("infinite values must be rejected")
    # unknown analysis type fails closed (never substituted) - a spec-level error
    try:
        stats_run.run_spec(FIXTURES / "groups_fixture.csv",
                           {"analyses": [{"type": "bayesian_ttest"}]})
    except stats_run.StatsError as exc:
        if "unknown analysis type" not in str(exc):
            raise CheckFailure(f"unexpected refusal message: {exc}") from None
    else:
        raise CheckFailure("unknown analysis types must fail closed")
    # unknown column is recorded as a failed analysis (fail-closed per entry,
    # never a silent numeric substitute) and surfaces in the exit code
    payload = stats_run.run_spec(FIXTURES / "groups_fixture.csv",
                                 {"analyses": [{"type": "descriptives", "column": "nope"}]})
    result = payload["results"][0]
    if result.get("status") != "failed" or "unknown column" not in result.get("error", ""):
        raise CheckFailure(f"unknown columns must fail closed, got {result!r}")
    out = tmp / "nope.json"
    code = stats_run.main([str(FIXTURES / "groups_fixture.csv"), "--spec",
                           str(_write_spec(tmp, {"analyses": [{"type": "descriptives", "column": "nope"}]})),
                           "--output", str(out)])
    _exact(3, code, "failed analyses must exit 3")


def check_rank_deficiency_refusal(tmp: Path) -> None:
    """A collinear design must be refused, never solved via pseudo-inverse."""
    import stats_run

    collinear = tmp / "collinear.csv"
    collinear.write_text(
        "x,y,z2\n1,2.0,2\n2,4.0,4\n3,5.0,6\n4,4.0,8\n5,5.0,10\n6,7.0,12\n",
        encoding="utf-8")
    spec_path = _write_spec(
        tmp, {"analyses": [{"type": "ols", "label": "collinear", "y": "y", "predictors": ["x", "z2"]}]},
        name="spec-collinear.json")
    out = tmp / "collinear.json"
    code = stats_run.main([str(collinear), "--spec", str(spec_path), "--output", str(out)])
    _exact(3, code, "rank-deficient OLS must exit 3 (fail-closed)")
    saved = json.loads(out.read_text(encoding="utf-8"))
    result = saved["results"][0]
    _exact("failed", result["status"], "rank-deficient OLS status")
    if "rank-deficient" not in result["error"]:
        raise CheckFailure(f"refusal message must name the rank deficiency: {result['error']}")


def _write_spec(tmp: Path, spec: dict, name: str = "spec-nope.json") -> Path:
    path = tmp / name
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# declared dependency layer: version pins + full golden battery
# --------------------------------------------------------------------------

def _base_version(raw: str) -> str:
    return raw.split("+", 1)[0]


def check_layer_versions(results: list[dict[str, Any]]) -> None:
    import stats_run

    versions = stats_run.engine_versions()
    detail: dict[str, Any] = {}
    missing = []
    for name, pin in DECLARED_PINS.items():
        installed = versions.get(name)
        if installed is None:
            missing.append(name)
            detail[name] = {"installed": None, "declared_pin": pin}
            continue
        detail[name] = {
            "installed": installed,
            "declared_pin": pin,
            "pin_matches_base_version": _base_version(installed) == pin,
        }
        if not detail[name]["pin_matches_base_version"]:
            raise CheckFailure(
                f"{name} installed {installed} does not match declared pin {pin} "
                "(Debian local suffixes like +dfsg are tolerated)")
    results.append({"name": "layer_versions", "status": "pass", "detail": detail})
    if missing:
        raise LayerMissing(missing)


class LayerMissing(Exception):
    """The declared dependency layer (or part of it) is not provisioned."""

    def __init__(self, missing: list[str]):
        super().__init__("missing: " + ", ".join(missing))
        self.missing = missing


def check_golden_battery() -> None:
    import stats_run

    groups_spec = json.loads((FIXTURES / "groups_spec.json").read_text(encoding="utf-8"))
    relation_spec = json.loads((FIXTURES / "relation_spec.json").read_text(encoding="utf-8"))
    groups = stats_run.run_spec(FIXTURES / "groups_fixture.csv", groups_spec)
    relation = stats_run.run_spec(FIXTURES / "relation_fixture.csv", relation_spec)
    by_label: dict[str, dict[str, Any]] = {}
    for payload in (groups, relation):
        for result in payload["results"]:
            if result.get("status") != "ok":
                raise CheckFailure(f"analysis {result.get('label')!r} failed: {result.get('error')}")
            by_label[result["label"]] = result

    # --- descriptives over score (n=17, one omitted) already checked above ---
    desc = by_label["score-descriptives"]
    _exact(17, desc["n"], "golden descriptives n")
    _close(325.0 / 17.0, desc["mean"], "golden descriptives mean")

    # --- Welch A vs B ---
    welch = by_label["welch-A-B"]
    _close(-10.333333333333334, welch["mean_difference"], "welch mean diff (89/6 - 151/6)")
    _close(-5.131156509334681, welch["t_statistic"], "welch t")
    _close(10.0, welch["df"], "welch df")
    _close(0.00044342843483424776, welch["p_value"], "welch p")
    _close(-14.82045069730743, welch["mean_difference_ci"][0], "welch ci low")
    _close(-5.846215969359237, welch["mean_difference_ci"][1], "welch ci high")
    _close(3.488074922742725, welch["effect_sizes"]["pooled_sd"], "welch pooled sd sqrt(73/6)")
    _close(-2.962474591918479, welch["effect_sizes"]["cohens_d"], "welch cohen d")
    _close(-2.734591931001673, welch["effect_sizes"]["hedges_g"], "welch hedges g")
    _exact(6, welch["group_a"]["n"], "welch n_a")
    screens = welch["assumption_screens"]
    _exact(2, len(screens["normality_per_group"]), "welch normality screens")
    if screens["homogeneity"] is None:
        raise CheckFailure("Welch must still record the Levene screen")

    # --- paired pre/post (n=18 complete pairs) ---
    paired = by_label["paired-pre-post"]
    _exact(18, paired["n_pairs"], "paired n")
    _exact(0, paired["rows_omitted_missing_either_cell"], "paired omissions")
    _close(4.737648414561807, paired["t_statistic"], "paired t")
    _exact(17.0, paired["df"], "paired df")
    _close(0.00019038676597104396, paired["p_value"], "paired p")
    _close(1.11667444027145, paired["effect_sizes"]["cohens_dz"], "paired dz")

    # --- one-way ANOVA over A/B/C (C has one omitted score -> n=5) ---
    anova = by_label["anova-groups"]
    _exact(5, anova["groups"]["C"]["n"], "anova group C n after omission")
    _close(18.719136262099784, anova["F_statistic"], "anova F")
    _exact([2, 14], anova["df"], "anova df")
    _close(0.00011063476671543443, anova["p_value"], "anova p")
    _close(0.7278291180285344, anova["effect_sizes"]["partial_eta_squared"], "anova partial eta2")
    pairs = {tuple(entry["pair"]): entry for entry in anova["posthoc"]["pairs"]}
    _close(-10.333333333333334, pairs[("A", "B")]["statistic"], "tukey A-B diff")
    _close(0.00012018179516215532, pairs[("A", "B")]["p_value"], "tukey A-B p")
    _close(0.4911550818084178, pairs[("A", "C")]["p_value"], "tukey A-C p")
    _close(0.0016460069648998044, pairs[("B", "C")]["p_value"], "tukey B-C p")

    # --- Mann-Whitney A vs B: complete separation, exact p = 2/C(12,6) ---
    mwu = by_label["mwu-A-B"]
    _exact(0.0, mwu["U_statistic"], "mwu U (complete separation)")
    _close(2.0 / math.comb(12, 6), mwu["p_value"], "mwu exact p = 2/924")
    _close(1.0, mwu["effect_sizes"]["rank_biserial_r"], "mwu rank-biserial")

    # --- Kruskal-Wallis ---
    kruskal = by_label["kruskal-groups"]
    _close(11.477162771627714, kruskal["H_statistic"], "kruskal H")
    _exact(2, kruskal["df"], "kruskal df")
    _close(0.003219332027523834, kruskal["p_value"], "kruskal p")
    _close(0.6769401979734082, kruskal["effect_sizes"]["epsilon_squared"], "kruskal epsilon2 (n=17 analyzed, s18 omitted)")

    # --- Wilcoxon pre/post (zeros dropped by method) ---
    wilcoxon = by_label["wilcoxon-pre-post"]
    _close(4.0, wilcoxon["W_statistic"], "wilcoxon W")
    _close(0.0012533756042178315, wilcoxon["p_value"], "wilcoxon p")
    _exact(3, wilcoxon["zero_differences_dropped_by_method"],
           "wilcoxon zero diffs (s10, s15, s17; W=4.0 equals the mean rank of the tied 0.5 band)")


def check_relation_goldens() -> None:
    import stats_run

    relation_spec = json.loads((FIXTURES / "relation_spec.json").read_text(encoding="utf-8"))
    relation = stats_run.run_spec(FIXTURES / "relation_fixture.csv", relation_spec)
    by_label = {r["label"]: r for r in relation["results"] if r.get("status") == "ok"}
    if len(by_label) != len(relation["results"]):
        failed = [r for r in relation["results"] if r.get("status") != "ok"]
        raise CheckFailure(f"relation analyses failed: {failed}")

    pearson = by_label["pearson-x-y"]
    _exact(10, pearson["n_pairs"], "pearson n")
    _close(0.9714656283979266, pearson["r"], "pearson r (closed form from raw sums)")
    _close(2.802220135803212e-06, pearson["p_value"], "pearson p")
    _close(0.880258537633845, pearson["r_ci95"][0], "pearson ci low (Fisher z)")
    _close(0.9934425506952999, pearson["r_ci95"][1], "pearson ci high (Fisher z)")

    spearman = by_label["spearman-x-y"]
    _close(0.9695302189773755, spearman["r"], "spearman rho")
    _close(3.634851475785749e-06, spearman["p_value"], "spearman p")

    chi2 = by_label["chi2-condition-response"]
    _exact(["A", "B"], chi2["observed"]["row_labels"], "chi2 row labels")
    _exact(["no", "yes"], chi2["observed"]["column_labels"], "chi2 column labels")
    _exact([[1, 4], [3, 2]], chi2["observed"]["table"], "chi2 observed table")
    _close(1.6666666666666665, chi2["chi2_statistic"], "chi2 (uncorrected sum (O-E)^2/E = 5/3)")
    _exact(1, chi2["df"], "chi2 df")
    _close(0.1967056024589432, chi2["p_value"], "chi2 p")
    _close(0.408248290463863, chi2["effect_sizes"]["cramers_v"], "cramers v = sqrt(1/6)")
    _exact(False, chi2["yates_correction_applied"], "chi2 correction flag off")

    chi2_y = by_label["chi2-yates"]
    _close(0.41666666666666663, chi2_y["chi2_statistic"], "yates-corrected chi2")
    _close(0.5186050164287255, chi2_y["p_value"], "yates-corrected p")

    fisher = by_label["fisher-2x2"]
    _close(1.0 / 6.0, fisher["odds_ratio"], "fisher OR = 1/6")
    _close(11.0 / 21.0, fisher["p_value"], "fisher exact p = 11/21 (hypergeometric, hand-computable)")

    ols = by_label["ols-y-x-z"]
    _exact(10, ols["n"], "ols n")
    # coefficients verified by exact rational normal equations:
    # beta = [2294/2235, 789/745, -52/1341]
    _close(2294.0 / 2235.0, ols["coefficients"][0], "ols intercept (exact 2294/2235)")
    _close(789.0 / 745.0, ols["coefficients"][1], "ols beta_x (exact 789/745)")
    _close(-52.0 / 1341.0, ols["coefficients"][2], "ols beta_z (exact -52/1341)")
    _close(0.9445084623974064, ols["r_squared"], "ols R2 (exact rational)")
    _close(0.9286537373680939, ols["r_squared_adjusted"], "ols adj R2")
    _close(59.57268010963195, ols["F_statistic"], "ols F (exact rational)")
    _exact([2, 7], ols["df"], "ols df")
    _close(1.6649340689366295e-05, ols["p_values"][1], "ols p(x)")
    _close(0.09356366340956687, ols["hc3"]["bse"][1], "ols HC3 se(x)")

    power_n = by_label["power-n"]
    _close(63.76561058785403, power_n["n_per_group_exact"], "power n exact (noncentral t)")
    _exact(64, power_n["n_per_group_rounded_up"], "power n rounded up")
    power_d = by_label["power-sensitivity"]
    _close(0.5658802975131417, power_d["detectable_d"], "detectable d at n=50")


def check_reproducibility_records(tmp: Path) -> None:
    import hashlib

    import stats_run

    spec_path = FIXTURES / "groups_spec.json"
    spec = json.loads(spec_path.read_bytes())
    payload = stats_run.run_spec(FIXTURES / "groups_fixture.csv", spec)
    expected_spec = hashlib.sha256(spec_path.read_bytes()).hexdigest()
    expected_input = hashlib.sha256((FIXTURES / "groups_fixture.csv").read_bytes()).hexdigest()
    _exact(expected_input, payload["reproducibility"]["input_sha256"], "input digest")
    versions = payload["reproducibility"]["engine_versions"]
    for name, pin in DECLARED_PINS.items():
        if versions.get(name) is None:
            raise CheckFailure(f"engine version record missing for {name}")
    # CLI end-to-end: real subprocess-free main() run writing outputs
    out = tmp / "result.json"
    report = tmp / "report.md"
    code = stats_run.main([str(FIXTURES / "groups_fixture.csv"), "--spec", str(spec_path),
                           "--output", str(out), "--report", str(report)])
    if code != 0:
        raise CheckFailure(f"stats_run.main exited {code}")
    saved = json.loads(out.read_text(encoding="utf-8"))
    _exact(expected_spec, saved["reproducibility"]["spec_sha256"], "spec digest recorded")
    body = report.read_text(encoding="utf-8")
    for marker in ("Welch t-test", "one-way ANOVA", "Mann-Whitney", "Standing caveats"):
        if marker not in body:
            raise CheckFailure(f"report lacks {marker!r}")
    # overwrite protection
    code = stats_run.main([str(FIXTURES / "groups_fixture.csv"), "--spec", str(spec_path),
                           "--output", str(out)])
    _exact(2, code, "overwrite without --force must exit 2")


def check_assumption_screens(tmp: Path) -> None:
    import numpy as np
    import pandas as pd

    import assumption_checks as ac
    import stats_run

    header, rows = stats_run.read_table(FIXTURES / "groups_fixture.csv")
    frame = pd.DataFrame(
        {name: stats_run.column_values(header, rows, name) for name in header}
    )
    frame["score"] = pd.to_numeric(frame["score"], errors="coerce")
    results = ac.comprehensive_assumption_check(frame, "score", "group", plot=False)
    for key in ("outliers_per_group", "normality_per_group", "homogeneity"):
        if key not in results:
            raise CheckFailure(f"comprehensive check lacks {key}")
    homogeneity = results["homogeneity"]
    _exact("Levene", homogeneity["test"], "levene test name")
    _exact("median", homogeneity["center"], "levene center (Brown-Forsythe)")
    normality = results["normality_per_group"]
    _exact(3, len(normality), "one normality row per group")
    # honest semantics: legacy labels mean non-rejection only
    if "normality_not_rejected" not in ac.check_normality(np.array([1.0, 2.0, 3.0, 4.0, 5.0]), plot=False):
        raise CheckFailure("normality results must carry non-rejection semantics")
    # plots are opt-in files, never interactive
    plots = tmp / "plots"
    plots.mkdir()
    ac.comprehensive_assumption_check(frame, "score", "group", plot=True, output_dir=str(plots))
    written = sorted(p.name for p in plots.iterdir())
    if not written or not all(name.endswith(".png") for name in written):
        raise CheckFailure(f"plot=True must write PNG files, got {written}")
    try:
        ac.check_normality(np.array([1.0, 2.0, 3.0, 4.0, 5.0]), plot=True)
    except ValueError:
        pass
    else:
        raise CheckFailure("plot=True without output_dir must be rejected")


# --------------------------------------------------------------------------
# runner
# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--require-layer", action="store_true",
        help="fail when the declared dependency layer is absent (use after provisioning)")
    parser.add_argument("--output", help="optional JSON report path")
    args = parser.parse_args()

    results: list[dict[str, Any]] = []
    failures: list[str] = []

    def record(name: str, function) -> None:
        # keep the verifier's stdout pure JSON: check noise goes to stderr
        with contextlib.redirect_stdout(sys.stderr):
            try:
                function()
                results.append({"name": name, "status": "pass"})
            except CheckFailure as exc:
                results.append({"name": name, "status": "fail", "error": str(exc)})
                failures.append(f"{name}: {exc}")
            except Exception as exc:
                results.append({"name": name, "status": "fail", "error": f"{type(exc).__name__}: {exc}"})
                failures.append(f"{name}: {type(exc).__name__}: {exc}")

    with tempfile.TemporaryDirectory(prefix="stats-verify-") as raw_tmp:
        tmp = Path(raw_tmp)
        record("runtime", check_runtime)
        record("stdlib_descriptives_goldens", check_stdlib_descriptives)
        record("input_validation", lambda: check_input_validation(tmp))

        layer_status = "pass"
        try:
            layer_results: list[dict[str, Any]] = []
            check_layer_versions(layer_results)
            results.extend(layer_results)
        except LayerMissing as exc:
            layer_status = "missing"
            results.append({"name": "layer_versions", "status": "missing", "detail": str(exc)})
            if args.require_layer:
                failures.append(
                    f"layer_versions: declared dependency layer not provisioned ({exc})")
        except CheckFailure as exc:
            results.append({"name": "layer_versions", "status": "fail", "error": str(exc)})
            failures.append(f"layer_versions: {exc}")

        if layer_status == "pass":
            record("golden_battery_groups", check_golden_battery)
            record("golden_battery_relations", check_relation_goldens)
            record("rank_deficiency_refusal", lambda: check_rank_deficiency_refusal(tmp))
            record("reproducibility_records", lambda: check_reproducibility_records(tmp))
            record("assumption_screens", lambda: check_assumption_screens(tmp))
        else:
            for name in ("golden_battery_groups", "golden_battery_relations",
                         "rank_deficiency_refusal",
                         "reproducibility_records", "assumption_screens"):
                results.append({"name": name, "status": f"skipped ({layer_status} layer)"})

    report = {
        "verifier": "stats_verify.py",
        "package": "statistical-analysis 1.0.0 (Floe adaptation)",
        "python": sys.version.split()[0],
        "ok": not failures,
        "layer_required": bool(args.require_layer),
        "declared_pins": DECLARED_PINS,
        "golden_tolerance_relative": REL_TOL,
        "checks": results,
        "failures": failures,
        "evidence_class": "runs wherever executed; guest execution evidence requires a real run in the resolved Linux environment",
    }
    payload = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
