#!/usr/bin/env python3
"""wtp_analyzer.py — Van Westendorp Price Sensitivity Meter (PSM).

Implements the classical PSM analysis (van Westendorp, 1976). Each respondent answers
4 questions:

  1. Too cheap     — price at which you'd doubt the quality
  2. Bargain       — price that feels like a great deal
  3. Getting expensive — price where you'd start to hesitate
  4. Too expensive — price at which you would never buy

Computes the 4 intersection points:

  - OPP (Optimal Price Point):    intersection of "too cheap" and "too expensive"
  - IDP (Indifference Price Point): intersection of "bargain" and "getting expensive"
  - PMC (Point of Marginal Cheapness):  intersection of "too cheap" and "getting expensive"
  - PME (Point of Marginal Expensiveness): intersection of "bargain" and "too expensive"

Range of Acceptable Prices (RAP) = [PMC, PME].

Output: markdown or JSON. Stdlib only.

Usage:
    wtp_analyzer.py --input survey.json --output markdown
    wtp_analyzer.py --sample
"""
from __future__ import annotations

import argparse
import bisect
import json
import math
import random
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pricing_io import (  # noqa: E402
    PricingError,
    checked_input_file,
    emit,
    load_json,
    require_list,
    require_mapping,
    require_number,
    run_cli,
)

RESPONSE_KEYS = ("too_cheap", "bargain", "getting_expensive", "too_expensive")
MAX_RESPONDENTS = 20_000
MAX_PRICE = 1_000_000_000


@dataclass
class Curves:
    prices: list[float]
    too_cheap: list[float]          # P(too cheap >= price)  — decreasing in price
    bargain: list[float]            # P(bargain >= price)    — decreasing in price
    getting_expensive: list[float]  # P(getting expensive <= price) — increasing
    too_expensive: list[float]      # P(too expensive <= price)     — increasing


def validate_respondents(value: Any) -> list[dict[str, float]]:
    """Require complete, finite, non-negative responses for every respondent.

    The pinned upstream tool silently divided by the total respondent count
    when a question was missing, which biased every cumulative curve. PSM
    requires all four answers; a missing answer is a screening error here, not
    a zero.
    """

    rows = require_list(value, "respondents", max_items=MAX_RESPONDENTS)
    if not rows:
        raise PricingError("respondents must be a non-empty array")
    validated: list[dict[str, float]] = []
    for index, row in enumerate(rows, 1):
        item = require_mapping(row, f"respondents[{index}]")
        missing = [key for key in RESPONSE_KEYS if key not in item]
        if missing:
            raise PricingError(
                f"respondents[{index}] is missing: " + ", ".join(missing)
            )
        clean: dict[str, float] = {}
        for key in RESPONSE_KEYS:
            number = require_number(
                item[key],
                f"respondents[{index}].{key}",
                minimum=0,
                maximum=MAX_PRICE,
            )
            clean[key] = float(number)
        validated.append(clean)
    return validated


def build_price_grid(respondents: list[dict[str, float]]) -> list[float]:
    """Build a sorted unique-price grid from all responses."""
    prices: set[float] = set()
    for r in respondents:
        for k in ("too_cheap", "bargain", "getting_expensive", "too_expensive"):
            v = r.get(k)
            if v is not None:
                prices.add(float(v))
    grid = sorted(prices)
    if not grid:
        return []
    # Densify with intermediate steps to make intersection detection stable.
    densified: list[float] = []
    for i, p in enumerate(grid):
        densified.append(p)
        if i + 1 < len(grid):
            nxt = grid[i + 1]
            mid = (p + nxt) / 2.0
            if mid not in prices:
                densified.append(mid)
    return sorted(set(densified))


