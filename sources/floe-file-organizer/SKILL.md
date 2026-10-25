---
name: floe-file-organizer
description: Organize workspace files through an inventory-plan-preview-commit-verify loop; deletes happen only via recoverable archive moves.
---


# Floe File Organizer

Organize task-workspace files with a previewed plan and a recoverable commit. Every move, rename or delete is a planned, reviewable operation — nothing destructive happens silently.

## The loop: inventory → plan → preview → commit → verify

1. **Inventory** — `workspace.listDirectory` / `workspace.searchFiles` / `workspace.inspectFileMetadata`. Classify candidates: type, size, name pattern, last-modified, duplicate hashes (content identity beats name similarity).
2. **Plan** — write `organize-plan.md`: every operation as one line (`MOVE a → b`, `RENAME x → y`, `TRASH z (recoverable)`), with the reason and the target folder convention the user approved. Conflicts (same destination name, cross-device moves, permission-skewed entries) are flagged in the plan, never resolved by guessing.
3. **Preview** — show the user a summary by group (counts + notable examples + total size), the exact operations file, and an explicit "undo path" for each: moves record the reverse; "deletes" become moves into a dated `.archive/` staging folder inside the workspace (recoverable), never `deleteFile` at plan time.
4. **Commit** — only after the user's normal task authorization covers the edits: `workspace.moveFile` / `workspace.copyFile` for relocations; `workspace.createDirectory` for structure. Apply in dependency order (parents before children), re-checking each source path exists with the expected size/hash before touching it.
5. **Verify** — re-list the affected directories; compare against the plan line by line; report actual results, including any operation that failed mid-way and the current real state (partial commits stay honest: state exactly what moved and what didn't).

## Rules
- A delete is a move to `.archive/<date>/` first; `workspace.deleteFile` only on the user's explicit per-round instruction pointing at already-archived items.
- Never touch: files the task didn't scope, dotfiles/config unless named, running artifacts (jobs/services own their files — check the job registry state before organizing workspace output).
- Deduplication reports content-hash groups; the "winner" keeps the canonical name, the rest archive — the plan lists every member.
- Large sets run as a `jobs.submit` job when the task has one, so closing a view never cancels the organize pass; an interrupted job's outcome is UNKNOWN until read-only inspection confirms which operations landed.
- Name conventions come from the user's existing folders; consistency with current style beats a theoretically-better scheme.

## Report format
Operations attempted / applied / skipped(with reason); bytes and counts by group; archive location; verification re-list output. If anything looks inconsistent, stop and present the discrepancy — recovery comes before tidiness.
