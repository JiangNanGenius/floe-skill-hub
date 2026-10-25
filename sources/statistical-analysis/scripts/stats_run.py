#!/usr/bin/env python3
"""Spec-driven statistical runner for the Floe statistical-analysis skill.

First-party Floe script (MIT (c) Floe project); NOT upstream K-Dense
content. It executes a prespecified analysis spec over a bounded local CSV
inside the task's resolved Linux environment and writes a reproducible JSON
result plus an optional APA-style Markdown report. Design rules:

* Prespecified, fail-closed analysis selection: every analysis in the spec
  names its exact method; unknown methods, non-finite values, degenerate
  samples and unmet structural requirements raise errors instead of
  silently switching to a different algorithm.
* Layered engines with honest boundaries: `descriptives` runs on the Python
  standard library alone; hypothesis tests require the declared dependency
  layer (numpy/scipy/pandas/statsmodels pins in floe.json); a missing layer
  produces an explicit provisioning error, never a quieter substitute.
* Missing-data policy: rows missing a used cell are omitted pairwise with
  reported counts; infinities are rejected; raw inputs are never modified.
* Assumption checks accompany each parametric test (Shapiro-Wilk per group
  with the n>5000 reliability caveat, Levene for two-group/ANOVA designs)
  and are reported as non-rejection screens - they never select the test.
* Reproducibility: the output records the spec digest, input digest, exact
  engine versions and the full result payload.

No network access. Outputs are written atomically; existing outputs require
--force.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

MIN_PYTHON = (3, 11)
MAX_ROWS = 1_000_000
MAX_COLUMNS = 512
DEFAULT_ALPHA = 0.05

ANALYSIS_TYPES = (
    "descriptives",
    "welch_ttest",
    "student_ttest",
    "paired_ttest",
    "one_way_anova",
    "kruskal_wallis",
    "mann_whitney",
    "wilcoxon",
    "chi2_independence",
    "fisher_exact_2x2",
    "pearson",
    "spearman",
    "ols",
    "power_ttest",
)


class StatsError(ValueError):
    """An expected validation failure with an actionable, value-free message."""


# --------------------------------------------------------------------------
# bounded input handling (stdlib; no third-party requirement)
# --------------------------------------------------------------------------

def read_table(path: Path, max_rows: int = MAX_ROWS) -> tuple[list[str], list[list[str]]]:
    """Read a bounded rectangular UTF-8 CSV without evaluating anything."""
    if not path.is_file():
        raise StatsError("the input file does not exist")
    if path.is_symlink():
        raise StatsError("symlinked inputs are not accepted")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, strict=True)
        try:
            header = next(reader)
        except StopIteration:
            raise StatsError("the table is empty") from None
        if not header or len(header) > MAX_COLUMNS:
            raise StatsError(f"the header must name 1..{MAX_COLUMNS} columns")
        if any(not name.strip() for name in header):
            raise StatsError("the table contains an empty column identifier")
        if len(set(header)) != len(header):
            raise StatsError("duplicate column identifiers are not accepted")
        rows = []
        for index, row in enumerate(reader):
            if index >= max_rows:
                raise StatsError(f"the table exceeds the {max_rows}-row bound")
            if len(row) != len(header):
                raise StatsError("the table contains a non-rectangular row")
            rows.append(row)
    if not rows:
        raise StatsError("the table has no data rows")
    return header, rows


def column_values(header: list[str], rows: list[list[str]], name: str) -> list[str]:
    if name not in header:
        raise StatsError(f"unknown column: {name!r}")
    index = header.index(name)
    return [row[index] for row in rows]


def numeric_column(header, rows, name: str) -> tuple[list[float], list[int], int]:
    """Finite floats with pairwise-missing positions; rejects infinities."""
    raw = column_values(header, rows, name)
    values: list[float] = []
    positions: list[int] = []
    missing = 0
    for position, cell in enumerate(raw):
        text = cell.strip()
        if not text:
            missing += 1
            continue
        try:
            number = float(text)
        except ValueError:
            raise StatsError(f"column {name!r} contains a non-numeric value") from None
        if not math.isfinite(number):
            raise StatsError(f"column {name!r} contains a non-finite value; rejected")
        values.append(number)
        positions.append(position)
    if not values:
        raise StatsError(f"column {name!r} has no non-missing numeric values")
    return values, positions, missing


def paired_numeric_columns(header, rows, name_a: str, name_b: str):
    """Align two columns row-wise; rows missing either cell are omitted."""
    raw_a = column_values(header, rows, name_a)
    raw_b = column_values(header, rows, name_b)
    a: list[float] = []
    b: list[float] = []
    omitted = 0
    for cell_a, cell_b in zip(raw_a, raw_b):
        text_a, text_b = cell_a.strip(), cell_b.strip()
        if not text_a or not text_b:
            omitted += 1
            continue
        try:
            value_a, value_b = float(text_a), float(text_b)
        except ValueError:
            raise StatsError(f"paired columns {name_a!r}/{name_b!r} contain non-numeric values") from None
        if not (math.isfinite(value_a) and math.isfinite(value_b)):
            raise StatsError(f"paired columns {name_a!r}/{name_b!r} contain non-finite values; rejected")
        a.append(value_a)
        b.append(value_b)
    if len(a) < 2:
        raise StatsError("paired analyses need at least two complete pairs")
    return a, b, omitted


def group_values(header, rows, value_col: str, group_col: str,
                 wanted: list[str] | None = None) -> dict[str, list[float]]:
    values_raw = column_values(header, rows, value_col)
    groups_raw = column_values(header, rows, group_col)
    grouped: dict[str, list[float]] = {}
    for cell, label in zip(values_raw, groups_raw):
        label = label.strip()
        if not label:
            raise StatsError("group labels must be non-missing")
        if wanted is not None and label not in wanted:
            continue
        text = cell.strip()
        if not text:
            grouped.setdefault(label, [])
            continue
        try:
            number = float(text)
        except ValueError:
            raise StatsError(f"column {value_col!r} contains a non-numeric value") from None
        if not math.isfinite(number):
            raise StatsError(f"column {value_col!r} contains a non-finite value; rejected")
        grouped.setdefault(label, []).append(number)
    if wanted is not None:
        missing_labels = [label for label in wanted if label not in grouped]
        if missing_labels:
            raise StatsError(f"requested groups absent from the data: {missing_labels}")
    return {label: grouped[label] for label in sorted(grouped)}


# --------------------------------------------------------------------------
# engine layer (declared pins; imported lazily and honestly)
# --------------------------------------------------------------------------

def require_layer(component: str):
    try:
        if component == "numpy":
            import numpy as np
            return np
        if component == "scipy":
            from scipy import stats
            return stats
        if component == "pandas":
            import pandas as pd
            return pd
        if component == "statsmodels":
            import statsmodels.api as sm
            return sm
    except ImportError as exc:
        raise StatsError(
            f"the declared dependency layer is not provisioned ({component}); "
            "provision the reviewed pins through the Floe environment/package "
            "flow (Debian guest: python3-numpy python3-scipy python3-pandas "
            "python3-statsmodels) - this runner never substitutes a quieter "
            "algorithm for a missing engine"
        ) from exc
    raise StatsError(f"unknown engine component: {component}")


def engine_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {"python": sys.version.split()[0]}
    for name in ("numpy", "scipy", "pandas", "statsmodels"):
        try:
            module = __import__(name)
            versions[name] = str(getattr(module, "__version__", "unknown"))
        except ImportError:
            versions[name] = None
    return versions


# --------------------------------------------------------------------------
# descriptives (stdlib-only path; exact)
# --------------------------------------------------------------------------

def descriptives(header, rows, spec: dict[str, Any]) -> dict[str, Any]:
    column = spec["column"]
    values, _, missing = numeric_column(header, rows, column)
    n = len(values)
    ordered = sorted(values)
    mean = statistics.fmean(values)
    return {
        "analysis": "descriptives",
        "column": column,
        "engine": "python-stdlib(statistics)",
        "n": n,
        "n_missing_omitted": missing,
        "mean": mean,
        "sample_standard_deviation": statistics.stdev(values) if n > 1 else None,
        "median": statistics.median(ordered),
        "q1": statistics.quantiles(ordered, n=4, method="inclusive")[0] if n > 1 else None,
        "q3": statistics.quantiles(ordered, n=4, method="inclusive")[2] if n > 1 else None,
        "minimum": ordered[0],
        "maximum": ordered[-1],
        "units": spec.get("units", "unspecified - record the measurement unit in the report"),
        "note": "stdlib path; no third-party package required",
    }


# --------------------------------------------------------------------------
# assumption screens (shared)
# --------------------------------------------------------------------------

def normality_screen(stats_mod, np, values: list[float], label: str) -> dict[str, Any]:
    if len(values) < 3:
        return {"group": label, "n": len(values), "screen": "not-run",
                "reason": "Shapiro-Wilk needs at least 3 observations"}
    if len(values) > 5000:
        return {"group": label, "n": len(values), "screen": "shapiro-wilk",
                "p_value_reliable": False,
                "note": "binary verdict withheld above 5000 observations (upstream caveat)"}
    statistic, p_value = stats_mod.shapiro(np.asarray(values, dtype=float))
    return {"group": label, "n": len(values), "screen": "shapiro-wilk",
            "statistic": float(statistic), "p_value": float(p_value),
            "normality_not_rejected": bool(p_value > DEFAULT_ALPHA),
            "p_value_reliable": True,
            "note": "non-rejection is not evidence of normality"}


def levene_screen(stats_mod, np, groups: dict[str, list[float]]) -> dict[str, Any] | None:
    arrays = [np.asarray(values, dtype=float) for values in groups.values() if len(values) >= 2]
    if len(arrays) < 2:
        return None
    statistic, p_value = stats_mod.levene(*arrays, center="median")
    return {"screen": "levene-brown-forsythe", "statistic": float(statistic),
            "p_value": float(p_value),
            "variance_equality_not_rejected": bool(p_value > DEFAULT_ALPHA),
            "note": "prespecify Welch rather than choosing by a variance pretest"}


def cohens_d(a: list[float], b: list[float]) -> tuple[float, float, float]:
    """Pooled-SD Cohen's d (signed a-b), Hedges' g and the pooled SD."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        raise StatsError("effect sizes need at least 2 observations per group")
    var_a = statistics.variance(a)
    var_b = statistics.variance(b)
    pooled_sd = math.sqrt(((na - 1) * var_a + (nb - 1) * var_b) / (na + nb - 2))
    if pooled_sd == 0:
        raise StatsError("pooled SD is zero; standardized effect size undefined")
    d = (statistics.fmean(a) - statistics.fmean(b)) / pooled_sd
    df = na + nb - 2
    j = 1.0 - 3.0 / (4.0 * df - 1.0)
    return d, d * j, pooled_sd


