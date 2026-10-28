#!/usr/bin/env python3
"""Tests for workflows/tools/verify_published_baseline.py — the fail-closed
binding that makes the honest GHA comparison boundary real:

  * --verify-binary binds the tracked dist artifact for the tracked lock's
    published identity to the official lock digests, SHA256SUMS and the
    tracked contract identity;
  * --verify-record refuses any recorded tree that was not produced by that
    exact digest-verified binary under a clean emulated-riscv64 behaviour
    matrix with the published identity — candidate output can never be
    blessed as a baseline.

Read-only against the tracked tree; all synthesis happens in temp roots.

The same module covers the routed comparison gate (`TestBaselineRouting`):
the frozen committed goldens may be the reference only while their recorded
identity equals that digest-bound published baseline; otherwise the workflow
must run the verified published-baseline regression instead — exactly one
strict comparator, never none and never a self-blessed one.

  cd floe-skill-hub && python3 -m unittest \
      engines.impeccable.workflows.tools.tests.test_published_baseline
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS_DIR = HERE.parent
ENGINE_DIR = TOOLS_DIR.parent.parent
HUB_ROOT = ENGINE_DIR.parent.parent
BASELINE_PY = TOOLS_DIR / "verify_published_baseline.py"
TRACKED_LOCK = ENGINE_DIR / "ENGINE-LOCK.json"
TRACKED_CONTRACT_DIR = ENGINE_DIR / "contract"
TRACKED_GOLDENS = TRACKED_CONTRACT_DIR / "expected" / "riscv64-docker"

LOCK = json.loads(TRACKED_LOCK.read_text(encoding="utf-8"))
ENGINE_ID = LOCK["engineId"]
ARTIFACT_SHA = LOCK["component"]["artifactSha256"]
ARTIFACT_BYTES = LOCK["component"]["artifactBytes"]
ADAPTER = LOCK["floe"]["adapterVersion"]
UPSTREAM = LOCK["upstream"]

BASE_ENV = {
    "PATH": "/usr/bin:/bin",
    "HOME": os.environ.get("HOME", "/tmp"),
    "GIT_CONFIG_NOSYSTEM": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(BASELINE_PY), *args],
                          capture_output=True, text=True, env=BASE_ENV, timeout=180)


def published_engine_block(**over) -> dict:
    block = {
        "binary": "floe-impeccable",
        "upstreamProject": "pbakaus/impeccable",
        "upstreamEngineVersion": UPSTREAM["engineVersion"],
        "upstreamCommit": UPSTREAM["commit"],
        "upstreamTree": UPSTREAM["tree"],
        "pinAuthority": UPSTREAM["pinAuthority"],
        "floeAdapterVersion": ADAPTER,
        "engineId": ENGINE_ID,
        "targetTriple": "riscv64gc-unknown-linux-musl",
        "abi": "static ELF, no dynamic loader dependency",
        "adapterCrateVersion": ADAPTER,
        "contractTargetTriple": "riscv64gc-unknown-linux-musl",
        "runtimeExecution": "riscv64-linux",
    }
    block.update(over)
    return block


class ToolCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="impeccable-baseline-"))
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        self._record_seq = iter(range(1_000_000))

    def binary_receipt(self, engine_dir=ENGINE_DIR, lock=TRACKED_LOCK):
        receipt = self.tmp / "receipt.json"
        proc = run(["--verify-binary", "--engine-dir", str(engine_dir),
                    "--lock", str(lock), "--out", str(receipt)])
        return proc, receipt

    def write_record(self, *, cases_docs=None, manifest_over=None,
                     doc_over=None, engine_sha=ARTIFACT_SHA, drop_cases=(),
                     label=f"published-baseline-{ENGINE_ID}",
                     runner="docker linux/riscv64 alpine:3.20 (published baseline re-run)") -> Path:
        """Synthesise a recorded baseline tree exactly in the export_expected
        shape, built from the REAL committed case list so coverage is tested
        against the true matrix."""
        record = self.tmp / f"expected-baseline-{next(self._record_seq)}" / "riscv64-docker"
        record.mkdir(parents=True)
        tracked = json.loads((TRACKED_GOLDENS / "MANIFEST.json").read_text(encoding="utf-8"))
        manifest = {
            "kind": "engine-observed goldens",
            "label": label,
            "normalization": "budget.elapsedMs and error.detail.elapsedMs normalized to 0; "
                             "facts file sources reduced to basenames",
            "observedOn": {"uname": ["Linux", "riscv64", "6.8.0-117-generic"],
                           "runner": runner, "hostPlatform": "Ubuntu-24.04-x86_64"},
            "engine": {"binary": "floe-impeccable", "sha256": engine_sha},
            "verification": {"checksTotal": 74, "checksPassed": 74, "failures": [],
                             "parity": {"cases": 12, "byteIdentical": 12},
                             "runner": runner},
            "cases": {},
        }
        for over in (manifest_over or []):
            node = manifest
            parts = over[0].split(".")
            for p in parts[:-1]:
                node = node[p]
            node[parts[-1]] = over[1]
        golden_manifest_cases = tracked["cases"]
        for name, gentry in golden_manifest_cases.items():
            if name in drop_cases:
                continue
            if cases_docs is not None and name not in cases_docs:
                continue
            base = json.loads((TRACKED_GOLDENS / gentry["file"]).read_text(encoding="utf-8"))
            base["engine"] = published_engine_block(**(doc_over or {}))
            if cases_docs and name in cases_docs:
                base.update(cases_docs[name])
            text = json.dumps(base, indent=2, ensure_ascii=False) + "\n"
            file_name = f"{name}.result.v1.json"
            (record / file_name).write_text(text, encoding="utf-8")
            manifest["cases"][name] = {"file": file_name, "exit": gentry.get("exit"),
                                       "sha256": sha256_bytes(text.encode("utf-8"))}
        (record / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                              encoding="utf-8")
        return record

    def verify_record(self, record: Path, receipt: Path):
        out = self.tmp / "record-receipt.json"
        proc = run(["--verify-record", "--engine-dir", str(ENGINE_DIR),
                    "--lock", str(TRACKED_LOCK), "--receipt", str(receipt),
                    "--record", str(record), "--out", str(out)])
        return proc, out


class TestVerifyBinary(ToolCase):
    def test_real_tracked_baseline_verifies(self):
        proc, receipt = self.binary_receipt()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        data = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertTrue(data["ok"])
        self.assertEqual(data["engineId"], ENGINE_ID)
        self.assertEqual(data["componentVersion"], f"0.1.17+floe.{ADAPTER}")
        self.assertEqual(data["sha256"], ARTIFACT_SHA)
        self.assertEqual(data["bytes"], ARTIFACT_BYTES)
        self.assertEqual(data["upstream"]["commit"], UPSTREAM["commit"])

    def test_tampered_lock_digest_fails_closed(self):
        lock = json.loads(TRACKED_LOCK.read_text(encoding="utf-8"))
        lock["component"]["artifactSha256"] = "0" * 64
        path = self.tmp / "lock.json"
        path.write_text(json.dumps(lock), encoding="utf-8")
        proc, _ = self.binary_receipt(lock=path)
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("artifactSha256", proc.stdout)

    def test_noncanonical_lock_identity_fails_closed(self):
        lock = json.loads(TRACKED_LOCK.read_text(encoding="utf-8"))
        lock["engineId"] = "impeccable-0.1.17+floe.1.0.0"
        path = self.tmp / "lock.json"
        path.write_text(json.dumps(lock), encoding="utf-8")
        proc, _ = self.binary_receipt(lock=path)
        self.assertEqual(proc.returncode, 2, proc.stdout)

    def test_missing_dist_artifact_fails_closed(self):
        fake_engine = self.tmp / "engine-dir"
        (fake_engine / "contract").mkdir(parents=True)
        shutil.copyfile(TRACKED_CONTRACT_DIR / "snapshot-contract.v1.json",
                        fake_engine / "contract" / "snapshot-contract.v1.json")
        proc, _ = self.binary_receipt(engine_dir=fake_engine)
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("published baseline artifact is missing", proc.stdout + proc.stderr)

    def test_sha256sums_drift_fails_closed(self):
        fake_engine = self.tmp / "engine-dir"
        shutil.copytree(ENGINE_DIR / "dist" / ENGINE_ID,
                        fake_engine / "dist" / ENGINE_ID)
        shutil.copytree(TRACKED_CONTRACT_DIR, fake_engine / "contract",
                        ignore=shutil.ignore_patterns("expected"))
        notice = (fake_engine / "dist" / ENGINE_ID / "riscv64gc-unknown-linux-musl"
                  / "NOTICE-impeccable.md")
        notice.write_text(notice.read_text(encoding="utf-8") + "\nappended\n", encoding="utf-8")
        proc, _ = self.binary_receipt(engine_dir=fake_engine)
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("SHA256SUMS", proc.stdout)


class TestVerifyRecord(ToolCase):
    def test_clean_published_record_passes(self):
        proc, receipt = self.binary_receipt()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        record = self.write_record()
        vproc, vout = self.verify_record(record, receipt)
        self.assertEqual(vproc.returncode, 0, vproc.stdout + vproc.stderr)
        data = json.loads(vout.read_text(encoding="utf-8"))
        self.assertTrue(data["ok"])
        self.assertEqual(data["cases"], data["trackedGoldenCasesCovered"])

    def test_candidate_identity_record_is_refused(self):
        # "bless the candidate output as the baseline" must fail closed.
        proc, receipt = self.binary_receipt()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        record = self.write_record(doc_over={"engineId": f"impeccable-0.1.18+floe.{ADAPTER}"})
        vproc, _ = self.verify_record(record, receipt)
        self.assertEqual(vproc.returncode, 2, vproc.stdout)
        self.assertIn("engineId", vproc.stdout)

    def test_candidate_binary_sha_record_is_refused(self):
        proc, receipt = self.binary_receipt()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        record = self.write_record(engine_sha="b" * 64)
        vproc, _ = self.verify_record(record, receipt)
        self.assertEqual(vproc.returncode, 2, vproc.stdout)
        self.assertIn("digest-verified published binary", vproc.stdout)

    def test_adapter_field_drift_is_refused(self):
        proc, receipt = self.binary_receipt()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for over in ({"floeAdapterVersion": "1.0.0"}, {"adapterCrateVersion": "1.0.0"},
                     {"upstreamCommit": "f" * 40}, {"targetTriple": "aarch64-apple-darwin"},
                     {"runtimeExecution": "host-comparison-build"}):
            with self.subTest(**over):
                record = self.write_record(doc_over=over)
                vproc, _ = self.verify_record(record, receipt)
                self.assertEqual(vproc.returncode, 2, vproc.stdout)

    def test_host_observed_record_is_refused(self):
        proc, receipt = self.binary_receipt()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        record = self.write_record(runner="local host, aarch64-apple-darwin dev build")
        vproc, _ = self.verify_record(record, receipt)
        self.assertEqual(vproc.returncode, 2, vproc.stdout)
        self.assertIn("riscv64", vproc.stdout)

    def test_dirty_matrix_record_is_refused(self):
        proc, receipt = self.binary_receipt()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for over in ([("verification.failures", ["positive-round2: exit code"])],
                     [("verification.checksPassed", 70)],
                     [("verification.parity.byteIdentical", 11)]):
            with self.subTest(field=over[0]):
                record = self.write_record(manifest_over=list(over))
                vproc, _ = self.verify_record(record, receipt)
                self.assertEqual(vproc.returncode, 2, vproc.stdout)

    def test_incomplete_case_coverage_is_refused(self):
        proc, receipt = self.binary_receipt()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        tracked = json.loads((TRACKED_GOLDENS / "MANIFEST.json").read_text(encoding="utf-8"))
        one_case = sorted(tracked["cases"])[0]
        record = self.write_record(drop_cases=[one_case])
        vproc, _ = self.verify_record(record, receipt)
        self.assertEqual(vproc.returncode, 2, vproc.stdout)
        self.assertIn(one_case, vproc.stdout)

    def test_drifted_case_file_is_refused(self):
        proc, receipt = self.binary_receipt()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        record = self.write_record()
        first = sorted((record / "MANIFEST.json").read_text(encoding="utf-8") and
                       json.loads((record / "MANIFEST.json").read_text(encoding="utf-8"))["cases"])[0]
        file_name = json.loads((record / "MANIFEST.json").read_text(encoding="utf-8"))["cases"][first]["file"]
        target = record / file_name
        target.write_text(target.read_text(encoding="utf-8").replace('"verdict"', '"verdictx"'),
                          encoding="utf-8")
        vproc, _ = self.verify_record(record, receipt)
        self.assertEqual(vproc.returncode, 2, vproc.stdout)
        self.assertIn("drifted", vproc.stdout)

    def test_receipt_pointing_at_swapped_binary_is_refused(self):
        proc, receipt = self.binary_receipt()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        data = json.loads(receipt.read_text(encoding="utf-8"))
        fake = self.tmp / "floe-impeccable-fake"
        fake.write_bytes(b"not the baseline")
        data["binaryPath"] = str(fake)
        receipt.write_text(json.dumps(data), encoding="utf-8")
        record = self.write_record()
        vproc, _ = self.verify_record(record, receipt)
        self.assertEqual(vproc.returncode, 2, vproc.stdout)
        self.assertIn("drifted", vproc.stdout)

# ---------------------------------------------------------------------------
# Routed comparison gate
# ---------------------------------------------------------------------------
# The updater must run exactly ONE strict Needs/facts comparator, selected by
# the authenticated identity of the digest-bound published baseline:
#
#   historical  the frozen committed goldens, only when their recorded binary
#               digest AND every recorded engine identity field equal the
#               published baseline (a matching, immutable reference);
#   published   otherwise a fresh re-run of the digest-bound published
#               baseline, recorded in TEMP and bound by --verify-record.
#
# A forged receipt, a malformed or tampered frozen tree, or an identity drift
# under a matching manifest digest must never select the historical route, must
# never crash into a bare traceback, and must never leave both comparators
# unselected. The frozen 1.0.0-era goldens are read-only here.

WORKFLOW_YML = TOOLS_DIR.parent / "impeccable-engine-updater.yml"
ROUTE_STEP = "Route the Needs/facts comparison by authenticated baseline identity"
ROUTE_SUMMARY_STEP = "Record the Needs/facts comparison route"
BASELINE_BINARY_STEP = "Verify the published baseline binary against the official lock"
PUBLISHED_WORKTREE_STEP = ("Check out the baseline's own pinned tree "
                           "(temp worktree of the existing clone)")
PUBLISHED_MATRIX_STEP = "Behaviour matrix on the published baseline (emulated riscv64)"
PUBLISHED_RECORD_STEP = ("Record the versioned baseline results "
                         "(temp only; never committed, never blessed)")
PUBLISHED_BIND_STEP = "Bind the recorded baseline tree to the official lock and binary"
PUBLISHED_COMPARATOR = "Needs/facts fixpoint regression against the published baseline"
HISTORICAL_COMPARATOR = "Needs/facts fixpoint regression against the recorded goldens"
PUBLISHED_CONDITION = "steps.route.outputs.baseline_route == 'published'"
HISTORICAL_CONDITION = "steps.route.outputs.baseline_route == 'historical'"


def workflow_lines() -> list[str]:
    return WORKFLOW_YML.read_text(encoding="utf-8").splitlines()


def workflow_step(name: str) -> list[str]:
    """The lines of the step whose `- name:` is exactly ``name``."""
    lines = workflow_lines()
    try:
        start = lines.index(f"      - name: {name}")
    except ValueError:
        raise AssertionError(f"workflow step not found in {WORKFLOW_YML}: {name}") from None
    for end in range(start + 1, len(lines)):
        line = lines[end]
        if line.startswith("      - ") or (
                line.startswith("  ") and not line.startswith("    ") and line.strip()):
            return lines[start:end]
    return lines[start:]


def step_condition(name: str):
    for line in workflow_step(name):
        if line.startswith("        if: "):
            return line[len("        if: "):].strip()
    return None


def route_script() -> str:
    """The exact python heredoc the workflow executes for the routing decision."""
    body, inside = [], False
    for line in workflow_step(ROUTE_STEP):
        if not inside:
            if line.strip() == "python3 - <<'PY' >> \"$GITHUB_OUTPUT\"":
                inside = True
            continue
        if line == "          PY":
            return "\n".join(body) + "\n"
        if line == "":
            body.append("")
            continue
        if not line.startswith("          "):
            raise AssertionError(f"routing heredoc line is not uniformly indented: {line!r}")
        body.append(line[10:])
    raise AssertionError("routing heredoc is not terminated")


def compare_invocations(step_lines: list[str]) -> list[str]:
    return [line for line in step_lines if "compare_expected.py" in line]


def step_run_block(name: str) -> str:
    """The exact shell script a step's block `run: |` executes."""
    lines = workflow_step(name)
    try:
        start = lines.index("        run: |")
    except ValueError:
        raise AssertionError(f"{name}: step carries no block run: script") from None
    body = []
    for line in lines[start + 1:]:
        if line.strip() and not line.startswith("          "):
            break
        body.append(line[10:] if line.strip() else "")
    return "\n".join(body).rstrip("\n") + "\n"


