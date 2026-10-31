# Upstream tracking and automatic update candidates

The tracker (`scripts/upstream_updates.py` and
`catalog/upstream-update-policy.json`) resolves upstream changes and constructs
independently verifiable candidates. Signing, publication and append-only
history are handled by the [automatic publication pipeline](AUTOMATIC-PUBLICATION.md).

## Hard execution requirement

ALL automatic upstream tracking and updating executes **unattended in GitHub
Actions**, independent of any Mac/App/Codex online state. There is no local
daemon, no heartbeat and no local scheduled repair. The CLI is
non-interactive, stdlib-only (plus the git CLI for tokenless public upstream
reads), needs no secret for check/plan/stage, and derives every decision from
committed inputs plus resolved immutable upstream commits. A dropped run
simply re-runs: identical resolved commits produce byte-identical reports.

Cloud gates may HOLD runtime/native changes that need genuine qualification
unavailable in the cloud; a hold preserves the previously published version
and records an actionable adaptation state. Qualification is never fabricated
and CI emulation never counts as guest-verified. Normal eligible updates flow
check → plan → stage → build → verify → sign → publish end-to-end in the cloud
using the existing credentials, scoped tokens and fixed reviewed code.

## Coverage (43 registry rows, exact partition)

| Group | Count | Behaviour |
| --- | --- | --- |
| tracked external skills | 30 | full automatic tracking + candidate construction |
| engine-managed (`impeccable`) | 1 | signals only; candidates exclusively via the `engines/impeccable` pipeline + `impeccable-engine-updater.yml` (stable `engine-v*` tags, never main HEAD) |
| watch-only replacements | 5 | license-appearance signals for the license-blocked originals of `doc-coauthoring`, `writing-guidelines`, `react-best-practices`, `composition-patterns`, `web-design-guidelines`; copying upstream bytes is structurally impossible for these ids and re-adoption is a maintainer curation decision |
| excluded builtins | 4 | App-provided (`floe-pdf/office/network/video`), first-party pins, never tracked |
| excluded first-party optionals | 3 | `floe-email-drafting`, `floe-file-organizer`, `floe-invoice-organizer`; upstream=null by design |

`validate-policy` (and `tests/test_upstream_updates.py`) enforce the partition
against the live registry fail-closed: an id in two groups, a missing id, a
tracked id without an upstream block, or an excluded/watch id with an upstream
block all refuse. Unselected upstream skills are never imported: fetches are
restricted to the exact declared subpaths, and a repository pin alone is not a
license to copy (the five replacements stay first-party even though their
original repositories remain pinned for signals).

## Scanning (check)

Repository checks are **grouped**: one head resolution per repository, then
per-entry comparison of the **relevant source subpath tree** between the
entry's effective pin and the resolved immutable head commit. A moved
repository head with an unchanged subpath tree is `up-to-date`/`no-change` —
unrelated upstream commits never bump a pin, a version or a package. Per-entry
effective pins consume the entry-pins contract (`scripts/upstream_pins.py`:
bound `skillOverrides` entry, else the repository default). Repository-root
license files declared in the policy are compared between pin and head; drift
holds every tracked skill of that repository (license re-audit, never an
automatic carry). The engine repository is additionally scanned for stable
`engine-v<semver>` release tags versus `engines/impeccable/ENGINE-LOCK.json`.

## Candidate construction (plan/stage)

For a genuinely drifted subpath the planner fetches the OLD (pinned) and NEW
(resolved head) upstream subtrees and merges three ways against the staged
local source in `sources/<id>`:

* correspondence comes from `catalog/upstream-update-policy.json` per skill:
  explicit `fileMappings` > `excludedUpstream` globs > `relocations` prefixes >
  path identity. Content hashes never invent mappings; they classify carries as
  verbatim/adapted and detect undeclared carries fail-closed
  (`held-policy-inconsistent`);
