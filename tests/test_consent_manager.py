# tests/test_consent_manager.py
# TASK-PP1: 同意管理システム テスト (35件以上)

import hashlib
import json
import threading
import time
import urllib.request
import urllib.error
from http.server import HTTPServer

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from common.consent_manager import (
    ConsentManager,
    ConsentRecord,
    VALID_CONSENT_TYPES,
    VALID_SERVICES,
)
from common.consent_api import ConsentAPIHandler, _consent_manager


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def new_manager() -> ConsentManager:
    return ConsentManager()


# ---------------------------------------------------------------------------
# 1. VALID_CONSENT_TYPES の全9種でgrant確認
# ---------------------------------------------------------------------------

class TestGrantAllConsentTypes:
    def test_terms_of_service(self):
        m = new_manager()
        r = m.grant('u1', 'sbds', 'terms_of_service')
        assert r.consent_type == 'terms_of_service'
        assert r.granted is True

    def test_privacy_policy(self):
        m = new_manager()
        r = m.grant('u1', 'sbds', 'privacy_policy')
        assert r.consent_type == 'privacy_policy'
        assert r.granted is True

    def test_delivery_preference(self):
        m = new_manager()
        r = m.grant('u1', 'smartlife', 'delivery_preference')
        assert r.granted is True

    def test_line_integration(self):
        m = new_manager()
        r = m.grant('u1', 'smartlife', 'line_integration')
        assert r.granted is True

    def test_ai_learning(self):
        m = new_manager()
        r = m.grant('u1', 'research', 'ai_learning')
        assert r.granted is True

    def test_location_info_travel(self):
        m = new_manager()
        r = m.grant('u1', 'travel', 'location_info_travel')
        assert r.granted is True

    def test_marketing_communication(self):
        m = new_manager()
        r = m.grant('u1', 'marketing', 'marketing_communication')
        assert r.granted is True

    def test_cookie_analytics(self):
        m = new_manager()
        r = m.grant('u1', 'sbds', 'cookie_analytics')
        assert r.granted is True

    def test_gdpr_rights_acknowledged(self):
        m = new_manager()
        r = m.grant('u1', 'gov', 'gdpr_rights_acknowledged')
        assert r.granted is True


# ---------------------------------------------------------------------------
# 2. VALID_CONSENT_TYPES の全9種でrevoke確認
# ---------------------------------------------------------------------------

class TestRevokeAllConsentTypes:
    @pytest.mark.parametrize('ct', VALID_CONSENT_TYPES)
    def test_revoke_all_types(self, ct):
        m = new_manager()
        svc = VALID_SERVICES[0]
        m.grant('u2', svc, ct)
        r = m.revoke('u2', svc, ct)
        assert r.granted is False
        assert r.revoked_at != ''


# ---------------------------------------------------------------------------
# 3. is_granted: grant後True、revoke後False
# ---------------------------------------------------------------------------

class TestIsGranted:
    def test_is_granted_after_grant(self):
        m = new_manager()
        m.grant('u3', 'sbds', 'privacy_policy')
        assert m.is_granted('u3', 'sbds', 'privacy_policy') is True

    def test_is_granted_after_revoke(self):
        m = new_manager()
        m.grant('u3', 'sbds', 'privacy_policy')
        m.revoke('u3', 'sbds', 'privacy_policy')
        assert m.is_granted('u3', 'sbds', 'privacy_policy') is False

    def test_is_granted_no_record(self):
        m = new_manager()
        assert m.is_granted('unknown', 'sbds', 'privacy_policy') is False

    def test_is_granted_re_grant_after_revoke(self):
        m = new_manager()
        m.grant('u3', 'sbds', 'privacy_policy')
        m.revoke('u3', 'sbds', 'privacy_policy')
        m.grant('u3', 'sbds', 'privacy_policy')
        assert m.is_granted('u3', 'sbds', 'privacy_policy') is True


# ---------------------------------------------------------------------------
# 4. ai_learning revoke → ai_learning_excluded=True フラグ確認
# ---------------------------------------------------------------------------

