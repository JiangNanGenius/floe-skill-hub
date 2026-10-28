#!/usr/bin/env python3
"""Verifier identity tests: the runtime handshake of verify_engine_run.py is
derived strictly from the contract the run authenticates against — for the
published 0.1.17+floe.1.1.1 baseline (tracked contract) and for a staged
0.1.18+floe.1.1.1 candidate (staged contract) — and fails closed on any
self-inconsistent or unusable contract BEFORE anything executes.

This replaces the historical hardcoded strings
(`probe.startswith("impeccable-engine 0.1.17+floe.")` and
`version == "0.1.17+floe.1.0.0"`), which went stale twice: they refused the
published 1.1.1 baseline's real `--version` and would refuse any future
upstream version bump. Nothing else about the verifier changed: every
behaviour, ABI, schema, coverage, finding and parity check still runs exactly
as before, and the two identity checks got STRICTER (byte-exact probe stdout
against the contract's own example, component version derived from the
canonical engineId).

Regression context: hosted run 40622397082 (patches applied, staged 0.1.18
contract) and the published-baseline qualification route both need one
verifier whose expectations follow the contract, not a frozen literal.

  cd floe-skill-hub && python3 tests/test_impeccable_verifier_identity.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[1]
ENGINE_DIR = REPO / "engines" / "impeccable"
VERIFY_PY = ENGINE_DIR / "build" / "verify_engine_run.py"
TRACKED_CONTRACT = ENGINE_DIR / "contract"
TRACKED_LOCK = ENGINE_DIR / "ENGINE-LOCK.json"
STAGE_PY = ENGINE_DIR / "workflows" / "tools" / "stage_candidate_engine.py"

HEX64 = re.compile(r"[0-9a-f]{64}")

BASE_ENV = {
    "PATH": "/usr/bin:/bin",
    "HOME": os.environ.get("HOME", "/tmp"),
    "GIT_CONFIG_NOSYSTEM": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
}

CANDIDATE = {
    "commit": "f29cd24fdecfa5612e35e34c1c868d4a3fca930c",
    "tree": "dd704e4fe593e595f274637332aa1ee35060bace",
    "version": "0.1.18",
}

ADAPTER_VERSION = re.search(
    r'^version\s*=\s*"([^"]+)"\s*$',
    (ENGINE_DIR / "adapter" / "Cargo.toml").read_text(encoding="utf-8"),
    re.MULTILINE).group(1)


def load_verify():
    spec = importlib.util.spec_from_file_location("floe_verify_engine_run", VERIFY_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VERIFY = load_verify()


def stage_candidate(tmp: Path) -> Path:
    """Stage the real 0.1.18 candidate view with the accepted stager and
    return the staged contract directory."""
    lock_doc = json.loads(TRACKED_LOCK.read_text(encoding="utf-8"))
    lock_doc["upstream"].update({"commit": CANDIDATE["commit"], "tree": CANDIDATE["tree"],
                                 "engineVersion": CANDIDATE["version"]})
    lock_doc["engineId"] = f"impeccable-{CANDIDATE['version']}+floe.{ADAPTER_VERSION}"
    lock_path = tmp / "ENGINE-LOCK.json"
    lock_path.write_text(json.dumps(lock_doc, indent=2, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(STAGE_PY), "--engine-dir", str(ENGINE_DIR),
         "--candidate-lock", str(lock_path), "--out", str(tmp / "hub")],
        capture_output=True, text=True, env=BASE_ENV, timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return tmp / "hub" / "engines" / "impeccable" / "contract"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fake_stage(tmp: Path, probe_stdout: str, version_stdout: str,
               contract_dir: Path) -> tuple[Path, dict]:
    """A stage whose out/ files carry the given probe/version prints, enough
    for evaluate()'s identity checks to be inspected by name."""
    stage = tmp / "stage"
    out = stage / "out"
    out.mkdir(parents=True)
    (out / "uname.txt").write_text("Linux\nriscv64\n6.8.0-117-generic\n", encoding="utf-8")
    (out / "binary.sha256").write_text("aa" * 32 + "\n", encoding="utf-8")
    (out / "probe.stdout").write_text(probe_stdout, encoding="utf-8")
    (out / "probe.exit").write_text("0\n", encoding="utf-8")
    (out / "version.stdout").write_text(version_stdout, encoding="utf-8")
    (out / "version.exit").write_text("0\n", encoding="utf-8")
    contract_bytes = (contract_dir / "snapshot-contract.v1.json").read_bytes()
    staged = {
        "binarySha256Host": "aa" * 32,
        "binaryBytes": 1,
        "parityCases": 0,
        "contractSnapshotSha256": sha256_bytes(contract_bytes),
        "identity": VERIFY.contract_identity(contract_dir),
    }
    return stage, staged


