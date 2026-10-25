#!/usr/bin/env python3
"""Golden verifier for the Floe markitdown adaptation.

First-party Floe script (MIT (c) Floe project). One offline command proves
that the bundled guest converters produce REAL Markdown from the bundled
synthetic fixtures in the CURRENT environment, that every refusal path
stays honest, and that source files are preserved byte-for-byte:

  * exact-output goldens for XLSX (declared openpyxl layer, incl. the
    no-cached-formula-value warning), PPTX (stdlib OOXML extraction with
    slide order, table and speaker notes), extractable PDF (declared
    pdfminer layer, page-accurate markers), CSV/TSV/JSON/TXT (stdlib);
  * honest refusals: scanned/text-less PDFs route to the native OCR
    workflow, encrypted PDFs route to the native PDFKit unlock/convert
    flow (protection never bypassed, password never echoed), NaN JSON
    rejected by strict parsing, DOCX/HTML/RTF/images return native-route
    receipts naming the exact Floe tool, audio is unsupported, unknown
    extensions fail closed;
  * safety negatives: symlink, out-of-root, byte-cap and overwrite
    refusals;
  * receipt truth: source/output SHA-256 and character counts recomputed
    and compared; every fixture re-hashed after the whole run to prove
    source preservation;
  * batch CLI end-to-end with a truthful manifest (converted/native-route/
    skipped counts and per-record digests).

Declared-layer checks (XLSX/PDF) are skipped honestly when openpyxl/
pdfminer are absent and required via --require-layer. Exit 0 only when
every required check passes. No network; writes only to an ephemeral
temp directory.
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

DECLARED_PINS = {"openpyxl": "3.1.5", "pdfminer.six": "20221105"}

# Exact expected Markdown for the bundled synthetic fixtures (captured from
# the pinned engines during adaptation and asserted byte-for-byte here).
EXPECTED = {
    "sample.csv": "| id | name | score |\n| --- | --- | --- |\n| 1 | 合成记录 | 3.5 |\n| 2 | plain row | 4.25 |",
    "sample.tsv": "| id | value |\n| --- | --- |\n| 1 | 7.5 |\n| 2 | 8.25 |",
    "sample.json": '```json\n{\n  "title": "Floe synthetic JSON",\n  "values": [\n    1,\n    2.5,\n    3\n  ],\n  "meta": {\n    "synthetic": true\n  }\n}\n```\n',
    "sample.txt": "Floe synthetic plain text fixture.\nSecond line 中文.\n",
    "sample.xlsx": (
        "## Sheet: Data\n\n"
        "| 名称 | 值 | note |\n| --- | --- | --- |\n"
        "| alpha | 1.5 | ok |\n| beta | 2.25 | 含中文备注 |\n| gamma |  |  |\n\n"
        "## Sheet: 测量\n\n| t (s) | x (mmol/L) |\n| --- | --- |\n| 0 | 5 |\n| 1 | 12.5 |\n"
    ),
    "sample.pptx": (
        "## Slide 1\n\nFloe 合成演示 Fixture\n\n- Second bullet line\n\n"
        "| 格式 | 路径 |\n| --- | --- |\n| XLSX | guest openpyxl |\n| PDF | native first |\n\n"
        "**Speaker notes:**\n\n> 演讲者备注：合成夹具 slide one notes\n\n"
        "## Slide 2\n\nPlain ASCII conclusion slide\n\n"
    ),
    "sample.pdf": "<!-- page 1 -->\n\nFloe synthetic PDF fixture 42\nsecond line\n",
}


class CheckFailure(Exception):
    """One failed golden/safety check with an actionable message."""


class LayerMissing(Exception):
    def __init__(self, missing: list[str]):
        super().__init__("missing: " + ", ".join(missing))
        self.missing = missing


def _exact(reference: Any, candidate: Any, label: str) -> None:
    if candidate != reference:
        raise CheckFailure(f"{label}: expected exactly {reference!r}, got {candidate!r}")


def _base_version(raw: str) -> str:
    return raw.split("+", 1)[0].split("-", 1)[0]


def check_runtime() -> None:
    if sys.version_info < (3, 11):
        raise CheckFailure(
            f"Python {sys.version_info.major}.{sys.version_info.minor} is below the "
            "required 3.11 (the resolved Floe Linux guest provides 3.13)")


def check_layer_versions(results: list[dict[str, Any]]) -> None:
    import md_converters

    versions = md_converters.engine_versions()
    detail = {}
    missing = []
    mapping = {"openpyxl": "openpyxl", "pdfminer.six": "pdfminer.six"}
    for name, pin in DECLARED_PINS.items():
        installed = versions.get(mapping[name])
        if installed is None:
            missing.append(name)
            detail[name] = {"installed": None, "declared_pin": pin}
            continue
        match = _base_version(installed) == pin
        detail[name] = {"installed": installed, "declared_pin": pin,
                        "pin_matches_base_version": match}
        if not match:
            raise CheckFailure(
                f"{name} installed {installed} does not match declared pin {pin}")
    results.append({"name": "layer_versions", "status": "pass", "detail": detail})
    if missing:
        raise LayerMissing(missing)


def _convert(fixture: str, tmp: Path):
    import md_converters

    source = md_converters.checked_input_file(fixture, root=FIXTURES)
    output = tmp / f"{fixture}.md"
    receipt = md_converters.convert_file(source, output)
    return receipt, output


def _assert_receipt_truth(receipt, output: Path, fixture: str, tmp: Path) -> str:
    import md_converters

    if receipt.status != "converted":
        raise CheckFailure(f"{fixture}: expected converted, got {receipt.status}: {receipt.error}")
    body = output.read_text(encoding="utf-8")
    source_bytes = (FIXTURES / fixture).read_bytes()
    _exact(hashlib.sha256(source_bytes).hexdigest(), receipt.source_sha256,
           f"{fixture}: receipt source sha256")
    _exact(hashlib.sha256(body.encode("utf-8")).hexdigest(), receipt.output_sha256,
           f"{fixture}: receipt output sha256")
    _exact(len(body), receipt.characters, f"{fixture}: receipt characters")
    _exact(True, receipt.source_preserved, f"{fixture}: source preserved flag")
    if not body.strip():
        raise CheckFailure(f"{fixture}: conversion produced empty markdown")
    return body


def check_stdlib_goldens(tmp: Path) -> None:
    for fixture in ("sample.csv", "sample.tsv", "sample.json", "sample.txt", "sample.pptx"):
        receipt, output = _convert(fixture, tmp)
        body = _assert_receipt_truth(receipt, output, fixture, tmp)
        _exact(EXPECTED[fixture], body, f"{fixture} exact markdown golden")
    # PPTX specifics: slide order, table, notes, CJK
    body = (tmp / "sample.pptx.md").read_text(encoding="utf-8")
    for marker in ("## Slide 1", "## Slide 2", "**Speaker notes:**", "Floe 合成演示 Fixture"):
        if marker not in body:
            raise CheckFailure(f"pptx golden lost {marker!r}")
    if body.index("## Slide 1") > body.index("## Slide 2"):
        raise CheckFailure("pptx slide order is wrong")
    # strict JSON rejects NaN
    bad = tmp / "bad.json"
    bad.write_text('{"v": NaN}', encoding="utf-8")
    import md_converters
    receipt = md_converters.convert_file(bad, tmp / "bad.json.md")
    _exact("failed", receipt.status, "NaN JSON must fail")
    if "strict" not in (receipt.error or ""):
        raise CheckFailure(f"NaN JSON refusal must cite strict parsing: {receipt.error}")


def check_layer_goldens(tmp: Path) -> None:
    # XLSX: exact golden + the honest no-cached-formula warning
    receipt, output = _convert("sample.xlsx", tmp)
    body = _assert_receipt_truth(receipt, output, "sample.xlsx", tmp)
    _exact(EXPECTED["sample.xlsx"], body, "sample.xlsx exact markdown golden")
    if not any("formula cell(s) carry no cached value" in w for w in receipt.warnings):
        raise CheckFailure(f"xlsx must warn about uncached formula cells: {receipt.warnings}")
    # PDF: exact golden, page-accurate markers
    receipt, output = _convert("sample.pdf", tmp)
    body = _assert_receipt_truth(receipt, output, "sample.pdf", tmp)
    _exact(EXPECTED["sample.pdf"], body, "sample.pdf exact markdown golden")
    _exact(1, body.count("<!-- page"), "pdf page markers must equal the real page count")
    # scanned/text-less PDF routes to native OCR honestly
    receipt, _ = _convert("notext.pdf", tmp)
    _exact("failed", receipt.status, "text-less PDF must fail")
    for marker in ("scanned", "image.ocr"):
        if marker not in (receipt.error or ""):
            raise CheckFailure(f"text-less PDF refusal must route to OCR ({marker!r}): {receipt.error}")
    # encrypted PDF routes to the native PDFKit flow; password never echoed
    receipt, _ = _convert("encrypted.pdf", tmp)
    _exact("failed", receipt.status, "encrypted PDF must fail")
    for marker in ("protected", "document.pdf.unlock"):
        if marker not in (receipt.error or ""):
            raise CheckFailure(f"encrypted PDF refusal must route to native unlock ({marker!r}): {receipt.error}")
    if "floe-fixture" in json.dumps(receipt.as_dict(), ensure_ascii=False):
        raise CheckFailure("receipts must never echo password material")


def check_native_routes(tmp: Path) -> None:
    import md_converters

    cases = {
        "fake.docx": ("native-route", "document.convert"),
        "fake.html": ("native-route", "document.convert"),
        "fake.rtf": ("native-route", "document.convert"),
        "photo.png": ("native-route", "image.ocr"),
        "clip.mp3": ("unsupported", "transcription"),
        "mystery.xyz": ("unsupported", "fail closed"),
    }
    for name, (status, marker) in cases.items():
        path = tmp / name
        path.write_bytes(b"arbitrary bytes; routing is by declared extension, content is never sniffed")
        receipt = md_converters.convert_file(path, tmp / (name + ".md"))
        _exact(status, receipt.status, f"{name} status")
        haystack = json.dumps(receipt.as_dict(), ensure_ascii=False)
        if marker.lower() not in haystack.lower():
            raise CheckFailure(f"{name} receipt must name {marker!r}: {haystack[:200]}")
        if receipt.status == "native-route" and (tmp / (name + ".md")).exists():
            raise CheckFailure(f"{name}: native-route must not write a guest output file")


def check_safety_negatives(tmp: Path) -> None:
    import md_converters
    from md_converters import ConversionError

    root = tmp / "root"
    (root / "in").mkdir(parents=True)
    inside = root / "in" / "table.csv"
    inside.write_text("a,b\n1,2\n", encoding="utf-8")
    outside = tmp / "outside.csv"
    outside.write_text("a,b\n1,2\n", encoding="utf-8")
    # out-of-root
    try:
        md_converters.checked_input_file("../outside.csv", root=root)
    except ConversionError:
        pass
    else:
        raise CheckFailure("out-of-root input must be rejected")
    # symlink
    os.symlink(outside, root / "in" / "link.csv")
    try:
        md_converters.checked_input_file("in/link.csv", root=root)
    except ConversionError:
        pass
    else:
        raise CheckFailure("symlinked input must be rejected")
    # byte cap
    try:
        md_converters.checked_input_file("in/table.csv", root=root, max_bytes=4)
    except ConversionError:
        pass
    else:
        raise CheckFailure("byte cap must be enforced")
    # overwrite refusal at converter-CLI level
    out = root / "in" / "table.csv.md"
    out.write_text("existing", encoding="utf-8")
    code = _run_cli(["scripts/md_convert.py", "in/table.csv", "--root", str(root),
                     "--output", "in/table.csv.md"])
    _exact(2, code, "overwrite without --force must exit 2")
    code = _run_cli(["scripts/md_convert.py", "in/table.csv", "--root", str(root),
                     "--output", "in/table.csv.md", "--force"])
    _exact(0, code, "conversion with --force must exit 0")


def _run_cli(args: list[str], cwd: Path | None = None) -> int:
    completed = subprocess.run(
        [sys.executable, *args], cwd=cwd or PACKAGE_ROOT, capture_output=True,
        text=True, timeout=300,
        env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
             "HOME": str(Path.home()), "PYTHONIOENCODING": "utf-8"})
    return completed.returncode


def check_cli_exit_codes(tmp: Path) -> None:
    work = tmp / "cli"
    work.mkdir()
    for name in ("sample.csv", "sample.pdf", "notext.pdf"):
        (work / name).write_bytes((FIXTURES / name).read_bytes())
    (work / "fake.docx").write_bytes(b"not a real docx")
    _exact(0, _run_cli(["scripts/md_convert.py", "sample.csv", "--root", str(work),
                        "--output", "sample.csv.md"]), "md_convert success exit code")
    _exact(4, _run_cli(["scripts/md_convert.py", "fake.docx", "--root", str(work),
                        "--output", "fake.docx.md"]), "md_convert native-route exit code")
    _exact(1, _run_cli(["scripts/md_convert.py", "notext.pdf", "--root", str(work),
                        "--output", "notext.pdf.md"]), "md_convert failed exit code")


def check_batch_manifest(tmp: Path) -> None:
    work = tmp / "batch"
    (work / "in" / "nested").mkdir(parents=True)
    out = work / "out"
    (work / "in" / "sample.csv").write_bytes((FIXTURES / "sample.csv").read_bytes())
    (work / "in" / "nested" / "sample.tsv").write_bytes((FIXTURES / "sample.tsv").read_bytes())
    (work / "in" / "fake.docx").write_bytes(b"not a real docx")
    os.symlink(work / "in" / "sample.csv", work / "in" / "link.csv")
    manifest = work / "manifest.json"
    code = _run_cli(["scripts/md_batch.py", str(work / "in"), str(out), "--recursive",
                     "--manifest", str(manifest)])
    _exact(0, code, "batch exit code")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    counts = payload["counts"]
    _exact(2, counts["converted"], "batch converted count (csv + nested tsv)")
    _exact(1, counts["native-route"], "batch native-route count (docx)")
    _exact(1, counts["skipped"], "batch skipped count (symlink)")
    records = {r["source"]: r for r in payload["records"]}
    if "link.csv" not in records or records["link.csv"]["status"] != "skipped":
        raise CheckFailure("symlink must appear as skipped in the manifest")
    nested = records.get("nested/sample.tsv")
    if nested is None or nested["status"] != "converted":
        raise CheckFailure(f"nested file missing from manifest: {sorted(records)}")
    if not (out / "nested" / "sample.tsv.md").is_file():
        raise CheckFailure("batch must preserve relative directories")
    # receipt truth inside the manifest
    for record in payload["records"]:
        if record["status"] != "converted":
            continue
        source = work / "in" / record["source"]
        _exact(hashlib.sha256(source.read_bytes()).hexdigest(), record["source_sha256"],
               f"manifest source digest {record['source']}")
        output = out / record["output"]
        _exact(hashlib.sha256(output.read_bytes()).hexdigest(), record["output_sha256"],
               f"manifest output digest {record['source']}")
        _exact(True, record["source_preserved"], f"manifest source preservation {record['source']}")
    # rerun without --overwrite skips existing outputs
    payload2_path = work / "manifest2.json"
    code = _run_cli(["scripts/md_batch.py", str(work / "in"), str(out), "--recursive",
                     "--manifest", str(payload2_path)])
    _exact(0, code, "batch rerun exit code")
    second = json.loads(payload2_path.read_text(encoding="utf-8"))
    _exact(0, second["counts"]["converted"], "rerun must convert nothing new")
    if second["counts"]["skipped"] < 3:
        raise CheckFailure(f"rerun must skip existing outputs: {second['counts']}")


def check_source_preservation(before: dict[str, str]) -> None:
    for name, digest in before.items():
        actual = hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest()
        if actual != digest:
            raise CheckFailure(f"fixture {name} was modified by the verifier run")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--require-layer", action="store_true",
                        help="fail when the declared openpyxl/pdfminer layer is absent")
    parser.add_argument("--output", help="optional JSON report path")
    args = parser.parse_args()

    if not FIXTURES.is_dir():
        print(json.dumps({"verifier": "md_verify.py", "ok": False,
                          "failures": [f"fixtures directory missing: {FIXTURES}"]}, indent=2))
        return 1

    results: list[dict[str, Any]] = []
    failures: list[str] = []
    fixture_digests = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in sorted(FIXTURES.iterdir()) if p.is_file()}

    def record(name: str, function) -> None:
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

    with tempfile.TemporaryDirectory(prefix="md-verify-") as raw_tmp:
        tmp = Path(raw_tmp)
        record("runtime", check_runtime)
        layer_status = "pass"
        try:
            layer_results: list[dict[str, Any]] = []
            check_layer_versions(layer_results)
            results.extend(layer_results)
        except LayerMissing as exc:
            layer_status = "missing"
            results.append({"name": "layer_versions", "status": "missing", "detail": str(exc)})
            if args.require_layer:
                failures.append(f"layer_versions: declared layer not provisioned ({exc})")
        except CheckFailure as exc:
            layer_status = "fail"
            results.append({"name": "layer_versions", "status": "fail", "error": str(exc)})
            failures.append(f"layer_versions: {exc}")

        record("stdlib_goldens", lambda: check_stdlib_goldens(tmp))
        if layer_status == "pass":
            record("layer_goldens_xlsx_pdf", lambda: check_layer_goldens(tmp))
        else:
            results.append({"name": "layer_goldens_xlsx_pdf",
                            "status": f"skipped ({layer_status} layer)"})
        record("native_routes", lambda: check_native_routes(tmp))
        record("safety_negatives", lambda: check_safety_negatives(tmp))
        record("cli_exit_codes", lambda: check_cli_exit_codes(tmp))
        record("batch_manifest", lambda: check_batch_manifest(tmp))
        record("source_preservation", lambda: check_source_preservation(fixture_digests))

    report = {
        "verifier": "md_verify.py",
        "package": "markitdown 1.0.0 (Floe adaptation)",
        "python": sys.version.split()[0],
        "ok": not failures,
        "layer_required": bool(args.require_layer),
        "declared_pins": DECLARED_PINS,
        "checks": results,
        "failures": failures,
        "evidence_class": "runs wherever executed; guest execution evidence requires a real run in the resolved Linux environment",
    }
    payload = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
