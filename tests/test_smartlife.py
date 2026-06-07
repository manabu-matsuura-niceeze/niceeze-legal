"""SmartLife EC — ユニットテスト (30件以上)"""
from __future__ import annotations

import io
import json
import unittest
from http.server import BaseHTTPRequestHandler
from unittest.mock import patch, MagicMock

from src.smartlife.products import (
    Product, ProductStore, register_from_surplus,
    BUILDING_TYPES, CATEGORIES,
)
from src.smartlife.orders import (
    OrderItem, GroupOrder, GroupOrderStore, ZeroStockTrigger,
)
from src.smartlife.api import _smartlife_api_app, PORT


# ── Helpers ───────────────────────────────────────────────────────────────

def _make_product(**kwargs) -> Product:
    defaults = dict(
        id='test0001',
        name='テスト商品',
        building_type='family',
        category='daily_goods',
        price_jpy=1000,
        min_order_qty=1,
        supplier_code='SUP001',
        created_at='2026-06-07T00:00:00+00:00',
    )
    defaults.update(kwargs)
    return Product(**defaults)


def _make_order_item(**kwargs) -> OrderItem:
    defaults = dict(product_id='test0001', qty=5, unit_price_jpy=1000)
    defaults.update(kwargs)
    return OrderItem(**defaults)


# ── ProductStore tests ─────────────────────────────────────────────────────

class TestProductStore(unittest.TestCase):

    def setUp(self):
        self.store = ProductStore()

    def test_add_returns_product(self):
        p = _make_product()
        result = self.store.add(p)
        self.assertIs(result, p)

    def test_add_invalid_building_type_raises(self):
        p = _make_product(building_type='invalid')
        with self.assertRaises(ValueError):
            self.store.add(p)

    def test_add_invalid_category_raises(self):
        p = _make_product(category='invalid_cat')
        with self.assertRaises(ValueError):
            self.store.add(p)

    def test_get_existing(self):
        p = _make_product(id='aaa00001')
        self.store.add(p)
        result = self.store.get('aaa00001')
        self.assertEqual(result, p)

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.store.get('nonexist'))

    def test_update_name(self):
        p = _make_product(id='upd00001')
        self.store.add(p)
        updated = self.store.update('upd00001', {'name': '新商品名'})
        self.assertEqual(updated.name, '新商品名')

    def test_update_price(self):
        p = _make_product(id='upd00002')
        self.store.add(p)
        updated = self.store.update('upd00002', {'price_jpy': 9999})
        self.assertEqual(updated.price_jpy, 9999)

    def test_update_invalid_building_type_raises(self):
        p = _make_product(id='upd00003')
        self.store.add(p)
        with self.assertRaises(ValueError):
            self.store.update('upd00003', {'building_type': 'unknown'})

    def test_update_invalid_category_raises(self):
        p = _make_product(id='upd00004')
        self.store.add(p)
        with self.assertRaises(ValueError):
            self.store.update('upd00004', {'category': 'bad_cat'})

    def test_update_missing_returns_none(self):
        result = self.store.update('nonexist', {'name': 'X'})
        self.assertIsNone(result)

    def test_list_by_building_type_filters(self):
        self.store.add(_make_product(id='l001', building_type='luxury'))
        self.store.add(_make_product(id='f001', building_type='family'))
        self.store.add(_make_product(id='f002', building_type='family'))
        luxury = self.store.list_by_building_type('luxury')
        family = self.store.list_by_building_type('family')
        self.assertEqual(len(luxury), 1)
        self.assertEqual(len(family), 2)

    def test_list_all(self):
        self.store.add(_make_product(id='a001'))
        self.store.add(_make_product(id='a002'))
        self.assertEqual(len(self.store.list_all()), 2)

    def test_all_building_types_accepted(self):
        for i, bt in enumerate(BUILDING_TYPES):
            p = _make_product(id=f'bt0000{i}', building_type=bt)
            self.store.add(p)
        self.assertEqual(len(self.store.list_all()), len(BUILDING_TYPES))

    def test_all_categories_accepted(self):
        for i, cat in enumerate(CATEGORIES):
            p = _make_product(id=f'ct0000{i}', category=cat)
            self.store.add(p)


# ── register_from_surplus tests ───────────────────────────────────────────

