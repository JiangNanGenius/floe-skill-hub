#!/usr/bin/env python3
"""Compact synthetic fixtures for the PR-only candidate-reuse tests.

The fixture is deliberately tiny: one candidate ELF-shaped file, one published
baseline ELF-shaped file, three engine files, one contract file, two patches and
the fixed protected paths. It exercises the real verifier's path/mode/digest
checks without duplicating the native build or the full engine tree.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True
TOOLS_DIR = Path(__file__).resolve().parent.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import verify_candidate_reuse as verify  # noqa: E402

CANDIDATE = {
    "engineVersion": "0.1.18",
    "commit": "f29cd24fdecfa5612e35e34c1c868d4a3fca930c",
    "tree": "dd704e4fe593e595f274637332aa1ee35060bace",
    "adapterVersion": "1.1.1",
    "engineId": "impeccable-0.1.18+floe.1.1.1",
    "packageVersion": "4.7.1",
    "commitDate": "2026-10-26T13:18:20-07:00",
    "commitSubject": "Engine 0.1.18",
    "resolvedVia": "local clone",
}
BASE_COMMIT = "4fc2f83e1c8710dba772bfd4523d0efab57737b6"
BASE_TREE = "1363fadfb2141db1cf22b4ba171d6fc4dbf5cd72"
BASE_VERSION = "0.1.17"
BASE_ENGINE_ID = "impeccable-0.1.17+floe.1.1.1"
RUN_ID = 40648648353
BUILD_JOB_ID = 122683359853
ARTIFACT_ID = 12798517598
HEAD_SHA = "53b13b3f21f351ce800212db491e6c24770b039c"

GIT_ENV = {
    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
    "HOME": "/tmp",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_NAME": "fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, env=GIT_ENV)
    if check and proc.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {proc.stderr}")
    return proc


def make_elf(size: int, *, machine: int = 243, e_type: int = 2,
             interp: bool = False, dynamic: bool = False) -> bytes:
    """A tiny ELF header + program headers; never executed, only parsed."""
    ident = b"\x7fELF" + bytes([2, 1, 1, 0]) + b"\x00" * 8
    phdrs = []
    count = 1 + int(interp) + int(dynamic)
    header_size = 64
    phoff = header_size
    phentsize = 56
    body_offset = header_size + count * phentsize
    body = b"\x00" * max(1, size - body_offset)
    phdrs.append(struct.pack("<IIQQQQQQ", 1, 5, body_offset, 0, 0,
                             len(body), len(body), 0x1000))
    if interp:
        phdrs.append(struct.pack("<IIQQQQQQ", 3, 4, body_offset + 8, 0, 0,
                                 8, 8, 1))
    if dynamic:
        phdrs.append(struct.pack("<IIQQQQQQ", 2, 6, body_offset + 16, 0, 0,
                                 16, 16, 8))
    header = ident + struct.pack(
        "<HHIQQQIHHHHHH", e_type, machine, 1, 0, phoff, 0, 0, 64,
        phentsize, count, 0, 0, 0)
    data = header + b"".join(phdrs) + body
    return data[:size].ljust(size, b"\x00")


def make_repo(root: Path) -> dict:
    root = Path(root)
    root.mkdir(parents=True)
    files = {
        "LICENSE": "fixture license\n",
        ".github/workflows/impeccable-engine-updater.yml": (
            "# fixture updater\n"
            "name: impeccable-engine-updater\n"
            "on:\n"
            "  workflow_dispatch:\n"
            "permissions:\n"
            "  contents: read\n"
            "jobs:\n"
            "  pin:\n"
            "    runs-on: ubuntu-24.04\n"
            "  build-and-verify:\n"
            "    runs-on: ubuntu-24.04\n"
            "  open-update-pr:\n"
            "    runs-on: ubuntu-24.04\n"
            "    # fixture tail\n"
        ),
        "engines/impeccable/adapter/build.rs": "fn main() {}\n",
        "engines/impeccable/adapter/src/main.rs": "fn main() {}\n",
        "engines/impeccable/adapter/tests/contract_embedded.rs": "// adapter test\n",
        "engines/impeccable/adapter/tests/data/expected-large-shape.v1.json": "{}\n",
        "engines/impeccable/build/build_engine.py": "# fixture builder\n",
        "engines/impeccable/contract/snapshot-contract.v1.json":
            '{"engine":{"engineId":"impeccable-0.1.17+floe.1.1.1"}}\n',
        "engines/impeccable/contract/fixtures/config-default.v1.json":
            '{"fixture":true}\n',
        "engines/impeccable/patches/0001-floe-context-network-and-updater-trim.patch":
            "patch one\n",
        "engines/impeccable/patches/0002-floe-rule-pass-limiter.patch":
            "patch two\n",
        "engines/impeccable/workflows/tools/compare_expected.py": "# fixture\n",
        "engines/impeccable/workflows/tools/resolve_upstream_pin.py": "# fixture\n",
        "engines/impeccable/workflows/tools/stage_candidate_engine.py": "# fixture\n",
        "engines/impeccable/workflows/tools/update_lock.py": "# fixture\n",
        "engines/impeccable/workflows/tools/verify_published_baseline.py": "# fixture\n",
        "tests/test_automatic_publication.py": "# fixture test\n",
    }
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    baseline_bytes = make_elf(2048)
    baseline_dir = (root / "engines/impeccable/dist" / BASE_ENGINE_ID /
                    verify.TARGET_TRIPLE)
    baseline_dir.mkdir(parents=True)
    baseline_path = baseline_dir / "floe-impeccable"
    baseline_path.write_bytes(baseline_bytes)
    (baseline_dir / "SHA256SUMS.txt").write_text(
        f"{sha256_bytes(baseline_bytes)}  floe-impeccable\n", encoding="utf-8")
    contract_sha = sha256_file(root / "engines/impeccable/contract/snapshot-contract.v1.json")
    lock = {
        "engineId": BASE_ENGINE_ID,
        "status": "candidate-build-not-qualified",
        "upstream": {
            "project": "pbakaus/impeccable",
            "repository": "https://github.com/pbakaus/impeccable",
            "commit": BASE_COMMIT,
            "tree": BASE_TREE,
            "engineVersion": BASE_VERSION,
            "packageVersion": "4.7.1",
            "commitDate": "2026-10-25T22:28:14+08:00",
            "commitSubject": "fixture base",
            "license": "Apache-2.0",
        },
        "floe": {
            "adapterVersion": "1.1.1",
            "contractVersion": 1,
            "patches": [
                "patches/0001-floe-context-network-and-updater-trim.patch",
                "patches/0002-floe-rule-pass-limiter.patch",
            ],
        },
        "toolchain": {"rust": "1.98.1"},
        "component": {
            "componentID": "impeccable-engine",
            "componentVersion": BASE_ENGINE_ID.removeprefix("impeccable-"),
            "artifactSha256": sha256_bytes(baseline_bytes),
            "artifactBytes": len(baseline_bytes),
            "captureContractSha256": contract_sha,
        },
    }
    lock_path = root / "engines/impeccable/ENGINE-LOCK.json"
    lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    git(root, "init", "-q", "-b", "main")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "fixture run head")
    run_head = git(root, "rev-parse", "HEAD").stdout.strip()

    # The later PR-controller/test-fixture commits must not disturb any
    # protected input or the updater recipe above open-update-pr.
    updater = root / ".github/workflows/impeccable-engine-updater.yml"
    updater.write_text(updater.read_text() + "    # fixed tail\n", encoding="utf-8")
    (root / ".github/workflows/impeccable-engine-review.yml").write_text(
        "# fixture review workflow\n", encoding="utf-8")
    (root / "tests/test_automatic_publication.py").write_text(
        "# fixture test fixed\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "fixture PR tail/test fix")
    current = git(root, "rev-parse", "HEAD").stdout.strip()
    return {
        "root": root,
        "run_head": run_head,
        "head": current,
        "base_lock": lock,
        "baseline_sha": sha256_bytes(baseline_bytes),
        "baseline_bytes": len(baseline_bytes),
        "contract_sha": contract_sha,
    }


def _write_json(path: Path, document) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _sha_sums(directory: Path) -> None:
    lines = []
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            lines.append(f"{sha256_file(path)}  {path.name}")
    (directory / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_artifact(root: Path, fixture: dict) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    repo = fixture["root"]
    base_lock = fixture["base_lock"]
    proposal = verify.expected_candidate_lock(base_lock, CANDIDATE)
    proposal_bytes = verify.canonical_lock_bytes(proposal)
    (root / "candidate-lock").mkdir(parents=True, exist_ok=True)
    (root / "candidate-lock/ENGINE-LOCK.json").write_bytes(proposal_bytes)

    engine_dir = repo / "engines/impeccable"
    dist = root / "dist" / CANDIDATE["engineId"] / verify.TARGET_TRIPLE
    dist.mkdir(parents=True, exist_ok=True)
    binary = make_elf(4096)
    (dist / "floe-impeccable").write_bytes(binary)
    binary_sha = sha256_bytes(binary)

    tracked_contract = sha256_file(engine_dir / "contract/snapshot-contract.v1.json")
    staged_contract = "1" * 64
    provenance = {
        "engineId": CANDIDATE["engineId"],
        "binary": "floe-impeccable",
        "target": verify.TARGET_TRIPLE,
        "upstream": {
            "commit": CANDIDATE["commit"],
            "tree": CANDIDATE["tree"],
            "engineVersion": CANDIDATE["engineVersion"],
            "packageVersion": CANDIDATE["packageVersion"],
        },
        "floe": {
            "adapterVersion": CANDIDATE["adapterVersion"],
            "contractVersion": 1,
            "adapterSources": {
                "build.rs": sha256_file(engine_dir / "adapter/build.rs"),
                "src/main.rs": sha256_file(engine_dir / "adapter/src/main.rs"),
                "tests/contract_embedded.rs": "2" * 64,
            },
            "contractFiles": {
                "snapshot-contract.v1.json": staged_contract,
                "fixtures/config-default.v1.json":
                    sha256_file(engine_dir / "contract/fixtures/config-default.v1.json"),
            },
            "patches": [
                {"patch": "0001-floe-context-network-and-updater-trim.patch",
                 "sha256": sha256_file(engine_dir / "patches/0001-floe-context-network-and-updater-trim.patch")},
                {"patch": "0002-floe-rule-pass-limiter.patch",
                 "sha256": sha256_file(engine_dir / "patches/0002-floe-rule-pass-limiter.patch")},
            ],
        },
        "toolchain": {
            "target": verify.TARGET_TRIPLE,
            "profile": "release",
            "jobs": 6,
            "toolchain": "1.98.1",
        },
        "artifact": {
            "sha256": binary_sha,
            "bytes": len(binary),
            "format": "ELF",
            "elfMachine": "RISC-V",
            "elfType": "EXEC",
            "static": True,
            "dynamic": False,
        },
    }
    receipt = {
        "engineId": CANDIDATE["engineId"],
        "componentVersion": f"{CANDIDATE['engineVersion']}+floe.{CANDIDATE['adapterVersion']}",
        "adapterVersion": CANDIDATE["adapterVersion"],
        "contractVersion": 1,
        "upstreamPackageVersion": CANDIDATE["packageVersion"],
        "pin": {
            "commit": CANDIDATE["commit"],
            "tree": CANDIDATE["tree"],
            "engineVersion": CANDIDATE["engineVersion"],
        },
        "artifact": {
            "sha256": binary_sha,
            "bytes": len(binary),
            "format": "ELF",
            "elfClass": "ELF64",
            "endian": "little",
            "elfMachine": "RISC-V",
            "elfType": "EXEC",
            "static": True,
            "dynamic": False,
        },
        "build": {
            "target": verify.TARGET_TRIPLE,
            "profile": "release",
            "toolchain": "1.98.1",
            "jobs": 6,
        },
        "dependencyAudit": {
            "ring": {"present": False},
            "rustls": {"present": False},
            "aws-lc-rs": {"present": False},
            "rustls-native-certs": {"present": False},
            "webpki-roots": {"present": False},
            "cratesInGraph": 1,
            "target": verify.TARGET_TRIPLE,
        },
    }
    _write_json(dist / "BUILD-RECEIPT.json", receipt)
    _write_json(dist / "PROVENANCE.json", provenance)
    (dist / "LICENSE-adapter").write_text("adapter license\n", encoding="utf-8")
    (dist / "LICENSE-impeccable-apache-2.0").write_text("upstream license\n", encoding="utf-8")
    (dist / "NOTICE-impeccable.md").write_text("notice\n", encoding="utf-8")
    _sha_sums(dist)

    logs = root / "logs"
    _write_json(logs / "stage-candidate-engine.json", {
        "ok": True,
        "candidate": {
            "commit": CANDIDATE["commit"],
            "tree": CANDIDATE["tree"],
            "version": CANDIDATE["engineVersion"],
            "engineId": CANDIDATE["engineId"],
        },
        "adapterVersion": CANDIDATE["adapterVersion"],
        "componentVersion": f"{CANDIDATE['engineVersion']}+floe.{CANDIDATE['adapterVersion']}",
        "identitySelfCheck": "passed",
        "trackedContractSha256": tracked_contract,
        "stagedContractSha256": staged_contract,
        "stagedTestIdentity": {
            "files": {
                "tests/contract_embedded.rs": {
                    "trackedSha256": sha256_file(engine_dir / "adapter/tests/contract_embedded.rs"),
                    "stagedSha256": "2" * 64,
                    "changed": True,
                },
                "tests/data/expected-large-shape.v1.json": {
                    "trackedSha256": sha256_file(
                        engine_dir / "adapter/tests/data/expected-large-shape.v1.json"),
                    "stagedSha256": "3" * 64,
                    "changed": True,
                },
            },
        },
    })
    _write_json(logs / "build-summary-riscv64gc-unknown-linux-musl-release.json", receipt)
    _write_json(logs / "build-summary-x86_64-unknown-linux-gnu-dev.json", {
        "engineId": CANDIDATE["engineId"],
        "componentVersion": f"{CANDIDATE['engineVersion']}+floe.{CANDIDATE['adapterVersion']}",
        "adapterVersion": CANDIDATE["adapterVersion"],
        "contractVersion": 1,
        "upstreamPackageVersion": CANDIDATE["packageVersion"],
        "pin": {
            "commit": CANDIDATE["commit"],
            "tree": CANDIDATE["tree"],
            "engineVersion": CANDIDATE["engineVersion"],
        },
        "artifact": {"sha256": "4" * 64, "bytes": 1024},
        "build": {"target": "x86_64-unknown-linux-gnu", "profile": "dev",
                  "toolchain": "1.98.1", "jobs": 6},
        "dependencyAudit": {"cratesInGraph": 1,
                            "target": "x86_64-unknown-linux-gnu"},
    })

    _write_json(logs / "contract-validation.json", {
        "upstreamCommit": CANDIDATE["commit"],
        "upstreamTree": CANDIDATE["tree"],
        "engineVersion": CANDIDATE["engineVersion"],
        "adapterVersion": CANDIDATE["adapterVersion"],
        "contractVersion": 1,
        "checksTotal": 3,
        "checksPassed": 3,
        "failures": [],
        "digests": {
            "snapshot-contract.v1.json": staged_contract,
            "fixtures/config-default.v1.json":
                sha256_file(engine_dir / "contract/fixtures/config-default.v1.json"),
        },
    })

    def behaviour(arch: str, binary_sha: str, runner: str) -> dict:
        return {
            "ok": True,
            "runnerExitCode": 0,
            "failures": [],
            "checksTotal": 3,
            "checksPassed": 3,
            "checks": [{"check": "one", "ok": True},
                       {"check": "two", "ok": True},
                       {"check": "three", "ok": True}],
            "environment": {
                "uname": ["Linux", arch, "6.17.0"],
                "runner": runner,
                "binarySha256": binary_sha,
                "binaryBytes": 4096,
            },
            "parity": {"cases": 2, "byteIdentical": 2, "mismatched": []},
        }

    _write_json(logs / "verify-riscv64.json",
                behaviour("riscv64", binary_sha, "docker linux/riscv64"))
    _write_json(logs / "verify-host.json",
                behaviour("x86_64", "4" * 64, "local host (no runner)"))
    _write_json(logs / "verify-baseline.json",
                behaviour("riscv64", fixture["baseline_sha"], "docker linux/riscv64"))
    _write_json(logs / "baseline-binary-verify.json", {
        "ok": True,
        "mode": "verify-binary",
        "engineId": BASE_ENGINE_ID,
        "componentVersion": BASE_ENGINE_ID.removeprefix("impeccable-"),
        "adapterVersion": "1.1.1",
        "upstream": {
            "commit": BASE_COMMIT,
            "tree": BASE_TREE,
            "engineVersion": BASE_VERSION,
        },
        "sha256": fixture["baseline_sha"],
        "bytes": fixture["baseline_bytes"],
        "contractSnapshotSha256": tracked_contract,
    })
    _write_json(logs / "baseline-record-verify.json", {
        "ok": True,
        "mode": "verify-record",
        "engineId": BASE_ENGINE_ID,
        "engineSha256": fixture["baseline_sha"],
        "cases": 1,
        "trackedGoldenCasesCovered": 1,
    })
    identity_changes = [
        {"case": "positive", "field": "engine.engineId",
         "goldenValue": BASE_ENGINE_ID, "candidateValue": CANDIDATE["engineId"]},
        {"case": "positive", "field": "engine.upstreamCommit",
         "goldenValue": BASE_COMMIT, "candidateValue": CANDIDATE["commit"]},
        {"case": "positive", "field": "engine.upstreamTree",
         "goldenValue": BASE_TREE, "candidateValue": CANDIDATE["tree"]},
        {"case": "positive", "field": "engine.upstreamEngineVersion",
         "goldenValue": BASE_VERSION, "candidateValue": CANDIDATE["engineVersion"]},
        {"case": "positive", "field": "diagnostics.engineVersion",
         "goldenValue": BASE_VERSION, "candidateValue": CANDIDATE["engineVersion"]},
        {"case": "positive", "field": "diagnostics.upstreamCommit",
         "goldenValue": BASE_COMMIT, "candidateValue": CANDIDATE["commit"]},
    ]
    _write_json(logs / "golden-comparison-vs-baseline.json", {
        "ok": True,
        "engine": {"observedSha256": binary_sha,
                   "goldenSha256": fixture["baseline_sha"]},
        "goldenLabel": f"published-baseline-{BASE_ENGINE_ID}",
        "candidateRunner": "linux/riscv64",
        "candidateIdentity": {"authenticated": True, "changes": identity_changes},
        "cases": 1,
        "identical": 1,
        "changed": 0,
        "changedUnapproved": [],
        "missing": [],
        "newCases": [],
        "verification": 3,
    })

    expected = root / "expected-baseline/riscv64-docker"
    result = {
        "engine": {
            "engineId": BASE_ENGINE_ID,
            "upstreamCommit": BASE_COMMIT,
            "upstreamTree": BASE_TREE,
            "upstreamEngineVersion": BASE_VERSION,
            "floeAdapterVersion": "1.1.1",
            "adapterCrateVersion": "1.1.1",
            "targetTriple": verify.TARGET_TRIPLE,
            "runtimeExecution": "riscv64-linux",
        }
    }
    _write_json(expected / "positive.result.v1.json", result)
    _write_json(expected / "MANIFEST.json", {
        "kind": "engine-observed goldens",
        "engine": {"sha256": fixture["baseline_sha"]},
        "cases": {
            "positive": {
                "file": "positive.result.v1.json",
                "sha256": sha256_file(expected / "positive.result.v1.json"),
            }
        },
    })

    source = root / "sources-impeccable"
    (source / "skill").mkdir(parents=True)
    (source / "skill/VERSION").write_text(CANDIDATE["engineVersion"] + "\n", encoding="utf-8")
    _write_json(source / "SOURCE-LOCK.json", {
        "upstream": {
            "commit": CANDIDATE["commit"],
            "tree": CANDIDATE["tree"],
            "engineVersion": CANDIDATE["engineVersion"],
            "skillPackageVersion": CANDIDATE["packageVersion"],
        },
        "pairing": {"engineId": CANDIDATE["engineId"]},
        "derivedFiles": {"skill/VERSION": sha256_file(source / "skill/VERSION")},
        "derivedFileCount": 1,
    })

    zip_path = root / "candidate.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file() and path != zip_path:
                archive.write(path, path.relative_to(root).as_posix())
    return zip_path


def build_api(root: Path, fixture: dict, zip_path: Path) -> dict:
    root = Path(root)
    zip_sha = sha256_file(zip_path)
    run = {
        "id": RUN_ID,
        "run_attempt": 1,
        "status": "completed",
        "conclusion": "success",
        "event": "workflow_dispatch",
        "head_branch": "main",
        "head_sha": fixture["run_head"],
        "path": verify.UPDATER_WORKFLOW_PATH,
        "name": "impeccable-engine-updater",
        "repository": {"id": verify.OFFICIAL_REPOSITORY_ID,
                       "full_name": verify.OFFICIAL_REPOSITORY},
        "head_repository": {"full_name": verify.OFFICIAL_REPOSITORY},
    }
    steps = [{"name": name, "conclusion": "success"}
             for name in verify.REQUIRED_BUILD_STEPS]
    steps.extend({"name": name, "conclusion": "success"} for name in
                 verify.PUBLISHED_ROUTE_STEPS if name not in
                 {step["name"] for step in steps})
    steps.extend([
        {"name": verify.PUBLISHED_COMPARISON_STEP, "conclusion": "success"},
        {"name": verify.HISTORICAL_COMPARISON_STEP, "conclusion": "skipped"},
    ])
    jobs = {
        "total_count": 2,
        "jobs": [
            {"id": 1, "name": verify.PIN_JOB_NAME, "status": "completed",
             "conclusion": "success", "steps": []},
            {"id": BUILD_JOB_ID, "name": verify.BUILD_JOB_NAME, "status": "completed",
             "conclusion": "success", "head_sha": fixture["run_head"], "steps": steps},
        ],
    }
    artifacts = {
        "total_count": 2,
        "artifacts": [
            {"id": ARTIFACT_ID, "name": verify.CANDIDATE_ARTIFACT_NAME,
             "size_in_bytes": zip_path.stat().st_size, "expired": False,
             "expires_at": "2099-01-01T00:00:00Z", "digest": f"sha256:{zip_sha}",
             "workflow_run": {"id": RUN_ID, "head_sha": fixture["run_head"]}},
            {"id": 99, "name": verify.CANDIDATE_ARTIFACT_NAME + "-failure-logs",
             "size_in_bytes": 1, "expired": False,
             "expires_at": "2099-01-01T00:00:00Z", "digest": "sha256:" + "0" * 64,
             "workflow_run": {"id": RUN_ID, "head_sha": fixture["run_head"]}},
        ],
    }
    api = root / "api"
    _write_json(api / "run.json", run)
    _write_json(api / "jobs.json", jobs)
    _write_json(api / "artifacts.json", artifacts)
    shutil.copyfile(zip_path, api / "candidate.zip")
    return {"run": run, "jobs": jobs, "artifacts": artifacts,
            "zip": api / "candidate.zip", "dir": api}
