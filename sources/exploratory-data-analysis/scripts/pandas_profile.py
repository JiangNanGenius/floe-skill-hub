#!/usr/bin/env python3
"""Optional pandas tabular profile with a mandatory stdlib cross-check.

First-party Floe script (MIT (c) Floe project); NOT upstream K-Dense
content. It complements the bundled stdlib core CLIs: the same bounded
CSV/TSV input is profiled through pandas AND through the stdlib
`_tabular.profile_table`, and the two engines' aggregates must agree
within a fixed tolerance or this CLI fails closed. A missing pandas layer
is an honest provisioning error, never a silent downgrade.

Safety contract matches the bundled core CLIs: bounded rows/bytes inside
--root, symlink/traversal rejection, strict JSON output, atomic writes,
no network, raw values are never emitted.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

from _common import (
    DEFAULT_MAX_FILE_BYTES,
    DEFAULT_MAX_ROWS,
    CliError,
    bounded_file_limit,
    bounded_integer,
    checked_input_file,
    display_identifier,
    emit_json,
    run_cli,
)
from _tabular import delimiter_for_path, normalize_missing_tokens, profile_table


CROSS_ENGINE_TOLERANCE = 1e-9
COMPARE_KEYS = (
    "mean",
    "median",
    "minimum",
    "maximum",
    "q1",
    "q3",
    "sample_standard_deviation",
)


def _load_pandas() -> Any:
    try:
        import numpy as np
        import pandas as pd
    except ImportError as exc:
        raise CliError(
            "the optional pandas layer is not provisioned; pandas==2.2.3 and "
            "numpy==2.2.4 come from the Floe environment/package flow "
            "(Debian guest: python3-pandas / python3-numpy); the stdlib core "
            "CLIs (tabular_profile.py / eda_analyzer.py) work without it"
        ) from exc
    return pd, np


def _numeric_aggregates(series: Any, np: Any) -> dict[str, Any] | None:
    """Finite-only aggregates using the same conventions as the stdlib core."""
    values = series.to_numpy(dtype="float64", na_value=np.nan)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return None
    quantiles = np.quantile(finite, (0.25, 0.5, 0.75), method="linear")
    return {
        "count": int(finite.size),
        "mean": float(np.mean(finite)),
        "median": float(quantiles[1]),
        "minimum": float(np.min(finite)),
        "maximum": float(np.max(finite)),
        "q1": float(quantiles[0]),
        "q3": float(quantiles[2]),
        "sample_standard_deviation": float(np.std(finite, ddof=1))
        if finite.size > 1
        else None,
    }


def _close(reference: float | None, candidate: float | None) -> bool:
    if reference is None or candidate is None:
        return reference is candidate
    if not (math.isfinite(reference) and math.isfinite(candidate)):
        return False
    scale = max(1.0, abs(reference), abs(candidate))
    return abs(reference - candidate) <= CROSS_ENGINE_TOLERANCE * scale


def pandas_profile(
    path: Path,
    *,
    max_rows: int = DEFAULT_MAX_ROWS,
    max_bytes: int = DEFAULT_MAX_FILE_BYTES,
    missing_tokens: list[str] | None = None,
    reveal_identifiers: bool = False,
) -> dict[str, Any]:
    """Profile one bounded CSV/TSV with pandas and cross-check the stdlib."""
    pd, np = _load_pandas()
    max_rows = bounded_integer(
        max_rows, name="max rows", minimum=1, maximum=DEFAULT_MAX_ROWS * 10
    )
    delimiter = delimiter_for_path(path)
    tokens = normalize_missing_tokens(missing_tokens)

    frame = pd.read_csv(
        path,
        sep=delimiter,
        encoding="utf-8-sig",
        dtype=str,
        keep_default_na=False,
        nrows=max_rows + 1,
        engine="python",
        on_bad_lines="error",
    )
    row_limit_reached = len(frame) > max_rows
    if row_limit_reached:
        frame = frame.iloc[:max_rows]
    if frame.empty:
        raise CliError("the table has no data rows")

    # Stdlib reference profile over the identical bounded input.
    stdlib = profile_table(
        path,
        max_rows=max_rows,
        missing_tokens=list(tokens - {""}) or None,
        reveal_identifiers=reveal_identifiers,
    )
    stdlib_columns = {c["column_id"]: c for c in stdlib["columns"]}

    columns: list[dict[str, Any]] = []
    deviations: list[dict[str, Any]] = []
    for index, column in enumerate(frame.columns):
        raw = frame[column]
        normalized = raw.str.strip().str.casefold()
        missing_mask = normalized.isin(tokens)
        missing_count = int(missing_mask.sum())
        present = raw[~missing_mask]
        numeric = pd.to_numeric(present, errors="coerce")
        numeric_mask = numeric.notna() & np.isfinite(
            numeric.to_numpy(dtype="float64", na_value=np.nan)
        )
        numeric_count = int(numeric_mask.sum())
        aggregates = (
            _numeric_aggregates(numeric[numeric_mask], np)
            if numeric_count
            else None
        )
        column_id = display_identifier(
            str(column), kind="column", reveal_identifiers=reveal_identifiers
        )
        entry: dict[str, Any] = {
            "column_index": index,
            "column_id": column_id,
            "pandas_dtype": "object(raw-string ingest)",
            "missing_count": missing_count,
            "non_missing_count": int(len(raw) - missing_count),
            "numeric_parse_count": numeric_count,
            "numeric_aggregates": aggregates,
        }
        columns.append(entry)

        reference = stdlib_columns.get(column_id)
        if reference is None:
            deviations.append(
                {"column_id": column_id, "problem": "absent from the stdlib profile"}
            )
            continue
        if reference["missing_count"] != missing_count:
            deviations.append(
                {
                    "column_id": column_id,
                    "problem": "missing_count",
                    "stdlib": reference["missing_count"],
                    "pandas": missing_count,
                }
            )
        if reference["numeric_parse_count"] != numeric_count:
            deviations.append(
                {
                    "column_id": column_id,
                    "problem": "numeric_parse_count",
                    "stdlib": reference["numeric_parse_count"],
                    "pandas": numeric_count,
                }
            )
        stdlib_aggregates = reference.get("numeric_aggregates") or {}
        for key in COMPARE_KEYS:
            if not _close(
                stdlib_aggregates.get(key),
                (aggregates or {}).get(key),
            ):
                deviations.append(
                    {
                        "column_id": column_id,
                        "problem": f"numeric_aggregates.{key}",
                        "stdlib": stdlib_aggregates.get(key),
                        "pandas": (aggregates or {}).get(key),
                    }
                )

    duplicate_count = int(frame.duplicated().sum())
    stdlib_duplicates = stdlib.get("duplicate_row_count_in_scanned_rows")
    if stdlib_duplicates is not None and stdlib_duplicates != duplicate_count:
        deviations.append(
            {
                "column_id": "<rows>",
                "problem": "duplicate_row_count",
                "stdlib": stdlib_duplicates,
                "pandas": duplicate_count,
            }
        )

    return {
        "schema_version": "1.0",
        "profile_type": "pandas_tabular_profile_with_stdlib_cross_check",
        "engine": {
            "name": "pandas",
            "version": str(pd.__version__),
            "numpy_version": str(np.__version__),
            "declared_pins": {"pandas": "2.2.3", "numpy": "2.2.4"},
        },
        "rows_scanned": int(len(frame)),
        "row_limit_reached": bool(row_limit_reached),
        "column_count": int(len(frame.columns)),
        "duplicate_row_count_in_scanned_rows": duplicate_count,
        "missing_code_policy": {
            "empty_or_whitespace_is_missing": True,
            "additional_token_count": max(len(tokens) - 1, 0),
            "tokens_are_not_emitted": True,
        },
        "identifier_redaction": "revealed sanitized" if reveal_identifiers else "tokenized",
        "columns": columns,
        "cross_engine_check": {
            "performed": True,
            "reference_profile_type": stdlib.get("profile_type"),
            "tolerance": CROSS_ENGINE_TOLERANCE,
            "consistent": not deviations,
            "deviations": deviations,
        },
        "raw_values_emitted": False,
        "limitations": [
            "pandas ingests every cell as a raw string first so missing-code and finite-number semantics match the stdlib core exactly; dtype-directed parsing is a separate analysis step.",
            "A bounded prefix scan is not a random sample; row_limit_reached must be reported downstream.",
            "This profile does not modify, impute, or delete anything.",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Bounded pandas CSV/TSV profile cross-checked against the bundled "
            "stdlib profiler; fails closed on any engine disagreement."
        )
    )
    parser.add_argument("input", help="Local .csv/.tsv file inside --root")
    parser.add_argument(
        "--root",
        default=".",
        help="Existing local directory that bounds all input/output paths",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_FILE_BYTES,
        help="Maximum input bytes",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=DEFAULT_MAX_ROWS,
        help="Maximum rows to scan",
    )
    parser.add_argument(
        "--missing-token",
        action="append",
        help="Explicit additional missing code; repeat as needed",
    )
    parser.add_argument(
        "--reveal-identifiers",
        action="store_true",
        help="Reveal sanitized column identifiers instead of tokens",
    )
    parser.add_argument("--output", help="Optional local .json output path")
    parser.add_argument("--force", action="store_true")
    return parser


def _main() -> None:
    args = build_parser().parse_args()
    max_bytes = bounded_file_limit(args.max_bytes)
    path = checked_input_file(
        args.input,
        root=args.root,
        max_bytes=max_bytes,
        suffixes=(".csv", ".tsv"),
    )
    report = pandas_profile(
        path,
        max_rows=args.max_rows,
        max_bytes=max_bytes,
        missing_tokens=args.missing_token,
        reveal_identifiers=args.reveal_identifiers,
    )
    if not report["cross_engine_check"]["consistent"]:
        raise CliError(
            "pandas and stdlib engines disagree; refusing to publish an "
            "inconsistent profile"
        )
    emit_json(report, output=args.output, root=args.root, force=args.force)


def main() -> int:
    return run_cli(_main)


if __name__ == "__main__":
    raise SystemExit(main())
