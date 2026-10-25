---
name: floe-email-drafting
description: Draft emails in the user's voice from authorized samples and hand them to the existing mail flow; this skill never sends by itself.
---


# Floe Email Drafting

Draft emails in the user's own voice and hand them to the app's existing mail surface — this skill never sends anything by itself.

## Voice sources (in priority order)
1. The user's explicit instruction for this email ("brief, firm, no blame").
2. Authorized writing samples: sent-mail text the user opened for this task (`mail.read` only when the task grants it), Notes documents, or files in the workspace.
3. A captured voice profile (`voice-profile.md`) the user maintains: register, typical openings/closings, vocabulary to keep, phrases to never use.

Read before writing. If none are available, ask for one line of tone direction — do not default to corporate neutral.

## Draft workflow
1. Brief: purpose, recipient, relationship, must-include facts, desired outcome. Missing facts come from the user or authorized files — never invented; unverified specifics stay as [bracketed placeholders] with a warning line.
2. Draft: subject line(s) (2–3 options, ≤ 8 words), greeting per relationship, body that states the ask early, closes per voice profile. Keep thread history out of the new body unless the user asked to quote it.
3. Review copy: plain-text and (if requested) an HTML-flavored variant; attachments referenced as workspace file paths the app can attach, not embedded guesses.
4. Handoff: place the final draft where the user's mail flow picks it up (app compose surface / clipboard / `draft-*.md` in the workspace). Sending, recipients, scheduling and account choices belong to the user and the existing approval path.

## Red lines
- No auto-send, no recipient inference from address books, no calendar invitations created silently.
- Mailbox content is user data: it informs drafts, never leaves the task as "context" to external tools.
- Financial, legal or HR-sensitive drafts: mark the draft for explicit human read-before-send, whatever the tone.
- Signature blocks, reply-all behavior and threading stay with the mail client — the draft is body + subject.

## Verification before handoff
- Every proper noun, number, date and file reference matches the brief's sources (the consistency ledger habit).
- Length: the email the recipient can finish on a phone screen.
- Tone: read it aloud; if it sounds like no sample you have of this user, say so and offer two alternatives.
