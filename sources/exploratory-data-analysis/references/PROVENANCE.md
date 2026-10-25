# Provenance — exploratory-data-analysis (Floe adaptation, 1.0.0)

- Upstream repository: https://github.com/K-Dense-AI/scientific-agent-skills
- Pinned commit: `593377bb048752abb0152deab9fbb1083a6087df` (repository tree `d4d202beb151c1f1c6c15738be0692d65e0447af`; skill subtree `skills/exploratory-data-analysis` tree `05078b0b57ce5387f8883e6ae1273f11f8329115`, verified at fetch on 2026-10-26)
- Upstream path: `skills/exploratory-data-analysis`
- License: MIT (root `LICENSE.md` at the pinned commit, Copyright (c) 2025 K-Dense Inc.) — full text at references/licenses/UPSTREAM-LICENSE.txt; per-file audit in references/licenses/LICENSE-NOTE.md
- Retrieval: sparse subtree fetch into maintainer-owned temporary storage; no full-repo vendoring.
- Adaptation record: references/ADAPTATION-NOTES.md (kept-verbatim / modified / added / excluded, each with reasons).
- Declared dependency layer (floe.json): numpy==2.2.4, pandas==2.2.3 — the exact versions the resolved Debian 13 (trixie) riscv64 guest provides as `python3-numpy` (1:2.2.4+ds-1) and `python3-pandas` (2.2.3+dfsg-9). Upstream's heavier pins (numpy 2.5.3, h5py, Biopython, Pillow, tifffile, pandas 3.0.6, Polars) are deliberately not declared; the corresponding upstream inspectors are not bundled.
- First-release version: 1.0.0 (no previously published id/version exists for this skill in the legacy four-item feed or the candidate registry; registry versionTarget is 1.0.0).

## Host development evidence (NOT guest execution evidence)

Executed 2026-10-26 by the H4 lane on the coordination host, labeled by environment:

1. Debian trixie arm64 dev container (docker `floe-data-five-dev`; distro release, Python 3.13.5 and package versions identical to the guest pins; NOT the riscv64 guest and NOT the 4.15 TinyEMU kernel): `python3 scripts/eda_verify.py --require-optional` → exit 0, `"ok": true`, 12/12 checks pass (stdlib goldens, safety negatives, 6-CLI subprocess end-to-end, numpy 2.2.4 layer incl. object-NPY rejection, pandas 2.2.3 layer with cross-engine consistency `consistent: true`).
2. Bare macOS venv, Python 3.12.13, stdlib only: `eda_verify.py` → exit 0, `"ok": true`, 8/8 mandatory checks pass, optional layers honestly reported `missing`; `pandas_profile.py` → exit 2 with the explicit provisioning message (no silent downgrade).
3. `pandas_profile.py` in the container over the shipped fixture: cross-engine check consistent, 8 rows profiled.

These runs prove script correctness on the tested interpreters only. riscv64 guest execution evidence remains UNPROVEN until Main runs the runbook below in the resolved Linux environment.

## GUEST-PENDING handoff for Main (exact steps; do not flip evidence without a real passing run)

In a task workspace in the resolved Linux environment (explicit environmentID/write layer), with this package installed/staged so `scripts/` and `assets/fixtures/` are present:

1. Provision the reviewed layer through the existing environment/package flow (guest apt identities): `python3-numpy` (2.2.4) and `python3-pandas` (2.2.3). No chat-time pip/uv.
2. `exec.shell`: `python3 scripts/eda_verify.py --require-optional --output verify.json` → must exit 0 with `"ok": true`; `verify.json` records numpy/pandas installed versions and `pin_matches_base_version: true` (Debian `+dfsg` local suffixes are tolerated by base-version comparison).
3. Stdlib-only proof (before/without provisioning, or in a layer where pandas is absent): `python3 scripts/eda_verify.py` → exit 0, optional layers `missing`.
4. Real workload: stage one authorized task CSV, then
   `python3 scripts/eda_analyzer.py <file>.csv --root . --missing-token NA --output eda.json` and
   `python3 scripts/pandas_profile.py <file>.csv --root . --missing-token NA --output pandas.json` → both exit 0; `pandas.json` shows `cross_engine_check.consistent: true`; read the outputs back with the workspace file tools (long scans via `jobs.submit`/`jobs.result`).
5. Only after 2-4 pass in the actual guest may `plannedRuntime.execution.evidence` become `guest-verified` and `status.executionVerified` flip.

## File inventory (sha256, this checkout; PROVENANCE.md self-hash intentionally omitted)