# --------------------------------------------------------------------------
# tests (declared layer)
# --------------------------------------------------------------------------

def welch_or_student_ttest(header, rows, spec, pooled: bool) -> dict[str, Any]:
    stats_mod = require_layer("scipy")
    np = require_layer("numpy")
    groups = group_values(header, rows, spec["value_column"], spec["group_column"],
                          wanted=[spec["group_a"], spec["group_b"]])
    a = groups[spec["group_a"]]
    b = groups[spec["group_b"]]
    if len(a) < 2 or len(b) < 2:
        raise StatsError("two-sample t-tests need at least 2 observations per group")
    alpha = float(spec.get("alpha", DEFAULT_ALPHA))
    result = stats_mod.ttest_ind(np.asarray(a), np.asarray(b), equal_var=not pooled,
                                 alternative=spec.get("alternative", "two-sided"))
    ci = result.confidence_interval(confidence_level=1.0 - alpha)
    d, g, pooled_sd = cohens_d(a, b)
    assumptions = {
        "normality_per_group": [normality_screen(stats_mod, np, a, spec["group_a"]),
                                 normality_screen(stats_mod, np, b, spec["group_b"])],
        "homogeneity": levene_screen(stats_mod, np, {spec["group_a"]: a, spec["group_b"]: b})
        if not pooled else None,
        "independence": "established by design review, never by this screen",
    }
    mean_diff = statistics.fmean(a) - statistics.fmean(b)
    name = "student_ttest" if pooled else "welch_ttest"
    return {
        "analysis": name,
        "engine": f"scipy.stats.ttest_ind(equal_var={pooled})",
        "group_a": {"label": spec["group_a"], "n": len(a), "mean": statistics.fmean(a)},
        "group_b": {"label": spec["group_b"], "n": len(b), "mean": statistics.fmean(b)},
        "mean_difference": mean_diff,
        "mean_difference_ci": [float(ci.low), float(ci.high)],
        "t_statistic": float(result.statistic),
        "df": float(result.df),
        "p_value": float(result.pvalue),
        "alternative": spec.get("alternative", "two-sided"),
        "alpha": alpha,
        "effect_sizes": {"cohens_d": d, "hedges_g": g, "pooled_sd": pooled_sd},
        "assumption_screens": assumptions,
        "interpretation": "p assesses incompatibility with the null; report the effect and its CI",
    }


