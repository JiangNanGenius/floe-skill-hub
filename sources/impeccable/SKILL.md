---
name: impeccable
description: "Use when the user wants to design, redesign, shape, critique, audit, polish, simplify, harden, animate, or otherwise improve a frontend interface: websites, landing pages, dashboards, product UI, components, forms, settings, onboarding, empty states, and native iOS or Android screens. Handles UX review, hierarchy, layout, typography, color, motion, UX copy, accessibility, responsive behavior, edge cases, and capturing or documenting design systems (DESIGN.md, tokens). Also for making bland UI bolder, loud UI quieter, or ambitious visual effects. Not for backend-only or non-UI tasks."
---
<!-- Floe adaptation: this file is derived from pbakaus/impeccable
     skill/SKILL.src.md at the pinned commit recorded in references/SOURCE-LOCK.json.
     Apache-2.0 (upstream) is preserved; Floe changes are listed in
     references/MODIFICATIONS.md. Do not treat this banner as upstream text. -->

## Floe v1 engine surface

This skill runs the Floe Impeccable engine (`scripts/floe-impeccable.sh`), a static
riscv64 Linux binary built from the pinned upstream commit. It has **no network,
no Chromium, no DevTools endpoint and no arbitrary JavaScript evaluation**.

Available verbs: `context`, `detect`, `ignores`, `detect-csp`, `palette`,
`signals`, and the Floe `snapshot-scan` / `contract` / `snapshot-schema`.

Not available in v1 (the launcher and engine refuse each with a reason): live
mode, editor hooks, skill `install`/`update`/`check`/`link` (the Floe Skill Hub
owns those), `doctor`, `pin`, telemetry, image generation, the decision-page
server, and every Chromium/CDP capture verb (`component-review`,
`capture-server`, `font-match`, `build-phase`, `comp-spec`, `comp-diff`).

### Installed layout (canonical)

- The launcher is `scripts/floe-impeccable.sh`; run it as
  `sh <skill-base-dir>/scripts/floe-impeccable.sh <verb> [args...]` in the task's
  resolved Linux environment. Where this skill or its references show a compact
  `floe-impeccable <verb>`, that is this command.
- The engine's read-only data directory is `references/engine-data/` — a mirror
  of the upstream skill directory (`reference/`, `scripts/command-metadata.json`,
  `SKILL.md`, `VERSION`). Wherever text or engine output says `reference/<name>.md`,
  the installed file is
  `<skill-base-dir>/references/engine-data/reference/<name>.md`. The runtime sets
  `IMPECCABLE_SKILL_DIR` to that root; the launcher defaults to it. Do not move
  or edit files under `references/engine-data/` at run time.
- `references/engine-dependency.json` is the frozen managed runtime-artifact
  descriptor (data, never a permission). Design scans require the provisioned,
  probe-verified engine; without it `snapshot-scan` cannot run.

### Design scans of a rendered page

A page scan is a controlled data hand-off, not a browser session:

1. the native side captures a snapshot with the fixed, audited WebKit
   measurement producer (redacted, bound to the current task/session/tab/
   document/viewport);
2. `floe-impeccable snapshot-scan --snapshot <file> --identity <file> --out
   <file>` runs the pinned upstream rule core over it;
3. when the rules need measurements the snapshot cannot answer, the engine
   returns `needs-facts` (exit 3) with the exact points; the native side answers
   from the same document and the scan is re-run with `--facts`;
4. the result carries `findings`, a `coverage` receipt and a `verdict`.

**Never read an empty finding list as a clean page.** v1 cannot measure pixel
contrast, scroll-revealed content, content hidden at rest, console/script errors
or any iframe content, so a run with nothing to report is `verdict:
"inconclusive"` (exit 4) with `coverage.uncoveredRequired` naming the gaps.
Report those gaps to the user instead of claiming the page passed. Navigation,
reload, a viewport change or a scroll invalidates the snapshot and every answer
issued for it.

