"""tool_server.py — expose the SAME Python tools over HTTP so the n8n low-code
workflow can call them as tool nodes.

This is the "hybrid" architecture in the benchmark: n8n owns the orchestration
(trigger, AI Agent node, logging), but the business tools are the exact Python
functions the full-code agent uses — one implementation, two orchestrators. It
makes the low-code vs full-code comparison fair (same tools, same catalog) and
demonstrates integrating custom code into a low-code platform, which is a core
task in the Würth role.

Stdlib only — no framework. Run:

    python -m agentic_lab.tool_server           # serves on :8000
    curl -s localhost:8000/lookup_sku -d '{"description":"M8x40 hex bolts zinc"}'

Endpoints (POST, JSON body -> JSON result): /parse_email /lookup_sku /check_stock
/draft_quote /classify_category /normalize_fields /validate_record /health

Author: Dimitres Kisimov.
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import tools

_TOOLS = {
    "parse_email": tools.parse_email,
    "lookup_sku": tools.lookup_sku,
    "check_stock": tools.check_stock,
    "draft_quote": tools.draft_quote,
    "classify_category": tools.classify_category,
    "normalize_fields": tools.normalize_fields,
    "validate_record": tools.validate_record,
}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") in ("/health", ""):
            self._send(200, {"ok": True, "tools": sorted(_TOOLS)})
        else:
            self._send(404, {"error": "GET only supports /health"})

    def do_POST(self) -> None:  # noqa: N802
        name = self.path.strip("/")
        fn = _TOOLS.get(name)
        if not fn:
            return self._send(404, {"error": f"unknown tool {name!r}", "tools": sorted(_TOOLS)})
        try:
            length = int(self.headers.get("Content-Length", 0))
            args = json.loads(self.rfile.read(length) or b"{}")
            self._send(200, {"tool": name, "result": fn(**args)})
        except Exception as exc:
            self._send(400, {"tool": name, "error": f"{type(exc).__name__}: {exc}"})

    def log_message(self, *_a) -> None:  # keep the console quiet
        pass


def serve(host: str = "0.0.0.0", port: int | None = None) -> None:
    port = port or int(os.environ.get("TOOL_SERVER_PORT", "8000"))
    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"agentic_lab tool server on http://{host}:{port}  tools={sorted(_TOOLS)}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    serve()