class TestBaselineRouting(ToolCase):
    def setUp(self):
        super().setUp()
        self.runner_temp = self.tmp / "runner"
        (self.runner_temp / "logs").mkdir(parents=True)
        self._seq = iter(range(1_000_000))

    # -- fixtures ---------------------------------------------------------
    def real_receipt(self) -> dict:
        proc, path = self.binary_receipt()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return json.loads(path.read_text(encoding="utf-8"))

    def install_receipt(self, data: dict) -> None:
        (self.runner_temp / "logs" / "baseline-binary-verify.json").write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def fake_engine_dir(self, *, engine_sha=None, doc_over=None) -> Path:
        """An ENGINE_DIR whose committed goldens were (synthetically) re-recorded
        from the digest-bound published baseline."""
        root = self.tmp / f"engine-{next(self._seq)}"
        goldens = root / "contract" / "expected" / "riscv64-docker"
        goldens.mkdir(parents=True)
        (root / "ENGINE-LOCK.json").write_text(TRACKED_LOCK.read_text(encoding="utf-8"),
                                               encoding="utf-8")
        manifest = {
            "kind": "engine-observed goldens",
            "label": "riscv64-docker",
            "engine": {"binary": "floe-impeccable",
                       "sha256": engine_sha if engine_sha is not None else ARTIFACT_SHA},
            "cases": {},
        }
        for name in ("sample-clean", "sample-findings"):
            doc = {"engine": published_engine_block(**(doc_over or {})), "verdict": "clean"}
            raw = (json.dumps(doc, indent=2) + "\n").encode("utf-8")
            file_name = f"{name}.result.v1.json"
            (goldens / file_name).write_bytes(raw)
            manifest["cases"][name] = {"file": file_name, "sha256": sha256_bytes(raw)}
        (goldens / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                               encoding="utf-8")
        return root

    def rewrite_manifest(self, engine_dir: Path, updates: dict) -> None:
        path = engine_dir / "contract" / "expected" / "riscv64-docker" / "MANIFEST.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest.update(updates)
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    def run_route(self, engine_dir: Path):
        script = self.tmp / f"route-{next(self._seq)}.py"
        script.write_text(route_script(), encoding="utf-8")
        env = dict(BASE_ENV, RUNNER_TEMP=str(self.runner_temp), ENGINE_DIR=str(engine_dir))
        proc = subprocess.run([sys.executable, str(script)], capture_output=True,
                              text=True, env=env, timeout=120)
        outputs = {}
        for line in proc.stdout.splitlines():
            key, sep, value = line.partition("=")
            if sep:
                outputs[key] = value
        return proc, outputs

    # -- the real, current state -----------------------------------------
    def test_real_published_baseline_against_frozen_goldens_routes_to_published(self):
        self.install_receipt(self.real_receipt())
        proc, out = self.run_route(ENGINE_DIR)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(out["baseline_route"], "published")
        self.assertIn("different binary digest", out["baseline_route_reason"])
        self.assertIn(ARTIFACT_SHA, proc.stderr)
        self.assertIn("af8795bf", proc.stderr)
        self.assertNotIn(ARTIFACT_SHA, out.values())

    def test_identity_matched_frozen_goldens_route_to_historical(self):
        self.install_receipt(self.real_receipt())
        proc, out = self.run_route(self.fake_engine_dir())
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(out["baseline_route"], "historical")
        self.assertIn("digest-bound published baseline", out["baseline_route_reason"])

    def test_recorded_identity_drift_routes_to_published(self):
        self.install_receipt(self.real_receipt())
        for over in ({"floeAdapterVersion": "1.0.0"},
                     {"adapterCrateVersion": "1.0.0"},
                     {"engineId": "impeccable-0.1.17+floe.1.0.0"},
                     {"upstreamEngineVersion": "0.1.16"},
                     {"upstreamCommit": "f" * 40},
                     {"upstreamTree": "e" * 40}):
            with self.subTest(**over):
                proc, out = self.run_route(self.fake_engine_dir(doc_over=over))
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                self.assertEqual(out["baseline_route"], "published")
                field = next(iter(over))
                self.assertIn(f"engine.{field}", out["baseline_route_reason"])

    def test_matching_digest_alone_never_blesses_a_foreign_identity(self):
        # a manifest digest that matches cannot mask drifted recorded identity:
        # the declared engine identity fields are compared as well.
        self.install_receipt(self.real_receipt())
        proc, out = self.run_route(
            self.fake_engine_dir(doc_over={"floeAdapterVersion": "1.0.0"}))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(out["baseline_route"], "published")

    # -- fail-closed boundaries -------------------------------------------
    def test_forged_or_stale_receipt_fails_closed(self):
        real = self.real_receipt()
        mutations = [
            ("ok", False),
            ("mode", "verify-record"),
            ("engineId", "impeccable-0.1.17+floe.1.0.0"),
            ("engineId", "impeccable-0.1.18+floe.1.1.1"),
            ("sha256", "0" * 64),
            ("sha256", "not-a-digest"),
            ("adapterVersion", "1.0.0"),
            ("upstream.commit", "f" * 40),
            ("upstream.tree", "e" * 40),
            ("upstream.engineVersion", "0.1.16"),
        ]
        for key_path, value in mutations:
            with self.subTest(field=key_path, value=value):
                data = json.loads(json.dumps(real))
                node = data
                parts = key_path.split(".")
                for part in parts[:-1]:
                    node = node[part]
                node[parts[-1]] = value
                self.install_receipt(data)
                proc, out = self.run_route(ENGINE_DIR)
                self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
                self.assertIn("refusing to route", proc.stderr)
                self.assertEqual(out, {})
        (self.runner_temp / "logs" / "baseline-binary-verify.json").unlink()
        proc, out = self.run_route(ENGINE_DIR)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("receipt", proc.stderr)
        self.assertEqual(out, {})

    def test_missing_or_tampered_frozen_tree_fails_closed(self):
        self.install_receipt(self.real_receipt())
        goldens = ENGINE_DIR / "contract" / "expected" / "riscv64-docker"
        cases = []

        root = self.fake_engine_dir()
        (root / "contract" / "expected" / "riscv64-docker" / "MANIFEST.json").unlink()
        cases.append(("missing-manifest", root))

        root = self.fake_engine_dir()
        self.rewrite_manifest(root, {"kind": "something else"})
        cases.append(("wrong-kind", root))

        root = self.fake_engine_dir()
        self.rewrite_manifest(root, {"cases": {}})
        cases.append(("empty-cases", root))

        root = self.fake_engine_dir()
        self.rewrite_manifest(root, {"engine": {"sha256": "zz" * 32}})
        cases.append(("non-hex-digest", root))

        root = self.fake_engine_dir()
        (root / "contract" / "expected" / "riscv64-docker"
         / "sample-clean.result.v1.json").unlink()
        cases.append(("missing-case-file", root))

        root = self.fake_engine_dir()
        target = (root / "contract" / "expected" / "riscv64-docker"
                  / "sample-clean.result.v1.json")
        target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        cases.append(("drifted-case-file", root))

        root = self.fake_engine_dir()
        target = (root / "contract" / "expected" / "riscv64-docker"
                  / "sample-clean.result.v1.json")
        target.write_text("{not json\n", encoding="utf-8")
        cases.append(("tampered-case-file", root))

        for label, engine in cases:
            with self.subTest(case=label):
                proc, out = self.run_route(engine)
                self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
                self.assertIn("refusing to route", proc.stderr)
                self.assertEqual(out, {})

    def test_route_decision_is_read_only_on_the_frozen_tree(self):
        tracked = ENGINE_DIR / "contract" / "expected" / "riscv64-docker"

        def digest_tree(root: Path) -> dict:
            return {str(path.relative_to(root)): sha256_bytes(path.read_bytes())
                    for path in sorted(root.rglob("*")) if path.is_file()}

        before = digest_tree(tracked)
        self.assertEqual(len(before), 22, "21 cases + MANIFEST expected")
        self.install_receipt(self.real_receipt())
        proc, out = self.run_route(ENGINE_DIR)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(digest_tree(tracked), before)

    # -- workflow wiring ---------------------------------------------------
    def test_wiring_selects_exactly_one_strict_comparator_per_route(self):
        self.assertIsNone(step_condition(BASELINE_BINARY_STEP))
        self.assertIsNone(step_condition(ROUTE_STEP))
        self.assertIsNone(step_condition(ROUTE_SUMMARY_STEP))

        for name in (PUBLISHED_WORKTREE_STEP, PUBLISHED_MATRIX_STEP,
                     PUBLISHED_RECORD_STEP, PUBLISHED_BIND_STEP, PUBLISHED_COMPARATOR):
            with self.subTest(step=name):
                self.assertEqual(step_condition(name), PUBLISHED_CONDITION)
        self.assertEqual(step_condition(HISTORICAL_COMPARATOR), HISTORICAL_CONDITION)

        selected = {"historical": [], "published": []}
        for name in (PUBLISHED_COMPARATOR, HISTORICAL_COMPARATOR):
            condition = step_condition(name) or ""
            if condition == PUBLISHED_CONDITION:
                selected["published"] += compare_invocations(workflow_step(name))
            elif condition == HISTORICAL_CONDITION:
                selected["historical"] += compare_invocations(workflow_step(name))
            else:
                self.fail(f"{name}: comparator is not routed by the baseline identity")
        self.assertEqual(len(selected["historical"]), 1)
        self.assertEqual(len(selected["published"]), 1)

    def test_historical_comparator_still_targets_the_frozen_tracked_tree(self):
        text = "\n".join(workflow_step(HISTORICAL_COMPARATOR))
        self.assertIn('--expected "$ENGINE_DIR/contract/expected/riscv64-docker"', text)
        for flag in ("--engine", "--contract", "--expected", "--out",
                     "--candidate-lock", "--build-tree", "--adapter-data"):
            self.assertIn(flag, text)
        published = "\n".join(workflow_step(PUBLISHED_COMPARATOR))
        self.assertIn('--expected "$RUNNER_TEMP/expected-baseline/riscv64-docker"', published)
        self.assertIn('--candidate-lock "$RUNNER_TEMP/candidate-lock/ENGINE-LOCK.json"',
                      published)

    def test_workflow_run_block_emits_parseable_github_output(self):
        # the exact YAML run block (heredoc plus the shell redirect) is
        # exercised through bash, not a re-implementation of it
        interpreter = shutil.which("python3", path=BASE_ENV["PATH"])
        if interpreter is None:
            self.skipTest("host has no python3 on the hermetic PATH")
        self.install_receipt(self.real_receipt())
        script = self.tmp / "route-step.sh"
        script.write_text(step_run_block(ROUTE_STEP), encoding="utf-8")
        out_path = self.tmp / "github-output"
        env = dict(BASE_ENV, RUNNER_TEMP=str(self.runner_temp),
                   ENGINE_DIR=str(ENGINE_DIR), GITHUB_OUTPUT=str(out_path))
        proc = subprocess.run(["bash", str(script)], capture_output=True, text=True,
                              env=env, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        lines = out_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2, lines)
        self.assertRegex(lines[0], r"^baseline_route=(historical|published)$")
        self.assertRegex(lines[1], r"^baseline_route_reason=[ -~]{1,240}$")
        self.assertIn(ARTIFACT_SHA, proc.stderr)

    def test_routing_outputs_are_shape_bounded(self):
        script = route_script()
        self.assertNotIn("${{", script)
        self.assertIn('re.fullmatch(r"historical|published", route)', script)
        self.assertIn('re.fullmatch(r"[ -~]{1,240}", reason)', script)
        self.install_receipt(self.real_receipt())
        proc, out = self.run_route(ENGINE_DIR)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(sorted(out), ["baseline_route", "baseline_route_reason"])
        self.assertRegex(out["baseline_route"], r"^(historical|published)$")
        self.assertRegex(out["baseline_route_reason"], r"^[ -~]{1,240}$")


