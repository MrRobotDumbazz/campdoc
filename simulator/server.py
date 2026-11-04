#!/usr/bin/env python3
"""HTTP wrapper for the /contracts/simulation.api.yaml contract (simulator zone, S-1 acting).

POST /simulate  {"campaign_id", "seed", "changes", ...} -> contract output
GET  /health    -> {"status": "ok", ...}
Run: python3 simulator/server.py [--port 8100] [--data-root data/datasets]
Stdlib only; determinism is inherited from simulate.run_simulation.
"""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from simulate import DATA_ROOT, LIMITATION_NOTE, run_simulation


def make_handler(data_root: Path):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, payload: dict | str):
            body = (payload if isinstance(payload, str)
                    else json.dumps(payload, ensure_ascii=False))
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type",
                             "text/markdown" if code == 200 and isinstance(payload, str)
                             else "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):  # noqa: N802
            if self.path == "/health":
                self._send(200, {"status": "ok",
                                 "service": "campaign-doctor-simulator",
                                 "contract": "simulation.api.yaml v1-draft",
                                 "limitation": LIMITATION_NOTE})
            else:
                self._send(404, {"error": "not_found"})

        def do_POST(self):  # noqa: N802
            if self.path != "/simulate":
                self._send(404, {"error": "not_found"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            try:
                inp = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError as e:
                self._send(400, {"error": "bad_json", "detail": str(e)})
                return
            if not isinstance(inp, dict) or not inp.get("campaign_id"):
                self._send(400, {"error": "bad_request",
                                 "detail": "campaign_id is required"})
                return
            try:
                out = run_simulation(inp, data_root=data_root)
            except FileNotFoundError as e:
                self._send(404, {"error": "unknown_campaign", "detail": str(e)})
                return
            except (KeyError, ValueError, TypeError) as e:
                self._send(400, {"error": "bad_request", "detail": str(e)})
                return
            self._send(200, out)

        def log_message(self, fmt, *args):  # keep console output quiet
            pass

    return Handler


def serve(port: int, data_root: Path) -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(data_root))
    print(f"simulator: listening on 127.0.0.1:{port} "
          f"(data={data_root}, contract simulation.api.yaml v1)")
    httpd.serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8100)
    ap.add_argument("--data-root", default=str(DATA_ROOT))
    args = ap.parse_args()
    serve(args.port, Path(args.data_root))
