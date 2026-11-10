# Floe adaptation notice

Taste Skill 2.5.1 by Leonxlnx, MIT. Exact upstream commit:
f6b76575f949707b4e3c37cd86cb44b0b98643e8. The complete root LICENSE is retained.
All original resources, individual image/icon metadata and credits are retained;
the software MIT license does not replace their individual licenses or trademarks.

Floe changes: scalar SKILL frontmatter and task-owned ARM64 Linux execution guidance;
remove the Claude-only automatic Stop hook; move two HTML templates into assets
and update their reads; add same-environment runtime detection; add Linux Chromium
launch flags (no-sandbox only for root inside the resolved Linux environment).
No native binary, credential, extra installer tool or native-host fallback is included.
This notice does not assert an App version floor or completed execution qualification.

The two data-library JSON files moved under assets/taste-library; their bytes are unchanged and all three actual reads were updated.
All 20 original CLI modules use an automatic process-local compatibility startup for tested Debian Node20.19.2 or newer within Node20, preserving exit status/signals and explicit feature-disable choices. Node22+ uses its existing WebSocket. No system Node is replaced.
