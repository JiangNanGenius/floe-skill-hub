# Example Workflow

Illustrative end-to-end recipe, not an executed review. Run from the skill directory; populate the protocol, normalized search records, bibliography, and CSL file before the dependent commands. Dates below are a deliberately historical 2015-2024 interval.

## Example Workflow

Complete workflow for a biomedical literature review:

```bash
# 1. Create review document from template
mkdir -p sources styles
cp assets/review_template.md crispr_sickle_cell_review.md

# 2. Optional supplementary discovery (Floe adaptation: native web.search, no paid account)
#    web.search "CRISPR Cas9 sickle cell disease gene therapy efficacy"
#    web.search "CRISPR sickle cell disease clinical trials treatment"
#    -> save each query, date, tool and result count into sources/ (e.g. sources/litreview_crispr_scd-scoping.md)
#    -> web.fetch specific accessible records (arXiv/PubMed abstract pages) into sources/

# 3. Search specialized databases using appropriate skills
# - Use PubMed E-utilities and bioRxiv/medRxiv search or date-metadata APIs
# - Use direct API access for arXiv, Semantic Scholar
# - Save all pages and counts; document any API caps or failed requests
# - Normalize into a JSON array; keep raw exports and provenance

# 4. Process your normalized combined_results.json; raw API envelopes will fail
python3 scripts/search_databases.py combined_results.json \
  --deduplicate \
  --year-start 2015 \
  --year-end 2024 \
  --format markdown \
  --output search_results.md \
  --summary

# 5. Screen results and extract data
# - Request extracts with --full-content; obtain original reports and record failures
# - Use independent final full-text decisions and retain exclusion reasons
# - Track records, reports, studies, and overlapping participants separately
# - Extract key data into the review document
# - Organize by themes

# 6. Write the review following template structure
# - Introduction with clear objectives
# - Detailed methodology section
# - Results organized thematically
# - Critical discussion
# - Clear conclusions

# 7. Check DOI registration/metadata, then manually verify identity and claim support
python3 scripts/verify_citations.py crispr_sickle_cell_review.md

# Review the citation report
cat crispr_sickle_cell_review_citation_report.json

# Investigate missing/inconclusive results; transient failures do not invalidate citations
python3 scripts/verify_citations.py crispr_sickle_cell_review.md

# 8. Export (Floe adaptation: native app path; the upstream Pandoc/XeLaTeX generate_pdf.py is not bundled)
#    - finalize crispr_sickle_cell_review.md with the reference list as formatted text
#      (BibTeX source: python3 scripts/search_databases.py sources/records.json --format bibtex --output review.bib)
#    - native tool: document.pdf.convert inputPath=crispr_sickle_cell_review.md format=pdf
#      -> crispr_sickle_cell_review.pdf (add document.convert first for a DOCX/HTML intermediate)

# 9. Review final PDF (document.pdf.render page images) and markdown outputs
```