def paired_ttest(header, rows, spec) -> dict[str, Any]:
    stats_mod = require_layer("scipy")
    np = require_layer("numpy")
    a, b, omitted = paired_numeric_columns(header, rows, spec["column_a"], spec["column_b"])
    differences = [x - y for x, y in zip(a, b)]
    zero_differences = sum(1 for d in differences if d == 0.0)
    result = stats_mod.ttest_rel(np.asarray(a), np.asarray(b),
                                 alternative=spec.get("alternative", "two-sided"))
    sd_diff = statistics.stdev(differences)
    dz = statistics.fmean(differences) / sd_diff if sd_diff > 0 else None
    alpha = float(spec.get("alpha", DEFAULT_ALPHA))
    ci = result.confidence_interval(confidence_level=1.0 - alpha)
    return {
        "analysis": "paired_ttest",
        "engine": "scipy.stats.ttest_rel",
        "n_pairs": len(a),
        "rows_omitted_missing_either_cell": omitted,
        "zero_differences": zero_differences,
        "mean_difference": statistics.fmean(differences),
        "mean_difference_ci": [float(ci.low), float(ci.high)],
        "t_statistic": float(result.statistic),
        "df": float(result.df),
        "p_value": float(result.pvalue),
        "alternative": spec.get("alternative", "two-sided"),
        "alpha": alpha,
        "effect_sizes": {"cohens_dz": dz},
        "assumption_screens": {
            "normality_of_differences": normality_screen(stats_mod, np, differences, "differences"),
            "note": "diagnose the paired differences, not the raw columns",
        },
    }


