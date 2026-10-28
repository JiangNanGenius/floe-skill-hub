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

Follow-up real failure (hosted updater run 40642311746 at source 5c954c8): the
0.1.18 candidate built for riscv64 and for the host, then the host adapter
suite failed 2/12 — `contract_embedded.rs:49` and `:175` — because the staged
FLOE-owned Rust tests still pinned the published 0.1.17 identity. The same
stager now projects exactly those pinned identity literals in the staged TEMP
test copy (`tests/contract_embedded.rs`, `tests/snapshot_scan.rs` and the
engine/diagnostics identity lines of the recorded `tests/data/expected-*.json`
rule-pass goldens) from the frozen contract's authenticated identity to the
authenticated candidate identity. The trusted-test shape is anchored exactly
and fails closed before any test byte is written; every non-identity test byte,
assertion and behaviour check stays the tracked byte; staging the published pin
remains a byte-identical no-op; the rewritten temp bytes are hashed into the
staging receipt.

Hosted suite portability (same run 40642311746, next gate after the identity
literals): `tests/rule_pass_limiter.rs` compared `engine.targetTriple`
exactly, but its recorded goldens name `aarch64-apple-darwin` while the hosted
adapter suite compiles for `x86_64-unknown-linux-gnu`. The staged TEMP copy of
that single harness now asserts the observed result names the actual cargo
target from `adapter/build.rs`, asserts the recorded golden names its single
trusted archived target, and projects the expected golden's target to the
actual cargo target while keeping the field in the exact comparison. The
tracked test, the production comparator and the riscv verification target stay
strict; the binding is candidate-only, so staging the published pin still
reproduces every tracked test byte.

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


TEST_IDENTITY_FILES = (
    "tests/contract_embedded.rs",
    "tests/snapshot_scan.rs",
    "tests/data/expected-large-shape.v1.json",
    "tests/data/expected-admission-exactcap.v1.json",
    "tests/rule_pass_limiter.rs",
)


def archived_test_target() -> str:
    """The single trusted archived build target, from the frozen goldens."""
    targets = {
        json.loads((ENGINE_DIR / "adapter" / "tests" / "data" / name)
                   .read_text(encoding="utf-8"))["engine"]["targetTriple"]
        for name in ("expected-large-shape.v1.json", "expected-admission-exactcap.v1.json")
    }
    assert len(targets) == 1, targets
    return targets.pop()


def tracked_published_identity() -> dict:
    """The published identity the tracked tests pin, from the frozen contract."""
    engine = json.loads(TRACKED_CONTRACT.read_text(encoding="utf-8"))["engine"]
    return {"commit": engine["upstreamCommit"], "tree": engine["upstreamTree"],
            "version": engine["upstreamEngineVersion"]}


