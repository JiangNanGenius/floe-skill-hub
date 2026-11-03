#!/usr/bin/env python3
"""Bounded local JSON input helpers for the pricing-strategist tools.

Floe-added support module (MIT, (c) Floe project). The upstream MIT-licensed
calculations live in the three sibling scripts; this module only makes their
file input explicit, bounded and fail-closed:

- one regular UTF-8 JSON file inside an explicit workspace root;
- symlinks, multiply linked files, directories, URLs, traversal and oversized
  files are refused before any content is parsed;
- duplicate JSON keys, non-finite numbers and out-of-range values are refused;
- reports are written to stdout only; this module never opens an output file,
  starts a process, or makes a network call.
"""

from __future__ import annotations

import json
import math
import os
import stat
import sys
from pathlib import Path, PurePath
from typing import Any, Iterable

MIB = 1024 * 1024
DEFAULT_MAX_INPUT_BYTES = 2 * MIB
MAX_INPUT_BYTES = 8 * MIB
MAX_TEXT_CHARS = 2_000


class PricingError(ValueError):
    """An expected input or contract error with a safe, non-sensitive message."""


def _absolute_lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _reject_path_form(raw: str) -> None:
    stripped = raw.strip()
    lowered = stripped.lower()
    if not stripped:
        raise PricingError("the input path must not be empty")
    if "\x00" in raw:
        raise PricingError("the input path must not contain a NUL byte")
    if "://" in lowered or lowered.startswith(
        ("http:", "https:", "ftp:", "s3:", "gs:", "file:", "data:")
    ):
        raise PricingError("URLs are not accepted; provide a local JSON file")
    if stripped.startswith("~"):
        raise PricingError("home-directory expansion is not accepted")
    if ".." in PurePath(stripped).parts:
        raise PricingError("parent-directory traversal is not accepted")