def one_way_anova(header, rows, spec) -> dict[str, Any]:
    stats_mod = require_layer("scipy")
    np = require_layer("numpy")
    groups = group_values(header, rows, spec["value_column"], spec["group_column"])
    arrays = {label: values for label, values in groups.items() if len(values) >= 1}
    if len(arrays) < 2:
        raise StatsError("one-way ANOVA needs at least two observed groups")
    for label, values in arrays.items():
        if len(values) < 2:
            raise StatsError(f"group {label!r} has fewer than 2 observations")
    result = stats_mod.f_oneway(*[np.asarray(v) for v in arrays.values()])
    # eta-squared from the between/within decomposition (exact closed form)
    all_values = [v for values in arrays.values() for v in values]
    grand_mean = statistics.fmean(all_values)
    ss_between = sum(len(v) * (statistics.fmean(v) - grand_mean) ** 2 for v in arrays.values())
    ss_total = sum((x - grand_mean) ** 2 for x in all_values)
    ss_within = ss_total - ss_between
    df_between = len(arrays) - 1
    df_within = len(all_values) - len(arrays)
    eta_sq = ss_between / ss_total if ss_total > 0 else None
    eta_p_sq = ss_between / (ss_between + ss_within) if (ss_between + ss_within) > 0 else None
    posthoc = None
    if spec.get("posthoc") == "tukey_hsd":
        hsd = stats_mod.tukey_hsd(*[np.asarray(v) for v in arrays.values()])
        labels = list(arrays)
        pairs = []
        for i in range(len(labels)):
            for j in range(i + 1, len(labels)):
                pairs.append({
                    "pair": [labels[i], labels[j]],
                    "statistic": float(hsd.statistic[i][j]),
                    "p_value": float(hsd.pvalue[i][j]),
                })
        posthoc = {"method": "scipy.stats.tukey_hsd (studentized range, no pooled-variance assumption beyond HSD)",
                   "pairs": pairs}
    elif spec.get("posthoc") is not None:
        raise StatsError(f"unsupported posthoc method: {spec['posthoc']!r} (only 'tukey_hsd' or omit)")
    return {
        "analysis": "one_way_anova",
        "engine": "scipy.stats.f_oneway",
        "groups": {label: {"n": len(v), "mean": statistics.fmean(v)} for label, v in arrays.items()},
        "F_statistic": float(result.statistic),
        "df": [df_between, df_within],
        "p_value": float(result.pvalue),
        "alpha": float(spec.get("alpha", DEFAULT_ALPHA)),
        "effect_sizes": {"eta_squared": eta_sq, "partial_eta_squared": eta_p_sq},
        "posthoc": posthoc,
        "assumption_screens": {
            "normality_per_group": [normality_screen(stats_mod, np, v, label) for label, v in arrays.items()],
            "homogeneity": levene_screen(stats_mod, np, arrays),
            "independence": "established by design review, never by this screen",
        },
        "note": "repeated measures or clustering require a model of that dependence, not one-way ANOVA",
    }


def kruskal_wallis(header, rows, spec) -> dict[str, Any]:
    stats_mod = require_layer("scipy")
    np = require_layer("numpy")
    groups = group_values(header, rows, spec["value_column"], spec["group_column"])
    arrays = [np.asarray(v) for v in groups.values() if len(v) >= 1]
    if len(arrays) < 2:
        raise StatsError("Kruskal-Wallis needs at least two observed groups")
    result = stats_mod.kruskal(*arrays)
    all_values = [v for values in groups.values() for v in values]
    n_total = len(all_values)
    k = len(arrays)
    epsilon_sq = float((result.statistic - (k - 1)) / (n_total - k)) if n_total > k else None
    return {
        "analysis": "kruskal_wallis",
        "engine": "scipy.stats.kruskal",
        "groups": {label: len(v) for label, v in groups.items()},
        "H_statistic": float(result.statistic),
        "df": k - 1,
        "p_value": float(result.pvalue),
        "alpha": float(spec.get("alpha", DEFAULT_ALPHA)),
        "effect_sizes": {"epsilon_squared": epsilon_sq},
        "note": "a rank contrast; not automatically a test of medians",
    }


def mann_whitney(header, rows, spec) -> dict[str, Any]:
    stats_mod = require_layer("scipy")
    np = require_layer("numpy")
    groups = group_values(header, rows, spec["value_column"], spec["group_column"],
                          wanted=[spec["group_a"], spec["group_b"]])
    a = groups[spec["group_a"]]
    b = groups[spec["group_b"]]
    result = stats_mod.mannwhitneyu(np.asarray(a), np.asarray(b),
                                    alternative=spec.get("alternative", "two-sided"))
    n1, n2 = len(a), len(b)
    rank_biserial = 1.0 - (2.0 * float(result.statistic)) / (n1 * n2)
    return {
        "analysis": "mann_whitney",
        "engine": "scipy.stats.mannwhitneyu (exact for small tie-free samples, normal approximation otherwise)",
        "group_a": {"label": spec["group_a"], "n": n1},
        "group_b": {"label": spec["group_b"], "n": n2},
        "U_statistic": float(result.statistic),
        "p_value": float(result.pvalue),
        "alternative": spec.get("alternative", "two-sided"),
        "alpha": float(spec.get("alpha", DEFAULT_ALPHA)),
        "effect_sizes": {"rank_biserial_r": rank_biserial,
                         "formula": "r = 1 - 2U/(n1*n2) with U for group_a"},
        "note": "a distribution/rank contrast; medians require an extra shape assumption",
    }


