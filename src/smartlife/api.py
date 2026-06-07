"""SmartLife EC — REST API (port 8086)

stdlib only: http.server.BaseHTTPRequestHandler + json + urllib.parse
"""
from __future__ import annotations

import json
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from typing import Tuple

from .products import Product, ProductStore, register_from_surplus, BUILDING_TYPES, CATEGORIES
from .orders import OrderItem, GroupOrderStore, ZeroStockTrigger

PORT = 8086

_product_store = ProductStore()
_order_store = GroupOrderStore()


def _new_short_id() -> str:
    return str(uuid.uuid4())[:8]


def _json_response(handler: BaseHTTPRequestHandler, status: int, data: object) -> None:
    body = json.dumps(data, ensure_ascii=False).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json_body(handler: BaseHTTPRequestHandler) -> Tuple[dict, str]:
    length = int(handler.headers.get('Content-Length', 0))
    if length == 0:
        return {}, ''
    raw = handler.rfile.read(length).decode('utf-8')
    try:
        return json.loads(raw), ''
    except json.JSONDecodeError as exc:
        return {}, str(exc)


def _smartlife_api_app():
    """テスト用: HTTPRequestHandlerクラスを返す"""

    class SmartLifeHandler(BaseHTTPRequestHandler):
        product_store = _product_store
        order_store = _order_store

        def log_message(self, fmt, *args):  # suppress default logging
            pass

        # ── GET ──────────────────────────────────────────────────────────────
        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path.rstrip('/')
            qs = parse_qs(parsed.query)

            if path == '/health':
                _json_response(self, 200, {'status': 'ok', 'service': 'smartlife', 'port': PORT})

            elif path == '/api/v1/smartlife/products':
                building_type = qs.get('building_type', [None])[0]
                if building_type:
                    products = self.product_store.list_by_building_type(building_type)
                else:
                    products = self.product_store.list_all()
                _json_response(self, 200, [p.to_dict() for p in products])

            elif path == '/api/v1/smartlife/orders':
                building_code = qs.get('building_code', [None])[0]
                orders = self.order_store.list(building_code)
                _json_response(self, 200, [o.to_dict() for o in orders])

            elif path.startswith('/api/v1/smartlife/static/'):
                self._serve_static(path)

            else:
                _json_response(self, 404, {'error': 'Not found', 'path': path})

        # ── POST ─────────────────────────────────────────────────────────────
        def do_POST(self):
            parsed = urlparse(self.path)
            path = parsed.path.rstrip('/')

            if path == '/api/v1/smartlife/products':
                body, err = _read_json_body(self)
                if err:
                    _json_response(self, 400, {'error': f'Invalid JSON: {err}'})
                    return
                try:
                    product = Product(
                        id=body.get('id') or _new_short_id(),
                        name=body.get('name', ''),
                        building_type=body.get('building_type', ''),
                        category=body.get('category', ''),
                        price_jpy=int(body.get('price_jpy', 0)),
                        min_order_qty=int(body.get('min_order_qty', 1)),
                        supplier_code=body.get('supplier_code', ''),
                        created_at=body.get('created_at', ''),
                    )
                    if not product.created_at:
                        from datetime import datetime, timezone
                        product.created_at = datetime.now(timezone.utc).isoformat()
                    self.product_store.add(product)
                    _json_response(self, 201, product.to_dict())
                except ValueError as exc:
                    _json_response(self, 422, {'error': str(exc)})

            elif path == '/api/v1/smartlife/orders/group':
                body, err = _read_json_body(self)
                if err:
                    _json_response(self, 400, {'error': f'Invalid JSON: {err}'})
                    return
                try:
                    items_raw = body.get('items', [])
                    items = [
                        OrderItem(
                            product_id=i.get('product_id', ''),
                            qty=int(i.get('qty', 1)),
                            unit_price_jpy=int(i.get('unit_price_jpy', 0)),
                        )
                        for i in items_raw
                    ]
                    order = self.order_store.create(
                        building_code=body.get('building_code', ''),
                        items=items,
                        delivery_date=body.get('delivery_date', ''),
                        deadline=body.get('deadline', ''),
                    )
                    _json_response(self, 201, order.to_dict())
                except (ValueError, TypeError) as exc:
                    _json_response(self, 422, {'error': str(exc)})

            elif path == '/api/v1/smartlife/from-surplus':
                body, err = _read_json_body(self)
                if err:
                    _json_response(self, 400, {'error': f'Invalid JSON: {err}'})
                    return
                try:
                    product = register_from_surplus(body)
                    self.product_store.add(product)
                    _json_response(self, 201, product.to_dict())
                except ValueError as exc:
                    _json_response(self, 422, {'error': str(exc)})

            else:
                _json_response(self, 404, {'error': 'Not found', 'path': path})

        # ── PUT ──────────────────────────────────────────────────────────────
        def do_PUT(self):
            parsed = urlparse(self.path)
            path = parsed.path.rstrip('/')

            if path.startswith('/api/v1/smartlife/products/'):
                product_id = path.split('/')[-1]
                body, err = _read_json_body(self)
                if err:
                    _json_response(self, 400, {'error': f'Invalid JSON: {err}'})
                    return
                try:
                    product = self.product_store.update(product_id, body)
                    if product is None:
                        _json_response(self, 404, {'error': f'Product {product_id} not found'})
                    else:
                        _json_response(self, 200, product.to_dict())
                except ValueError as exc:
                    _json_response(self, 422, {'error': str(exc)})
            else:
                _json_response(self, 404, {'error': 'Not found', 'path': path})

        def _serve_static(self, path: str) -> None:
            _json_response(self, 404, {'error': 'Static file not found via API', 'path': path})

    return SmartLifeHandler


def run_server(port: int = PORT) -> None:
    handler = _smartlife_api_app()
    server = HTTPServer(('0.0.0.0', port), handler)  # nosec B104
    print(f"SmartLife EC API running on port {port}")
    server.serve_forever()


if __name__ == '__main__':
    run_server()
