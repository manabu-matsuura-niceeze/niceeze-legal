"""RESEARCH API — Cloud Run HTTPエントリポイント (Ver 1.0)"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

from .res_a01 import PriceFetcher
from .res_a02 import TrendFetcher


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