class TestAiLearningExclusion:
    def test_ai_learning_revoke_sets_excluded_flag(self):
        m = new_manager()
        m.grant('u4', 'research', 'ai_learning')
        r = m.revoke('u4', 'research', 'ai_learning')
        assert r.ai_learning_excluded is True

    def test_ai_learning_revoke_sets_all_records_excluded(self):
        m = new_manager()
        m.grant('u4', 'sbds', 'privacy_policy')
        m.grant('u4', 'research', 'ai_learning')
        m.revoke('u4', 'research', 'ai_learning')
        status = m.get_status('u4')
        for rec in status:
            assert rec.ai_learning_excluded is True

    def test_ai_learning_excluded_flag_not_set_without_revoke(self):
        m = new_manager()
        m.grant('u5', 'research', 'ai_learning')
        assert m.is_granted('u5', 'research', 'ai_learning') is True
        status = m.get_status('u5')
        assert all(not r.ai_learning_excluded for r in status)

    def test_get_ai_learning_excluded_users(self):
        m = new_manager()
        m.grant('u6', 'research', 'ai_learning')
        assert 'u6' not in m.get_ai_learning_excluded_users()
        m.revoke('u6', 'research', 'ai_learning')
        assert 'u6' in m.get_ai_learning_excluded_users()

    def test_get_ai_learning_excluded_users_multiple(self):
        m = new_manager()
        for uid in ['ua', 'ub', 'uc']:
            m.grant(uid, 'research', 'ai_learning')
            m.revoke(uid, 'research', 'ai_learning')
        excluded = m.get_ai_learning_excluded_users()
        assert set(excluded) == {'ua', 'ub', 'uc'}


# ---------------------------------------------------------------------------
# 5. ip_addressがハッシュ化されることの確認（平文が残らない）
# ---------------------------------------------------------------------------

class TestIpAddressHashing:
    def test_ip_is_hashed(self):
        m = new_manager()
        ip = '192.168.1.100'
        r = m.grant('u7', 'sbds', 'privacy_policy', ip_address=ip)
        assert r.ip_address != ip
        expected_hash = hashlib.sha256(ip.encode('utf-8')).hexdigest()
        assert r.ip_address == expected_hash

    def test_ip_plaintext_not_stored(self):
        m = new_manager()
        ip = '10.0.0.1'
        r = m.grant('u7', 'sbds', 'terms_of_service', ip_address=ip)
        assert ip not in r.ip_address

    def test_empty_ip_stays_empty(self):
        m = new_manager()
        r = m.grant('u7', 'sbds', 'cookie_analytics', ip_address='')
        assert r.ip_address == ''


# ---------------------------------------------------------------------------
# 6. user_agentが100文字以内に切り詰められる確認
# ---------------------------------------------------------------------------

class TestUserAgentTruncation:
    def test_user_agent_truncated_to_100(self):
        m = new_manager()
        ua = 'A' * 200
        r = m.grant('u8', 'sbds', 'privacy_policy', user_agent=ua)
        assert len(r.user_agent) == 100

    def test_user_agent_short_unchanged(self):
        m = new_manager()
        ua = 'Mozilla/5.0'
        r = m.grant('u8', 'sbds', 'cookie_analytics', user_agent=ua)
        assert r.user_agent == ua

    def test_user_agent_exactly_100(self):
        m = new_manager()
        ua = 'B' * 100
        r = m.grant('u8', 'sbds', 'line_integration', user_agent=ua)
        assert r.user_agent == ua


# ---------------------------------------------------------------------------
# 7. get_status (service指定あり/なし)
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_get_status_all_services(self):
        m = new_manager()
        m.grant('u9', 'sbds', 'privacy_policy')
        m.grant('u9', 'smartlife', 'terms_of_service')
        records = m.get_status('u9')
        assert len(records) == 2

    def test_get_status_with_service_filter(self):
        m = new_manager()
        m.grant('u9', 'sbds', 'privacy_policy')
        m.grant('u9', 'smartlife', 'terms_of_service')
        records = m.get_status('u9', service='sbds')
        assert len(records) == 1
        assert records[0].service == 'sbds'

    def test_get_status_empty_for_unknown_user(self):
        m = new_manager()
        assert m.get_status('unknown_user') == []

    def test_get_status_includes_revoked(self):
        m = new_manager()
        m.grant('u10', 'sbds', 'privacy_policy')
        m.revoke('u10', 'sbds', 'privacy_policy')
        records = m.get_status('u10')
        assert len(records) == 1
        assert records[0].granted is False


# ---------------------------------------------------------------------------
# 8. get_history（全件返す）
# ---------------------------------------------------------------------------

class TestGetHistory:
    def test_get_history_returns_all_changes(self):
        m = new_manager()
        m.grant('u11', 'sbds', 'privacy_policy')
        m.revoke('u11', 'sbds', 'privacy_policy')
        m.grant('u11', 'sbds', 'privacy_policy')
        history = m.get_history('u11')
        assert len(history) == 3

    def test_get_history_descending_order(self):
        m = new_manager()
        m.grant('u11', 'sbds', 'cookie_analytics')
        m.grant('u11', 'sbds', 'privacy_policy')
        history = m.get_history('u11')
        assert history[0].granted_at >= history[-1].granted_at

    def test_get_history_empty_for_unknown_user(self):
        m = new_manager()
        assert m.get_history('nobody') == []


# ---------------------------------------------------------------------------
# 9. バリデーションエラー
# ---------------------------------------------------------------------------

