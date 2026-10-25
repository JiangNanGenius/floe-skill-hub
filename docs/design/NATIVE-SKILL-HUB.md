# Floe native Skill Hub design contract

Status: native discovery visual direction accepted by the user on 2026-10-26. Native App implementation remains owned by the iOS main thread. Concepts are design references, never App acceptance evidence.

## Product structure

Skill Hub is the existing App's destination for discovering task skills and connecting tools. It retains the stable outer split view, task history and primary workspaces. It is a native store experience, not an embedded website or a settings list with covers added.

The user accepted the light iPad concept: SF system typography, semantic grouped backgrounds, native blue tint, two editorial feature covers, clear categories and compact skill rows. Dark appearance uses semantic system backgrounds and the same hierarchy. Existing App icon and SF Symbols are authoritative; illustrative concept logos are replaced with real assets.

Referencing ChatGPT's Apps discovery means separating discovery, detail, connection and connected-state management. It does not introduce ChatGPT authentication, a new Floe account, partner claims, or a clone of the App shell.

## Navigation and content

- Keep the existing sidebar destination; its visible title becomes `Skill Hub` in both locales, with a localized accessibility description. Do not rebuild the outer split view.
- The content toolbar has `发现 / Discover` and `已添加 / Added`, a native search field and a plus menu. Added contains both installed skills and configured MCP connections; it does not erase existing imported or user-created items.
- Discover opens with two editorial skill selections, then the category/filter row and the complete directory. The first editorial selection must identify `Impeccable` explicitly, with a web/UI design description. No Office/document-making description for it.
- Add a distinct, always-findable `MCP 与连接器 / MCP & connectors` section in the first discovery screen, above the long skill directory. It offers `连接 MCP / Connect MCP`, `创建服务 / Create service`, and `管理连接器 / Manage connectors`. It remains a simple native grouped action region rather than three marketing cards.
- `Connect MCP` opens the existing MCP server editor. `Create service` opens the existing MCP component's new A3 wizard. `Manage connectors` opens the existing connector/credential management destination. No duplicate registry, account store or service supervisor.
- The plus menu retains `导入技能 / Import skill`, `创建技能 / Create skill`, `连接 MCP / Connect MCP`, and `创建 MCP 服务 / Create MCP service`. Existing import/create functionality is preserved.
- Creation and assisted import use the [durable authoring flow](SKILL-AUTHORING-FLOW.md): one foreground operation, fixed auxiliary model, durable drafts/progress/results, cancellation at any time, and a once-only advisory after 90 active seconds. Only its Convert to task choice promotes the same owner/run; no automatic promotion or separate conversion button. Keep waiting suppresses further suggestions for that operation. Do not retain the old dismiss-and-forget form behavior.
- Add a content-kind scope `全部 / All`, `技能 / Skills`, `MCP` to search/Added filters where both kinds are visible. Skill-only categories do not incorrectly classify an arbitrary user MCP endpoint. Search covers signed skill metadata and existing real connector metadata; do not invent a third-party MCP marketplace to fill the page.

## Store directory

Use seven stable main categories: office/documents, writing/communication, research/data, design/creation, web/development, product/requirements, productivity/organization. Categories and tags come from the same verified Hub data as the website. The displayed count is actual qualified/visible content, never a hard-coded 43 when candidates are not ready.

Regular entries use a distinctive square icon/cover, readable title, one concise purpose line and a trailing native action. Grouping, dividers and spacing establish hierarchy; avoid nested card stacks or small type dominated by internal metadata. Add source attribution inside details, not a full repository path on every row.

Skill actions: `获取 / Get`, `下载中 / Downloading`, `已添加 / Added`, `启用 / Enable`, `更新 / Update`, or `暂不可用 / Unavailable` as supported by actual state. Download progress comes from real byte/item progress, not a timer. An already-added row can open details; a disabled skill is not silently enabled by browsing.

The App resolves signed publisher review plus the user's effective grants. Already granted store permissions permit direct install/enable/use with no repeated item confirmation. Only missing/revoked/new grants open the existing combined permission flow. The normal page does not explain approval token internals.

MCP actions use `连接 / Connect`, `连接中 / Connecting`, `已连接 / Connected`, or `重新连接 / Reconnect`, never `Get`. Native tool availability and endpoint health govern state; merely saving configuration is not proof of a successful connection. Account authorization remains with the existing connector flow.

## Skill detail

Push inside the feature's existing navigation stack, retaining back gesture, selection and list scroll position. The header contains the real icon, title, concise purpose, original author/Floe adaptation attribution and one primary native action. Standard native toolbar overflow holds secondary management actions.

The body contains:

1. Preview gallery or a single coherent illustrative cover; distinguish real qualified output from `效果示意 / Illustration`.
2. `它能帮你做什么 / What it helps with`: concrete outputs and limits, not generic capability claims.
3. `试着这样说 / Try asking`: a representative task, copy action and an existing task-composer handoff if supported. Copying an example does not auto-launch a new conversation or navigation.
4. `要求与权限 / Requirements & permissions`: concise readiness/permission status. Internal runtime architecture, hashes and diagnostics live behind explicit details.
5. `关于 / About`, `版本记录 / Version history`, upstream source and license attribution.
6. A small related-skill section based on actual catalog tags, without fabricated popularity.

Do not show a disconnected `Get` action for a candidate lacking a qualified package. Candidate progress, missing dependencies and unavailable current environment are distinguishable. Retain the user's task when an install finishes; show a concise result instead of forcing navigation.

## MCP detail and creation entry

Reuse the existing MCP component's account, endpoint and tool information. Details lead with what the integration does, required access, connection state and the relevant action. Technical endpoint/header fields are in the editor/details, not repeated on discovery tiles.

The A3 wizard is a focused task-owned flow: choose the resolved project/environment, describe the service, generate a project, show real build/test progress, inspect the result and save through the same MCP connection manager. Preserve generated source and failure evidence on errors. Navigation away does not orphan its job; Stop remains reachable. Tests include initialize, tools/list and an explicitly safe tool call, never automatically exercising arbitrary generated destructive operations.

## Responsive and native behavior

- Regular iPad: keep sidebar. Main content has two editorial covers and two-column compact directory rows. Detail can use a main preview/content column and a narrow About/requirements rail when space actually fits.
- Narrow iPad multitasking: collapse the local content to one column using available feature width; do not modify the App's outer split model. Category row can scroll or become a native scope/menu without truncating labels.
- iPhone: use the existing compact navigation, single-column rows, one editorial cover at a time with a manual pager if necessary, and a pushed full-width detail. Never autoplay a cover carousel. Existing swipe-back and safe-area behavior remain intact.
- Use system text styles and semantic colors, Dynamic Type, VoiceOver labels, clear focus, keyboard search and minimum 44-point controls. At accessibility sizes, trailing actions move below text when required rather than clipping titles.
- Native bars/materials can use supported system appearances. Do not add custom glass panels, a new global tab bar, hover-only actions, emoji icon systems or website navigation.
- Respect Reduce Motion; artwork never animates continuously during browsing. Lazy-load offscreen artwork and retain stable item identity during catalog refresh.

## Acceptance with the native owner

Source/preview work is separate from acceptance. The iOS main owner runs the final App on the one canonical shared iPad Simulator under its lock, preserving data and other owners. Verify discovery, MCP entry, category/search, detail/back, already-installed/disabled state, real download and permission-delta behavior. Verify dark/light and large Dynamic Type on the same device; compact layout can be checked through supported width changes without creating an extra Simulator. Physical acceptance is only claimed from actual observations.

This design handoff does not authorize this thread to edit App source, run its own competing App build, or publish a release.
