# Provenance — literature-review (Floe adaptation, 1.0.0)

- Upstream repository: https://github.com/K-Dense-AI/scientific-agent-skills
- Pinned commit: `593377bb048752abb0152deab9fbb1083a6087df` (repository tree `d4d202beb151c1f1c6c15738be0692d65e0447af`; skill subtree `skills/literature-review` tree `abbd5cd9f06e1fb4fae66345a4df790cc34d2ad8`, verified at fetch on 2026-10-26)
- Upstream path: `skills/literature-review`
- License: MIT (root `LICENSE.md` at the pinned commit, Copyright (c) 2025 K-Dense Inc.) — full text at references/licenses/UPSTREAM-LICENSE.txt; per-file audit in references/licenses/LICENSE-NOTE.md
- Retrieval: sparse subtree fetch into task scratch; no full-repo vendoring.
- Adaptation record: references/ADAPTATION-NOTES.md (kept-verbatim / modified / added / excluded, each with reasons).
- Declared dependency layer (floe.json): NONE — both shipped scripts are pure Python standard library (the upstream `requests` dependency was replaced by stdlib urllib). The manifest declares network access for optional online verification and native discovery; offline verification itself performs no network I/O. No paid provider, no API-key prompt: upstream parallel-cli (Parallel account) and OPENROUTER_API_KEY schematics are removed, and discovery uses Floe's own configured web.search/web.fetch/browser surfaces.
- First-release version: 1.0.0 (no previously published id/version exists for this skill; registry versionTarget 1.0.0).

## Host development evidence (NOT guest execution evidence)

Executed 2026-10-26 by the H4 lane, labeled by environment:

