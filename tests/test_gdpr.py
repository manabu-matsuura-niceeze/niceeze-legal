# tests/test_gdpr.py
# TASK-PP2: EU/GDPR フラグ + GDPR権利API テスト

from __future__ import annotations

import io
import json
import threading
import time
from datetime import datetime, timezone, timedelta
from http.client import HTTPConnection

import pytest

from src.common.eu_countries import (
    is_gdpr_applicable,
    EU_MEMBER_STATES,
    EEA_ADDITIONAL,
    GDPR_APPLICABLE_COUNTRIES,
)
from src.common.gdpr_manager import GDPRManager, ResidentProfile, ProcessingRestrictionRequest
from src.common.gdpr_api import create_server, GDPRRequestHandler, GDPRManager as _ApiGDPRManager


# ---------------------------------------------------------------------------
# eu_countries テスト
# ---------------------------------------------------------------------------

class TestEuCountries:

    def test_de_is_gdpr(self):
        assert is_gdpr_applicable('DE') is True

    def test_fr_is_gdpr(self):
        assert is_gdpr_applicable('FR') is True

    def test_it_is_gdpr(self):
        assert is_gdpr_applicable('IT') is True

    def test_at_is_gdpr(self):
        assert is_gdpr_applicable('AT') is True

    def test_se_is_gdpr(self):
        assert is_gdpr_applicable('SE') is True

    def test_pl_is_gdpr(self):
        assert is_gdpr_applicable('PL') is True

    def test_nl_is_gdpr(self):
        assert is_gdpr_applicable('NL') is True

    def test_es_is_gdpr(self):
        assert is_gdpr_applicable('ES') is True

    def test_eea_is_is_gdpr(self):
        assert is_gdpr_applicable('IS') is True

    def test_eea_li_is_gdpr(self):
        assert is_gdpr_applicable('LI') is True

    def test_eea_no_is_gdpr(self):
        assert is_gdpr_applicable('NO') is True

    def test_jp_is_not_gdpr(self):
        assert is_gdpr_applicable('JP') is False

    def test_us_is_not_gdpr(self):
        assert is_gdpr_applicable('US') is False

    def test_kr_is_not_gdpr(self):
        assert is_gdpr_applicable('KR') is False

    def test_th_is_not_gdpr(self):
        assert is_gdpr_applicable('TH') is False

    def test_cn_is_not_gdpr(self):
        assert is_gdpr_applicable('CN') is False

    def test_lowercase_de_is_gdpr(self):
        """小文字でも正しく判定"""
        assert is_gdpr_applicable('de') is True

    def test_lowercase_jp_is_not_gdpr(self):
        assert is_gdpr_applicable('jp') is False

    def test_unknown_code_is_not_gdpr(self):
        assert is_gdpr_applicable('XX') is False

    def test_eu_member_states_count(self):
        assert len(EU_MEMBER_STATES) == 27

    def test_eea_additional_count(self):
        assert len(EEA_ADDITIONAL) == 3

    def test_gdpr_applicable_countries_union(self):
        assert GDPR_APPLICABLE_COUNTRIES == EU_MEMBER_STATES | EEA_ADDITIONAL

    def test_all_eu_members_applicable(self):
        for code in EU_MEMBER_STATES:
            assert is_gdpr_applicable(code), f"{code} should be GDPR applicable"

    def test_all_eea_additional_applicable(self):
        for code in EEA_ADDITIONAL:
            assert is_gdpr_applicable(code), f"{code} should be GDPR applicable"


# ---------------------------------------------------------------------------
# GDPRManager テスト
# ---------------------------------------------------------------------------