ARGS = SimpleNamespace(docker_platform=None, docker_image="alpine:3.20", runner=None)


def named_checks(report: dict) -> dict:
    return {c["check"]: c["ok"] for c in report["checks"]}


class TestContractIdentityDerivation(unittest.TestCase):
    def test_tracked_published_contract(self):
        identity = VERIFY.contract_identity(TRACKED_CONTRACT)
        self.assertEqual(identity["engineId"], "impeccable-0.1.17+floe.1.1.1")
        self.assertEqual(identity["componentVersion"], "0.1.17+floe.1.1.1")
        self.assertEqual(identity["probeStdout"], "impeccable-engine 0.1.17+floe.1.1.1\n")

    def test_staged_candidate_contract_projects_0_1_18(self):
        with tempfile.TemporaryDirectory(prefix="verifier-identity-") as t:
            tmp = Path(t)
            staged_contract = stage_candidate(tmp)
            identity = VERIFY.contract_identity(staged_contract)
            self.assertEqual(identity["engineId"], f"impeccable-0.1.18+floe.{ADAPTER_VERSION}")
            self.assertEqual(identity["componentVersion"], f"0.1.18+floe.{ADAPTER_VERSION}")
            self.assertEqual(identity["probeStdout"],
                             f"impeccable-engine 0.1.18+floe.{ADAPTER_VERSION}\n")

    def test_self_inconsistent_contract_fails_closed(self):
        for mutate, needle in [
            (lambda d: d["engine"].__setitem__("engineId", "impeccable-0.2.0+floe.1.1.1"),
             "upstreamEngineVersion"),
            (lambda d: d["engine"].__setitem__("floeAdapterVersion", "9.9.9"),
             "floeAdapterVersion"),
            (lambda d: next(v for v in d["verbs"] if v.get("name") == "engine-probe")
                .__setitem__("stdout", "impeccable-engine 0.1.17+floe.1.1.0\n"),
             "verbs[engine-probe].stdout"),
            (lambda d: d["engine"].__setitem__("engineId", "impeccable-0.1.17"),
             "canonical component identity"),
        ]:
            with self.subTest(needle=needle):
                with tempfile.TemporaryDirectory(prefix="verifier-hostile-") as t:
                    tmp = Path(t) / "contract"
                    shutil.copytree(TRACKED_CONTRACT, tmp)
                    doc = json.loads((tmp / "snapshot-contract.v1.json").read_text(encoding="utf-8"))
                    mutate(doc)
                    (tmp / "snapshot-contract.v1.json").write_text(
                        json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
                    with self.assertRaises(ValueError) as ctx:
                        VERIFY.contract_identity(tmp)
                    self.assertIn(needle, str(ctx.exception))

    def test_missing_contract_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix="verifier-empty-") as t:
            with self.assertRaises(ValueError):
                VERIFY.contract_identity(Path(t))

    def test_no_stale_literals_remain(self):
        source = VERIFY_PY.read_text(encoding="utf-8")
        self.assertNotIn("0.1.17+floe.1.0.0", source)
        self.assertNotIn('probe.startswith("impeccable-engine', source)
        self.assertNotIn('"0.1.17"', source)


