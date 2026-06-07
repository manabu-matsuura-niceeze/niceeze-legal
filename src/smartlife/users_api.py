"""SmartLife 利用開始フロー API — ConsentFlowProcessor を使った同意取得フロー

POST /api/v1/smartlife/users/register
PORT = 8092
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from ..common.consent_flow import ConsentFlowProcessor, RegistrationRequest
from ..common.eu_countries import is_gdpr_applicable

PORT = 8092

_processor = ConsentFlowProcessor()


class SmartlifeUsersHandler(BaseHTTPRequestHandler):
    """HTTP request handler for SmartLife Users Registration API."""

    def _send_json(self, code: int, data: dict) -> None:
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

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == '/health':
            self._send_json(200, {'status': 'ok', 'module': 'smartlife_users', 'version': '1.0'})
        else:
            self._send_json(404, {'error': 'Not Found'})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == '/api/v1/smartlife/users/register':
            self._handle_register()
        else:
            self._send_json(404, {'error': 'Not Found'})

    def _handle_register(self) -> None:
        raw = self._read_body()
        try:
            body = json.loads(raw.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            self._send_json(400, {'success': False, 'errors': ['Invalid JSON body']})
            return

        user_id = body.get('user_id', '')
        country_code = body.get('country_code', '')
        consents = body.get('consents', {})
        age_confirmed = body.get('age_confirmed', True)
        is_minor = body.get('is_minor', False)
        guardian_consent_method = body.get('guardian_consent_method', '')
        guardian_name = body.get('guardian_name', '')

        if not user_id or not country_code:
            self._send_json(400, {'success': False, 'errors': ['user_id と country_code は必須です']})
            return

        req = RegistrationRequest(
            user_id=user_id,
            service='smartlife',
            country_code=country_code,
            consents=consents,
            age_confirmed=age_confirmed,
            is_minor=is_minor,
            guardian_consent_method=guardian_consent_method,
            guardian_name=guardian_name,
        )
        result = _processor.process_registration(req)

        gdpr_applicable = is_gdpr_applicable(country_code)

        if result.success:
            self._send_json(200, {
                'success': True,
                'granted_consents': result.granted_consents,
                'skipped_consents': result.skipped_consents,
                'gdpr_applicable': gdpr_applicable,
            })
        else:
            self._send_json(400, {
                'success': False,
                'errors': result.errors,
            })


def run(port: int = PORT) -> None:  # pragma: no cover
    server = HTTPServer(('0.0.0.0', port), SmartlifeUsersHandler)  # nosec B104 — Cloud Run requires 0.0.0.0 binding
    server.serve_forever()


if __name__ == '__main__':  # pragma: no cover
    run()
