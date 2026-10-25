# Skill creation and assisted import flow

Status: user requested model-assisted creation/import and durable return behavior on 2026-10-26. This contract extends the accepted native Skill Hub design; App implementation belongs to the iOS main A1 owner. It is not a new public Skill Creator package or a second agent runtime.

## User experience

`Create skill` opens a focused native assistant panel. Lead with a natural-language request and optional source files/examples. Use the existing general auxiliary text-model route, frozen when processing begins; show only a read-only model label if useful, never a model picker. Raw name/description/SKILL.md editing is an optional manual path, not the required first step. Show saved draft state, real activity, errors and generated output in the same panel.

Resolve through `generalAuxiliaryProviderAndModel()` and `generalAuxiliaryLLMModelID`, not the old Finder's list of all agent models. Preserve an explicitly configured "follow main chat model" auxiliary setting as existing routing policy; do not silently choose a different available model when a configured auxiliary model is unavailable. Creation/adaptation stays bound to the resolved provider/model for its run, including after a display promotion. Changing global settings does not swap an in-flight request. Missing/unusable configuration displays a clear configuration or retry action. A valid deterministic import still does not invoke a model unnecessarily.

`Import skill` first inspects a complete selected package deterministically. A valid upstream package is preserved byte-for-byte and does not need an LLM rewrite. Show its actual contents, provenance and requirements. When adaptation is necessary, offer `让模型适配 / Adapt with AI`; preserve the original and create a distinct adapted revision with provenance. Do not silently rewrite a published immutable package or accept model-invented privileges.

Generation finishes in `已生成，待添加 / Generated, ready to add`. Show purpose, output/files, declared permissions and preview, with one `添加到我的技能 / Add to my skills` action. Only a real installation receipt changes this to `已添加 / Added`. For an already-authorized direct-import action, use the existing install transaction and return its real receipt. User-created/adapted packages do not inherit store publisher review status.

## Durable ownership

- Reuse ConversationCenter/AgentRuntime, existing jobs, workspaces, model configuration and permission services. Add a durable feature-owned `skillAuthoring` purpose/visibility to existing conversation ownership if needed; do not misuse `.temporary` or `.notes`.
- Existing temporary chat is RAM-only, public/text-limited and navigation-discarded. Its Keep/promoter semantics must remain unchanged. This feature requires persistence, files and ordinary task-authorized tools, so it is a separate purpose on the same runtime, not a special temporary-chat loophole.
- Before submitting any model or conversion job, persist the input revision, owner/session identity, selected model, explicit workspace/environment binding and source attachment snapshot. Plain-text-only work need not install a guest. Script execution requires a resolved Linux environment with an explicit write layer, never the first project or an unowned temp directory.
- Autosave editable drafts using the existing draft persistence approach; flush on leaving the panel, scene/background transition and before submission. Opening a panel restores the persisted draft instead of creating a fresh empty state.
- The service owns running work and pending results. SwiftUI view lifetime, sheet dismissal and destination reconstruction are not cancellation signals. Each operation returns a specific result/receipt; never infer success merely because shared `center.errorMessage` happens to be nil.
- Preserve selected package bytes in an owned, bounded recoverable snapshot before relying on a file-picker lease. Failure/retry must not require an already-expired picker URL or overwrite original input.

Minimal additional durable linkage includes authoring ID/kind, input revision, state, existing conversation/run/job IDs, explicit source/artifact references, model and environment/workspace identities where used, accumulated active-processing duration, promotion state and final installation receipt. Store full messages, files and grants in their existing stores rather than duplicating them into a second database.

## State and rendering

| Durable state | Panel | Skill Hub on return |
| --- | --- | --- |
| draft | Saved input, continue editing | `继续创建 / Continue creating` or `继续导入 / Continue import` |
| running | Real stage, streamed explanation where useful, Close/check later and Cancel processing | `正在创建 / Creating` or `正在整理 / Preparing`; opens the same session |
| needsUser | Existing permission request or concrete clarification; retry is not automatic | `需要你确认 / Needs your attention` |
| ready | Generated output and Add action | `技能已生成，待添加 / Skill ready to add` |
| installed | Verified skill ID/version and View skill | `已添加 / Added`, linked to actual installed item |
| failed/interrupted | Saved input/output, actual failure, safe Resume/Retry | `处理失败 / Failed` or `处理已中断 / Interrupted`, never an empty fresh form |
| stopped | Partial output preserved and explicit resume/edit choice | `已停止 / Stopped` |
| promoted | Same work continues in ordinary task view, with a link | `已在任务中继续 / Continued in tasks`, plus the real current result |

Place a compact `继续处理 / Continue your work` shelf below the feature toolbar and above discovery content when a draft, active job or unacknowledged result exists. Each row identifies its operation and state. Opening Skill Hub does not automatically reopen a sheet, steal the current task route or create a new run. Acknowledge/archive controls can remove a finished row while the installed skill and required recoverable source remain accessible through their normal stores. No new OS notification authorization or countdown modal is required.

