#!/usr/bin/env python3
"""Append one browser-test case record as a JSONL line (stdlib only).

Runs inside the task's resolved Linux guest through exec.shell, from the
skill's staged copy in the task workspace. The model records what the
native tools actually returned; this writer only bounds and orders the
evidence. It never executes, never networks, and writes only the explicit
--results path (which must stay inside the task workspace).

Example:
  python3 scripts/record_case.py --results results/webapp-testing.jsonl \
    --case nav-index --status PASS --detail "browser.observe ok" \
    --set document_id=8f2c... --set tab_id=2C91...

Statuses: PASS, FAIL, TIMEOUT, BLOCKED. A failing expectation must be
recorded honestly as FAIL or TIMEOUT; check_fixture.py requires the
declared failing case to be one of those.
"""
import argparse
import json
import pathlib
import re
import sys

STATUSES = ("PASS", "FAIL", "TIMEOUT", "BLOCKED")
HEX64 = re.compile(r"[0-9a-fA-F]{64}")
CASE_PATTERN = re.compile(r"[a-z0-9][a-z0-9.-]{0,63}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", required=True,
                        help="workspace-relative JSONL results file to append")
    parser.add_argument("--case", required=True,
                        help="lowercase case id (a-z0-9 . -), unique per runbook case")
    parser.add_argument("--status", required=True, choices=STATUSES)
    parser.add_argument("--detail", required=True, help="what the tools actually returned")
    parser.add_argument("--set", dest="fields", action="append", default=[],
                        metavar="KEY=VALUE", help="evidence field (repeatable)")
    parser.add_argument("--max-detail-bytes", type=int, default=2048)
    args = parser.parse_args()

    if not CASE_PATTERN.fullmatch(args.case):
        print("record_case: invalid --case id", file=sys.stderr)
        return 2
    detail = args.detail.strip()
    if not detail:
        print("record_case: --detail must not be empty", file=sys.stderr)
        return 2
    detail = detail[: args.max_detail_bytes]

    evidence = {}
    for item in args.fields:
        key, sep, value = item.partition("=")
        if not sep or not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", key):
            print(f"record_case: invalid --set field {item!r}", file=sys.stderr)
            return 2
        if key in ("case", "status", "detail"):
            print("record_case: reserved evidence key", key, file=sys.stderr)
            return 2
        evidence[key] = value[:2048]
    if "screenshot_sha256" in evidence and not HEX64.fullmatch(evidence["screenshot_sha256"]):
        print("record_case: screenshot_sha256 must be 64 hex characters", file=sys.stderr)
        return 2

    record = {"case": args.case, "status": args.status, "detail": detail,
              "evidence": evidence}
    out = pathlib.Path(args.results)
    out.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, sort_keys=True)
    with out.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    print(json.dumps({"recorded": args.case, "status": args.status,
                      "results": str(out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
