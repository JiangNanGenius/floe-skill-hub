# Voice and output rules — Floe guide adaptation

The upstream skill referred to shared plugin documents for voice and artifact style. Those shared documents are not part of this package. Use these rules instead.

## Voice

- Prefer writing samples the owner supplies: past proposals, sent emails or a style guide.
- If no sample exists, write plainly and concisely in neutral business English (or the user's language). Say the document is un-voiced rather than inventing a personality.
- Match the owner's existing template, headings and terminology more than a general style preference.
- Keep customer-facing text free of internal risk notes, margin analysis and pricing rationale.

## Output

- Produce Markdown in the task workspace by default.
- A self-contained HTML review copy is optional when the user wants a visual review; it must not depend on external scripts, fonts, images or trackers.
- Use the app's native document export only when it is actually available and the user asks for it. State the real format produced.
- Keep source files unchanged. Write new files; do not overwrite the owner's template.
- Never include secrets, credentials or private paths in the document or provenance.
