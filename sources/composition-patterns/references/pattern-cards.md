# Pattern Selection Cards

| Situation | First choice | Why / tradeoff |
|-----------|--------------|----------------|
| One wrapper, unknown inside | `children` slot (P1) | Keeps parent ignorant of content; type it `ReactNode` |
| Pieces must talk to each other | Compound with internal context (P2) | Context stays private; never ship it as the app's data bus |
| 2–4 looks, 1 behavior | Variant union (P3) | Invalid combos become unnameable |
| Both app-controlled and self-managed use | Controlled-when-prop-present (P2 tail) | One rule: defined prop wins; document it |
| Implementation will churn (store swap, SSR) | Stable hook interface (P5) | Consumers freeze; provider evolves |
| Data may be missing/late | Explicit fallback nodes (P6) | Empty states are testable states |
| Third party must own the DOM node | Named escape hatch (P8) | Keep out of shared library APIs; comment the reason |
| Spacing/order disagreements in reviews | Geometry/meaning split (P9) | Margin owner becomes provable |

## Anti-pattern quick test
- Boolean prop count ≥ 3 → variant union or split components.
- Context carries arrays of business entities → it's a store, not composition wiring.
- `render` prop returns JSX that closes over parent internals → replace with controlled state + children.
- Component exposes `setState` through a ref → it wants two components or a lift (P4).