def rust_test_identity_pairs(published: dict) -> dict:
    """The pinned -> candidate identity lines for the real 0.1.18 candidate.

    Declared independently of the stager's own table so this test proves the
    expected bytes, not a mirror of the implementation."""
    version = CANDIDATE["version"]
    commit = CANDIDATE["commit"]
    tree = CANDIDATE["tree"]
    published_version = published["version"]
    published_commit = published["commit"]
    published_tree = published["tree"]
    published_component = f"{published_version}+floe.{ADAPTER_VERSION}"
    return {
        "tests/contract_embedded.rs": [
            (f'    assert_eq!(contract["engine"]["upstreamEngineVersion"]'
             f'.as_str().unwrap(), "{published_version}");',
             f'    assert_eq!(contract["engine"]["upstreamEngineVersion"]'
             f'.as_str().unwrap(), "{version}");', 1),
            (f'    assert_eq!(stdout, "impeccable-engine {published_component}\\n");',
             f'    assert_eq!(stdout, "impeccable-engine {COMPONENT}\\n");', 1),
            (f'    assert_eq!(stdout, "{published_component}\\n");',
             f'    assert_eq!(stdout, "{COMPONENT}\\n");', 1),
        ],
        "tests/snapshot_scan.rs": [
            (f'    assert_eq!(result.doc["engine"]["upstreamEngineVersion"], '
             f'json!("{published_version}"));',
             f'    assert_eq!(result.doc["engine"]["upstreamEngineVersion"], '
             f'json!("{version}"));', 1),
            (f'    assert_eq!(engine["upstreamEngineVersion"], json!("{published_version}"));',
             f'    assert_eq!(engine["upstreamEngineVersion"], json!("{version}"));', 1),
            (f'    assert_eq!(engine["engineId"], json!("impeccable-{published_component}"));',
             f'    assert_eq!(engine["engineId"], json!("impeccable-{COMPONENT}"));', 1),
        ],
        "tests/data/expected-large-shape.v1.json": [
            (f'    "upstreamEngineVersion": "{published_version}",',
             f'    "upstreamEngineVersion": "{version}",', 1),
            (f'    "upstreamCommit": "{published_commit}",',
             f'    "upstreamCommit": "{commit}",', 2),
            (f'    "upstreamTree": "{published_tree}",',
             f'    "upstreamTree": "{tree}",', 1),
            (f'    "engineVersion": "{published_version}",',
             f'    "engineVersion": "{version}",', 1),
        ],
        "tests/data/expected-admission-exactcap.v1.json": [
            (f'    "upstreamEngineVersion": "{published_version}",',
             f'    "upstreamEngineVersion": "{version}",', 1),
            (f'    "upstreamCommit": "{published_commit}",',
             f'    "upstreamCommit": "{commit}",', 2),
            (f'    "upstreamTree": "{published_tree}",',
             f'    "upstreamTree": "{tree}",', 1),
            (f'    "engineVersion": "{published_version}",',
             f'    "engineVersion": "{version}",', 1),
        ],
        "tests/rule_pass_limiter.rs": [
            (
                '        let observed = normalize(doc(&result).clone());\n',
                '        assert_eq!(\n'
                '            doc(&result)["engine"]["targetTriple"],\n'
                '            json!(env!("FLOE_TARGET_TRIPLE")),\n'
                '            "{name}: the candidate result names the build host target"\n'
                '        );\n'
                '        let observed = normalize(doc(&result).clone());\n',
                1,
            ),
            (
                '        let golden: Value = serde_json::from_str(\n'
                '            &std::fs::read_to_string(test_data().join(expected)).expect("golden exists"),\n'
                '        )\n'
                '        .expect("golden JSON");\n'
                '        let golden = normalize(golden);\n',
                '        let mut golden: Value = serde_json::from_str(\n'
                '            &std::fs::read_to_string(test_data().join(expected)).expect("golden exists"),\n'
                '        )\n'
                '        .expect("golden JSON");\n'
                '        assert_eq!(\n'
                '            golden["engine"]["targetTriple"],\n'
                f'            json!("{archived_test_target()}"),\n'
                '            "{name}: the recorded reference names its trusted archived build target"\n'
                '        );\n'
                '        golden["engine"]["targetTriple"] = json!(env!("FLOE_TARGET_TRIPLE"));\n'
                '        let golden = normalize(golden);\n',
                1,
            ),
        ],
    }