class TestRuntimeIdentityChecks(unittest.TestCase):
    """evaluate() enforces the contract-derived expectations exactly; a binary
    presenting a different identity than the contract it is authenticated
    against fails even when everything else would pass."""

    def staged_tmp(self):
        tmp = Path(tempfile.mkdtemp(prefix="verifier-eval-"))
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        return tmp

    def candidate_pair(self):
        tmp = self.staged_tmp()
        staged_contract = stage_candidate(tmp)
        return tmp, staged_contract

    def run_eval(self, tmp, contract_dir, probe, version):
        sub = Path(tempfile.mkdtemp(prefix="eval-", dir=str(tmp)))
        stage, staged = fake_stage(sub, probe, version, contract_dir)
        report = VERIFY.evaluate(ARGS, stage, staged)
        return named_checks(report)

    def test_candidate_matching_identity_passes(self):
        tmp, staged_contract = self.candidate_pair()
        checks = self.run_eval(tmp, staged_contract,
                               f"impeccable-engine 0.1.18+floe.{ADAPTER_VERSION}\n",
                               f"0.1.18+floe.{ADAPTER_VERSION}\n")
        self.assertTrue(checks["engine-probe answers the handshake"])
        self.assertTrue(checks["--version prints engine+adapter"])

    def test_published_baseline_identity_passes_fixed_verifier(self):
        # The ORIGINAL hardcoded gate (`version == "0.1.17+floe.1.0.0"`) failed
        # the published qualified 1.1.1 baseline. The fixed verifier, derived
        # from the tracked contract, accepts it.
        tmp = self.staged_tmp()
        checks = self.run_eval(tmp, TRACKED_CONTRACT,
                               "impeccable-engine 0.1.17+floe.1.1.1\n",
                               "0.1.17+floe.1.1.1\n")
        self.assertTrue(checks["engine-probe answers the handshake"])
        self.assertTrue(checks["--version prints engine+adapter"])

    def test_malicious_identity_fails(self):
        tmp, staged_contract = self.candidate_pair()
        # stale handshake: claims the previous published version against the
        # staged candidate contract
        checks = self.run_eval(tmp, staged_contract,
                               "impeccable-engine 0.1.17+floe.1.1.1\n",
                               "0.1.18+floe.1.1.1\n")
        self.assertFalse(checks["engine-probe answers the handshake"])
        self.assertTrue(checks["--version prints engine+adapter"])
        # spoofed version line
        checks = self.run_eval(tmp, staged_contract,
                               f"impeccable-engine 0.1.18+floe.{ADAPTER_VERSION}\n",
                               "0.1.18+floe.9.9.9\n")
        self.assertTrue(checks["engine-probe answers the handshake"])
        self.assertFalse(checks["--version prints engine+adapter"])
        # prefix-only forgery: the old startswith gate accepted this shape
        checks = self.run_eval(tmp, staged_contract,
                               f"impeccable-engine 0.1.18+floe.{ADAPTER_VERSION} backdoored\n",
                               f"0.1.18+floe.{ADAPTER_VERSION}\n")
        self.assertFalse(checks["engine-probe answers the handshake"])
        # missing trailing newline: byte-exact gate rejects
        checks = self.run_eval(tmp, staged_contract,
                               f"impeccable-engine 0.1.18+floe.{ADAPTER_VERSION}",
                               f"0.1.18+floe.{ADAPTER_VERSION}\n")
        self.assertFalse(checks["engine-probe answers the handshake"])


class TestCandidateVersusPublishedBaselineDiff(unittest.TestCase):
    """The recorded-baseline comparison semantics used by the new GHA gate:
    candidate results (0.1.18 @ the candidate pin, same adapter crate as the
    published baseline) against a baseline record (0.1.17+floe.1.1.1 @ the
    tracked pin) must pass with exactly the four authenticated identity keys
    moving, while adapter-version, ABI/target and any finding/coverage change
    must stay review-blocking."""

    def setUp(self):
        spec = importlib.util.spec_from_file_location(
            "floe_compare_expected_baseline_semantics",
            ENGINE_DIR / "workflows" / "tools" / "compare_expected.py")
        self.compare = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.compare)
        self.tmp = Path(tempfile.mkdtemp(prefix="verifier-diff-"))
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))

    def baseline_lock(self) -> dict:
        return json.loads(TRACKED_LOCK.read_text(encoding="utf-8"))

    def candidate_lock(self) -> dict:
        lock = self.baseline_lock()
        lock["upstream"].update({"commit": CANDIDATE["commit"], "tree": CANDIDATE["tree"],
                                 "engineVersion": CANDIDATE["version"]})
        lock["engineId"] = f"impeccable-{CANDIDATE['version']}+floe.{ADAPTER_VERSION}"
        return lock

    def write_lock(self, doc: dict) -> Path:
        path = self.tmp / f"lock-{len(list(self.tmp.iterdir()))}.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        return path

    def baseline_doc(self, **engine_over) -> dict:
        base = self.baseline_lock()
        return {"engine": {
            "binary": "floe-impeccable",
            "upstreamEngineVersion": base["upstream"]["engineVersion"],
            "upstreamCommit": base["upstream"]["commit"],
            "upstreamTree": base["upstream"]["tree"],
            "pinAuthority": base["upstream"]["pinAuthority"],
            "floeAdapterVersion": ADAPTER_VERSION,
            "adapterCrateVersion": ADAPTER_VERSION,
            "engineId": base["engineId"],
            "targetTriple": "riscv64gc-unknown-linux-musl",
            "abi": "static ELF, no dynamic loader dependency",
            "runtimeExecution": "riscv64-linux",
        }, "findings": {"counts": {"total": 3, "byRule": {"tiny-text": 3}}},
            "coverage": {"passes": [{"id": "hit-test-fixpoint", "state": "covered"}]}}

    def candidate_doc(self, **engine_over) -> dict:
        doc = self.baseline_doc()
        cand = self.candidate_lock()
        doc["engine"].update({
            "upstreamEngineVersion": cand["upstream"]["engineVersion"],
            "upstreamCommit": cand["upstream"]["commit"],
            "upstreamTree": cand["upstream"]["tree"],
            "engineId": cand["engineId"],
        })
        doc["engine"].update(engine_over)
        return doc

    def diff(self, expected, observed):
        lock_identity = self.compare.load_lock_identity(self.write_lock(self.candidate_lock()))
        return self.compare.diff_documents("positive-round2", expected, observed,
                                           lock_identity, [])

    def test_identity_only_change_passes_with_evidence(self):
        entry = self.diff(self.baseline_doc(), self.candidate_doc())
        self.assertEqual(entry["state"], "identical")
        changed = {c["field"] for c in entry["candidateIdentityChanges"]}
        self.assertEqual(changed, set(self.compare.IDENTITY_KEYS))

    def test_adapter_version_drift_is_review_blocking(self):
        # never normalize adapter versions away
        entry = self.diff(self.baseline_doc(),
                          self.candidate_doc(adapterCrateVersion="1.1.2"))
        self.assertEqual(entry["state"], "changed-unapproved")
        self.assertIn("engine.adapterCrateVersion", [d["field"] for d in entry["differences"]])
        entry = self.diff(self.baseline_doc(),
                          self.candidate_doc(floeAdapterVersion="1.0.0"))
        self.assertEqual(entry["state"], "changed-unapproved")

    def test_abi_and_target_drift_is_review_blocking(self):
        entry = self.diff(self.baseline_doc(), self.candidate_doc(targetTriple="aarch64-apple-darwin"))
        self.assertEqual(entry["state"], "changed-unapproved")
        entry = self.diff(self.baseline_doc(), self.candidate_doc(runtimeExecution="host-comparison-build"))
        self.assertEqual(entry["state"], "changed-unapproved")

    def test_findings_change_is_review_blocking(self):
        observed = self.candidate_doc()
        observed["findings"]["counts"]["total"] = 2
        observed["findings"]["counts"]["byRule"]["tiny-text"] = 2
        entry = self.diff(self.baseline_doc(), observed)
        self.assertEqual(entry["state"], "changed-unapproved")
        fields = {d["field"] for d in entry["differences"]}
        self.assertIn("findings.counts.total", fields)

    def test_unauthenticated_candidate_identity_still_fails_closed(self):
        # a candidate result whose engineId is not its staged lock's can never
        # hide behind the identity exclusion
        forged = self.candidate_doc()
        forged["engine"]["engineId"] = f"impeccable-{CANDIDATE['version']}+floe.9.9.9"
        with self.assertRaises(SystemExit):
            self.diff(self.baseline_doc(), forged)


