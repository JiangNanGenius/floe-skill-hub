#!/usr/bin/env python3
"""Export engine-observed goldens from a verification stage.

The verification matrix (`verify_engine_run.py`) leaves one result document per
case in `<stage>/out/`. This turns them into the labeled golden set the hub
tracks, with the volatile fields normalized so a golden is comparable across
runs, hosts and architectures:

  * `budget.elapsedMs` -> 0 (wall clock is a measurement, not an expectation);
  * `diagnostics.factsFiles[].source` -> the basename (an absolute path would
    record the runner's filesystem layout).

Everything else is exactly what the engine printed, including the coverage
receipt, the error codes and the finding counts.

  export_expected.py --stage <verify-stage> --label <label> --out <expected/label> \
      [--runner "docker linux/riscv64 alpine:3.20"] [--binary <path>]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

VOLATILE_NOTE = ("budget.elapsedMs and error.detail.elapsedMs normalized to 0; "
                 "facts file sources reduced to basenames")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize(doc: dict) -> dict:
    if isinstance(doc.get("budget"), dict):
        doc["budget"]["elapsedMs"] = 0
    error = doc.get("error")
    if isinstance(error, dict) and isinstance(error.get("detail"), dict):
        # a timeout refusal reports the wall clock it observed; that is a
        # measurement, not an expectation
        if "elapsedMs" in error["detail"]:
            error["detail"]["elapsedMs"] = 0
    diagnostics = doc.get("diagnostics")
    if isinstance(diagnostics, dict):
        for entry in diagnostics.get("factsFiles") or []:
            if isinstance(entry, dict) and isinstance(entry.get("source"), str):
                entry["source"] = Path(entry["source"]).name
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, type=Path)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--runner", default=None)
    ap.add_argument("--binary", type=Path, default=None)
    ap.add_argument("--evidence", type=Path, default=None,
                    help="the verify_engine_run.py report to copy runner facts from")
    args = ap.parse_args()
    for name in ("stage", "out", "binary", "evidence"):
        value = getattr(args, name)
        if value is not None:
            setattr(args, name, Path(value).expanduser().resolve())

    out_dir = args.stage / "out"
    if not out_dir.is_dir():
        print(json.dumps({"ok": False, "error": "no out/ directory in the stage", "stage": str(args.stage)}))
        return 2
    if args.out.exists():
        import shutil
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True)

    uname = (out_dir / "uname.txt").read_text(encoding="utf-8").split() if (out_dir / "uname.txt").is_file() else []
    binary_sha = None
    if (out_dir / "binary.sha256").is_file():
        binary_sha = (out_dir / "binary.sha256").read_text(encoding="utf-8").split()[0]
    if binary_sha is None and args.binary and args.binary.is_file():
        binary_sha = sha256_bytes(args.binary.read_bytes())

    manifest = {
        "kind": "engine-observed goldens",
        "label": args.label,
        "normalization": VOLATILE_NOTE,
        "observedOn": {
            "uname": uname,
            "runner": args.runner or ("local host (no runner)" if not uname else "unspecified"),
            "hostPlatform": platform.platform(),
        },
        "engine": {"binary": "floe-impeccable", "sha256": binary_sha},
        "cases": {},
    }
    if args.evidence and args.evidence.is_file():
        evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
        manifest["verification"] = {
            "checksTotal": evidence.get("checksTotal"),
            "checksPassed": evidence.get("checksPassed"),
            "failures": evidence.get("failures"),
            "parity": {k: v for k, v in (evidence.get("parity") or {}).items() if k != "mismatched"},
            "runner": (evidence.get("environment") or {}).get("runner"),
        }
        manifest["engine"]["sha256"] = (evidence.get("environment") or {}).get("binarySha256", binary_sha)

    for result in sorted(out_dir.glob("*.result.json")):
        case = result.name[: -len(".result.json")]
        exit_path = out_dir / f"{case}.exit"
        try:
            doc = json.loads(result.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            manifest["cases"][case] = {"error": f"unparseable result: {exc}"}
            continue
        normalized = normalize(doc)
        text = json.dumps(normalized, indent=2, ensure_ascii=False) + "\n"
        target = args.out / f"{case}.result.v1.json"
        target.write_text(text, encoding="utf-8")
        manifest["cases"][case] = {
            "file": target.name,
            "exit": int(exit_path.read_text(encoding="utf-8").strip()) if exit_path.is_file() else None,
            "status": normalized.get("status"),
            "verdict": normalized.get("verdict"),
            "errorCode": (normalized.get("error") or {}).get("code"),
            "findingsTotal": ((normalized.get("findings") or {}).get("counts") or {}).get("total"),
            "byRule": ((normalized.get("findings") or {}).get("counts") or {}).get("byRule"),
            "needsHitTests": len(((normalized.get("needs") or {}).get("hitTests")) or []),
            "uncoveredRequired": (normalized.get("coverage") or {}).get("uncoveredRequired"),
            "sha256": sha256_bytes(text.encode("utf-8")),
            "bytes": len(text.encode("utf-8")),
        }

    (args.out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "label": args.label,
        "out": str(args.out),
        "cases": len(manifest["cases"]),
        "uname": uname,
        "engineSha256": manifest["engine"]["sha256"],
        "verification": manifest.get("verification", {}).get("checksPassed"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
