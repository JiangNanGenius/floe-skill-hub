---
name: react-best-practices
description: Original React rules: state placement, derivation over duplication, honest memoization, effects, keys, async races and measurement-driven performance.
---


# React Best Practices (Floe original guide)

Rules for React application code written inside Floe tasks: readable first, measured second, memoized never-by-reflex. Examples are deliberately small; apply the reasoning, not the snippets.

## R1 — State lives at the lowest component that needs it
Data two siblings need goes in their parent; data a page needs goes in the page or a store the page owns. Pushing state up is cheap to reverse; pulling scattered state back together is not.

## R2 — Derive, don't duplicate
If a value can be computed from props/state, do not keep a second state copy of it. `const visible = items.filter(i => i.on)` beats a `visibleItems` state that drifts on every mutation. Expensive derivations get memoization (R6), not duplicated truth.

## R3 — One source of truth per fact
The same value living in local state, a context, and a URL query is three values. Choose the owner; sync deliberately (URL as truth for shareable state; server cache as truth for remote data); delete the rest.

## R4 — Effects are for external systems only
Subscriptions, imperative APIs, browser APIs, timers. A missing dependency in the deps array is a bug, never a style choice; `eslint-plugin-react-hooks` rules apply. If an effect "sets state from state", it is usually R2 in disguise. Clean up what you start — every listener, observer and timer leaves in the same effect it entered.

## R5 — Key stability
`key` is identity across renders. Use the item's stable domain id. Array index as key is only correct when the list is append-only and items are stateless; reordering or filtering with index keys corrupts component state and diffing.

## R6 — Memoize with evidence
`memo`/`useMemo`/`useCallback` add bookkeeping cost. Apply only after profiling shows the re-render or recomputation is actually expensive, or when a stable function identity is required by a memoized child or effect contract. Default answer: reorganize data (R2, R7) instead.

## R7 — Move interactivity down, not state up
A toggle that re-renders the whole page means the page owns state its margins don't need. Extract the interactive island; leave the static surroundings as stable children (JSX passed in, not re-created).

## R8 — Props over context for leaf data
Context is for genuinely shared, rarely-changing values (theme, locale, session). Per-item data through context re-renders every consumer; pass props. Split contexts by change-frequency (auth identity vs auth loading state are different contexts).

## R9 — Never share mutable module state across requests
A module-scope cache or counter is per-process, per-instance. On server rendering it leaks between requests; on the client it breaks under hot reload and multiple app instances. Scope to the component, the store, or the request.

## R10 — Async: race and cancel
Fetches that can overlap need cancellation or a "latest wins" guard (`AbortController`, a request id compared in `.then`). Loading and error are real states, not toasts: render them. Don't refetch in a loop because an effect dependency changed identity every render (R6 covers the stable-identity contract).

## R11 — Code-split at route and heavy-widget boundaries
Dynamic `import()` for below-the-fold and rarely-used heavy features (charts, editors, maps); preload on intent, don't split what the first paint needs. Bundle growth shows up as startup cost on mobile — verify with the bundle analyzer in the task's Linux environment (`exec.shell`) before/after.

## R12 — Controlled forms; validation at the boundary
Keep form state in one place; validate against the schema on submit and on blur where it helps the user; server validation remains the final authority. Uncontrolled with refs is fine when nobody re-renders on input.

## R13 — Test behavior, not implementation
Screen-level tests render the component as users use it and assert what's visible; internal state and hook calls are private. Failing tests from R2/R3 refactors mean the test knew too much.

## Measurement before every optimization
React DevTools Profiler for render causes; the app's own build stats for bundle size; wall-clock before/after for recomputations. "Feels faster" is not evidence — record the numbers in the task report.

## Running checks in a Floe task
Read/modify project code with `workspace.*` tools; run the project's real test, lint, typecheck and build commands inside the task's resolved Linux environment via `exec.shell` (long suites through `jobs.submit`). This guide grants nothing by itself; tool ceilings come from the task's authorization.