class TestGDPRManager:

    def setup_method(self):
        self.mgr = GDPRManager()

    def test_register_eu_user(self):
        profile = self.mgr.register_user('u1', 'DE')
        assert profile.gdpr_applicable is True
        assert profile.country_code == 'DE'

    def test_register_non_eu_user(self):
        profile = self.mgr.register_user('u2', 'JP')
        assert profile.gdpr_applicable is False

    def test_register_lowercase_country(self):
        profile = self.mgr.register_user('u3', 'fr')
        assert profile.gdpr_applicable is True
        assert profile.country_code == 'FR'

    def test_get_my_data_registered(self):
        self.mgr.register_user('u4', 'DE', {'email': 'test@example.com'})
        data = self.mgr.get_my_data('u4')
        assert data['user_id'] == 'u4'
        assert data['data_records']['email'] == 'test@example.com'

    def test_get_my_data_unregistered_raises(self):
        with pytest.raises(ValueError):
            self.mgr.get_my_data('nonexistent')

    def test_get_my_data_non_gdpr_user(self):
        """gdpr_applicable=False でも開示請求は可能"""
        self.mgr.register_user('u5', 'JP', {'name': 'TestUser'})
        data = self.mgr.get_my_data('u5')
        assert data['gdpr_applicable'] is False
        assert 'data_records' in data

    def test_delete_recent_user_anonymizes(self):
        """1年以内に登録されたユーザーは匿名化"""
        self.mgr.register_user('u6', 'DE', {'email': 'a@b.com'})
        result = self.mgr.delete_my_data('u6')
        assert 'u6' in result['anonymized']
        assert result['deleted'] == []
        # プロファイルはまだ存在するが匿名化済み
        profile = self.mgr._profiles['u6']
        assert profile.anonymized is True
        assert profile.data_records == {}

    def test_delete_old_user_fully_deletes(self):
        """1年超前に登録されたユーザーは完全削除"""
        self.mgr.register_user('u7', 'JP')
        # 作成日を2年前に書き換え
        old_date = (datetime.now(timezone.utc) - timedelta(days=730)).strftime('%Y-%m-%dT%H:%M:%SZ')
        self.mgr._profiles['u7'].created_at = old_date
        result = self.mgr.delete_my_data('u7')
        assert 'u7' in result['deleted']
        assert result['anonymized'] == []
        assert 'u7' not in self.mgr._profiles

    def test_delete_logs_to_deletion_log(self):
        self.mgr.register_user('u8', 'FR')
        self.mgr.delete_my_data('u8')
        assert len(self.mgr._deletion_log) == 1
        assert self.mgr._deletion_log[0]['user_id'] == 'u8'

    def test_delete_nonexistent_raises(self):
        with pytest.raises(ValueError):
            self.mgr.delete_my_data('ghost')

    def test_export_csv_gdpr_user(self):
        self.mgr.register_user('u9', 'IT', {'phone': '090-0000-0000'})
        csv_str = self.mgr.export_my_data_csv('u9')
        assert 'user_id' in csv_str
        assert 'u9' in csv_str

    def test_export_csv_non_gdpr_raises(self):
        self.mgr.register_user('u10', 'US')
        with pytest.raises(PermissionError):
            self.mgr.export_my_data_csv('u10')

    def test_request_restriction_valid(self):
        req = self.mgr.request_processing_restriction('u11', 'erasure', 'I want to be forgotten')
        assert isinstance(req, ProcessingRestrictionRequest)
        assert req.status == 'pending'
        assert req.restriction_type == 'erasure'
        assert len(req.request_id) == 12

    def test_request_restriction_invalid_type(self):
        with pytest.raises(ValueError):
            self.mgr.request_processing_restriction('u12', 'invalid_type', 'reason')

    def test_all_valid_restriction_types(self):
        valid_types = ['object_to_processing', 'restrict_processing', 'portability', 'erasure']
        for i, rt in enumerate(valid_types):
            req = self.mgr.request_processing_restriction(f'u_rt_{i}', rt, 'reason')
            assert req.restriction_type == rt

    def test_gdpr_notification_required_true(self):
        self.mgr.register_user('u13', 'BE')
        assert self.mgr.gdpr_notification_required('u13') is True

    def test_gdpr_notification_required_false(self):
        self.mgr.register_user('u14', 'KR')
        assert self.mgr.gdpr_notification_required('u14') is False

    def test_gdpr_notification_unknown_user(self):
        assert self.mgr.gdpr_notification_required('nobody') is False


# ---------------------------------------------------------------------------
# API テスト（HTTP）
# ---------------------------------------------------------------------------

import src.common.gdpr_api as _gdpr_api_module


@pytest.fixture(scope='module')
def api_server():
    """モジュールスコープでAPIサーバーを起動"""
    mgr = GDPRManager()
    # モジュールレベルの _manager を差し替え
    _gdpr_api_module._manager = mgr
    server = _gdpr_api_module.HTTPServer(('', 0), _gdpr_api_module.GDPRRequestHandler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever)
    t.daemon = True
    t.start()
    yield port, mgr
    server.shutdown()


def _get(port, path):
    conn = HTTPConnection('localhost', port)
    conn.request('GET', path)
    resp = conn.getresponse()
    body = resp.read()
    conn.close()
    return resp.status, json.loads(body)


