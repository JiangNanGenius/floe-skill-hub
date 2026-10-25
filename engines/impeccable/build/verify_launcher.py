#!/usr/bin/env python3
"""Launcher verification, on this host and inside a riscv64 environment.

The launcher is the only thing that decides *which* engine binary runs, so its
resolution order, its digest gate and — above all — the absence of any download
path are checked as behaviour, not read as prose:

  * an explicit engine path, a runtime-chosen engine directory and a Hub-installed
    `engines/impeccable/dist/<engineId>/<triple>/` layout all resolve;
  * a riscv64 machine maps to `riscv64gc-unknown-linux-musl` (the upstream
    launcher maps only arm64/x64 and then tries to download a release asset);
  * a missing or tampered binary exits 127 with the Hub-owned message and never
    touches the network;
  * `FLOE_IMPECCABLE_VERIFY_DIGEST=1` refuses a binary whose digest does not
    match the engine directory's `SHA256SUMS.txt`;
  * a same-named binary found on PATH is exec'd only after it answers the
    `engine-probe` handshake.

  verify_launcher.py --launcher <path> --host-binary <path> --stage <dir> \
      --out <evidence.json> [--riscv64-binary <path>] [--engine-id <id>] \
      [--docker-platform linux/riscv64] [--docker-image alpine:3.20]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def triple_for(system: str, machine: str) -> str:
    if system == "Linux" and machine == "riscv64":
        return "riscv64gc-unknown-linux-musl"
    if system == "Darwin" and machine in ("arm64", "aarch64"):
        return "aarch64-apple-darwin"
    if system == "Linux" and machine in ("arm64", "aarch64"):
        return "aarch64-unknown-linux-gnu"
    return "unknown"


class Report:
    def __init__(self):
        self.checks: list[dict] = []
        self.failures: list[str] = []

    def check(self, name: str, ok: bool, detail=None) -> None:
        self.checks.append({"check": name, "ok": bool(ok), "detail": detail})
        if not ok:
            self.failures.append(name)

    def payload(self) -> dict:
        return {
            "checksTotal": len(self.checks),
            "checksPassed": sum(1 for c in self.checks if c["ok"]),
            "failures": self.failures,
            "checks": self.checks,
        }


def build_hub_layout(root: Path, launcher: Path, binary: Path, engine_id: str, triple: str) -> Path:
    """A minimal Hub-installed skill layout: skill/scripts + engines/<...>/<triple>."""
    scripts = root / "skill" / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(launcher, scripts / "floe-impeccable")
    (scripts / "floe-impeccable").chmod(0o755)
    engine_dir = root / "engines" / "impeccable" / "dist" / engine_id / triple
    engine_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(binary, engine_dir / "floe-impeccable")
    (engine_dir / "floe-impeccable").chmod(0o755)
    sums = engine_dir / "SHA256SUMS.txt"
    sums.write_text(f"{sha256_file(binary)}  floe-impeccable\n", encoding="utf-8")
    return scripts / "floe-impeccable"


def run_launcher(launcher: Path, args: list[str], env: dict | None = None, cwd: Path | None = None):
    full_env = dict(os.environ)
    for key in ("FLOE_IMPECCABLE_ENGINE", "FLOE_IMPECCABLE_ENGINE_DIR", "FLOE_IMPECCABLE_VERIFY_DIGEST",
                "IMPECCABLE_SKILL_DIR", "IMPECCABLE_SELF"):
        full_env.pop(key, None)
    if env:
        full_env.update({k: str(v) for k, v in env.items()})
    result = subprocess.run(["sh", str(launcher), *args], capture_output=True, text=True,
                            env=full_env, cwd=str(cwd) if cwd else None, timeout=300)
    return result.returncode, result.stdout, result.stderr


def static_checks(report: Report, launcher: Path) -> None:
    text = launcher.read_text(encoding="utf-8")
    report.check("the launcher maps riscv64 to the static musl triple",
                 "riscv64) arch=riscv64" in text and "linux-riscv64) triple=riscv64gc-unknown-linux-musl" in text)
    for needle in ("curl", "wget", "https://github.com", "releases/download", "IMPECCABLE_DOWNLOAD_BASE"):
        report.check(f"the launcher has no download path ({needle})", needle not in text)
    report.check("the launcher keeps the upstream engine-probe handshake", "engine-probe" in text and "impeccable-engine*" in text)
    report.check("the launcher exports the skill directory the verbs read",
                 "IMPECCABLE_SKILL_DIR" in text and "export IMPECCABLE_SKILL_DIR" in text)
    report.check("the launcher fails closed with exit 127", "exit 127" in text)
    report.check("the launcher offers an opt-in digest gate", "FLOE_IMPECCABLE_VERIFY_DIGEST" in text and "SHA256SUMS.txt" in text)
    syntax = subprocess.run(["sh", "-n", str(launcher)], capture_output=True, text=True)
    report.check("the launcher is valid POSIX shell", syntax.returncode == 0, syntax.stderr[:300])


def host_checks(report: Report, args, stage: Path) -> None:
    system = "Darwin" if sys.platform == "darwin" else "Linux"
    machine = "arm64" if os.uname().machine in ("arm64", "aarch64") else os.uname().machine
    triple = triple_for(system, machine)
    engine_id = args.engine_id

    layout_root = stage / "hub-layout"
    if layout_root.exists():
        shutil.rmtree(layout_root)
    launcher = build_hub_layout(layout_root, args.launcher, args.host_binary, engine_id, triple)

    code, out, err = run_launcher(launcher, ["engine-probe"])
    report.check("the Hub layout resolves without any environment variable", code == 0 and out.startswith("impeccable-engine"),
                 {"exit": code, "stdout": out.strip(), "stderr": err[:200]})

    code, out, err = run_launcher(args.launcher, ["engine-probe"],
                                  env={"FLOE_IMPECCABLE_ENGINE": args.host_binary})
    report.check("an explicit engine path is exec'd", code == 0 and out.startswith("impeccable-engine"),
                 {"exit": code, "stdout": out.strip()})

    missing = stage / "does-not-exist" / "floe-impeccable"
    code, out, err = run_launcher(args.launcher, ["engine-probe"], env={"FLOE_IMPECCABLE_ENGINE": missing})
    report.check("a missing explicit engine fails closed instead of downloading",
                 code == 127 and "never downloads" in err, {"exit": code, "stderr": err[-260:]})

    engine_dir = layout_root / "engines" / "impeccable" / "dist" / engine_id / triple
    code, out, err = run_launcher(args.launcher, ["--version"],
                                  env={"FLOE_IMPECCABLE_ENGINE_DIR": engine_dir})
    report.check("a runtime-chosen engine directory resolves by triple", code == 0 and "+floe." in out,
                 {"exit": code, "stdout": out.strip()})

    # The digest gate: correct digest passes, a tampered binary is refused.
    code, out, err = run_launcher(args.launcher, ["engine-probe"],
                                  env={"FLOE_IMPECCABLE_ENGINE": engine_dir / "floe-impeccable",
                                       "FLOE_IMPECCABLE_VERIFY_DIGEST": "1"},
                                  cwd=engine_dir)
    report.check("the digest gate passes for the verified binary", code == 0 and out.startswith("impeccable-engine"),
                 {"exit": code, "stderr": err[:200]})

    tampered_root = stage / "tampered"
    if tampered_root.exists():
        shutil.rmtree(tampered_root)
    tampered_launcher = build_hub_layout(tampered_root, args.launcher, args.host_binary, engine_id, triple)
    tampered_dir = tampered_root / "engines" / "impeccable" / "dist" / engine_id / triple
    with (tampered_dir / "floe-impeccable").open("ab") as fh:
        fh.write(b"\x00")
    code, out, err = run_launcher(tampered_launcher, ["engine-probe"],
                                  env={"FLOE_IMPECCABLE_ENGINE": tampered_dir / "floe-impeccable",
                                       "FLOE_IMPECCABLE_VERIFY_DIGEST": "1"},
                                  cwd=tampered_dir)
    report.check("the digest gate refuses a tampered binary", code == 127 and "digest mismatch" in err,
                 {"exit": code, "stderr": err[-260:]})

    # A same-named binary on PATH that does not answer the handshake is not exec'd.
    fake_bin = stage / "fakebin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    fake = fake_bin / "floe-impeccable"
    fake.write_text("#!/bin/sh\necho 'Unknown command'\nexit 1\n", encoding="utf-8")
    fake.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    result = subprocess.run(["sh", str(args.launcher), "engine-probe"], capture_output=True, text=True, env=env, timeout=120)
    report.check("a PATH candidate that fails the handshake is not exec'd",
                 result.returncode == 127 and "Unknown command" not in result.stdout,
                 {"exit": result.returncode, "stdout": result.stdout[:120], "stderr": result.stderr[-200:]})

    good = fake_bin / "floe-impeccable"
    good.write_text("#!/bin/sh\nif [ \"$1\" = engine-probe ]; then echo 'impeccable-engine 0.0.0-fake'; exit 0; fi\nexit 9\n",
                    encoding="utf-8")
    good.chmod(0o755)
    result = subprocess.run(["sh", str(args.launcher), "engine-probe"], capture_output=True, text=True, env=env,
                            cwd=str(stage / "empty-cwd" if (stage / "empty-cwd").mkdir(exist_ok=True) is None else stage),
                            timeout=120)
    report.check("a PATH candidate that answers the handshake is exec'd",
                 result.returncode == 0 and "impeccable-engine" in result.stdout,
                 {"exit": result.returncode, "stdout": result.stdout[:120]})


RISCV_SCRIPT = r"""#!/bin/sh
set -u
OUT=/l/out
rm -rf "$OUT"; mkdir -p "$OUT"
{ uname -s; uname -m; } > "$OUT/uname.txt" 2>&1
L=/l/skill/scripts/floe-impeccable

