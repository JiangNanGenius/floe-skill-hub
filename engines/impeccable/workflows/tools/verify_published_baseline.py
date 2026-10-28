#!/usr/bin/env python3
"""Authenticate the PUBLISHED qualified engine baseline used as the honest
GHA comparison boundary — never the candidate's own output.

The updater pipeline compares a candidate engine against the current published
engine, re-executed in the same hosted emulated-riscv64 matrix. That baseline
must be the official qualified artifact, bound to the tracked lock and the
tracked contract — this tool is the fail-closed binding at both ends:

  --verify-binary   BEFORE the baseline is ever executed: the tracked
                    ENGINE-LOCK.json names engineId/component digests; the
                    dist artifact for that exact identity must exist under
                    engines/impeccable/dist/<engineId>/<target>/, its sha256
                    and size must equal the lock's component digests, every
                    SHA256SUMS.txt entry must verify, and the tracked
                    snapshot contract must carry the SAME canonical identity
                    (engineId, upstream pin fields, floeAdapterVersion and the
                    engine-probe stdout the binary must print). Writes a
                    receipt (engineId, binaryPath, digests, upstream pin) the
                    workflow threads through shape-asserted outputs.

  --verify-record   AFTER the baseline re-run has been recorded as a temp,
                    versioned expected tree (never committed): the recorded
                    tree's MANIFEST must bind the exact digest-verified binary
                    sha256, must have been observed under linux/riscv64
                    emulation with the full behaviour matrix clean (all checks
                    passed, no failures, upstream parity byte-identical), must
                    carry every case the committed goldens carry, and every
                    recorded result document must show the published identity
                    — upstream pin, engineId, floeAdapterVersion AND
                    adapterCrateVersion equal to the lock, targetTriple/abi/
                    runtimeExecution riscv64. A candidate result tree can
                    never pass this gate: its engine identity is the candidate
                    lock's, which the tracked lock forbids. This is what stops
                    "bless the candidate output as the baseline".

Nothing is executed, downloaded, committed or published; every input is read
only; any disagreement exits 2 with a JSON problem list.

  verify_published_baseline.py --verify-binary \
      --engine-dir engines/impeccable --lock engines/impeccable/ENGINE-LOCK.json \
      --out <receipt.json>

  verify_published_baseline.py --verify-record \
      --engine-dir engines/impeccable --lock engines/impeccable/ENGINE-LOCK.json \
      --receipt <binary receipt.json> --record <temp expected tree> \
      --out <record receipt.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ENGINE_ID_RE = re.compile(r"impeccable-([0-9]+\.[0-9]+\.[0-9]+)\+floe\.([0-9]+\.[0-9]+\.[0-9]+)")
HEX64 = re.compile(r"[0-9a-f]{64}")
HEX40 = re.compile(r"[0-9a-f]{40}")
TARGET_TRIPLE = "riscv64gc-unknown-linux-musl"
# The runtime facts a baseline observed under the hosted emulated matrix must
# show; anything else means the record did not come from that environment.
REQUIRED_TARGET_TRIPLE = TARGET_TRIPLE
REQUIRED_RUNTIME_EXECUTION = "riscv64-linux"


def fail(error: str, **detail) -> int:
    print(json.dumps({"ok": False, "error": error, **detail}, indent=2))
    return 2


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_published_identity(lock_path: Path, engine_dir: Path) -> dict:
    """The single published identity from the tracked lock and the tracked
    contract; they must agree exactly or nothing downstream is trustworthy."""
    problems = []
    lock = json.loads(Path(lock_path).read_text(encoding="utf-8"))
    engine_id = lock.get("engineId")
    match = ENGINE_ID_RE.fullmatch(engine_id) if isinstance(engine_id, str) else None
    if not match:
        return {"problems": [f"tracked lock engineId is not the canonical component identity: "
                             f"{engine_id!r}"]}
    version, adapter = match.group(1), match.group(2)
    upstream = lock.get("upstream") or {}
    commit, tree = upstream.get("commit"), upstream.get("tree")
    if not isinstance(commit, str) or not HEX40.fullmatch(commit):
        problems.append(f"tracked lock upstream.commit is not a 40-hex sha: {commit!r}")
    if not isinstance(tree, str) or not HEX40.fullmatch(tree):
        problems.append(f"tracked lock upstream.tree is not a 40-hex sha: {tree!r}")
    if upstream.get("engineVersion") != version:
        problems.append(f"tracked lock upstream.engineVersion {upstream.get('engineVersion')!r} "
                        f"does not embed into engineId version {version!r}")
    floe_adapter = (lock.get("floe") or {}).get("adapterVersion")
    if floe_adapter != adapter:
        problems.append(f"tracked lock floe.adapterVersion {floe_adapter!r} disagrees with "
                        f"engineId floe.{adapter!r}")
    component = lock.get("component") or {}
    artifact_sha, artifact_bytes = component.get("artifactSha256"), component.get("artifactBytes")
    if not isinstance(artifact_sha, str) or not HEX64.fullmatch(artifact_sha):
        problems.append(f"tracked lock component.artifactSha256 is not 64-hex: {artifact_sha!r}")
    if not isinstance(artifact_bytes, int) or artifact_bytes <= 0:
        problems.append(f"tracked lock component.artifactBytes is not a positive int: {artifact_bytes!r}")
    contract_path = engine_dir / "contract" / "snapshot-contract.v1.json"
    if not contract_path.is_file():
        problems.append(f"tracked contract snapshot missing: {contract_path}")
        return {"problems": problems}
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    ceng = contract.get("engine") or {}
    if ceng.get("engineId") != engine_id:
        problems.append(f"tracked contract engine.engineId {ceng.get('engineId')!r} != lock engineId {engine_id!r}")
    if ceng.get("upstreamCommit") != commit or ceng.get("upstreamTree") != tree:
        problems.append("tracked contract engine.upstreamCommit/Tree do not match the tracked lock pin")
    if ceng.get("upstreamEngineVersion") != version:
        problems.append(f"tracked contract engine.upstreamEngineVersion {ceng.get('upstreamEngineVersion')!r} != {version!r}")
    if ceng.get("floeAdapterVersion") != adapter:
        problems.append(f"tracked contract engine.floeAdapterVersion {ceng.get('floeAdapterVersion')!r} != {adapter!r}")
    probe = next((v for v in (contract.get("verbs") or [])
                  if isinstance(v, dict) and v.get("name") == "engine-probe"), None)
    want_probe = f"impeccable-engine {version}+floe.{adapter}\n"
    if probe is None or probe.get("stdout") != want_probe:
        problems.append(f"tracked contract verbs[engine-probe].stdout is "
                        f"{(probe or {}).get('stdout')!r}, must be {want_probe!r}")
    return {
        "problems": problems,
        "engineId": engine_id,
        "componentVersion": f"{version}+floe.{adapter}",
        "adapterVersion": adapter,
        "engineVersion": version,
        "upstreamCommit": commit,
        "upstreamTree": tree,
        "artifactSha256": artifact_sha,
        "artifactBytes": artifact_bytes,
        "contractSha256": sha256_file(contract_path),
        "probeStdout": want_probe,
    }


def verify_binary(args) -> int:
    engine_dir = Path(args.engine_dir).expanduser().resolve()
    ident = load_published_identity(Path(args.lock).expanduser().resolve(), engine_dir)
    if ident["problems"]:
        return fail("the tracked lock and tracked contract do not agree on one published identity",
                    problems=ident["problems"])
    dist_dir = engine_dir / "dist" / ident["engineId"] / TARGET_TRIPLE
    binary = dist_dir / "floe-impeccable"
    if not binary.is_file():
        return fail("the published baseline artifact is missing for the tracked lock identity",
                    binary=str(binary))
    problems = []
    digest = sha256_file(binary)
    if digest != ident["artifactSha256"]:
        problems.append(f"baseline binary sha256 {digest} != tracked lock artifactSha256 "
                        f"{ident['artifactSha256']}")
    size = binary.stat().st_size
    if size != ident["artifactBytes"]:
        problems.append(f"baseline binary size {size} != tracked lock artifactBytes "
                        f"{ident['artifactBytes']}")
    sums = dist_dir / "SHA256SUMS.txt"
    if not sums.is_file():
        problems.append(f"the dist artifact carries no SHA256SUMS.txt: {sums}")
    else:
        for line in sums.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 2 or not HEX64.fullmatch(parts[0]):
                problems.append(f"unparseable SHA256SUMS line: {line!r}")
                continue
            name = parts[1].lstrip("*")
            target = dist_dir / name
            if not target.is_file():
                problems.append(f"SHA256SUMS names a missing file: {name}")
            elif sha256_file(target) != parts[0]:
                problems.append(f"SHA256SUMS digest drifted for: {name}")
    if problems:
        return fail("the published baseline binary is not the artifact the official lock describes",
                    problems=problems)
    receipt = {
        "ok": True,
        "mode": "verify-binary",
        "engineId": ident["engineId"],
        "componentVersion": ident["componentVersion"],
        "adapterVersion": ident["adapterVersion"],
        "upstream": {"commit": ident["upstreamCommit"], "tree": ident["upstreamTree"],
                     "engineVersion": ident["engineVersion"]},
        "binaryPath": str(binary),
        "sha256": digest,
        "bytes": size,
        "contractSnapshotSha256": ident["contractSha256"],
        "note": "tracked bytes only; nothing executed, committed or published; the workflow "
                "re-runs this binary in the hosted emulated riscv64 matrix and records TEMP results",
    }
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in receipt.items() if k != "note"}, indent=2))
    return 0


def verify_record(args) -> int:
    engine_dir = Path(args.engine_dir).expanduser().resolve()
    ident = load_published_identity(Path(args.lock).expanduser().resolve(), engine_dir)
    if ident["problems"]:
        return fail("the tracked lock and tracked contract do not agree on one published identity",
                    problems=ident["problems"])
    receipt_path = Path(args.receipt).expanduser().resolve()
    record = Path(args.record).expanduser().resolve()
    if not receipt_path.is_file():
        return fail("the binary verification receipt is missing; run --verify-binary first",
                    receipt=str(receipt_path))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    manifest_path = record / "MANIFEST.json"
    if not manifest_path.is_file():
        return fail("the recorded baseline tree carries no MANIFEST.json", record=str(record))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems = []
    if not isinstance(receipt, dict) or receipt.get("ok") is not True \
            or receipt.get("mode") != "verify-binary":
        problems.append("the binary receipt is missing or was not written by a successful --verify-binary")
    else:
        if receipt.get("engineId") != ident["engineId"]:
            problems.append(f"the binary receipt names {receipt.get('engineId')!r}, not the tracked "
                            f"published identity {ident['engineId']!r}")
        bound_binary = Path(receipt.get("binaryPath", ""))
        if not bound_binary.is_file() or sha256_file(bound_binary) != ident["artifactSha256"]:
            problems.append("the binary the receipt bound has drifted from the official lock digest since verification")
    if manifest.get("kind") != "engine-observed goldens":
        problems.append(f"unexpected record kind: {manifest.get('kind')!r}")
    if manifest.get("engine", {}).get("sha256") != ident["artifactSha256"]:
        problems.append("the recorded tree was not produced by the digest-verified published binary")
    observed = (manifest.get("observedOn") or {}).get("runner") or ""
    if "linux/riscv64" not in observed and "riscv64" not in observed:
        problems.append(f"the record was not observed in the riscv64 matrix: runner {observed!r}")
    ver = manifest.get("verification") or {}
    if not ver:
        problems.append("the record carries no behaviour-matrix verification block; the baseline "
                        "must be re-run through the full matrix, not recorded from a bare scan")
    else:
        if ver.get("failures") != []:
            problems.append(f"the baseline matrix run reported failures: {ver.get('failures')!r}")
        if not ver.get("checksTotal") or ver.get("checksPassed") != ver.get("checksTotal"):
            problems.append(f"the baseline matrix checks did not all pass: "
                            f"{ver.get('checksPassed')}/{ver.get('checksTotal')}")
        parity = ver.get("parity") or {}
        if not parity.get("cases") or parity.get("byteIdentical") != parity.get("cases"):
            problems.append(f"upstream oracle parity is not byte-clean on the baseline: {parity!r}")
    label = manifest.get("label") or ""
    if not label.startswith(f"published-baseline-{ident['engineId']}"):
        problems.append(f"the record label {label!r} does not version the published identity")
    tracked_cases_path = engine_dir / "contract" / "expected" / "riscv64-docker" / "MANIFEST.json"
    tracked_cases = set()
    if tracked_cases_path.is_file():
        tracked_cases = set(json.loads(tracked_cases_path.read_text(encoding="utf-8")).get("cases") or {})
    else:
        problems.append(f"the committed riscv64-docker goldens MANIFEST is missing: {tracked_cases_path}")
    cases = manifest.get("cases") or {}
    missing = sorted(tracked_cases - set(cases))
    if missing:
        problems.append(f"the baseline record is missing cases the committed matrix carries: {missing}")
    if not cases:
        problems.append("the baseline record carries no cases at all")
    published_engine_block = {
        "upstreamCommit": ident["upstreamCommit"],
        "upstreamTree": ident["upstreamTree"],
        "upstreamEngineVersion": ident["engineVersion"],
        "engineId": ident["engineId"],
        "floeAdapterVersion": ident["adapterVersion"],
        "adapterCrateVersion": ident["adapterVersion"],
        "targetTriple": REQUIRED_TARGET_TRIPLE,
        "runtimeExecution": REQUIRED_RUNTIME_EXECUTION,
    }
    for case, entry in sorted(cases.items()):
        file_name = (entry or {}).get("file")
        if not file_name or not (record / file_name).is_file():
            problems.append(f"case {case}: recorded result file missing: {file_name!r}")
            continue
        if (entry or {}).get("sha256") and entry["sha256"] != sha256_file(record / file_name):
            problems.append(f"case {case}: the result file drifted from the record manifest digest")
            continue
        doc = json.loads((record / file_name).read_text(encoding="utf-8"))
        eng = doc.get("engine") or {}
        for field, want in published_engine_block.items():
            if eng.get(field) != want:
                problems.append(f"case {case}: engine.{field} is {eng.get(field)!r}, "
                                f"must be the published baseline value {want!r}")
    if problems:
        return fail("the recorded baseline tree is not a trusted published-baseline record",
                    problems=sorted(set(problems))[:40])
    out_receipt = {
        "ok": True,
        "mode": "verify-record",
        "engineId": ident["engineId"],
        "record": str(record),
        "label": label,
        "engineSha256": ident["artifactSha256"],
        "cases": len(cases),
        "trackedGoldenCasesCovered": len(tracked_cases),
        "note": "the temp baseline record is bound to the official lock digest, the published "
                "identity and a clean emulated-riscv64 behaviour matrix; candidate output cannot "
                "satisfy this gate and is never blessed as a baseline",
    }
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(out_receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out_receipt.items() if k != "note"}, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-binary", action="store_true")
    ap.add_argument("--verify-record", action="store_true")
    ap.add_argument("--engine-dir", required=True, type=Path)
    ap.add_argument("--lock", required=True, type=Path)
    ap.add_argument("--receipt", type=Path, default=None)
    ap.add_argument("--record", type=Path, default=None)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    if args.verify_binary == args.verify_record:
        return fail("exactly one of --verify-binary / --verify-record is required")
    if args.verify_record and not (args.receipt and args.record):
        return fail("--verify-record requires --receipt and --record")
    try:
        if args.verify_binary:
            return verify_binary(args)
        return verify_record(args)
    except (json.JSONDecodeError, OSError) as exc:
        return fail("unusable baseline verification input", problem=str(exc))


if __name__ == "__main__":
    sys.exit(main())
