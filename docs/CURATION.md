# First-release curation decisions

Assessment: 2026-10-26 (Australia/Sydney). This is editorial planning, not user ratings, certification, permission grants or an installability claim. Licensing, functional qualification and signed approval remain independent gates; scores cannot waive a failed gate.

Weights remain usefulness 25, Floe fit 25, content/examples 20, maintenance 15, per-skill adoption 10 and complementarity 5. No reliable per-skill adoption data is available, so that dimension stays unknown instead of borrowing an entire repository's stars. The provisional total covers only the assessed 90 points. Values are editorial judgments from inspected scope, not benchmark measurements. Dependency-heavy skills receive lower fit scores until real RISC-V guest checks pass. New original guides have less maintenance history.

Repository context is recorded with API source URLs and an exact observation timestamp in [the signal snapshot](CURATION-REPOSITORY-SIGNALS.json). Null repository license metadata never grants distribution rights: each shipped subtree/font/asset follows its own preserved license audit. Five candidates without redistribution permission were replaced by original Floe content and do not inherit the original repository's popularity.

| Skill | Planning score /90 | Selection reason and boundary |
| --- | ---: | --- |
| Floe PDF (`floe-pdf`) | 83 | High-frequency PDF work; reuses the protected native document path. |
| Floe Office (`floe-office`) | 83 | Editable documents, tables and slides provide the delivery path for other skills. |
| Floe Network (`floe-network`) | 75 | Connectivity and DNS diagnosis is distinct from research retrieval. |
| Floe Video (`floe-video`) | 76 | Makes existing media tools useful without promising absent codecs. |
| Doc Co-authoring (`doc-coauthoring`) | 77 | Outline and section feedback; original Floe replacement, no unlicensed text copied. |
| Internal Comms (`internal-comms`) | 76 | Audience-specific updates and retrospectives rather than marketing copy. |
| Writing Guidelines (`writing-guidelines`) | 74 | Technical clarity and consistency through an original licensed rule set. |
| Copywriting (`copywriting`) | 80 | Product-page structure and persuasive copy complement editing existing drafts. |
| Copy Editing (`copy-editing`) | 81 | Improves existing drafts while preserving the author's purpose. |
| Content Production (`content-production`) | 78 | Topic-to-long-form workflow is distinct from landing-page copy and editing. |
| Social Content (`social-content`) | 76 | Platform content and schedules; drafting never authorizes public posting. |
| Floe Email Drafting (`floe-email-drafting`) | 75 | Uses the app's mail services; sending remains separately task-authorized. |
| Deep Research (`deep-research`) | 83 | Question-driven retrieval and traceable evidence beyond a standalone summary. |
| Deep Read (`deepread`) | 80 | Close reading of supplied long material, distinct from multi-source discovery. |
| Literature Review (`literature-review`) | 81 | Screening and PRISMA discipline with offline DOI taxonomy; no paid CLI. |
| Citation Management (`citation-management`) | 76 | BibTeX and metadata checks; live APIs and guest dependencies still need acceptance. |
| Scientific Critical Thinking (`scientific-critical-thinking`) | 82 | Checks methods, bias and evidence strength instead of equating retrieval with reliability. |
| Research Summarizer (`research-summarizer`) | 78 | Short sourced synthesis from existing materials, distinct from a full review. |
| EDA (`exploratory-data-analysis`) | 78 | Bounded standard-library core plus independent pandas consistency checks. |
| Statistical Analysis (`statistical-analysis`) | 75 | Prespecified methods and numeric goldens; real SciPy guest qualification is pending. |
| Scientific Visualization (`scientific-visualization`) | 76 | Checks coordinates, gaps, units and actual files; guest fonts and native dependencies remain pending. |
| MarkItDown (`markitdown`) | 80 | Native services plus bounded original extractors; does not bundle Microsoft MarkItDown. |
| SymPy (`sympy`) | 77 | Exact roots and residuals are checkable; false-success verifier fixed, guest proof pending. |
| Impeccable (`impeccable`) | 82 | Actual design engine and controlled facts; missing measurements cannot imply a clean scan. |
| Algorithmic Art (`algorithmic-art`) | 75 | Deterministic seeds with Python/JS parity and no CDN; previews are not full-size exports. |
| Canvas Design (`canvas-design`) | 80 | Poster layout with corrected real font advances and complete font notices. |
| Theme Factory (`theme-factory`) | 77 | Consistent themes across outputs; actual PDF-embedded fonts and licenses were checked. |
| UI Design System (`ui-design-system`) | 80 | Reusable tokens and component rules support sustained product work. |
| UX Researcher-Designer (`ux-researcher-designer`) | 80 | Research and usability evidence inform design decisions beyond visual generation. |
| React Best Practices (`react-best-practices`) | 74 | Original component, data and performance rules replace an unlicensed candidate. |
| Composition Patterns (`composition-patterns`) | 72 | Original component composition guidance complements performance rules. |
| Web Design Guidelines (`web-design-guidelines`) | 74 | Fixed original local checks instead of loading unreviewed remote rules. |
| Webapp Testing (`webapp-testing`) | 80 | Real interactions and result files through Floe browser/jobs; no Chromium package. |
| A11y Audit (`a11y-audit`) | 82 | Keyboard, semantics and contrast checks remain distinct from aesthetic judgment. |
| Systematic Debugging (`systematic-debugging`) | 84 | Reproduction and root-cause evidence; unreliable poller is reference-only. |
| TDD (`test-driven-development`) | 81 | Behavior tests must run the project's real commands, not pass a template. |
| Requesting Code Review (`requesting-code-review`) | 82 | Reviews actual changes, risk and evidence through the existing review path. |
| Product Manager Toolkit (`product-manager-toolkit`) | 77 | Requirements, prioritization and roadmap templates for general product work. |
| Product Discovery (`product-discovery`) | 78 | Opportunity hypotheses and experiments complement specifications and planning. |
| Code to PRD (`code-to-prd`) | 79 | Derives specifications from actual code and distinguishes facts from inference. |
| Meetings (`meetings`) | 83 | Minutes and actions from authorized text; no implied recording or notification access. |
| Floe File Organizer (`floe-file-organizer`) | 77 | Original workflow with previews and recoverable changes under existing file permissions. |
| Floe Invoice Organizer (`floe-invoice-organizer`) | 76 | Existing OCR and spreadsheet services preserve source and correction traceability. |

