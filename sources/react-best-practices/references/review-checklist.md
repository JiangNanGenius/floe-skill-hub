# Review Checklist — React Code

Compressed audit list; each line expands to the matching SKILL.md rule.

## Correctness
- [ ] No state copies of derivable values (R2); no dual sources of truth (R3)
- [ ] Effect deps arrays honest; every subscription/timer cleaned up (R4)
- [ ] List keys stable domain ids; no index keys in reorderable lists (R5)
- [ ] Async races guarded; loading/error are rendered states (R10)
- [ ] No mutable module state shared across instances/requests (R9)

## Structure
- [ ] State at lowest common owner (R1); interactive islands extracted (R7)
- [ ] Context used for shared low-churn values only; split by change frequency (R8)
- [ ] Components return stable children where possible (slots/children over render-props soup)
- [ ] Forms controlled with single state owner; server validates last (R12)

## Performance (only when profiling demanded it)
- [ ] memo/useMemo/useCallback present only beside a measured reason or identity contract (R6)
- [ ] Route/heavy-widget code splits carry no first-paint essentials (R11)
- [ ] Profiler numbers recorded before/after, not adjectives

## Tests
- [ ] Behavior-level assertions; no hook-call or internal-state spying (R13)
- [ ] Failing-first discipline for each fix in the change (see the hub TDD guide)

## Report format
Findings as: file:line, rule id, quote, suggested fix. Fixes land on a copy or tracked patch; the project's real lint/typecheck/test/build commands run in the task's authorized Linux environment via exec.shell and their actual output is what gets reported.
