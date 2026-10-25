#!/usr/bin/env python3
"""Bundled-fixture golden verifier for the Floe EDA adaptation.

First-party Floe script (MIT (c) Floe project); NOT upstream K-Dense
content. It proves, in one offline command, that the bundled bounded EDA
tools still compute the exact expected results in the CURRENT interpreter
and environment:

  * the stdlib core path (mandatory) against hand-computable goldens;
  * the safety contract (root confinement, symlink/traversal/overwrite
    rejection, fail-closed unknown formats) via negative tests;
  * the declared optional numpy layer (NPY/NPZ bounded inspection);
  * the declared optional pandas layer via pandas_profile.py, whose
    cross-engine consistency check must report zero deviations;
  * every bundled CLI end-to-end through a real subprocess.

Expected aggregates for the shipped synthetic fixtures are computable by
hand from assets/fixtures/*.csv (for example `value` = 10,12,18,14,100,
16,20 with one NA: mean 190/7, median 16, q1 13, q3 19, fences [4,28],
one value outside, mean-without-fence-values 15). Goldens use exact
integer equality where the value is an integer and a relative tolerance
of 1e-12 for floats.

The verifier writes nothing outside an ephemeral temporary directory and
makes no network calls. Exit status: 0 only when every required check
passes; optional layers are skipped honestly unless --require-optional.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = SCRIPTS_DIR.parent
FIXTURES = PACKAGE_ROOT / "assets" / "fixtures"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

TOLERANCE = 1e-12
DECLARED_OPTIONAL_PINS = {"numpy": "2.2.4", "pandas": "2.2.3"}


class CheckFailure(Exception):
    """One failed golden/safety check with an actionable message."""


def _close(reference: float, candidate: float) -> bool:
    scale = max(1.0, abs(reference), abs(candidate))
    return abs(reference - candidate) <= TOLERANCE * scale


def _eq_int(reference: int, candidate: Any, label: str) -> None:
    if isinstance(candidate, bool) or not isinstance(candidate, int) or candidate != reference:
        raise CheckFailure(f"{label}: expected exact integer {reference}, got {candidate!r}")


def _eq_float(reference: float, candidate: Any, label: str) -> None:
    if not isinstance(candidate, (int, float)) or isinstance(candidate, bool):
        raise CheckFailure(f"{label}: expected a number, got {candidate!r}")
    if not _close(reference, float(candidate)):
        raise CheckFailure(f"{label}: expected {reference!r}, got {candidate!r}")


def _eq(value: Any, reference: Any, label: str) -> None:
    if value != reference:
        raise CheckFailure(f"{label}: expected {reference!r}, got {value!r}")


# ----------------------------------------------------------------------
# mandatory stdlib checks
# ----------------------------------------------------------------------

def check_runtime(results: list[dict[str, Any]]) -> None:
    version = sys.version_info
    if version < (3, 11):
        raise CheckFailure(
            f"Python {version.major}.{version.minor} is below the required 3.11 "
            "(the resolved Floe Linux guest provides 3.13)"
        )


def check_capability_registry(results: list[dict[str, Any]]) -> None:
    import _capabilities as capabilities

    automated = set(capabilities.AUTOMATED_FORMATS)
    _eq(automated, {".csv", ".tsv", ".json", ".npy", ".npz"}, "automated formats")
    for suffix in (".h5", ".hdf5", ".fastq", ".png", ".tiff", ".ome.tif"):
        entry = capabilities.REFERENCE_ONLY_FORMATS.get(suffix)
        if entry is None or entry["tier"] != "reference_only":
            raise CheckFailure(f"{suffix} must stay reference-only in the Floe release")
        if "not bundled" not in entry["depth"]:
            raise CheckFailure(f"{suffix} reference row lost the not-bundled note")
    # fail-closed on unknown extensions (.qqq is not a registered suffix)
    try:
        capabilities.suffix_key(Path("mystery.qqq"))
    except capabilities.CliError:
        pass
    else:
        raise CheckFailure("unknown extensions must fail closed")


def check_stdlib_profile_goldens(tmp: Path) -> None:
    from _tabular import profile_table

    report = profile_table(
        FIXTURES / "profile_fixture.csv",
        max_rows=1000,
        missing_tokens=["NA"],
        reveal_identifiers=True,
    )
    _eq_int(8, report["rows_scanned"], "profile rows_scanned")
    _eq(report["row_limit_reached"], False, "profile row_limit_reached")
    columns = {c["column_id"]: c for c in report["columns"]}
    value = columns["value"]
    _eq(value["inferred_kind"], "integer", "value inferred_kind with NA token")
    _eq_int(1, value["missing_count"], "value missing_count")
    _eq_int(7, value["numeric_parse_count"], "value numeric_parse_count")
    aggregates = value["numeric_aggregates"]
    _eq_int(7, aggregates["count"], "value count")
    _eq_float(190.0 / 7.0, aggregates["mean"], "value mean")
    _eq_float(16.0, aggregates["median"], "value median")
    _eq_float(10.0, aggregates["minimum"], "value minimum")
    _eq_float(100.0, aggregates["maximum"], "value maximum")
    _eq_float(13.0, aggregates["q1"], "value q1")
    _eq_float(19.0, aggregates["q3"], "value q3")
    # sample SD of [10,12,18,14,100,16,20]: sqrt(6262.857142.../6)
    _eq_float(32.308041163300565, aggregates["sample_standard_deviation"], "value sd")
    count = columns["count"]
    _eq(count["inferred_kind"], "integer", "count inferred_kind")
    _eq_float(4.5, count["numeric_aggregates"]["mean"], "count mean")
    _eq_float(2.449489742783178, count["numeric_aggregates"]["sample_standard_deviation"], "count sd (sqrt 6)")
    note = columns["note"]
    _eq(note["inferred_kind"], "text", "note inferred_kind")
    _eq_int(0, note["numeric_parse_count"], "note numeric_parse_count")
    _eq(report["raw_values_emitted"], False, "profile raw_values_emitted")


def check_missingness_leakage_goldens(tmp: Path) -> None:
    from _tabular import audit_missingness_and_leakage

    audit = audit_missingness_and_leakage(
        FIXTURES / "leak_fixture.csv",
        max_rows=100,
        group_column="group",
        entity_column="subject_id",
        split_column="split",
        time_column="obs_time",
        missing_tokens=None,
        reveal_identifiers=True,
    )
    leakage = audit["leakage_audit"]
    _eq(leakage["status"], "potential_leakage_detected", "leakage status")
    _eq_int(2, leakage["entity_tokens_in_multiple_splits"], "entities across splits")
    _eq_int(1, leakage["overlapping_split_time_interval_pairs"], "overlapping time pairs")
    gaps = {g["column_id"]: g["maximum_group_missingness_gap"] for g in audit["maximum_group_missingness_gaps"]}
    _eq_float(1.0 / 3.0, gaps["measurement"], "measurement worst-group gap")
    _eq_float(0.0, gaps["split"], "split worst-group gap")
    _eq(audit["automatic_imputation_or_deletion"], False, "no automatic imputation")


def check_distribution_goldens(tmp: Path) -> None:
    from _tabular import audit_distributions

    audit = audit_distributions(
        FIXTURES / "profile_fixture.csv",
        columns=["value"],
        max_rows=1000,
        missing_tokens=["NA"],
        reveal_identifiers=True,
    )
    column = audit["columns"][0]
    _eq(column["column_id"], "value", "distribution column")
    location = column["location_and_scale"]
    _eq_float(4.0, location["median_absolute_deviation"], "value MAD")
    _eq_float(6.0, location["interquartile_range"], "value IQR")
    sensitivity = column["outlier_sensitivity"]
    _eq_float(4.0, sensitivity["iqr_fence_low"], "value fence low")
    _eq_float(28.0, sensitivity["iqr_fence_high"], "value fence high")
    _eq_int(1, sensitivity["outside_iqr_fence_count_in_sample"], "outside fence count")
    _eq_float(15.0, sensitivity["mean_without_iqr_fence_values"], "mean without fence values")
    _eq(sensitivity["values_were_not_deleted_or_modified"], True, "values untouched")
    skew = column["transformation_sensitivity"]["raw_skewness_moment"]
    _eq_float(1.9935025349740592, skew, "raw skewness moment")


def check_json_profile_goldens(tmp: Path) -> None:
    from _common import CliError, load_strict_json
    from _tabular import profile_json_structure

    document = load_strict_json(FIXTURES / "structure_fixture.json", max_bytes=1 << 20)
    profile = profile_json_structure(document, reveal_identifiers=True)
    _eq(profile["root_type"], "object", "json root_type")
    # hand-countable: root + records array + 2 record objects + 2 ids + 2 values
    # + 2 tags arrays + 1 tag string + meta object + n + synthetic = 14 nodes
    _eq_int(14, profile["nodes_visited"], "json nodes_visited")
    _eq(
        profile["type_counts"],
        {"array": 3, "boolean": 1, "number": 3, "object": 4, "string": 3},
        "json type_counts",
    )
    _eq(profile["top_level_field_ids"], ["records", "meta"], "json top-level fields")
    _eq_int(3, profile["array_count"], "json array_count")
    _eq_int(0, profile["array_length_minimum"], "json empty tags array length")
    _eq_int(4, profile["maximum_depth_visited"], "json maximum_depth_visited")
    # strict parsing must reject NaN/Infinity literals
    bad = tmp / "bad.json"
    bad.write_text('{"v": NaN}', encoding="utf-8")
    try:
        load_strict_json(bad, max_bytes=1 << 20)
    except CliError:
        pass
    else:
        raise CheckFailure("NaN literals must be rejected by the strict JSON loader")


def check_safety_contract(tmp: Path) -> None:
    from _common import CliError, checked_input_file, checked_output_file

    root = tmp / "root"
    (root / "nested").mkdir(parents=True)
    inside = root / "nested" / "table.csv"
    inside.write_text("a,b\n1,2\n", encoding="utf-8")
    outside = tmp / "outside.csv"
    outside.write_text("a,b\n1,2\n", encoding="utf-8")

    # path outside the root is rejected
    try:
        checked_input_file("../outside.csv", root=root, max_bytes=1 << 20)
    except CliError:
        pass
    else:
        raise CheckFailure("out-of-root input must be rejected")
    # symlinked input is rejected
    link = root / "nested" / "link.csv"
    os.symlink(outside, link)
    try:
        checked_input_file("nested/link.csv", root=root, max_bytes=1 << 20)
    except CliError:
        pass
    else:
        raise CheckFailure("symlinked input must be rejected")
    # URL-like input is rejected
    try:
        checked_input_file("https://example.org/table.csv", root=root, max_bytes=1 << 20)
    except CliError:
        pass
    else:
        raise CheckFailure("URL inputs must be rejected")
    # byte cap is enforced
    try:
        checked_input_file("nested/table.csv", root=root, max_bytes=4)
    except CliError:
        pass
    else:
        raise CheckFailure("oversized input must be rejected")
    # overwrite protection
    existing = root / "nested" / "out.json"
    existing.write_text("{}", encoding="utf-8")
    try:
        checked_output_file("nested/out.json", root=root, suffixes=(".json",), force=False)
    except CliError:
        pass
    else:
        raise CheckFailure("overwrite without --force must be rejected")
    checked_output_file("nested/out.json", root=root, suffixes=(".json",), force=True)
    # non-rectangular CSV fails closed in the stdlib scanner
    from _tabular import profile_table

    ragged = root / "nested" / "ragged.csv"
    ragged.write_text("a,b\n1,2\n3\n", encoding="utf-8")
    try:
        profile_table(ragged, max_rows=10, missing_tokens=None, reveal_identifiers=False)
    except CliError:
        pass
    else:
        raise CheckFailure("non-rectangular tables must fail closed")


# ----------------------------------------------------------------------
# declared optional layers
# ----------------------------------------------------------------------

def _base_version(raw: str) -> str:
    return raw.split("+", 1)[0]


def check_numpy_layer(tmp: Path, results: list[dict[str, Any]]) -> str:
    try:
        import numpy as np
    except ImportError:
        return "missing"
    from _structured import inspect_numpy
    from _common import CliError

    array = np.arange(12, dtype=np.float64).reshape(3, 4)
    npy = tmp / "array.npy"
    np.save(npy, array, allow_pickle=False)
    report = inspect_numpy(npy, suffix=".npy", reveal_identifiers=False)
    _eq(report["array"]["shape"], [3, 4], "npy shape")
    sample = report["array"]["numeric_sample"]
    _eq_int(12, sample["finite_count"], "npy finite_count")
    _eq_float(5.5, sample["mean"], "npy mean")
    _eq_float(0.0, sample["minimum"], "npy minimum")
    _eq_float(11.0, sample["maximum"], "npy maximum")
    npz = tmp / "bundle.npz"
    np.savez(npz, a=np.array([1.0, 2.0, 3.0]), b=np.array([True, False, True]))
    report = inspect_numpy(npz, suffix=".npz", reveal_identifiers=True)
    arrays = {entry["array_id"]: entry for entry in report["arrays"]}
    if len(arrays) != 2:
        raise CheckFailure(f"npz array count: expected 2, got {len(arrays)}")
    boolean = next(a for a in report["arrays"] if "boolean_sample" in a)
    _eq_int(2, boolean["boolean_sample"]["true_count"], "npz boolean true_count")
    # object arrays must be rejected (pickle never allowed): craft a minimal
    # object-dtype NPY by hand because numpy itself refuses to SAVE one
    # without pickle; the inspector must fail closed when LOADING it.
    object_npy = tmp / "object.npy"
    header_dict = "{'descr': '|O', 'fortran_order': False, 'shape': (1,), }"
    header_len = 64 - (10 + len(header_dict) + 1) % 64
    if header_len == 64:
        header_len = 0
    header = (header_dict + " " * header_len + "\n").encode("ascii")
    object_npy.write_bytes(b"\x93NUMPY" + b"\x01\x00" + len(header).to_bytes(2, "little") + header + b"\x00" * 8)
    try:
        inspect_numpy(object_npy, suffix=".npy", reveal_identifiers=False)
    except CliError:
        pass
    else:
        raise CheckFailure("object-dtype NPY must be rejected")
    pin_ok = _base_version(str(np.__version__)) == DECLARED_OPTIONAL_PINS["numpy"]
    results.append(
        {
            "name": "numpy_layer_versions",
            "status": "pass" if pin_ok else "fail",
            "detail": {
                "installed": str(np.__version__),
                "declared_pin": DECLARED_OPTIONAL_PINS["numpy"],
                "pin_matches_base_version": pin_ok,
            },
        }
    )
    if not pin_ok:
        # a wrong version is never a passing receipt: goldens are bound to the pin
        raise CheckFailure(
            f"numpy {np.__version__} does not match the declared pin "
            f"{DECLARED_OPTIONAL_PINS['numpy']} (Debian local suffixes tolerated)")
    return "pass"


def check_pandas_layer(tmp: Path, results: list[dict[str, Any]]) -> str:
    try:
        import pandas as pd
    except ImportError:
        return "missing"
    import pandas_profile

    report = pandas_profile.pandas_profile(
        FIXTURES / "profile_fixture.csv",
        max_rows=1000,
        missing_tokens=["NA"],
        reveal_identifiers=True,
    )
    cross = report["cross_engine_check"]
    if not cross["consistent"]:
        raise CheckFailure(f"cross-engine deviations: {cross['deviations']}")
    columns = {c["column_id"]: c for c in report["columns"]}
    _eq_int(1, columns["value"]["missing_count"], "pandas value missing_count")
    _eq_int(7, columns["value"]["numeric_parse_count"], "pandas value numeric_parse_count")
    _eq_float(190.0 / 7.0, columns["value"]["numeric_aggregates"]["mean"], "pandas value mean")
    pin_ok = _base_version(str(pd.__version__)) == DECLARED_OPTIONAL_PINS["pandas"]
    results.append(
        {
            "name": "pandas_layer_versions",
            "status": "pass" if pin_ok else "fail",
            "detail": {
                "installed": str(pd.__version__),
                "declared_pin": DECLARED_OPTIONAL_PINS["pandas"],
                "pin_matches_base_version": pin_ok,
            },
        }
    )
    if not pin_ok:
        raise CheckFailure(
            f"pandas {pd.__version__} does not match the declared pin "
            f"{DECLARED_OPTIONAL_PINS['pandas']} (Debian local suffixes tolerated)")
    return "pass"


# ----------------------------------------------------------------------
# end-to-end CLI proof (real subprocesses, temp workspace only)
# ----------------------------------------------------------------------

def _run_cli(args: list[str], tmp: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=PACKAGE_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


def check_cli_end_to_end(tmp: Path) -> None:
    workspace = tmp / "cli"
    workspace.mkdir()
    for name in ("profile_fixture.csv", "leak_fixture.csv", "structure_fixture.json"):
        (workspace / name).write_bytes((FIXTURES / name).read_bytes())
    root = str(workspace)

    cases: list[tuple[list[str], str | None, list[str]]] = [
        (
            ["scripts/capability_manifest.py", "list", "--output", "capabilities.json", "--root", root],
            "capabilities.json",
            ["automated_core"],
        ),
        (
            ["scripts/tabular_profile.py", "profile_fixture.csv", "--root", root,
             "--missing-token", "NA", "--reveal-identifiers", "--output", "profile.json"],
            "profile.json",
            ["numeric_aggregates"],
        ),
        (
            ["scripts/missingness_leakage_audit.py", "leak_fixture.csv", "--root", root,
             "--group-column", "group", "--entity-column", "subject_id",
             "--split-column", "split", "--time-column", "obs_time",
             "--reveal-identifiers", "--output", "leak.json"],
            "leak.json",
            ["potential_leakage_detected"],
        ),
        (
            ["scripts/distribution_sensitivity.py", "profile_fixture.csv", "--root", root,
             "--column", "value", "--missing-token", "NA", "--reveal-identifiers",
             "--output", "dist.json"],
            "dist.json",
            ["iqr_fence_high"],
        ),
        (
            ["scripts/eda_analyzer.py", "structure_fixture.json", "--root", root,
             "--reveal-identifiers", "--output", "eda.json"],
            "eda.json",
            ["json_structural_profile"],
        ),
        (
            ["scripts/report_scaffold.py", "--input", "profile_fixture.csv", "--root", root,
             "--analysis-date", "2026-10-26", "--output", "scaffold.md"],
            "scaffold.md",
            ["Exploratory"],
        ),
    ]
    for args, output_name, markers in cases:
        completed = _run_cli(args, tmp)
        if completed.returncode != 0:
            raise CheckFailure(
                f"CLI {args[0]} exited {completed.returncode}: "
                f"{completed.stderr.strip()[:400]}"
            )
        output = workspace / output_name
        if not output.is_file():
            raise CheckFailure(f"CLI {args[0]} did not write {output_name}")
        body = output.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in body:
                raise CheckFailure(f"CLI {args[0]} output lacks {marker!r}")
        if output_name.endswith(".json"):
            json.loads(body)  # strict round-trip


# ----------------------------------------------------------------------
# runner
# ----------------------------------------------------------------------

MANDATORY_CHECKS = [
    ("runtime", check_runtime),
    ("capability_registry", check_capability_registry),
    ("stdlib_profile_goldens", check_stdlib_profile_goldens),
    ("missingness_leakage_goldens", check_missingness_leakage_goldens),
    ("distribution_goldens", check_distribution_goldens),
    ("json_profile_goldens", check_json_profile_goldens),
    ("safety_contract", check_safety_contract),
    ("cli_end_to_end", check_cli_end_to_end),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--require-optional",
        action="store_true",
        help="Fail when the declared optional numpy/pandas layers are absent "
             "(use after provisioning the reviewed dependency layer)",
    )
    parser.add_argument("--output", help="Optional JSON report path")
    args = parser.parse_args()

    results: list[dict[str, Any]] = []
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="eda-verify-") as raw_tmp:
        tmp = Path(raw_tmp)
        for name, check in MANDATORY_CHECKS:
            try:
                check(tmp)
                results.append({"name": name, "status": "pass"})
            except CheckFailure as exc:
                results.append({"name": name, "status": "fail", "error": str(exc)})
                failures.append(f"{name}: {exc}")
            except Exception as exc:  # keep the full picture, fail closed
                results.append(
                    {"name": name, "status": "fail", "error": f"{type(exc).__name__}: {exc}"}
                )
                failures.append(f"{name}: {type(exc).__name__}: {exc}")
        for name, checker in (("numpy_layer", check_numpy_layer), ("pandas_layer", check_pandas_layer)):
            try:
                status = checker(tmp, results)
                results.append({"name": name, "status": status})
                if status == "missing" and args.require_optional:
                    failures.append(f"{name}: declared optional layer is not provisioned")
            except CheckFailure as exc:
                results.append({"name": name, "status": "fail", "error": str(exc)})
                failures.append(f"{name}: {exc}")
            except Exception as exc:
                results.append(
                    {"name": name, "status": "fail", "error": f"{type(exc).__name__}: {exc}"}
                )
                failures.append(f"{name}: {type(exc).__name__}: {exc}")

    report = {
        "verifier": "eda_verify.py",
        "package": "exploratory-data-analysis 1.0.0 (Floe adaptation)",
        "python": sys.version.split()[0],
        "ok": not failures,
        "optional_layers_required": bool(args.require_optional),
        "declared_optional_pins": DECLARED_OPTIONAL_PINS,
        "checks": results,
        "failures": failures,
        "evidence_class": "runs wherever it is executed; guest execution evidence "
                          "requires a real run in the resolved Linux environment",
    }
    payload = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