def wilcoxon(header, rows, spec) -> dict[str, Any]:
    stats_mod = require_layer("scipy")
    np = require_layer("numpy")
    a, b, omitted = paired_numeric_columns(header, rows, spec["column_a"], spec["column_b"])
    differences = [x - y for x, y in zip(a, b)]
    nonzero = [d for d in differences if d != 0.0]
    if len(nonzero) < 1:
        raise StatsError("Wilcoxon needs at least one non-zero paired difference")
    result = stats_mod.wilcoxon(np.asarray(differences),
                                alternative=spec.get("alternative", "two-sided"))
    n_r = len(nonzero)
    matched = rank_biserial = None
    try:
        matched = stats_mod.rankdata(np.abs(differences))
        r_plus = sum(m for m, d in zip(matched, differences) if d > 0)
        rank_biserial = (r_plus - (n_r * (n_r + 1) / 2 - r_plus)) / (n_r * (n_r + 1) / 2)
    except Exception:
        rank_biserial = None
    return {
        "analysis": "wilcoxon",
        "engine": "scipy.stats.wilcoxon",
        "n_pairs": len(a),
        "rows_omitted_missing_either_cell": omitted,
        "zero_differences_dropped_by_method": len(differences) - n_r,
        "W_statistic": float(result.statistic),
        "p_value": float(result.pvalue),
        "alternative": spec.get("alternative", "two-sided"),
        "alpha": float(spec.get("alpha", DEFAULT_ALPHA)),
        "effect_sizes": {"rank_biserial_r": rank_biserial},
        "note": "requires meaningfully symmetric paired differences",
    }


def contingency(header, rows, spec) -> tuple[list[list[int]], list[str], list[str]]:
    row_col = column_values(header, rows, spec["row_column"])
    col_col = column_values(header, rows, spec["column_column"]) if "column_column" in spec \
        else column_values(header, rows, spec["col_column"])
    row_labels = sorted({v.strip() for v in row_col if v.strip()})
    col_labels = sorted({v.strip() for v in col_col if v.strip()})
    table = [[0] * len(col_labels) for _ in row_labels]
    for r, c in zip(row_col, col_col):
        r, c = r.strip(), c.strip()
        if not r or not c:
            raise StatsError("contingency cells must be non-missing")
        table[row_labels.index(r)][col_labels.index(c)] += 1
    return table, row_labels, col_labels


def chi2_independence(header, rows, spec) -> dict[str, Any]:
    stats_mod = require_layer("scipy")
    np = require_layer("numpy")
    table, row_labels, col_labels = contingency(header, rows, spec)
    if len(row_labels) < 2 or len(col_labels) < 2:
        raise StatsError("chi-square independence needs at least a 2x2 table")
    correction = bool(spec.get("correction", True))
    observed = np.asarray(table, dtype=int)
    result = stats_mod.chi2_contingency(observed, correction=correction)
    n = int(observed.sum())
    k = min(len(row_labels), len(col_labels))
    cramers_v = math.sqrt(float(result.statistic) / (n * (k - 1))) if n > 0 and k > 1 else None
    expected_warning = None
    if float(np.min(result.expected_freq)) < 5:
        expected_warning = ("an expected frequency is below 5; consider fisher_exact_2x2 "
                            "or exact methods before interpreting")
    return {
        "analysis": "chi2_independence",
        "engine": f"scipy.stats.chi2_contingency(correction={correction})",
        "yates_correction_applied": correction and len(row_labels) == 2 and len(col_labels) == 2,
        "observed": {"row_labels": row_labels, "column_labels": col_labels, "table": table},
        "expected_frequencies": result.expected_freq.tolist(),
        "chi2_statistic": float(result.statistic),
        "df": int(result.dof),
        "p_value": float(result.pvalue),
        "alpha": float(spec.get("alpha", DEFAULT_ALPHA)),
        "effect_sizes": {"cramers_v": cramers_v},
        "warning": expected_warning,
    }


def fisher_exact_2x2(header, rows, spec) -> dict[str, Any]:
    stats_mod = require_layer("scipy")
    table, row_labels, col_labels = contingency(header, rows, spec)
    if len(row_labels) != 2 or len(col_labels) != 2:
        raise StatsError("fisher_exact_2x2 requires exactly a 2x2 table")
    odds_ratio, p_value = stats_mod.fisher_exact(table, alternative=spec.get("alternative", "two-sided"))
    return {
        "analysis": "fisher_exact_2x2",
        "engine": "scipy.stats.fisher_exact",
        "observed": {"row_labels": row_labels, "column_labels": col_labels, "table": table},
        "odds_ratio": float(odds_ratio) if math.isfinite(float(odds_ratio)) else None,
        "odds_ratio_note": "None means a zero cell made the OR infinite; report the table",
        "p_value": float(p_value),
        "alternative": spec.get("alternative", "two-sided"),
        "alpha": float(spec.get("alpha", DEFAULT_ALPHA)),
    }


