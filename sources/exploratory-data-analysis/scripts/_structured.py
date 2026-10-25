#!/usr/bin/env python3
"""Bounded inspectors for JSON and NumPy containers.

Floe adaptation: the upstream HDF5 metadata inspector was removed because
its HDF5 binding is outside this release's declared dependency layer; HDF5
stays a reference-only format in _capabilities.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from _capabilities import preflight_npz
from _common import (
    MAX_JSON_BYTES,
    CliError,
    display_identifier,
    load_strict_json,
)
from _tabular import profile_json_structure


MAX_ARRAY_SAMPLE = 4096


def inspect_json(
    path: Path,
    *,
    reveal_identifiers: bool = False,
) -> dict[str, Any]:
    """Strictly parse bounded JSON and emit structure, never scalar values."""

    document = load_strict_json(path, max_bytes=MAX_JSON_BYTES)
    return profile_json_structure(
        document,
        reveal_identifiers=reveal_identifiers,
    )


def _dtype_report(
    dtype: Any,
    *,
    reveal_identifiers: bool,
) -> dict[str, Any]:
    fields = getattr(dtype, "fields", None)
    report: dict[str, Any] = {
        "kind": str(dtype.kind),
        "itemsize": int(dtype.itemsize),
        "byteorder": str(dtype.byteorder),
        "contains_python_objects": bool(dtype.hasobject),
        "structured": fields is not None,
    }
    if fields is not None:
        names = list(dtype.names or ())
        report["field_count"] = len(names)
        report["field_ids"] = [
            display_identifier(
                name,
                kind="field",
                reveal_identifiers=reveal_identifiers,
            )
            for name in names[:128]
        ]
        report["field_ids_truncated"] = len(names) > 128
    else:
        report["dtype"] = str(dtype)
    return report


def _sample_array(array: Any, np: Any) -> Any:
    size = int(array.size)
    if size <= MAX_ARRAY_SAMPLE:
        return np.asarray(array).reshape(-1)
    positions = np.linspace(
        0,
        size - 1,
        num=MAX_ARRAY_SAMPLE,
        dtype=np.int64,
    )
    # ndarray.flat indexes in C order without materializing a full C-order
    # copy of a Fortran-contiguous memory map.
    return np.asarray(array.flat[positions])


def _array_report(
    array: Any,
    np: Any,
    *,
    array_id: str | None,
    reveal_identifiers: bool,
) -> dict[str, Any]:
    if bool(array.dtype.hasobject):
        raise CliError("NumPy object arrays are not accepted because they require pickle")
    report: dict[str, Any] = {
        "shape": [int(value) for value in array.shape],
        "dimension_count": int(array.ndim),
        "element_count": int(array.size),
        "dtype": _dtype_report(
            array.dtype,
            reveal_identifiers=reveal_identifiers,
        ),
    }
    if array_id is not None:
        report["array_id"] = array_id
    if int(array.size) == 0:
        report["numeric_sample"] = {"sample_count": 0}
        return report
    if np.issubdtype(array.dtype, np.bool_):
        sample = _sample_array(array, np)
        report["boolean_sample"] = {
            "sample_count": int(sample.size),
            "true_count": int(np.count_nonzero(sample)),
            "sample_is_bounded": int(sample.size) < int(array.size),
        }
        return report
    if np.issubdtype(array.dtype, np.number):
        sample = _sample_array(array, np)
        if np.iscomplexobj(sample):
            finite = np.isfinite(sample.real) & np.isfinite(sample.imag)
            magnitudes = np.abs(sample[finite])
            report["numeric_sample"] = {
                "sample_count": int(sample.size),
                "finite_count": int(np.count_nonzero(finite)),
                "complex_values_summarized_by_magnitude": True,
                "magnitude_mean": (
                    float(np.mean(magnitudes)) if magnitudes.size else None
                ),
                "magnitude_minimum": (
                    float(np.min(magnitudes)) if magnitudes.size else None
                ),
                "magnitude_maximum": (
                    float(np.max(magnitudes)) if magnitudes.size else None
                ),
                "sample_is_bounded": int(sample.size) < int(array.size),
            }
        else:
            finite = np.isfinite(sample)
            finite_values = sample[finite]
            report["numeric_sample"] = {
                "sample_count": int(sample.size),
                "finite_count": int(np.count_nonzero(finite)),
                "nan_count": int(np.count_nonzero(np.isnan(sample)))
                if np.issubdtype(sample.dtype, np.inexact)
                else 0,
                "infinite_count": int(np.count_nonzero(np.isinf(sample)))
                if np.issubdtype(sample.dtype, np.inexact)
                else 0,
                "mean": (
                    float(np.mean(finite_values)) if finite_values.size else None
                ),
                "minimum": (
                    float(np.min(finite_values)) if finite_values.size else None
                ),
                "maximum": (
                    float(np.max(finite_values)) if finite_values.size else None
                ),
                "sample_is_bounded": int(sample.size) < int(array.size),
            }
    return report


def inspect_numpy(
    path: Path,
    *,
    suffix: str,
    reveal_identifiers: bool = False,
) -> dict[str, Any]:
    """Inspect NPY/NPZ with pickle disabled and bounded decompression."""

    try:
        import numpy as np
    except ImportError as exc:
        raise CliError(
            "optional dependency missing; numpy==2.2.4 is provisioned through "
            "the Floe environment/package flow, never ad-hoc at chat time"
        ) from exc
    if suffix == ".npy":
        try:
            array = np.load(
                path,
                mmap_mode="r",
                allow_pickle=False,
                max_header_size=10_000,
            )
        except (OSError, ValueError, TypeError, MemoryError) as exc:
            raise CliError(
                "the NPY file could not be inspected safely; object arrays are rejected"
            ) from exc
        return {
            "profile_type": "numpy_npy_bounded_profile",
            "pickle_allowed": False,
            "array": _array_report(
                array,
                np,
                array_id=None,
                reveal_identifiers=reveal_identifiers,
            ),
            "raw_values_emitted": False,
        }
    if suffix != ".npz":
        raise CliError("the NumPy inspector received an unsupported suffix")
    preflight = preflight_npz(path)
    arrays: list[dict[str, Any]] = []
    try:
        with np.load(
            path,
            allow_pickle=False,
            max_header_size=10_000,
        ) as archive:
            for name in archive.files:
                array = archive[name]
                arrays.append(
                    _array_report(
                        array,
                        np,
                        array_id=display_identifier(
                            name,
                            kind="array",
                            reveal_identifiers=reveal_identifiers,
                        ),
                        reveal_identifiers=reveal_identifiers,
                    )
                )
                del array
    except (OSError, ValueError, TypeError, MemoryError) as exc:
        raise CliError(
            "the NPZ arrays could not be inspected safely; object arrays are rejected"
        ) from exc
    return {
        "profile_type": "numpy_npz_bounded_profile",
        "pickle_allowed": False,
        "archive_preflight": preflight,
        "arrays": arrays,
        "raw_values_emitted": False,
    }