* `old == new` → keep the local file (adaptation preserved);
  `local == old` → carry NEW verbatim; `local == new` → converged keep;
  all three differ → deterministic hunk-level three-way line merge
  (difflib, autojunk off): disjoint hunks both apply, identical changes
  deduplicate, overlapping/adjacent/divergent regions hold (`held-conflict`)
  with file, region and both previews. Binary divergences always hold;
* Floe-owned files (floe.json, provenance, licenses, dependency locks,
  fixtures, verify scripts — where the RISC-V guest integrations live) are
  never taken from upstream and are preserved byte-identical;
* new upstream files are carried only under a declared relocation or an
  existing carried area, through the full gates; anything else holds
  (`held-adaptation-required`). A guide-only candidate additionally refuses
  code-like additions or changes outside `scripts/` (known executable
  suffixes and extensionless shebangs), so a tool or script smuggled under
  `assets/` or a nested reference area can never ride an assumed prose delta.
  Upstream removals delete only verbatim
  carries; removing a locally adapted file holds;
* mapped license carries (`kind: license`) whose upstream bytes change always
  hold (`held-license-drift`); license text is never auto-adopted.

Every candidate tree passes the unchanged `hubcore` package gates (paths,
symlinks, native payloads, sizes, counts, notice preservation, runtime/script
consistency). Upstream entries are refused on symlink/submodule modes, unsafe
names, oversize and native magics (`held-unsafe`).

## Runtime proof reuse (never fabricated)

* **Execution fingerprint** — exactly the publication-design definition:
  sha256 over sorted `<path> <blobSha256>` lines of every package member
  outside the narrow prose allowlist (`SKILL.md`, `references/*.md` one level
  only, `references/licenses/**`), plus `floe.json` canonicalized with only
  `version` removed. Deny-by-default: scripts, assets/fonts/templates,
  engine-data, dependency/engine descriptors, locks and every non-prose file
  are inside; the fingerprint is stable across the mechanical version bump.
* **Instruction-code fingerprint** (tracker hardening): fenced code blocks and
  inline code spans of every instruction markdown (excluding licenses,
  engine-data and the Floe bookkeeping docs). A changed command inside changed
  SKILL instructions is a runtime-relevant change — a text extension is never
  treated as safe by itself.
* **Tier 1 (guide-only, scriptRuntime none)**: auto-publishable when the
  deterministic gates pass, grants/dependencies do not drift, the license is
  preserved, changed paths stay within the upstream-derived set plus the
  mechanical set (floe.json version, provenance re-pin), AND the
  instruction-code fingerprint is byte-identical. Any fenced code block or
  inline code span changed in an instruction markdown holds
  `held-instruction-code-changed`; fenced formulas are code under this
  declared contract. Code-like files added or changed anywhere in the carried
  tree outside `scripts/` (obvious executable suffixes, or an extensionless
  file with a shebang) hold `held-adaptation-required`; ordinary prose and data
  assets do not trip the gate. The proposed review record is an honest machine
  static-content review; execution stays `{null, n/a, unproven}`.
* **Tier 2 (scripted, docs-only)**: eligible only when the execution
  fingerprint AND the instruction-code fingerprint are byte-identical to the
  published version, the prior guest-qualified review verifies under the
  production trust at its ledger-verified publication pin with matching
  digests, and minimumAppVersion is untouched. The proposed record cites the
  complete prior binding and claims NO new execution.
* **Tier 3**: any fingerprint/instruction-code drift, engine binding drift,
  conflict, license/permission/dependency drift, unsafe content or editorial
  gap holds the candidate; the old published version stays live and the hold
  record carries code, detail and repair.

## Immutable versions and pins

An accepted content change always proposes a NEW version (patch bump, re-bumped
while the version exists in `packages/`, feeds or the ledger); identical
candidate content is a no-change and never bumps. Same `(id, version)` digest
replacement is refused by construction here and again by
`publication_immutability` downstream. Pin acceptance is **per entry**:
accepted entries advance `upstream.commit`/`retrievedAt` to the resolved head
they were verified/derived at; held entries keep their exact old pin and
version; `docs/UPSTREAM-PINS.json` advances through the entry-pins helper
(`advance_pin_document`: compacted repository default when all rows agree,
explicit `skillOverrides` where they differ). Pin-only advances for
unchanged-subtree entries happen only alongside an accepted content update of
their repository — scans without content updates create no churn.