class TestStagedRustTestIdentity(unittest.TestCase):
    """Hosted run 40642311746: the staged FLOE-owned Rust tests pinned the
    published 0.1.17 identity while the staged contract and binary carried
    0.1.18, so the adapter suite failed 2/12 after a successful build. The
    staged TEMP tests must carry exactly the validated candidate identity, with
    every non-identity assertion byte-preserved."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="impeccable-staged-rust-identity-"))
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

    def test_staged_tests_pin_exactly_the_candidate_identity(self):
        receipt = self.stage()
        staged = self.out / "engines" / "impeccable"
        contract = json.loads((staged / "contract" / "snapshot-contract.v1.json")
                              .read_text(encoding="utf-8"))
        engine = contract["engine"]
        version = CANDIDATE["version"]
        # the staged tests must agree with the contract the staged binary embeds
        self.assertEqual(engine["upstreamEngineVersion"], version)
        self.assertEqual(engine["upstreamCommit"], CANDIDATE["commit"])
        self.assertEqual(engine["upstreamTree"], CANDIDATE["tree"])
        self.assertEqual(engine["engineId"], f"impeccable-{COMPONENT}")
        self.assertEqual(receipt["componentVersion"], COMPONENT)

        embedded = (staged / "adapter" / "tests" / "contract_embedded.rs").read_text(encoding="utf-8")
        # the hosted failure's line 49 and line 175 assertions, now pinned to
        # the candidate — the literal still guards an unintended bump
        self.assertIn('    assert_eq!(contract["engine"]["upstreamEngineVersion"]'
                      f'.as_str().unwrap(), "{version}");', embedded)
        self.assertIn(f'    assert_eq!(stdout, "impeccable-engine {COMPONENT}\\n");', embedded)
        self.assertIn(f'    assert_eq!(stdout, "{COMPONENT}\\n");', embedded)
        self.assertNotIn('"0.1.17"', embedded)

        scan = (staged / "adapter" / "tests" / "snapshot_scan.rs").read_text(encoding="utf-8")
        self.assertIn('    assert_eq!(result.doc["engine"]["upstreamEngineVersion"], '
                      f'json!("{version}"));', scan)
        self.assertIn(f'    assert_eq!(engine["upstreamEngineVersion"], json!("{version}"));', scan)
        self.assertIn(f'    assert_eq!(engine["engineId"], json!("impeccable-{COMPONENT}"));', scan)
        self.assertNotIn('"0.1.17"', scan)

        for name in ("expected-large-shape.v1.json", "expected-admission-exactcap.v1.json"):
            tracked = json.loads((ENGINE_DIR / "adapter" / "tests" / "data" / name)
                                 .read_text(encoding="utf-8"))
            doc = json.loads((staged / "adapter" / "tests" / "data" / name)
                             .read_text(encoding="utf-8"))
            self.assertEqual(doc["engine"]["upstreamEngineVersion"], version)
            self.assertEqual(doc["engine"]["upstreamCommit"], CANDIDATE["commit"])
            self.assertEqual(doc["engine"]["upstreamTree"], CANDIDATE["tree"])
            self.assertEqual(doc["diagnostics"]["upstreamCommit"], CANDIDATE["commit"])
            self.assertEqual(doc["diagnostics"]["engineVersion"], version)
            # the recorded pre-patch engineId is normalized away by the Rust
            # test; it stays the recorded byte, never blessed as the candidate
            self.assertEqual(doc["engine"]["engineId"], tracked["engine"]["engineId"])

        harness = (staged / "adapter" / "tests" / "rule_pass_limiter.rs").read_text(encoding="utf-8")
        # the candidate-only host binding asserts the actual cargo target on
        # both sides, pins the recorded golden's archived target, projects the
        # expected field, and KEEPS targetTriple in normalize() for exact
        # comparison (the normalizer must not remove it)
        self.assertIn('doc(&result)["engine"]["targetTriple"],', harness)
        self.assertIn('json!(env!("FLOE_TARGET_TRIPLE")),', harness)
        self.assertIn(f'json!("{archived_test_target()}"),', harness)
        self.assertIn('golden["engine"]["targetTriple"] = json!(env!("FLOE_TARGET_TRIPLE"));',
                      harness)
        normalize_body = re.search(
            r"fn normalize\(mut d: Value\) -> Value \{(.*?)\n\}", harness, re.S).group(1)
        self.assertIn('["engineId", "floeAdapterVersion", "adapterCrateVersion"]',
                      normalize_body)
        self.assertNotIn("targetTriple", normalize_body)

        identity = receipt["stagedTestIdentity"]
        self.assertEqual(identity["published"], {
            **tracked_published_identity(),
            "component": f"{tracked_published_identity()['version']}+floe.{ADAPTER_VERSION}",
        })
        self.assertEqual(len(identity["changes"]), 16)
        self.assertEqual({change["file"] for change in identity["changes"]},
                         set(TEST_IDENTITY_FILES))
        binding = identity["hostTargetBinding"]
        self.assertEqual(binding["file"], "tests/rule_pass_limiter.rs")
        self.assertEqual(binding["archivedTarget"], archived_test_target())
        self.assertEqual(binding["compileTargetExpression"], 'env!("FLOE_TARGET_TRIPLE")')
        self.assertTrue(binding["applied"])
        self.assertEqual(set(identity["files"]), set(TEST_IDENTITY_FILES))
        for rel in TEST_IDENTITY_FILES:
            entry = identity["files"][rel]
            self.assertEqual(entry["stagedSha256"], sha256_file(staged / "adapter" / rel))
            self.assertEqual(entry["trackedSha256"],
                             sha256_file(ENGINE_DIR / "adapter" / rel))
            self.assertTrue(entry["changed"], rel)
            self.assertNotEqual(entry["stagedSha256"], entry["trackedSha256"], rel)

    def test_only_the_pinned_identity_lines_moved(self):
        receipt = self.stage()
        staged_adapter = self.out / "engines" / "impeccable" / "adapter"
        tracked_adapter = ENGINE_DIR / "adapter"
        pairs = rust_test_identity_pairs(tracked_published_identity())
        for rel in TEST_IDENTITY_FILES:
            tracked = (tracked_adapter / rel).read_bytes().decode("utf-8")
            expected = tracked
            for pinned, projected, occurrences in pairs[rel]:
                self.assertEqual(expected.count(pinned), occurrences,
                                 f"{rel}: the pinned test shape changed: {pinned!r}")
                expected = expected.replace(pinned, projected)
            staged = (staged_adapter / rel).read_bytes().decode("utf-8")
            self.assertEqual(staged, expected,
                             f"{rel}: only the pinned identity lines may move")
            # exact reverse projection restores the tracked test byte: no
            # non-projected byte moved in the staged TEMP copy
            restored = staged
            for change in reversed(receipt["stagedTestIdentity"]["changes"]):
                if change["file"] == rel and change["pinned"] != change["projected"]:
                    restored = restored.replace(change["projected"], change["pinned"])
            self.assertEqual(restored, tracked,
                             f"{rel}: reverse projection must restore the tracked byte")
        # every test function survives: no assertion was skipped, weakened or
        # removed by either projection
        for rel, expected_tests in (("tests/contract_embedded.rs", 11),
                                    ("tests/snapshot_scan.rs", 27),
                                    ("tests/rule_pass_limiter.rs", 10)):
            text = (staged_adapter / rel).read_text(encoding="utf-8")
            self.assertEqual(text.count("#[test]"), expected_tests, rel)

    def test_published_identity_staging_is_byte_identical_for_the_tests(self):
        tracked_copy = self.tmp / "tracked-lock.json"
        tracked_copy.write_bytes(TRACKED_LOCK.read_bytes())
        receipt = self.stage(tracked_copy)
        staged_adapter = self.out / "engines" / "impeccable" / "adapter"
        for rel in TEST_IDENTITY_FILES:
            self.assertEqual(sha256_file(staged_adapter / rel),
                             sha256_file(ENGINE_DIR / "adapter" / rel), rel)
        identity = receipt["stagedTestIdentity"]
        changes = identity["changes"]
        self.assertEqual(len(changes), 16)
        self.assertTrue(all(change["pinned"] == change["projected"] for change in changes))
        self.assertTrue(all(not change["changed"] for change in changes))
        self.assertTrue(all(not entry["changed"] for entry in identity["files"].values()))
        self.assertFalse(identity["hostTargetBinding"]["applied"],
                         "the host target binding is candidate-only")
        self.assertEqual(identity["hostTargetBinding"]["archivedTarget"],
                         archived_test_target())
        self.assertEqual(receipt["trackedContractSha256"], receipt["stagedContractSha256"])

    def test_unexpected_trusted_test_shape_fails_closed_without_writes(self):
        stager = load_module(STAGE_PY, "candidate_identity_stager")
        identity = {"commit": CANDIDATE["commit"], "tree": CANDIDATE["tree"],
                    "version": CANDIDATE["version"], "engineId": f"impeccable-{COMPONENT}"}
        _, adapter_version, expected = stager.derive_component_identity(ENGINE_DIR, identity)
        published = stager.published_test_identity(ENGINE_DIR, adapter_version)
        for label, rel, old, new in (
            ("identity literal",
             "tests/contract_embedded.rs", b'"0.1.17"', b'"0.1.16"'),
            ("host-target anchor",
             "tests/rule_pass_limiter.rs",
             b"        let observed = normalize(doc(&result).clone());",
             b"        let observed = normalize(doc(&result).clone()); // moved"),
        ):
            with self.subTest(label):
                adapter = self.tmp / label.replace(" ", "-")
                for name in TEST_IDENTITY_FILES:
                    target = adapter / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes((ENGINE_DIR / "adapter" / name).read_bytes())
                mutated = adapter / rel
                data = mutated.read_bytes()
                self.assertIn(old, data)
                mutated.write_bytes(data.replace(old, new, 1))
                before = {name: sha256_file(adapter / name) for name in TEST_IDENTITY_FILES}
                with self.assertRaises(ValueError):
                    stager.project_staged_test_identity(ENGINE_DIR / "adapter", adapter,
                                                        published, identity, expected)
                self.assertEqual(before, {name: sha256_file(adapter / name)
                                          for name in TEST_IDENTITY_FILES},
                                 "a refused trusted-test shape must not write any test bytes")

    def test_recorded_target_disagreement_or_unsafe_target_fails_closed(self):
        stager = load_module(STAGE_PY, "candidate_identity_stager")
        good = json.loads((ENGINE_DIR / "adapter" / "tests" / "data"
                           / "expected-large-shape.v1.json").read_text(encoding="utf-8"))
        second = json.loads((ENGINE_DIR / "adapter" / "tests" / "data"
                             / "expected-admission-exactcap.v1.json").read_text(encoding="utf-8"))
        for label, target, other_target in (
            ("disagreement", "aarch64-apple-darwin", "x86_64-unknown-linux-gnu"),
            ("unsafe literal", 'x86_64")); panic!("', "x86_64\")); panic!(\""),
            ("build fallback", "unknown-target", "unknown-target"),
        ):
            with self.subTest(label):
                adapter = self.tmp / ("target-" + label.replace(" ", "-"))
                (adapter / "tests" / "data").mkdir(parents=True)
                for name, base, value in (
                    ("expected-large-shape.v1.json", good, target),
                    ("expected-admission-exactcap.v1.json", second, other_target),
                ):
                    doc = json.loads(json.dumps(base))
                    doc["engine"]["targetTriple"] = value
                    (adapter / "tests" / "data" / name).write_text(
                        json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
                with self.assertRaises(ValueError):
                    stager.archived_test_target(adapter)

    def test_generated_rust_harness_keeps_compile_target_guards(self):
        """Static anchor proof (no Cargo/rustfmt on this host): both guards are
        independent of the projection, the archived literal is the trusted
        value, and the exact comparison field is retained. The delimiter count
        is a coarse sanity check only; the actual compile is Root GHA."""
        receipt = self.stage()
        staged = self.out / "engines" / "impeccable" / "adapter" / "tests" / "rule_pass_limiter.rs"
        text = staged.read_text(encoding="utf-8")
        self.assertIn('doc(&result)["engine"]["targetTriple"],\n'
                      '            json!(env!("FLOE_TARGET_TRIPLE")),', text)
        self.assertIn('golden["engine"]["targetTriple"],\n'
                      f'            json!("{archived_test_target()}"),', text)
        self.assertIn('golden["engine"]["targetTriple"] = json!(env!("FLOE_TARGET_TRIPLE"));',
                      text)
        self.assertEqual(receipt["stagedTestIdentity"]["hostTargetBinding"]["archivedTarget"],
                         archived_test_target())
        # brace/paren sanity on the generated Rust file (rustfmt is absent from
        # this host's installed toolchain; the actual compile stays Root GHA)
        for opener, closer in (("{", "}"), ("(", ")"), ("[", "]")):
            self.assertEqual(text.count(opener), text.count(closer), (opener, closer))

    def test_noncanonical_published_contract_fails_closed(self):
        stager = load_module(STAGE_PY, "candidate_identity_stager")
        fake = self.tmp / "fake-engine"
        (fake / "contract").mkdir(parents=True)
        doc = json.loads(TRACKED_CONTRACT.read_text(encoding="utf-8"))
        doc["engine"]["engineId"] = (f"impeccable-{doc['engine']['upstreamEngineVersion']}"
                                     "+floe.9.9.9")
        (fake / "contract" / "snapshot-contract.v1.json").write_text(
            json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            stager.published_test_identity(fake, ADAPTER_VERSION)

    def test_malformed_candidate_lock_fails_closed_before_staging(self):
        for label, mutate in (
            ("bad commit", lambda d: d["upstream"].update(commit="not-a-sha")),
            ("bad version", lambda d: d["upstream"].update(engineVersion="0.1")),
            ("engineId disagrees",
             lambda d: d.update(engineId=f"impeccable-{CANDIDATE['version']}+floe.9.9.9")),
        ):
            with self.subTest(label):
                doc = candidate_lock_doc()
                mutate(doc)
                bad = self.tmp / (label.replace(" ", "-") + ".json")
                bad.write_text(json.dumps(doc), encoding="utf-8")
                out = self.out / label.replace(" ", "-")
                proc = subprocess.run(
                    [sys.executable, str(STAGE_PY), "--engine-dir", str(ENGINE_DIR),
                     "--candidate-lock", str(bad), "--out", str(out)],
                    capture_output=True, text=True, env=BASE_ENV, timeout=120)
                self.assertEqual(proc.returncode, 2, f"{label}: {proc.stdout}{proc.stderr}")
                self.assertFalse(json.loads(proc.stdout)["ok"])
                self.assertFalse(out.exists(), f"{label}: a refused candidate must stage nothing")


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
