"""SURPLUS SHIFT 商談サポートAPI テスト (Ver 1.0)"""
from __future__ import annotations

import json
import threading
import urllib.request
import urllib.error
from http.server import HTTPServer

import pytest

from src.surplus_shift.negotiation_api import (
    NegotiationEntry,
    NegotiationManager,
    SmartLifeProduct,
    STATUS_INITIAL_CONTACT,
    STATUS_AGREED,
    STATUS_NEGOTIATING,
    VALID_STATUSES,
)
from src.surplus_shift.surplus_api import SurplusHandler

TEST_PORT = 18085
BASE_URL = f'http://localhost:{TEST_PORT}'


# ──────────────────────────────────────────
# TestNegotiationManager
# ──────────────────────────────────────────

class TestNegotiationManager:

    def setup_method(self):
        self.mgr = NegotiationManager()
        self.entry = self.mgr.create(
            counterparty='テスト商事株式会社',
            product_name='高品質テスト商品',
            category='食品・飲料',
            proposed_price_jpy=50000,
            quantity=100,
            notes='テスト備考',
        )

    def test_create_returns_negotiation_entry(self):
        assert isinstance(self.entry, NegotiationEntry)

    def test_negotiation_id_is_16_chars(self):
        assert len(self.entry.negotiation_id) == 16

    def test_initial_status_is_initial_contact(self):
        assert self.entry.status == STATUS_INITIAL_CONTACT

    def test_update_status(self):
        updated = self.mgr.update_status(self.entry.negotiation_id, STATUS_NEGOTIATING)
        assert updated.status == STATUS_NEGOTIATING

    def test_update_status_invalid_raises_value_error(self):
        with pytest.raises(ValueError):
            self.mgr.update_status(self.entry.negotiation_id, 'invalid_status_xyz')

    def test_agree_sets_agreed_price(self):
        agreed = self.mgr.agree(self.entry.negotiation_id, agreed_price_jpy=45000)
        assert agreed.agreed_price_jpy == 45000

    def test_agree_sets_status_agreed(self):
        agreed = self.mgr.agree(self.entry.negotiation_id, agreed_price_jpy=45000)
        assert agreed.status == STATUS_AGREED

    def test_list_all_returns_all(self):
        self.mgr.create('別会社', '別商品', '日用品・消耗品', 10000, 50)
        entries = self.mgr.list_all()
        assert len(entries) == 2

    def test_list_all_status_filter(self):
        self.mgr.update_status(self.entry.negotiation_id, STATUS_NEGOTIATING)
        result = self.mgr.list_all(status=STATUS_NEGOTIATING)
        assert all(e.status == STATUS_NEGOTIATING for e in result)
        assert len(result) >= 1

    def test_export_pdf_html_returns_str(self):
        html = self.mgr.export_pdf_html(self.entry.negotiation_id)
        assert isinstance(html, str)

    def test_export_pdf_html_contains_html(self):
        html = self.mgr.export_pdf_html(self.entry.negotiation_id)
        assert '<html' in html.lower()

    def test_export_pdf_html_contains_counterparty(self):
        html = self.mgr.export_pdf_html(self.entry.negotiation_id)
        assert 'テスト商事株式会社' in html

    def test_to_smartlife_agreed_returns_product(self):
        self.mgr.agree(self.entry.negotiation_id, agreed_price_jpy=45000)
        product = self.mgr.to_smartlife(self.entry.negotiation_id)
        assert isinstance(product, SmartLifeProduct)

    def test_to_smartlife_not_agreed_raises_value_error(self):
        with pytest.raises(ValueError):
            self.mgr.to_smartlife(self.entry.negotiation_id)

    def test_smartlife_human_review_required_is_true(self):
        self.mgr.agree(self.entry.negotiation_id, agreed_price_jpy=45000)
        product = self.mgr.to_smartlife(self.entry.negotiation_id)
        assert product.human_review_required is True

    def test_summary_keys(self):
        result = self.mgr.summary()
        assert 'total_negotiations' in result
        assert 'by_status' in result
        assert 'smartlife_registered' in result


