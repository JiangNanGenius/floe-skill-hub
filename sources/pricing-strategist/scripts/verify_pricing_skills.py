#!/usr/bin/env python3
"""Deterministic offline self-check for the pricing-strategist scripts.

This is a Floe-added test harness, not an upstream file. It runs only local,
synthetic fixtures with the standard library: no network, no model/provider
call, no subprocess, no host fallback and no file output. A green result proves
the bundled calculations and refusal paths on the interpreter that executed it;
it does NOT prove market validity or execution in the App's Linux guest.

Usage (from the installed package root):
    python3 scripts/verify_pricing_skills.py
    python3 scripts/verify_pricing_skills.py --output json
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import packaging_designer as packaging  # noqa: E402
import pricing_model_picker as picker  # noqa: E402
import wtp_analyzer as wtp  # noqa: E402
from _pricing_io import (  # noqa: E402
    PricingError,
    checked_input_file,
    load_json,
    run_cli,
)

RESPONSE_KEYS = ("too_cheap", "bargain", "getting_expensive", "too_expensive")
CHECKS: list[dict[str, Any]] = []


def _capture(function: Callable[[], Any]) -> tuple[Any, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        value = function()
    return value, stdout.getvalue(), stderr.getvalue()


def check(name: str, function: Callable[[], Any]) -> None:
    try:
        detail = function()
    except Exception as exc:  # noqa: BLE001 - report the check, never hide it
        CHECKS.append(
            {"name": name, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
        )
        return
    CHECKS.append({"name": name, "ok": True, "detail": detail})


def _fixture(name: str) -> dict[str, Any]:
    path = checked_input_file(ROOT / "assets" / "fixtures" / name, root=ROOT)
    value = load_json(path)
    if not isinstance(value, dict):
        raise AssertionError(f"fixture {name} is not an object")
    return value


def _naive_psm(rows: list[dict[str, float]]) -> dict[str, float | None]:
    """Independent reference for the PSM curves and intersections."""

    prices = sorted({float(row[key]) for row in rows for key in RESPONSE_KEYS})
    densified: list[float] = []
    for index, price in enumerate(prices):
        densified.append(price)
        if index + 1 < len(prices):
            midpoint = (price + prices[index + 1]) / 2.0
            if midpoint not in prices:
                densified.append(midpoint)
    grid = sorted(set(densified))
    n = len(rows)
    curves = {key: [] for key in RESPONSE_KEYS}
    for price in grid:
        curves["too_cheap"].append(
            sum(1 for row in rows if row["too_cheap"] >= price) / n
        )
        curves["bargain"].append(
            sum(1 for row in rows if row["bargain"] >= price) / n
        )
        curves["getting_expensive"].append(
            sum(1 for row in rows if row["getting_expensive"] <= price) / n
        )
        curves["too_expensive"].append(
            sum(1 for row in rows if row["too_expensive"] <= price) / n
        )

    def intersection(first: str, second: str) -> float | None:
        a, b = curves[first], curves[second]
        previous = a[0] - b[0]
        for index in range(1, len(grid)):
            difference = a[index] - b[index]
            if previous == 0:
                return grid[index - 1]
            if (previous < 0 < difference) or (previous > 0 > difference):
                fraction = previous / (previous - difference)
                return grid[index - 1] + fraction * (grid[index] - grid[index - 1])
            previous = difference
        return None

    return {
        "opp": intersection("too_cheap", "too_expensive"),
        "idp": intersection("bargain", "getting_expensive"),
        "pmc": intersection("too_cheap", "getting_expensive"),
        "pme": intersection("bargain", "too_expensive"),
    }


def check_picker() -> None:
    brief = _fixture("brief_valid.json")
    validated = picker.validate_context(brief)
    assert validated is brief
    ranked = picker.score_models(validated, "saas")
    assert [row.model for row in ranked] == sorted(
        [row.model for row in ranked],
        key=lambda model: -next(item.score for item in ranked if item.model == model),
    )
    assert len(ranked) == 5
    assert len({row.model for row in ranked}) == 5
    assert all(0 <= row.score <= 100 for row in ranked)
    assert all(row.tradeoffs for row in ranked)
    assert ranked[0].model == "hybrid" and ranked[0].score == 95

    def cli() -> dict[str, Any]:
        def run() -> int:
            return picker.main(
                ["--input", str(ROOT / "assets/fixtures/brief_valid.json"), "--output", "json"]
            )

        _, stdout, stderr = _capture(run)
        assert not stderr
        report = json.loads(stdout)
        assert len(report["ranked"]) == 5
        assert report["ranked"][0]["model"] == "hybrid"
        return {"ranked": len(report["ranked"]), "top": report["ranked"][0]["model"]}

    check("picker_scoring_invariants", lambda: {"top": ranked[0].model, "score": ranked[0].score})
    check("picker_cli_json", cli)


def check_packaging() -> None:
    sample = packaging.sample_input()
    segments, prices, features = packaging.validate_input(sample)
    tiers = packaging.assign_tiers(features, segments, "saas")
    packaging.price_tiers(tiers, prices, "saas")
    flags = packaging.detect_anti_patterns(tiers)
    assigned = [feature.name for key in ("good", "better", "best") for feature in tiers[key].features]
    assert sorted(assigned) == sorted(feature.name for feature in features)
    assert len(assigned) == len(set(assigned)) == 9
    assert (tiers["good"].price, tiers["better"].price, tiers["best"].price) == (49.0, 149.0, 499.0)
    assert any("upgrade trigger" in flag for flag in flags)

    def no_anchor() -> dict[str, Any]:
        data = _fixture("features_valid.json")
        segments, prices, features = packaging.validate_input(data)
        tiers = packaging.assign_tiers(features, segments, "saas")
        packaging.price_tiers(tiers, prices, "saas")
        flags = packaging.detect_anti_patterns(tiers)
        assert prices["best"] == 0.0
        assert tiers["best"].price == 0.0
        assert any("no published anchor price" in flag for flag in flags)
        return {"best_price": tiers["best"].price, "flags": len(flags)}

    check("packaging_assignment", lambda: {"assigned": len(assigned), "flags": len(flags)})
    check("packaging_explicit_zero_anchor", no_anchor)


def check_wtp() -> None:
    survey = _fixture("survey_valid.json")
    rows = survey["respondents"]
    result = wtp.analyze(rows)
    reference = _naive_psm(rows)
    for key in ("opp", "idp", "pmc", "pme"):
        actual = getattr(result, key)
        expected = reference[key]
        if actual is None or expected is None:
            assert actual is expected
        else:
            assert abs(actual - expected) <= 1e-12, (key, actual, expected)
    assert result.n == 40
    assert result.rap_low is not None and result.rap_high is not None
    assert result.rap_low <= result.rap_high
    assert any("N=40" in warning for warning in result.warnings)

    sample = wtp.analyze(wtp.synthetic_sample(50))
    assert sample.n == 50
    assert all(getattr(sample, key) is not None for key in ("opp", "idp", "pmc", "pme"))
    assert sample.rap_low <= sample.rap_high

    identical = wtp.analyze(
        [{"too_cheap": 10, "bargain": 20, "getting_expensive": 30, "too_expensive": 40}] * 3
    )
    assert any("identical answers" in warning for warning in identical.warnings)

    check(
        "wtp_naive_equivalence",
        lambda: {
            "n": result.n,
            "opp": result.opp,
            "idp": result.idp,
            "pmc": result.pmc,
            "pme": result.pme,
        },
    )
    check("wtp_sample_and_degenerate", lambda: {"sample_n": sample.n})


def check_malformed() -> None:
    cases: list[tuple[str, Callable[[], Any]]] = [
        ("picker_list", lambda: picker.validate_context([])),
        ("picker_bad_pattern", lambda: picker.validate_context({"consumption_pattern": "x"})),
        ("picker_bad_count", lambda: picker.validate_context({"customer_count": "many"})),
        ("picker_bool_count", lambda: picker.validate_context({"customer_count": True})),
        ("picker_negative_deal", lambda: picker.validate_context({"deal_size_avg": -1})),
        ("picker_unknown_signal", lambda: picker.validate_context({"consumption_pattern": {"seat_based": 0.5}})),
        ("picker_value_drivers_type", lambda: picker.validate_context({"value_drivers": "x"})),
        ("picker_control_text", lambda: picker.validate_context({"industry": "a\nb"})),
        ("packaging_no_features", lambda: packaging.validate_input({})),
        ("packaging_empty_features", lambda: packaging.validate_input({"features": []})),
        ("packaging_missing_name", lambda: packaging.validate_input({"features": [{"importance": 0.5}]})),
        ("packaging_duplicate_names", lambda: packaging.validate_input({"features": [{"name": "A"}, {"name": "A"}]})),
        ("packaging_bad_importance", lambda: packaging.validate_input({"features": [{"name": "A", "importance": 2}]})),
        ("packaging_bad_fit", lambda: packaging.validate_input({"features": [{"name": "A", "segment_fit": []}]})),
        ("packaging_negative_best", lambda: packaging.validate_input({"features": [{"name": "A"}], "current_pricing": {"best": -1}})),
        ("packaging_duplicate_segments", lambda: packaging.validate_input({"segments": ["S", "S"], "features": [{"name": "A"}]})),
        ("wtp_empty", lambda: wtp.validate_respondents([])),
        ("wtp_missing_key", lambda: wtp.validate_respondents([{"too_cheap": 1, "bargain": 2, "getting_expensive": 3}])),
        ("wtp_string_row", lambda: wtp.validate_respondents(["x"])),
        ("wtp_negative", lambda: wtp.validate_respondents([{"too_cheap": -1, "bargain": 2, "getting_expensive": 3, "too_expensive": 4}])),
        ("wtp_nan", lambda: wtp.validate_respondents([{"too_cheap": float("nan"), "bargain": 2, "getting_expensive": 3, "too_expensive": 4}])),
        ("wtp_bool", lambda: wtp.validate_respondents([{"too_cheap": True, "bargain": 2, "getting_expensive": 3, "too_expensive": 4}])),
        ("wtp_too_many", lambda: wtp.validate_respondents([{"too_cheap": 1, "bargain": 2, "getting_expensive": 3, "too_expensive": 4}] * (wtp.MAX_RESPONDENTS + 1))),
    ]
    failures: list[str] = []
    for name, function in cases:
        try:
            function()
        except PricingError:
            continue
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{name}: wrong error {type(exc).__name__}")
            continue
        failures.append(f"{name}: accepted")
    assert not failures, failures

    def file_gates() -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "dup.json").write_text('{"a":1,"a":2}', encoding="utf-8")
            (root / "nan.json").write_text('{"a":NaN}', encoding="utf-8")
            (root / "bad.json").write_text("{", encoding="utf-8")
            (root / "big.json").write_text("{}", encoding="utf-8")
            (root / "target.json").write_text("{}", encoding="utf-8")
            (root / "link.json").symlink_to(root / "target.json")
            (root / "dir").mkdir()
            for name in ("dup.json", "nan.json", "bad.json"):
                try:
                    load_json(checked_input_file(name, root=root))
                except PricingError:
                    continue
                raise AssertionError(f"{name} was accepted")
            for value in ("link.json", "dir", "../target.json", "/etc/passwd", "https://example.com/x.json"):
                try:
                    checked_input_file(value, root=root)
                except PricingError:
                    continue
                raise AssertionError(f"path gate accepted {value}")
            try:
                checked_input_file("big.json", root=root, max_bytes=1)
            except PricingError:
                pass
            else:
                raise AssertionError("oversized input was accepted")
        return {"gates": 9}

    check("malformed_values_refused", lambda: {"cases": len(cases)})
    check("file_and_path_gates", file_gates)


def check_offline_and_output() -> None:
    forbidden = ("socket", "urllib", "http.client", "requests", "subprocess", "ctypes")
    names = ("pricing_model_picker.py", "packaging_designer.py", "wtp_analyzer.py", "_pricing_io.py")
    inspected = 0
    for name in names:
        text = (HERE / name).read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in text, (name, marker)
        assert "os.system" not in text and "popen" not in text.lower()
        inspected += 1

    def stdout_only() -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as directory:
            previous = os.getcwd()
            os.chdir(directory)
            try:
                for module, flag in (
                    (picker, "--sample"),
                    (wtp, "--sample"),
                    (packaging, "--sample"),
                ):
                    def run(mod=module, arg=flag) -> int:
                        return mod.main([arg, "--output", "json"])

                    _, stdout, stderr = _capture(run)
                    assert stdout and not stderr
                assert os.listdir(".") == []
            finally:
                os.chdir(previous)
        return {"scripts": 3, "files_created": 0}

    def refusal_codes() -> dict[str, Any]:
        def failing() -> None:
            raise PricingError("synthetic refusal")

        def interrupted() -> None:
            raise KeyboardInterrupt

        code, _, stderr = _capture(lambda: run_cli(failing))
        assert "Traceback" not in stderr and "error: synthetic refusal" in stderr
        assert code == 2
        code, _, _ = _capture(lambda: run_cli(interrupted))
        assert code == 130
        return {"expected_error": 2, "interrupt": 130}

    check("no_network_or_process_imports", lambda: {"files": inspected})
    check("stdout_only", stdout_only)
    check("refusal_exit_codes", refusal_codes)

    def deterministic() -> dict[str, Any]:
        outputs = []
        for _ in range(2):
            _, stdout, _ = _capture(lambda: picker.main(["--sample", "--output", "json"]))
            outputs.append(stdout)
        assert outputs[0] == outputs[1]
        outputs = []
        for _ in range(2):
            _, stdout, _ = _capture(lambda: wtp.main(["--sample", "--output", "json"]))
            outputs.append(stdout)
        assert outputs[0] == outputs[1]
        return {"repeatable": True}

    check("deterministic_output", deterministic)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", default="json", choices=["json", "text"], help="Report format.")
    args = parser.parse_args(argv)

    check_picker()
    check_packaging()
    check_wtp()
    check_malformed()
    check_offline_and_output()

    ok = all(item["ok"] for item in CHECKS)
    report = {
        "ok": ok,
        "checks": CHECKS,
        "checkCount": len(CHECKS),
        "failedCount": sum(1 for item in CHECKS if not item["ok"]),
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "scope": "Deterministic synthetic self-check. A green result is not market validation and not App/Linux-guest qualification.",
        "network": "not used",
    }
    if args.output == "text":
        for item in CHECKS:
            mark = "PASS" if item["ok"] else "FAIL"
            print(f"{mark} {item['name']}")
            if not item["ok"]:
                print(f"     {item['error']}")
        print(f"ok={ok} checks={len(CHECKS)} failed={report['failedCount']}")
    else:
        print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
