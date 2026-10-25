# Provenance — webapp-testing

- Upstream repository: https://github.com/anthropics/skills
- Pinned commit: `dbd4588f9e1033efb41dad4bef2f7947c8993d44`
- Pinned subtree: `skills/webapp-testing`, tree `5ffb7dc66b9fd4c25c3e400a4c00da99a349b714`
  (verified via `git ls-tree` at the commit)
- License: Apache-2.0 per-skill `LICENSE.txt` (`Copyright 2026 Anthropic, PBC.`), full text kept
  byte-identical at references/licenses/UPSTREAM-LICENSE.txt; per-asset audit closed (the subtree
  ships no fonts/images/binary templates — see licenses/LICENSE-NOTE.md).
- Retrieval 2026-10-26: sparse subtree-only clone into lane scratch at the pinned commit; the
  full repository was never vendored into the Hub.

## Upstream file identities (bytes at the pinned commit, working-tree sha256)

- `LICENSE.txt` sha256 `bc6b3af2f331cbc7fb0da1344efb2cbe5877a31498b4d70dbc7000f3405a1362`
- `SKILL.md` sha256 `51b7349e77ec63b7744a6f63647e7566a0b4d2e301121cc10e8c2113af6556a2`
- `scripts/with_server.py` sha256 `b0dcf4918935b795f4eda9821579b9902119235ff4447f687a30286e7d0925fd`
- `examples/console_logging.py` sha256 `ea46877289acb82da7e7ce59d0bc37c8977cd57e2a006d0c88d7a1c625bf95da`
- `examples/element_discovery.py` sha256 `d63c89604a22f8845d724e95dda45db49b1bf57c25ce0a83afbb7b8da3d402f0`
- `examples/static_html_automation.py` sha256 `9d533aafb875ee3ab8b8ebf8f5b9003ac8d999da3d09b285cce252e623140064`

## Keep / transform / exclude decisions

- Kept byte-identical: `LICENSE.txt` → `references/licenses/UPSTREAM-LICENSE.txt` (required notice).
- Transformed (methodology preserved, stack rebound): upstream `SKILL.md` → rewritten
  `SKILL.md` + `references/upstream-methodology.md` (decision tree, reconnaissance-then-action,
  wait-before-inspect pitfall, black-box script practice, and all three example patterns mapped
  to exact Floe tool calls).
- Excluded by product policy (audited, with reason — NOT silently dropped):
  - `scripts/with_server.py`: subprocess mini-supervisor (`subprocess.Popen(shell=True)` +
    hand-rolled port polling + terminate). Floe forbids replacing the supervisor/jobs lifecycle;
    fully replaced by `jobs.submit → exec.localService` (probe-gated readiness, real-exit cancel).
  - Playwright/Chromium example bodies as runnable code: unsupported in the RISC-V Linux guest;
    preserved only as mapped history in references/upstream-methodology.md.
  - `file://` navigation pattern: the product browser is http/https + authorized loopback
    services; the static-HTML workflow was rebound to `exec.localService` runtime `static`.
  - Console-event capture (`page.on("console")`): no arbitrary JS/console domain exists by
    design; replaced with `browser.events`, observable page state and server logs, with the
    honest gap recorded in references/upstream-methodology.md (a console channel would be a
    native interface request to the App owner, never a fixture claim).
- New Floe-authored substance (Apache-2.0 distributed per LICENSE-NOTE.md):
  `floe.json`, the two synthetic fixture pages, `scripts/fixture_server.py` (stdlib authority
  server: /submit receipts, /api/click counter, /state snapshot, /slow late-result probe),
  `scripts/record_case.py` + `scripts/check_fixture.py` (evidence recorder + deterministic
  consistency gate that REQUIRES one honestly failing case), `references/floe-browser-tools.md`,
  `references/service-lifecycle.md`, `references/qualification-runbook.md`,
  `references/evidence-samples/honest-run-sample.jsonl`.

## Script audit (2026-10-26, this lane)

- All three scripts are Python 3.9+ stdlib only: no subprocess/os.system/ctypes/pip, no network
  client, no file writes except the explicit `--results` argument, bounded body/detail/evidence
  sizes, deterministic canonical JSON output (sorted keys, UTF-8). `fixture_server.py` executes
  nothing it receives, keeps state in memory, prints only method/path/status to logs, and
  refuses to boot without a valid `PORT`/`FLOE_SERVICE_PORT`.
- `scriptRuntime` is `remote`: scripts run only through the task's resolved Linux guest via
  `exec.shell` / `exec.localService`; no host interpreter fallback, no native alias, no new
  permission system.

## Capability/tool binding audit

- floe.json declares exactly the registry plan33 ceiling: capabilities
  `execution.remote, workspace.read, workspace.write, browser.observe, browser.interact`,
  tools `["exec.shell"]`, `pythonPackages: []` (stdlib scripts need no dependency pins).