Closing a running panel is `稍后查看 / Check later`; `取消处理 / Cancel processing` is a separate explicit operation available at any time. Unsubmitted drafts use Close with saved-state feedback. Discard is explicit, never the side effect of a swipe-dismiss.

There is one persisted foreground authoring slot for Skill Hub creation or assisted import. A nonterminal, nonpromoted operation occupies it; starting another creation/import reopens that operation instead of creating a second run. Closing the panel does not release the slot. Completion releases it while retaining the result; explicit cancellation releases it after owned work has actually settled; dialog-approved promotion releases it after the atomic promotion commits. Saved stopped/finished results remain recoverable without occupying an active slot. Promoted ordinary tasks use the normal task lifecycle and no longer occupy the foreground slot. This serializes only this lightweight authoring/import flow, not unrelated normal tasks or the entire Skill Hub. Distinct retained records keep independent IDs and resource ownership.

## Promotion to an ordinary task

At 90 seconds of accumulated active processing, excluding user authorization/clarification waits and confirmed system suspension, offer one advisory dialog. It is not a timeout, failure or cancellation. The dialog explains that processing is still continuing and offers `继续等待 / Keep waiting` and `转为任务 / Convert to task`.

There is no persistent "Continue in tasks" button in the panel, toolbar, shelf or overflow menu. Promotion occurs only if the user chooses Convert to task in this advisory. Choosing Keep waiting retains the foreground operation and permanently dismisses this suggestion for the current operation; do not repeat it after another interval, view reconstruction, background return or process recovery. Waiting and Cancel processing remain available. Short successful work stays in the lightweight flow and does not fill the ordinary task list.

If the panel is not visible at the threshold, persist eligibility without interrupting another destination or showing a global modal. When the user explicitly reopens the active panel, show the one eligible suggestion only if the operation is still running and the suggestion has never been answered. Terminal state wins over a pending advisory. Persist the advisory decision against the operation so no repeated query or callback can show it again.

Promotion is an atomic, idempotent visibility/purpose transition on the same durable owner. Preserve conversation ID, run/job IDs, messages, files, selected environment, grants and current attempt. Do not copy messages into a second conversation, restart the LLM, resubmit scripts, switch environments or charge for another identical run. Completion and threshold firing may race; resolve from persisted terminal state and a once-only promotion transition.

User-confirmed conversion adds the ordinary task and updates the Hub shelf. Do not navigate away from unrelated work; follow the explicitly confirmed conversion's local completion state. Returning to Skill Hub opens no automatic modal. Task and Hub projections reference the same result, never two separately mutable status records. If conversion fails, retain the original foreground slot and recoverable input until the durable transition is known; do not run a second copy.

## Background and recovery

Leaving the page keeps the owned operation alive within existing runtime/system capabilities. Entering background does not promise unlimited execution; existing background policy determines continue, pause or interruption. Re-entry reconciles actual job/process/provider state before showing progress.

Process death does not imply that an old model request or install can safely be repeated. Recover from persisted attempt/commit records. If continuation cannot be proven safe, show Interrupted with preserved input and require an explicit safe retry. A committed install discovered after cancellation/restart remains Installed, not Failed or installed twice. Stale callbacks are fenced by owner/run/input revision and cannot overwrite a newer draft or another task.

Draft/result retention follows existing user-controlled storage/cleanup behavior. Do not add an age-based cleanup that deletes unacknowledged drafts, active jobs, generated skills or the only recovery copy.

## Required acceptance

1. Enter text/select an import, close before submission, return and recover the same inputs.
2. Start model creation/adaptation, dismiss, revisit and observe the same run with no second provider call.
3. Complete under 90 seconds: retain result in the Hub with no ordinary task created.
4. At 90 active seconds, show one advisory only in the active panel. Keep waiting creates no ordinary task and never prompts again. Convert creates exactly one ordinary task with the original owner/run/files. There is no other conversion button and no automatic conversion.
5. Permission/clarification wait and system suspension do not incorrectly increment the advisory threshold. Completion before an eligible dialog is presented suppresses it.
6. Race promotion, successful completion, Stop, dismissal and callbacks: no duplicate tasks, installs, calls or loss of receipts.
7. Background/termination/relaunch restores draft or actual interrupted/committed state; never displays fake ongoing progress.
8. Valid imports preserve original bytes; adaptation records a separate revision and honors authorization.
9. New model-created content is not treated as pre-reviewed storefront content. Existing temporary-chat constraints and navigation fencing remain unchanged.
10. A second creation/import returns to the occupied foreground operation; completion, settled cancellation or committed conversion frees the slot exactly once. Returning after dismissal does not accidentally free it or launch a duplicate.
11. The creator/adaptation uses the frozen configured auxiliary route, has no model-switch UI, survives display conversion without swapping models, and reports an unavailable auxiliary model without selecting an arbitrary substitute.

These checks belong to the same new-build acceptance as the native Skill Hub, rather than an untracked follow-up to the old ephemeral form.