# 1. The Hub layout resolves on a riscv64 machine and really execs the engine.
sh "$L" engine-probe > "$OUT/probe.stdout" 2> "$OUT/probe.stderr"
echo $? > "$OUT/probe.exit"

# 2. No engine anywhere: fail closed, no download attempt.
mkdir -p /l/empty
cp "$L" /l/empty/floe-impeccable
( cd /l/empty && FLOE_IMPECCABLE_ENGINE=/l/empty/missing sh /l/empty/floe-impeccable engine-probe \
    > "$OUT/missing.stdout" 2> "$OUT/missing.stderr" )
echo $? > "$OUT/missing.exit"

# 3. The digest gate accepts the verified binary and refuses a tampered one.
ENGINE=$(ls -d /l/engines/impeccable/dist/*/riscv64gc-unknown-linux-musl 2>/dev/null | head -1)
if [ -n "$ENGINE" ]; then
  ( cd "$ENGINE" && FLOE_IMPECCABLE_VERIFY_DIGEST=1 FLOE_IMPECCABLE_ENGINE="$ENGINE/floe-impeccable" \
      sh "$L" engine-probe > "$OUT/digest-ok.stdout" 2> "$OUT/digest-ok.stderr" )
  echo $? > "$OUT/digest-ok.exit"
  cp -r "$ENGINE" /l/tampered
  printf '\000' >> /l/tampered/floe-impeccable
  ( cd /l/tampered && FLOE_IMPECCABLE_VERIFY_DIGEST=1 FLOE_IMPECCABLE_ENGINE=/l/tampered/floe-impeccable \
      sh "$L" engine-probe > "$OUT/digest-bad.stdout" 2> "$OUT/digest-bad.stderr" )
  echo $? > "$OUT/digest-bad.exit"
fi

# 4. A real scan through the launcher, to prove the whole path works on riscv64.
if [ -d /l/contract ]; then
  sh "$L" snapshot-scan --snapshot /l/contract/snapshot-needs-hit-tests.v1.json \
      --identity /l/contract/identity-needs.v1.json --out "$OUT/scan.result.json" \
      > "$OUT/scan.stdout" 2> "$OUT/scan.stderr"
  echo $? > "$OUT/scan.exit"
fi
"""


def riscv64_checks(report: Report, args, stage: Path) -> None:
    if not args.riscv64_binary:
        report.check("riscv64 launcher behaviour was exercised in a riscv64 environment", False,
                     "no --riscv64-binary supplied; the guest launcher path is unverified")
        return
    root = stage / "riscv64"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    triple = "riscv64gc-unknown-linux-musl"
    build_hub_layout(root, args.launcher, args.riscv64_binary, args.engine_id, triple)
    contract_fixtures = args.contract / "fixtures"
    shutil.copytree(contract_fixtures, root / "contract", ignore=shutil.ignore_patterns("invalid"))
    (root / "launcher-checks.sh").write_text(RISCV_SCRIPT, encoding="utf-8")
    (root / "launcher-checks.sh").chmod(0o755)

    create = subprocess.run(
        ["docker", "create", "--platform", args.docker_platform, args.docker_image, "sh", "/l/launcher-checks.sh"],
        capture_output=True, text=True)
    if create.returncode != 0:
        report.check("the riscv64 launcher container started", False, create.stderr[-400:])
        return
    container = create.stdout.strip()
    log = [f"container {container}"]
    try:
        copy_in = subprocess.run(["docker", "cp", f"{root}/.", f"{container}:/l"], capture_output=True, text=True)
        log.append(f"cp in: {copy_in.returncode} {copy_in.stderr[-300:]}")
        if copy_in.returncode != 0:
            report.check("the riscv64 launcher stage was copied into the container", False, copy_in.stderr[-300:])
            return
        started = subprocess.run(["docker", "start", "-a", container], capture_output=True, text=True, timeout=1800)
        log.append(f"start: exit={started.returncode}\n{started.stdout[-500:]}\n{started.stderr[-500:]}")
        out_dir = root / "out"
        copy_out = subprocess.run(["docker", "cp", f"{container}:/l/out", str(out_dir)], capture_output=True, text=True)
        log.append(f"cp out: {copy_out.returncode} {copy_out.stderr[-300:]}")
    finally:
        (root / "container.log").write_text("\n".join(log), encoding="utf-8")
        subprocess.run(["docker", "rm", "-f", container], capture_output=True, text=True)

    def read(name: str) -> str:
        path = root / "out" / name
        return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""

    uname = read("uname.txt").split()
    report.check("the launcher ran on a riscv64 machine", len(uname) >= 2 and uname[1] == "riscv64", uname[:2])
    probe = read("probe.stdout")
    report.check("the Hub layout resolves the riscv64 engine and execs it",
                 read("probe.exit").strip() == "0" and probe.startswith("impeccable-engine 0.1.17+floe."),
                 {"exit": read("probe.exit").strip(), "stdout": probe.strip(), "stderr": read("probe.stderr")[:200]})
    missing_err = read("missing.stderr")
    report.check("a missing riscv64 engine fails closed with no download",
                 read("missing.exit").strip() == "127" and "never downloads" in missing_err,
                 {"exit": read("missing.exit").strip(), "stderr": missing_err[-240:]})
    report.check("the digest gate accepts the verified riscv64 binary",
                 read("digest-ok.exit").strip() == "0" and read("digest-ok.stdout").startswith("impeccable-engine"),
                 {"exit": read("digest-ok.exit").strip(), "stderr": read("digest-ok.stderr")[:200]})
    report.check("the digest gate refuses a tampered riscv64 binary",
                 read("digest-bad.exit").strip() == "127" and "digest mismatch" in read("digest-bad.stderr"),
                 {"exit": read("digest-bad.exit").strip(), "stderr": read("digest-bad.stderr")[-240:]})
    scan_exit = read("scan.exit").strip()
    scan_doc = None
    scan_path = root / "out" / "scan.result.json"
    if scan_path.is_file():
        try:
            scan_doc = json.loads(scan_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            scan_doc = None
    report.check("a real snapshot scan runs through the launcher on riscv64 and returns Needs",
                 scan_exit == "3" and scan_doc is not None and scan_doc.get("status") == "needs-facts",
                 {"exit": scan_exit, "status": (scan_doc or {}).get("status"),
                  "points": len(((scan_doc or {}).get("needs") or {}).get("hitTests") or [])})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--launcher", required=True, type=Path)
    ap.add_argument("--host-binary", required=True, type=Path)
    ap.add_argument("--riscv64-binary", type=Path, default=None)
    ap.add_argument("--contract", required=True, type=Path)
    ap.add_argument("--engine-id", default="impeccable-0.1.17+floe.1.0.0")
    ap.add_argument("--stage", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--docker-platform", default="linux/riscv64")
    ap.add_argument("--docker-image", default="alpine:3.20")
    ap.add_argument("--skip-host", action="store_true")
    args = ap.parse_args()
    for name in ("launcher", "host_binary", "contract", "stage", "out", "riscv64_binary"):
        value = getattr(args, name)
        if value is not None:
            setattr(args, name, Path(value).expanduser().resolve())
    args.stage.mkdir(parents=True, exist_ok=True)

    report = Report()
    static_checks(report, args.launcher)
    if not args.skip_host:
        host_checks(report, args, args.stage)
    riscv64_checks(report, args, args.stage)

    payload = report.payload()
    payload["ok"] = not report.failures
    payload["launcher"] = str(args.launcher)
    payload["launcherSha256"] = sha256_file(args.launcher)
    payload["hostBinary"] = {"path": str(args.host_binary), "sha256": sha256_file(args.host_binary)}
    if args.riscv64_binary and args.riscv64_binary.is_file():
        payload["riscv64Binary"] = {"path": str(args.riscv64_binary), "sha256": sha256_file(args.riscv64_binary)}
    payload["engineId"] = args.engine_id
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in payload.items() if k != "checks"}, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
