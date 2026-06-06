"""SURPLUS SHIFT HTTP API — Cloud Run エントリポイント (Ver 1.0)
Gate D制約: AIは提案生成まで。最終送信は人間担当者が承認後に手動実行。
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from .negotiation_api import NegotiationManager

# モジュールレベルシングルトン（インメモリMVP）
_manager = NegotiationManager()


class SurplusHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the SURPLUS SHIFT Cloud Run service."""

    # ── 内部ヘルパー ──────────────────────

    def _send_json(self, code: int, data: dict | list) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, code: int, html_str: str) -> None:
        body = html_str.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length)
        return json.loads(raw.decode('utf-8')) if raw else {}

    def log_message(self, fmt, *args):  # suppress default stderr logging
        pass

    # ── ルーティング ──────────────────────

    def do_GET(self) -> None:
        path = self.path.split('?')[0]
        query = self.path[len(path):]  # e.g. '?status=negotiating'
        parts = [p for p in path.split('/') if p]
        # parts examples:
        #   ['health']
        #   ['api', 'v1', 'surplus', 'negotiations']
        #   ['api', 'v1', 'surplus', 'negotiations', '{id}']
        #   ['api', 'v1', 'surplus', 'negotiations', '{id}', 'export-pdf']

        if path == '/health':
            self._send_json(200, {'status': 'ok', 'module': 'surplus', 'version': '1.0'})
            return

        if parts[:4] == ['api', 'v1', 'surplus', 'negotiations']:
            if len(parts) == 4:
                # GET /api/v1/surplus/negotiations[?status=...]
                status_filter = None
                if query.startswith('?status='):
                    status_filter = query[len('?status='):]
                entries = _manager.list_all(status=status_filter)
                self._send_json(200, [e.to_dict() for e in entries])
                return

            if len(parts) == 5:
                # GET /api/v1/surplus/negotiations/{id}
                negotiation_id = parts[4]
                try:
                    entry = _manager.get(negotiation_id)
                    self._send_json(200, entry.to_dict())
                except KeyError:
                    self._send_json(404, {'error': 'Not Found', 'negotiation_id': negotiation_id})
                return

            if len(parts) == 6 and parts[5] == 'export-pdf':
                # GET /api/v1/surplus/negotiations/{id}/export-pdf
                negotiation_id = parts[4]
                try:
                    html_report = _manager.export_pdf_html(negotiation_id)
                    self._send_html(200, html_report)
                except KeyError:
                    self._send_json(404, {'error': 'Not Found', 'negotiation_id': negotiation_id})
                return

        self._send_json(404, {'error': 'Not Found', 'path': self.path})

    def do_POST(self) -> None:
        path = self.path.split('?')[0]
        parts = [p for p in path.split('/') if p]

        if parts[:4] == ['api', 'v1', 'surplus', 'negotiations'] and len(parts) == 4:
            # POST /api/v1/surplus/negotiations
            body = self._read_json_body()
            try:
                entry = _manager.create(
                    counterparty=body.get('counterparty', ''),
                    product_name=body.get('product_name', ''),
                    category=body.get('category', ''),
                    proposed_price_jpy=int(body.get('proposed_price_jpy', 0)),
                    quantity=int(body.get('quantity', 0)),
                    notes=body.get('notes', ''),
                )
                self._send_json(201, entry.to_dict())
            except (ValueError, TypeError) as exc:
                self._send_json(400, {'error': str(exc)})
            return

        if parts[:4] == ['api', 'v1', 'surplus', 'to-smartlife'] and len(parts) == 4:
            # POST /api/v1/surplus/to-smartlife
            body = self._read_json_body()
            negotiation_id = body.get('negotiation_id', '')
            try:
                product = _manager.to_smartlife(negotiation_id)
                self._send_json(200, product.to_dict())
            except KeyError:
                self._send_json(404, {'error': 'Not Found', 'negotiation_id': negotiation_id})
            except ValueError as exc:
                self._send_json(400, {'error': str(exc)})
            return

        self._send_json(404, {'error': 'Not Found', 'path': self.path})

    def do_PUT(self) -> None:
        path = self.path.split('?')[0]
        parts = [p for p in path.split('/') if p]

        if parts[:4] == ['api', 'v1', 'surplus', 'negotiations'] and len(parts) == 5:
            # PUT /api/v1/surplus/negotiations/{id}
            negotiation_id = parts[4]
            body = self._read_json_body()
            try:
                entry = _manager.update_status(
                    negotiation_id=negotiation_id,
                    status=body.get('status', ''),
                    notes=body.get('notes', ''),
                )
                self._send_json(200, entry.to_dict())
            except KeyError:
                self._send_json(404, {'error': 'Not Found', 'negotiation_id': negotiation_id})
            except ValueError as exc:
                self._send_json(400, {'error': str(exc)})
            return

        self._send_json(404, {'error': 'Not Found', 'path': self.path})


def run_server(port: int = 8085) -> None:
    """Start the SURPLUS SHIFT HTTP server on the given port."""
    server_address = ('0.0.0.0', port)  # nosec B104 — Cloud Run requires 0.0.0.0 binding
    httpd = HTTPServer(server_address, SurplusHandler)
    print(f'SURPLUS SHIFT API listening on port {port}')
    httpd.serve_forever()


if __name__ == '__main__':
    run_server()
