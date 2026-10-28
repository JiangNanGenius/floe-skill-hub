#!/usr/bin/env python3
"""Regression for the Impeccable candidate identity projection (job-0fddfe266ef24033).

Real failure (hosted updater run 40622397082 at source 20e850e4): the staged
candidate preflight passed the exact-context patch application, then the
UNCHANGED build identity gate refused the staged contract because the staging
projection carried the four upstream identity keys but missed the rest of the
canonical component identity — the engine-probe verb's documented stdout still
said `impeccable-engine 0.1.17+floe.1.1.1`, while the gate derived
`impeccable-engine 0.1.18+floe.1.1.1` from the candidate pin ENGINE_VERSION
plus the adapter crate Cargo.toml version (the single component version
constant the binary embeds).

The repair is inside `stage_candidate_engine.py` only: the staged TEMP
contract is projected through the adapter's own canonical helper
(`adapter/tools/sync_contract_identity.py`, the trusted Root-frozen formula)
using the candidate lock's validated engineVersion and the crate component
version — never a caller-supplied string — covering engine.floeAdapterVersion
and verbs[engine-probe].stdout next to the existing keys, authenticating the
lock's engineId/floe.adapterVersion against the derivation, and self-checking
the written staged contract. The frozen contract, lock, adapter, goldens and
every validator are unchanged.

Stdlib only. Run:

    python3 tests/test_impeccable_candidate_identity.py

Set TMPDIR outside the hub checkout first (as for the other impeccable tests).
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ENGINE_DIR = REPO / "engines" / "impeccable"
TRACKED_CONTRACT = ENGINE_DIR / "contract" / "snapshot-contract.v1.json"
TRACKED_LOCK = ENGINE_DIR / "ENGINE-LOCK.json"
STAGE_PY = ENGINE_DIR / "workflows" / "tools" / "stage_candidate_engine.py"
BUILDER = ENGINE_DIR / "build" / "build_engine.py"
COMPARE_PY = ENGINE_DIR / "workflows" / "tools" / "compare_expected.py"

# The real hosted candidate: upstream pin f29cd24f (tree dd704e4f,
# ENGINE_VERSION 0.1.18). Identity fields only; the rest of the candidate
# lock is the tracked lock's reviewed content, exactly like update_lock.py
# stages it in the workflow.
CANDIDATE = {
    "commit": "f29cd24fdecfa5612e35e34c1c868d4a3fca930c",
    "tree": "dd704e4fe593e595f274637332aa1ee35060bace",
    "version": "0.1.18",
}

BASE_ENV = {
    "PATH": "/usr/bin:/bin",
    "HOME": os.environ.get("HOME", "/tmp"),
    "GIT_CONFIG_NOSYSTEM": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
}

ADAPTER_VERSION = re.search(
    r'^version\s*=\s*"([^"]+)"\s*$',
    (ENGINE_DIR / "adapter" / "Cargo.toml").read_text(encoding="utf-8"),
    re.MULTILINE).group(1)
COMPONENT = f"{CANDIDATE['version']}+floe.{ADAPTER_VERSION}"
PUBLISHED_COMPONENT = f"0.1.17+floe.{ADAPTER_VERSION}"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load_module(BUILDER, "candidate_identity_build_engine")
compare = load_module(COMPARE_PY, "candidate_identity_compare_expected")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_digest(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            h.update(str(path.relative_to(root)).encode("utf-8"))
            h.update(sha256_file(path).encode("ascii"))
    return h.hexdigest()


def candidate_lock_doc() -> dict:
    lock = json.loads(TRACKED_LOCK.read_text(encoding="utf-8"))
    lock["upstream"]["commit"] = CANDIDATE["commit"]
    lock["upstream"]["tree"] = CANDIDATE["tree"]
    lock["upstream"]["engineVersion"] = CANDIDATE["version"]
    lock["engineId"] = f"impeccable-{COMPONENT}"
    lock["status"] = "candidate-update-not-qualified"
    return lock


def pre_fix_projection() -> dict:
    """What the staged contract looked like BEFORE this repair: the seven
    upstream/provenance identity fields projected, but the engine-probe verb
    and the crate-derived component fields left at the published values."""
    doc = json.loads(TRACKED_CONTRACT.read_text(encoding="utf-8"))
    doc["engine"]["upstreamCommit"] = CANDIDATE["commit"]
    doc["engine"]["upstreamTree"] = CANDIDATE["tree"]
    doc["engine"]["upstreamEngineVersion"] = CANDIDATE["version"]
    doc["engine"]["engineId"] = f"impeccable-{COMPONENT}"
    doc["provenance"]["upstreamCommit"] = CANDIDATE["commit"]
    doc["provenance"]["upstreamTree"] = CANDIDATE["tree"]
    doc["provenance"]["engineVersionFile"] = CANDIDATE["version"]
    return doc


class TestOriginalHostedFailurePreserved(unittest.TestCase):
    """The unchanged validator still refuses the OLD projection with exactly
    the single engine-probe problem the hosted log recorded."""

    def test_pre_fix_projection_fails_the_identity_gate_with_the_hosted_problem(self):
        pin = {"commit": CANDIDATE["commit"], "tree": CANDIDATE["tree"],
               "engineVersion": CANDIDATE["version"]}
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), self.assertRaises(SystemExit) as ctx:
            builder.verify_contract_identity(pre_fix_projection(), ADAPTER_VERSION, pin)
        self.assertEqual(ctx.exception.code, 2)
        failure = json.loads(stdout.getvalue())
        self.assertIn("single component version constant", failure["error"])
        self.assertEqual(failure["problems"], [
            f"verbs[engine-probe].stdout is 'impeccable-engine {PUBLISHED_COMPONENT}\\n', "
            f"must be 'impeccable-engine {COMPONENT}\\n'",
        ], "the preserved failure must be exactly the hosted run's identity-gate problem")


class TestStagedProjection(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="impeccable-candidate-identity-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.lock = self.tmp / "ENGINE-LOCK.json"
        self.lock.write_text(json.dumps(candidate_lock_doc(), indent=2,
                                        ensure_ascii=False) + "\n", encoding="utf-8")
        self.out = self.tmp / "hub"

    def stage(self, lock: Path | None = None) -> dict:
        proc = subprocess.run(
            [sys.executable, str(STAGE_PY), "--engine-dir", str(ENGINE_DIR),
             "--candidate-lock", str(lock or self.lock), "--out", str(self.out)],
            capture_output=True, text=True, env=BASE_ENV, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        return json.loads(proc.stdout)

    def test_staged_contract_passes_the_unchanged_identity_validator(self):
        receipt = self.stage()
        self.assertEqual(receipt["identitySelfCheck"], "passed")
        self.assertEqual(receipt["componentVersion"], COMPONENT)
        staged_dir = self.out / "engines" / "impeccable"
        doc = json.loads((staged_dir / "contract" / "snapshot-contract.v1.json")
                         .read_text(encoding="utf-8"))
        pin = {"commit": CANDIDATE["commit"], "tree": CANDIDATE["tree"],
               "engineVersion": CANDIDATE["version"]}
        self.assertEqual(builder.verify_contract_identity(
            doc, builder.crate_adapter_version(staged_dir / "adapter"), pin), COMPONENT)
        self.assertEqual(doc["engine"]["upstreamCommit"], pin["commit"])

    def test_only_the_canonical_identity_fields_moved(self):
        receipt = self.stage()
        doc = json.loads((self.out / "engines" / "impeccable" / "contract"
                          / "snapshot-contract.v1.json").read_text(encoding="utf-8"))
        tracked = json.loads(TRACKED_CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(receipt["contractChanges"], [
            {"field": "engine.upstreamCommit", "before": tracked["engine"]["upstreamCommit"],
             "after": CANDIDATE["commit"]},
            {"field": "engine.upstreamTree", "before": tracked["engine"]["upstreamTree"],
             "after": CANDIDATE["tree"]},
            {"field": "engine.upstreamEngineVersion", "before": "0.1.17",
             "after": CANDIDATE["version"]},
            {"field": "engine.engineId", "before": f"impeccable-{PUBLISHED_COMPONENT}",
             "after": f"impeccable-{COMPONENT}"},
            {"field": "provenance.upstreamCommit",
             "before": tracked["provenance"]["upstreamCommit"], "after": CANDIDATE["commit"]},
            {"field": "provenance.upstreamTree",
             "before": tracked["provenance"]["upstreamTree"], "after": CANDIDATE["tree"]},
            {"field": "provenance.engineVersionFile", "before": "0.1.17",
             "after": CANDIDATE["version"]},
            {"field": "engine.floeAdapterVersion", "before": ADAPTER_VERSION,
             "after": ADAPTER_VERSION},
            {"field": "verbs[engine-probe].stdout",
             "before": f"impeccable-engine {PUBLISHED_COMPONENT}\n",
             "after": f"impeccable-engine {COMPONENT}\n"},
        ])
        # every remaining field is value-identical to the tracked contract:
        # re-applying exactly the nine projected identity fields to the
        # tracked document must reproduce the staged document
        expected_doc = json.loads(TRACKED_CONTRACT.read_text(encoding="utf-8"))
        expected_doc["engine"].update(
            upstreamCommit=CANDIDATE["commit"], upstreamTree=CANDIDATE["tree"],
            upstreamEngineVersion=CANDIDATE["version"], engineId=f"impeccable-{COMPONENT}",
            floeAdapterVersion=ADAPTER_VERSION)
        expected_doc["provenance"].update(
            upstreamCommit=CANDIDATE["commit"], upstreamTree=CANDIDATE["tree"],
            engineVersionFile=CANDIDATE["version"])
        probe = next(v for v in expected_doc["verbs"] if v.get("name") == "engine-probe")
        probe["stdout"] = f"impeccable-engine {COMPONENT}\n"
        self.assertEqual(doc, expected_doc)
        # pinned source digests and coverage stay exactly as reviewed
        self.assertEqual(doc["provenance"]["pinnedSourceDigests"],
                         tracked["provenance"]["pinnedSourceDigests"])
        self.assertEqual(doc["contractVersion"], tracked["contractVersion"])

    def test_receipt_hash_matches_the_rewritten_bytes(self):
        receipt = self.stage()
        staged = self.out / "engines" / "impeccable" / "contract" / "snapshot-contract.v1.json"
        self.assertEqual(sha256_file(staged), receipt["stagedContractSha256"])

    def test_malicious_or_stale_lock_identity_is_refused_without_writes(self):
        for label, mutate in (
            ("crate suffix mismatch", lambda d: d.update(engineId=f"impeccable-{CANDIDATE['version']}+floe.9.9.9")),
            ("version part mismatch", lambda d: d.update(engineId=f"impeccable-9.9.9+floe.{ADAPTER_VERSION}")),
            ("non-canonical shape", lambda d: d.update(engineId="impeccable-tampered")),
            ("floe.adapterVersion mismatch", lambda d: d["floe"].update(adapterVersion="9.9.9")),
        ):
            with self.subTest(label):
                doc = candidate_lock_doc()
                mutate(doc)
                bad_lock = self.tmp / f"bad-{label.replace(' ', '-')}.json"
                bad_lock.write_text(json.dumps(doc), encoding="utf-8")
                proc = subprocess.run(
                    [sys.executable, str(STAGE_PY), "--engine-dir", str(ENGINE_DIR),
                     "--candidate-lock", str(bad_lock), "--out", str(self.out / label)],
                    capture_output=True, text=True, env=BASE_ENV, timeout=120)
                self.assertEqual(proc.returncode, 2, f"{label}: {proc.stdout}{proc.stderr}")
                payload = json.loads(proc.stdout)
                self.assertFalse(payload["ok"])
                self.assertFalse((self.out / label).exists(),
                                 f"{label}: a refused candidate must stage nothing")

    def test_published_0117_candidate_projection_is_byte_compatible(self):
        tracked_copy = self.tmp / "tracked-lock.json"
        tracked_copy.write_bytes(TRACKED_LOCK.read_bytes())
        receipt = self.stage(tracked_copy)
        staged = self.out / "engines" / "impeccable" / "contract" / "snapshot-contract.v1.json"
        self.assertEqual(sha256_file(staged), sha256_file(TRACKED_CONTRACT))
        self.assertEqual(json.loads(staged.read_text(encoding="utf-8")),
                         json.loads(TRACKED_CONTRACT.read_text(encoding="utf-8")))
        self.assertEqual(receipt["trackedContractSha256"], receipt["stagedContractSha256"])


class TestFrozenDataUntouched(unittest.TestCase):
    """Staging candidates never writes into the tracked contract, lock,
    adapter, builder or the recorded goldens."""

    def test_tracked_tree_bytes_are_unchanged_after_projection(self):
        before = {
            "contract": sha256_file(TRACKED_CONTRACT),
            "lock": sha256_file(TRACKED_LOCK),
            "adapter": tree_digest(ENGINE_DIR / "adapter"),
            "goldens-host": tree_digest(ENGINE_DIR / "contract" / "expected" / "host-arm64"),
            "goldens-riscv": tree_digest(ENGINE_DIR / "contract" / "expected" / "riscv64-docker"),
            "builder": sha256_file(BUILDER),
        }
        tmp = Path(tempfile.mkdtemp(prefix="impeccable-frozen-check-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        lock = tmp / "ENGINE-LOCK.json"
        lock.write_text(json.dumps(candidate_lock_doc(), indent=2, ensure_ascii=False),
                        encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(STAGE_PY), "--engine-dir", str(ENGINE_DIR),
             "--candidate-lock", str(lock), "--out", str(tmp / "hub")],
            capture_output=True, text=True, env=BASE_ENV, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        after = {
            "contract": sha256_file(TRACKED_CONTRACT),
            "lock": sha256_file(TRACKED_LOCK),
            "adapter": tree_digest(ENGINE_DIR / "adapter"),
            "goldens-host": tree_digest(ENGINE_DIR / "contract" / "expected" / "host-arm64"),
            "goldens-riscv": tree_digest(ENGINE_DIR / "contract" / "expected" / "riscv64-docker"),
            "builder": sha256_file(BUILDER),
        }
        self.assertEqual(before, after)


class TestComparatorLockAuthentication(unittest.TestCase):
    """compare_expected authenticates against the canonical component identity
    embedded in the candidate lock's engineId; stale or malformed forms fail
    closed before any golden is read."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="impeccable-compare-identity-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))

    def write_lock(self, doc: dict) -> Path:
        path = self.tmp / f"lock-{abs(hash(json.dumps(doc, sort_keys=True)))}.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        return path

    def valid_lock(self) -> dict:
        return {"engineId": f"impeccable-{COMPONENT}",
                "floe": {"adapterVersion": ADAPTER_VERSION},
                "upstream": {"commit": CANDIDATE["commit"], "tree": CANDIDATE["tree"],
                             "engineVersion": CANDIDATE["version"]}}

    def test_canonical_candidate_lock_authenticates(self):
        identity = compare.load_lock_identity(self.write_lock(self.valid_lock()))
        self.assertEqual(identity["engine.engineId"], f"impeccable-{COMPONENT}")
        self.assertEqual(identity["engine.upstreamEngineVersion"], CANDIDATE["version"])

    def test_stale_or_malformed_engine_id_fails_closed(self):
        cases = []
        stale = self.valid_lock()
        stale["engineId"] = f"impeccable-{PUBLISHED_COMPONENT}"  # the CURRENT published id
        cases.append(stale)
        suffix = self.valid_lock()
        suffix["engineId"] = f"impeccable-{CANDIDATE['version']}+floe.9.9.9"
        cases.append(suffix)
        shape = self.valid_lock()
        shape["engineId"] = "impeccable-tampered"
        cases.append(shape)
        floe = self.valid_lock()
        floe["floe"]["adapterVersion"] = "9.9.9"
        cases.append(floe)
        for doc in cases:
            with self.subTest(engineId=doc["engineId"],
                              floe=doc.get("floe", {}).get("adapterVersion")):
                with self.assertRaises(SystemExit) as ctx:
                    compare.load_lock_identity(self.write_lock(doc))
                self.assertIn("identity is unusable", str(ctx.exception.code))


if __name__ == "__main__":
    unittest.main(verbosity=2)
