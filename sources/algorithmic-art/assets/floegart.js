/* Floe first-party (MPL-2.0). Workflow derivation documented in
 * references/PROVENANCE.md (upstream: anthropics/skills@dbd4588 algorithmic-art,
 * Apache-2.0; this file replaces the upstream p5.js CDN binding with an
 * offline, seed-deterministic Canvas 2D core).
 *
 * floegart.js — deterministic generative-art core + Canvas renderer + viewer UI.
 * Runs in any browser (App WKWebView preview) and in Node (verification).
 * The Python mirror (scripts/generate_art.py) implements the identical numeric
 * contract; scripts/prng_parity.js and generate_art.py --digest must produce
 * equal canonical digests for equal (seed, algo, width, height, paramOverrides).
 *
 * Numeric contract (shared by both languages, exact or tolerance-stated):
 *  - mulberry32: uint32 state, division by 2^32 (exact in IEEE double).
 *  - valueNoise: uint32 integer hash lattice (exact), smoothstep (same op order).
 *  - trig/angles: engine libm may differ in last ulp; canonical digests round
 *    every coordinate to 4 decimals, which absorbs it (<< 0.1 um at poster scale).
 */
(function (root, factory) {
  if (typeof module !== "undefined" && module.exports) { module.exports = factory(); }
  else { root.FloeArt = factory(); }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  var M32 = 0xFFFFFFFF;
  function imul32(a, b) { return Math.imul(a >>> 0, b >>> 0) >>> 0; }

  function mulberry32(seed) {
    var a = seed >>> 0;
    return function () {
      a = (a + 0x6D2B79F5) >>> 0;
      var t = Math.imul(a ^ (a >>> 15), a | 1) >>> 0;
      t = (t ^ (t + Math.imul(t ^ (t >>> 7), t | 61))) >>> 0;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  /* integer lattice hash → [0,1) */
  function hash2(x, y, seed) {
    var h = imul32(x >>> 0, 374761393) + imul32(y >>> 0, 668265263) + imul32(seed >>> 0, 69052909);
    h = h >>> 0;
    h = imul32(h ^ (h >>> 13), 1274126177);
    h ^= h >>> 16;
    return (h >>> 0) / 4294967296;
  }
  function valueNoise(x, y, seed) {
    var xi = Math.floor(x), yi = Math.floor(y);
    var xf = x - xi, yf = y - yi;
    var sx = xf * xf * (3 - 2 * xf), sy = yf * yf * (3 - 2 * yf);
    var n00 = hash2(xi, yi, seed), n10 = hash2(xi + 1, yi, seed);
    var n01 = hash2(xi, yi + 1, seed), n11 = hash2(xi + 1, yi + 1, seed);
    var a = n00 + (n10 - n00) * sx, b = n01 + (n11 - n01) * sx;
    return a + (b - a) * sy;
  }

  var PALETTES = [
    ["#0e1a26", "#1c3f5a", "#8fb8d8", "#d97757", "#f6f3ec"],
    ["#141413", "#788c5d", "#b0aea5", "#e8e6dc", "#faf9f5"],
    ["#1a1026", "#4b2e83", "#c17fb8", "#f2c5b0", "#fdf6ee"],
    ["#03171f", "#124f5b", "#5ab8a8", "#d8ecdd", "#e8b15a"]
  ];

  /* parameter specs: [name, min, max, step]; defaults are seed-resolved */
  var ALGOS = {
    flowfield: {
      label: "Flow field — particles drifting through a seeded noise lattice",
      params: [
        ["particles", 40, 520, 1],
        ["steps", 24, 240, 1],
        ["stepLen", 2, 26, 1],
        ["fieldScale", 0.004, 0.05, 0.001],
        ["lineWidth", 0.5, 5, 0.1],
        ["twist", 0.5, 4.5, 0.05],
        ["palette", 0, 3, 1]
      ]
    },
    orbitwash: {
      label: "Orbit wash — concentric seeded arc bursts",
      params: [
        ["rings", 8, 60, 1],
        ["arcs", 6, 46, 1],
        ["spread", 0.2, 3.1, 0.01],
        ["jitter", 0, 40, 1],
        ["lineWidth", 0.6, 6, 0.1],
        ["palette", 0, 3, 1]
      ]
    }
  };

  function resolveParams(algo, seed, overrides) {
    var rng = mulberry32((seed ^ 0x9E3779B9) >>> 0);
    var spec = ALGOS[algo].params, out = {};
    for (var i = 0; i < spec.length; i++) {
      var p = spec[i];
      var v = p[1] + rng() * (p[2] - p[1]);
      v = Math.round(v / p[3]) * p[3];
      out[p[0]] = v;
    }
    if (overrides) {
      for (var k in overrides) {
        for (var j = 0; j < spec.length; j++) {
          if (spec[j][0] === k) {
            var q = spec[j][3];
            out[k] = Math.round(Math.min(spec[j][2], Math.max(spec[j][1], overrides[k])) / q) * q;
          }
        }
      }
    }
    return out;
  }

  /* deterministic primitive emission (the artwork, language-neutral) */
  function buildOps(algo, seed, width, height, params) {
    var rng = mulberry32(seed >>> 0);
    var pi = Math.round(params.palette !== undefined ? params.palette : (seed % PALETTES.length));
    var pal = PALETTES[((pi % PALETTES.length) + PALETTES.length) % PALETTES.length];
    var ops = [];
    var i, k;
    if (algo === "flowfield") {
      ops.push({ t: "bg", c: pal[0] });
      for (i = 0; i < params.particles; i++) {
        var px = rng() * width, py = rng() * height;
        var pts = [px, py];
        for (k = 0; k < params.steps; k++) {
          var n = valueNoise(px * params.fieldScale, py * params.fieldScale, seed);
          /* slope field: only + - * / sqrt — IEEE-correctly-rounded in every
             engine, so trajectories are bit-identical across V8/JSC/CPython
             (trig-free by design; angle-based fields amplify last-ulp libm
             differences chaotically and cannot be made portable) */
          var sl = (n - 0.5) * params.twist;
          var inv = params.stepLen / Math.sqrt(1 + sl * sl);
          px += inv;
          py += sl * inv;
          if (px < 0 || py < 0 || px > width || py > height) break;
          pts = pts.concat([px, py]);
        }
        if (pts.length >= 4) {
          ops.push({ t: "poly", pts: pts, c: pal[1 + (Math.floor(rng() * (pal.length - 2))) % (pal.length - 2)], w: params.lineWidth });
        }
      }
    } else if (algo === "orbitwash") {
      ops.push({ t: "bg", c: pal[0] });
      var ccx = width / 2, ccy = height / 2;
      var maxR = Math.min(width, height) * 0.46;
      for (i = 0; i < params.rings; i++) {
        var frac = (i + 1) / params.rings;
        var r = maxR * frac + (rng() * 2 - 1) * params.jitter;
        if (r < 1) r = 1;
        var count = Math.max(3, Math.round(params.arcs * (1 - frac * 0.55)));
        var base = rng() * Math.PI * 2;
        for (k = 0; k < count; k++) {
          var a0 = base + (k / count) * Math.PI * 2;
          var sweep = (Math.PI * 2 / count) * (0.25 + rng() * params.spread * 0.35);
          ops.push({ t: "arc", cx: ccx, cy: ccy, r: r, a0: a0, a1: a0 + sweep,
                     c: pal[1 + (Math.floor(rng() * (pal.length - 2))) % (pal.length - 2)],
                     w: params.lineWidth * (1 - frac * 0.4) });
        }
      }
    }
    return { algo: algo, seed: seed >>> 0, canvas: [width, height], palette: pal, ops: ops };
  }

  /* canonical digest input: 4-decimal rounded serialization */
  function r4(v) { return (Math.round(v * 10000) / 10000).toFixed(4); }
  function canonicalJSON(doc) {
    var parts = [];
    parts.push('{"algo":' + JSON.stringify(doc.algo));
    parts.push('"canvas":[' + r4(doc.canvas[0]) + "," + r4(doc.canvas[1]) + "]");
    parts.push('"ops":[');
    var body = [];
    for (var i = 0; i < doc.ops.length; i++) {
      var o = doc.ops[i];
      if (o.t === "bg") body.push('{"c":' + JSON.stringify(o.c) + ',"t":"bg"}');
      else if (o.t === "poly") {
        var pts = [];
        for (var k = 0; k < o.pts.length; k++) pts.push(r4(o.pts[k]));
        body.push('{"c":' + JSON.stringify(o.c) + ',"pts":[' + pts.join(",") + '],"t":"poly","w":' + r4(o.w) + "}");
      } else {
        body.push('{"a0":' + r4(o.a0) + ',"a1":' + r4(o.a1) + ',"c":' + JSON.stringify(o.c) +
                  ',"cx":' + r4(o.cx) + ',"cy":' + r4(o.cy) + ',"r":' + r4(o.r) + ',"t":"arc","w":' + r4(o.w) + "}");
      }
    }
    parts.push(body.join(","));
    parts.push('],"palette":[' + JSON.stringify(doc.palette).slice(1, -1) + '],"seed":' + doc.seed + "}");
    return parts.join(",");
  }

  /* Canvas 2D renderer (browser).
   * 1.1.0 render-lifecycle change (HYPOTHESIS for the Art37 native 5-pixel
   * initial-vs-restored difference, not a proven fix): the shipped element is
   * <canvas> WITHOUT size attributes, so the FIRST render grew a fresh 300x150
   * backing store (a reallocation), while every later render (next/prev restore)
   * assigned the SAME 1200x1200 values and reused the existing backing store.
   * The Art37 draw-state probe proved both renders emit identical inputs, ops
   * and Canvas2D transcripts, localizing the divergence below the API — an
   * asymmetric raster lifecycle is the remaining candidate. This sequence forces
   * EVERY render (including the first) through one identical 0 -> size
   * reallocation before replaying the ops, so initial and restored outputs share
   * the same allocation/clear path. Emitted drawing calls, coordinates, styles
   * and digests are byte-identical to 1.0.0 (draw-preserving); the strict
   * restored == initial pixel assert is unchanged and remains the verdict. */
  function renderToCanvas(ctx, doc, width, height) {
    ctx.canvas.width = 0;
    ctx.canvas.height = 0;
    ctx.canvas.width = width;
    ctx.canvas.height = height;
    ctx.fillStyle = doc.palette[0];
    ctx.fillRect(0, 0, width, height);
    ctx.lineCap = "round";
    for (var i = 0; i < doc.ops.length; i++) {
      var o = doc.ops[i];
      if (o.t === "bg") continue;
      ctx.strokeStyle = o.c;
      ctx.lineWidth = Math.max(0.2, o.w);
      ctx.beginPath();
      if (o.t === "poly") {
        ctx.moveTo(o.pts[0], o.pts[1]);
        for (var k = 2; k < o.pts.length; k += 2) ctx.lineTo(o.pts[k], o.pts[k + 1]);
      } else {
        ctx.arc(o.cx, o.cy, o.r, o.a0, o.a1, false);
      }
      ctx.stroke();
    }
  }

  return {
    VERSION: "1.1.0",
    PALETTES: PALETTES,
    ALGOS: ALGOS,
    mulberry32: mulberry32,
    hash2: hash2,
    valueNoise: valueNoise,
    resolveParams: resolveParams,
    buildOps: buildOps,
    canonicalJSON: canonicalJSON,
    r4: r4,
    renderToCanvas: renderToCanvas
  };
});