- Tool names/schemas in references/floe-browser-tools.md were verified read-only against the
  CURRENT native surface (`Local/Worktrees/ios-pencil-live-20261019`, source `f274b1f2` plus the
  main owner's in-flight edits, at `FloeApp/Browser/BrowserTools.swift`,
  `BrowserModels.swift`, `BrowserURLPolicy.swift`, `FloeApp/Execution/LocalServiceTool.swift`,
  `Sources/FloeExecution/Tools/{LocalShellTool,BackgroundJobTools}.swift`,
  `Sources/FloeExecution/Linux/LinuxGuestLocalService.swift`,
  `docs/FLOE_BROWSER_PROTOCOL.md`). No fabricated bridge API: the skill never pretends Python
  drives WKWebView; browser orchestration is the agent's compiled-tool job, the guest runs only
  the service under test. `jobs.*` and `browser.*` are core runtime tools admitted by the
  declared capabilities, not manifest-invented aliases.

## Level-A host-reference results (executed 2026-10-26 on the development host; NOT guest/device proof)

- `python3 -m py_compile scripts/*.py` → OK (all three).
- Guest-layout copy boot: `PORT=8742 python3 scripts/fixture_server.py` → `/` and `/checkout.html`
  HTTP 200, `HEAD /` 200, deterministic `POST /submit` receipt `526effe574a7` for the canonical
  sample body, `POST /api/click` → 1,2,3, `/state` echoes both authorities, `/slow` answered
  `SLOW-DONE-45` after ≈2.03s without blocking, unknown POST → 404; missing PORT exits with the
  documented error.
- `record_case.py` built the 14-case honest sample; `check_fixture.py` → exit 0 with 14 CHECK PASS
  lines. Tamper runs: dishonest `absent-marker-fails=PASS` → exit 1 with the explicit dual rule;
  malformed receipt → exit 1; deleted case → exit 1; recorder rejects bad digest/bad case id with
  exit 2.
- Hub gates: `hubcore.validate_package_files` over the 14 staged files (this PROVENANCE.md is
  added last and excluded from its own inventory, per hub convention) → OK; contentDigest
  `67479b7654e17a952f10890458e12b6463799c356524ec9cdd0446a67818685d`; deterministic archive
  sha256 `accb909c1cc68af76252494b8bd2f45cbbf5843b7bdfdeff74c5eea9a9dd3340` (67,709 B); archive
  unpack round-trip OK; `build_packages.build_one` (isolated scratch root, same registry) wrote
  both channel paths `packages/…` and `android/packages/…` byte-identical. The staged version is
  `1.0.0`, matching the registry `versionTarget`.
- PENDING beyond this lane (Main-owned): Level B guest run and Level C native App browser loop
  per references/qualification-runbook.md §"What level B/C runs must additionally capture".
  Nothing here marks reviewed/qualified/published/executionVerified.

## File inventory (sha256, this checkout; PROVENANCE.md self-hash intentionally omitted)

- `SKILL.md` sha256 `99f21728643faf16c2576c8e2819cbd01c4abe39ff1bf86f1dc10367dfc191ac`
- `assets/fixtures/site/checkout.html` sha256 `21e469d2b71484d665fdcb6ea23f23a591824e1f01594f78ae8d4fb6b83361c5`
- `assets/fixtures/site/index.html` sha256 `7590ccb0c883d332ca751e4b745f201779338e8dac76f45c7ba416c05a59ff64`
- `floe.json` sha256 `8626d1bd38f4ed147bdc10e252473191aff848a575c9fa32e010fefe393772b7`
- `references/evidence-samples/honest-run-sample.jsonl` sha256 `dcfa14fef50a6dd4f2c1c3fd6baa87672ed3aceb43906cf21c1ef992f367c8e8`
- `references/floe-browser-tools.md` sha256 `cae48c5adc7f8310e1a3be602985db4dbae6667a1dd962fcecbf98f16a1f6a65`
- `references/licenses/LICENSE-NOTE.md` sha256 `6d3019a700f20309a65d180cf6bbf5aca6e9556cd72d6b5696b959c46e6a4a0c`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `bc6b3af2f331cbc7fb0da1344efb2cbe5877a31498b4d70dbc7000f3405a1362`
- `references/qualification-runbook.md` sha256 `11e3257ea31483a6c95ed963080b8beecd4cb8196674bcb5a4d7e794a5983e64`
- `references/service-lifecycle.md` sha256 `c252de442a72df1ae5cd5b6801035eeb5c345617a36efce866fdc68a694b3479`
- `references/upstream-methodology.md` sha256 `a09eda4e688568b7dcbe0b76f91d95e2e17175dae87c3fc41f2ed09a94ab2284`
- `scripts/check_fixture.py` sha256 `07c540cae8659bbd9ca89628f3e4b118c2c4c373a0aaf32b8115726b5dadb2ba`
- `scripts/fixture_server.py` sha256 `8297f994d2d43175bee4c96349fa2e181d5f5e5ea6063f1e937ef1c56bc5097b`
- `scripts/record_case.py` sha256 `cfd16c0b5a83e0684bf48e1e640aa760ffe757387f1d2dc85138637791365408`
