# Showcase media sources

This note is the documentary source and license record for every media file
currently referenced by `showcase/skills.json`. It is presentation data for the
unsigned candidate storefront; it implies no review, qualification, publication
or install offer. Paths below are relative to `showcase/media/`.

## Covers and gallery: official and Floe-owned originals (11 files)

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

## Floe illustrations (6 files)

Original concept illustrations created for this catalog on 2026-10-26 using
AI-assisted image generation, included with the project owner’s permission.
These depict their respective uses; they are not upstream brand assets or
product screenshots. All six are unchanged 1254×1254 PNGs under `covers/`.
Their public source is this repository’s `showcase/media/covers/` directory.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `exploratory-data-analysis.png` | 1,927,366 | `79937c042f75d406010760fe402e26e9f8e60e16c58dc40eca3dab25ce90ec1e` |
| `markitdown.png` | 1,774,973 | `c94df186ab37a141e1d6bcbd03ba54986e9a4e7efb32fd441d09a2a9995955d3` |
| `floe-pdf.png` | 1,989,169 | `2d5503fe8af7a166244759d5ed3a6b08721bb2dc13aa9c47afe07e7cc9af642b` |
| `floe-network.png` | 1,749,595 | `bbf3f72ef540f58f04aad243e584955bf84e9ecdb2f604cf507ef73742b9406e` |
| `floe-video.png` | 1,805,636 | `0c1b214e1c5de96006974c213a736a67d3f20d8a3d96398ba8b95c2566271e39` |
| `floe-invoice-organizer.png` | 2,005,153 | `f0a44507947abc7aa3254871dd228b15e55c2157a4d999236a44939d8421a117` |

## Cover expansion: the remaining 35 entries (35 files, 2026-10-26)

Root independently verified the hash and size of all 35 new source assets and
visually reviewed each one in a native browser (wide crop and square gallery)
before approval. This is presentation data only: no entry gained a review,
qualification, publication or install-offer claim from these files.

### `covers/theme-factory.png` — official upstream example

- What it is: the Ocean Depths theme page from the upstream Theme Factory
  showcase PDF — an official example-output asset, not Floe artwork.
- Public source: https://raw.githubusercontent.com/anthropics/skills/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/theme-factory/theme-showcase.pdf
  (pinned commit `dbd4588f9e1033efb41dad4bef2f7947c8993d44`; source PDF SHA-256 `3e126eca9fe99088051f7cb984c97cedb31c7d9e09ce0ba5d61bd01e70a0d253`)
- License: Apache-2.0 per-skill at the pinned commit. The verbatim upstream
  license, the embedded font notices and the GPL-3.0 text for those fonts are
  retained byte-identically under `showcase/licenses/theme-factory/`.
- Exact bytes: image/png, 79,382 bytes, 990×1280 px, SHA-256 `e96edd50eaaf562852a119009643b91fd0f1b1d148d6254952b41b7806af56e9`.

### 34 original AI-assisted concept covers

Stylized-concept illustrations created for this catalog with AI-assisted image
generation, owned by Floe and included with the project owner’s permission.
Each is `kind: illustration` with the truthful credit “Floe original,
AI-assisted illustration.” The distributed file is a same-dimension native
`sips` JPEG re-encoding (quality 78) of the 1254×1254 original PNG — no crop,
no redraw, no content change. The originals (65,324,541 bytes combined) are
intentionally not vendored here; their per-file SHA-256 keys them for future
verification, together with the full generation prompt for each entry, in
[`docs/provenance/cover-expansion-20261026.json`](provenance/cover-expansion-20261026.json).

