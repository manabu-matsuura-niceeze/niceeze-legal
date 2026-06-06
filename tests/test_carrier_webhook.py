"""テスト: キャリアWebhook受信処理 (carrier_webhook.py)"""
from __future__ import annotations

import hashlib
import hmac
import json
import pytest

from src.sbds.carrier_webhook import (
    CARRIER_SAGAWA,
    CARRIER_YAMATO,
    DELIVERY_STATUS_DELIVERED,
    DELIVERY_STATUS_IN_TRANSIT,
    CarrierWebhookProcessor,
    DeliveryRecord,
    LockerAssignment,
)


# ──────────────────────────────────────────
# ヘルパー
# ──────────────────────────────────────────

def _make_processor() -> CarrierWebhookProcessor:
    """デフォルトのモックシークレットを使うプロセッサ"""
    return CarrierWebhookProcessor()


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()


def _yamato_body(
    tracking_no: str = 'TRK-YMT-0001',
    status: str = DELIVERY_STATUS_IN_TRANSIT,
    building: str = 'BLDG01',
    floor: int = 3,
    room: str = '301',
    size: str = 'M',
) -> bytes:
    return json.dumps({
        'tracking_no': tracking_no,
        'status': status,
        'building': building,
        'floor': floor,
        'room': room,
        'size': size,
    }).encode('utf-8')


def _sagawa_body(
    tracking_no: str = 'TRK-SGW-0001',
    status: str = DELIVERY_STATUS_IN_TRANSIT,
    building: str = 'BLDG02',
    floor: int = 5,
    room: str = '501',
    size: str = 'L',
) -> bytes:
    return json.dumps({
        'tracking_no': tracking_no,
        'status': status,
        'building': building,
        'floor': floor,
        'room': room,
        'size': size,
    }).encode('utf-8')


YAMATO_SECRET = 'yamato-mock-secret'
SAGAWA_SECRET = 'sagawa-mock-secret'


# ──────────────────────────────────────────
# TestCarrierWebhook
# ──────────────────────────────────────────

class TestCarrierWebhook:

    def test_process_yamato_returns_delivery_record(self):
        proc = _make_processor()
        body = _yamato_body()
        sig = _sign(YAMATO_SECRET, body)
        record = proc.process_yamato(body, sig)
        assert isinstance(record, DeliveryRecord)
        assert record.carrier == CARRIER_YAMATO

    def test_tracking_number_is_sha256_hash(self):
        proc = _make_processor()
        raw_tracking = 'TRK-YMT-0001'
        body = _yamato_body(tracking_no=raw_tracking)
        sig = _sign(YAMATO_SECRET, body)
        record = proc.process_yamato(body, sig)
        assert record.tracking_number != raw_tracking
        expected_hash = hashlib.sha256(raw_tracking.encode('utf-8')).hexdigest()
        assert record.tracking_number == expected_hash

    def test_invalid_yamato_signature_raises_value_error(self):
        proc = _make_processor()
        body = _yamato_body()
        with pytest.raises(ValueError, match='YAMATO'):
            proc.process_yamato(body, 'bad-signature-xxx')

    def test_process_sagawa_returns_delivery_record(self):
        proc = _make_processor()
        body = _sagawa_body()
        sig = _sign(SAGAWA_SECRET, body)
        record = proc.process_sagawa(body, sig)
        assert isinstance(record, DeliveryRecord)
        assert record.carrier == CARRIER_SAGAWA

    def test_auto_assign_locker_returns_assignment(self):
        proc = _make_processor()
        body = _yamato_body(building='BLDG01', floor=3, size='M')
        sig = _sign(YAMATO_SECRET, body)
        record = proc.process_yamato(body, sig)
        assignments = proc.get_assignments()
        assert len(assignments) >= 1
        assignment = assignments[0]
        assert isinstance(assignment, LockerAssignment)

    def test_locker_id_format(self):
        proc = _make_processor()
        body = _yamato_body(building='BLDG01', floor=3, size='M')
        sig = _sign(YAMATO_SECRET, body)
        proc.process_yamato(body, sig)
        assignment = proc.get_assignments()[0]
        # Expected: BLDG01-F03-LM001
        assert assignment.locker_id == 'BLDG01-F03-LM001'

    def test_get_records_filter_yamato(self):
        proc = _make_processor()
        yb = _yamato_body()
        ys = _sign(YAMATO_SECRET, yb)
        proc.process_yamato(yb, ys)

        sb = _sagawa_body()
        ss = _sign(SAGAWA_SECRET, sb)
        proc.process_sagawa(sb, ss)

        records = proc.get_records(carrier=CARRIER_YAMATO)
        assert all(r.carrier == CARRIER_YAMATO for r in records)
        assert len(records) == 1

    def test_get_records_filter_sagawa(self):
        proc = _make_processor()
        yb = _yamato_body()
        ys = _sign(YAMATO_SECRET, yb)
        proc.process_yamato(yb, ys)

        sb = _sagawa_body()
        ss = _sign(SAGAWA_SECRET, sb)
        proc.process_sagawa(sb, ss)

        records = proc.get_records(carrier=CARRIER_SAGAWA)
        assert all(r.carrier == CARRIER_SAGAWA for r in records)
        assert len(records) == 1

    def test_get_records_no_filter_returns_all(self):
        proc = _make_processor()
        yb = _yamato_body()
        proc.process_yamato(yb, _sign(YAMATO_SECRET, yb))
        sb = _sagawa_body()
        proc.process_sagawa(sb, _sign(SAGAWA_SECRET, sb))

        records = proc.get_records()
        assert len(records) == 2

    def test_summary_keys(self):
        proc = _make_processor()
        s = proc.summary()
        for key in ('total', 'yamato', 'sagawa', 'assignments', 'status_counts'):
            assert key in s

    def test_locker_assignment_size_match_is_bool(self):
        proc = _make_processor()
        body = _yamato_body()
        sig = _sign(YAMATO_SECRET, body)
        proc.process_yamato(body, sig)
        assignment = proc.get_assignments()[0]
        assert isinstance(assignment.size_match, bool)

    def test_delivered_status_record(self):
        proc = _make_processor()
        body = _yamato_body(status=DELIVERY_STATUS_DELIVERED)
        sig = _sign(YAMATO_SECRET, body)
        record = proc.process_yamato(body, sig)
        assert record.status == DELIVERY_STATUS_DELIVERED
        assert record.delivered_at != ''


