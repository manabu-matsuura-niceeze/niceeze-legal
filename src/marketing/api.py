"""MARKETING API — Cloud Run HTTPエントリポイント (Ver 1.0)"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from .content_generator import ContentGenerator, ContentInput
from .delivery_log import DeliveryLog


class MarketingHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the MARKETING Cloud Run service."""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send_json(self, code: int, data: dict | list) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8")) if raw else {}

    def log_message(self, fmt, *args):  # suppress default stderr logging
        pass

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(200, {
                "status": "ok",
                "module": "marketing",
                "version": "1.0",
            })
        elif self.path == "/log/summary":
            log = DeliveryLog()
            self._send_json(200, log.summary())
        else:
            self._send_json(404, {"error": "Not Found", "path": self.path})

    def do_POST(self) -> None:
        if self.path == "/generate":
            body = self._read_json_body()
            inp = ContentInput(
                topic=body.get("topic", ""),
                category=body.get("category", ""),
                product_name=body.get("product_name") or None,
                trend_score=float(body.get("trend_score", 0.5)),
                tone=body.get("tone", "professional"),
            )
            gen = ContentGenerator()
            content = gen.generate_all(inp)
            self._send_json(200, content.to_dict())

        elif self.path == "/log/add":
            body = self._read_json_body()
            log = DeliveryLog()
            record = log.add(
                content_type=body.get("content_type", "x_post"),
                topic=body.get("topic", ""),
                category=body.get("category", ""),
                char_count=int(body.get("char_count", 0)),
            )
            from dataclasses import asdict
            self._send_json(201, asdict(record))

        else:
            self._send_json(404, {"error": "Not Found", "path": self.path})


def run_server(port: int = 8081) -> None:
    """Start the MARKETING HTTP server on the given port."""
    server_address = ("0.0.0.0", port)  # nosec B104 — Cloud Run requires 0.0.0.0 binding
    httpd = HTTPServer(server_address, MarketingHandler)
    print(f"MARKETING API listening on port {port}")
    httpd.serve_forever()


if __name__ == "__main__":
    run_server()
