#!/usr/bin/env python3
# Floe first-party (MPL-2.0). Workflow derivation from anthropics/skills@dbd4588
# algorithmic-art (Apache-2.0; see references/PROVENANCE.md). This script and
# assets/floegart.js implement ONE numeric contract; scripts/prng_parity.js proves
# cross-runtime agreement (guest: python3 + node; host dev-smoke: same).
"""generate_art.py — seeded, reproducible generative-art bundle for the algorithmic-art skill.

Runs in the task's resolved Linux guest via exec.shell (python3 stdlib only).
Given (seed, algo, width, height, parameter overrides) it deterministically emits:

  <prefix>.html           self-contained interactive artifact (inline floegart.js
                           core + viewer UI; seed navigation, parameter sliders,
                           palette picker, regenerate/reset/download-PNG; an
                           explicit About & licenses disclosure for the inlined
                           MPL-2.0 code and the Apache-2.0 upstream derivation —
                           artwork, viewer code and font-free chrome are labeled
                           separately; NO CDN, NO external fonts, NO network)
  <prefix>.svg            static render of the same deterministic primitive list
  <prefix>.primitives.json  canonical primitive document (the artwork source)
  <prefix>.params.json    resolved parameters + sha256 digest + provenance

Modes: --digest prints only the canonical digest (must equal
prng_parity.js on the same inputs); --check-only validates without writing.

Exit codes: 0 ok, 2 invalid input, 3 output guard, 4 missing package resource.
"""
import argparse
import hashlib
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MIN_DIM, MAX_DIM = 100, 4096
MAX_SEED = 4294967295
M32 = 0xFFFFFFFF

PALETTES = [
    ["#0e1a26", "#1c3f5a", "#8fb8d8", "#d97757", "#f6f3ec"],
    ["#141413", "#788c5d", "#b0aea5", "#e8e6dc", "#faf9f5"],
    ["#1a1026", "#4b2e83", "#c17fb8", "#f2c5b0", "#fdf6ee"],
    ["#03171f", "#124f5b", "#5ab8a8", "#d8ecdd", "#e8b15a"],
]

ALGOS = {
    "flowfield": {
        "label": "Flow field — particles drifting through a seeded noise lattice",
        "params": [
            ["particles", 40, 520, 1],
            ["steps", 24, 240, 1],
            ["stepLen", 2, 26, 1],
            ["fieldScale", 0.004, 0.05, 0.001],
            ["lineWidth", 0.5, 5, 0.1],
            ["twist", 0.5, 4.5, 0.05],
            ["palette", 0, 3, 1],
        ],
    },
    "orbitwash": {
        "label": "Orbit wash — concentric seeded arc bursts",
        "params": [
            ["rings", 8, 60, 1],
            ["arcs", 6, 46, 1],
            ["spread", 0.2, 3.1, 0.01],
            ["jitter", 0, 40, 1],
            ["lineWidth", 0.6, 6, 0.1],
            ["palette", 0, 3, 1],
        ],
    },
}

def die(code, msg):
    sys.stderr.write("generate_art: %s\n" % msg)
    sys.exit(code)

def im32(a, b):
    return (a * b) & M32

def jsround(x):
    """JS Math.round for x >= 0: floor(x + 0.5)."""
    return math.floor(x + 0.5)

def jsround_neg(x):
    """JS Math.round full definition (half up toward +inf)."""
    return math.floor(x + 0.5)

class Rng(object):
    def __init__(self, seed):
        self.a = seed & M32

    def next(self):
        self.a = (self.a + 0x6D2B79F5) & M32
        t = im32(self.a ^ (self.a >> 15), self.a | 1)
        t = (t ^ ((t + im32(t ^ (t >> 7), t | 61)) & M32)) & M32
        return ((t ^ (t >> 14)) & M32) / 4294967296.0

def hash2(x, y, seed):
    h = (im32(x & M32, 374761393) + im32(y & M32, 668265263) + im32(seed & M32, 69052909)) & M32
    h = im32(h ^ (h >> 13), 1274126177)
    h ^= h >> 16
    return (h & M32) / 4294967296.0

def value_noise(x, y, seed):
    xi, yi = math.floor(x), math.floor(y)
    xf, yf = x - xi, y - yi
    sx = xf * xf * (3 - 2 * xf)
    sy = yf * yf * (3 - 2 * yf)
    n00 = hash2(xi, yi, seed)
    n10 = hash2(xi + 1, yi, seed)
    n01 = hash2(xi, yi + 1, seed)
    n11 = hash2(xi + 1, yi + 1, seed)
    a = n00 + (n10 - n00) * sx
    b = n01 + (n11 - n01) * sx
    return a + (b - a) * sy