- `SKILL.md` sha256 `cc497de5163122c4673e97955c5c626750e4bbab94875c6bfbbe9a3498b40384` (11437 bytes)
- `assets/fixtures/README.md` sha256 `8677c985e8f0ccdd12f3d8ce881854a8bf52702475b551b66d4e5bba67f8306d` (1038 bytes)
- `assets/fixtures/leak_fixture.csv` sha256 `ecf59f70f50e68ff3b1f3a287a908f2fd67e9b18173d19b1f6b72e589939889c` (194 bytes)
- `assets/fixtures/profile_fixture.csv` sha256 `d54ac71bf3d00357ca0ae5d72f9bf1c6905599b7d6e78351838868676dd2babe` (164 bytes)
- `assets/fixtures/structure_fixture.json` sha256 `a5adabc51511941ea1f4d46a6448621f16843f13f3f7d4b54e53251b34b7be8a` (152 bytes)
- `assets/report_template.md` sha256 `c6cd0644dbefeb64c77e84935509f52a92d45256daf2cd4be84012e99e4d7d44` (7873 bytes)
- `floe.json` sha256 `e470a2caa157ebe1be85be263e6716e67cb89c52a147a1d576c3e6c8262afa95` (772 bytes)
- `references/ADAPTATION-NOTES.md` sha256 `379ede6977a4d86017c42a557530b38f47e1e98144dde34b7db1b2f2dfece982` (4750 bytes)
- `references/bioinformatics_genomics_formats.md` sha256 `b3594673cbe22e29fd5bc2681c1b53d4f8b02b48ff17fc9ffaf5a09d1d885be3` (8977 bytes)
- `references/chemistry_molecular_formats.md` sha256 `3ff937541ebf0396d4c2304016cebc42d405110300df7379f59c40953fc8ed41` (8732 bytes)
- `references/general_scientific_formats.md` sha256 `42bcf3389bbd78e426dd41139208517f3f78bdc17e068a1eb3a984d2f2487320` (12276 bytes)
- `references/licenses/LICENSE-NOTE.md` sha256 `1043c53017571c4547acd1dc256d884b9cfcaf928a9ccd4a130c432eb9bdfc1d` (1042 bytes)
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `09b02a3c9df3053c55531d503357a9c7cde275970e6c3ceaa1ddf5f0e90b40c1` (1068 bytes)
- `references/microscopy_imaging_formats.md` sha256 `c96bb7291ded320a106800c1132191683aa3028f2240c5fcf954079f1a26c382` (9305 bytes)
- `references/proteomics_metabolomics_formats.md` sha256 `66d9493fe14c717f5e8e60500e8fa7bfe1f619084e23b643a767f0952a35efd7` (9821 bytes)
- `references/spectroscopy_analytical_formats.md` sha256 `102a68c212ef5447815c889cf06668f3cb5bd8644f018354d6e98d1a15101a0f` (9555 bytes)
- `scripts/__init__.py` sha256 `87539288ce5d4caf24fc9fca14e5d70c41730c9d4285106ac4db0c4b5cefd60c` (69 bytes)
- `scripts/_capabilities.py` sha256 `0449bc9829fc132c22d798310a636a974cdfcb27f698f10c8356bf74621983cf` (17870 bytes)
- `scripts/_common.py` sha256 `f363af255cc78ea63864e0da9f679f57a9e71efd36b6813332f3d2c419b30d51` (14293 bytes)
- `scripts/_structured.py` sha256 `57c27f2ffc1a0a835771190d056f796e970d20fc2a7dee6b9384beecee7bcc81` (7788 bytes)
- `scripts/_tabular.py` sha256 `5d1db825890dd035c30e51ac1c11aee56e1e1dca6ffd238ee87ae7d51d8df2f0` (32782 bytes)
- `scripts/capability_manifest.py` sha256 `1e52e1db668ebce919751a75b53ad959c36749e4b1695f59d8ac2d6c8eda4abf` (5433 bytes)
- `scripts/distribution_sensitivity.py` sha256 `ca6e9f3dd59cfb382b1ff0874e709933c136ec942085a0437d4000bbf7f1f3c8` (3304 bytes)
- `scripts/eda_analyzer.py` sha256 `d3ab34d882c172c6348963c5ad025e80583e24d8132f4e580c33bc5cad07f8fb` (9093 bytes)
- `scripts/eda_verify.py` sha256 `9197473236f7e713bac623f94a13e1c70a4439603d8e6a8e0293d2d88522cf3e` (23005 bytes)
- `scripts/missingness_leakage_audit.py` sha256 `28458714e80ee31db636c0265ba21e1623ba27816d31e236fdc9b873a5b78ffc` (3904 bytes)
- `scripts/pandas_profile.py` sha256 `711555c208e170e32376592a74014b5600e8360f73ab6bd9302fd268c82348a5` (11038 bytes)
- `scripts/report_scaffold.py` sha256 `4d745592384bfceb0ec7384eecfc5e8ba49ebfa4ec55be75a99ce7c7e102f60b` (4247 bytes)
- `scripts/tabular_profile.py` sha256 `78cd139292c18e31d17de882762948db7b51fdc3278546f994270a287d0149db` (3077 bytes)

TOTAL 29 files, 223059 bytes
