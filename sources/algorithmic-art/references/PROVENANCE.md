# Provenance — algorithmic-art

- Upstream repository: https://github.com/anthropics/skills
- Pinned commit: `dbd4588f9e1033efb41dad4bef2f7947c8993d44`
  (subtree `skills/algorithmic-art`, git tree `4aef6bcad51d058ec32b1acb9da436851863e56e`, 4 files:
  SKILL.md, LICENSE.txt, templates/viewer.html, templates/generator_template.js;
  proof recorded with the lane evidence)
- Upstream license: Apache-2.0 per-skill `LICENSE.txt`, preserved byte-identical at
  `references/licenses/UPSTREAM-LICENSE.txt` (`cmp`-verified against the pinned checkout)
- Fetch mode: sparse subtree clone into task scratch (blob-filtered); no full-repo vendoring.
- Upstream content kept: philosophy → conceptual-seed → implementation workflow, the
  fixed-vs-variable viewer contract (seed navigation prev/next/random/jump and
  Regenerate/Reset/Download PNG actions always present; parameters and algorithm variable),
  Art Blocks-style seeded-reproducibility requirement, palette-harmony and craftsmanship
  guidance, variation exploration via seed navigation.
- Adaptations:
  1. p5.js 1.7.0 from cdnjs + Poppins/Lora from Google Fonts → replaced by the bundled
     first-party offline core (`assets/floegart.js`) with a local system font stack.
     The generated artifact has zero external resource loads — every `src`/`url()`
     field is inline code or data; the only http(s) strings in the page are inert
     license-text references inside the About & licenses disclosure (nothing is
     fetched; the scan checks resource-bearing fields, not "no URL characters").
     The only "p5" text is the explanatory comment recording this replacement.
     p5.js itself is NOT redistributed (LGPL considered and rejected). The inlined
     Floe viewer code keeps its MPL-2.0 file headers and the page discloses the
     license availability; the generated artwork belongs to its author (the skill
     asserts no license over user content).
  2. Anthropic template branding (colors/fonts/gradient chrome) → neutral Floe viewer
     chrome. `assets/shell-template.html` derives the sidebar/canvas STRUCTURE from
     upstream `templates/viewer.html` (Apache-2.0 derivative, documented in
     `references/licenses/LICENSE-NOTE.md`); branding, CDN bindings and remote fonts
     removed. Upstream template files are not vendored.
  3. claude.ai artifacts platform wording → Floe surfaces: generation/verification in the
     task Linux guest via `exec.shell` (python3 + node), preview via `exec.localService`
     + `browser.navigate`, capture via `browser.screenshot`, delivery via
     `workspace.publishOutput`; explicit rule that the RISC-V guest must not download
     Playwright/Chromium and that host/Node numeric smokes never count as render proof.
  4. Cross-runtime determinism contract: the generative loops use only IEEE-exact ops
     (+ − × ÷, uint32 integer arithmetic, correctly-rounded sqrt); trigonometry is banned
     inside digest/trajectory paths (measured: 1-ulp libm differences amplify chaotically
     in particle walks — documented in `references/numeric-contract.md`). The JS core and
     `scripts/generate_art.py` implement the same contract and are checked against each
     other by `scripts/prng_parity.js` (`--digest` equality).
- Excluded upstream files (with reason):
  * `templates/viewer.html` and `templates/generator_template.js` (verbatim): their fixed
    sections are branding + p5/CDN bindings; structure was rebuilt as the derivative
    shell above; keeping the originals would re-introduce the exact bindings this
    adaptation must remove.
- First-party additions (MPL-2.0): `assets/floegart.js`, `assets/viewer-ui.js`,
  `assets/shell-template.html` (derivative, Apache-2.0 notice kept),
  `scripts/generate_art.py`, `scripts/prng_parity.js`,
  `references/numeric-contract.md`, `floe.json`.
- Verification status: source-complete; host dev-smokes executed (100-combination
  python↔node canonical-digest parity sweep incl. boundary seeds and overrides — PASS;
  PRNG stream equality — PASS; artifact byte determinism across runs — PASS; seed
  sensitivity — PASS; invalid-input classes — PASS; canvas-dispatch mock smoke labeled
  script-correctness; QuickLook host render of sample SVGs labeled host-only; HTML
  self-containment static scan). Guest execution and any on-device render/visual QA are
  PENDING (runbook in the lane evidence). Nothing here claims guest or App verification,
  and partial parity coverage is not full upstream p5.js workflow equivalence.