class TestRegisterFromSurplus(unittest.TestCase):

    def _base(self, **kwargs):
        data = dict(
            status='agreed',
            product_name='テスト食品',
            building_type='family',
            category='food',
            agreed_price_jpy=2000,
            min_order_qty=3,
            supplier_code='SURP01',
        )
        data.update(kwargs)
        return data

    def test_agreed_status_creates_product(self):
        p = register_from_surplus(self._base(status='agreed'))
        self.assertIsInstance(p, Product)
        self.assertEqual(p.name, 'テスト食品')

    def test_closed_won_status_creates_product(self):
        p = register_from_surplus(self._base(status='closed_won'))
        self.assertIsInstance(p, Product)

    def test_invalid_status_raises(self):
        for status in ('pending', 'rejected', 'open', '', 'negotiating'):
            with self.assertRaises(ValueError):
                register_from_surplus(self._base(status=status))

    def test_product_id_truncated_to_8(self):
        p = register_from_surplus(self._base(product_id='abcdefghijklmnop'))
        self.assertEqual(len(p.id), 8)

    def test_invalid_building_type_defaults_to_family(self):
        p = register_from_surplus(self._base(building_type='unknown'))
        self.assertEqual(p.building_type, 'family')

    def test_invalid_category_defaults_to_other(self):
        p = register_from_surplus(self._base(category='bad'))
        self.assertEqual(p.category, 'other')


# ── GroupOrderStore tests ─────────────────────────────────────────────────

class TestGroupOrderStore(unittest.TestCase):

    def setUp(self):
        self.store = GroupOrderStore()
        self.items = [_make_order_item()]

    def test_create_returns_pending(self):
        order = self.store.create('BLDG-001', self.items, '2026-07-01', '2026-06-20')
        self.assertEqual(order.status, 'pending')
        self.assertEqual(order.building_code, 'BLDG-001')

    def test_create_unique_ids(self):
        o1 = self.store.create('B1', self.items, '2026-07-01', '2026-06-20')
        o2 = self.store.create('B2', self.items, '2026-07-02', '2026-06-21')
        self.assertNotEqual(o1.order_id, o2.order_id)

    def test_get_existing(self):
        order = self.store.create('BLDG-002', self.items, '2026-07-05', '2026-06-25')
        result = self.store.get(order.order_id)
        self.assertEqual(result.order_id, order.order_id)

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.store.get('nonexist'))

    def test_list_all(self):
        self.store.create('B1', self.items, '2026-07-01', '2026-06-20')
        self.store.create('B2', self.items, '2026-07-02', '2026-06-21')
        self.assertEqual(len(self.store.list()), 2)

    def test_list_by_building_code(self):
        self.store.create('BLDG-A', self.items, '2026-07-01', '2026-06-20')
        self.store.create('BLDG-A', self.items, '2026-07-02', '2026-06-21')
        self.store.create('BLDG-B', self.items, '2026-07-03', '2026-06-22')
        result = self.store.list('BLDG-A')
        self.assertEqual(len(result), 2)

    def test_confirm_pending_order(self):
        order = self.store.create('BLDG-001', self.items, '2026-07-01', '2026-06-20')
        confirmed = self.store.confirm_order(order.order_id)
        self.assertEqual(confirmed.status, 'confirmed')

    def test_confirm_non_pending_raises(self):
        order = self.store.create('BLDG-001', self.items, '2026-07-01', '2026-06-20')
        self.store.confirm_order(order.order_id)
        with self.assertRaises(ValueError):
            self.store.confirm_order(order.order_id)

    def test_confirm_missing_returns_none(self):
        self.assertIsNone(self.store.confirm_order('nonexist'))

    def test_cancel_pending_order(self):
        order = self.store.create('BLDG-001', self.items, '2026-07-01', '2026-06-20')
        cancelled = self.store.cancel(order.order_id)
        self.assertEqual(cancelled.status, 'cancelled')

    def test_cancel_delivered_raises(self):
        order = self.store.create('BLDG-001', self.items, '2026-07-01', '2026-06-20')
        order.status = 'delivered'
        with self.assertRaises(ValueError):
            self.store.cancel(order.order_id)

    def test_cancel_missing_returns_none(self):
        self.assertIsNone(self.store.cancel('nonexist'))


# ── ZeroStockTrigger tests ────────────────────────────────────────────────