Interactions with the page (navigate, click, type, screenshot) keep using the
existing Floe browser tools; this engine only reads the handed-off measurement.

This skill gives you the tools and permission to make design that earns the name out-of-distribution craft. Work as an award-winning design director would: production-grade code, a clear POV, a deep grasp of what the client and its users need, and exceptional craft.

Core principles:
- Finish the job. No hedging, no shortcuts: the deliverable is complete, except assets the user must provide.
- Scale ambition to the surface's mode (see Modes). Persuade and Experience get full commitment: bold, distinct work with a point of view. On Operate and Read, ambition shows as precision and restraint, and patterns the visitor already knows earn their place.
- Verify by looking at the rendered result at the sizes it ships at, and batch the checks: fix what one look shows before looking again, rather than screenshotting after every tweak.

## Setup

1. Run `sh <skill-base-dir>/scripts/floe-impeccable.sh context` once per session, where `<skill-base-dir>` is the directory that contains this SKILL.md (the skill folder, not a plugin root two levels above it); keep cwd at the user's project. That base directory resolves every `<skill-base-dir>/scripts/floe-impeccable.sh <verb>` command in this skill and its references, and `<skill-base-dir>/scripts` is the fallback only when the runtime reports no base directory. The launcher runs under the task Linux environment's `/bin/sh`; there is no host or Windows path. The engine binary is not inside this skill: the Floe Skill Hub provisions it as a separate digest-bound runtime component into the task's resolved Linux environment (bound in references/engine-dependency.json) and points the launcher at it. The launcher is never downloaded and never downloads; until that component is provisioned and probed it exits 127. Say the engine is unavailable in this environment instead of trying to install or fetch it, and no Node or other runtime is required. Pass a named source file or route as `--target <path>`. It loads PRODUCT.md, DESIGN.md, the matching surface brief, and native-platform guidance when applicable; follow its directives and do not rerun it. <!-- rule:skill-setup-context -->
2. Load the request's playbook: its Commands-table reference for an explicit/implied sub-command, or [reference/new-work.md](references/engine-data/reference/new-work.md) for a new surface or replacement visual world. Inspect target and incumbent visual truth before editing. When the app cannot run, start with committed visual-regression goldens or screenshot fixtures; verify target and freshness against current tokens, CSS, components, or assets, resolve conflicts, and compare theme/variant captures. <!-- rule:skill-setup-command-ref --> <!-- rule:skill-setup-read-project -->
3. After resolving analysis and direction, read [reference/craft-floor.md](references/engine-data/reference/craft-floor.md) immediately before any UI edit, including small refinements. It carries the quality floor, the absolute bans, and the reflexes no detector catches. Do not load it for planning-only work. <!-- rule:skill-craft-floor-load -->

**Launcher unavailable:** On refusal or failure, send a separate message **before the next tool call**: “Context loading did not run; I’ll read the existing project context directly.” Then read existing PRODUCT.md and DESIGN.md without inventing missing context, follow applicable steps 2–3, including reading [reference/craft-floor.md](references/engine-data/reference/craft-floor.md) immediately before any UI edit, and continue through permitted tools. This applies to planning and editing; launcher failure alone does not block either.

## How to design

- **The brief wins.** Honor pinned aesthetics, eras, materials, fonts, and palettes even when they conflict with a saturated-pattern warning. Redirecting a clear brief toward your taste is failure. <!-- rule:skill-brief-wins -->
- **Refinement preserves; redesign replaces.** Refinement keeps the incumbent identity, behavior, copy, and everything outside scope. Ask before replacing factual copy or adding claims. Redesign keeps product truth, content, function, native affordances, and constraints, but treats the old look as evidence and anti-reference; choose a replacement world in new-work and replace DESIGN.md. Never split the difference into polish on the discarded look. <!-- rule:skill-world-change-semantics -->
- **Loaded symbols stay out of the decoration.** A subject's world does not license emblems tied to militarism, supremacy, or hate movements as motifs, badges, or ornament, such as the Rising Sun flag's rays, the Confederate battle flag, or Nazi-era insignia and their stylised variants; reach for that world's neutral forms instead. Content that documents such a symbol as fact stays as it is. <!-- rule:skill-loaded-symbols -->
- **Visual authority is evidence, not a filename.** Missing DESIGN.md alone does not make a project greenfield; new-work decides whether to preserve, expand, or replace the incumbent world. <!-- rule:skill-new-work-gate -->