## 1.1.0 local change record (private candidate, job-c988e0c9de8a459d, 2026-10-27)

First-party changes only; the upstream pin (anthropics/skills@dbd4588), Apache-2.0
notices, OFL files, numeric contract, PRNG, buildOps and canonical digest paths are
untouched. The 1.0.0 published bytes stay immutable; this tree is versioned 1.1.0.

1. assets/viewer-ui.js — slider-listener closure bug fixed: 1.0.0 bound every
   slider's `input` listener to the function-scoped loop variables, so each
   slider wrote the LAST slider's override and value display (host-proven;
   adopted from the art-native-state lane proposal, with the unused `step` IIFE
   parameter dropped). Each listener now receives its own `input`/`val`
   elements. Restore flows dispatch no slider events, so 1.0.0 artwork output
   is unchanged by this fix.
2. assets/floegart.js — render lifecycle (HYPOTHESIS, not a proven fix):
   renderToCanvas now forces a fresh backing-store reallocation (width/height
   -> 0 -> declared size) before replaying ops for EVERY render including the
   first. The shipped <canvas> has no size attributes, so in 1.0.0 the initial
   render grew a fresh 300x150 store while every next/prev render re-assigned
   the same 1200x1200 values and reused the existing store — an asymmetric
   raster lifecycle, and the Art37 draw-state probe proved both renders emit
   identical inputs/ops/transcripts (divergence localized BELOW the Canvas2D
   API). Device verdict remains the unchanged strict restored==initial pixel
   assert in the App qualification test; host WebKit shows the emitted canvas
   PNG digest is identical to 1.0.0 (draw-preserving: initial
   79ff95a5…, next 382b7860…).
3. assets/viewer-ui.js — Download PNG honesty + delivery: the click still
   dispatches the data-URL anchor inside the gesture, but the page now reports
   what actually happened: exact bytes staged on window.__artExport (name,
   size, byte length, SHA-256) and, when the app installs the `floeExport`
   WKScriptMessageHandler bridge, bounded base64 chunk delivery through it.
   A status line is never presented as a delivered file (SKILL.md Export
   section restated to the same rule).
4. floe.json version 1.1.0; floegart.js VERSION "1.1.0"; generate_art.py
   packageVersion "1.1.0".

## File inventory (sha256 per file, this checkout; PROVENANCE.md self-hash intentionally omitted)

- `SKILL.md` sha256 `bc794a64b905e6f2d42c6dc12c71481871fd7716e949d95424ebbcaf3c8b2728` (6662 bytes)
- `assets/floegart.js` sha256 `80d6f365f3d4662c08a7fc9102bd2a88140f20ac83dc40916ceb5b0194191c94` (9829 bytes)
- `assets/shell-template.html` sha256 `78cb58692a53058cb1c4e3172eddaf6be7854b7933df1869cc2e19d6ce0bcdd5` (6562 bytes)
- `assets/viewer-ui.js` sha256 `72c268d399e85c236fd639e98422a6c517a5100ce34ec03c933f50b95192531c` (8376 bytes)
- `floe.json` sha256 `b7e0b98b114b52cb44184c8c7d8491a7b23666f586b7d5ef911636a1a75086f6` (220 bytes)
- `references/licenses/LICENSE-NOTE.md` sha256 `2dd4360d16a7ce888a996cbf38bec1b75932efa9f0c1ff15c409bcb9563840d3` (1961 bytes)
- `references/licenses/UPSTREAM-LICENSE.txt` sha256 `bc6b3af2f331cbc7fb0da1344efb2cbe5877a31498b4d70dbc7000f3405a1362` (11345 bytes)
- `references/numeric-contract.md` sha256 `da176a0c7822d1fc26524242c92b460f53c201494eb35f4ca5a0fb2843774786` (2711 bytes)
- `scripts/generate_art.py` sha256 `88c978da3b6367c8936d66bb17e0584b85a766a35ffb28f6b9320c001f8ff854` (16802 bytes)
- `scripts/prng_parity.js` sha256 `35d8d2e8809344d343b51723b65f14c533a4f4d29c71aaf0220f8696e4db42e9` (2507 bytes)
