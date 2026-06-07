# src/common/gdpr_api.py
# NiceEze GDPR権利API (port 8090)
# stdlib only

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

from .gdpr_manager import GDPRManager

PORT = 8090

_manager = GDPRManager()


def _json_response(handler: BaseHTTPRequestHandler, status: int, data: dict) -> None:
    body = json.dumps(data, ensure_ascii=False).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get('Content-Length', 0))
    if length == 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


class GDPRRequestHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt: str, *args) -> None:  # type: ignore[override]
        pass  # suppress default logging

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == '/health':
            _json_response(self, 200, {'status': 'ok', 'port': PORT})

        elif path == '/api/v1/privacy/my-data':
            user_id = qs.get('user_id', [None])[0]
            if not user_id:
                _json_response(self, 400, {'error': 'user_id is required'})
                return
            try:
                data = _manager.get_my_data(user_id)
                _json_response(self, 200, data)
            except ValueError as exc:
                _json_response(self, 404, {'error': str(exc)})

        elif path == '/api/v1/privacy/my-data/export':
            user_id = qs.get('user_id', [None])[0]
            if not user_id:
                _json_response(self, 400, {'error': 'user_id is required'})
                return
            try:
                csv_str = _manager.export_my_data_csv(user_id)
                body = csv_str.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/csv; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except ValueError as exc:
                _json_response(self, 404, {'error': str(exc)})
            except PermissionError as exc:
                _json_response(self, 403, {'error': str(exc)})

        else:
            _json_response(self, 404, {'error': 'Not Found'})

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/v1/privacy/my-data':
            body = _read_body(self)
            user_id = body.get('user_id')
            if not user_id:
                _json_response(self, 400, {'error': 'user_id is required'})
                return
            try:
                result = _manager.delete_my_data(user_id)
                _json_response(self, 200, result)
            except ValueError as exc:
                _json_response(self, 404, {'error': str(exc)})
        else:
            _json_response(self, 404, {'error': 'Not Found'})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        body = _read_body(self)

        if path == '/api/v1/residents/register':
            user_id = body.get('user_id')
            country_code = body.get('country_code')
            data_records = body.get('data_records')

            if not user_id or not country_code:
                _json_response(self, 400, {'error': 'user_id and country_code are required'})
                return

            profile = _manager.register_user(user_id, country_code, data_records)
            resp = {
                'user_id': profile.user_id,
                'country_code': profile.country_code,
                'gdpr_applicable': profile.gdpr_applicable,
                'created_at': profile.created_at,
            }
            if profile.gdpr_applicable:
                resp['gdpr_notification'] = True
            _json_response(self, 201, resp)

        elif path == '/api/v1/privacy/processing-restriction':
            user_id = body.get('user_id')
            restriction_type = body.get('restriction_type')
            reason = body.get('reason', '')

            if not user_id or not restriction_type:
                _json_response(self, 400, {'error': 'user_id and restriction_type are required'})
                return

            try:
                req = _manager.request_processing_restriction(user_id, restriction_type, reason)
                _json_response(self, 201, {
                    'request_id': req.request_id,
                    'user_id': req.user_id,
                    'restriction_type': req.restriction_type,
                    'reason': req.reason,
                    'status': req.status,
                    'created_at': req.created_at,
                })
            except ValueError as exc:
                _json_response(self, 400, {'error': str(exc)})

        else:
            _json_response(self, 404, {'error': 'Not Found'})


def create_server(port: int = PORT, manager: GDPRManager = None) -> HTTPServer:
    """テスト・本番共用のサーバーファクトリ"""
    global _manager
    if manager is not None:
        _manager = manager
    return HTTPServer(('', port), GDPRRequestHandler)


def main() -> None:
    server = create_server()
    print(f"GDPR API listening on port {PORT}")
    server.serve_forever()


if __name__ == '__main__':
    main()
