"""SBDS キャリアWebhook HTTP API — Cloud Run エントリポイント (Ver 1.0)
ヤマト運輸・佐川急便 Webhook受信 / 管理API
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

from .carrier_webhook import CarrierWebhookProcessor


class CarrierHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the Carrier Webhook Cloud Run service."""

    _processor: CarrierWebhookProcessor = CarrierWebhookProcessor()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send_json(self, code: int, data: dict | list) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        length = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(length) if length > 0 else b''

    def log_message(self, fmt, *args):  # suppress default stderr logging
        pass

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == '/health':
            self._send_json(200, {
                'status': 'ok',
                'module': 'carrier',
                'version': '1.0',
            })

        elif path == '/api/v1/admin/deliveries':
            carrier = query.get('carrier', [None])[0]
            date_from = query.get('date_from', [None])[0]
            date_to = query.get('date_to', [None])[0]
            try:
                records = self._processor.get_records(
                    carrier=carrier,
                    date_from=date_from,
                    date_to=date_to,
                )
                self._send_json(200, [r.to_dict() for r in records])
            except ValueError as exc:
                self._send_json(400, {'error': str(exc)})

        else:
            self._send_json(404, {'error': 'Not Found', 'path': self.path})

    def do_POST(self) -> None:
        path = self.path

        if path == '/api/v1/webhook/yamato':
            body = self._read_body()
            signature = self.headers.get('X-Yamato-Signature', '')
            try:
                record = self._processor.process_yamato(body, signature)
                self._send_json(200, record.to_dict())
            except ValueError as exc:
                msg = str(exc)
                if 'signature' in msg.lower():
                    self._send_json(401, {'error': 'Invalid signature'})
                else:
                    self._send_json(400, {'error': msg})
            except (json.JSONDecodeError, KeyError, UnicodeDecodeError) as exc:
                self._send_json(400, {'error': f'JSON parse error: {exc}'})

        elif path == '/api/v1/webhook/sagawa':
            body = self._read_body()
            signature = self.headers.get('X-Sagawa-Signature', '')
            try:
                record = self._processor.process_sagawa(body, signature)
                self._send_json(200, record.to_dict())
            except ValueError as exc:
                msg = str(exc)
                if 'signature' in msg.lower():
                    self._send_json(401, {'error': 'Invalid signature'})
                else:
                    self._send_json(400, {'error': msg})
            except (json.JSONDecodeError, KeyError, UnicodeDecodeError) as exc:
                self._send_json(400, {'error': f'JSON parse error: {exc}'})

        else:
            self._send_json(404, {'error': 'Not Found', 'path': self.path})


def run_server(port: int = 8084) -> None:
    """Start the Carrier Webhook HTTP server on the given port."""
    server_address = ('0.0.0.0', port)  # nosec B104 — Cloud Run requires 0.0.0.0 binding
    httpd = HTTPServer(server_address, CarrierHandler)
    print(f'CARRIER API listening on port {port}')
    httpd.serve_forever()


if __name__ == '__main__':
    run_server()
