#!/usr/bin/env python3
"""Runtime verification of a built Floe Impeccable engine.

Static verification (ELF class, machine, static linkage, digest) proves what the
artifact *is*. This script proves what it *does*, by running it in an execution
environment for its own architecture and checking the contract's observable
behaviour:

  * identity: `uname`, binary digest, `engine-probe`, `--version`;
  * the frozen contract: the `contract` verb prints bytes identical to the
    committed `snapshot-contract.v1.json`;
  * the Needs fixpoint: round 1 must come back `needs-facts` (exit 3) and never
    clean, and round 2 with the reference answers must complete with the real
    finding (exit 2);
  * the verdict rule: an empty finding list must stay `inconclusive` (exit 4)
    while required coverage passes are uncovered;
  * every refusal: parse, version, schema, identity binding, redaction,
    producer trust, fencing, facts bits, facts binding, budgets, timeout;
  * the offline upstream verbs: `detect` over the pinned upstream antipattern
    fixtures, compared byte-for-byte with the upstream oracle goldens, and
    `--list-rules`.

The runner is a command prefix, so the same checks run locally for a host build
and inside an emulated or real riscv64 environment for the guest artifact:

  verify_engine_run.py --binary <path> --stage <dir> --out <evidence.json> \
      --build-tree <exported-pinned-tree> --contract <contract-dir> \
      --adapter-data <adapter/tests/data> \
      [--runner "docker run --rm --platform linux/riscv64 -v <stage>:/verify -w /verify alpine:3.20"] \
      [--parity-limit 40]

With no --runner the checks run on this host, and the evidence records that
plainly: a host run is never riscv64 guest execution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

STAGE_MOUNT = "/verify"

# name -> (argv builder key, expected exit, expectation)
SCAN_CHECKS = [
    ("positive-round1", "positive", 3, {"status": "needs-facts", "verdict": "none"}),
    ("positive-round2", "positive-answered", 2, {"status": "complete", "verdict": "findings"}),
    ("overlay-round1", "overlay", 3, {"status": "needs-facts", "verdict": "none"}),
    ("overlay-round2", "overlay-answered", 2, {"status": "complete", "verdict": "findings"}),
    ("no-findings-round2", "no-findings-answered", 4, {"status": "inconclusive", "verdict": "inconclusive"}),
    ("snapshot-truncated", "invalid:snapshot-truncated.v1.json", 1, {"error.code": "snapshot-parse"}),
    ("snapshot-bad-version", "invalid:snapshot-bad-version.v1.json", 1, {"error.code": "snapshot-version-unsupported"}),
    ("snapshot-column-mismatch", "invalid:snapshot-style-column-mismatch.v1.json", 1, {"error.code": "schema-mismatch"}),
    ("identity-mismatch", "identity-invalid:identity-mismatch.v1.json", 1, {"error.code": "identity-mismatch"}),
    ("identity-missing-binding", "identity-invalid:identity-missing-session-binding.v1.json", 1, {"error.code": "identity-invalid"}),
    ("identity-redaction", "identity-invalid:identity-redaction-not-applied.v1.json", 1, {"error.code": "identity-redaction-not-applied"}),
    ("identity-model-trust", "identity-invalid:identity-model-declared-trust.v1.json", 1, {"error.code": "identity-untrusted-producer"}),
    ("identity-fenced", "identity-invalid:identity-fenced.v1.json", 1, {"error.code": "identity-superseded"}),
    ("facts-bits-mismatch", "facts-invalid:facts-bits-mismatch.v1.json", 1, {"error.code": "facts-bits-mismatch"}),
    ("facts-stale-capture", "facts-invalid:facts-stale-capture.v1.json", 1, {"error.code": "facts-binding-mismatch"}),
    ("facts-other-tab", "facts-invalid:facts-other-tab.v1.json", 1, {"error.code": "facts-binding-mismatch"}),
    ("budget-bytes", "budget-bytes", 1, {"error.code": "budget-exceeded"}),
    ("budget-rounds", "budget-rounds", 1, {"error.code": "budget-exceeded"}),
    ("timeout", "timeout", 1, {"error.code": "timeout"}),
    ("no-identity", "no-identity", 1, {"error.code": "identity-invalid"}),
    ("refused-update-verb", "verb:update", 1, {}),
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stage_inputs(args, stage: Path) -> dict:
    """Collect everything the runner needs into one mountable directory."""
    if stage.exists():
        shutil.rmtree(stage)
    (stage / "bin").mkdir(parents=True)
    binary = stage / "bin" / "floe-impeccable"
    shutil.copyfile(args.binary, binary)
    binary.chmod(0o755)

    shutil.copytree(args.contract / "fixtures", stage / "fixtures")
    shutil.copytree(args.adapter_data, stage / "adapter-data")

    # Upstream antipattern fixtures and their oracle goldens, bounded.
    fixtures_dir = args.build_tree / "tests" / "fixtures" / "antipatterns"
    golden_dir = args.build_tree / "tests" / "oracle" / "golden"
    parity = []
    if fixtures_dir.is_dir() and golden_dir.is_dir():
        (stage / "parity" / "fixtures").mkdir(parents=True)
        (stage / "parity" / "golden").mkdir(parents=True)
        for fixture in sorted(fixtures_dir.iterdir()):
            if not fixture.is_file():
                continue
            # Upstream derives the case id from the full file name, extension
            # included (`ent.name.replace(/[^a-z0-9]+/gi, '-')`), so the golden
            # for `all-caps-body.html` is `detect-fixture-json-all-caps-body-html.json`.
            case_id = "".join(c if c.isalnum() else "-" for c in fixture.name).lower()
            case_id = "-".join(part for part in case_id.split("-") if part)
            golden = golden_dir / f"detect-fixture-json-{case_id}.json"
            if not golden.is_file():
                continue
            shutil.copyfile(fixture, stage / "parity" / "fixtures" / fixture.name)
            shutil.copyfile(golden, stage / "parity" / "golden" / golden.name)
            parity.append({"fixture": fixture.name, "golden": golden.name, "caseId": case_id})
            if len(parity) >= args.parity_limit:
                break
    (stage / "parity" / "index.json").write_text(json.dumps(parity, indent=2) + "\n", encoding="utf-8")

    return {
        "binarySha256Host": sha256_file(args.binary),
        "binaryBytes": binary.stat().st_size,
        "parityCases": len(parity),
        "contractSnapshotSha256": sha256_file(args.contract / "snapshot-contract.v1.json"),
    }


def write_runner_script(stage: Path, prefix: str = STAGE_MOUNT) -> None:
    """One shell script: run every check, keep raw stdout/stderr/exit per check.

    Every staged path is quoted, so a stage directory whose path contains spaces
    (the parent checkout does) still runs.
    """
    lines = [
        "#!/bin/sh",
        "set -u",
        f'OUT="{prefix}/out"',
        "rm -rf \"$OUT\"; mkdir -p \"$OUT\"",
        f'E="{prefix}/bin/floe-impeccable"',
        f'F="{prefix}/fixtures"',
        f'A="{prefix}/adapter-data"',
        "{ uname -s; uname -m; uname -r; } > \"$OUT/uname.txt\" 2>&1",
        "( sha256sum \"$E\" || shasum -a 256 \"$E\" ) > \"$OUT/binary.sha256\" 2>&1",
        "run() {",
        "  name=$1; shift",
        "  \"$E\" \"$@\" > \"$OUT/$name.stdout\" 2> \"$OUT/$name.stderr\"",
        "  echo $? > \"$OUT/$name.exit\"",
        "}",
        "run probe engine-probe",
        "run version --version",
        "run contract contract",
        "run snapshot-schema snapshot-schema",
        "run help --help",
        # scan matrix
        "scan() {",
        "  name=$1; shift",
        "  run \"$name\" snapshot-scan --out \"$OUT/$name.result.json\" \"$@\"",
        "}",
        "scan positive-round1 --snapshot \"$F/snapshot-positive.v1.json\" --identity \"$F/identity-positive.v1.json\"",
        "scan positive-round2 --snapshot \"$F/snapshot-positive.v1.json\" --identity \"$F/identity-positive.v1.json\" --facts \"$A/facts-positive-round2.v1.json\" --round 2",
        "scan overlay-round1 --snapshot \"$F/snapshot-needs-hit-tests.v1.json\" --identity \"$F/identity-needs.v1.json\"",
        "scan overlay-round2 --snapshot \"$F/snapshot-needs-hit-tests.v1.json\" --identity \"$F/identity-needs.v1.json\" --facts \"$A/facts-overlay-round2.v1.json\" --round 2",
        "scan no-findings-round2 --snapshot \"$A/snapshot-no-findings.v1.json\" --identity \"$A/identity-no-findings.v1.json\" --facts \"$A/facts-no-findings-round2.v1.json\" --round 2",
        "scan media-round2 --snapshot \"$A/snapshot-media-intrinsics.v1.json\" --identity \"$A/identity-media.v1.json\" --facts \"$A/facts-media-round2.v1.json\" --round 2",
        "scan snapshot-truncated --snapshot \"$F/invalid/snapshot-truncated.v1.json\" --identity \"$F/identity-needs.v1.json\"",
        "scan snapshot-bad-version --snapshot \"$F/invalid/snapshot-bad-version.v1.json\" --identity \"$F/identity-needs.v1.json\"",
        "scan snapshot-column-mismatch --snapshot \"$F/invalid/snapshot-style-column-mismatch.v1.json\" --identity \"$F/identity-needs.v1.json\"",
        "scan identity-mismatch --snapshot \"$F/snapshot-needs-hit-tests.v1.json\" --identity \"$F/invalid/identity-mismatch.v1.json\"",
        "scan identity-missing-binding --snapshot \"$F/snapshot-needs-hit-tests.v1.json\" --identity \"$F/invalid/identity-missing-session-binding.v1.json\"",
        "scan identity-redaction --snapshot \"$F/snapshot-needs-hit-tests.v1.json\" --identity \"$F/invalid/identity-redaction-not-applied.v1.json\"",
        "scan identity-model-trust --snapshot \"$F/snapshot-needs-hit-tests.v1.json\" --identity \"$F/invalid/identity-model-declared-trust.v1.json\"",
        "scan identity-fenced --snapshot \"$F/snapshot-needs-hit-tests.v1.json\" --identity \"$F/invalid/identity-fenced.v1.json\"",
        "scan facts-bits-mismatch --snapshot \"$F/snapshot-needs-hit-tests.v1.json\" --identity \"$F/identity-needs.v1.json\" --facts \"$F/invalid/facts-bits-mismatch.v1.json\"",
        "scan facts-stale-capture --snapshot \"$F/snapshot-needs-hit-tests.v1.json\" --identity \"$F/identity-needs.v1.json\" --facts \"$F/invalid/facts-stale-capture.v1.json\"",
        "scan facts-other-tab --snapshot \"$F/snapshot-needs-hit-tests.v1.json\" --identity \"$F/identity-needs.v1.json\" --facts \"$F/invalid/facts-other-tab.v1.json\"",
        "scan budget-bytes --snapshot \"$F/snapshot-needs-hit-tests.v1.json\" --identity \"$F/identity-needs.v1.json\" --max-snapshot-bytes 4096",
        "scan budget-rounds --snapshot \"$F/snapshot-positive.v1.json\" --identity \"$F/identity-positive.v1.json\" --round 9",
        "scan timeout --snapshot \"$F/snapshot-positive.v1.json\" --identity \"$F/identity-positive.v1.json\" --timeout-ms 0",
        "scan no-identity --snapshot \"$F/snapshot-positive.v1.json\"",
        "run refused-update-verb update",
        "run refused-telemetry-verb telemetry",
        "run refused-cdp-verb detect --cdp 9222",
        "run list-rules detect --list-rules --json",
        # upstream parity corpus
        f'if [ -d "{prefix}/parity/fixtures" ]; then',
        f'  for f in "{prefix}"/parity/fixtures/*; do',
        "    base=$(basename \"$f\")",
        "    run \"parity-$base\" detect --no-config --json \"$f\"",
        "  done",
        "fi",
    ]
    (stage / "run-checks.sh").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (stage / "run-checks.sh").chmod(0o755)


def run_stage_docker(args, stage: Path) -> int:
    """Run the checks in a container for another architecture.

    `docker cp` rather than a bind mount: this host's Docker Desktop has no
    shared-path mapping for the checkout or the build cache, so a `-v` bind
    silently presents an empty directory. create + cp + start + cp-back is
    explicit, and it fails loudly when the copy does not land.
    """
    write_runner_script(stage, STAGE_MOUNT)
    image = args.docker_image
    create = subprocess.run(
        ["docker", "create", "--platform", args.docker_platform, image, "sh", f"{STAGE_MOUNT}/run-checks.sh"],
        capture_output=True, text=True,
    )
    if create.returncode != 0:
        raise RuntimeError(f"docker create failed: {create.stderr[-500:]}")
    container = create.stdout.strip()
    log_lines = [f"$ docker create --platform {args.docker_platform} {image}  -> {container}"]
    try:
        copy_in = subprocess.run(["docker", "cp", f"{stage}/.", f"{container}:{STAGE_MOUNT}"],
                                 capture_output=True, text=True)
        log_lines.append(f"$ docker cp {stage}/. {container}:{STAGE_MOUNT}\n{copy_in.stdout}{copy_in.stderr}")
        if copy_in.returncode != 0:
            raise RuntimeError(f"docker cp in failed: {copy_in.stderr[-500:]}")
        started = subprocess.run(["docker", "start", "-a", container], capture_output=True, text=True,
                                 timeout=args.timeout)
        log_lines.append(f"$ docker start -a {container}\nexit={started.returncode}\n"
                         f"--- stdout ---\n{started.stdout}\n--- stderr ---\n{started.stderr}")
        out_dir = stage / "out"
        if out_dir.exists():
            shutil.rmtree(out_dir)
        copy_out = subprocess.run(["docker", "cp", f"{container}:{STAGE_MOUNT}/out", str(out_dir)],
                                  capture_output=True, text=True)
        log_lines.append(f"$ docker cp {container}:{STAGE_MOUNT}/out {out_dir}\n{copy_out.stdout}{copy_out.stderr}")
        if copy_out.returncode != 0:
            raise RuntimeError(f"docker cp out failed: {copy_out.stderr[-500:]}")
        return started.returncode
    finally:
        (stage / "runner.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
        subprocess.run(["docker", "rm", "-f", container], capture_output=True, text=True)


def run_stage(args, stage: Path) -> int:
    if args.docker_platform:
        return run_stage_docker(args, stage)
    if args.runner:
        import shlex
        write_runner_script(stage, STAGE_MOUNT)
        cmd = shlex.split(args.runner) + ["sh", f"{STAGE_MOUNT}/run-checks.sh"]
        cwd = None
    else:
        # No runner: the same checks against relative paths, with the stage as
        # the working directory. Identical script shape, no path rewriting.
        write_runner_script(stage, ".")
        cmd = ["sh", "./run-checks.sh"]
        cwd = str(stage)
    print(f"[verify] {' '.join(cmd)} (cwd={cwd or 'inherited'})", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout, cwd=cwd)
    (stage / "runner.log").write_text(
        f"$ {' '.join(cmd)}\nexit={result.returncode}\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}\n",
        encoding="utf-8",
    )
    return result.returncode


def read_out(stage: Path, name: str, kind: str) -> str | None:
    path = stage / "out" / f"{name}.{kind}"
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else None


def normalize_parity_stdout(text: str, stage: Path) -> str:
    """Rewrite the staged fixture path to the oracle's own `<REPO>` placeholder.

    The upstream goldens record `<REPO>/tests/fixtures/antipatterns/<name>`
    verbatim, so the only legitimate difference between a golden and this
    engine's output is that path prefix. Everything else must match byte for
    byte; normalising more than the prefix would hide a real divergence.
    """
    placeholder = "<REPO>/tests/fixtures/antipatterns/"
    for prefix in (f"{STAGE_MOUNT}/parity/fixtures/", f"{stage}/parity/fixtures/"):
        text = text.replace(prefix, placeholder)
    return text


def dotted(doc: dict, path: str):
    node = doc
    for part in path.split("."):
        if isinstance(node, list):
            node = node[int(part)]
        elif isinstance(node, dict):
            node = node.get(part)
        else:
            return None
    return node


def evaluate(args, stage: Path, staged: dict) -> dict:
    checks: list[dict] = []
    failures: list[str] = []

    def check(name: str, ok: bool, detail=None) -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})
        if not ok:
            failures.append(name)

    uname = (read_out(stage, "uname", "txt") or "").split()
    binary_sha = (read_out(stage, "binary", "sha256") or "").split()
    check("the runner reports its architecture", len(uname) >= 2, uname[:3])
    check("the binary digest inside the runner matches the host artifact",
          bool(binary_sha) and binary_sha[0] == staged["binarySha256Host"],
          {"inRunner": binary_sha[0] if binary_sha else None, "host": staged["binarySha256Host"]})

    probe = read_out(stage, "probe", "stdout") or ""
    check("engine-probe answers the handshake", probe.startswith("impeccable-engine 0.1.17+floe."), probe.strip())
    check("engine-probe exits 0", (read_out(stage, "probe", "exit") or "").strip() == "0")
    version = (read_out(stage, "version", "stdout") or "").strip()
    check("--version prints engine+adapter", version == "0.1.17+floe.1.0.0", version)

    contract_bytes = read_out(stage, "contract", "stdout") or ""
    contract_digest = hashlib.sha256(contract_bytes.encode("utf-8")).hexdigest()
    check("the contract verb prints the committed contract bytes",
          contract_digest == staged["contractSnapshotSha256"],
          {"printed": contract_digest, "committed": staged["contractSnapshotSha256"]})
    schema_out = read_out(stage, "snapshot-schema", "stdout") or ""
    try:
        schema = json.loads(schema_out)
        check("snapshot-schema lists the pinned property columns",
              len(schema.get("styleProps", [])) == 138 and len(schema.get("pseudoProps", [])) == 23,
              {"styleProps": len(schema.get("styleProps", [])), "pseudoProps": len(schema.get("pseudoProps", []))})
    except json.JSONDecodeError as exc:
        check("snapshot-schema prints JSON", False, str(exc))

    help_out = read_out(stage, "help", "stdout") or ""
    check("help advertises the Floe verbs and not the refused ones",
          "snapshot-scan" in help_out and "  install " not in help_out and "  update " not in help_out)

    # The scan matrix.
    expectations = {name: (exit_code, expected) for name, _key, exit_code, expected in SCAN_CHECKS}
    expectations["media-round2"] = (2, {"status": "complete", "verdict": "findings"})
    for name, (expected_exit, expected_fields) in expectations.items():
        raw_exit = (read_out(stage, name, "exit") or "").strip()
        result_text = read_out(stage, name, "result.json")
        doc = None
        if result_text:
            try:
                doc = json.loads(result_text)
            except json.JSONDecodeError as exc:
                check(f"{name}: the result document is JSON", False, str(exc))
        check(f"{name}: exit code", raw_exit == str(expected_exit), {"exit": raw_exit, "expected": expected_exit})
        for path, expected in expected_fields.items():
            actual = dotted(doc, path) if doc else None
            check(f"{name}: {path}", actual == expected, {"actual": actual, "expected": expected})

    # Specific contract properties that the matrix alone does not pin.
    round1 = _load(stage, "positive-round1")
    if round1:
        needs = round1.get("needs") or {}
        points = needs.get("hitTests") or []
        bits = needs.get("hitTestsBits") or []
        check("round 1 asks for hit tests and carries their exact bits",
              len(points) > 0 and len(points) == len(bits),
              {"points": len(points), "bits": len(bits)})
        check("round 1 reports no findings", round1.get("findings") is None)
        states = {p["id"]: p["state"] for p in (round1.get("coverage", {}).get("passes") or [])}
        check("round 1 marks the fixpoint as needs-facts", states.get("hit-test-fixpoint") == "needs-facts", states.get("hit-test-fixpoint"))

    round2 = _load(stage, "positive-round2")
    if round2:
        counts = ((round2.get("findings") or {}).get("counts") or {})
        check("round 2 reports the real finding", (counts.get("byRule") or {}).get("tiny-text") == 1, counts.get("byRule"))
        check("round 2 has nothing pending", round2.get("needs") is None)
        states = {p["id"]: p["state"] for p in (round2.get("coverage", {}).get("passes") or [])}
        check("round 2 marks the fixpoint covered", states.get("hit-test-fixpoint") == "covered")
        check("round 2 marks style parity complete", states.get("state") is None and states.get("style-parity") == "complete")

    overlay = _load(stage, "overlay-round2")
    if overlay:
        by_rule = ((overlay.get("findings") or {}).get("counts") or {}).get("byRule") or {}
        check("the overlay page reports text-occlusion once the hit tests are answered",
              by_rule.get("text-occlusion") == 1, by_rule)

    no_findings = _load(stage, "no-findings-round2")
    if no_findings:
        counts = ((no_findings.get("findings") or {}).get("counts") or {})
        check("an empty finding list is inconclusive, never clean",
              counts.get("total") == 0 and no_findings.get("verdict") == "inconclusive",
              {"total": counts.get("total"), "verdict": no_findings.get("verdict")})
        uncovered = (no_findings.get("coverage") or {}).get("uncoveredRequired") or []
        check("the inconclusive receipt names the uncovered required passes",
              {"pixel-contrast", "reveal-sweep", "cross-origin-iframe", "same-origin-iframe", "script-errors"} <= set(uncovered),
              uncovered)
        check("the receipt says a clean verdict was not possible",
              (no_findings.get("coverage") or {}).get("cleanCapable") is False)

    media = _load(stage, "media-round2")
    if media:
        states = {p["id"]: p["state"] for p in (media.get("coverage", {}).get("passes") or [])}
        check("media intrinsics are reported as covered when the capture records them",
              states.get("media-intrinsics") == "covered", states.get("media-intrinsics"))

    for name, needle in (("refused-update-verb", "verb-unavailable"),
                         ("refused-telemetry-verb", "verb-unavailable"),
                         ("refused-cdp-verb", "--cdp")):
        stderr = read_out(stage, name, "stderr") or ""
        check(f"{name}: refusal carries its reason", needle in stderr, stderr[:160])

    rules_out = read_out(stage, "list-rules", "stdout") or ""
    try:
        rules = json.loads(rules_out)
        check("detect --list-rules prints the upstream rule catalog",
              isinstance(rules, list) and len(rules) > 40, {"rules": len(rules) if isinstance(rules, list) else None})
    except json.JSONDecodeError as exc:
        check("detect --list-rules prints JSON", False, str(exc))

    # Upstream parity corpus.
    parity_index_path = stage / "parity" / "index.json"
    parity_results = {"cases": 0, "byteIdentical": 0, "mismatched": []}
    if parity_index_path.is_file():
        for case in json.loads(parity_index_path.read_text(encoding="utf-8")):
            name = f"parity-{case['fixture']}"
            stdout = read_out(stage, name, "stdout")
            exit_code = (read_out(stage, name, "exit") or "").strip()
            golden_path = stage / "parity" / "golden" / case["golden"]
            if stdout is None or not golden_path.is_file():
                continue
            golden = json.loads(golden_path.read_text(encoding="utf-8"))
            parity_results["cases"] += 1
            normalized = normalize_parity_stdout(stdout, stage)
            same = normalized == golden.get("stdout", "") and exit_code == str(golden.get("exit"))
            if same:
                parity_results["byteIdentical"] += 1
            else:
                parity_results["mismatched"].append({
                    "case": case["caseId"],
                    "exit": exit_code,
                    "goldenExit": golden.get("exit"),
                    "stdoutMatches": normalized == golden.get("stdout", ""),
                    "stdoutBytes": len(stdout),
                    "goldenBytes": len(golden.get("stdout") or ""),
                    "firstDifference": _first_difference(normalized, golden.get("stdout") or ""),
                })
    check("the offline detect verb reproduces the upstream oracle goldens byte for byte",
          parity_results["cases"] > 0 and not parity_results["mismatched"], parity_results)

    return {
        "environment": {
            "uname": uname[:3],
            "runner": (
                f"docker {args.docker_platform} {args.docker_image}" if args.docker_platform
                else (args.runner or "local host (no runner)")
            ),
            "binarySha256": staged["binarySha256Host"],
            "binaryBytes": staged["binaryBytes"],
        },
        "checksTotal": len(checks),
        "checksPassed": sum(1 for c in checks if c["ok"]),
        "failures": failures,
        "parity": parity_results,
        "checks": checks,
    }


def _first_difference(got: str, expected: str) -> dict:
    """The first offset where two outputs diverge, so a mismatch is diagnosable."""
    for index, (a, b) in enumerate(zip(got, expected)):
        if a != b:
            return {"offset": index, "got": got[max(0, index - 60):index + 60],
                    "expected": expected[max(0, index - 60):index + 60]}
    return {"offset": min(len(got), len(expected)), "note": "prefix identical, lengths differ",
            "gotLength": len(got), "expectedLength": len(expected)}


def _load(stage: Path, name: str):
    text = read_out(stage, name, "result.json")
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--binary", required=True, type=Path)
    ap.add_argument("--build-tree", required=True, type=Path)
    ap.add_argument("--contract", required=True, type=Path)
    ap.add_argument("--adapter-data", required=True, type=Path)
    ap.add_argument("--stage", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--runner", default=None)
    ap.add_argument("--docker-platform", default=None,
                    help="run the checks in a container for this platform (for example linux/riscv64)")
    ap.add_argument("--docker-image", default="alpine:3.20")
    ap.add_argument("--parity-limit", type=int, default=40)
    ap.add_argument("--timeout", type=int, default=3600)
    args = ap.parse_args()

    # Absolute paths only: the engine prints absolute file paths in findings, and
    # the parity normaliser has to recognise the staged prefix exactly.
    for name in ("binary", "build_tree", "contract", "adapter_data", "stage", "out"):
        setattr(args, name, Path(getattr(args, name)).expanduser().resolve())

    for path in (args.binary, args.build_tree, args.contract, args.adapter_data):
        if not path.exists():
            print(json.dumps({"ok": False, "error": "missing input", "path": str(path)}, indent=2))
            return 2

    staged = stage_inputs(args, args.stage)
    print(f"[verify] staged {staged['parityCases']} parity cases; binary {staged['binarySha256Host'][:16]}…", flush=True)
    exit_code = run_stage(args, args.stage)
    report = evaluate(args, args.stage, staged)
    report["runnerExitCode"] = exit_code
    report["ok"] = not report["failures"] and exit_code == 0
    report["stage"] = str(args.stage)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    summary = {k: v for k, v in report.items() if k != "checks"}
    print(json.dumps(summary, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