## Modes

The mode names what the visitor's success looks like on this surface.

- **Persuade:** the visitor decides and acts; design is the product. Landing pages, marketing, campaigns, pricing. Earn attention and action. Ship real imagery when the brief needs it; follow the committed world, not category habit. <!-- rule:brand-register-core -->
- **Operate:** the visitor completes a task. App UI, dashboards, editors, admin, settings, tools. Scanability, consistency, native expectations, and the real usage scene outrank expression. Brand lives in precise details. <!-- rule:product-register-core -->
- **Read:** the visitor understands something. Docs, articles, guides, help, changelogs. Structure for comprehension, then make the reading experience worth staying in. <!-- rule:skill-read-register -->
- **Experience:** the visitor is inside the work itself. Portfolios, galleries, showcases. Let the artifact lead from the first viewport; the interface recedes. <!-- rule:skill-experience-register -->

Choose the mode from the requested surface, not the product, and persist it only in that surface brief. A tool's landing page is still Persuade; a fashion house's documentation is still Read; a docs index is Read, not Persuade. See [new-work.md](references/engine-data/reference/new-work.md) for new surfaces and [operate.md](references/engine-data/reference/operate.md) for deeper Operate/Read guidance. <!-- rule:skill-visitor-mode -->

## Commands

| Command | Category | Description | Reference |
|---|---|---|---|
| `craft [feature]` | Build | Deprecated alias for an ordinary new-work request | [reference/craft.md](references/engine-data/reference/craft.md) |
| `shape [feature]` | Build | Plan UX/UI before writing code | [reference/shape.md](references/engine-data/reference/shape.md) |
| `init` | Build | Capture durable product context in PRODUCT.md | [reference/init.md](references/engine-data/reference/init.md) |
| `document` | Build | Generate DESIGN.md from existing project code | [reference/document.md](references/engine-data/reference/document.md) |
| `extract [target]` | Build | Pull reusable tokens and components into design system | [reference/extract.md](references/engine-data/reference/extract.md) |
| `critique [target]` | Evaluate | UX design review with heuristic scoring | [reference/critique.md](references/engine-data/reference/critique.md) |
| `audit [target]` | Evaluate | Technical quality checks (a11y, perf, responsive) | [reference/audit.md](references/engine-data/reference/audit.md) · native: [reference/audit.native.md](references/engine-data/reference/audit.native.md) |
| `polish [target]` | Refine | Final quality pass before shipping | [reference/polish.md](references/engine-data/reference/polish.md) |
| `bolder [target]` | Refine | Amplify safe or bland designs | [reference/bolder.md](references/engine-data/reference/bolder.md) |
| `quieter [target]` | Refine | Tone down aggressive or overstimulating designs | [reference/quieter.md](references/engine-data/reference/quieter.md) |
| `distill [target]` | Refine | Strip to essence, remove complexity | [reference/distill.md](references/engine-data/reference/distill.md) |
| `harden [target]` | Refine | Production-ready: errors, i18n, edge cases | [reference/harden.md](references/engine-data/reference/harden.md) |
| `onboard [target]` | Refine | Design first-run flows, empty states, activation | [reference/onboard.md](references/engine-data/reference/onboard.md) |
| `animate [target]` | Enhance | Add purposeful animations and motion | [reference/animate.md](references/engine-data/reference/animate.md) |
| `colorize [target]` | Enhance | Add strategic color to monochromatic UIs | [reference/colorize.md](references/engine-data/reference/colorize.md) |
| `typeset [target]` | Enhance | Improve typography hierarchy and fonts | [reference/typeset.md](references/engine-data/reference/typeset.md) |
| `layout [target]` | Enhance | Fix spacing, rhythm, and visual hierarchy | [reference/layout.md](references/engine-data/reference/layout.md) |
| `delight [target]` | Enhance | Add personality and memorable touches | [reference/delight.md](references/engine-data/reference/delight.md) |
| `overdrive [target]` | Enhance | Push past conventional limits | [reference/overdrive.md](references/engine-data/reference/overdrive.md) |
| `clarify [target]` | Fix | Improve UX copy, labels, and error messages | [reference/clarify.md](references/engine-data/reference/clarify.md) |
| `adapt [target]` | Fix | Adapt for different devices and screen sizes | [reference/adapt.md](references/engine-data/reference/adapt.md) · native: [reference/adapt.native.md](references/engine-data/reference/adapt.native.md) |
| `optimize [target]` | Fix | Diagnose and fix UI performance | [reference/optimize.md](references/engine-data/reference/optimize.md) |
| `live` | Iterate | Visual variant mode: pick elements in the browser, iterate on alternatives | [reference/live.md](reference/live.md)<!-- Floe: reference/live.md is not shipped; live mode rewrites the page through a local server; not in the Floe v1 engine --> |
| `generate [n] [action] [element]` | Iterate | Variants, versions, or alternatives of a named element to choose from in the live browser; no manual picking | [reference/generate.md](references/engine-data/reference/generate.md) |

