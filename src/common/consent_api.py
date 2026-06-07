# src/common/consent_api.py
# NiceEze 同意管理API (port 8089)
# stdlib only: http.server + json + urllib.parse

from __future__ import annotations

import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

from .consent_manager import ConsentManager

PORT = 8089

# シングルトン ConsentManager インスタンス
_consent_manager = ConsentManager()


def _json_response(handler: BaseHTTPRequestHandler, status: int, data: object) -> None:
    body = json.dumps(data, ensure_ascii=False).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _record_to_dict(record) -> dict:
    return {
        'record_id': record.record_id,
        'user_id': record.user_id,
        'service': record.service,
        'consent_type': record.consent_type,
        'granted': record.granted,
        'granted_at': record.granted_at,
        'revoked_at': record.revoked_at,
        'ip_address': record.ip_address,
        'user_agent': record.user_agent,
        'ai_learning_excluded': record.ai_learning_excluded,
    }


class ConsentAPIHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):  # pylint: disable=arguments-differ
        pass  # suppress default logging

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path == '/health':
            _json_response(self, 200, {'status': 'ok', 'service': 'consent_api', 'port': PORT})
            return

        if path == '/api/v1/consent/status':
            user_id = params.get('user_id', [None])[0]
            if not user_id:
                _json_response(self, 400, {'error': 'user_id is required'})
                return
            service = params.get('service', [None])[0]
            records = _consent_manager.get_status(user_id, service)
            _json_response(self, 200, {'records': [_record_to_dict(r) for r in records]})
            return

        if path == '/api/v1/consent/history':
            user_id = params.get('user_id', [None])[0]
            if not user_id:
                _json_response(self, 400, {'error': 'user_id is required'})
                return
            records = _consent_manager.get_history(user_id)
            _json_response(self, 200, {'records': [_record_to_dict(r) for r in records]})
            return

        _json_response(self, 404, {'error': 'Not Found'})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get('Content-Length', 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b'{}'
        try:
            body = json.loads(body_bytes.decode('utf-8'))
        except json.JSONDecodeError:
            _json_response(self, 400, {'error': 'Invalid JSON'})
            return

        if path == '/api/v1/consent/grant':
            user_id = body.get('user_id')
            service = body.get('service')
            consent_type = body.get('consent_type')
            if not user_id or not service or not consent_type:
                _json_response(self, 400, {'error': 'user_id, service, consent_type are required'})
                return
            try:
                record = _consent_manager.grant(
                    user_id=user_id,
                    service=service,
                    consent_type=consent_type,
                    ip_address=body.get('ip_address', ''),
                    user_agent=body.get('user_agent', ''),
                )
            except ValueError as exc:
                _json_response(self, 400, {'error': str(exc)})
                return
            _json_response(self, 200, {'record': _record_to_dict(record)})
            return

        if path == '/api/v1/consent/revoke':
            user_id = body.get('user_id')
            service = body.get('service')
            consent_type = body.get('consent_type')
            if not user_id or not service or not consent_type:
                _json_response(self, 400, {'error': 'user_id, service, consent_type are required'})
                return
            try:
                record = _consent_manager.revoke(
                    user_id=user_id,
                    service=service,
                    consent_type=consent_type,
                )
            except ValueError as exc:
                _json_response(self, 400, {'error': str(exc)})
                return
            _json_response(self, 200, {'record': _record_to_dict(record)})
            return

        _json_response(self, 404, {'error': 'Not Found'})


def run_server(port: int = PORT, host: str = '127.0.0.1') -> None:
    server = HTTPServer((host, port), ConsentAPIHandler)  # nosec B104
    server.serve_forever()


if __name__ == '__main__':
    run_server()