def correlation(header, rows, spec, method: str) -> dict[str, Any]:
    stats_mod = require_layer("scipy")
    np = require_layer("numpy")
    x, y, omitted = paired_numeric_columns(header, rows, spec["x"], spec["y"])
    if len(x) < 3:
        raise StatsError("correlations need at least 3 complete pairs")
    if method == "pearson":
        result = stats_mod.pearsonr(np.asarray(x), np.asarray(y))
        r = float(result.statistic)
        n = len(x)
        fisher_z = math.atanh(r) if abs(r) < 1 else None
        if fisher_z is not None:
            se = 1.0 / math.sqrt(n - 3)
            z_crit = float(stats_mod.norm.ppf(1.0 - float(spec.get("alpha", DEFAULT_ALPHA)) / 2.0))
            ci = [math.tanh(fisher_z - z_crit * se), math.tanh(fisher_z + z_crit * se)]
        else:
            ci = [1.0, 1.0]
        engine = "scipy.stats.pearsonr"
    else:
        result = stats_mod.spearmanr(np.asarray(x), np.asarray(y))
        r = float(result.statistic)
        ci = None
        engine = "scipy.stats.spearmanr"
    return {
        "analysis": method,
        "engine": engine,
        "n_pairs": len(x),
        "rows_omitted_missing_either_cell": omitted,
        "r": r,
        "p_value": float(result.pvalue),
        "r_ci95": ci,
        "alpha": float(spec.get("alpha", DEFAULT_ALPHA)),
        "note": ("linear association; CI via Fisher z" if method == "pearson"
                 else "monotone rank association; no CI reported by this engine"),
    }


def ols(header, rows, spec) -> dict[str, Any]:
    sm = require_layer("statsmodels")
    np = require_layer("numpy")
    y_raw = column_values(header, rows, spec["y"])
    predictor_names = spec["predictors"]
    if not predictor_names:
        raise StatsError("ols needs at least one predictor")
    columns = [column_values(header, rows, name) for name in predictor_names]
    y: list[float] = []
    matrix_rows: list[list[float]] = []
    omitted = 0
    for index, cell in enumerate(y_raw):
        cells = [column[index] for column in columns]
        texts = [cell.strip()] + [c.strip() for c in cells]
        if any(not t for t in texts):
            omitted += 1
            continue
        try:
            parsed = [float(t) for t in texts]
        except ValueError:
            raise StatsError("ols columns must be numeric") from None
        if not all(math.isfinite(v) for v in parsed):
            raise StatsError("ols columns must be finite; rejected")
        y.append(parsed[0])
        matrix_rows.append(parsed[1:])
    if len(y) <= len(predictor_names) + 1:
        raise StatsError("ols needs more complete rows than predictors + intercept")
    exog = sm.add_constant(np.asarray(matrix_rows, dtype=float))
    if np.linalg.matrix_rank(exog) != exog.shape[1]:
        raise StatsError(
            "the design matrix is rank-deficient (collinear predictors); OLS "
            "coefficients are not identified - refusing to report a "
            "pseudo-inverse solution as if it were unique")
    model = sm.OLS(np.asarray(y, dtype=float), exog).fit()
    hc3 = None
    if spec.get("hc3"):
        robust = model.get_robustcov_results("HC3")
        hc3 = {
            "bse": [float(v) for v in robust.bse],
            "pvalues": [float(v) for v in robust.pvalues],
            "note": "HC3 addresses heteroscedasticity, not clustering or confounding",
        }
    names = ["const"] + list(predictor_names)
    ci = model.conf_int(alpha=float(spec.get("alpha", DEFAULT_ALPHA)))
    return {
        "analysis": "ols",
        "engine": "statsmodels.regression.linear_model.OLS",
        "n": int(model.nobs),
        "rows_omitted_missing_any_cell": omitted,
        "predictors": names,
        "coefficients": [float(v) for v in model.params],
        "std_errors": [float(v) for v in model.bse],
        "t_values": [float(v) for v in model.tvalues],
        "p_values": [float(v) for v in model.pvalues],
        "ci95": [[float(row[0]), float(row[1])] for row in ci],
        "r_squared": float(model.rsquared),
        "r_squared_adjusted": float(model.rsquared_adj),
        "F_statistic": float(model.fvalue),
        "F_p_value": float(model.f_pvalue),
        "df": [int(model.df_model), int(model.df_resid)],
        "hc3": hc3,
        "alpha": float(spec.get("alpha", DEFAULT_ALPHA)),
        "note": "exact OLS normal equations via statsmodels; no silent regularization",
    }


def power_ttest(spec) -> dict[str, Any]:
    require_layer("scipy")
    from statsmodels.stats.power import tt_ind_solve_power
    alpha = float(spec.get("alpha", DEFAULT_ALPHA))
    power = float(spec.get("power", 0.80))
    ratio = float(spec.get("ratio", 1.0))
    alternative = spec.get("alternative", "two-sided")
    mode = spec.get("solve_for", "n")
    if mode == "n":
        effect = spec.get("effect_size_d")
        if effect is None or float(effect) <= 0:
            raise StatsError("solve_for='n' requires a positive effect_size_d")
        n1 = tt_ind_solve_power(effect_size=float(effect), alpha=alpha, power=power,
                                ratio=ratio, alternative=alternative)
        return {
            "analysis": "power_ttest",
            "engine": "statsmodels.stats.power.tt_ind_solve_power",
            "solved_for": "n",
            "effect_size_d": float(effect),
            "alpha": alpha, "power": power, "ratio": ratio, "alternative": alternative,
            "n_per_group_exact": float(n1),
            "n_per_group_rounded_up": math.ceil(float(n1)),
            "n_second_group_rounded_up": math.ceil(float(n1) * ratio),
            "note": "independent equal-variance planning model; clustering/attrition need design-specific calculations",
        }
    if mode == "effect_size":
        n1 = spec.get("n_per_group")
        if n1 is None or int(n1) < 2:
            raise StatsError("solve_for='effect_size' requires n_per_group >= 2")
        detectable = tt_ind_solve_power(effect_size=None, nobs1=int(n1), alpha=alpha,
                                        power=power, ratio=ratio, alternative=alternative)
        return {
            "analysis": "power_ttest",
            "engine": "statsmodels.stats.power.tt_ind_solve_power",
            "solved_for": "effect_size (sensitivity analysis)",
            "n_per_group": int(n1),
            "alpha": alpha, "power": power, "ratio": ratio, "alternative": alternative,
            "detectable_d": float(detectable),
            "note": "post-hoc 'observed power' from an observed effect is circular; this is a sensitivity analysis",
        }
    raise StatsError(f"unknown solve_for: {mode!r}")