def cumulative_curves(respondents: list[dict[str, float]], grid: list[float]) -> Curves:
    """Compute the same counts as the pinned loop in O((n+g) log n).

    The grid is densified to roughly twice the unique response count, so the
    original per-grid-point scan became quadratic and took minutes at a few
    thousand respondents. Sorted arrays plus binary search preserve the exact
    >=/<= counts and therefore every intersection value.
    """

    n = len(respondents)
    too_cheap_sorted = sorted(r["too_cheap"] for r in respondents)
    bargain_sorted = sorted(r["bargain"] for r in respondents)
    getting_expensive_sorted = sorted(r["getting_expensive"] for r in respondents)
    too_expensive_sorted = sorted(r["too_expensive"] for r in respondents)
    too_cheap: list[float] = []
    bargain: list[float] = []
    getting_expensive: list[float] = []
    too_expensive: list[float] = []
    for p in grid:
        tc = n - bisect.bisect_left(too_cheap_sorted, p)
        bg = n - bisect.bisect_left(bargain_sorted, p)
        ge = bisect.bisect_right(getting_expensive_sorted, p)
        te = bisect.bisect_right(too_expensive_sorted, p)
        too_cheap.append(tc / n)
        bargain.append(bg / n)
        getting_expensive.append(ge / n)
        too_expensive.append(te / n)
    return Curves(grid, too_cheap, bargain, getting_expensive, too_expensive)


def find_intersection(prices: list[float], a: list[float], b: list[float]) -> float | None:
    """Find first price where curve a crosses curve b (linear interp between grid points)."""
    if len(prices) < 2:
        return None
    prev_diff = a[0] - b[0]
    for i in range(1, len(prices)):
        diff = a[i] - b[i]
        if prev_diff == 0:
            return prices[i - 1]
        if (prev_diff < 0 < diff) or (prev_diff > 0 > diff):
            # Linear interpolation
            p0, p1 = prices[i - 1], prices[i]
            t = prev_diff / (prev_diff - diff)
            return p0 + t * (p1 - p0)
        prev_diff = diff
    return None


@dataclass
class PSMResult:
    n: int
    opp: float | None
    idp: float | None
    pmc: float | None
    pme: float | None
    rap_low: float | None
    rap_high: float | None
    warnings: list[str]


def analyze(respondents: list[dict[str, float]]) -> PSMResult:
    respondents = validate_respondents(respondents)
    warnings: list[str] = []
    n = len(respondents)
    if n < 30:
        warnings.append(
            f"Sample size N={n} is below 30. PSM results are directional only; "
            "treat the range as a hypothesis, not a recommendation. Aim for N≥100."
        )
    elif n < 100:
        warnings.append(f"Sample size N={n} is acceptable but below the preferred N≥100 threshold.")

    # Sanity-check monotonicity (too_cheap < bargain < getting_expensive < too_expensive per respondent)
    inconsistent = 0
    for r in respondents:
        try:
            tc = float(r["too_cheap"])
            bg = float(r["bargain"])
            ge = float(r["getting_expensive"])
            te = float(r["too_expensive"])
        except (KeyError, TypeError, ValueError):
            inconsistent += 1
            continue
        if not (tc <= bg <= ge <= te):
            inconsistent += 1
    if inconsistent:
        warnings.append(
            f"{inconsistent} of {n} respondents have inconsistent price ordering "
            "(expected too_cheap ≤ bargain ≤ getting_expensive ≤ too_expensive). "
            "Consider screening these before reporting."
        )

    grid = build_price_grid(respondents)
    if not grid:
        return PSMResult(n=n, opp=None, idp=None, pmc=None, pme=None, rap_low=None, rap_high=None, warnings=warnings)

    c = cumulative_curves(respondents, grid)
    if len({tuple(row[key] for key in RESPONSE_KEYS) for row in respondents}) == 1:
        warnings.append(
            "All respondents gave identical answers; PSM intersections are not "
            "unique. Screen the sample or collect varied responses."
        )
    opp = find_intersection(c.prices, c.too_cheap, c.too_expensive)
    idp = find_intersection(c.prices, c.bargain, c.getting_expensive)
    pmc = find_intersection(c.prices, c.too_cheap, c.getting_expensive)
    pme = find_intersection(c.prices, c.bargain, c.too_expensive)
    if any(point is None for point in (opp, idp, pmc, pme)):
        warnings.append(
            "One or more intersection points were not identified; the curves may not "
            "cross inside the observed price range. Treat the missing values as unknown, "
            "not as zero."
        )
    if pmc is not None and pme is not None and pmc > pme:
        warnings.append(
            "The Range of Acceptable Prices is inverted (PMC > PME). Check the survey "
            "data and respondent screening before using this range."
        )

    return PSMResult(n=n, opp=opp, idp=idp, pmc=pmc, pme=pme, rap_low=pmc, rap_high=pme, warnings=warnings)


def _fmt(v: float | None) -> str:
    return f"{v:,.2f}" if v is not None else "n/a"