class TestZeroStockTrigger(unittest.TestCase):

    def test_human_approval_required_is_true(self):
        trigger = ZeroStockTrigger()
        self.assertTrue(trigger.human_approval_required)

    def test_human_approval_required_cannot_be_changed_to_false(self):
        trigger = ZeroStockTrigger()
        with self.assertRaises(AttributeError):
            trigger.human_approval_required = False

    def test_human_approval_required_cannot_be_changed_to_true(self):
        trigger = ZeroStockTrigger()
        with self.assertRaises(AttributeError):
            trigger.human_approval_required = True

    def test_trigger_supplier_order_sends_correct_payload(self):
        trigger = ZeroStockTrigger()
        items = [_make_order_item()]
        order = GroupOrder(
            order_id='ord00001', building_code='BLDG-001', items=items,
            status='confirmed', delivery_date='2026-07-01',
            deadline='2026-06-20', created_at='2026-06-07T00:00:00+00:00',
        )

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({'ok': True}).encode()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch('src.smartlife.orders.urllib.request.urlopen', return_value=mock_resp) as mock_urlopen:
            result = trigger.trigger_supplier_order(order, 'http://localhost:9999/api/orders')

        self.assertTrue(result.get('ok'))
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        payload = json.loads(req.data.decode())
        self.assertEqual(payload['source'], 'smartlife')
        self.assertEqual(payload['building_code'], 'BLDG-001')
        self.assertTrue(payload['human_approval_required'])
        self.assertEqual(len(payload['items']), 1)


# ── API handler tests ─────────────────────────────────────────────────────

class FakeSocket:
    def makefile(self, *a, **kw):
        return io.BytesIO()


def _make_handler(method: str, path: str, body: bytes = b'', product_store=None, order_store=None):
    """テスト用 HTTPRequestHandler インスタンスを生成する"""
    Handler = _smartlife_api_app()

    # Override stores for isolation
    ps = product_store or ProductStore()
    os_ = order_store or GroupOrderStore()

    request_data = (
        f"{method} {path} HTTP/1.1\r\n"
        f"Host: localhost\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Content-Type: application/json\r\n"
        f"\r\n"
    ).encode() + body

    request = io.BytesIO(request_data)
    response = io.BytesIO()

    class FakeSock:
        def makefile(self, mode, *a, **kw):
            if 'r' in mode:
                return request
            return response

    handler = Handler.__new__(Handler)
    handler.product_store = ps
    handler.order_store = os_
    handler.rfile = request
    handler.wfile = response
    handler.headers = {
        'Content-Length': str(len(body)),
        'Content-Type': 'application/json',
    }
    handler.path = path
    handler.request_version = 'HTTP/1.1'
    handler.server_version = 'TestServer'
    handler.sys_version = ''
    handler.error_message_format = '%s'
    handler.error_content_type = 'text/plain'
    return handler, response


def _call_handler(method: str, path: str, body: dict | None = None,
                  product_store=None, order_store=None):
    body_bytes = json.dumps(body, ensure_ascii=False).encode() if body else b''
    Handler = _smartlife_api_app()
    ps = product_store or ProductStore()
    os_ = order_store or GroupOrderStore()

    response_buf = io.BytesIO()
    captured = {}

    class TestHandler(Handler):
        def send_response(self, code, message=None):
            captured['status'] = code

        def send_header(self, k, v):
            captured.setdefault('headers', {})[k] = v

        def end_headers(self):
            pass

        def log_message(self, *a):
            pass

    handler = TestHandler.__new__(TestHandler)
    handler.product_store = ps
    handler.order_store = os_
    handler.wfile = response_buf
    handler.rfile = io.BytesIO(body_bytes)
    handler.headers = {'Content-Length': str(len(body_bytes)), 'Content-Type': 'application/json'}
    handler.path = path
    handler.request_version = 'HTTP/1.1'

    method_func = getattr(handler, f'do_{method}')
    method_func()

    response_buf.seek(0)
    raw = response_buf.read()
    try:
        resp_json = json.loads(raw)
    except Exception:
        resp_json = {}

    return captured.get('status', 0), resp_json


class TestAPIHealth(unittest.TestCase):

    def test_health_returns_200(self):
        status, body = _call_handler('GET', '/health')
        self.assertEqual(status, 200)
        self.assertEqual(body.get('status'), 'ok')
        self.assertEqual(body.get('port'), PORT)