# ──────────────────────────────────────────
# TestSurplusAPIE2E — HTTPServer経由
# ──────────────────────────────────────────

@pytest.fixture(scope='module')
def surplus_server():
    """テスト用HTTPServerをバックグラウンドスレッドで起動"""
    # テスト用に独立したマネージャインスタンスを使うためハンドラをモンキーパッチ
    import src.surplus_shift.surplus_api as surplus_api_mod
    original_manager = surplus_api_mod._manager
    surplus_api_mod._manager = NegotiationManager()

    server = HTTPServer(('localhost', TEST_PORT), SurplusHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    surplus_api_mod._manager = original_manager


def _request(method: str, path: str, body: dict | None = None):
    url = f'{BASE_URL}{path}'
    data = json.dumps(body).encode('utf-8') if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode('utf-8'), resp.headers.get('Content-Type', '')
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode('utf-8'), ''


class TestSurplusAPIE2E:

    @pytest.fixture(autouse=True)
    def setup(self, surplus_server):
        pass

    def test_post_negotiations_201(self):
        status, body, _ = _request('POST', '/api/v1/surplus/negotiations', {
            'counterparty': 'E2E商事',
            'product_name': 'E2Eテスト品',
            'category': '家電・ガジェット',
            'proposed_price_jpy': 30000,
            'quantity': 10,
        })
        assert status == 201
        data = json.loads(body)
        assert 'negotiation_id' in data

    def test_get_negotiations_200_list(self):
        status, body, _ = _request('GET', '/api/v1/surplus/negotiations')
        assert status == 200
        data = json.loads(body)
        assert isinstance(data, list)

    def test_get_negotiation_by_id_200(self):
        _, create_body, _ = _request('POST', '/api/v1/surplus/negotiations', {
            'counterparty': 'ID取得テスト',
            'product_name': '商品X',
            'category': '日用品・消耗品',
            'proposed_price_jpy': 5000,
            'quantity': 20,
        })
        nid = json.loads(create_body)['negotiation_id']
        status, body, _ = _request('GET', f'/api/v1/surplus/negotiations/{nid}')
        assert status == 200
        assert json.loads(body)['negotiation_id'] == nid

    def test_get_export_pdf_200_html(self):
        _, create_body, _ = _request('POST', '/api/v1/surplus/negotiations', {
            'counterparty': 'PDF出力テスト',
            'product_name': '商品PDF',
            'category': '美容・健康',
            'proposed_price_jpy': 8000,
            'quantity': 5,
        })
        nid = json.loads(create_body)['negotiation_id']
        status, body, content_type = _request('GET', f'/api/v1/surplus/negotiations/{nid}/export-pdf')
        assert status == 200
        assert 'text/html' in content_type
        assert '<html' in body.lower()

    def test_post_to_smartlife_before_agree_400(self):
        _, create_body, _ = _request('POST', '/api/v1/surplus/negotiations', {
            'counterparty': 'SmartLifeテスト未合意',
            'product_name': '商品SL',
            'category': 'ペット用品',
            'proposed_price_jpy': 3000,
            'quantity': 30,
        })
        nid = json.loads(create_body)['negotiation_id']
        status, _, _ = _request('POST', '/api/v1/surplus/to-smartlife', {'negotiation_id': nid})
        assert status == 400

    def test_get_health_200(self):
        status, body, _ = _request('GET', '/health')
        assert status == 200
        data = json.loads(body)
        assert data['status'] == 'ok'
        assert data['module'] == 'surplus'

    def test_get_negotiations_with_status_filter_200(self):
        status, body, _ = _request('GET', '/api/v1/surplus/negotiations?status=initial_contact')
        assert status == 200
        data = json.loads(body)
        assert isinstance(data, list)
        for item in data:
            assert item['status'] == 'initial_contact'

    def test_get_negotiations_invalid_id_404(self):
        status, _, _ = _request('GET', '/api/v1/surplus/negotiations/nonexistent_id_xyz')
        assert status == 404
