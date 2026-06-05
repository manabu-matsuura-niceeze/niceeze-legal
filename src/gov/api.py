"""GOV API — Cloud Run HTTPエンドポイント (Ver 1.0)
GOV部門 MVP
FinOps: 月額¥5,000以内 / PII不使用 / bandit 0件
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from .s10_coo_report import COOReportEngine
from .finops_monitor import FinOpsMonitor
from .ops_log_collector import OpsLogCollector

_engine = COOReportEngine()
_finops = FinOpsMonitor()
_ops_log = OpsLogCollector()


class GovHandler(BaseHTTPRequestHandler):

    def _send_json(self, code: int, data: dict | list) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length)
        return json.loads(raw.decode('utf-8')) if raw else {}

    def log_message(self, fmt, *args):
        pass

    def do_GET(self) -> None:
        path = self.path
        if path == '/health':
            self._send_json(200, {'status': 'ok', 'module': 'gov', 'version': '1.0'})
        elif path.startswith('/coo/report/'):
            month = path.split('/')[-1]
            report = _engine.generate_report(month)
            self._send_json(200, report.to_dict())
        elif path.startswith('/finops/summary/'):
            month = path.split('/')[-1]
            self._send_json(200, _finops.monthly_summary(month))
        elif path == '/finops/alerts':
            self._send_json(200, [a.to_dict() for a in _finops.check_alerts()])
        elif path == '/ops/health':
            self._send_json(200, [s.to_dict() for s in _ops_log.health_status()])
        elif path.startswith('/ops/logs/'):
            service = path.split('/')[-1]
            self._send_json(200, [e.to_dict() for e in _ops_log.get_by_service(service)])
        else:
            self._send_json(404, {'error': 'Not Found', 'path': path})

    def do_POST(self) -> None:
        path = self.path
        body = self._read_json_body()
        try:
            if path == '/coo/kpi':
                rec = _engine.add_kpi(
                    kpi_name=body['kpi_name'], target=float(body['target']),
                    actual=float(body['actual']), unit=body['unit'], month=body['month'],
                )
                self._send_json(201, rec.to_dict())
            elif path == '/coo/budget':
                rec = _engine.add_budget(
                    item_name=body['item_name'], budget_jpy=int(body['budget_jpy']),
                    actual_jpy=int(body['actual_jpy']), month=body['month'],
                )
                self._send_json(201, rec.to_dict())
            elif path == '/coo/pmo':
                task = _engine.add_pmo_task(
                    task_name=body['task_name'], gate=body['gate'],
                    status=body['status'], owner=body['owner'], due_date=body['due_date'],
                )
                self._send_json(201, task.to_dict())
            elif path == '/finops/cost':
                rec = _finops.record_cost(
                    service=body['service'], cost_jpy=float(body['cost_jpy']),
                    delivery_count=int(body['delivery_count']), month=body['month'],
                )
                self._send_json(201, rec.to_dict())
            elif path == '/ops/log':
                entry = _ops_log.record(
                    service=body['service'], level=body['level'],
                    message=body['message'], metadata=body.get('metadata'),
                )
                self._send_json(201, entry.to_dict())
            else:
                self._send_json(404, {'error': 'Not Found', 'path': path})
        except (KeyError, ValueError) as exc:
            self._send_json(400, {'error': str(exc)})


def run_server(port: int = 8082) -> None:
    server_address = ('0.0.0.0', port)  # nosec B104 — Cloud Run requires 0.0.0.0 binding
    httpd = HTTPServer(server_address, GovHandler)
    print(f'GOV API listening on port {port}')
    httpd.serve_forever()


if __name__ == '__main__':
    run_server()