DISPATCH = {
    "welch_ttest": lambda h, r, s: welch_or_student_ttest(h, r, s, pooled=False),
    "student_ttest": lambda h, r, s: welch_or_student_ttest(h, r, s, pooled=True),
    "paired_ttest": paired_ttest,
    "one_way_anova": one_way_anova,
    "kruskal_wallis": kruskal_wallis,
    "mann_whitney": mann_whitney,
    "wilcoxon": wilcoxon,
    "chi2_independence": chi2_independence,
    "fisher_exact_2x2": fisher_exact_2x2,
    "pearson": lambda h, r, s: correlation(h, r, s, "pearson"),
    "spearman": lambda h, r, s: correlation(h, r, s, "spearman"),
    "ols": ols,
}


# --------------------------------------------------------------------------
# report rendering
# --------------------------------------------------------------------------

def apa_line(result: dict[str, Any]) -> str:
    analysis = result["analysis"]
    p = result.get("p_value")
    p_text = "p < .001" if p is not None and p < 0.001 else (f"p = {p:.3f}" if p is not None else "p = n/a")
    if analysis in ("welch_ttest", "student_ttest"):
        d = result["effect_sizes"]["cohens_d"]
        ci = result["mean_difference_ci"]
        name = "Welch t-test" if analysis == "welch_ttest" else "Student t-test"
        return (f"{name}: t({result['df']:.2f}) = {result['t_statistic']:.2f}, "
                f"{p_text}, d = {d:.2f}, 95% CI of difference [{ci[0]:.2f}, {ci[1]:.2f}]")
    if analysis == "paired_ttest":
        return (f"Paired t-test: t({result['df']:.2f}) = {result['t_statistic']:.2f}, {p_text}, "
                f"dz = {result['effect_sizes']['cohens_dz']:.2f}")
    if analysis == "one_way_anova":
        eta = result["effect_sizes"]["partial_eta_squared"]
        return (f"one-way ANOVA: F({result['df'][0]}, {result['df'][1]}) = {result['F_statistic']:.2f}, "
                f"{p_text}, partial eta^2 = {eta:.3f}")
    if analysis == "kruskal_wallis":
        return f"Kruskal-Wallis: H({result['df']}) = {result['H_statistic']:.2f}, {p_text}"
    if analysis == "mann_whitney":
        return (f"Mann-Whitney U = {result['U_statistic']:.1f}, {p_text}, "
                f"rank-biserial r = {result['effect_sizes']['rank_biserial_r']:.2f}")
    if analysis == "wilcoxon":
        return f"Wilcoxon W = {result['W_statistic']:.1f}, {p_text}"
    if analysis == "chi2_independence":
        return (f"chi-square({result['df']}) = {result['chi2_statistic']:.2f}, {p_text}, "
                f"Cramer's V = {result['effect_sizes']['cramers_v']:.2f}")
    if analysis == "fisher_exact_2x2":
        or_text = f"OR = {result['odds_ratio']:.2f}" if result["odds_ratio"] is not None else "OR undefined (zero cell)"
        return f"Fisher exact: {or_text}, {p_text}"
    if analysis in ("pearson", "spearman"):
        return f"{analysis} r = {result['r']:.3f}, {p_text}, n = {result['n_pairs']}"
    if analysis == "ols":
        return (f"OLS: R^2 = {result['r_squared']:.3f}, adj R^2 = {result['r_squared_adjusted']:.3f}, "
                f"F({result['df'][0]}, {result['df'][1]}) = {result['F_statistic']:.2f}, {p_text}")
    if analysis == "power_ttest":
        if result["solved_for"] == "n":
            return (f"power (t-test): d = {result['effect_size_d']:.2f}, alpha = {result['alpha']:.2f}, "
                    f"power = {result['power']:.2f} -> n = {result['n_per_group_rounded_up']} per group")
        return (f"sensitivity (t-test): n = {result['n_per_group']} per group -> detectable "
                f"d >= {result['detectable_d']:.2f}")
    if analysis == "descriptives":
        return (f"descriptives {result['column']}: n = {result['n']}, M = {result['mean']:.2f}, "
                f"SD = {result['sample_standard_deviation']:.2f}, Mdn = {result['median']:.2f}")
    return f"{analysis}: {p_text}"