Routing: <!-- rule:skill-routing -->

- **No argument:** read [routing.md](references/engine-data/reference/routing.md) and present its context-aware menu; never auto-run a command.
- **Explicit or clearly implied request to run a command:** load its reference (native variant on native platforms) and follow it. Ask once if two commands fit.
- **Workflow or command-selection question:** read [Workflow questions](references/engine-data/reference/routing.md#workflow-questions).
- **Otherwise:** treat the request as general design work. Missing PRODUCT.md routes a new surface or replacement world through init, then new-work; a narrow refinement of existing code proceeds on the incumbent implementation as `floe-impeccable context` directs, offering init afterward rather than blocking on it.
- `teach` aliases `init`. `craft` is a deprecated alias for ordinary new-work and adds nothing. `shape` owns task discovery, then enters new-work only for visual-world and surface-concept decisions.

After init writes PRODUCT.md, resume without rerunning `floe-impeccable context`; init loads the native platform reference itself when the platform it recorded is `ios`, `android`, or `adaptive`.

**Pin / Unpin:** `<skill-base-dir>/scripts/floe-impeccable.sh pin <pin|unpin> <command>` creates or removes a standalone `<command>` shortcut. Report the script's result concisely; relay stderr verbatim on error.

**Hooks:** `floe-impeccable hooks <on|off|status|ignore-rule|ignore-file|ignore-value|reset>` manages the design detector hook for this project (auto-runs the detector after UI file edits and surfaces findings). Load [reference/hooks.md](reference/hooks.md)<!-- Floe: reference/hooks.md is not shipped; editor design hooks; not in the Floe v1 engine --> when the user invokes it with any argument.

**Doctor:** `floe-impeccable doctor` reports and repairs drift between this project's Impeccable artifacts (PRODUCT.md, DESIGN.md and its sidecar, config, surface briefs, the hook) and what this version reads. Load [reference/doctor.md](reference/doctor.md)<!-- Floe: reference/doctor.md is not shipped; doctor reports drift in upstream hook and update artifacts Floe does not install --> when the user invokes it, or when they ask what is out of date, stale, or needs refreshing. A `CONTEXT_STALE` directive in Setup's output is the cheap subset of the same report; act on it there per its own instructions rather than running doctor unasked. <!-- rule:skill-doctor-route -->

**Never repair drift as a side effect of a design task.** A `CONTEXT_STALE` finding is reported, not acted on, unless the user asks. The one exception is a finding marked `auto`, which the next write to that file performs anyway. <!-- rule:skill-drift-not-a-side-quest -->
