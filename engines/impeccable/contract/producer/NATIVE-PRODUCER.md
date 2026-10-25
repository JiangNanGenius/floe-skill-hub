# Native measurement producer guidance (A2)

Audience: the iOS main owner implementing the controlled WebKit design capture and file bridge.
This document is guidance plus a typed schema — it is **not** an App edit and it does not
prescribe native architecture. Contract: [`../SNAPSHOT-CONTRACT.md`](../SNAPSHOT-CONTRACT.md).

## 1. What the producer must emit

One snapshot document per capture, conforming to
[`snapshot.schema.v1.json`](snapshot.schema.v1.json), plus one identity document conforming to
[`identity.schema.v1.json`](identity.schema.v1.json). The engine consumes both; the snapshot
alone is not sufficient for a real capture.

The measurement itself is a **fixed, audited script** running in an isolated content world.
It reads only:

* `document.documentElement` / `body` geometry, `window.innerWidth/innerHeight`,
  `window.scrollX/scrollY`, `document.compatMode`, `location.hostname`;
* per element: `tagName`, `namespaceURI`, `parentElement`, `childNodes` (element ids, text data,
  CDATA), `getAttributeNames()`/`getAttribute()`, `getComputedStyle(el)` for the **138 columns**
  in [`style-props.v1.json`](style-props.v1.json) in that exact order, `getComputedStyle(el,
  '::before'|'::after')` for the **23 columns** in [`pseudo-props.v1.json`](pseudo-props.v1.json)
  only where computed `content` is not `none`/empty, `getComputedStyle(el, '::placeholder').color`
  for text controls with a `placeholder`, `getBoundingClientRect()`, the eight metrics
  (`clientWidth`, `clientHeight`, `clientLeft`, `scrollWidth`, `scrollLeft`, `offsetWidth`,
  `offsetHeight`, `scrollHeight`, `null` → JSON null), `checkVisibility({checkOpacity:false,
  checkVisibilityCSS:true})` (or `-1` when the method is missing), the element's **own** direct
  text client rects (`dl`) and their union (`d`), last-word rects for `P/LI/DD/BLOCKQUOTE/
  FIGCAPTION`, `isContentEditable`, `hidden`, `typeof el.id !== 'string'`,
  `typeof el.className !== 'string'`, the pseudo-class states in
  [`state-pseudos.v1.json`](state-pseudos.v1.json), media intrinsics for `IMG/VIDEO/CANVAS/
  PICTURE` (`naturalWidth/Height`, `videoWidth/Height`, `width`, `height`, `currentSrc`, `src`,
  `complete` for images, `readyState` for video), running animations/transitions, and open
  shadow trees (`shadowRoot`, `assignedSlot`);
* document level: `outerHTML` of a clone with tool-injected nodes removed, `body.innerText`,
  `@keyframes` rules with their frame selectors, and same-origin or CORS-readable linked
  stylesheet text.

It must **not** traverse iframes, must not mutate the page, must not read cookies/storage, and
must not evaluate anything the model or the page supplied.

## 2. Element identity and ordering

* Walk in document order from `documentElement`; assign `id = index + 1`.
* Append open shadow-tree elements **after** every light-DOM element, linking them with `sh`
  (host), `as` (assigned slot) and `ts` (text slot). A shadow tree that would cross the element
  budget is dropped whole, and so is every tree after it — record that in `diagnostics`, never
  as a silent truncation.
* `strings` is the interned value table; every style/pseudo column entry is an index into it.
  An empty string is a legitimate interned value and is **not** the same as an unrecorded
  column: omitting a column from `styleProps` is what makes the engine report a parity gap.
* `els[i].s.length` must equal `styleProps.length` for every element. The adapter rejects a
  mismatch (`error.code: schema-mismatch`).

## 3. Caps and budgets

| Limit | Value | Source |
| --- | --- | --- |
| max elements | 30000 | upstream capture default |
| max snapshot bytes | 48 MiB | upstream capture default; the Floe budget may be lower |
| max rounds (Needs→Facts) | 4 | Floe budget |
| max hit tests | 4096/round, 16384 total | Floe budget |
| timeout | 120000 ms | matches the guest `exec.shell` foreground limit |

Exceeding a budget is a **failure**, not a partial pass: the result carries
`status: failed`, `budget.exceeded: [...]` and exit 1. On iPad, a pure-interpreter riscv64
guest is the expected bottleneck; capture size and round count are the two knobs to bound.

## 4. Answering Needs (the hit-test fixpoint)

1. The engine returns `needs.hitTests` (points in CSS pixels, viewport coordinate space, at the
   scroll position recorded in the snapshot) plus `hitTestsBits`.
