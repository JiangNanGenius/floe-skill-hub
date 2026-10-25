# Bundled fixtures — literature-review (Floe adaptation)

All files here are SMALL SYNTHETIC fixtures authored for this Floe release
(first-party, MIT (c) Floe project), with ONE documented exception.

- `records_fixture.json` — 12 normalized search records: a DOI duplicate
  (URL form + case variance), a title duplicate among DOI-less records,
  a missing-year record, a missing-author record, null citations, and a
  non-ASCII author name exercising the BibTeX key normalization. Synthetic
  10.99999-prefix DOIs; no real papers.
- `review_fixture.md` — mini review text citing only synthetic DOIs,
  exercising extraction edge cases: `doi:` prefix, `https://doi.org/` URL,
  legacy parenthesized suffix `10.99999/old(1998)style`, trailing
  punctuation, and repeat citations (dedup).
- `clean_review.md` — one registered synthetic citation (CLI exit-0 golden).
- `crossref/` — offline verification envelopes, named
  `<percent-encoded-doi>.json`: full Handle+Crossref record (0001),
  handle-only (0002 → metadata unavailable), `responseCode: 100` (0003 →
  missing), garbage envelope (0004 → inconclusive), legacy-parenthesis
  percent-encoded filename, and one DELIBERATELY ABSENT record (0005 →
  inconclusive, offline_record missing).
- `online_acceptance.md` — THE EXCEPTION: carries one REAL public DOI
  (10.48550/arXiv.2609.00065, the upstream Scientific Agent Skills paper).
  Used ONLY in the optional guest network-egress acceptance step; never in
  offline goldens; makes no claim about any other paper.

`scripts/lit_verify.py` embeds the expected results for all of the above
and re-hashes every fixture after the run to prove source preservation.