| File (`.jpg`) | Bytes | Distributed SHA-256 | Raw PNG SHA-256 |
| --- | ---: | --- | --- |
| `a11y-audit.jpg` | 222,675 | `db9bbd0a3a491234d01cdc777f859a99b5afa924944968a3f19b56402affee5b` | `53a5d1e69cfbed598d7f0e31bb58f9080bd9bddcaa5e68de65a925542327eec3` |
| `algorithmic-art.jpg` | 239,266 | `c05feebb2da1f9aa18efd925f4a92c63d8fbd3bd317be4a00d97b1775a7572cf` | `26235200764c2b486ce3ad73a29e59bbdd9d5234159528115c8f5ed04a1eb88c` |
| `canvas-design.jpg` | 212,339 | `3adf045145c641ea9a4f226c72b0c839d6a216010e95c142b6884a1329250ad7` | `19da123b2cad3a96c599ab4eafc2040c7765589c3c6975dafecbf3828012c9e4` |
| `citation-management.jpg` | 212,881 | `06421ec4d313ccd5713ebf405c67eeea1392ad1ccc4ba4d03ec6d1cf9c6bfa71` | `c74765a5e8d932d39b74daff8d2123bd19166a4b88f5263f30e8e4d4a4e86438` |
| `code-to-prd.jpg` | 179,239 | `ff41159ea494929647c07637a65db5ce4f5cce39117ace01b520eab670cc376e` | `b691d0ae528515223566155d8e5f745c7374be98f5031f37a3e76901a682245a` |
| `composition-patterns.jpg` | 201,383 | `6876322060f00dab505a095875261ffc76dd5d462b3b2a47addd4bc18e1b4ea2` | `432f4995dac3dd0719f60af834065f5499506d0bd7771d0b429fdb336fbb697b` |
| `content-production.jpg` | 183,471 | `21fd990093e93eba9e7f3822facd8a27c83f12dbb738018057b99d766f005238` | `7dd7edb8347c74178ea5834ca0b98936df74796f003620dcaabff3907ff43ded` |
| `copy-editing.jpg` | 193,849 | `4bff3bc1bf2bad625c3acb1505e454211687462048116f54e53b9a25f6b4506b` | `4806421bf5ca51031a5c5da6d6126294b54722f7251d00f8164ddb65965b7f56` |
| `copywriting.jpg` | 296,918 | `9c6c39edac30aa1d6b7b70b89934af5bc59282ed78ea4a42ff3737cde073c000` | `4666bbabfb08f5d4deb7505950130ad38b2ead1482b7104c06b2af7a114b2d98` |
| `deep-research.jpg` | 214,905 | `22c0b54972d3355d0dd7e1158450ac54bf6b5264941b9106278bac42378f7fcb` | `831cbd63cd425aa72e2af06bdb798f5baa194f0733170a576f70fdeb87c0ce8a` |
| `deepread.jpg` | 207,550 | `b855bf04e37f4f699860978ff2381c1d2333dbbc23398f1a9d3d935cc46a23fe` | `68cbee27e246ef4bdc2abd3834cc3efb3ca65cb967de576d435d01c2cbe2119c` |
| `doc-coauthoring.jpg` | 212,992 | `222de4af4f0271ed6125c7704125ff330e31800b6abccca766ffc6259d2b2187` | `6c3f747bedeed5ae14b62faf95c55a867f89e96e37bce8dac2ab3ab755065934` |
| `floe-email-drafting.jpg` | 178,357 | `5ce7d248f1fd46e33c2aa42530f720634a3dd18b42a97d186995867461ac229d` | `974d0af2836134c59802920befbfd2f1396f18b6688e0cf6bde21843fef7817a` |
| `floe-file-organizer.jpg` | 216,415 | `a5e0f254f013a22c1cbb611fc7f47f4bc267e65e4f321e8aec8f19ff02eeaa8e` | `0525a1104c3491c24ff15c7785faf93690666ef699b92119a1f06faa865828bc` |
| `internal-comms.jpg` | 167,527 | `ef6d2a680385b5625d2ff3512a96cdbd00cc541177ccc183dbdd0aa718cdf5c4` | `e3687f2528e4c8aff8b2ff049007739058bbcc355f222f8a8c8aea508384c903` |
| `literature-review.jpg` | 220,540 | `d46d1889b9b6d6ef0ede5a6359024111249ecee3127414462109c904a6eca3d7` | `959c23bd09f42b0884b55fcf9c0c97b940912ea46c344e44cc028971058e0e8f` |
| `meetings.jpg` | 208,939 | `c451c8ba711eaaf596b1d8712785f3be0d0481aa12f7db34f008d5268597527d` | `bc56686a7b9d3617fde9756f9798f884f3c0d2eb7818bdc3cbf1699b786d3089` |
| `product-discovery.jpg` | 200,578 | `9f691bd6d3dc30304b310ff98ee8ade8d5a27139efb8a240820c1012cdd49d6d` | `0f839ffaec95144258ab5bdcba4a6913246a0a875837e7ab4ab586b40d6d96a9` |
| `product-manager-toolkit.jpg` | 194,079 | `be62d02fda99b3860bc8c57967431a3fa6d5b4dc7719547e2e90e7b767f223b5` | `2d420e57884f43d0b52aa962e7793e7f3714a0ea0f4fa7890ae354fc0b61a751` |
| `react-best-practices.jpg` | 229,552 | `ffee785c85f226843d67923ebaaa301a3225e3c3a709b5873e6043f87ef44636` | `05bcdcbdd918a36413c6c3d7eb31deecfe2c0e82a3440ca4ee3fb4914f6a8bfa` |
| `requesting-code-review.jpg` | 176,442 | `a925c45cb7ab26808ef4f4a0978f47b4de1849a490d104ad8bca90cc96751a22` | `162b243e20802021c6c7832b9cb5ff15cd797792f29e461dd00159cb204c9ed5` |
| `research-summarizer.jpg` | 207,911 | `33121cfa08f9ccbed9a08c40f8741988a3aae2a45c33e246e77807a330c84616` | `0e173c2f5c565c3e00c53872a0ff309e2b13e2b2bace2ddf245906f367f677ff` |
| `scientific-critical-thinking.jpg` | 176,258 | `ca739bde123a5fd61547242c4dde9082bb9435f562f74c314c71925e3b3a212c` | `0569207bb3e659c4803390f653ed6af28f08cdb79c1c892d7ae437a4990d2406` |
| `scientific-visualization.jpg` | 216,813 | `0ce436b83b135053cdeb2bf31ca2824a83d741da83e9a2f0a04ffad20dab715f` | `2436e3e95a06139cc35b7f6230ce69b6a12e63926c1961419f957ef9a042cea4` |
| `social-content.jpg` | 209,656 | `42ff4fc40e8e683bd58df3a138d7fa2e6aa31b2230af41821b4d583212aa15bf` | `abb0a2c07599bf11d4acfa2e016887e9873b017654036b0babad39630e7c08e3` |
| `statistical-analysis.jpg` | 200,257 | `336561719a0a34d309881f3a97dbf8e59d74805af1b23dbf715b9eb22023a77d` | `66e5aaef5ad3abf513a8badc906757b263c085218703c1b1bbfe945c6eaec005` |
| `sympy.jpg` | 182,776 | `7390e329aca59aa7d3e3db972d03eae3bbeb9da57af6597d0e5cf83cb14e0b2b` | `b78ca61653b721cc2a8511df8f13b86104e7d08d4af9b7afbb7a03add51b2727` |
| `systematic-debugging.jpg` | 250,243 | `65ca1ebb5acb4736ce1e8856253535d64d8029df6ebaf80c079ecfb7e4e4535f` | `48d7ffdb4ea8ce11e5edaca4aeaba4a66dd7de3968c06eb9e0e8928d1f23f3a5` |
| `test-driven-development.jpg` | 166,925 | `3462535c0fb316e8ec9baee4cab9d539051dd7cad8561edcc93676336d3d1ccb` | `f989b5df932b7d9806b111db2c746b4ccb3d43d9a4904033baf0da1b9c8603bf` |
| `ui-design-system.jpg` | 202,082 | `2610a517c38323e7a18e1250c2be3a2e1641eb889ba191440514712d04ae41c0` | `2db0a33845634682948bc31d3c8b99467de35ec17deaa4d1b59ed94a4d15ba89` |
| `ux-researcher-designer.jpg` | 205,572 | `6e831bafd3549762f89d2f442fd78e51eb041dcba1bbff1edf17aec75026d5c6` | `3ca17efb9576c0a8432e38ed42345e9f9c6eb60be66fc4f8d20bf9c3e596d32d` |
| `web-design-guidelines.jpg` | 182,484 | `1cbc8a3cde52126ae35269be9d5bf56c64381a21248c5cf5dbda39b62dc7cc0f` | `4281d4f649330bd3094d9ff9161f02796883b1cb262908c29e319ac681b61595` |
| `webapp-testing.jpg` | 155,073 | `4089ac0c9f81756ca53e98fadd926ae1bb04f11b2802ed28a47ad80be7a9709e` | `61bf5d5376a916f8728f8b3d0b22a7be0634e4783010a10ca08c25a466e66e50` |
| `writing-guidelines.jpg` | 206,686 | `2c037a14616f7dcc4f1461973e90cd18bd16499f8b244ec144286659a639a648` | `9ea694572bc87f35446e92775910f47416177f72e0349eb7f3d638bac8343570` |

All 43 editorial entries now carry a cover; the eight previously
listed originals are unchanged. The previously generated SVG illustrations
remain retired (see the repository-history note above).

## Rules applied

- Every file above is an unchanged copy of its listed source. Each SHA-256
  records the exact distributed bytes.
- Editorial credits state exactly what each image is; non-illustration media
  carry truthful captions. No cover claims skill execution.
- No candidate skill was marked reviewed, qualified, published or installed by
  this change, and no new schema, kind, proxy or external image loading was
  introduced — media stays under `showcase/media/` per `showcase/CONTRACT.md`.
