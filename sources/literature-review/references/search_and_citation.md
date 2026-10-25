# Search, citation chaining, and source verification

Use [database_strategies.md](database_strategies.md) for current request syntax,
authentication, response shapes, and paging limits. Commands below are
illustrative discovery recipes, not executed searches or complete corpora.

## Supplementary web search (Floe native tools)

Floe adaptation: the upstream Parallel CLI (paid provider account,
`PARALLEL_API_KEY`) is REPLACED by the app's own configured search and
retrieval surfaces — no extra CLI is installed and no provider-specific key
is requested by this skill:

- `web.search` — the user's configured public web search for scoping and
  supplementary discovery; ranked results are a sample, never a complete
  retrieval.
- `web.fetch` — retrieve one accessible URL's text content (for example an
  arXiv abstract page or an open-access paper) into the task workspace.
- `browser.navigate` + `browser.observe`/`browser.get` — the unobtrusive
  controlled browser for pages that need real rendering; explicit user
  interaction only via `browser.interact` when the task authorizes it.

Record every query, tool, date and result count as you go (the reproducibility
rule is unchanged). Save fetched content and provenance into the task
workspace `sources/` directory with the workspace file tools.

A search tool's result cap is a limit on ranked returned hits, not the database total.
Unavailable or truncated web extraction still requires retrieval from the original source. Save the URL, extraction
status, date, and exact text supporting each inference. Never report a title,
web excerpt, or machine summary as if the full paper was assessed.

## Citation chaining

- **Forward:** use Google Scholar Cited by or documented Semantic Scholar /
  OpenAlex citation queries. Search-engine queries such as "papers citing ..."
  are supplementary leads, not complete forward-citation exports.
- **Backward:** inspect reference lists of eligible reports and relevant reviews;
  retrieve candidate records and apply the same eligibility criteria.
- Track seed papers, tools, dates, retrieved counts, and screening decisions.
  Link preprint, journal, protocol, and follow-up reports to a study ID before
  synthesis. Citation-count thresholds and journal prestige are not eligibility
  rules; recent and negative studies must have an equal chance of inclusion.

## DOI checks and bibliographic identity

```bash
python scripts/verify_citations.py review.md --output review_citation_report.json
```

Optional `--email` supplies a real contact to the Crossref polite pool. The
helper extracts unique DOI candidates, URL-encodes them, and checks
`GET https://doi.org/api/handles/{doi}`. Registration requires a successful
Handle `responseCode=1` and matching identifier, not HTTP 200 alone. It then
requests `GET https://api.crossref.org/works/{doi}` and checks metadata identity.
These public singleton reads require no key or pagination.

Read the report's `verified` as **registration confirmed**, `failed` as
**unresolved/missing/inconclusive**, and `metadata_unavailable` as **manual
metadata follow-up needed**. Transient errors and throttling are not proof of
fabrication. Crossref does not cover every registration agency. The script
preserves the original Crossref message and full author list; its compatibility
formatting methods are previews, not compliant APA or Nature output.

DOI extraction is heuristic: inspect ambiguous trailing punctuation and older
suffixes with parentheses. Citations without DOIs require manual verification.
Check titles, authors, year, version, correction/retraction notices, and that
the source actually supports the cited statement. Registered identifiers and
accessible URLs do not establish those properties.

Sources: [Handle proxy API](https://www.handle.net/proxy_servlet.html),
[Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/).

## Rendering references

Use complete metadata in BibTeX/CSL JSON and a current, venue-appropriate CSL
file. See [citation_styles.md](citation_styles.md).

Floe adaptation: the upstream Pandoc/XeLaTeX citation-rendering pipeline is
REPLACED by the app's supported export path — finalize the review as Markdown
(with the bibliography rendered as plain formatted reference text by the
model or from BibTeX via `scripts/search_databases.py --format bibtex`), then:

1. `document.convert` (native) if an intermediate DOCX/HTML deliverable is wanted;
2. `document.pdf.convert` (native) Markdown → paginated PDF for the PDF deliverable.

CSL-processor-grade citation typesetting (Pandoc `[@key]` + `.csl`) is NOT
available in this release; formatted reference lists must be assembled
directly in the Markdown text and checked against the destination journal's
instructions.

Inspect the exported PDF (`document.pdf.render` page images or a PDF viewer) and match
in-text citations to the bibliography; manually verify formatting against the
destination journal's instructions. Unresolved citation keys are your responsibility to catch — the native export does not process `[@key]` syntax.
