# Adaptation notes — literature-review 1.0.0 (Floe)

Upstream: K-Dense-AI/scientific-agent-skills `skills/literature-review`
at commit `593377bb048752abb0152deab9fbb1083a6087df` (MIT).

## Shipped verbatim (audited)

- `scripts/search_databases.py` — pure-stdlib normalized-record processor (dedup/rank/year-filter/summary; JSON/Markdown/BibTeX rendering; refuses raw provider envelopes). No network, no subprocess, no eval; missing fields render empty (no fabrication). Audited and shipped unchanged.
- `references/database_strategies.md` — database request syntax/limits guidance (public APIs, no paid CLI dependency).
- `assets/review_template.md` — review document template (no removed-service references found at pin).

## Modified (upstream MIT content, changes recorded)

- `scripts/verify_citations.py` — DOI taxonomy, retry/backoff discipline, rate-limit throttling and honesty rules preserved 1:1. Floe changes: (1) `requests` dependency REPLACED by stdlib `urllib.request` (the package now declares zero Python dependencies); (2) NEW `--offline-dir` mode verifying against Handle/Crossref JSON records the agent fetched with native `web.fetch`/`network.http` into the workspace — the preferred Floe path with no guest network egress; (3) report carries `mode` and offline-specific statuses (`offline_record: missing/unreadable/malformed` → inconclusive, never registered); (4) `invalid_syntax` bucket surfaced in the report; (5) module docstring records the adaptation.
- `references/core_workflow.md` — Phase 1/2 parallel-web (paid `parallel-cli`) discovery replaced by Floe native `web.search`/`web.fetch`/browser guidance with the same record-everything discipline; Phase 7 Pandoc/XeLaTeX `generate_pdf.py` export replaced by the native `document.convert` + `document.pdf.convert` path, with the CSL-typesetting limitation stated explicitly; all other methodology text unchanged.
- `references/search_and_citation.md` — "Supplementary web search" section rewritten from Parallel CLI 0.9.3 (paid account, `PARALLEL_API_KEY`) to the native tool surfaces; "Rendering references" Pandoc block replaced by the native export route and honest CSL limitation; source-verification guidance (Handle proxy + Crossref REST) preserved.
- `references/example_workflow.md` — the two `parallel-cli search` steps replaced by native `web.search`/`web.fetch` recording steps; `generate_pdf.py` step replaced by the native export steps; `python` → `python3`.
- `references/citation_styles.md` — the Pandoc resource line re-labeled: CSL semantics remain a formatting reference, with an explicit note that no CSL processor is bundled or provisioned in this release.
- `SKILL.md` — rewritten around the Floe runtime (native search/fetch surfaces, offline-first verification, native PDF export, stdlib-only scripts, guest-pending execution evidence); upstream methodology substance (seven phases, records/reports/studies, PRISMA reconciliation, citation-honesty rules, pitfalls) preserved; K-Dense attribution and citation request preserved.

## Added (first-party Floe, MIT (c) Floe project)

- `scripts/lit_verify.py` — fully offline golden verifier: DOI-extraction goldens (legacy parenthesized suffixes, doi.org/`doi:` normalization, prose-punctuation stripping, dedup), the complete offline taxonomy over synthetic fixtures (registered+retrieved with exact fetched fields / registered-metadata-unavailable / missing / inconclusive envelope / absent record / invalid syntax), a network-isolation proof (identical results behind a dead proxy; a blocked online run never claims `missing`), search_databases dedup/rank/filter/BibTeX/Markdown goldens including no-fabrication assertions (`year = {},`, `author = {},`, ASCII-normalized keys), CLI exit-code goldens and whole-run fixture preservation re-hashing.
- `assets/fixtures/` — SYNTHETIC, clearly labeled: `records_fixture.json` (12 normalized records with a DOI duplicate, a title duplicate, missing year/author cases), `review_fixture.md` (synthetic 10.99999-prefix DOIs only), `clean_review.md`, `online_acceptance.md` (the single REAL DOI — the upstream skills paper — used only in the optional guest online-egress step), `crossref/*.json` offline envelopes (full record, handle-only, responseCode 100, garbage, percent-encoded legacy-parenthesis filename, one deliberately absent), `README.md`.
- `references/PROVENANCE.md`, `references/ADAPTATION-NOTES.md`, `references/licenses/*`.

## Excluded (audited, with reasons — recorded, not silently dropped)

- `scripts/generate_pdf.py` — subprocess-driven Pandoc/XeLaTeX pipeline; neither tool is provisioned in the guest and host-side subprocess toolchain calls are out of the runtime contract. PDF delivery reuses the app's supported export path (native `document.convert`/`document.pdf.convert`).
- `scripts/generate_schematic.py`, `scripts/generate_schematic_ai.py` — require `OPENROUTER_API_KEY` and a fixed paid image/chat model API (`google/gemini-*` via OpenRouter). Prohibited for this release (no hardcoded paid provider or key prompts); conceptual schematics are declared NOT a review prerequisite. Deterministic PRISMA-style figures can be produced via the scientific-visualization skill when its layer is provisioned.
- `parallel-web-tools[cli]` (Parallel) dependency and `PARALLEL_API_KEY` — paid provider CLI replaced by Floe's configured search/web/browser surfaces.
- `requests` dependency — replaced by stdlib urllib so the package declares zero Python dependencies (honest minimal layer).