The per-dimension record and source revisions are in [catalog/curation.json](../catalog/curation.json). The target remains 43 candidates with at least 40 qualified entries and all nine deep adaptations; these are coverage goals. The user-approved staged opening publishes qualified items incrementally, prioritizing text guides and scripts without binary dependencies. The four App-provided builtin ids (`floe-pdf`, `floe-office`, `floe-network`, `floe-video`) are native App features and never Hub download offers: they stay qualified, reviewable registry rows, but a release feed carries only the qualified optional items (the first wave is exactly those 30) and never references the four builtin archives or reviews. Publication itself is a feed-side projection (`published=true` on each qualified download offer in the signed feed only; the candidate registry rows keep `published=false`). Each offered item still needs its authentic review and applicable execution/runtime proofs; missing deep adaptations do not block unrelated qualified items. MCP integration remains a system workflow. Skill Creator and MCP Builder do not inflate the product count.

These planning scores are not imported into the App/store feed or shown as star ratings. The live signed catalog remains the authority for release availability.

## Current storefront highlights — 2026-10-27

The current editorial picks are Doc Coauthoring, Webapp Testing and SymPy, covering everyday document collaboration, browser workflows and verified symbolic calculation. All three are available in the signed catalog. The complete 43-entry selection continues to include unfinished adaptations with their actual readiness state. This changes presentation metadata only; package bytes, signed catalog offers and qualification evidence stay unchanged.
