# Numeric determinism contract (floegart core)

Guarantee: for identical `(seed, algo, width, height, overrides)`,
`canonicalJSON` produces an identical byte string in every JavaScript engine
(V8 in Node — guest verification — and JSC in the device WKWebView preview) and
in the Python generator, hence the static SVG, the primitives JSON and the
browser-rendered canvas show the same artwork for the same seed.

## Exact-equality rules (shared op order, both languages)

- PRNG: mulberry32 on uint32 state (`(a + 0x6D2B79F5) >>> 0` / `& 0xFFFFFFFF`);
  every intermediate converted to uint32 before `^`, `|`, `>>>`; final value
  `(t ^ (t >>> 14)) >>> 0` divided by 2^32 — an exact binary fraction,
  representable identically in IEEE double everywhere.
- `Math.imul(a, b)` ≡ `(a * b) & 0xFFFFFFFF` (low 32 bits of the product;
  Python ints mask the same).
- Lattice hash (`hash2`) and value noise use only the above plus `+ - * /` and
  `Math.floor` on non-negative inputs (≡ Python `math.floor`).
- Smoothstep `x*x*(3-2*x)` and bilinear mixes are written in identical
  operation order in both languages; IEEE single-rounding makes each step
  bit-exact.
- Quantization: `Math.round(v/step)*step` in JS ≡ `math.floor(v/step + 0.5) *
  step` in Python (inputs ≥ 0; JS Math.round is floor(x+0.5)).
- Canonical serialization rounds every coordinate to 4 decimals
  (`Math.round(v*1e4)/1e4 → toFixed(4)` ≡ `floor(v*1e4+0.5)/1e4 → "%.4f"`,
  values ≥ 0). The round-trip is stable because k/10000 doubles sit ≥ 5e-5
  away from any 4-decimal rounding tie.

## Forbidden inside generative loops

`sin`, `cos`, `tan`, `pow`, `exp`, `log` and anything libm-version-dependent:
they are correctly-rounded by no one, engines differ by 1 ulp, and chaotic
loops (particle walks re-entering their own noise field) amplify a 1e-16
difference into visible 1e-3+ coordinate drift within tens of steps — measured
during this adaptation (CPython vs V8, seed 1). Angles may only be used at
draw time (SVG path emission, canvas arc), never in the digest/trajectory path.
This is why the shipped `flowfield` steers with a slope field (`sqrt` is the
one IEEE-mandated correctly-rounded function) instead of `cos/sin(ang)`.

## Verification

`python3 scripts/generate_art.py --digest ...` must equal
`node scripts/prng_parity.js ...` stdout `digest`; `--prng-stream` must equal
`--streams`. The adaptation lane ran a 100-combination sweep across both
algorithms, boundary seeds (0, 1, 4294967295), extreme aspect ratios and
parameter overrides (host, labeled host-only dev-smoke). The guest runbook
reruns the same commands under the product's resolved Linux environment before
any `guest-verified` claim.
