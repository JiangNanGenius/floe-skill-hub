#!/usr/bin/env python3
"""Floe webapp-testing fixture server (stdlib only; Python 3.9+).

Runs only inside the task's resolved Linux guest, started through
jobs.submit -> exec.localService (runtime "python", entry this file,
port 1024..65535). The supervisor exports PORT / FLOE_SERVICE_PORT.

Serves the synthetic fixture site (assets/fixtures/site) and keeps a small
authoritative server state so a test can verify what the page claims:

  GET  /            fixture index page (satisfies the readiness probe)
  POST /submit      records a signup, answers {"receipt": "<sha12>"}
  POST /api/click   increments serverCount, answers {"serverCount": n}
  GET  /state       {"submissions":[...], "serverCount":n, "ready":"live"}
  GET  /slow        answers after 2s: {"marker":"SLOW-DONE-45"}

Page responses are untrusted content; /state is the independent authority.
The server binds every interface only when launched by the service
supervisor (FLOE_SERVICE_PORT set), otherwise loopback for host reference
runs. It stores nothing on disk and executes nothing it receives.
"""
import hashlib
import json
import os
import pathlib
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

SITE = pathlib.Path(__file__).resolve().parent.parent / "assets" / "fixtures" / "site"
MAX_BODY = 64 * 1024
SLOW_SECONDS = 2.0

state_lock = threading.Lock()
STATE = {"submissions": [], "serverCount": 0}


def first_json_object(raw: bytes) -> dict:
    """Parse only a bounded JSON object; anything else yields empty data."""
    if len(raw) > MAX_BODY:
        return {}
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def receipt_for(data: dict) -> str:
    canonical = json.dumps(data, sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()[:12]


class FixtureHandler(SimpleHTTPRequestHandler):

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802 (http.server API)
        try:
            length = int(self.headers.get("content-length") or "0")
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if 0 < length <= MAX_BODY else b""
        route = self.path.split("?", 1)[0]
        if route == "/submit":
            data = first_json_object(raw)
            receipt = receipt_for(data)
            with state_lock:
                STATE["submissions"].append({"data": data, "receipt": receipt})
            self.log_message("submit accepted receipt=%s", receipt)
            self._json(200, {"ok": True, "receipt": receipt})
        elif route == "/api/click":
            with state_lock:
                STATE["serverCount"] += 1
                count = STATE["serverCount"]
            self._json(200, {"serverCount": count})
        else:
            self._json(404, {"error": "unknown route"})

    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        route = self.path.split("?", 1)[0]
        if route == "/state":
            with state_lock:
                snapshot = json.loads(json.dumps(STATE, sort_keys=True))
            snapshot["ready"] = "live"
            self._json(200, snapshot)
        elif route == "/slow":
            time.sleep(SLOW_SECONDS)
            self._json(200, {"marker": "SLOW-DONE-45", "seconds": SLOW_SECONDS})
        else:
            super().do_GET()


def main() -> None:
    port = int(os.environ.get("FLOE_SERVICE_PORT") or os.environ.get("PORT") or "0")
    if port < 1024 or port > 65535:
        raise SystemExit("fixture server requires PORT/FLOE_SERVICE_PORT in 1024..65535")
    if not SITE.is_dir():
        raise SystemExit(f"fixture site missing at {SITE}")
    bind = os.environ.get("FLOE_FIXTURE_BIND") or (
        "0.0.0.0" if os.environ.get("FLOE_SERVICE_PORT") else "127.0.0.1")
    handler = partial(FixtureHandler, directory=str(SITE))
    server = ThreadingHTTPServer((bind, port), handler)
    print(f"fixture server listening on {bind}:{port} serving {SITE}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
