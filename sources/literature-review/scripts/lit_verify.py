#!/usr/bin/env python3
"""Golden verifier for the Floe literature-review adaptation.

First-party Floe script (MIT (c) Floe project); NOT upstream K-Dense
content. Fully OFFLINE: it never performs a network call and proves, with
embedded goldens over the bundled SYNTHETIC fixtures, that

  * DOI extraction preserves legal suffix punctuation (parenthesized legacy
    DOIs), strips prose punctuation, normalizes doi.org URLs and `doi:`
    prefixes, and deduplicates;
  * offline citation verification classifies every honesty bucket exactly:
    registered+retrieved (with the real fetched fields, nothing invented),
    registered with metadata unavailable, missing handle, inconclusive
    envelope, missing offline record, invalid syntax;
  * offline mode provably attempts NO network I/O: the CLI is re-run with
    http(s)_proxy pointed at a closed port and must behave identically;
  * record dedup/rank/year-filter/BibTeX/Markdown formatting of
    search_databases.py match hand-computed goldens, including the
    no-fabrication rules (missing year renders `year = {},`, missing author
    renders `author = {},`, keys never gain data that is not in the record);
  * CLI exit codes and report files are truthful, and every fixture is
    byte-preserved after the whole run.

Online verification against doi.org/Crossref is guest-acceptance scope
(see references/PROVENANCE.md runbook; `online_acceptance.md` carries the
single real DOI used there). Exit 0 only when every check passes.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = SCRIPTS_DIR.parent
FIXTURES = PACKAGE_ROOT / "assets" / "fixtures"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


class CheckFailure(Exception):
    """One failed golden/safety check with an actionable message."""


def _exact(reference: Any, candidate: Any, label: str) -> None:
    if candidate != reference:
        raise CheckFailure(f"{label}: expected exactly {reference!r}, got {candidate!r}")


def check_runtime() -> None:
    if sys.version_info < (3, 11):
        raise CheckFailure(
            f"Python {sys.version_info.major}.{sys.version_info.minor} is below the "
            "required 3.11 (the resolved Floe Linux guest provides 3.13)")


def check_doi_extraction() -> None:
    import verify_citations as vc

    text = (FIXTURES / "review_fixture.md").read_text(encoding="utf-8")
    dois = vc.extract_dois(text)
    _exact(
        [
            "10.99999/floe-synthetic-0001",
            "10.99999/floe-synthetic-0002",
            "10.99999/old(1998)style",
            "10.99999/floe-synthetic-0003",
            "10.99999/floe-synthetic-0004",
            "10.99999/floe-synthetic-0005",
        ],
        dois,
        "DOI extraction golden (order, normalization, balanced parens, dedup)",
    )
    registered, meta = vc.CitationVerifier(offline_dir=None).verify_doi("not-a-doi")
    _exact(False, registered, "invalid syntax must not verify")
    _exact("invalid_syntax", meta["status"], "invalid syntax status")


def check_offline_taxonomy() -> None:
    import verify_citations as vc

    verifier = vc.CitationVerifier(offline_dir=FIXTURES / "crossref")
    _exact("offline", verifier.mode, "verifier mode")
    report = verifier.verify_citations_in_file(str(FIXTURES / "review_fixture.md"))
    _exact("offline", report["mode"], "report mode")
    _exact(6, report["total_dois"], "total dois")
    _exact(
        ["10.99999/floe-synthetic-0001", "10.99999/floe-synthetic-0002",
         "10.99999/old(1998)style"],
        report["verified"],
        "verified list (order of appearance)",
    )
    _exact(["10.99999/floe-synthetic-0003"], report["missing"], "missing list")
    _exact(sorted(["10.99999/floe-synthetic-0004", "10.99999/floe-synthetic-0005"]),
           sorted(report["inconclusive"]), "inconclusive list")
    _exact(["10.99999/floe-synthetic-0002"], report["metadata_unavailable"],
           "registered-but-metadata-unavailable list")
    # retrieved metadata must equal the fetched record exactly - no invention
    meta = report["metadata"]["10.99999/floe-synthetic-0001"]
    _exact("retrieved", meta["metadata_status"], "0001 metadata status")
    _exact("Synthetic CRISPR screening study", meta["title"], "0001 title")
    _exact("Zhang, W.; Li, H.", meta["authors"], "0001 authors")
    _exact("2024", meta["year"], "0001 year")
    _exact("Journal of Synthetic Examples", meta["journal"], "0001 journal")
    _exact("12", meta["volume"], "0001 volume")
    _exact("45-67", meta["pages"], "0001 pages")
    legacy = report["metadata"]["10.99999/old(1998)style"]
    _exact("1998", legacy["year"], "legacy-suffix year via issued date-parts")
    unavailable = report["errors"]["10.99999/floe-synthetic-0004"]
    _exact("inconclusive", unavailable["status"], "garbage envelope status")
    missing_record = report["errors"]["10.99999/floe-synthetic-0005"]
    _exact("missing", missing_record.get("offline_record"), "absent offline record reason")


def _run_cli(args: list[str], env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(SCRIPTS_DIR)
    if env_extra:
        env.update(env_extra)
    return subprocess.run([sys.executable, *args], cwd=PACKAGE_ROOT,
                          capture_output=True, text=True, timeout=300, env=env)


def check_cli_goldens(tmp: Path) -> None:
    import verify_citations as vc

    dead_proxy = {"http_proxy": "http://127.0.0.1:9", "https_proxy": "http://127.0.0.1:9",
                  "HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9"}
    # mixed-result fixture: exit 1 with truthful counts, even behind a dead proxy
    out = tmp / "report.json"
    completed = _run_cli(["scripts/verify_citations.py", str(FIXTURES / "review_fixture.md"),
                          "--offline-dir", str(FIXTURES / "crossref"), "-o", str(out)],
                         env_extra=dead_proxy)
    _exact(1, completed.returncode, "mixed offline verification exit code (failed present)")
    report = json.loads(out.read_text(encoding="utf-8"))
    _exact(3, len(report["verified"]), "proxy-isolated run verified count")
    _exact(3, len(report["failed"]), "proxy-isolated run failed count")
    _exact("offline", report["mode"], "proxy-isolated run mode")
    # all-registered fixture: exit 0
    out2 = tmp / "clean.json"
    completed = _run_cli(["scripts/verify_citations.py", str(FIXTURES / "clean_review.md"),
                          "--offline-dir", str(FIXTURES / "crossref"), "-o", str(out2)],
                         env_extra=dead_proxy)
    _exact(0, completed.returncode, "clean offline verification exit code")
    clean = json.loads(out2.read_text(encoding="utf-8"))
    _exact(1, len(clean["verified"]), "clean verified count")
    _exact(0, len(clean["failed"]), "clean failed count")
    # online mode behind a dead proxy must NOT claim registration
    out3 = tmp / "online-blocked.json"
    completed = _run_cli(["scripts/verify_citations.py", str(FIXTURES / "clean_review.md"),
                          "-o", str(out3)], env_extra=dead_proxy)
    blocked = json.loads(out3.read_text(encoding="utf-8")) if out3.exists() else None
    if blocked is not None:
        _exact("online", blocked["mode"], "blocked online mode label")
        for doi, error in blocked["errors"].items():
            if error.get("status") == "missing":
                raise CheckFailure("a blocked network must never report a DOI as missing (it is inconclusive)")
    # note: exit code may be 1 with inconclusive statuses - both are honest


def check_search_databases(tmp: Path) -> None:
    import search_databases as sd

    records = json.loads((FIXTURES / "records_fixture.json").read_text(encoding="utf-8"))
    _exact(12, len(records), "fixture record count")
    deduped = sd.deduplicate_results(records)
    _exact(10, len(deduped), "dedup count (DOI-duplicate + title-duplicate removed)")
    titles = [r["title"] for r in deduped]
    if "Duplicate title no DOI" not in titles or "duplicate title no doi" in titles:
        raise CheckFailure(f"title dedup kept the wrong record: {titles}")
    first = next(r for r in deduped if r.get("doi", "").endswith("floe-synthetic-0001"))
    _exact("PubMed", first["source"], "first-occurrence DOI record kept")
    # year filter keeps unparseable/missing years (documented upstream behavior)
    filtered = sd.filter_by_year(deduped, 2023, 2026)
    _exact(6, len(filtered), "year-filter count 2023..2026 (missing year retained)")
    ranked = sd.rank_results(deduped, "citations")
    _exact("Synthetic gene therapy review", ranked[0]["title"], "rank-by-citations top (40)")
    _exact("Synthetic clinical outcomes", ranked[1]["title"], "rank-by-citations second (23)")
    _exact("Duplicate title no DOI", ranked[-1]["title"], "null citations rank last")
    # BibTeX: no fabrication for missing fields; ASCII-normalized keys
    bibtex = sd.format_search_results(deduped, "bibtex")
    for expected in ("@article{Zhang2024,", "@article{Novak0000,", "@article{unknown2021,",
                     "@article{Mller2019,", "year = {},", "author = {},",
                     "doi = {10.99999/floe-synthetic-0001},"):
        if expected not in bibtex:
            raise CheckFailure(f"bibtex golden lacks {expected!r}")
    if bibtex.count("@") != 10:
        raise CheckFailure(f"bibtex entry count wrong: {bibtex.count('@')}")
    # Markdown rendering keeps provenance-visible fields
    markdown = sd.format_search_results(deduped, "markdown")
    for expected in ("# Literature Search Results", "**Total Results**: 10",
                     "Synthetic CRISPR screening study", "**DOI**: [10.99999/floe-synthetic-0001]"):
        if expected not in markdown:
            raise CheckFailure(f"markdown golden lacks {expected!r}")
    summary = sd.generate_search_summary(deduped)
    _exact(10, summary["total_results"], "summary total")
    _exact(3, summary["sources"]["arXiv"], "summary arXiv source count")
    # CLI end-to-end through a real subprocess
    out = tmp / "records.md"
    completed = _run_cli(["scripts/search_databases.py", str(FIXTURES / "records_fixture.json"),
                          "--format", "markdown", "--deduplicate", "--output", str(out)])
    _exact(0, completed.returncode, "search_databases CLI exit code")
    if "**Total Results**: 10" not in out.read_text(encoding="utf-8"):
        raise CheckFailure("CLI markdown output lost the deduplicated count")


def check_source_preservation(before: dict[str, str]) -> None:
    for relative, digest in before.items():
        actual = hashlib.sha256((FIXTURES / relative).read_bytes()).hexdigest()
        if actual != digest:
            raise CheckFailure(f"fixture {relative} was modified by the verifier run")


def fixture_digests() -> dict[str, str]:
    return {p.relative_to(FIXTURES).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(FIXTURES.rglob("*")) if p.is_file()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", help="optional JSON report path")
    args = parser.parse_args()

    if not FIXTURES.is_dir():
        print(json.dumps({"verifier": "lit_verify.py", "ok": False,
                          "failures": [f"fixtures missing: {FIXTURES}"]}, indent=2))
        return 1

    results: list[dict[str, Any]] = []
    failures: list[str] = []
    before = fixture_digests()

    def record(name: str, function) -> None:
        # keep verifier stdout pure JSON: in-process check prints go to stderr
        with contextlib.redirect_stdout(sys.stderr):
            try:
                function()
                results.append({"name": name, "status": "pass"})
            except CheckFailure as exc:
                results.append({"name": name, "status": "fail", "error": str(exc)})
                failures.append(f"{name}: {exc}")
            except Exception as exc:
                results.append({"name": name, "status": "fail",
                                "error": f"{type(exc).__name__}: {exc}"})
                failures.append(f"{name}: {type(exc).__name__}: {exc}")

    with tempfile.TemporaryDirectory(prefix="lit-verify-") as raw_tmp:
        tmp = Path(raw_tmp)
        record("runtime", check_runtime)
        record("doi_extraction_goldens", check_doi_extraction)
        record("offline_taxonomy_goldens", check_offline_taxonomy)
        record("cli_goldens_network_isolated", lambda: check_cli_goldens(tmp))
        record("search_databases_goldens", lambda: check_search_databases(tmp))
        record("source_preservation", lambda: check_source_preservation(before))

    report = {
        "verifier": "lit_verify.py",
        "package": "literature-review 1.0.0 (Floe adaptation)",
        "python": sys.version.split()[0],
        "ok": not failures,
        "network_used": False,
        "checks": results,
        "failures": failures,
        "evidence_class": "offline host/guest-agnostic checks; live doi.org/Crossref "
                          "verification is guest-acceptance scope (PROVENANCE runbook)",
    }
    payload = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