def _reject_symlink_components(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            if current.is_symlink():
                raise PricingError("symlink path components are not accepted")
        except OSError:
            raise PricingError("a path component could not be inspected") from None


def checked_root(value: str | os.PathLike[str]) -> Path:
    """Return an existing, non-symlink directory used as the I/O boundary."""

    raw = os.fspath(value)
    _reject_path_form(raw)
    supplied = _absolute_lexical(Path(raw))
    if supplied.is_symlink():
        raise PricingError("the root directory must not be a symlink")
    try:
        root = supplied.resolve(strict=True)
        info = root.stat()
    except OSError:
        raise PricingError("the root directory is not accessible") from None
    if not stat.S_ISDIR(info.st_mode):
        raise PricingError("the root must be an existing directory")
    _reject_symlink_components(root)
    return root


def _within_root(path: Path, root: Path) -> None:
    try:
        path.relative_to(root)
    except ValueError:
        raise PricingError("the input must stay inside the workspace root") from None


def checked_input_file(
    value: str | os.PathLike[str],
    *,
    root: str | os.PathLike[str] = ".",
    suffixes: Iterable[str] = (".json",),
    max_bytes: int = DEFAULT_MAX_INPUT_BYTES,
) -> Path:
    """Return a bounded regular JSON file inside root, rejecting escapes."""

    if not 1 <= max_bytes <= MAX_INPUT_BYTES:
        raise PricingError("the configured input byte limit is invalid")
    raw = os.fspath(value)
    _reject_path_form(raw)
    root_path = checked_root(root)
    path = Path(raw)
    if not path.is_absolute():
        path = root_path / path
    path = _absolute_lexical(path)
    if path.is_symlink():
        raise PricingError("the input must not be a symlink")
    try:
        resolved = path.resolve(strict=True)
        info = resolved.stat()
    except OSError:
        raise PricingError("the input file is not accessible") from None
    _within_root(resolved, root_path)
    _reject_symlink_components(resolved)
    if not stat.S_ISREG(info.st_mode):
        raise PricingError("the input must be a regular file")
    if info.st_nlink != 1:
        raise PricingError("multiply linked input files are not accepted")
    if info.st_size > max_bytes:
        raise PricingError(
            f"the input is {info.st_size} bytes; the configured limit is {max_bytes}"
        )
    allowed = tuple(suffix.casefold() for suffix in suffixes)
    if allowed and resolved.suffix.casefold() not in allowed:
        raise PricingError("the input suffix must be: " + ", ".join(allowed))
    return resolved


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise PricingError("duplicate JSON object key is not accepted")
        value[key] = item
    return value


def _reject_constant(_literal: str) -> None:
    raise PricingError("non-finite JSON numbers are not accepted")


def _finite_float(literal: str) -> float:
    number = float(literal)
    if not math.isfinite(number):
        raise PricingError("JSON number exceeds the finite floating-point range")
    return number


def _finite_int(literal: str) -> int:
    try:
        number = int(literal)
    except ValueError:
        raise PricingError("JSON integer is outside the supported range") from None
    if abs(number) > 10**15:
        raise PricingError("JSON integer is outside the supported range")
    return number


def load_json(path: Path, *, max_bytes: int = DEFAULT_MAX_INPUT_BYTES) -> Any:
    """Read one bounded UTF-8 JSON document with strict number handling."""

    try:
        size = path.stat().st_size
    except OSError:
        raise PricingError("the input file is not accessible") from None
    if size > max_bytes:
        raise PricingError(
            f"the input is {size} bytes; the configured limit is {max_bytes}"
        )
    try:
        raw = path.read_bytes()
    except OSError:
        raise PricingError("the input file could not be read") from None
    if len(raw) > max_bytes:
        raise PricingError(
            f"the input is {len(raw)} bytes; the configured limit is {max_bytes}"
        )
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError:
        raise PricingError("the input must be UTF-8 encoded JSON") from None
    try:
        return json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
            parse_float=_finite_float,
            parse_int=_finite_int,
        )
    except json.JSONDecodeError as exc:
        raise PricingError(
            f"invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from None
    except RecursionError:
        raise PricingError("the JSON nesting depth is too large") from None


def require_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PricingError(f"{name} must be a JSON object")
    return value


def require_list(value: Any, name: str, *, max_items: int) -> list[Any]:
    if not isinstance(value, list):
        raise PricingError(f"{name} must be a JSON array")
    if len(value) > max_items:
        raise PricingError(f"{name} has {len(value)} items; the limit is {max_items}")
    return value


def _has_control(value: str) -> bool:
    return any(ord(character) < 32 or 0x7F <= ord(character) <= 0x9F for character in value)


def require_text(value: Any, name: str, *, max_chars: int = MAX_TEXT_CHARS) -> str:
    if not isinstance(value, str):
        raise PricingError(f"{name} must be a string")
    if not value.strip():
        raise PricingError(f"{name} must not be empty")
    if len(value) > max_chars:
        raise PricingError(f"{name} exceeds {max_chars} characters")
    if _has_control(value):
        raise PricingError(f"{name} must not contain control characters")
    return value


def require_number(
    value: Any,
    name: str,
    *,
    minimum: float,
    maximum: float,
) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PricingError(f"{name} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise PricingError(f"{name} must be finite")
    if not minimum <= number <= maximum:
        raise PricingError(f"{name} must be between {minimum:g} and {maximum:g}")
    return value


def require_integer(
    value: Any,
    name: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool):
        raise PricingError(f"{name} must be an integer")
    if isinstance(value, int):
        number = value
    elif isinstance(value, float) and math.isfinite(value) and value.is_integer():
        number = int(value)
    else:
        raise PricingError(f"{name} must be an integer")
    if not minimum <= number <= maximum:
        raise PricingError(f"{name} must be between {minimum} and {maximum}")
    return number


def sanitize_inline(value: str, *, max_chars: int = 200) -> str:
    """Neutralize control characters and bound one untrusted display scalar."""

    cleaned = "".join(
        character
        if character.isprintable() and character not in "\r\n\t"
        else " "
        for character in value
    )
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars] + "…"
    return cleaned


def escape_markdown(value: str) -> str:
    """Escape Markdown structure while keeping ordinary product names readable."""

    escaped: list[str] = []
    for character in value:
        if character in "\\`*_{}[]<>#|~":
            escaped.append("\\")
        escaped.append(character)
    return "".join(escaped)


def emit(text: str) -> None:
    """Print one report to stdout; never create or overwrite a file."""

    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")


def run_cli(function: Any) -> int:
    """Run a CLI body with concise expected-error handling."""

    try:
        function()
    except PricingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("error: interrupted", file=sys.stderr)
        return 130
    except BrokenPipeError:
        return 0
    return 0