def render_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Statistical analysis report (generated by stats_run.py)",
        "",
        f"- Spec digest: `{payload['reproducibility']['spec_sha256']}`",
        f"- Input digest: `{payload['reproducibility']['input_sha256']}`",
        f"- Engines: {json.dumps(payload['reproducibility']['engine_versions'], sort_keys=True)}",
        f"- Alpha default: {payload['alpha_default']}",
        "",
        "## Results",
        "",
    ]
    for result in payload["results"]:
        lines.append(f"### {result.get('label') or result['analysis']}")
        lines.append("")
        if result.get("status") == "failed":
            lines.append(f"- FAILED (fail-closed): {result['error']}")
        else:
            lines.append(f"- {apa_line(result)}")
            screens = result.get("assumption_screens")
            if screens:
                lines.append("- Assumption screens recorded (non-rejection semantics; they never select the test)")
        lines.append("")
    lines.extend([
        "## Standing caveats",
        "",
        "- Numerical screens cannot certify assumptions or scientific validity; independence comes from design review.",
        "- p-values assess incompatibility with the null; effect sizes with CIs support practical importance.",
        "- All planned analyses must be reported, including non-significant findings.",
        "- Units and estimands must be stated by the analyst; this runner does not infer them.",
        "",
    ])
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_spec(data_path: Path, spec: dict[str, Any]) -> dict[str, Any]:
    analyses = spec.get("analyses")
    if not isinstance(analyses, list) or not analyses:
        raise StatsError("the spec must carry a non-empty 'analyses' list")
    alpha_default = float(spec.get("alpha", DEFAULT_ALPHA))
    if not (0 < alpha_default < 1):
        raise StatsError("alpha must be in (0,1)")
    header, rows = read_table(data_path, max_rows=int(spec.get("max_rows", MAX_ROWS)))
    results: list[dict[str, Any]] = []
    for item in analyses:
        if not isinstance(item, dict) or "type" not in item:
            raise StatsError("each analysis entry must be an object with a 'type'")
        kind = item["type"]
        label = item.get("label", kind)
        if kind not in ANALYSIS_TYPES:
            raise StatsError(
                f"unknown analysis type {kind!r}; supported: {', '.join(ANALYSIS_TYPES)} "
                "(fail-closed: unsupported methods are refused, never substituted)")
        try:
            if kind == "descriptives":
                result = descriptives(header, rows, item)
            elif kind == "power_ttest":
                result = power_ttest(item)
            else:
                result = DISPATCH[kind](header, rows, item)
            result["label"] = label
            result["status"] = "ok"
            results.append(result)
        except StatsError as exc:
            results.append({"analysis": kind, "label": label, "status": "failed", "error": str(exc)})
    return {
        "schema_version": "1.0",
        "alpha_default": alpha_default,
        "results": results,
        "reproducibility": {
            "spec_sha256": None,   # filled by main (needs the spec bytes)
            "input_sha256": sha256_file(data_path),
            "engine_versions": engine_versions(),
            "rows_scanned": len(rows),
            "command": "python3 scripts/stats_run.py <data.csv> --spec <spec.json>",
        },
        "missing_data_policy": "pairwise omission with reported counts; infinities rejected; raw input never modified",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a prespecified statistical analysis spec over a bounded CSV.")
    parser.add_argument("data", type=Path, help="local CSV data file")
    parser.add_argument("--spec", type=Path, required=True, help="JSON analysis spec")
    parser.add_argument("--output", type=Path, required=True, help="JSON result path (new file)")
    parser.add_argument("--report", type=Path, help="optional APA-style Markdown report path")
    parser.add_argument("--force", action="store_true", help="allow replacing existing outputs")
    args = parser.parse_args(argv)
    if sys.version_info < MIN_PYTHON:
        print(f"[FAIL] Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ required", file=sys.stderr)
        return 2
    for path in (args.output, args.report):
        if path is not None and path.exists() and not args.force:
            print(f"[FAIL] refusing to overwrite {path} without --force", file=sys.stderr)
            return 2
    try:
        spec_bytes = args.spec.read_bytes()
        spec = json.loads(spec_bytes)
        payload = run_spec(args.data, spec)
        payload["reproducibility"]["spec_sha256"] = hashlib.sha256(spec_bytes).hexdigest()
    except (StatsError, OSError, json.JSONDecodeError) as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    failed = [r for r in payload["results"] if r.get("status") == "failed"]
    payload_bytes = (json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    tmp.write_bytes(payload_bytes)
    tmp.replace(args.output)
    if args.report is not None:
        report_tmp = args.report.with_suffix(args.report.suffix + ".tmp")
        report_tmp.write_text(render_report(payload), encoding="utf-8")
        report_tmp.replace(args.report)
    print(f"[OK] {len(payload['results']) - len(failed)} analyses succeeded, {len(failed)} failed")
    print(f"[OK] results: {args.output}")
    for result in failed:
        print(f"[FAIL-CLOSED] {result['label']}: {result['error']}", file=sys.stderr)
    return 0 if not failed else 3


if __name__ == "__main__":
    raise SystemExit(main())
