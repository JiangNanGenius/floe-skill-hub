#!/usr/bin/env python3
"""Verify the App's vendored contract copy and native models against this lane.

The native side (A2) vendors the frozen contract into the App bundle and
implements the same wire shapes in Swift. This checks the two halves still agree,
from the committed App source at a given revision, without touching the App
working tree:

  * every vendored contract file is byte-identical to the frozen hub file;
  * the pin the native code hardcodes is the pin this engine was built from;
  * the budgets, exit codes, needs/facts/result key spellings and the coverage
    rule the native models declare match the contract;
  * the native producer script really embeds the pinned upstream capture script,
    with the exact byte ranges and digests named.

  verify_native_alignment.py --repo <parent-checkout> --app-commit <sha> \
      --contract engines/impeccable/contract --lock engines/impeccable/ENGINE-LOCK.json \
      --out <evidence.json>

Read-only: it uses `git show` against the given commit and writes only --out.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

RESOURCE_DIR = "FloeAgent/FloeApp/Resources/Impeccable"
BROWSER_DIR = "FloeAgent/FloeApp/Browser"

# Vendored App resource -> frozen hub contract file.
CONTRACT_PAIRS = [
    ("contract-snapshot-contract.v1.json", "snapshot-contract.v1.json"),
    ("snapshot.schema.v1.json", "producer/snapshot.schema.v1.json"),
    ("facts.schema.v1.json", "producer/facts.schema.v1.json"),
    ("identity.schema.v1.json", "producer/identity.schema.v1.json"),
    ("result.schema.v1.json", "producer/result.schema.v1.json"),
    ("style-props.v1.json", "producer/style-props.v1.json"),
    ("pseudo-props.v1.json", "producer/pseudo-props.v1.json"),
    ("state-pseudos.v1.json", "producer/state-pseudos.v1.json"),
    ("capture-limits.v1.json", "producer/capture-limits.v1.json"),
]

# Native model declarations that must match the contract text.
NATIVE_CONSTANTS = {
    "BrowserImpeccableContract.swift": [
        ('name = "floe.impeccable.snapshot"', "contract name"),
        ("contractVersion = 1", "contract version"),
        ('producerTrust = "native-fixed-script"', "the only accepted producer trust"),
        ('redactionPolicy = "floe.impeccable.redaction.v1"', "redaction policy"),
        ('producerEngine = "WebKit"', "producer engine"),
        ("stylePropCount = 138", "style column count"),
        ("pseudoPropCount = 23", "pseudo column count"),
        ("statePseudoCount = 31", "state pseudo count"),
        ("maxSnapshotBytes: 50_331_648", "48 MiB snapshot budget"),
        ("maxElements: 30_000", "element budget"),
        ("maxRounds: 4", "round budget"),
        ("maxHitTestsPerRound: 4_096", "per-round hit-test budget"),
        ("maxHitTestsTotal: 16_384", "total hit-test budget"),
        ("timeoutMs: 120_000", "timeout budget"),
        ("case clean = 0", "exit 0 clean"),
        ("case failure = 1", "exit 1 failure"),
        ("case findings = 2", "exit 2 findings"),
        ("case needsFacts = 3", "exit 3 needs-facts"),
        ("case inconclusive = 4", "exit 4 inconclusive"),
        ("hitTestsBits", "exact-bit hit-test channel"),
        ("unanswerable", "unanswerable points are reported, not answered"),
        ("findingCount", "result finding count"),
        ("uncoveredRequired", "coverage blockers"),
    ],
}

RESULT_KEYS = ["contract", "contractVersion", "status", "verdict", "identityCheck",
               "budget", "coverage", "needs", "findings", "error"]
NEEDS_KEYS = ["hitTests", "hitTestsBits", "scrollProbes", "round"]
FACTS_KEYS = ["taskId", "sessionId", "tabId", "documentId", "captureId",
              "documentGeneration", "fenced", "hits", "shownOnScroll"]
RECEIPT_KEYS = ["captureId", "binding", "bridgeRootIsTaskWorkspace", "relativeDirectory",
                "relativeSnapshotFile", "relativeIdentityFile", "documentGeneration",
                "elementCount", "snapshotBytes", "viewport", "scroll", "redaction",
                "scriptDigest"]


def show(repo: Path, commit: str, path: str) -> bytes | None:
    result = subprocess.run(["git", "-C", str(repo), "show", f"{commit}:{path}"],
                            capture_output=True)
    return result.stdout if result.returncode == 0 else None


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--app-commit", required=True)
    ap.add_argument("--contract", required=True, type=Path)
    ap.add_argument("--lock", required=True, type=Path)
    ap.add_argument("--upstream-js", type=Path, default=None,
                    help="the pinned upstream browser-bundle/15-snapshot.js, for the producer byte check")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    for name in ("repo", "contract", "lock", "upstream_js", "out"):
        value = getattr(args, name)
        if value is not None:
            setattr(args, name, Path(value).expanduser().resolve())

    checks: list[dict] = []
    failures: list[str] = []

    def check(name: str, ok: bool, detail=None) -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})
        if not ok:
            failures.append(name)

    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    contract = json.loads((args.contract / "snapshot-contract.v1.json").read_text(encoding="utf-8"))

    # 1. vendored contract bytes
    vendored = {}
    for app_name, hub_rel in CONTRACT_PAIRS:
        app_bytes = show(args.repo, args.app_commit, f"{RESOURCE_DIR}/{app_name}")
        hub_bytes = (args.contract / hub_rel).read_bytes()
        if app_bytes is None:
            check(f"the App vendors {app_name}", False, "not present at this commit")
            continue
        same = sha(app_bytes) == sha(hub_bytes)
        vendored[app_name] = {"sha256": sha(app_bytes), "bytes": len(app_bytes),
                              "hubFile": hub_rel, "identical": same}
        check(f"the App's {app_name} is byte-identical to the frozen contract", same,
              {"app": sha(app_bytes)[:16], "hub": sha(hub_bytes)[:16]})

    # 2. the native pin equals the build pin
    swift = show(args.repo, args.app_commit, f"{BROWSER_DIR}/BrowserImpeccableContract.swift")
    if swift is None:
        check("the native contract model exists at this commit", False)
    else:
        text = swift.decode("utf-8", "replace")
        check("the native code hardcodes the same upstream commit",
              lock["upstream"]["commit"] in text, lock["upstream"]["commit"])
        check("the native code hardcodes the same upstream tree",
              lock["upstream"]["tree"] in text, lock["upstream"]["tree"])
        check("the native code hardcodes the same engine version",
              f'upstreamEngineVersion = "{lock["upstream"]["engineVersion"]}"' in text,
              lock["upstream"]["engineVersion"])
        for needle, label in NATIVE_CONSTANTS["BrowserImpeccableContract.swift"]:
            check(f"the native model declares {label}", needle in text, needle)
        # the exact key spellings the engine writes
        for key in RESULT_KEYS + NEEDS_KEYS + FACTS_KEYS:
            check(f"the native model names the result/needs/facts key `{key}`", key in text, key)

    # 3. the capture receipt and the tool surface
    capture = show(args.repo, args.app_commit, f"{BROWSER_DIR}/BrowserImpeccableCapture.swift")
    if capture is None:
        check("the native capture service exists at this commit", False)
    else:
        text = capture.decode("utf-8", "replace")
        for key in RECEIPT_KEYS:
            check(f"the capture receipt carries `{key}`", key in text, key)
        for name in ("snapshot.v1.json", "identity.v1.json", "facts.round"):
            check(f"the bridge file naming uses `{name}`", name in text, name)
        check("the engine is invoked through the resolved Linux exec.shell, not in-process",
              "exec.shell" in text and "snapshot-scan" in text)

    tools = show(args.repo, args.app_commit, f"{BROWSER_DIR}/BrowserTools.swift")
    if tools is None:
        check("the browser tool surface exists at this commit", False)
    else:
        text = tools.decode("utf-8", "replace")
        for needle in ('"design"', "designAction", "captureID", "needsFile",
                       '"capture"', '"facts"', '"release"', "relativeFactsFile"):
            check(f"browser.observe exposes the design action `{needle}`", needle in text, needle)

    # 4. the native producer really embeds the pinned upstream capture script
    producer = show(args.repo, args.app_commit, f"{RESOURCE_DIR}/impeccable-producer.v1.js")
    manifest = show(args.repo, args.app_commit, f"{RESOURCE_DIR}/producer-manifest.v1.json")
    producer_facts: dict = {}
    if producer is None:
        check("the native producer script is vendored", False)
    else:
        producer_facts = {"bytes": len(producer), "sha256": sha(producer)}
        check("the producer manifest digest matches the vendored producer bytes",
              manifest is not None and sha(producer) in manifest.decode("utf-8", "replace"),
              sha(producer)[:16])
        if args.upstream_js and args.upstream_js.is_file():
            upstream = args.upstream_js.read_bytes()
            prefix_len = len(upstream) - 1  # the App embeds upstream minus its trailing newline
            prefix = producer[:prefix_len]
            check("the producer's prefix is the verbatim pinned upstream capture script",
                  prefix == upstream[:-1],
                  {"prefixBytes": prefix_len,
                   "prefixSha256": sha(prefix),
                   "upstreamFullSha256": sha(upstream)})
            adapter = producer[prefix_len + 1:]
            producer_facts.update({
                "upstreamPrefixBytes": prefix_len,
                "upstreamPrefixSha256": sha(prefix),
                "upstreamFullFileSha256": sha(upstream),
                "upstreamFullFileBytes": len(upstream),
                "floeAdapterBytes": len(adapter),
                "floeAdapterSha256": sha(adapter),
                "note": ("the pinned upstream file is %d bytes ending in a newline; the App embeds the "
                         "first %d bytes verbatim (sha256 %s) and appends the Floe adapter after one "
                         "separator newline (sha256 %s). The contract's pinnedSourceDigests entry "
                         "%s is the FULL upstream file digest, not the embedded prefix digest."
                         % (len(upstream), prefix_len, sha(prefix)[:12], sha(adapter)[:12], sha(upstream)[:12])),
            })
            if manifest is not None:
                check("the producer manifest records the Floe adapter digest",
                      sha(adapter) in manifest.decode("utf-8", "replace"), sha(adapter)[:16])

    report = {
        "ok": not failures,
        "appCommit": args.app_commit,
        "hubPin": {"commit": lock["upstream"]["commit"], "tree": lock["upstream"]["tree"],
                    "engineVersion": lock["upstream"]["engineVersion"],
                    "engineId": lock["engineId"]},
        "contractVersion": contract["contractVersion"],
        "vendoredContractFiles": vendored,
        "nativeProducer": producer_facts,
        "checksTotal": len(checks),
        "checksPassed": sum(1 for c in checks if c["ok"]),
        "failures": failures,
        "checks": checks,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "checks"}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
