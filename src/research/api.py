"""RESEARCH API — Cloud Run HTTPエントリポイント (Ver 1.0)"""

import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

from .res_a01 import PriceFetcher
from .res_a02 import TrendFetcher
from .analytics import ResearchAnalytics


class ResearchHandler(BaseHTTPRequestHandler):
    """RESEARCH部 HTTPリクエストハンドラ"""

    def _send_json(self, status: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')  # LIFF アクセス対応
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        def _get(key: str, default: str = '') -> str:
            vals = params.get(key, [default])
            return vals[0] if vals else default

        if path == '/health':
            self._send_json(200, {
                'status': 'ok',
                'module': 'research',
                'version': '1.0',
            })

        elif path == '/price':
            keyword = _get('keyword', 'unknown')
            category = _get('category', '日用品・消耗品')
            matrix = PriceFetcher().build_matrix(keyword, category)
            self._send_json(200, matrix.to_dict())

        elif path == '/trend':
            keyword = _get('keyword', 'unknown')
            category = _get('category', '日用品・消耗品')
            try:
                days = int(_get('days', '30'))
            except ValueError:
                days = 30
            trend = TrendFetcher().fetch(keyword, category, days)
            self._send_json(200, trend.to_dict())

        elif path == '/api/v1/research/price-trend':
            category = _get('category', '日用品・消耗品')
            try:
                days = int(_get('days', '30'))
            except ValueError:
                days = 30
            analytics = ResearchAnalytics()
            results = analytics.price_trend(category, days)
            now = datetime.now(timezone.utc).isoformat()
            self._send_json(200, {
                'data': [r.to_dict() for r in results],
                'count': len(results),
                'generated_at': now,
            })

        elif path == '/api/v1/research/ranking':
            building_type = _get('building_type', 'family')
            try:
                limit = int(_get('limit', '10'))
            except ValueError:
                limit = 10
            analytics = ResearchAnalytics()
            results = analytics.ranking(building_type, limit)
            now = datetime.now(timezone.utc).isoformat()
            self._send_json(200, {
                'data': [r.to_dict() for r in results],
                'count': len(results),
                'generated_at': now,
            })

        elif path == '/api/v1/research/growth-alert':
            try:
                threshold = float(_get('threshold', '0.30'))
            except ValueError:
                threshold = 0.30
            analytics = ResearchAnalytics()
            results = analytics.growth_alerts(threshold)
            now = datetime.now(timezone.utc).isoformat()
            self._send_json(200, {
                'data': [r.to_dict() for r in results],
                'count': len(results),
                'generated_at': now,
            })

        elif path == '/api/v1/research/new-products':
            try:
                days = int(_get('days', '30'))
            except ValueError:
                days = 30
            analytics = ResearchAnalytics()
            results = analytics.new_products(days)
            now = datetime.now(timezone.utc).isoformat()
            self._send_json(200, {
                'data': [r.to_dict() for r in results],
                'count': len(results),
                'generated_at': now,
            })

        else:
            self._send_json(404, {'error': 'Not Found', 'path': path})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/v1/research/export':
            # Authorization チェック
            auth_header = self.headers.get('Authorization', '')
            expected_token = os.environ.get('RESEARCH_EXPORT_TOKEN', 'demo-token')
            if not auth_header.startswith('Bearer '):
                self._send_json(401, {'error': 'Unauthorized', 'detail': 'Bearer token required'})
                return
            token = auth_header[len('Bearer '):]
            if token != expected_token:
                self._send_json(401, {'error': 'Unauthorized', 'detail': 'Invalid token'})
                return

            # ボディ読み込み
            content_length = int(self.headers.get('Content-Length', '0'))
            body_bytes = self.rfile.read(content_length) if content_length > 0 else b'{}'
            try:
                body = json.loads(body_bytes.decode('utf-8'))
            except (ValueError, UnicodeDecodeError):
                body = {}

            fmt = body.get('format', 'csv')
            category = body.get('category', '日用品・消耗品')
            try:
                days = int(body.get('days', 30))
            except (ValueError, TypeError):
                days = 30

            analytics = ResearchAnalytics()
            trend_results = analytics.price_trend(category, days)
            now = datetime.now(timezone.utc).isoformat()
            data_payload = {
                'data': [r.to_dict() for r in trend_results],
                'count': len(trend_results),
                'generated_at': now,
            }

            if fmt == 'csv':
                content = analytics.export_csv(data_payload)
            else:
                content = analytics.export_summary(data_payload)

            self._send_json(200, {
                'format': fmt,
                'content': content,
                'count': data_payload['count'],
                'generated_at': now,
            })
        else:
            self._send_json(404, {'error': 'Not Found', 'path': path})

    def log_message(self, fmt: str, *args) -> None:  # noqa: ANN002
        """標準ログ出力（Cloud Run stdout に出力）"""
        print(f'[RESEARCH API] {fmt % args}')


def run_server(port: int = 8080) -> None:
    """HTTPサーバーを起動する"""
    server_address = ('0.0.0.0', port)  # nosec B104 — Cloud Run container — external access controlled by GCP IAM
    httpd = HTTPServer(server_address, ResearchHandler)
    print(f'[RESEARCH API] Starting on port {port}')
    httpd.serve_forever()


if __name__ == '__main__':
    run_server()