def resolve_params(algo, seed, overrides):
    rng = Rng((seed ^ 0x9E3779B9) & M32)
    spec = ALGOS[algo]["params"]
    out = {}
    for name, lo, hi, step in spec:
        v = lo + rng.next() * (hi - lo)
        out[name] = jsround(v / step) * step
    if overrides:
        spec_map = dict((p[0], p) for p in spec)
        for k in sorted(overrides):  # JS for..in order == insertion; sorted keeps python stable
            if k in spec_map:
                _, lo, hi, step = spec_map[k]
                val = min(hi, max(lo, float(overrides[k])))
                out[k] = jsround(val / step) * step
    return out

def build_ops(algo, seed, width, height, params):
    rng = Rng(seed)
    pi = jsround_neg(params["palette"]) if "palette" in params else (seed % len(PALETTES))
    pal = PALETTES[pi % len(PALETTES)]
    ops = [{"t": "bg", "c": pal[0]}]
    if algo == "flowfield":
        for _ in range(int(params["particles"])):
            px = rng.next() * width
            py = rng.next() * height
            pts = [px, py]
            for _k in range(int(params["steps"])):
                n = value_noise(px * params["fieldScale"], py * params["fieldScale"], seed)
                sl = (n - 0.5) * params["twist"]
                inv = params["stepLen"] / math.sqrt(1.0 + sl * sl)
                px += inv
                py += sl * inv
                if px < 0 or py < 0 or px > width or py > height:
                    break
                pts.append(px)
                pts.append(py)
            if len(pts) >= 4:
                ops.append({"t": "poly", "pts": pts,
                            "c": pal[1 + int(rng.next() * (len(pal) - 2)) % (len(pal) - 2)],
                            "w": params["lineWidth"]})
    elif algo == "orbitwash":
        ccx, ccy = width / 2.0, height / 2.0
        maxr = min(width, height) * 0.46
        rings = int(params["rings"])
        for i in range(rings):
            frac = (i + 1) / float(rings)
            r = maxr * frac + (rng.next() * 2 - 1) * params["jitter"]
            if r < 1:
                r = 1
            count = max(3, jsround_neg(params["arcs"] * (1 - frac * 0.55)))
            base = rng.next() * math.pi * 2
            for k in range(count):
                a0 = base + (k / float(count)) * math.pi * 2
                sweep = (math.pi * 2 / count) * (0.25 + rng.next() * params["spread"] * 0.35)
                ops.append({"t": "arc", "cx": ccx, "cy": ccy, "r": r, "a0": a0, "a1": a0 + sweep,
                            "c": pal[1 + int(rng.next() * (len(pal) - 2)) % (len(pal) - 2)],
                            "w": params["lineWidth"] * (1 - frac * 0.4)})
    return {"algo": algo, "seed": seed & M32, "canvas": [width, height], "palette": pal, "ops": ops}

def r4(v):
    return "%.4f" % (math.floor(v * 10000 + 0.5) / 10000.0)

def canonical_json(doc):
    parts = ['{"algo":' + json.dumps(doc["algo"])]
    parts.append('"canvas":[%s,%s]' % (r4(doc["canvas"][0]), r4(doc["canvas"][1])))
    parts.append('"ops":[')
    body = []
    for o in doc["ops"]:
        if o["t"] == "bg":
            body.append('{"c":%s,"t":"bg"}' % json.dumps(o["c"]))
        elif o["t"] == "poly":
            pts = ",".join(r4(p) for p in o["pts"])
            body.append('{"c":%s,"pts":[%s],"t":"poly","w":%s}' % (json.dumps(o["c"]), pts, r4(o["w"])))
        else:
            body.append('{"a0":%s,"a1":%s,"c":%s,"cx":%s,"cy":%s,"r":%s,"t":"arc","w":%s}'
                        % (r4(o["a0"]), r4(o["a1"]), json.dumps(o["c"]), r4(o["cx"]), r4(o["cy"]),
                           r4(o["r"]), r4(o["w"])))
    parts.append(",".join(body))
    parts.append('],"palette":[%s],"seed":%d}' % (",".join(json.dumps(c) for c in doc["palette"]), doc["seed"]))
    # JS parts.join(",") emits a leading comma right after "ops":[ — mirrored exactly.
    return ",".join(parts)

