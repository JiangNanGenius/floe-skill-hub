/* Floe first-party (MPL-2.0) — algorithmic-art viewer UI glue.
 * Consumes the FloeArt core (assets/floegart.js); no network, no CDN, no
 * external fonts, no localStorage. Seed navigation follows the upstream
 * workflow (seed → prev/next/random/jump, parameters, actions) with the
 * Anthropic template branding replaced by a neutral local chrome.
 */
(function () {
  "use strict";
  var F = window.FloeArt;
  var state = JSON.parse(document.getElementById("initial-state").textContent);
  var overrides = {};
  var canvas = document.getElementById("art-canvas");
  /* PNG readback is a first-class viewer contract. Pin every lazily allocated
   * backing buffer to WebKit's unaccelerated path: dimension resets recreate
   * storage, but do not make accelerated stroke rasterization bit-stable
   * across independent draws. Geometry, styles and draw calls stay unchanged. */
  var ctx = canvas.getContext("2d", { willReadFrequently: true });

  function el(id) { return document.getElementById(id); }

  function currentParams() {
    var base = F.resolveParams(state.algo, state.seed);
    var keys = Object.keys(overrides);
    for (var i = 0; i < keys.length; i++) {
      var k = keys[i];
      var spec = specFor(k);
      if (spec) base[k] = Math.round(Math.min(spec[2], Math.max(spec[1], overrides[k])) / spec[3]) * spec[3];
    }
    return base;
  }
  function specFor(name) {
    var p = F.ALGOS[state.algo].params;
    for (var i = 0; i < p.length; i++) if (p[i][0] === name) return p[i];
    return null;
  }

  function render() {
    var params = currentParams();
    var doc = F.buildOps(state.algo, state.seed, state.width, state.height, params);
    F.renderToCanvas(ctx, doc, state.width, state.height);
    el("seed-value").textContent = String(state.seed);
    el("status-ops").textContent = "ops " + doc.ops.length + " — " + state.width + "x" + state.height + "px";
    var sw = el("palette-swatches");
    sw.innerHTML = "";
    for (var i = 0; i < doc.palette.length; i++) {
      var d = document.createElement("span");
      d.className = "swatch";
      d.style.background = doc.palette[i];
      d.title = doc.palette[i];
      sw.appendChild(d);
    }
    return doc;
  }

  function buildSliders() {
    var holder = el("params");
    holder.innerHTML = "";
    var params = currentParams();
    var spec = F.ALGOS[state.algo].params;
    for (var i = 0; i < spec.length; i++) {
      var p = spec[i];
      var div = document.createElement("div");
      div.className = "control-group";
      var label = document.createElement("label");
      label.textContent = p[0];
      var input = document.createElement("input");
      input.type = "range";
      input.min = p[1]; input.max = p[2]; input.step = p[3];
      input.value = params[p[0]];
      var val = document.createElement("span");
      val.className = "value-display";
      val.textContent = String(params[p[0]]);
      /* 1.1.0 fix (was a latent closure bug in 1.0.0): `input` and `val` are the
       * function-scoped loop variables, so the 1.0.0 listener read the LAST slider
       * created for EVERY slider's input event (host-proven in the art-native-state
       * lane: dispatch on `particles` wrote the palette value). Bind each listener
       * to its own elements. Drawing and digests are unchanged: the restore flow
       * dispatches no slider events, so overrides stayed {} there either way. */
      (function (name, inputEl, valEl) {
        inputEl.addEventListener("input", function () {
          overrides[name] = Number(inputEl.value);
          valEl.textContent = inputEl.value;
          render();
        });
      })(p[0], input, val);
      div.appendChild(label); div.appendChild(input); div.appendChild(val);
      holder.appendChild(div);
    }
  }

  function fullRedraw() { buildSliders(); render(); }

  function setSeed(s) {
    state.seed = ((Math.floor(s) % 4294967296) + 4294967296) % 4294967296;
    overrides = {};
    fullRedraw();
  }

  el("seed-prev").addEventListener("click", function () { setSeed(state.seed - 1); });
  el("seed-next").addEventListener("click", function () { setSeed(state.seed + 1); });
  el("seed-random").addEventListener("click", function () {
    var buf = new Uint32Array(1);
    (window.crypto || window.msCrypto).getRandomValues(buf);
    setSeed(buf[0]);
  });
  el("seed-jump-btn").addEventListener("click", function () {
    var v = Number(el("seed-jump").value);
    if (isFinite(v)) setSeed(v);
  });
  el("btn-regenerate").addEventListener("click", function () { render(); });
  el("btn-reset").addEventListener("click", function () { overrides = {}; fullRedraw(); });
  /* Staged export delivery (1.1.0). A data-URL anchor click only becomes a real
   * file in engines that save click-initiated downloads; WKWebView-based viewers
   * deliver nothing unless the app installs the floeExport message bridge. This
   * helper (a) keeps the exact bytes staged on window.__artExport for an
   * automation read-back, (b) delivers them through the bridge when present, and
   * (c) reports the delivery truth in a plain span (never a redraw — the canvas
   * is not touched after the click). */
  function exportStatusLine() {
    var line = el("export-delivery");
    if (!line) {
      line = document.createElement("span");
      line.id = "export-delivery";
      el("btn-download").parentNode.appendChild(line);
    }
    return line;
  }
  function stageExport(name, dataURL, width, height) {
    var line = exportStatusLine();
    var b64 = dataURL.slice(dataURL.indexOf(",") + 1);
    var bin = atob(b64);
    var bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    var hashing = (window.crypto && window.crypto.subtle && window.crypto.subtle.digest)
      ? window.crypto.subtle.digest("SHA-256", bytes).then(function (buf) {
          var v = new Uint8Array(buf), s = "", j;
          for (j = 0; j < v.length; j++) { if (v[j] < 16) s += "0"; s += v[j].toString(16); }
          return s;
        }, function () { return null; })
      : Promise.resolve(null);
    hashing.then(function (sha) {
      window.__artExport = {
        state: "staged", name: name, width: width, height: height,
        bytes: bytes.length, sha256: sha,
        dataURL: bytes.length <= 33554432 ? dataURL : null,
        stagedAt: Date.now()
      };
      var bridge = window.webkit && window.webkit.messageHandlers
        && window.webkit.messageHandlers.floeExport;
      if (bridge && bridge.postMessage) {
        var CH = 786432; /* base64 chars per message (multiple of 4) */
        var count = Math.ceil(b64.length / CH);
        try {
          for (var k = 0; k < count; k++) {
            bridge.postMessage({
              kind: "floe.export", v: 1, name: name, index: k, count: count,
              totalBytes: bytes.length, sha256: sha || "", encoding: "base64",
              data: b64.slice(k * CH, k * CH + CH)
            });
          }
          line.textContent = "Delivered " + bytes.length + " bytes to the app export bridge"
            + (sha ? " (sha256 " + sha.slice(0, 16) + "…)" : "")
            + " — verify the saved file before publishing it.";
        } catch (err) {
          line.textContent = "Export bridge delivery failed (" + err.name + "); "
            + bytes.length + " bytes remain staged in-page only.";
        }
        return;
      }
      line.textContent = "Rasterized " + width + "x" + height + " (" + bytes.length
        + " bytes" + (sha ? ", sha256 " + sha.slice(0, 16) + "…" : "")
        + ") and dispatched a download click; this engine does not save click downloads,"
        + " so no file was written by the page. The bytes stay staged for the app bridge.";
    });
  }
  el("btn-download").addEventListener("click", function () {
    // Exports the ACTUAL full-size canvas (canvas.width x canvas.height at 1:1),
    // artwork only — page chrome and this notice are not part of the image.
    var url = canvas.toDataURL("image/png");
    var name = "seed-" + state.seed + "-" + canvas.width + "x" + canvas.height + ".png";
    var a = document.createElement("a");
    a.download = name;
    a.href = url;
    a.click();
    stageExport(name, url, canvas.width, canvas.height);
  });

  var algos = el("algo-picker");
  Object.keys(F.ALGOS).sort().forEach(function (name) {
    var o = document.createElement("option");
    o.value = name; o.textContent = name + " — " + F.ALGOS[name].label;
    if (name === state.algo) o.selected = true;
    algos.appendChild(o);
  });
  algos.addEventListener("change", function () {
    state.algo = algos.value; overrides = {}; fullRedraw();
  });

  fullRedraw();
})();
