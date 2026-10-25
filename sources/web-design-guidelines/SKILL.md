---
name: web-design-guidelines
description: Checkable web design + accessibility rules (WCAG 2.2 floor) with a deterministic contrast worksheet and evidence-based review procedure.
---


# Web Design Guidelines (Floe original checklist)

Checkable rules for web interfaces, aligned to publicly documented standards (WCAG 2.2 as the accessibility floor, platform UI conventions). Every finding cites the rule id and the rendered evidence — screenshots, DOM/ARIA output from `browser.observe`, or source lines.

## A — Accessibility (the floor, not the ceiling)
- A1 Semantics: real `<button>`/`<a>`/`<input>` elements; landmarks (`header/nav/main/form`) present and unique; heading order never skips a level.
- A2 Names: every interactive element has an accessible name; icon-only controls get a label; images have `alt` with meaning (decorative ⇒ `alt=""`, never omitted). Placeholders are hints, never labels.
- A3 Keyboard: everything reachable in a sensible order; no keyboard trap; skip-link or equivalent for repeated navigation; focus never invisible (A4) and never suppressed by `outline:none` without a visible replacement.
- A4 Focus visibility: contrast between focused and unfocused state is obvious at a glance; `:focus-visible` styling for keyboard users is deliberate.
- A5 Contrast: text ≥ 4.5:1 (3:1 for ≥24 px bold / ≥30 px), UI component edges and icons ≥ 3:1 against adjacent colors. Procedure + worksheet: references/contrast-worksheet.md.
- A6 Motion: honor `prefers-reduced-motion` (no parallax/autoplay storms); nothing flashes >3 Hz; autoplaying media is user-stoppable and off by default in product flows.
- A7 Forms: labels bound; error messages say what's wrong and where, associated via `aria-describedby`; required fields announced; inputs get correct `type`, `autocomplete`, inputmode.
- A8 Targets: ≥ 24×24 CSS px (platform guidance; 44 px where touch is primary), with ≥ 8 px gaps when smaller.
- A9 Content order: DOM order = intended reading order; tab order matches; zoom to 400% without horizontal loss of function.

## D — Design system mechanics
- D1 Typography: ≤ 2 families; a modular scale (e.g. 1.2–1.334) with named steps; body ≥ 16 px; measure 45–75 chars; line-height 1.4–1.7 for body, tighter for headings.
- D2 Spacing rhythm: one spacing scale (4/8-pt family); related elements closer than unrelated (proximity groups); no arbitrary one-off margins.
- D3 Color: semantic tokens (surface/ink/accent/danger) over raw hex at call sites; light/dark both defined; color never the only signal (pairs with A2/A7).
- D4 States: every interactive element gets hover, focus, active, disabled, loading — designed, not defaulted. Empty, error and offline states are designed screens, not console logs.
- D5 Responsive: minimum supported width first; touch and pointer variants both considered; content reflows, doesn't shrink to illegibility; tap zones grow with viewport.
- D6 Affordance: anything clickable looks clickable; disabled ≠ invisible; loading shows skeleton or progress with actual byte/step truth when measurable (never a fake spinner timer).
- D7 Copy: buttons say the verb of the outcome ("Save draft", not "OK"); errors say the fix path; empty states say the next action. No internal implementation terms in user screens.
- D8 Density honesty: a dashboard of small cards is fine; a nested card-in-card stack that only adds chrome is a finding.

## Review procedure
1. Live pass: open the page in the app's controlled browser (`browser.observe`) — walk tab order, read the accessibility tree, check contrast on rendered colors, resize narrow, toggle reduced motion where available.
2. Source pass: map findings to files/lines with `workspace.searchFiles`/`readFile`; fixes proposed as tracked patches; the project's own tests/lint/build run through `exec.shell` in the task's authorized Linux environment.
3. Report format per finding: id, evidence (screenshot / a11y-tree extract / computed ratio), severity (blocks use / degrades / polish), suggested fix. Regressions compared against a saved baseline, same as the a11y-audit skill's flow.

## Limits
- This is a rules guide; audits with the controlled browser belong here, and the deeper WCAG remediation catalog lives in the hub's `a11y-audit` entry. Automated tools find ~30% of issues — the manual passes above are the remainder.
- Claims follow evidence: "contrast 3.1:1 fails A5 body minimum (needs 4.5)" is a finding; "looks inaccessible" is not.