2. The native side answers **on the same document identity**: `elementFromPoint(x, y)` → `top`,
   `elementsFromPoint(x, y)` → `stack`, both mapped to snapshot element ids (`0` when the
   element is not in the capture). If the page moved, refuse and re-capture instead of answering.
3. Facts must carry the full binding (`taskId`, `sessionId`, `tabId`, `documentId`, `captureId`,
   `documentGeneration`) and echo `xBits`/`yBits` so the adapter can prove the point is the one
   that was asked for. The upstream lookup key is the exact double bits.
4. Re-run with `--facts`. Deterministic runs converge in one or two rounds; the cap only guards
   against a page that refuses to answer.
5. A point that cannot be answered (element gone, fenced capture, out of viewport) keeps
   `"unanswerable": true` with a `reason`. The engine then reports `hit-test-fixpoint:
   unanswered` and the verdict cannot be clean.

`needs.scrollProbes` are element ids the rules asked about for content hidden at rest. v1 has no
scroll-probe producer, so they stay unanswered and are reported as such.

## 5. Privacy obligations (mandatory)

* `producerTrust` is the constant `native-fixed-script`; `producer.scriptDigest` is the sha256 of
  the exact fixed script bytes that ran. A model-declared or page-declared trust value is
  rejected by schema.
* `redaction.policy` is `floe.impeccable.redaction.v1` and `redaction.applied` must be `true`.
  Before the snapshot leaves the device, drop: `input[type=password]` values, form control
  values (`input`, `textarea`, `select`), and credential-bearing attribute values (for example
  `value`, `autocomplete` secrets, tokens in URLs). Record per-category counts
  (`passwordInputs`, `formValues`, `credentialAttributes`, `textRuns`).
* Redaction happens in the fixed producer, not by post-processing the JSON with model-authored
  logic, so a finding can never be produced from a value the policy should have dropped.
* Snapshots contain full `outerHTML` and `innerText`: treat them as sensitive task data. Keep
  them in the task-owned workspace or resolved environment, delete after the scan, and never log
  bodies or copy them into another task's workspace.

## 6. File bridge

Stage the snapshot, identity and facts through the task-owned workspace or the resolved
environment's secure file path, and read the result back from the same place. The engine never
chooses a directory, never touches another task's workspace, and has no network. Installation
and execution OS/architecture are separate facts: the engine is a static riscv64 ELF that runs
in the task Linux guest through the existing `exec.shell`/jobs lifecycle.

## 7. Coverage the producer cannot supply in v1

These passes are **uncovered** and each blocks a clean verdict; do not present their absence as
a pass:

| Pass | Why it is uncovered |
| --- | --- |
| `pixel-contrast` | needs `loadImage`/`readPixel` or the upstream PNG two-shot diff; a viewport JPEG is not a pixel source |
| `reveal-sweep` | needs pre-capture scrolling; content revealed only by scrolling is never measured |
| `content-hidden-at-rest-measure` | the upstream hidden-text step is not ported; scroll probes stay unanswered |
| `script-errors` | needs a console channel; not part of the fixed measurement |
| `cross-origin-iframe` | WebKit isolation forbids the read; `SnapshotDom` carries no frame content |
| `same-origin-iframe` | the capture producer never traverses frames, so in-frame rules are lost |
| `screenshot-diff`, `consent-overlay-hiding` | live-page mutation/evidence passes; out of scope, not required for a clean verdict |

Consequence for the product surface: v1 reports findings, Needs, or `inconclusive`. It never
certifies a page clean, and an empty finding list must be shown together with
`coverage.uncoveredRequired`.

## 8. WebKit parity notes

* The 138 columns use Chrome/WebKit `getComputedStyle` spellings; the list already contains both
  `clipPath`/`clip-path` and the `webkit*` aliases, so send what WebKit reports for each name and
  let the engine's own `unknown_style_props` diagnostic name any gap. WebKit returns different
  shorthands (for example `background`, `outline`, `textDecoration`) and different
  `checkVisibility` behaviour; both surface as `style-parity: partial` with the property names in
  the receipt rather than as a silent difference.
* Send empty strings for properties WebKit does not support, never omit the column.
* `textLines: true` only when the per-line rects (`dl`) were really recorded; without them the
  line-level rules stand down and the receipt says so.
* Set `anim`/`shadow` only when `getAnimations()` and the shadow walk really ran.
* Numbers are JSON doubles; keep full precision (`float_roundtrip` is enabled in the pinned
  engine) so hit-test keys match bit for bit.