class TestValidation:
    def test_invalid_consent_type_raises_value_error(self):
        m = new_manager()
        with pytest.raises(ValueError, match='無効なconsent_type'):
            m.grant('u12', 'sbds', 'invalid_type')

    def test_invalid_service_raises_value_error(self):
        m = new_manager()
        with pytest.raises(ValueError, match='無効なservice'):
            m.grant('u12', 'invalid_svc', 'privacy_policy')

    def test_revoke_invalid_consent_type_raises(self):
        m = new_manager()
        with pytest.raises(ValueError, match='無効なconsent_type'):
            m.revoke('u12', 'sbds', 'bad_type')

    def test_revoke_invalid_service_raises(self):
        m = new_manager()
        with pytest.raises(ValueError, match='無効なservice'):
            m.revoke('u12', 'bad_svc', 'privacy_policy')


# ---------------------------------------------------------------------------
# 10. API テスト (stdlib http.server)
# ---------------------------------------------------------------------------

TEST_PORT = 0  # 0 = OS assigns a free port dynamically


@pytest.fixture(scope='module')
def api_server():
    """テスト用APIサーバーをスレッドで起動"""
    server = HTTPServer(('127.0.0.1', 0), ConsentAPIHandler)
    actual_port = server.server_address[1]
    # モジュールレベルに実際のポートを格納
    global _ACTUAL_TEST_PORT
    _ACTUAL_TEST_PORT = actual_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)  # サーバー起動待ち
    yield server
    server.shutdown()


_ACTUAL_TEST_PORT = 0


def _get(path: str) -> tuple:
    url = f'http://127.0.0.1:{_ACTUAL_TEST_PORT}{path}'
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def _post(path: str, data: dict) -> tuple:
    url = f'http://127.0.0.1:{_ACTUAL_TEST_PORT}{path}'
    body = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


class TestConsentAPI:
    def test_health(self, api_server):
        status, data = _get('/health')
        assert status == 200
        assert data['status'] == 'ok'

    def test_grant_success(self, api_server):
        status, data = _post('/api/v1/consent/grant', {
            'user_id': 'api_user1',
            'service': 'sbds',
            'consent_type': 'privacy_policy',
        })
        assert status == 200
        assert data['record']['granted'] is True

    def test_grant_with_ip_and_ua(self, api_server):
        status, data = _post('/api/v1/consent/grant', {
            'user_id': 'api_user2',
            'service': 'smartlife',
            'consent_type': 'terms_of_service',
            'ip_address': '1.2.3.4',
            'user_agent': 'TestAgent/1.0',
        })
        assert status == 200
        # ipはハッシュ化されていること
        assert data['record']['ip_address'] != '1.2.3.4'

    def test_grant_invalid_consent_type(self, api_server):
        status, data = _post('/api/v1/consent/grant', {
            'user_id': 'api_user3',
            'service': 'sbds',
            'consent_type': 'unknown_type',
        })
        assert status == 400
        assert 'error' in data

    def test_revoke_success(self, api_server):
        _post('/api/v1/consent/grant', {
            'user_id': 'api_user4',
            'service': 'sbds',
            'consent_type': 'cookie_analytics',
        })
        status, data = _post('/api/v1/consent/revoke', {
            'user_id': 'api_user4',
            'service': 'sbds',
            'consent_type': 'cookie_analytics',
        })
        assert status == 200
        assert data['record']['granted'] is False

    def test_status_endpoint(self, api_server):
        _post('/api/v1/consent/grant', {
            'user_id': 'api_user5',
            'service': 'travel',
            'consent_type': 'location_info_travel',
        })
        status, data = _get('/api/v1/consent/status?user_id=api_user5')
        assert status == 200
        assert len(data['records']) >= 1

    def test_status_with_service_filter(self, api_server):
        status, data = _get('/api/v1/consent/status?user_id=api_user5&service=travel')
        assert status == 200
        for rec in data['records']:
            assert rec['service'] == 'travel'

    def test_history_endpoint(self, api_server):
        _post('/api/v1/consent/grant', {
            'user_id': 'api_user6',
            'service': 'gov',
            'consent_type': 'gdpr_rights_acknowledged',
        })
        _post('/api/v1/consent/revoke', {
            'user_id': 'api_user6',
            'service': 'gov',
            'consent_type': 'gdpr_rights_acknowledged',
        })
        status, data = _get('/api/v1/consent/history?user_id=api_user6')
        assert status == 200
        assert len(data['records']) >= 2

    def test_status_missing_user_id(self, api_server):
        status, data = _get('/api/v1/consent/status')
        assert status == 400

    def test_history_missing_user_id(self, api_server):
        status, data = _get('/api/v1/consent/history')
        assert status == 400

    def test_not_found(self, api_server):
        status, data = _get('/api/v1/unknown')
        assert status == 404
