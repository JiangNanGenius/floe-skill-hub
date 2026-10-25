# Provenance — citation-management

- Upstream repository: https://github.com/K-Dense-AI/scientific-agent-skills
- Pinned commit: `593377bb048752abb0152deab9fbb1083a6087df` (tree `d4d202beb151c1f1c6c15738be0692d65e0447af` verified at fetch)
- Upstream path: `skills/citation-management`
- License: MIT (root `LICENSE.md` at the pinned commit, Copyright (c) 2025 K-Dense Inc.) — full text at references/licenses/UPSTREAM-LICENSE.txt
- Subtree-only fetch into task scratch on 2026-10-26; no full-repo vendoring.
- Kept: references/*.md (13 files; script_reference.md edited: Google-Scholar section replaced by exclusion note); assets/bibtex_template.bib; assets/citation_checklist.md; scripts/_common.py, doi_to_bibtex.py, extract_metadata.py, format_bibtex.py, search_openalex.py, search_pubmed.py, validate_citations.py (byte-identical upstream)
- Excluded (audited): scripts/search_google_scholar.py (audited: scholarly-based scraper; third-party terms-of-use risk + extra proxy dependency; replaced by native web.search/web.fetch guidance)
- Adaptations: frontmatter normalized (allowed-tools/compat dropped; optional-credential envVars metadata replaced by explicit credential-services note); all script invocations bound to exec.shell in the resolved Linux environment; uv-pip install section replaced by pinned-dependency provisioning; Scholar scraper removed from workflow, resources list and script_reference.md; literature-review/scientific-schematics cross-references rebound
- Script audit (2026-10-26, this lane): no subprocess/shell-outs, no os.system, writes only to explicit `--output`/opt-in `--in-place` targets, rate-limit sleeps respected, optional API keys read from env only and never echoed, citation-key validation regex present upstream. The original handoff declared Python 3.9+ and requests==2.32.3. Coordinator review replaced that obsolete HTTP dependency set before publication; this package now requires Python 3.10+ and the exact five reviewed pins in references/requirements.lock.txt. These universal wheels are architecture-independent; actual RISC-V guest installation and API execution are still pending.
- GUEST-PENDING handoff for Main (unverified here): stage scripts into a task workspace in the resolved Linux environment, then `exec.shell`: `python3 scripts/search_openalex.py "CRISPR gene editing" --limit 5 --output o.json`; `python3 scripts/doi_to_bibtex.py 10.1038/s41586-021-03819-2`; `python3 scripts/validate_citations.py assets/bibtex_template.bib --report r.json`. Expect o.json non-empty, a valid BibTeX entry, and a report exit code by severity. Record actual results; only then may execution evidence become guest-verified.

- Coordinator integration (2026-10-26): explicit network capability now matches the shipped read-only HTTP clients; OpenAlex keyless first-page limit clarified from current official authentication documentation. No scripts changed; upstream script bytes remain the pinned originals. Requests dependency refresh basis: https://github.com/psf/requests/security/advisories/GHSA-9hjg-9r4m-mvj7 and https://pypi.org/project/requests/2.34.2/.

## File inventory (sha256, this checkout; PROVENANCE.md self-hash intentionally omitted)
- `SKILL.md` sha256 `2bda5baeb9c94055890e07a7865a20986efe6b6e3bc9404caef209a5a44b8a05`
- `assets/bibtex_template.bib` sha256 `08e21647fa68cad1aa1658264798c7d24775ba89bfbd2723ea6bfe4b562e2be1`
- `assets/citation_checklist.md` sha256 `ce7317f2983f8b7fd02949aad726ebd6188319c7e57c929fffe689d5ae18ce36`
- `floe.json` sha256 `7f1d863fc3a9a60bba8a541f168293bc76606f40bceb7da0d0ab9bda6c6a0b1a`
- `references/api_contracts.md` sha256 `078a61d37d4632f0226e0d000a7be8d5485ab913146f9bb705c0888af226f443`
- `references/best_practices.md` sha256 `df90d19c8f639590a6a430a889160b478dce61f4a5c0a5a36df5ab1be749b6b1`
- `references/bibtex_formatting.md` sha256 `6337a8d2b87de96bf0f72c076feb0fc5d61ed9c342d9c8f19b3633efbfec6fed`
- `references/citation_validation.md` sha256 `f235f82e02db282f0abdd23fd8d2973d870d427d355979e869f736259ba95774`
- `references/core_workflow.md` sha256 `19e8b52c43f5822163c79904236016616dc4515d21a01d29073d968c9251af8d`
- `references/example_workflows.md` sha256 `01c0a15e08e8115e10a07623f63565d119812fd2bb68c669eac413db2f9cd482`
- `references/google_scholar_search.md` sha256 `5b705ec8d6276ef83b819b737ed10bd991815ccb413de27e046b7bfdf4da8399`
- `references/licenses/LICENSE-NOTE.md` sha256 `677f6d4283a9de482f3c63aed0a544b7d6bf92faf82e1565bb1372dfc8e295cf`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `09b02a3c9df3053c55531d503357a9c7cde275970e6c3ceaa1ddf5f0e90b40c1`
- `references/metadata_extraction.md` sha256 `68c27886aff0d4efbf3a6f7e0a318dedd706d4cfd0f55dd859466de36ed78d46`
- `references/pubmed_search.md` sha256 `fab82cda700a0dfc6dccc9465c9cc60b9df68cb58d0bec9abe7b2d8748a49cd1`
- `references/requirements.lock.txt` sha256 `d5af37d358d90926ba2d4939ee672a86352ccc8ea4df4e3ff01e45cda740af61`
- `references/script_reference.md` sha256 `dcee73297c60ff70d46af45fa9784ce13eb9ce902ddf2d53445de004e2ba1de3`
- `references/search_strategies.md` sha256 `776c0dd1cbaf0432004ae80273640ff324b570401c569413c674829436385c85`
- `scripts/_common.py` sha256 `87540160163671b972c2fccb4d0a42db3cca2603c664d26d5da3ca5dbc7dfdd2`
- `scripts/doi_to_bibtex.py` sha256 `1b7d1ab2e8bf9bcf5a7d49bf45496e0f8b7d8e0d0cda8efd8fce4e527082dc4b`
- `scripts/extract_metadata.py` sha256 `bebc7835b5e659cdeee0087980e881635894330bac5eda4ce01f490fd41df781`
- `scripts/format_bibtex.py` sha256 `cc74fdc4d5819df8db3999e59f96469cebfb353ecf406a49a5a0fc60896707cb`
- `scripts/search_openalex.py` sha256 `538b2f086625fd1e9a2cb2fe8bd46ee852d888f17d2d1e889b8f50592594f693`
- `scripts/search_pubmed.py` sha256 `4543b74bf773747bae47a2bbb18acf2a4a050071119d88d1711db6049d157116`
- `scripts/validate_citations.py` sha256 `a08e8e0774287e9aca2bd87c3a66cd3dfc751018eafb6cdee37987e3f416d2b5`
