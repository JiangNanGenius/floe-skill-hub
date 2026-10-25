---
name: composition-patterns
description: Original React composition guide: slots, compound components, variant unions, controlled/unilateral contracts, escape-hatch discipline.
---


# React Composition Patterns (Floe original guide)

How to shape components so they stay testable and grow without forks. Each pattern names the problem it solves and the cost it accepts.

## P1 — Children as slots; props as knobs
A wrapper takes `children` (opaque content) and a small set of typed props (behavior). If a component takes six flags, it is three components.
Cost: composition indirection across files — mitigate with names (`<Card.Header>` reads better than `<Card part="header">`).

## P2 — Compound components with one internal contract
Related pieces (Tabs/List/Accordion/Menu) share context that carries structural wiring (ids, registration, active index) — never the app's business data. Parent owns the pattern state; children consume the contract through hooks. Users control either the whole (`defaultActive`, uncontrolled) or the piece (`active` + `onChange`, controlled) — support both by making the controlled prop the authority when present.

## P3 — Explicit variants over boolean soup
`<Button intent="danger" size="sm">` beats `<Button danger small secondary>`. Booleans multiply silently into impossible combinations (danger+secondary+disabled); a variant union makes invalid states unnameable and CSS mapping mechanical.

## P4 — Lift state, keep handlers local
State that two siblings negotiate belongs to their nearest common parent; the handler that formats a local input stays local. Parent passes down value+onEvent, not half-computed results — children render meaning, parents own truth.

## P5 — Decouple the context interface from its implementation
Consumers depend on a stable hook (`useDialog()` returning {open, show, close}); the provider tree behind it (reducer, store, portal owner) can be swapped without touching a single consumer. Write the interface first, in TypeScript, before the provider exists.

## P6 — Fallbacks are part of the contract
Slots render defaults when empty (`children ?? <DefaultPanel/>`); asynchronous content gets an explicit loading shape; empty collections get an empty-state node. A component that disappears on missing data hides bugs the next person will not see until production.

## P7 — Ref access as a prop (React 19+)
React 19 passes `ref` to function components as a normal prop; `forwardRef` remains for compatibility and for genuinely imperative handles. Expose imperative APIs (`focus`, `scrollIntoView`) only when the platform demands it — DOM focus, media, canvas — never as a data backdoor into a component's state.

## P8 — Escape hatches last, and named
Render-prop children, `asChild`/clone-element tricks and generic `render` slots erase the type surface and re-parent state unexpectedly. Reach for them only for a specific documented need (third-party integration that must own the DOM); when you do, keep them out of the public API of shared library components.

## P9 — Layout owns geometry; content owns meaning
A `Stack`/`Grid`/`Split` component knows spacing and ordering; it must not know what its children mean. Conversely content components never inline layout margins that the parent owns — that's where "one more mb-2" forks come from.

## P10 — Testing composition
Test each piece through its public props/children contract and the compound pattern through user-visible behavior (activation changes what's visible and announced). A pattern test that reaches into context internals is testing wiring, not behavior.

## Applying in a Floe task
Read the project first (`workspace.searchFiles`/`readFile`); propose pattern changes as tracked patches or a copy, with the project's real typecheck/test/build run through `exec.shell` in the task's authorized Linux environment. Show the render-behavior difference (before/after) in the report, not just the code.