1. Debian trixie arm64 dev container (Python 3.13.5 — same interpreter series as the guest; NOT the riscv64 guest): `python3 scripts/lit_verify.py` → exit 0, `"ok": true`, 6/6 checks: DOI extraction goldens (legacy parenthesized suffix, URL/doi: normalization, prose-punctuation stripping, dedup), full offline taxonomy (registered+retrieved with exact fetched fields; registered/metadata-unavailable; missing; inconclusive garbage envelope; absent offline record; invalid syntax), CLI goldens re-run behind a DEAD PROXY (http(s)_proxy → 127.0.0.1:9) proving offline mode performs no network I/O and blocked online runs never claim `missing`, search_databases dedup(12→10)/rank/year-filter/BibTeX-no-fabrication/Markdown goldens, whole-run fixture preservation.
2. Bare macOS venv (Python 3.12.13, stdlib only): `lit_verify.py` → exit 0, ok:true (package is stdlib-only; no layer to miss).
3. One real fixture defect was caught by the verifier itself and fixed at the source: prose containing a bare `10.99999/` prefix produced a spurious DOI candidate (the extractor's documented prose ambiguity) — the fixture prose was rewritten; the original failure log is preserved in the lane evidence.

## GUEST-PENDING handoff for Main (exact steps; do not flip evidence without a real passing run)

In a task workspace in the resolved Linux environment, with this package installed/staged:

1. No dependency provisioning is required (stdlib only).
2. `exec.shell`: `python3 scripts/lit_verify.py --output verify.json` → must exit 0 with `"ok": true`.
3. Online acceptance (guest network egress; confirm egress policy for doi.org + api.crossref.org first):
   `python3 scripts/verify_citations.py assets/fixtures/online_acceptance.md -o online_report.json`
   → exit 0; online_report.json shows mode `online`, 1 registered DOI (10.48550/arxiv.2609.00065); the 2026-10-26 live probe returned Handle responseCode 1 but Crossref HTTP 404, so expect metadata_status `unavailable` and no fabricated title — or, if egress is disallowed, the equivalent OFFLINE flow: fetch `https://doi.org/api/handles/10.48550/arXiv.2609.00065` and `https://api.crossref.org/works/10.48550/arXiv.2609.00065` with the native web.fetch/network.http tools into `sources/crossref/10.48550%2Farxiv.2609.00065.json` ({"handle_response": …, "crossref_works": …}) and re-run with `--offline-dir sources/crossref` → same taxonomy, no guest egress.
4. Real workload: one small authorized review markdown with ≥2 real DOIs, verified through the offline flow; keep report.json as evidence.
5. Only after 2–4 pass in the actual guest may `plannedRuntime.execution.evidence` become `guest-verified` and `status.executionVerified` flip. Native PDF-export acceptance (document.convert + document.pdf.convert over a completed review.md) is App-side, Main-owned.

## File inventory (sha256, this checkout; PROVENANCE.md self-hash intentionally omitted)

- `SKILL.md` sha256 `e4b00da02014b74a8920ae5137d6b45087ea9e55d8f5f7ad5be34e010d5e2575` (10540 bytes)
- `assets/fixtures/README.md` sha256 `d06409eff74242574ee0f28272c83d18cf799b9d9300190ef62bd062a2fe6a35` (1687 bytes)
- `assets/fixtures/clean_review.md` sha256 `1cac8f398d517b7234caca33927eaa5ecae64b0432c2e5a6f8ac0b3ab84aac6f` (103 bytes)
- `assets/fixtures/crossref/10.99999%2Ffloe-synthetic-0001.json` sha256 `7e9b04738ac17e1230d692bcc54ea25e78dad36593a1154b12bb78ee870e2122` (938 bytes)
- `assets/fixtures/crossref/10.99999%2Ffloe-synthetic-0002.json` sha256 `2232cbef4fcd8e3dce8e8cd1a38f2bca99e48d34608508dceb1714b9faca635b` (98 bytes)
- `assets/fixtures/crossref/10.99999%2Ffloe-synthetic-0003.json` sha256 `2186d819794635466d2da7d560f38b97f3bd696db96309d592911a31a8c8d6df` (100 bytes)
- `assets/fixtures/crossref/10.99999%2Ffloe-synthetic-0004.json` sha256 `39d60f976147b1604d2a2006d6136407bb3a6d9e45383111d4356ab57ba28834` (20 bytes)
- `assets/fixtures/crossref/10.99999%2Fold%281998%29style.json` sha256 `c3e0c8f77b852de6c9df38b4673a009ea7bac4993fa5c56cfc4c6d9763503c5a` (557 bytes)
- `assets/fixtures/online_acceptance.md` sha256 `64f0f0ebe37e430f24eec7b4ee1e5e3298b04f70f2218e64aa22dbafbbe48301` (669 bytes)
- `assets/fixtures/records_fixture.json` sha256 `9281640c38c843ac3e0be65b161448d5ce3864e373a48dfc5dd6a998229005a3` (2384 bytes)
- `assets/fixtures/review_fixture.md` sha256 `521718c2bd77b6701cfa9c77bc6d18b258e3f32f15db56db9c12ce299434df25` (929 bytes)
- `assets/review_template.md` sha256 `08671516976d01a7004f8ae7c944a50c253877504720c15d5fa24eed90889819` (13769 bytes)
- `floe.json` sha256 `49a2c6cede41c678f9f3f2d7f6b301bde1a77e3ae68840e9340361867a46165e` (231 bytes)
- `references/ADAPTATION-NOTES.md` sha256 `cb8e8504b606bbeaed724771dccb81b001b190bd7ca29ad698cdef2ae5652d0d` (5550 bytes)
- `references/citation_styles.md` sha256 `7418dd833879a84ced9a3bcafc04adaba5ff6b712ec4f9a1c420baa858198246` (7819 bytes)
- `references/core_workflow.md` sha256 `3834334d46e578bdde39fa973223ec691b2f480f84b7de1f57fed7d04be83dea` (11577 bytes)
- `references/database_strategies.md` sha256 `24b56cd88128a9016520ed6b5e2abb79e19dc9b86cbf064927e9056aa1504f48` (10431 bytes)
- `references/example_workflow.md` sha256 `e3aed8ab79b4cd87d12752e71452fb841ef61a74145542af37bc4d3d348ddcec` (3041 bytes)
- `references/licenses/LICENSE-NOTE.md` sha256 `5d6a2864669ffd5b6d070dcad8307584a6468a0a544362438c77271cf1b0482b` (1299 bytes)
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `09b02a3c9df3053c55531d503357a9c7cde275970e6c3ceaa1ddf5f0e90b40c1` (1068 bytes)
- `references/search_and_citation.md` sha256 `e5afbc432c3e2efcd8cd419f34550b1af6ca58e04b401d8ac71893f2bdee77b4` (5116 bytes)
- `scripts/lit_verify.py` sha256 `1823ebfd2146928ea12e8f1e59284c205b2abca75ba31328b2534ff6b6a0d67c` (13723 bytes)
- `scripts/search_databases.py` sha256 `76f47fd18ca28df4985ffc6d30d5ad659e67c8058bb3de8f385c2443752f4eaf` (8769 bytes)
- `scripts/verify_citations.py` sha256 `ea73d5ab42ff46a3de2bf8c8358600996385e1826fafbe6a5a8c18fc6df0b878` (15838 bytes)

TOTAL 24 files, 116256 bytes

## Coordinator online fixture correction

The first runbook incorrectly required retrieved Crossref metadata for an arXiv DOI and used a mixed-case offline filename. Direct Handle/Crossref read-back found registered/404 respectively. The script already distinguishes registration from metadata availability; only the acceptance expectation, normalized lower-case record filename and declared network capability changed. Original runbooks/probe receipts are retained privately; no execution claim was promoted.
