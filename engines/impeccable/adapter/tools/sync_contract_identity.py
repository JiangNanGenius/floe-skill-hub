#!/usr/bin/env python3
"""Derive the contract's engine-identity strings from the one component
version constant the binary actually embeds.

The live probe prints `impeccable-engine <upstreamEngineVersion>+floe.<version>`
where `<version>` is the adapter crate's Cargo.toml version (the crate embeds
`CARGO_PKG_VERSION`; no separate env override is set by the pinned recipe).
The frozen contract carries three static copies of that identity:

  * `engine.floeAdapterVersion`
  * `engine.engineId`
  * the `engine-probe` verb's documented `stdout` example

Root's 2026-10-27 review found the probe example stale (it said 1.0.0 while
the 1.1.0 binary printed 1.1.0). This tool ends the hand-copying: it computes
the three fields from (Cargo.toml version, engine.upstreamEngineVersion) and
either checks or rewrites the contract file in place, touching only those
lines so the tracked formatting and every other byte stay stable.

Usage:
  sync_contract_identity.py                       # check (exit 3 on drift)
  sync_contract_identity.py --apply              # rewrite the three lines
  sync_contract_identity.py --contract PATH --crate-dir PATH

Deterministic, stdlib-only, no network. Run it as part of the release bump
before the build; the build recipe also refuses to compile while it reports
drift, so an embedded contract can never disagree with the live probe.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ADAPTER_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"\s*$', re.MULTILINE)
ADAPTER_IDENTITY_FIELDS = ("floeAdapterVersion", "engineId")


def crate_version(crate_dir: Path) -> str:
    cargo_toml = crate_dir / "Cargo.toml"
    if not cargo_toml.is_file():
        raise SystemExit(f"missing adapter crate manifest: {cargo_toml}")
    match = ADAPTER_VERSION_RE.search(cargo_toml.read_text(encoding="utf-8"))
    if not match:
        raise SystemExit(f"no package version found in {cargo_toml}")
    return match.group(1)


def expected_identity(contract: dict, adapter_version: str) -> dict[str, str]:
    engine = contract["engine"]["upstreamEngineVersion"]
    component = f"{engine}+floe.{adapter_version}"
    return {
        "floeAdapterVersion": adapter_version,
        "engineId": f"impeccable-{component}",
        "engineProbeStdout": f"impeccable-engine {component}\\n",
    }


def apply(text: str, expected: dict[str, str]) -> tuple[str, list[str]]:
    changes: list[str] = []

    def sub_once(pattern: str, repl: str, label: str) -> str:
        nonlocal text
        hits = re.findall(pattern, text, re.MULTILINE)
        if len(hits) != 1:
            raise SystemExit(
                f"cannot safely {label}: expected exactly one matching line, found {len(hits)}"
            )
        new_text, n = re.subn(pattern, repl, text, count=1, flags=re.MULTILINE)
        if n != 1:
            raise SystemExit(f"cannot safely {label}: substitution failed")
        if new_text != text:
            changes.append(label)
        text = new_text
        return text

    sub_once(
        r'^(\s*)"floeAdapterVersion": "[^"]*",(\s*)$',
        rf'\1"floeAdapterVersion": "{expected["floeAdapterVersion"]}",\2',
        "engine.floeAdapterVersion",
    )
    sub_once(
        r'^(\s*)"engineId": "impeccable-[^"]*",(\s*)$',
        rf'\1"engineId": "{expected["engineId"]}",\2',
        "engine.engineId",
    )
    sub_once(
        r'^(\s*)"stdout": "impeccable-engine [^"]*",(\s*)$',
        rf'\1"stdout": "{expected["engineProbeStdout"]}",\2',
        "verbs[engine-probe].stdout",
    )
    return text, changes


def main() -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--contract", type=Path,
                    default=here.parent.parent / "candidate-contract" / "snapshot-contract.v1.json")
    ap.add_argument("--crate-dir", type=Path, default=here.parent)
    ap.add_argument("--apply", action="store_true", help="rewrite the contract identity lines")
    args = ap.parse_args()

    adapter = crate_version(args.crate_dir)
    raw = args.contract.read_text(encoding="utf-8")
    contract = json.loads(raw)
    expected = expected_identity(contract, adapter)

    actual_probe = next(
        (v.get("stdout") for v in contract.get("verbs", []) if v.get("name") == "engine-probe"),
        None,
    )
    drift = {
        "floeAdapterVersion": contract["engine"].get("floeAdapterVersion") != expected["floeAdapterVersion"],
        "engineId": contract["engine"].get("engineId") != expected["engineId"],
        "engineProbeStdout": actual_probe != expected["engineProbeStdout"].replace("\\n", "\n"),
    }
    stale = [k for k, v in drift.items() if v]

    if not args.apply:
        if stale:
            print(json.dumps({"ok": False, "adapterVersion": adapter,
                              "staleFields": stale,
                              "expected": expected,
                              "hint": "run with --apply, then re-hash the contract"},
                             indent=2))
            return 3
        print(json.dumps({"ok": True, "adapterVersion": adapter,
                          "engineId": expected["engineId"]}, indent=2))
        return 0

    if not stale:
        print(json.dumps({"ok": True, "applied": [], "adapterVersion": adapter}, indent=2))
        return 0

    new_text, changes = apply(raw, expected)
    json.loads(new_text)  # the rewrite must still be valid JSON
    args.contract.write_text(new_text, encoding="utf-8")
    print(json.dumps({"ok": True, "applied": changes, "adapterVersion": adapter}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