def _post(port, path, data):
    conn = HTTPConnection('localhost', port)
    body = json.dumps(data).encode('utf-8')
    conn.request('POST', path, body=body, headers={'Content-Type': 'application/json', 'Content-Length': str(len(body))})
    resp = conn.getresponse()
    resp_body = resp.read()
    conn.close()
    return resp.status, json.loads(resp_body)


def _delete(port, path, data):
    conn = HTTPConnection('localhost', port)
    body = json.dumps(data).encode('utf-8')
    conn.request('DELETE', path, body=body, headers={'Content-Type': 'application/json', 'Content-Length': str(len(body))})
    resp = conn.getresponse()
    resp_body = resp.read()
    conn.close()
    return resp.status, json.loads(resp_body)


def _get_raw(port, path):
    conn = HTTPConnection('localhost', port)
    conn.request('GET', path)
    resp = conn.getresponse()
    body = resp.read()
    conn.close()
    return resp.status, body


class TestGDPRApi:

    def test_health(self, api_server):
        port, _ = api_server
        status, data = _get(port, '/health')
        assert status == 200
        assert data['status'] == 'ok'

    def test_register_eu_user_api(self, api_server):
        port, _ = api_server
        status, data = _post(port, '/api/v1/residents/register', {
            'user_id': 'api_eu_1',
            'country_code': 'DE',
        })
        assert status == 201
        assert data['gdpr_applicable'] is True
        assert data['gdpr_notification'] is True

    def test_register_non_eu_user_api(self, api_server):
        port, _ = api_server
        status, data = _post(port, '/api/v1/residents/register', {
            'user_id': 'api_jp_1',
            'country_code': 'JP',
        })
        assert status == 201
        assert data['gdpr_applicable'] is False
        assert 'gdpr_notification' not in data

    def test_register_missing_fields(self, api_server):
        port, _ = api_server
        status, data = _post(port, '/api/v1/residents/register', {'user_id': 'only_id'})
        assert status == 400

    def test_get_my_data_api(self, api_server):
        port, _ = api_server
        _post(port, '/api/v1/residents/register', {'user_id': 'api_data_1', 'country_code': 'FR'})
        status, data = _get(port, '/api/v1/privacy/my-data?user_id=api_data_1')
        assert status == 200
        assert data['user_id'] == 'api_data_1'

    def test_get_my_data_missing_user_id(self, api_server):
        port, _ = api_server
        status, data = _get(port, '/api/v1/privacy/my-data')
        assert status == 400

    def test_get_my_data_not_found(self, api_server):
        port, _ = api_server
        status, data = _get(port, '/api/v1/privacy/my-data?user_id=ghost_user')
        assert status == 404

    def test_delete_my_data_api(self, api_server):
        port, _ = api_server
        _post(port, '/api/v1/residents/register', {'user_id': 'api_del_1', 'country_code': 'IT'})
        status, data = _delete(port, '/api/v1/privacy/my-data', {'user_id': 'api_del_1'})
        assert status == 200
        assert 'message' in data

    def test_delete_my_data_missing_user_id(self, api_server):
        port, _ = api_server
        status, data = _delete(port, '/api/v1/privacy/my-data', {})
        assert status == 400

    def test_export_gdpr_user_api(self, api_server):
        port, _ = api_server
        _post(port, '/api/v1/residents/register', {'user_id': 'api_exp_1', 'country_code': 'NL', 'data_records': {'key': 'val'}})
        status, body = _get_raw(port, '/api/v1/privacy/my-data/export?user_id=api_exp_1')
        assert status == 200
        assert b'user_id' in body

    def test_export_non_gdpr_user_api(self, api_server):
        port, _ = api_server
        _post(port, '/api/v1/residents/register', {'user_id': 'api_exp_2', 'country_code': 'US'})
        status, data = _get(port, '/api/v1/privacy/my-data/export?user_id=api_exp_2')
        assert status == 403

    def test_processing_restriction_api(self, api_server):
        port, _ = api_server
        status, data = _post(port, '/api/v1/privacy/processing-restriction', {
            'user_id': 'api_pr_1',
            'restriction_type': 'erasure',
            'reason': 'want deletion',
        })
        assert status == 201
        assert data['status'] == 'pending'

    def test_processing_restriction_invalid_type_api(self, api_server):
        port, _ = api_server
        status, data = _post(port, '/api/v1/privacy/processing-restriction', {
            'user_id': 'api_pr_2',
            'restriction_type': 'bad_type',
            'reason': 'reason',
        })
        assert status == 400

    def test_not_found_route(self, api_server):
        port, _ = api_server
        status, data = _get(port, '/api/v1/unknown')
        assert status == 404