def svg_render(doc):
    w, h = doc["canvas"][0], doc["canvas"][1]
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (w, h, w, h)]
    out.append('<rect width="%d" height="%d" fill="%s"/>' % (w, h, doc["palette"][0]))
    out.append('<g fill="none" stroke-linecap="round">')
    for o in doc["ops"]:
        if o["t"] == "poly":
            pts = " ".join("%.3f,%.3f" % (o["pts"][k], o["pts"][k + 1]) for k in range(0, len(o["pts"]), 2))
            out.append('<polyline points="%s" stroke="%s" stroke-width="%.3f"/>' % (pts, o["c"], max(0.2, o["w"])))
        elif o["t"] == "arc":
            x0 = o["cx"] + o["r"] * math.cos(o["a0"])
            y0 = o["cy"] + o["r"] * math.sin(o["a0"])
            x1 = o["cx"] + o["r"] * math.cos(o["a1"])
            y1 = o["cy"] + o["r"] * math.sin(o["a1"])
            large = 1 if (o["a1"] - o["a0"]) > math.pi else 0
            out.append('<path d="M %.3f %.3f A %.3f %.3f 0 %d 1 %.3f %.3f" stroke="%s" stroke-width="%.3f"/>'
                       % (x0, y0, o["r"], o["r"], large, x1, y1, o["c"], max(0.2, o["w"])))
    out.append("</g></svg>")
    return "".join(out)

def read_asset(name):
    path = os.path.join(ROOT, "assets", name)
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        die(4, "package resource missing: assets/%s" % name)

def build_html(title, algo, seed, width, height, params, digest, core_sha, ui_sha):
    core = read_asset("floegart.js")
    ui = read_asset("viewer-ui.js")
    shell = read_asset("shell-template.html").decode("utf-8")
    state = json.dumps({"algo": algo, "seed": seed, "width": width, "height": height,
                        "params": params}, separators=(",", ":")).replace("</", "\\u003c")
    notices = json.dumps({
        "schemaVersion": 1,
        "generator": "algorithmic-art/generate_art.py",
        "codeLicense": {"spdx": "MPL-2.0", "holders": "Floe Skill Hub authors",
                        "fullText": "https://www.mozilla.org/en-US/MPL/2.0/ and the LICENSE at the "
                                    "floe-skill-hub repository root (inert text; zero network use)"},
        "upstream": {"derivation": "anthropics/skills@dbd4588f9e1033efb41dad4bef2f7947c8993d44 "
                                   "skills/algorithmic-art viewer contract",
                     "spdx": "Apache-2.0",
                     "note": "structure only; branding + p5.js/Google-Fonts CDN removed; "
                             "no upstream code inlined"},
        "artwork": "Generated composition is the author's output; the generator asserts no "
                   "license over user content. Download PNG exports artwork only.",
        "provenance": {"algo": algo, "seed": seed, "canvas": [width, height],
                       "digest": digest, "coreSha256": core_sha, "uiSha256": ui_sha},
    }, sort_keys=True, ensure_ascii=False).replace("</", "\\u003c")
    html = (shell.replace("{{TITLE}}", title)
                  .replace("{{STATE_JSON}}", state)
                  .replace("@NOTICE_JSON@", notices)
                  .replace("{{CORE_JS}}", core.decode("utf-8"))
                  .replace("{{UI_JS}}", ui.decode("utf-8")))
    return html.encode("utf-8")

def atomic_write(outdir, name, data, overwrite):
    path = os.path.join(outdir, name)
    if os.path.exists(path) and not overwrite:
        die(3, "refusing to overwrite existing %s (pass --overwrite)" % path)
    tmp = path + ".tmp-%05d" % (os.getpid() & 0xFFFF)
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    return path

