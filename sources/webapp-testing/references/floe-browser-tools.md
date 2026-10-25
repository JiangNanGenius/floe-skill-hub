# Floe browser tool surface (as bound by this skill)

Audited 2026-10-26 read-only against the current native browser tool descriptors in the active
App checkout (`FloeApp/Browser/BrowserTools.swift`, protocol source SHA `f274b1f2` plus the main
owner's in-progress edits). Parameters are the tools' own JSON schemas. If a tool is missing,
disabled for the task, or its schema differs, the task's ceiling decides — this skill requests
nothing beyond its floe.json capabilities (`browser.observe`, `browser.interact`,
`execution.remote`, `workspace.read`, `workspace.write`) and never adds authority.

## Reading

| Tool | Parameters (schema root) | Notes |
| --- | --- | --- |
| `browser.observe` | `{tabID?, cursor?, profile ∈ semantic,design, designAction ∈ capture,facts,release, captureID?, needsFile?}` | FIRST choice for page content. **This skill always uses the default `profile=semantic` (omit `profile`); the design-profile fields are the App owner's concurrent H3 capture surface and must not be treated as test hooks.** Semantic snapshot: `documentID`, `revision`, `url`, `title`, `isLoading`, viewport/scroll, `tabs[]`, `nodes[]` (`ref`, `role`, `name`, `text`, `value`, `state{}`, `bounds{x,y,width,height}`), `nextCursor`. Paginate before concluding data is missing. |
| `browser.events` | `{tabID?, afterSequence?, limit 1..50 (default 20)}` | Bounded CDP-shaped lifecycle/DOM event queue with sequence numbers; never contains typed text or page text. Read to reason about late results. |
| `browser.wait` | `{tabID?, condition ∈ load,dom,selector,text,documentChanged,idle; value? ≤512B; quietMilliseconds 100..5000; timeoutMilliseconds 250..30000}` | `text`/`selector`/`documentChanged` require `value`. Timeout is a tool error — record FAIL/TIMEOUT, never silence. |
| `browser.tabs` | `{}` | List tabs with exact IDs and active state; changes nothing. |
| `browser.screenshot` | `{tabID?}` | Viewport capture + on-device OCR `visualTextRegions` (`text-N` refs, pixel bounds). Returns `screenshotArtifact{id, relativePath, mimeType, byteCount, sha256, pixelWidth, pixelHeight}` — retain path+digest as evidence. Prefer observe refs over this path. |

## Acting (browser.interact)

| Tool | Parameters | Notes |
| --- | --- | --- |
| `browser.navigate` | `{url, tabID?}` | http/https only. Loopback allowed only for this task's currently-ready managed services. |
| `browser.tab` | `{action ∈ create,activate,close; tabID? (absent for create)}` | create returns the new tab ID; activate/close need exact IDs. |
| `browser.type` | `{ref, documentID, text ≤16 KiB, submit?, tabID?}` | Non-password elements only; password fields require human takeover. |
| `browser.click` | `{ref, documentID, tabID?}` | Preferred action: a `browser.observe` ref bound to the current document. |
| `browser.clickVisualText` | `{documentID, reference "text-N", screenshotSHA256, tabID?}` | Click an OCR anchor from the latest screenshot; evidence-bound. |
| `browser.clickPoint` | `{documentID, x,y (screenshot px, 0..10000), screenshotSHA256, fallbackReason ∈ noStructuredTarget,insufficientStructuredInformation, tabID?}` | LAST resort; ordinary DOM controls with refs are rejected by design. Public WebKit hit-testing, not trusted iOS input. |
| `browser.scroll` | `{deltaY required, deltaX?, tabID?}` | ±20000 bound. |
| `browser.panel` | `{action ∈ requestUser,hide; reason? 1..500 chars; tabID? (requestUser only)}` | Human interaction handoff (login, captcha, file pickers, password fields). While held by the user, browser mutations return `needsUser`; other authorized tools keep working. Re-observe after the return event. |

## Result semantics (stale/late handling)

- Statuses: `ok`, `stale`, `blocked`, `needsUser`, `timeout`, `failed`. Anything but `ok`/
  `needsUser` surfaces to the model as a tool error with the protocol message.
- `documentID` changes at every main-frame commit. Refs, visual-text anchors and point clicks are
  bound to their document: stale → `stale` (code `document`, "The page changed; observe it
  again"), then observe before the next action.
- A `stale` result after a click/type does **not** prove the action didn't land. Read current
  state (or server state) before replaying side effects.
- Session/tab lifecycle failures are `stale` too (`released`, `session`, `tab`): the tab may be
  gone; a browser handoff can be fenced by the runtime when its original run finished.
- Temporary chats and runs without a task owner cannot open the browser at all (`blocked` at the
  tool boundary); tasks that disabled the browser keep it disabled.

## Evidence retention

Screenshot artifacts arrive as `{relativePath, mimeType, byteCount, sha256}` inside the task's
artifact store; record the path+sha256 in `results/webapp-testing.jsonl` via
`scripts/record_case.py --set screenshot_path=… --set screenshot_sha256=…` immediately after
capturing. Observations and events are bounded JSON — keep the deciding excerpt in the case
detail, not the whole payload.
