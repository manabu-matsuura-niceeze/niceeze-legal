"""手ぶら旅行システム 統合API (Ver 1.0)
SBDS部門 MVP

# GET  /health                  → {"status":"ok","module":"travel"}
# POST /qr/issue                → body:{traveler_ref,departure_hub,arrival_hub,baggage_count}
# POST /qr/scan                 → body:{token}
# GET  /qr/{qr_id}              → TravelQR.to_dict()
# POST /webhook/dispatch        → body:{qr_id, baggage_details:{}}
# POST /webhook/arrival         → body:{qr_id}
# POST /support/ask             → body:{language,category,message,qr_id?}
# GET  /support/health          → AISupportCenter.health_check()
# GET  /pdf/{qr_id}?lang=ja     → QR印刷用HTML返却（Content-Type: text/html）
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

from .travel_qr import TravelQRManager
from .hub_webhook import HubWebhookClient
from .ai_support import AISupportCenter
from .travel_pdf import TravelPDFGenerator, TravelPDFDocument

# シングルトン（プロセス内共有）
_qr_manager = TravelQRManager()
_webhook_client = HubWebhookClient()
_ai_support = AISupportCenter()
_pdf_generator = TravelPDFGenerator()


class TravelHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the Travel Cloud Run service."""

    def _send_json(self, code: int, data: dict | list) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, code: int, content: str) -> None:
        body = content.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length)
        return json.loads(raw.decode('utf-8')) if raw else {}

    def log_message(self, fmt, *args):  # suppress default stderr logging
        pass

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == '/health':
            self._send_json(200, {'status': 'ok', 'module': 'travel', 'version': '1.0'})

        elif path == '/support/health':
            self._send_json(200, _ai_support.health_check())

        elif path.startswith('/qr/') and len(path) > 4:
            qr_id = path[4:]
            # Find by qr_id in manager
            found = None
            for qr in _qr_manager._store.values():
                if qr.qr_id == qr_id:
                    found = qr
                    break
            if found is None:
                self._send_json(404, {'error': 'QR not found', 'qr_id': qr_id})
            else:
                self._send_json(200, found.to_dict())

        elif path.startswith('/pdf/') and len(path) > 5:
            qr_id = path[5:]
            lang = query.get('lang', ['ja'])[0]
            found = None
            for qr in _qr_manager._store.values():
                if qr.qr_id == qr_id:
                    found = qr
                    break
            if found is None:
                self._send_json(404, {'error': 'QR not found', 'qr_id': qr_id})
            else:
                html_content = _pdf_generator.generate_for_qr(found, language=lang)
                self._send_html(200, html_content)

        else:
            self._send_json(404, {'error': 'Not Found', 'path': self.path})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/qr/issue':
            body = self._read_json_body()
            try:
                qr = _qr_manager.issue(
                    traveler_ref=body.get('traveler_ref', ''),
                    departure_hub=body.get('departure_hub', ''),
                    arrival_hub=body.get('arrival_hub', ''),
                    baggage_count=int(body.get('baggage_count', 1)),
                )
                self._send_json(201, qr.to_dict())
            except Exception as exc:
                self._send_json(400, {'error': str(exc)})

        elif path == '/qr/scan':
            body = self._read_json_body()
            token = body.get('token', '')
            try:
                qr = _qr_manager.scan(token)
                self._send_json(200, qr.to_dict())
            except ValueError as exc:
                self._send_json(400, {'error': str(exc)})

        elif path == '/webhook/dispatch':
            body = self._read_json_body()
            qr_id = body.get('qr_id', '')
            baggage_details = body.get('baggage_details', {})
            found = None
            for qr in _qr_manager._store.values():
                if qr.qr_id == qr_id:
                    found = qr
                    break
            if found is None:
                self._send_json(404, {'error': 'QR not found', 'qr_id': qr_id})
                return
            result = _webhook_client.notify_dispatch(found, baggage_details)
            self._send_json(200, result.to_dict())

        elif path == '/webhook/arrival':
            body = self._read_json_body()
            qr_id = body.get('qr_id', '')
            found = None
            for qr in _qr_manager._store.values():
                if qr.qr_id == qr_id:
                    found = qr
                    break
            if found is None:
                self._send_json(404, {'error': 'QR not found', 'qr_id': qr_id})
                return
            result = _webhook_client.notify_arrival(found)
            self._send_json(200, result.to_dict())

        elif path == '/support/ask':
            body = self._read_json_body()
            request = _ai_support.create_request(
                language=body.get('language', 'ja'),
                category=body.get('category', 'general'),
                message=body.get('message', ''),
                qr_id=body.get('qr_id', ''),
            )
            response = _ai_support.respond(request)
            self._send_json(200, response.to_dict())

        else:
            self._send_json(404, {'error': 'Not Found', 'path': self.path})


def run_server(port: int = 8083) -> None:
    """Start the Travel API HTTP server on the given port."""
    server_address = ('0.0.0.0', port)  # nosec B104 — Cloud Run requires 0.0.0.0 binding
    httpd = HTTPServer(server_address, TravelHandler)
    print(f'TRAVEL API listening on port {port}')
    httpd.serve_forever()


if __name__ == '__main__':
    run_server()
