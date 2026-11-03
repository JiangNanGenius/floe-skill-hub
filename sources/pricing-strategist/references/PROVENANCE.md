# Provenance — pricing-strategist (Floe adaptation, 1.0.0)

- Upstream repository: `https://github.com/alirezarezvani/claude-skills`
- Pinned commit: `6d2f02ea077eead1bee5411a31bcc6db5a11a70c` (2026-10-23T11:30:17Z,
  “Merge pull request #1050 from alirezarezvani/dev — Release v2.14.1”)
- Upstream path: `commercial/skills/pricing-strategist`
- Retrieval: exact-pin GitHub Contents API blobs only (no full repository clone, no dependency
  environment), 2026-11-01 Australia/Sydney. The raw API evidence is retained in the private
  task handoff, outside this package.
- Upstream root license: MIT, Copyright (c) 2025 Alireza Rezvani. Root `LICENSE` blob
  `c3e30bcc287d6a1ebdb4ab29c10d344fd1053639`, sha256
  `a20126646f93d32a8989c3cf4772d59194f405034f7babe7daebeac22b8ab151`; full text preserved at
  `references/licenses/UPSTREAM-LICENSE.txt`.
- Per-file license treatment: `references/licenses/LICENSE-NOTE.md`.
- Adaptation record: `references/ADAPTATION-NOTES.md`; product/runtime copy:
  `references/FLOE-ADAPTATION.md`.

## Exact upstream files retrieved (sha256, git blob)

| Upstream path | Bytes | sha256 | Git blob |
| --- | ---: | --- | --- |
| `SKILL.md` | 9361 | `a72cb5ece93a9f377909ae3c02d612478ed8474bc5577ad5b1da6f1e5a991c09` | `fec55771b411765c122e33d228109c003a04fb4e` |
| `scripts/pricing_model_picker.py` | 11402 | `481bd4ea8e63656d773b5cefea16372169134af1c7d2f05cb52d56c2d57f2972` | `43a815b870e4afe299555fcfef5e379dcf468be2` |
| `scripts/packaging_designer.py` | 11970 | `62c31dca54aa646c525bb21d942bda6a94b0f8374d12af1f52e227dcf8436914` | `5cac31cad74345776e8c6d179bc005b5f5aa7248` |
| `scripts/wtp_analyzer.py` | 10492 | `6c78d2d2fd18fe5bfc8075033d84134551ebc8827110bc15c93c6c583001ee06` | `544c7648053c291d02dd1f3637278f3c6f19ca2b` |
| `references/packaging_anti_patterns.md` | 6152 | `b8f358d4a77bb51b2e428c55cadac74269aaac8cedf1754ca5ea81f012a78cb3` | `bb67a63442195b2cae046c5a2dc3dfd91d7f840e` |
| `references/saas_pricing_canon.md` | 5217 | `616104f34a8773ea41f1c48886eaeb6f576d67c0bac61f7b379794b9db8c5ea4` | `257f7af5a1ef4477b6e5dcf1a1a7bc0789db578e` |
| `references/van_westendorp_methodology.md` | 6579 | `baf10f064004791d68cf6644011d7bc454e42f927c5f96e35dadddcc352e0443` | `95a60a1f8ef400c4fe8a69afc5075149120c599b` |
| `assets/pricing_brief_template.md` | 3396 | `d1ea641d9b68c143235d041a491905634f562b1eca1dc7794b070faca2eb0f40` | `a3771eb28836f1bc797853e830190fdf10786477` |
| `LICENSE` (root) | 1072 | `a20126646f93d32a8989c3cf4772d59194f405034f7babe7daebeac22b8ab151` | `c3e30bcc287d6a1ebdb4ab29c10d344fd1053639` |

Exact-pin bytes are retained under `upstream/6d2f02ea077eead1bee5411a31bcc6db5a11a70c/`
in the private task directory. `SKILL.md` and the three scripts are adapted in the package;
the three reference documents and `LICENSE` are byte-identical; the brief template differs
only in its example command.

## Package file inventory (sha256, this checkout; PROVENANCE.md self-hash omitted)

| Package path | Bytes | sha256 |
| --- | ---: | --- |
| `SKILL.md` | 12920 | `5be7a4d65d10d54d68bd151206295579d478ff8cc11bdf8fef98d82cd1b05bf6` |
| `floe.json` | 223 | `96cb9a3b2942a7733321f8be5053a89cf6f463fe60ddf2f8ca1e05f9cf9855a4` |
| `assets/fixtures/README.md` | 669 | `3b726ed69e5bc030f81d9cac838bc695f90f57d3bce5b76ee3b89265067ef697` |
| `assets/fixtures/brief_valid.json` | 483 | `0c816d62e8e292f8402fdff680cdba3cc9f74d7b9305614a1433d3517041bd6a` |
| `assets/fixtures/features_valid.json` | 1995 | `59f626ee362e610345a8c0c85789c4b1da4b6b3d3b27e84d6e6ded1c654575eb` |
| `assets/fixtures/survey_valid.json` | 4962 | `908705448c5cd69f5efad7a149a3a78d8ca2f1d7e1c98d3204c870e1568f50f6` |
| `assets/pricing_brief_template.md` | 3406 | `c62887fe25666afb3e01f906635803cee5c935525161a6af644529019345305e` |
| `references/ADAPTATION-NOTES.md` | 5885 | `d1eee5c7c1dfa79308eb86864172019f6c2280902bdecfc36b108986d34ab498` |
| `references/FLOE-ADAPTATION.md` | 6464 | `92b51cb2ce421190bcf073c29faa15863cb999dab5a2a7c52f264b5e5314051c` |
| `references/licenses/LICENSE-NOTE.md` | 2119 | `35d039dfb4dadef95efb7a0b8f1062ae18cd5ac2eae9ff9f5129b2836a1a1820` |
| `references/licenses/UPSTREAM-LICENSE.txt` | 1072 | `a20126646f93d32a8989c3cf4772d59194f405034f7babe7daebeac22b8ab151` |
| `references/packaging_anti_patterns.md` | 6152 | `b8f358d4a77bb51b2e428c55cadac74269aaac8cedf1754ca5ea81f012a78cb3` |
| `references/saas_pricing_canon.md` | 5217 | `616104f34a8773ea41f1c48886eaeb6f576d67c0bac61f7b379794b9db8c5ea4` |
| `references/van_westendorp_methodology.md` | 6579 | `baf10f064004791d68cf6644011d7bc454e42f927c5f96e35dadddcc352e0443` |
| `scripts/_pricing_io.py` | 10433 | `92e75fe762b8578beff80cf784417e1d81e9f9c2ee987528c68b89838852225a` |
| `scripts/packaging_designer.py` | 16069 | `c14a960cb6c39524a4146024dda63d262abab455d5f40d0652eed231f33e6610` |
| `scripts/pricing_model_picker.py` | 14160 | `e1f70e4679c1cd9575e7e47c403a6cdba6afecc84e7430ca3ec9efafee298152` |
| `scripts/verify_pricing_skills.py` | 16404 | `29e45e64134c6de7d31c450efa5e9d99ab0ddce667cc098065d4a5b6fccf6fc1` |
| `scripts/wtp_analyzer.py` | 13555 | `a83189dd2de0ad0cc0c28905f9b727761dad80218d21cc50ed062cd0aa747e38` |

Total (excluding this file): see `SNAPSHOT.json` in the private task directory. The package is
far below the Hub 8 MiB / 128-file limits.

## Maintenance observation (path-level, not adoption)

Observed 2026-11-01 from the GitHub commits API:

- `commercial/skills/pricing-strategist` path: 5 commits. The three scripts, references and
  assets each have exactly **one** path commit — the 2026-05-19 initial `v2.8.0-sprint1`
  introduction (`7947638b310ddc...`). No later script or reference content change was observed
  at the pin; script content is therefore stable since 2026-05-19, not “recently active”.
- `SKILL.md` path: the same initial commit, a 2026-06-11 wave-3 optimization
  (`aecfb8e0bb71...`), two 2026-10-21 frontmatter/docs commits, and a post-pin 2026-10-30
  description rewrite (`b078bb899640...`) that is **not** included in this pin.
- Repository-level stars (29,054 at observation), pushed-at and 90/180-day commit counts are
  repository signals only; they are not per-skill adoption, usage or content activity.

## Linux/riscv64 guest qualification (this build)

The final 1.0.0 package (this source tree and its deterministic archive) was executed in a real
Linux/riscv64 component guest on 2026-11-03 (UTC): TinyEMU host from the retained f130
toolchain, OpenSBI + kernel 6.18.56, 1 vCPU / 768 MiB, no network. The guest ran the packaged
12-check verifier (`ok=true`, 0 failures), the three fixture CLIs with the documented figures
(top model `hybrid` score 95; Van Westendorp n=40, OPP 60.2, IDP 68.425, PMC 54.25, PME
79.775, RAP [54.25, 79.775]; packaging prices 49.0/149.0/0.0 with 9 features and 2 flags),
re-ran the three CLIs under `python3 -S` with byte-identical stdout, and confirmed active
`ModuleNotFoundError` denial for numpy and requests under `-S`. The extracted source tree
hashes were identical before and after execution. Full transcripts, exact stdout/exit codes
and hashes are retained in the private release task scope, outside this package.

Boundary: this is component-guest evidence only. It does not prove App install-time
provisioning, Simulator, physical device, signing, publication, Android, remote-Linux
execution or market/pricing validity. Host runs remain developer/static evidence.

## Host evidence boundary

Host/static checks ran on macOS 27.2 (build 26B123) with CPython 3.9.6 and 3.12.13; they are
developer evidence only. The real Linux/riscv64 component-guest run for this final build is
recorded above; no Android, App, Simulator or market execution was performed.