def main():
    ap = argparse.ArgumentParser(prog="generate_art")
    ap.add_argument("--seed", type=int, default=None,
                    help="unsigned 32-bit seed (required for everything except --list-algos)")
    ap.add_argument("--algo", default="flowfield", choices=sorted(ALGOS))
    ap.add_argument("--width", type=int, default=1000)
    ap.add_argument("--height", type=int, default=1000)
    ap.add_argument("--overrides", default=None, help='JSON object, e.g. {"particles":120}')
    ap.add_argument("--outdir", default="art-out")
    ap.add_argument("--prefix", default="artwork")
    ap.add_argument("--title", default=None)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--digest", action="store_true", help="print canonical digest only")
    ap.add_argument("--prng-stream", action="store_true",
                    help="print 8 mulberry32 values for --seed (parity with prng_parity.js --streams)")
    ap.add_argument("--check-only", action="store_true", help="validate + report, write nothing")
    ap.add_argument("--list-algos", action="store_true")
    args = ap.parse_args()

    if args.list_algos:
        for name in sorted(ALGOS):
            sys.stdout.write("%s — %s\n" % (name, ALGOS[name]["label"]))
        return
    if args.seed is None:
        die(2, "--seed is required (integer 0..%d) unless --list-algos is used" % MAX_SEED)
    if args.prng_stream:
        if not (0 <= args.seed <= MAX_SEED):
            die(2, "--seed must be an integer 0..%d" % MAX_SEED)
        rng = Rng(args.seed)
        sys.stdout.write("\n".join("%.17f" % rng.next() for _ in range(8)) + "\n")
        return
    if not (0 <= args.seed <= MAX_SEED):
        die(2, "--seed must be an integer 0..%d (unsigned 32-bit)" % MAX_SEED)
    if not (MIN_DIM <= args.width <= MAX_DIM and MIN_DIM <= args.height <= MAX_DIM):
        die(2, "--width/--height must be %d..%d px" % (MIN_DIM, MAX_DIM))
    overrides = None
    if args.overrides:
        try:
            overrides = json.loads(args.overrides)
        except ValueError:
            die(2, "--overrides must be a valid JSON object")
        if not isinstance(overrides, dict):
            die(2, "--overrides must be a JSON object of parameter names to numbers")
        for k, v in overrides.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                die(2, "override %r must be a number" % k)
    if args.prefix in ("", ".", "..") or "/" in args.prefix:
        die(2, "--prefix must be a single safe path segment")

    params = resolve_params(args.algo, args.seed, overrides)
    doc = build_ops(args.algo, args.seed, args.width, args.height, params)
    canon = canonical_json(doc)
    digest = hashlib.sha256(canon.encode("utf-8")).hexdigest()

    if args.digest:
        sys.stdout.write(digest + "\n")
        return
    report = {"algo": args.algo, "seed": args.seed, "canvas": [args.width, args.height],
              "params": params, "opsCount": len(doc["ops"]), "digest": digest}
    if args.check_only:
        sys.stdout.write(json.dumps(report, sort_keys=True, indent=1) + "\n")
        return

    core_sha = hashlib.sha256(read_asset("floegart.js")).hexdigest()
    ui_sha = hashlib.sha256(read_asset("viewer-ui.js")).hexdigest()
    title = args.title or ("Generative study — seed %d" % args.seed)
    svg = svg_render(doc).encode("utf-8")
    html = build_html(title, args.algo, args.seed, args.width, args.height, params,
                      digest, core_sha, ui_sha)
    prim = (json.dumps({"canonicalDigestSha256": digest, "doc": doc,
                        "note": "coordinates are full precision; the digest rounds to 4 decimals "
                                "to absorb last-ulp libm differences between engines"},
                       sort_keys=True, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    provenance = {
        "generator": {"tool": "algorithmic-art/generate_art.py", "core": "floegart.js",
                      "coreSha256": core_sha, "uiSha256": ui_sha, "packageVersion": "1.1.0"},
        "upstream": "anthropics/skills@dbd4588f9e1033efb41dad4bef2f7947c8993d44 skills/algorithmic-art "
                    "(workflow derivation only; this artifact runs no p5.js and loads no CDN)",
        "inputs": {"overrides": overrides},
        "output": report,
    }
    prov = (json.dumps(provenance, sort_keys=True, indent=1, ensure_ascii=False) + "\n").encode("utf-8")

    if not os.path.isdir(args.outdir):
        try:
            os.makedirs(args.outdir)
        except OSError as e:
            die(2, "cannot create outdir: %s" % e)
    written = [
        atomic_write(args.outdir, args.prefix + ".html", html, args.overwrite),
        atomic_write(args.outdir, args.prefix + ".svg", svg, args.overwrite),
        atomic_write(args.outdir, args.prefix + ".primitives.json", prim, args.overwrite),
        atomic_write(args.outdir, args.prefix + ".params.json", prov, args.overwrite),
    ]
    out = dict(report)
    out["written"] = written
    sys.stdout.write(json.dumps(out, sort_keys=True) + "\n")

if __name__ == "__main__":
    main()