class TestRealGoldenDiagnosticsIdentity(unittest.TestCase):
    """The tracked riscv64 matrix mixes full result documents — whose
    diagnostics block mirrors `engine.upstreamCommit` / `engineVersion` — with
    early refusals that carry only `diagnostics.strictSchema`. A legitimate
    candidate bump moves six authenticated identity values on the former and
    four on the latter. A presence disagreement is structural drift and stays
    in the strict diff: it is never ignored as an identity change."""

    def setUp(self):
        spec = importlib.util.spec_from_file_location(
            "published_real_compare_expected", TOOLS_DIR / "compare_expected.py")
        self.compare = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.compare)
        self.tmp = Path(tempfile.mkdtemp(prefix="impeccable-real-diagnostics-"))
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        lock = json.loads(TRACKED_LOCK.read_text(encoding="utf-8"))
        lock["upstream"].update({"commit": "b" * 40, "tree": "c" * 40,
                                 "engineVersion": "0.1.18"})
        lock["engineId"] = f"impeccable-0.1.18+floe.{ADAPTER}"
        path = self.tmp / "ENGINE-LOCK.json"
        path.write_text(json.dumps(lock), encoding="utf-8")
        self.lock_identity = self.compare.load_lock_identity(path)

    def doc(self, name: str) -> dict:
        return json.loads((TRACKED_GOLDENS / name).read_text(encoding="utf-8"))

    def candidate_from(self, doc: dict, *, diagnostics: bool = True) -> dict:
        candidate = json.loads(json.dumps(doc))
        candidate["engine"].update({
            "upstreamEngineVersion": "0.1.18",
            "upstreamCommit": "b" * 40,
            "upstreamTree": "c" * 40,
            "engineId": f"impeccable-0.1.18+floe.{ADAPTER}",
        })
        if diagnostics:
            candidate.setdefault("diagnostics", {}).update(
                {"upstreamCommit": "b" * 40, "engineVersion": "0.1.18"})
        return candidate

    def test_full_metadata_case_moves_six_authenticated_fields(self):
        golden = self.doc("positive-round2.result.v1.json")
        entry = self.compare.diff_documents(
            "positive-round2", golden, self.candidate_from(golden),
            self.lock_identity, [])
        self.assertEqual(entry["state"], "identical")
        self.assertEqual(entry["differenceCount"], 0)
        self.assertFalse(entry["structuralDrift"])
        self.assertEqual(entry["diagnosticsIdentityPresence"],
                         {"golden": True, "candidate": True})
        self.assertEqual({c["field"] for c in entry["candidateIdentityChanges"]},
                         set(self.compare.IDENTITY_KEYS))
        self.assertEqual(len(entry["candidateIdentityChanges"]), 6)

    def test_early_refusal_case_moves_only_the_four_engine_fields(self):
        golden = self.doc("budget-bytes.result.v1.json")
        entry = self.compare.diff_documents(
            "budget-bytes", golden, self.candidate_from(golden, diagnostics=False),
            self.lock_identity, [])
        self.assertEqual(entry["state"], "identical")
        self.assertEqual(entry["differenceCount"], 0)
        self.assertFalse(entry["structuralDrift"])
        self.assertEqual(entry["diagnosticsIdentityPresence"],
                         {"golden": False, "candidate": False})
        self.assertEqual({c["field"] for c in entry["candidateIdentityChanges"]},
                         set(self.compare.ENGINE_IDENTITY_KEYS))
        self.assertFalse(any(d["field"].startswith("diagnostics.")
                             for d in entry["differences"]))

    def test_presence_disagreement_is_structural_drift_never_ignored(self):
        full_golden = self.doc("positive-round2.result.v1.json")
        early_golden = self.doc("budget-bytes.result.v1.json")
        # the SAME case, differing only in whether the diagnostics mirror exists
        early_candidate = self.candidate_from(full_golden)
        for key in ("upstreamCommit", "engineVersion"):
            del early_candidate["diagnostics"][key]
        full_candidate = self.candidate_from(early_golden)
        full_candidate["diagnostics"].update(
            {"upstreamCommit": "b" * 40, "engineVersion": "0.1.18"})
        for label, golden, candidate, golden_present in (
            ("full golden / early candidate", full_golden, early_candidate, True),
            ("early golden / full candidate", early_golden, full_candidate, False),
        ):
            with self.subTest(label):
                entry = self.compare.diff_documents(
                    label, golden, candidate, self.lock_identity, [])
                self.assertEqual(entry["state"], "changed-unapproved")
                self.assertTrue(entry["structuralDrift"])
                self.assertEqual(entry["diagnosticsIdentityPresence"],
                                 {"golden": golden_present,
                                  "candidate": not golden_present})
                fields = {d["field"] for d in entry["differences"]}
                self.assertIn("diagnostics.upstreamCommit", fields)
                self.assertIn("diagnostics.engineVersion", fields)

    def test_forged_real_diagnostics_value_fails_closed(self):
        golden = self.doc("positive-round2.result.v1.json")
        forged = self.candidate_from(golden)
        forged["diagnostics"]["engineVersion"] = "9.9.9"
        with self.assertRaises(SystemExit) as ctx:
            self.compare.diff_documents("positive-round2", golden, forged,
                                        self.lock_identity, [])
        self.assertIn("diagnostics identity does not match", str(ctx.exception.code))

    def test_incoherent_real_golden_mirror_fails_closed(self):
        original = self.doc("positive-round2.result.v1.json")
        candidate = self.candidate_from(original)
        for label, mutate in (
            ("commit mismatch",
             lambda d: d["diagnostics"].update(upstreamCommit="f" * 40)),
            ("version mismatch",
             lambda d: d["diagnostics"].update(engineVersion="9.9.9")),
            ("explicit null commit",
             lambda d: d["diagnostics"].update(upstreamCommit=None)),
            ("explicit null version",
             lambda d: d["diagnostics"].update(engineVersion=None)),
        ):
            with self.subTest(label):
                golden = json.loads(json.dumps(original))
                mutate(golden)
                with self.assertRaises(SystemExit) as ctx:
                    self.compare.diff_documents("positive-round2", golden, candidate,
                                                self.lock_identity, [])
                self.assertEqual(
                    json.loads(ctx.exception.code)["error"],
                    "golden result carries an incoherent diagnostics identity mirror")


if __name__ == "__main__":
    unittest.main(verbosity=2)