# ──────────────────────────────────────────
# TestE2EWebhookFlow
# ──────────────────────────────────────────

class TestE2EWebhookFlow:

    def test_webhook_to_locker_assignment_flow(self):
        """Webhook受信→ロッカー割当→記録保存の一連フロー"""
        proc = _make_processor()
        body = _yamato_body(tracking_no='TRK-E2E-001', building='BLDGX', floor=2, size='S')
        sig = _sign(YAMATO_SECRET, body)
        record = proc.process_yamato(body, sig)

        assert record.record_id != ''
        assert record.locker_id == 'BLDGX-F02-LS001'

        records = proc.get_records()
        assert any(r.record_id == record.record_id for r in records)

        assignments = proc.get_assignments()
        assert any(a.record_id == record.record_id for a in assignments)

    def test_both_carriers_integrated_list(self):
        """ヤマト・佐川の両キャリア統合一覧確認"""
        proc = _make_processor()
        yb = _yamato_body(tracking_no='TRK-Y-INT')
        proc.process_yamato(yb, _sign(YAMATO_SECRET, yb))

        sb = _sagawa_body(tracking_no='TRK-S-INT')
        proc.process_sagawa(sb, _sign(SAGAWA_SECRET, sb))

        all_records = proc.get_records()
        assert len(all_records) == 2
        carriers = {r.carrier for r in all_records}
        assert CARRIER_YAMATO in carriers
        assert CARRIER_SAGAWA in carriers

    def test_date_filter(self):
        """日付フィルタ（date_from/date_to）"""
        proc = _make_processor()
        yb = _yamato_body()
        proc.process_yamato(yb, _sign(YAMATO_SECRET, yb))

        # 未来の日付でフィルタ → 0件
        records_future = proc.get_records(date_from='2099-01-01')
        assert len(records_future) == 0

        # 過去の日付でフィルタ → 全件
        records_past = proc.get_records(date_from='2000-01-01')
        assert len(records_past) == 1

        # date_to で過去に絞る → 0件
        records_old = proc.get_records(date_to='2000-01-01')
        assert len(records_old) == 0

    def test_invalid_carrier_raises_value_error(self):
        """無効carrier でValueError"""
        proc = _make_processor()
        with pytest.raises(ValueError, match='carrier'):
            proc.get_records(carrier='fedex')

    def test_summary_contains_both_carrier_counts(self):
        """summary() に yamato/sagawa 両方のカウント含む"""
        proc = _make_processor()
        yb = _yamato_body()
        proc.process_yamato(yb, _sign(YAMATO_SECRET, yb))
        proc.process_yamato(yb, _sign(YAMATO_SECRET, yb))

        sb = _sagawa_body()
        proc.process_sagawa(sb, _sign(SAGAWA_SECRET, sb))

        s = proc.summary()
        assert s['yamato'] == 2
        assert s['sagawa'] == 1
        assert s['total'] == 3