class TestAPIProducts(unittest.TestCase):

    def test_post_product_returns_201(self):
        ps = ProductStore()
        status, body = _call_handler('POST', '/api/v1/smartlife/products', {
            'name': '米 5kg', 'building_type': 'family', 'category': 'food',
            'price_jpy': 3000, 'min_order_qty': 2, 'supplier_code': 'S01',
        }, product_store=ps)
        self.assertEqual(status, 201)
        self.assertEqual(body.get('name'), '米 5kg')

    def test_post_product_invalid_building_type_returns_422(self):
        status, body = _call_handler('POST', '/api/v1/smartlife/products', {
            'name': 'X', 'building_type': 'bad', 'category': 'food',
            'price_jpy': 100, 'min_order_qty': 1, 'supplier_code': 'S00',
        })
        self.assertEqual(status, 422)

    def test_get_products_returns_200(self):
        ps = ProductStore()
        ps.add(_make_product(id='g001'))
        status, body = _call_handler('GET', '/api/v1/smartlife/products', product_store=ps)
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)
        self.assertEqual(len(body), 1)

    def test_get_products_filter_by_building_type(self):
        ps = ProductStore()
        ps.add(_make_product(id='lux1', building_type='luxury'))
        ps.add(_make_product(id='fam1', building_type='family'))
        status, body = _call_handler('GET', '/api/v1/smartlife/products?building_type=luxury', product_store=ps)
        self.assertEqual(status, 200)
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]['building_type'], 'luxury')

    def test_put_product_returns_200(self):
        ps = ProductStore()
        p = _make_product(id='put00001')
        ps.add(p)
        status, body = _call_handler('PUT', '/api/v1/smartlife/products/put00001',
                                     {'name': '更新済み商品'}, product_store=ps)
        self.assertEqual(status, 200)
        self.assertEqual(body.get('name'), '更新済み商品')

    def test_put_product_not_found_returns_404(self):
        status, body = _call_handler('PUT', '/api/v1/smartlife/products/notfound',
                                     {'name': 'X'})
        self.assertEqual(status, 404)


class TestAPIOrders(unittest.TestCase):

    def test_post_group_order_returns_201(self):
        os_ = GroupOrderStore()
        status, body = _call_handler('POST', '/api/v1/smartlife/orders/group', {
            'building_code': 'BLDG-001',
            'items': [{'product_id': 'abc', 'qty': 3, 'unit_price_jpy': 1000}],
            'delivery_date': '2026-07-01',
            'deadline': '2026-06-20',
        }, order_store=os_)
        self.assertEqual(status, 201)
        self.assertEqual(body.get('building_code'), 'BLDG-001')
        self.assertEqual(body.get('status'), 'pending')

    def test_get_orders_returns_200(self):
        os_ = GroupOrderStore()
        os_.create('BLDG-001', [_make_order_item()], '2026-07-01', '2026-06-20')
        status, body = _call_handler('GET', '/api/v1/smartlife/orders', order_store=os_)
        self.assertEqual(status, 200)
        self.assertIsInstance(body, list)

    def test_get_orders_filter_by_building_code(self):
        os_ = GroupOrderStore()
        os_.create('BLDG-A', [_make_order_item()], '2026-07-01', '2026-06-20')
        os_.create('BLDG-B', [_make_order_item()], '2026-07-02', '2026-06-21')
        status, body = _call_handler('GET', '/api/v1/smartlife/orders?building_code=BLDG-A', order_store=os_)
        self.assertEqual(status, 200)
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]['building_code'], 'BLDG-A')


class TestAPIFromSurplus(unittest.TestCase):

    def test_from_surplus_agreed_returns_201(self):
        ps = ProductStore()
        status, body = _call_handler('POST', '/api/v1/smartlife/from-surplus', {
            'status': 'agreed',
            'product_name': 'サプライ商品',
            'building_type': 'student',
            'category': 'food',
            'agreed_price_jpy': 1500,
            'min_order_qty': 5,
            'supplier_code': 'SURP01',
        }, product_store=ps)
        self.assertEqual(status, 201)
        self.assertEqual(body.get('name'), 'サプライ商品')

    def test_from_surplus_invalid_status_returns_422(self):
        status, body = _call_handler('POST', '/api/v1/smartlife/from-surplus', {
            'status': 'pending',
            'product_name': 'X',
        })
        self.assertEqual(status, 422)


class TestAPINotFound(unittest.TestCase):

    def test_unknown_get_returns_404(self):
        status, body = _call_handler('GET', '/api/v1/smartlife/unknown_endpoint')
        self.assertEqual(status, 404)

    def test_unknown_post_returns_404(self):
        status, body = _call_handler('POST', '/api/v1/smartlife/unknown_endpoint', {})
        self.assertEqual(status, 404)


if __name__ == '__main__':
    unittest.main()