## Showcase evidence maintenance

`showcase/links.json` evidence records (whole-file sha256 + line range into
`sources/<id>/*.md`) are maintained mechanically only when the exact cited line
block survives **uniquely** in the candidate (lines may relocate); otherwise
the candidate holds (`held-editorial-review`). Hashes are never blindly
rewritten, relationship claims and pinned target URLs are never touched
(URL pin staleness is reported only).

## CLI

```
python3 scripts/upstream_updates.py check   [--out F] [--only ids] [--fail-on-error]
python3 scripts/upstream_updates.py plan    [--check-report F] [--out F] [--only ids]
python3 scripts/upstream_updates.py stage   --plan F --stage-root DIR [--out F]
python3 scripts/upstream_updates.py validate-policy [--out F]
# global: --repo-root --policy --cache --today YYYY-MM-DD --git-timeout --quiet
```

Exit codes: 0 completed (drift and holds are data, not failures), 1 usage,
2 fail-closed contract violation, 3 with `--fail-on-error` when any fact is an
error state. `--cache` (default `$RUNNER_TEMP` or the system temp dir, always
outside the tracked tree) holds the blobless upstream clones; `plan`/`stage`
pin the resolved commits from the prior report and verify the report was
produced against the current policy/registry/pins bytes. `stage` replays the
plan and refuses any digest divergence.

Stage output (under `--stage-root`, never inside the live checkout):
`staging-manifest.json` (candidateFacts for the pipeline request/manifest),
`candidates/<id>/<version>/{tree/,package.zip,candidate.json}`,
`held/<id>.json`, and `apply/{manifest.json,files/**}` — the exact byte-level
integration recipe (sources, registry, pins, links, unsigned review skeletons)
for accepted candidates. `package.zip` is byte-identical to what
`scripts/build_packages.py` produces after the apply set lands.

## Boundaries

The tracker never signs, publishes, commits, pushes, deploys, writes
`sources/`, `packages/`, `reviews/`, feeds, the ledger, `showcase/` or the
pins in the live checkout, never touches `engines/` or `sources/impeccable`,
never reads secrets, never executes package code, never admits a new skill id
and never weakens a gate. Reviewer identities, signing, S/X/Y/H staging,
CAS publication and workflow wiring belong to the automatic publication pipeline.

## First live run (2026-10-28, pins baseline 2026-10-26)

Grouped scan of the six pinned repositories: `anthropics/skills` and
`obra/superpowers` heads equal their pins; `alirezarezvani/claude-skills`
(6d2f02e→5434623) and `K-Dense-AI/scientific-agent-skills` (593377b→5f2bc03)
heads moved with **all 22 tracked subtrees unchanged** and root licenses
unchanged (no bumps — the unrelated-commit protection observed live);
`pbakaus/impeccable` corpus drifted with a newer stable engine release
(`engine-v0.1.18` > lock 0.1.17) → held-engine-managed with the updater-workflow
route; `vercel-labs/agent-skills` moved with no license appearance for the four
watched originals. Result: 30 tracked up-to-date, 0 eligible, 1 held
(engine-managed), 5 watch-only signals, 0 errors; the apply set is empty and
every published byte, pin and version is untouched.

## Additional out-of-subtree license evidence

A repository policy may declare `licenseEvidencePaths`, a unique list of at most 16 clean repository-relative paths, in addition to the existing `rootLicense`; the same bounds and path rules are declared in `schema/upstream-update-policy.schema.json` and enforced by the runtime validator. Use it for applicable directory licenses and root notices outside the selected skill subtree. Each tracked entry compares these exact bytes between its effective pin and the resolved head. Changes, appearance or removal hold adoption for a license re-audit even when the skill subtree is unchanged; a read error is an error, never proof of an unchanged license. Existing per-file `kind: license` mappings keep their unchanged drift gate. This does not grant permission to import an unselected subtree or adopt a new skill.