def render_markdown(res: PSMResult) -> str:
    lines: list[str] = []
    lines.append("# Van Westendorp PSM Analysis")
    lines.append("")
    lines.append(f"**Respondents:** N = {res.n}")
    lines.append("")
    if res.warnings:
        lines.append("> **Warnings:**")
        for w in res.warnings:
            lines.append(f"> - {w}")
        lines.append("")
    lines.append("## Four intersection points")
    lines.append("")
    lines.append("| Point | Definition | Value |")
    lines.append("|---|---|---|")
    lines.append(f"| **OPP** — Optimal Price Point | too cheap ↔ too expensive | {_fmt(res.opp)} |")
    lines.append(f"| **IDP** — Indifference Price Point | bargain ↔ getting expensive | {_fmt(res.idp)} |")
    lines.append(f"| **PMC** — Point of Marginal Cheapness | too cheap ↔ getting expensive | {_fmt(res.pmc)} |")
    lines.append(f"| **PME** — Point of Marginal Expensiveness | bargain ↔ too expensive | {_fmt(res.pme)} |")
    lines.append("")
    lines.append("## Range of Acceptable Prices (RAP)")
    lines.append("")
    if res.rap_low is not None and res.rap_high is not None:
        lines.append(f"**RAP = [{_fmt(res.rap_low)}, {_fmt(res.rap_high)}]**")
        lines.append("")
        lines.append("Prices outside this range are likely to be rejected as either too cheap (quality doubt) or too expensive (no purchase).")
    else:
        lines.append("RAP could not be computed — check input data and sample size.")
    lines.append("")
    lines.append("## Interpretation guidance")
    lines.append("")
    lines.append("- PSM gives a **range**, not the price. Final price is a commercial decision.")
    lines.append("- OPP is a theoretical mid-point — the price at which equal % of respondents reject as too cheap and too expensive.")
    lines.append("- IDP is the median respondent's perceived 'fair' price.")
    lines.append("- Re-run with segmented samples (ICP vs non-ICP) — overall PSM averages across segments hide structure.")
    lines.append("- Validate the upper end with willingness-to-pay experiments in market before anchoring at PME.")
    return "\n".join(lines)


def synthetic_sample(n: int = 50, seed: int = 17) -> list[dict[str, float]]:
    """Generate N synthetic respondents with realistic price ordering and segmentation noise."""
    rng = random.Random(seed)
    respondents: list[dict[str, float]] = []
    for _ in range(n):
        anchor = rng.gauss(80, 20)  # respondent's reference price
        anchor = max(20.0, anchor)
        tc = max(5.0, anchor * rng.uniform(0.3, 0.5))
        bg = anchor * rng.uniform(0.6, 0.85)
        ge = anchor * rng.uniform(0.95, 1.15)
        te = anchor * rng.uniform(1.3, 1.8)
        respondents.append({
            "too_cheap": round(tc, 2),
            "bargain": round(bg, 2),
            "getting_expensive": round(ge, 2),
            "too_expensive": round(te, 2),
        })
    return respondents


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--input", type=Path, help="Path to survey JSON: {respondents: [{too_cheap, bargain, getting_expensive, too_expensive}]}.")
    p.add_argument("--root", default=".", help="Workspace root the input must stay inside.")
    p.add_argument("--output", default="markdown", choices=["markdown", "json"], help="Output format (stdout only).")
    p.add_argument("--sample", action="store_true", help="Run with synthetic 50-respondent sample.")
    args = p.parse_args(argv)

    if args.sample and args.input:
        p.error("Use either --input or --sample, not both.")
    if args.sample:
        respondents = synthetic_sample(50)
    elif args.input:
        path = checked_input_file(args.input, root=args.root)
        data = load_json(path)
        respondents = data.get("respondents", data) if isinstance(data, dict) else data
    else:
        p.error("Provide --input or --sample.")
        return 2

    res = analyze(respondents)
    if args.output == "json":
        out = {
            "n": res.n,
            "opp": res.opp,
            "idp": res.idp,
            "pmc": res.pmc,
            "pme": res.pme,
            "rap": [res.rap_low, res.rap_high],
            "warnings": res.warnings,
        }
        emit(json.dumps(out, indent=2))
    else:
        emit(render_markdown(res))
    return 0


if __name__ == "__main__":
    sys.exit(run_cli(lambda: main(sys.argv[1:])))
