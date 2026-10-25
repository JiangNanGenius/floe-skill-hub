# Provenance — sympy

- Upstream repository: https://github.com/K-Dense-AI/scientific-agent-skills
- Pinned commit: `593377bb048752abb0152deab9fbb1083a6087df` (tree `d4d202beb151c1f1c6c15738be0692d65e0447af` verified at fetch)
- Upstream path: `skills/sympy`
- License: MIT (root `LICENSE.md` at the pinned commit, Copyright (c) 2025 K-Dense Inc.) — full text at references/licenses/UPSTREAM-LICENSE.txt
- Subtree-only fetch into task scratch on 2026-10-26; no full-repo vendoring.
- Kept: references/*.md (7 files; both upstream core-capabilities docs preserved verbatim); scripts/sympy_verify.py (NEW first-party Floe verifier — not upstream content; MIT (c) Floe project; runs offline, no writes)
- Excluded (audited): upstream ships no scripts
- Adaptations: frontmatter normalized (allowed-tools/compat dropped); uv-pip install block replaced by pinned dependency provisioning through the environment flow; version check bound to the shipped verifier; optional numpy/scipy wording conditioned on environment presence
- GUEST-PENDING handoff for Main (unverified here): in the resolved Linux environment with the pinned deps, `exec.shell`: `python3 scripts/sympy_verify.py` must exit 0 with "ok": true and version 1.14.x; then run one real workload (e.g. solve `x**2-2` over the reals and emit `latex(sqrt(x))`). Only after a real passing run may execution evidence flip to guest-verified. sympy+mpmath are pure-Python wheels; confirm they come from the digest-bound wheel source (ios-wheelhouse policy), not ad-hoc pip.

- Coordinator review (2026-10-26): fixed the original first-party verifier which accepted False results; each check now requires True, and derivative/root/ODE checks compare the mathematical result. Version must equal the declared 1.14.0 pin. Positive/false/exception regression evidence is retained in the integration receipt. Added universal-wheel hashes in references/requirements.lock.txt. No guest execution claim.

- Coordinator packaging review (2026-10-26): included the full applicable source license text alongside the existing ownership notice; upstream license files remain unchanged.

## File inventory (sha256, this checkout; PROVENANCE.md self-hash intentionally omitted)
- `SKILL.md` sha256 `b1a57988f3207e83408af41e428c4ebbfe864e2f2c5adea01066a3082f2f543d`
- `floe.json` sha256 `b3ae004acf42e0ee021721dcec6818565c2ec90018fc4b750cc465d828a667f8`
- `references/advanced-topics.md` sha256 `cff0c044c5d7c7f65235f35a7c0fe19e41a42c27393c9aa7f38a31f00ed28e81`
- `references/code-generation-printing.md` sha256 `6a547f4dfd6975762d61d7effd47c9613e16d345e2e1dab89549bfc465f7e404`
- `references/core-capabilities.md` sha256 `2c7d55c127ccd5d4d0792892025979c421573f2662c5cededb6cbcf80ee61888`
- `references/core_capabilities.md` sha256 `69fffa94caf62276112108bbeff5b7dd4281a5b40c07e44eea381f46f00a6011`
- `references/licenses/FLOE-SCRIPT-LICENSE.txt` sha256 `8c60c7b93f14003f634b25129ce7713b3c33f7f7b4b5831231fc0facb900fc60`
- `references/licenses/LICENSE-NOTE.md` sha256 `08ba2a28134ded8610cbd871bd81171df7e3b46e93c35fe85e4f3639858609ff`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `09b02a3c9df3053c55531d503357a9c7cde275970e6c3ceaa1ddf5f0e90b40c1`
- `references/matrices-linear-algebra.md` sha256 `fd64e48e917cf0a71bb0d744e8cfee345a98284256a84fb55793fe4d9783272d`
- `references/physics-mechanics.md` sha256 `0d015cf60861aa5fe1598a76e08d612a758f0c0895bbd1ce1dcbfbc9d4bfaf8c`
- `references/requirements.lock.txt` sha256 `f2043cc8afa77b80c3de0423be69c75036bbfaf661992e7969dfcc97aa2718c5`
- `references/review.md` sha256 `03d4db2d0432cf7ec3a21b2746da7b96809aa7613d17c101d16460f5ec732ab1`
- `scripts/sympy_verify.py` sha256 `0ba63f05cebbaeb114fbfdcd456565de564d7cfcd13cb6379b25a3d0e3e0acdb`