class TestCliFailClosed(unittest.TestCase):
    """A staged tree whose contract cannot authenticate its own identity stops
    the run before anything executes and before the stage is created."""

    def run_cli(self, contract_dir: Path, stage: Path) -> subprocess.CompletedProcess:
        binary = contract_dir.parent / "floe-impeccable-not-executed"
        binary.write_bytes(b"#!/bin/sh\nexit 0\n")
        build_tree = contract_dir.parent / "build-tree"
        build_tree.mkdir(exist_ok=True)
        adapter_data = contract_dir.parent / "adapter-data"
        adapter_data.mkdir(exist_ok=True)
        return subprocess.run(
            [sys.executable, str(VERIFY_PY), "--binary", str(binary),
             "--build-tree", str(build_tree), "--contract", str(contract_dir),
             "--adapter-data", str(adapter_data), "--stage", str(stage),
             "--out", str(contract_dir.parent / "out.json")],
            capture_output=True, text=True, env=BASE_ENV, timeout=60)

    def test_missing_snapshot_exits_2_without_staging(self):
        with tempfile.TemporaryDirectory(prefix="verifier-cli-") as t:
            tmp = Path(t)
            empty_contract = tmp / "contract"
            empty_contract.mkdir()
            stage = tmp / "stage"
            proc = self.run_cli(empty_contract, stage)
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            self.assertIn("the contract runtime identity is unusable", proc.stdout)
            self.assertFalse(stage.exists())

    def test_self_inconsistent_contract_exits_2(self):
        with tempfile.TemporaryDirectory(prefix="verifier-cli2-") as t:
            tmp = Path(t)
            contract = tmp / "contract"
            shutil.copytree(TRACKED_CONTRACT, contract)
            doc = json.loads((contract / "snapshot-contract.v1.json").read_text(encoding="utf-8"))
            doc["engine"]["engineId"] = "impeccable-7.7.7+floe.1.1.1"
            (contract / "snapshot-contract.v1.json").write_text(
                json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
            proc = self.run_cli(contract, tmp / "stage")
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            self.assertIn("the contract runtime identity is unusable", proc.stdout)
            self.assertIn("upstreamEngineVersion", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
