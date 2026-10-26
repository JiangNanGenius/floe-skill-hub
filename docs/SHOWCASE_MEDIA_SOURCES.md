# Showcase media sources

This note is the documentary source and license record for every media file
currently referenced by `showcase/skills.json`. It is presentation data for the
unsigned candidate storefront; it implies no review, qualification, publication
or install offer. Paths below are relative to `showcase/media/`.

## Covers and gallery: the complete referenced set (5 files)

### `covers/impeccable-promo-small.png` — Impeccable entry cover

- What it is: the official Chrome-extension promo artwork of the upstream
  Impeccable project. It depicts the upstream browser extension, not Floe’s app
  UI and not any skill execution output.
- Public source: https://raw.githubusercontent.com/pbakaus/impeccable/4fc2f83e1c8710dba772bfd4523d0efab57737b6/extension/icons/promo-small.png
  (upstream git blob `aa9f5ee9d3f15067c3b4ba0b7842ddedb0e2034a`; commit is the
  pin recorded in `docs/UPSTREAM-PINS.json`).
- License: upstream `pbakaus/impeccable` is Apache-2.0 at that commit. The
  verbatim upstream LICENSE is already retained in this repository at
  `sources/impeccable/references/licenses/LICENSE`. No separate third-party
  notice at the pinned commit covers `extension/icons/` assets.
- Exact bytes: image/png, 30,235 bytes, 440×280 px,
  SHA-256 `fe18b4065238d6e59c0b106b03a246482ef01ab31665e90c53b7ede2e258c0db`.

### `gallery/impeccable-icon-128.png` — Impeccable entry gallery (identity)

- What it is: the official upstream project identity icon. A brand mark, not
  execution output.
- Public source: https://raw.githubusercontent.com/pbakaus/impeccable/4fc2f83e1c8710dba772bfd4523d0efab57737b6/extension/icons/icon-128.png
  (upstream git blob `3c4ae9d38d0b583a93290b32740572ee93ca4a44`).
- License: Apache-2.0 as above.
- Exact bytes: image/png, 1,837 bytes, 128×128 px,
  SHA-256 `1939b3a61b016a0f49f90a7b91319cbe95b339be1a46a4a44404edb7b43a3d91`.

### `covers/office-doc-zh.jpg` — Floe Office entry cover

- What it is: a real Floe Office document-editing screenshot captured on iPad
  (Chinese UI) with an example document. Floe-owned product content.
- Public source: https://www.floe-agent.com/assets/demos/office-doc-zh.jpg
  (already published on the official Floe website; the website owner, who also
  owns this content, authorized its reuse in the Skill Hub showcase).
- Permission: Floe-owned screenshot, included here with the project owner's
  permission. This note does not change the licenses of depicted software or fonts.
- Exact bytes: image/jpeg, 83,823 bytes, 1280×960 px,
  SHA-256 `4e7b5643db20d7431b18065c27dba953c0617c632512f4a4a4ee609c8acb5a7e`.

### `gallery/office-sheet-zh.jpg` — Floe Office entry gallery

- What it is: the companion Floe Office example-spreadsheet screenshot
  (Chinese UI), same capture set, same ownership and authorization as above.
- Public source: https://www.floe-agent.com/assets/demos/office-sheet-zh.jpg
- Permission: Floe-owned screenshot; owner-authorized reuse as above.
- Exact bytes: image/jpeg, 115,084 bytes, 1280×960 px,
  SHA-256 `818b77a962dabe0507fb5ddfdf4d28829e6a5ada5105804fced6df108b96e654`.

### `gallery/office-slide-zh.jpg` — Floe Office entry gallery

- What it is: the companion Floe Office example-presentation screenshot
  (Chinese UI), same capture set, same ownership and authorization as above.
- Public source: https://www.floe-agent.com/assets/demos/office-slide-zh.jpg
- Permission: Floe-owned screenshot; owner-authorized reuse as above.
- Exact bytes: image/jpeg, 76,673 bytes, 1280×960 px,
  SHA-256 `8b240c252e4fdc98b5fb52f7d59e33ce809dd6654dd72ab31af87cfb4fccfb8c`.

## Null covers for the remaining entries

The other 41 editorial entries currently have no selected cover and use
`"cover": null` with an empty gallery. Their image review can continue while
readers use compact identity/text cards. Previously generated SVG illustrations
were removed from the active references on 2026-10-26; the originals remain in
[repository history](https://github.com/JiangNanGenius/floe-skill-hub/tree/647d8a7e59c8020d297a01a8c42382bcde46fb2c/showcase/media/covers).

## Rules applied

- Every file above is an unchanged copy of its listed source. Each SHA-256
  records the exact distributed bytes.
- Editorial credits state exactly what each image is; non-illustration media
  carry truthful captions. No cover claims skill execution.
- No candidate skill was marked reviewed, qualified, published or installed by
  this change, and no new schema, kind, proxy or external image loading was
  introduced — media stays under `showcase/media/` per `showcase/CONTRACT.md`.
