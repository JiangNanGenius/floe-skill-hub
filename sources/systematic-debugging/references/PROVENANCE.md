# Provenance — systematic-debugging

- Upstream repository: https://github.com/obra/superpowers
- Pinned commit: `2ce8aa15d05bd57213e6f746f953aafb7ded7a8b` (tree verified at fetch; see the hub docs/UPSTREAM-PINS.json)
- Upstream path: `obra_superpowers/skills/systematic-debugging`
- License: MIT License (root LICENSE at the pinned commit), Copyright (c) 2025 Jesse Vincent — full text preserved at references/licenses/UPSTREAM-LICENSE.txt (copied byte-identical from the pinned checkout)
- Subtree-only fetch into task scratch on 2026-10-26; no full-repo vendoring.
- Kept upstream content: SKILL.md methodology body (with the adaptations below) plus reference/asset files copied verbatim unless listed as edited.
- Adaptations: frontmatter normalized; companion-skill references rebound to hub ids; technique docs moved under references/ with links fixed; author-side test fixtures excluded (audited); the original find-polluter.sh bytes are now preserved as a fenced reference in find-polluter-example.md, with a supported investigation procedure and explicit limits (the original suppresses test failures/accepts empty or skipped runs); root-cause-tracing.md no longer advertises it as a usable packaged script; the TypeScript waiting sample is explicitly project-specific
- Execution status: guide-only package; host static validation only. Nothing executed against a guest; no verification claimed.

- Coordinator reference review (2026-10-26): original shell reference SHA256 `dd7b8f13c4cc2a24b33ff87b18da9248f3e1c80a085c3316224f69ff0fa5c43c` remains verbatim in the new Markdown example. No script was executed, no runtime entrypoint added, and no failing assertion relaxed.

## File inventory (sha256, this checkout; PROVENANCE.md self-hash intentionally omitted)
- `SKILL.md` sha256 `2653842c2bdf6f27ef90b5cf531becb0cebe4a8956979d035cb7a788ed01be15`
- `floe.json` sha256 `4bfeb3df6715b7ef97d099d748f2daaaf89b028ff70db14f0cf7fa67e72a1e74`
- `references/condition-based-waiting-example.ts` sha256 `40ae5ebe497fdf310200e43fe986552546d0a22837c0d39e855db1cfd33eb88e`
- `references/condition-based-waiting.md` sha256 `3d601c321cc1118a9b7162f89273402db908b224cb47c1f07a50a10421caee11`
- `references/defense-in-depth.md` sha256 `1e175fb86fc357e58c6aebf5441e481e1b7868b4380c0456b63a17eefbd18ba7`
- `references/find-polluter-example.md` sha256 `4464cb2ecf3ad2d671e32906b08e858738ef00bc33fe074ef6f8277d39a3b080`
- `references/licenses/LICENSE-NOTE.md` sha256 `4db5f818e01fcd598854f5fe4a117f6a43c23af21f8d3e1ddda8335efbcd2f36`
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `a37e0e9697144819e1d965176ac4ae5bc3fa02d11e7812036bbcadf6dafe2400`
- `references/root-cause-tracing.md` sha256 `8fb33dc48faff782b5cad09832f230e94d835fdbf5562a31768e880c32b4275d`
