#!/usr/bin/env python3
"""Compare a candidate engine's results against the recorded goldens.

The updater workflow's regression gate: an upstream engine bump must not silently
change what a scan returns. This re-runs the same case matrix with the candidate
binary, normalizes the volatile fields exactly as `export_expected.py` does, and
diffs every case against the tracked golden directory.

A difference is a review item, not automatically a defect — an upstream rule fix
legitimately changes findings — so the output names each differing case, the
fields that moved, and the digest pair, and the workflow fails unless
`--allow-changes` lists them explicitly.

The recorded goldens carry the engine identity that produced them
(`engine.upstreamEngineVersion` / `engine.upstreamCommit` /
`engine.upstreamTree` / `engine.engineId`), so a legitimate newer engine
version would otherwise always diff. The same embedded contract identity is
also mirrored into `diagnostics.upstreamCommit` / `diagnostics.engineVersion`
on every result that reaches scan diagnostics (`adapter/src/scan.rs`), so
those two keys move with the same legitimate pin bump. The tool therefore
authenticates the candidate result's four engine identity fields (always
required) plus the diagnostics mirror against the explicitly staged candidate
lock FIRST: wrong or missing identity fails closed. The lock's
`engineId` — the component identity the engine-probe prints — must itself be
the canonical `impeccable-<engineVersion>+floe.<adapterVersion>` form
embedding that lock's own `upstream.engineVersion` (and agreeing with
`floe.adapterVersion` when present); a non-canonical or version-disagreeing
lock fails closed before any golden is read.

The diagnostics mirror is structural as well as authenticated: the two keys
must BOTH exist when EITHER exists (one alone, or an explicit null, is a
malformed result and fails closed), and they may be absent only when the
golden is equally an early-refusal document without them. A golden that does
carry the mirror must be self-coherent: its two non-null values must equal its
OWN `engine.upstreamCommit` / `engine.upstreamEngineVersion`, so a stale or
forged golden pair can never be silently excluded as a legitimate identity
change. A presence disagreement between the golden and the candidate is
structural drift, never an ignored identity change: the two fields stay in
the behavioural diff and the case is review-blocking. The golden-old vs
authenticated-new values of the validated keys are then recorded as
`candidateIdentityChanges` review evidence and excluded from the behavioural
diff. Nothing else under `engine.*` or `diagnostics.*` is ever excluded —
target triple, ABI, runtimeExecution, adapter versions, coverage, findings,
facts, other diagnostics fields and ownership still diff exactly, and a real
behavioural change still fails the gate.

  compare_expected.py --engine <binary> --contract <contract-dir> \
      --expected <expected/label> --out <comparison.json> \
      --candidate-lock <staged ENGINE-LOCK.json> \
      [--build-tree <exported-pinned-tree>] [--adapter-data <adapter/tests/data>] \
      [--allow-changes case1 case2] [--runner "docker ..."] [--docker-platform linux/riscv64]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD_DIR = HERE.parent.parent / "build"

# Fields that legitimately differ between two runs of the same engine.
VOLATILE = {
    "budget.elapsedMs",
    "error.detail.elapsedMs",
}

# The exact identity keys that may differ between a golden and a legitimately
# newer candidate, and only after the candidate's values are authenticated
# against the explicitly staged candidate lock. The four engine keys exist on
# every result; the diagnostics block mirrors the same embedded contract
# identity only on documents that reached scan diagnostics, so its two keys
# are validated structurally as well (both present or both absent).
ENGINE_IDENTITY_KEYS = (
    "engine.upstreamEngineVersion",
    "engine.upstreamCommit",
    "engine.upstreamTree",
    "engine.engineId",
)
DIAGNOSTICS_IDENTITY_KEYS = (
    "diagnostics.upstreamCommit",
    "diagnostics.engineVersion",
)
IDENTITY_KEYS = ENGINE_IDENTITY_KEYS + DIAGNOSTICS_IDENTITY_KEYS
# Every result document carries the engine block; only these four keys are
# unconditionally required. The diagnostics mirror's presence is handled by
# diagnostics_identity_presence().
REQUIRED_IDENTITY_KEYS = ENGINE_IDENTITY_KEYS


def load_lock_identity(path: Path) -> dict:
    """The candidate identity values the observed results must carry.

    The four engine fields and the two diagnostics mirror values are derived
    from the lock's validated upstream pin and canonical component id.
    Shape-checked fail-closed: a lock without a usable identity is a hard
    error, never a silent pass."""
    import re
    lock = json.loads(Path(path).read_text(encoding="utf-8"))
    upstream = lock.get("upstream") or {}
    commit = upstream.get("commit")
    tree = upstream.get("tree")
    version = upstream.get("engineVersion")
    engine_id = lock.get("engineId")
    hex40 = re.compile(r"[0-9a-f]{40}")
    semver = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
    component_id = re.compile(r"impeccable-([0-9]+\.[0-9]+\.[0-9]+)\+floe\.([0-9]+\.[0-9]+\.[0-9]+)")
    problems = []
    if not isinstance(commit, str) or not hex40.fullmatch(commit):
        problems.append(f"upstream.commit is not a 40-hex sha: {commit!r}")
    if not isinstance(tree, str) or not hex40.fullmatch(tree):
        problems.append(f"upstream.tree is not a 40-hex sha: {tree!r}")
    if not isinstance(version, str) or not semver.fullmatch(version):
        problems.append(f"upstream.engineVersion is not dotted-semver: {version!r}")
    if not isinstance(engine_id, str) or not engine_id:
        problems.append(f"engineId is missing: {engine_id!r}")
    else:
        # The engineId carries the full component identity the live
        # engine-probe prints (`impeccable-engine <engineId-minus-prefix>`),
        # so it must be the canonical `impeccable-<version>+floe.<adapter>`
        # form embedding THIS candidate's version — never an unchecked or
        # stale string. The build identity gate enforces the same shape from
        # the crate Cargo.toml; a lock that disagrees here fails closed.
        match = component_id.fullmatch(engine_id)
        if not match:
            problems.append("engineId is not the canonical component identity "
                            "'impeccable-<engineVersion>+floe.<adapterVersion>': "
                            f"{engine_id!r}")
        else:
            if isinstance(version, str) and match.group(1) != version:
                problems.append(f"engineId embeds version {match.group(1)!r} but "
                                f"upstream.engineVersion is {version!r}")
            floe_adapter = (lock.get("floe") or {}).get("adapterVersion")
            if floe_adapter is not None and floe_adapter != match.group(2):
                problems.append(f"engineId embeds adapter version {match.group(2)!r} but "
                                f"floe.adapterVersion is {floe_adapter!r}")
    if problems:
        raise SystemExit(json.dumps({"ok": False,
                                     "error": "candidate lock identity is unusable",
                                     "problems": problems}, indent=2))
    return {"engine.upstreamEngineVersion": version,
            "engine.upstreamCommit": commit,
            "engine.upstreamTree": tree,
            "engine.engineId": engine_id,
            # the diagnostics block mirrors the same embedded contract identity
            "diagnostics.upstreamCommit": commit,
            "diagnostics.engineVersion": version}


def diagnostics_identity_presence(case: str, flat: dict, side: str) -> bool:
    """Whether this document carries the two-key diagnostics identity mirror.

    The adapter writes both keys together, so one key alone is a malformed
    document and fails closed; both absent is the early-refusal shape.
    """
    present = {key: key in flat for key in DIAGNOSTICS_IDENTITY_KEYS}
    if any(present.values()) and not all(present.values()):
        raise SystemExit(json.dumps({
            "ok": False,
            "error": f"the {side} result carries only one of the two diagnostics "
                     "identity keys; they must both exist or both be absent",
            "case": case, "present": present}, indent=2))
    return all(present.values())


def authenticate_golden_diagnostics(case: str, expected_flat: dict) -> None:
    """Fail closed unless a golden's diagnostics mirror is self-coherent.

    The mirror records the identity of the binary that produced the golden, so
    both values must be non-null and equal the golden's OWN engine identity.
    Comparing it only for shape would let a stale or forged golden pair be
    excluded as a legitimate identity change; this check runs before any diff.
    """
    problems = []
    for diagnostics_key, engine_key in (
        ("diagnostics.upstreamCommit", "engine.upstreamCommit"),
        ("diagnostics.engineVersion", "engine.upstreamEngineVersion"),
    ):
        mirror = expected_flat.get(diagnostics_key)
        engine = expected_flat.get(engine_key)
        if mirror is None:
            problems.append(f"{diagnostics_key} is null")
        elif mirror != engine:
            problems.append(f"{diagnostics_key} is {mirror!r} but the golden's "
                            f"{engine_key} is {engine!r}")
    if problems:
        raise SystemExit(json.dumps({
            "ok": False,
            "error": "golden result carries an incoherent diagnostics identity mirror",
            "case": case, "problems": problems}, indent=2))


def authenticate_identity(case: str, observed_flat: dict, lock_identity: dict) -> bool:
    """Fail closed unless the candidate result carries EXACTLY the
    authenticated identity values of the staged candidate lock.

    The four engine keys are always required. The diagnostics mirror, when
    present at all, must be complete and carry the lock's values; an explicit
    null is a present-but-unusable value, never an absence. Returns whether
    the document carries the diagnostics mirror."""
    for key in REQUIRED_IDENTITY_KEYS:
        expected = lock_identity[key]
        if key not in observed_flat or observed_flat[key] is None:
            raise SystemExit(json.dumps({
                "ok": False,
                "error": "candidate result is missing an engine identity field",
                "case": case, "field": key, "lockExpected": expected}, indent=2))
        if observed_flat[key] != expected:
            raise SystemExit(json.dumps({
                "ok": False,
                "error": "candidate result engine identity does not match the staged candidate lock",
                "case": case, "field": key,
                "observed": observed_flat[key], "lockExpected": expected}, indent=2))
    has_diagnostics = diagnostics_identity_presence(case, observed_flat, "candidate")
    if has_diagnostics:
        for key in DIAGNOSTICS_IDENTITY_KEYS:
            expected = lock_identity[key]
            observed = observed_flat[key]
            if observed is None:
                raise SystemExit(json.dumps({
                    "ok": False,
                    "error": "candidate result carries a null diagnostics identity field",
                    "case": case, "field": key, "lockExpected": expected}, indent=2))
            if observed != expected:
                raise SystemExit(json.dumps({
                    "ok": False,
                    "error": "candidate result diagnostics identity does not match "
                             "the staged candidate lock",
                    "case": case, "field": key,
                    "observed": observed, "lockExpected": expected}, indent=2))
    return has_diagnostics


def diff_documents(case: str, expected_doc: dict, observed_doc: dict,
                   lock_identity: dict, allow_changes: list) -> dict:
    """Diff one golden against the observed candidate result.

    Returns the comparison entry; identity-key differences are authenticated
    first and reported separately as review evidence, never silently ignored:
    every other field still diffs exactly."""
    flat_expected = flatten(expected_doc)
    flat_observed = flatten(observed_doc)
    # Validate BOTH sides' diagnostics shape before authenticating: a golden
    # with half a mirror is as structurally unusable as a candidate with one.
    # A complete golden mirror must also agree with its OWN engine identity;
    # only then may it be excluded as a legitimate identity move.
    expected_diagnostics = diagnostics_identity_presence(case, flat_expected, "golden")
    if expected_diagnostics:
        authenticate_golden_diagnostics(case, flat_expected)
    observed_diagnostics = authenticate_identity(case, flat_observed, lock_identity)
    presence_agrees = expected_diagnostics == observed_diagnostics
    # A presence disagreement is structural drift, not an identity exclusion:
    # the diagnostics keys fall through to the strict diff below instead of
    # being skipped as a legitimate identity move.
    excluded_identity_keys = (set(IDENTITY_KEYS) if presence_agrees
                              else set(ENGINE_IDENTITY_KEYS))
    diffs = []
    identity_changes = []
    for key in sorted(set(flat_expected) | set(flat_observed)):
        if key in VOLATILE:
            continue
        if key in excluded_identity_keys:
            if flat_expected.get(key) != flat_observed.get(key):
                identity_changes.append({
                    "case": case, "field": key,
                    "goldenValue": flat_expected.get(key),
                    "candidateValue": flat_observed.get(key),
                })
            continue
        if (key not in flat_expected or key not in flat_observed
                or flat_expected[key] != flat_observed[key]):
            diffs.append({
                "field": key,
                "expected": flat_expected.get(key),
                "observed": flat_observed.get(key),
            })
    entry = {
        "case": case,
        "state": "identical" if not diffs else "changed",
        "byteIdentical": False,
        "expectedExit": None,
        "observedExit": None,
        "expectedStatus": None,
        "observedStatus": None,
        "expectedVerdict": None,
        "observedVerdict": None,
        "differences": diffs[:40],
        "differenceCount": len(diffs),
        "candidateIdentityChanges": identity_changes,
        "diagnosticsIdentityPresence": {
            "golden": expected_diagnostics,
            "candidate": observed_diagnostics,
        },
        "structuralDrift": not presence_agrees,
    }
    if diffs and case not in allow_changes:
        entry["state"] = "changed-unapproved"
    return entry


def flatten(doc, prefix: str = "") -> dict:
    flat: dict[str, object] = {}
    if isinstance(doc, dict):
        if not doc:
            flat[prefix] = {}
        for key, value in doc.items():
            flat.update(flatten(value, f"{prefix}.{key}" if prefix else key))
    elif isinstance(doc, list):
        if not doc:
            flat[prefix] = []
        for index, value in enumerate(doc):
            flat.update(flatten(value, f"{prefix}[{index}]"))
    else:
        flat[prefix] = doc
    return flat


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True, type=Path)
    ap.add_argument("--contract", required=True, type=Path)
    ap.add_argument("--expected", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--candidate-lock", required=True, type=Path,
                    help="the explicitly staged candidate ENGINE-LOCK.json the "
                         "observed results' engine identity is authenticated against")
    ap.add_argument("--build-tree", type=Path, default=None)
    ap.add_argument("--adapter-data", type=Path, default=None)
    ap.add_argument("--allow-changes", nargs="*", default=[])
    ap.add_argument("--runner", default=None)
    ap.add_argument("--docker-platform", default=None)
    ap.add_argument("--docker-image", default="alpine:3.20")
    ap.add_argument("--parity-limit", type=int, default=12)
    args = ap.parse_args()
    for name in ("engine", "contract", "expected", "out", "build_tree", "adapter_data",
                 "candidate_lock"):
        value = getattr(args, name)
        if value is not None:
            setattr(args, name, Path(value).expanduser().resolve())

    lock_identity = load_lock_identity(args.candidate_lock)

    manifest_path = args.expected / "MANIFEST.json"
    if not manifest_path.is_file():
        print(json.dumps({"ok": False, "error": "no MANIFEST.json in the golden directory",
                          "expected": str(args.expected)}, indent=2))
        return 2
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    engine_dir = BUILD_DIR
    adapter_data = args.adapter_data or (engine_dir.parent / "adapter" / "tests" / "data")
    build_tree = args.build_tree
    if build_tree is None:
        print(json.dumps({"ok": False, "error": "--build-tree is required to stage the parity corpus"}, indent=2))
        return 2

    workdir = Path(tempfile.mkdtemp(prefix="floe-impeccable-golden-"))
    try:
        stage = workdir / "stage"
        verify_report = workdir / "verify.json"
        verify_cmd = [
            sys.executable, str(engine_dir / "verify_engine_run.py"),
            "--binary", str(args.engine),
            "--build-tree", str(build_tree),
            "--contract", str(args.contract),
            "--adapter-data", str(adapter_data),
            "--stage", str(stage),
            "--out", str(verify_report),
            "--parity-limit", str(args.parity_limit),
        ]
        if args.docker_platform:
            verify_cmd += ["--docker-platform", args.docker_platform, "--docker-image", args.docker_image]
        elif args.runner:
            verify_cmd += ["--runner", args.runner]
        ran = subprocess.run(verify_cmd, capture_output=True, text=True)
        if not verify_report.is_file():
            print(json.dumps({"ok": False, "error": "the verification run produced no report",
                              "exit": ran.returncode, "stderr": ran.stderr[-1500:]}, indent=2))
            return 2

        observed_dir = workdir / "observed"
        exported = subprocess.run(
            [sys.executable, str(engine_dir / "export_expected.py"),
             "--stage", str(stage), "--label", "candidate", "--out", str(observed_dir),
             "--runner", args.runner or args.docker_platform or "local host",
             "--evidence", str(verify_report)],
            capture_output=True, text=True,
        )
        if exported.returncode != 0 or not (observed_dir / "MANIFEST.json").is_file():
            print(json.dumps({"ok": False, "error": "exporting the observed results failed",
                              "stderr": exported.stderr[-1500:]}, indent=2))
            return 2

        observed_manifest = json.loads((observed_dir / "MANIFEST.json").read_text(encoding="utf-8"))
        cases = sorted(set(manifest["cases"]) | set(observed_manifest["cases"]))
        comparison = []
        unexpected = []
        missing = []
        for case in cases:
            expected_entry = manifest["cases"].get(case)
            observed_entry = observed_manifest["cases"].get(case)
            if expected_entry is None:
                unexpected.append(case)
                comparison.append({"case": case, "state": "new-case", "observed": observed_entry})
                continue
            if observed_entry is None:
                missing.append(case)
                comparison.append({"case": case, "state": "missing-in-candidate",
                                   "expected": expected_entry})
                continue
            expected_path = args.expected / expected_entry["file"]
            observed_path = observed_dir / observed_entry["file"]
            expected_doc = json.loads(expected_path.read_text(encoding="utf-8"))
            observed_doc = json.loads(observed_path.read_text(encoding="utf-8"))
            entry = diff_documents(case, expected_doc, observed_doc,
                                   lock_identity, args.allow_changes)
            entry["byteIdentical"] = expected_entry.get("sha256") == observed_entry.get("sha256")
            entry["expectedExit"] = expected_entry.get("exit")
            entry["observedExit"] = observed_entry.get("exit")
            entry["expectedStatus"] = expected_entry.get("status")
            entry["observedStatus"] = observed_entry.get("status")
            entry["expectedVerdict"] = expected_entry.get("verdict")
            entry["observedVerdict"] = observed_entry.get("verdict")
            comparison.append(entry)

        unapproved = [c["case"] for c in comparison if c["state"] == "changed-unapproved"]
        identity_changes = [change for c in comparison
                            for change in c.get("candidateIdentityChanges", [])]
        report = {
            "ok": not unapproved and not missing,
            "engine": {
                "path": str(args.engine.name),
                "observedSha256": observed_manifest.get("engine", {}).get("sha256"),
                "goldenSha256": manifest.get("engine", {}).get("sha256"),
            },
            "goldenLabel": manifest.get("label"),
            "goldenRunner": (manifest.get("observedOn") or {}).get("runner"),
            "candidateRunner": observed_manifest.get("observedOn", {}).get("runner"),
            "candidateIdentity": {
                "authenticated": True,
                "source": "the explicitly staged candidate lock",
                "fields": sorted(IDENTITY_KEYS),
                "changes": identity_changes,
                "note": "these validated identity keys are excluded from the "
                        "behavioural diff only when the diagnostics mirror's "
                        "presence agrees on both sides; nothing else under "
                        "engine.* or diagnostics.* is, and a presence mismatch "
                        "is strict structural drift",
            },
            "cases": len(cases),
            "identical": sum(1 for c in comparison if c["state"] == "identical"),
            "changed": sum(1 for c in comparison if c["state"].startswith("changed")),
            "changedUnapproved": unapproved,
            "missing": missing,
            "newCases": unexpected,
            "allowedChanges": args.allow_changes,
            "volatileFields": sorted(VOLATILE),
            "verification": json.loads(verify_report.read_text(encoding="utf-8")).get("checksPassed"),
            "comparison": comparison,
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        summary = {k: v for k, v in report.items() if k != "comparison"}
        print(json.dumps(summary, indent=2))
        return 0 if report["ok"] else 1
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
