# Adaptation notes — exploratory-data-analysis 1.0.0 (Floe)

Upstream: K-Dense-AI/scientific-agent-skills `skills/exploratory-data-analysis`
at commit `593377bb048752abb0152deab9fbb1083a6087df` (MIT). This release is a
substantive runtime adaptation, not a rename: the dependency layer, entrypoints
and capability matrix were re-bound to the Floe resolved Linux guest (Debian 13
riscv64), and the unsupported upstream tiers were removed fail-closed instead of
being advertised.

## Shipped verbatim (audited: stdlib-only imports, no network/subprocess/eval/pickle; aggregate-only output)

- `scripts/_common.py` — bounded safe-I/O core (root confinement, symlink and traversal rejection, atomic writes, strict JSON).
- `scripts/_tabular.py` — stdlib CSV/TSV/JSON profiling and sensitivity math (numerical core; golden-verified).
- `scripts/capability_manifest.py`, `scripts/tabular_profile.py`, `scripts/missingness_leakage_audit.py`, `scripts/distribution_sensitivity.py`, `scripts/report_scaffold.py` — thin CLIs over the two modules above.
- `scripts/__init__.py`.
- `references/*.md` (6 upstream reference documents) — kept as guidance. NOTE: the domain references describe formats whose automated inspectors are NOT bundled in this release (see capability matrix in SKILL.md); they remain upstream reference-only guidance for separately provisioned tooling.
- `assets/report_template.md` — upstream report scaffold template.

## Modified (upstream MIT content, changes recorded)

- `scripts/_capabilities.py` — automated tier trimmed to `.csv/.tsv/.json` (stdlib) and `.npy/.npz` (declared `numpy==2.2.4` layer, was upstream pin numpy 2.5.3); the 14 removed automated entries (HDF5 ×2, FASTA ×3, FASTQ ×2, PNG/JPEG ×3, TIFF/OME-TIFF ×4) moved to reference-only rows explicitly marked "automated inspector not bundled in the Floe release"; magic-signature checks trimmed to NPY/NPZ; unused itertools/helper removed. Fail-closed unknown-format behavior unchanged.
- `scripts/_structured.py` — HDF5 inspector removed (h5py outside the declared layer); NumPy import-failure message re-bound to the Floe environment/package flow (was `uv pip install`); NPY/NPZ logic otherwise unchanged.
- `scripts/eda_analyzer.py` — imports/dispatch for HDF5, sequence and image inspectors removed (modules not shipped); `--max-records/--max-bases` arguments removed; tabular/JSON/NumPy routing, guardrails block and report rendering unchanged.
- `SKILL.md` — rewritten around the Floe runtime (exec.shell/jobs.submit, declared pins, guest-pending execution evidence, two-layer validation, trimmed capability matrix); upstream scope/boundary/IO-contract/reasoning/interpretation sections preserved in substance; upstream frontmatter (allowed-tools/compatibility/metadata) replaced by the native scalar name/description contract; K-Dense attribution and citation request preserved.

## Added (first-party Floe, MIT (c) Floe project)

- `scripts/pandas_profile.py` — the optional pandas layer required by the Floe plan ("stdlib and pandas paths validated separately"): bounded pandas profile with stdlib-equivalent missing-code/finite-number semantics, mandatory cross-engine consistency check (fails closed on any deviation), honest provisioning error when pandas is absent.
- `scripts/eda_verify.py` — bundled golden verifier: hand-computable aggregate goldens for the shipped fixtures, safety negative tests (symlink/out-of-root/URL/byte-cap/overwrite/ragged-CSV/NaN-JSON), numpy and pandas optional-layer checks with version-pin honesty, and end-to-end subprocess runs of all six CLIs.
- `assets/fixtures/` — small synthetic fixtures + README (first-party; no third-party data).
- `references/PROVENANCE.md`, `references/ADAPTATION-NOTES.md`, `references/licenses/*`.

## Excluded (audited, with reasons — recorded, not silently dropped)

- `scripts/sequence_inspector.py`, `scripts/image_inspector.py` — require Biopython 1.88 / tifffile 2026.9.20 / Pillow 12.3.0, none of which is in this release's declared dependency layer; shipping them would advertise unprovisioned capability. Formats stay reference-only and fail closed. (Debian trixie does package python3-biopython/python3-tifffile/python3-pil; a future release may add a separately reviewed optional layer.)
- Upstream dependency pins numpy 2.5.3 / h5py 3.16.0 / biopython 1.88 / pillow 12.3.0 / tifffile 2026.9.20 / pandas 3.0.6 / polars 1.44.2 — replaced by the versions the resolved Debian 13 guest actually provides (numpy 2.2.4, pandas 2.2.3); h5py/biopython/tifffile/polars not declared at all.
- Upstream `uv pip install` provisioning blocks — the Floe guest provisions through the existing environment/package flow; ad-hoc chat-time pip/uv is prohibited.
