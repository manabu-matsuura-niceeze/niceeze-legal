"""
TASK-PP3: WebhookReceiverテスト
プライバシーポリシー準拠検証・25件以上のテストケース
"""
from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from src.sbds.webhook_receiver import (
    DeliveryRecord,
    WebhookProcessingLog,
    WebhookReceiver,
    ResidentStub,
    SAMPLE_YAMATO_PAYLOAD,
)


# ──────────────────────────────────────────
# ヘルパー
# ──────────────────────────────────────────

def _make_signature(payload: dict, secret: str) -> str:
    """テスト用: 正しいHMAC-SHA256署名を生成"""
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode('utf-8')
    return hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()


SECRET = 'test-secret-key'

PAYLOAD_SINGLE = {
    "carrier": "yamato",
    "deliveries": [
        {
            "tracking_number": "1234-5678-9012",
            "recipient_name": "田中花子",
            "building_code": "BLDG-A",
            "floor": 3,
            "size": "m",
        }
    ]
}

PAYLOAD_MULTI = {
    "carrier": "yamato",
    "deliveries": [
        {
            "tracking_number": "AAA-001",
            "recipient_name": "山田太郎",
            "building_code": "BLDG-A",
            "floor": 3,
            "size": "s",
        },
        {
            "tracking_number": "BBB-002",
            "recipient_name": "鈴木次郎",
            "building_code": "BLDG-B",
            "floor": 5,
            "size": "l",
        },
        {
            "tracking_number": "CCC-003",
            "recipient_name": "佐藤三郎",
            "building_code": "BLDG-Z",  # 未登録
            "floor": 9,
            "size": "m",
        },
    ]
}

PAYLOAD_NO_MATCH = {
    "carrier": "sagawa",
    "deliveries": [
        {
            "tracking_number": "9999-0000",
            "recipient_name": "不明太郎",
            "building_code": "UNKNOWN",
            "floor": 99,
            "size": "s",
        }
    ]
}

PAYLOAD_EMPTY = {
    "carrier": "yamato",
    "deliveries": []
}


def _receiver_with_resident() -> tuple[WebhookReceiver, ResidentStub]:
    """BLDG-A フロア3 の居住者が登録済みのレシーバーを返す"""
    r = WebhookReceiver()
    stub = r.register_resident("R-101", "BLDG-A", 3)
    return r, stub


# ──────────────────────────────────────────
# 1. 正常マッチング: DeliveryRecordが作成される
# ──────────────────────────────────────────

def test_normal_match_creates_delivery_record():
    receiver, _ = _receiver_with_resident()
    sig = _make_signature(PAYLOAD_SINGLE, SECRET)
    receiver.process_webhook("yamato", PAYLOAD_SINGLE, sig, SECRET)
    records = receiver.get_delivery_records()
    assert len(records) == 1


def test_normal_match_record_is_delivery_record_type():
    receiver, _ = _receiver_with_resident()
    sig = _make_signature(PAYLOAD_SINGLE, SECRET)
    receiver.process_webhook("yamato", PAYLOAD_SINGLE, sig, SECRET)
    records = receiver.get_delivery_records()
    assert isinstance(records[0], DeliveryRecord)


def test_normal_match_record_has_correct_building_code():
    receiver, _ = _receiver_with_resident()
    sig = _make_signature(PAYLOAD_SINGLE, SECRET)
    receiver.process_webhook("yamato", PAYLOAD_SINGLE, sig, SECRET)
    record = receiver.get_delivery_records()[0]
    assert record.building_code == "BLDG-A"


def test_normal_match_record_has_correct_floor():
    receiver, _ = _receiver_with_resident()
    sig = _make_signature(PAYLOAD_SINGLE, SECRET)
    receiver.process_webhook("yamato", PAYLOAD_SINGLE, sig, SECRET)
    record = receiver.get_delivery_records()[0]
    assert record.floor == 3


def test_normal_match_record_has_correct_carrier():
    receiver, _ = _receiver_with_resident()
    sig = _make_signature(PAYLOAD_SINGLE, SECRET)
    receiver.process_webhook("yamato", PAYLOAD_SINGLE, sig, SECRET)
    record = receiver.get_delivery_records()[0]
    assert record.carrier == "yamato"


def test_normal_match_record_status_is_matched():
    receiver, _ = _receiver_with_resident()
    sig = _make_signature(PAYLOAD_SINGLE, SECRET)
    receiver.process_webhook("yamato", PAYLOAD_SINGLE, sig, SECRET)
    record = receiver.get_delivery_records()[0]
    assert record.status == "matched"


# ──────────────────────────────────────────
# 2. 正常マッチング後: raw_data_retained=False
# ──────────────────────────────────────────

def test_raw_data_retained_false_on_match():
    receiver, _ = _receiver_with_resident()
    sig = _make_signature(PAYLOAD_SINGLE, SECRET)
    result = receiver.process_webhook("yamato", PAYLOAD_SINGLE, sig, SECRET)
    assert result['raw_data_retained'] is False


def test_raw_data_retained_false_on_no_match():
    receiver = WebhookReceiver()  # 居住者なし
    sig = _make_signature(PAYLOAD_NO_MATCH, SECRET)
    result = receiver.process_webhook("sagawa", PAYLOAD_NO_MATCH, sig, SECRET)
    assert result['raw_data_retained'] is False


def test_has_raw_data_in_memory_always_false():
    receiver, _ = _receiver_with_resident()
    sig = _make_signature(PAYLOAD_SINGLE, SECRET)
    receiver.process_webhook("yamato", PAYLOAD_SINGLE, sig, SECRET)
    assert receiver.has_raw_data_in_memory() is False


def test_has_raw_data_in_memory_false_before_any_call():
    receiver = WebhookReceiver()
    assert receiver.has_raw_data_in_memory() is False


# ──────────────────────────────────────────
# 3. DeliveryRecordにtracking_numberや氏名が含まれない（PII最小化）
# ──────────────────────────────────────────

def test_record_has_no_tracking_number_field():
    receiver, _ = _receiver_with_resident()
    sig = _make_signature(PAYLOAD_SINGLE, SECRET)
    receiver.process_webhook("yamato", PAYLOAD_SINGLE, sig, SECRET)
    record = receiver.get_delivery_records()[0]
    assert not hasattr(record, 'tracking_number')


def test_record_has_no_recipient_name_field():
    receiver, _ = _receiver_with_resident()
    sig = _make_signature(PAYLOAD_SINGLE, SECRET)
    receiver.process_webhook("yamato", PAYLOAD_SINGLE, sig, SECRET)
    record = receiver.get_delivery_records()[0]
    assert not hasattr(record, 'recipient_name')


def test_record_has_no_phone_field():
    receiver, _ = _receiver_with_resident()
    sig = _make_signature(PAYLOAD_SINGLE, SECRET)
    receiver.process_webhook("yamato", PAYLOAD_SINGLE, sig, SECRET)
    record = receiver.get_delivery_records()[0]
    assert not hasattr(record, 'phone')


def test_record_id_not_equal_to_raw_tracking_number():
    receiver, _ = _receiver_with_resident()
    sig = _make_signature(PAYLOAD_SINGLE, SECRET)
    receiver.process_webhook("yamato", PAYLOAD_SINGLE, sig, SECRET)
    record = receiver.get_delivery_records()[0]
    assert record.record_id != "1234-5678-9012"


def test_record_id_is_hex_hash():
    """record_idがSHA-256ハッシュ(先頭12文字の16進数)であることを確認"""
    receiver, _ = _receiver_with_resident()
    sig = _make_signature(PAYLOAD_SINGLE, SECRET)
    receiver.process_webhook("yamato", PAYLOAD_SINGLE, sig, SECRET)
    record = receiver.get_delivery_records()[0]
    assert len(record.record_id) == 12
    int(record.record_id, 16)  # 16進数として解釈できること


# ──────────────────────────────────────────
# 4. マッチング失敗: エラーコード ROOM_NOT_FOUND のみ
# ──────────────────────────────────────────

def test_no_match_returns_room_not_found_error_code():
    receiver = WebhookReceiver()
    sig = _make_signature(PAYLOAD_NO_MATCH, SECRET)
    result = receiver.process_webhook("sagawa", PAYLOAD_NO_MATCH, sig, SECRET)
    assert 'ROOM_NOT_FOUND' in result['error_codes']


def test_no_match_failed_count_is_one():
    receiver = WebhookReceiver()
    sig = _make_signature(PAYLOAD_NO_MATCH, SECRET)
    result = receiver.process_webhook("sagawa", PAYLOAD_NO_MATCH, sig, SECRET)
    assert result['failed'] == 1


def test_no_match_matched_count_is_zero():
    receiver = WebhookReceiver()
    sig = _make_signature(PAYLOAD_NO_MATCH, SECRET)
    result = receiver.process_webhook("sagawa", PAYLOAD_NO_MATCH, sig, SECRET)
    assert result['matched'] == 0


def test_no_match_delivery_records_not_created():
    """マッチング失敗時はdelivery_recordsが増えない"""
    receiver = WebhookReceiver()
    sig = _make_signature(PAYLOAD_NO_MATCH, SECRET)
    receiver.process_webhook("sagawa", PAYLOAD_NO_MATCH, sig, SECRET)
    assert len(receiver.get_delivery_records()) == 0


def test_no_match_error_codes_contain_no_pii():
    """エラーコードにPIIが含まれないこと"""
    receiver = WebhookReceiver()
    sig = _make_signature(PAYLOAD_NO_MATCH, SECRET)
    result = receiver.process_webhook("sagawa", PAYLOAD_NO_MATCH, sig, SECRET)
    for code in result['error_codes']:
        assert "不明太郎" not in code
        assert "9999-0000" not in code


# ──────────────────────────────────────────
# 5. 署名検証: 無効署名でValueError
# ──────────────────────────────────────────

def test_invalid_signature_raises_value_error():
    receiver, _ = _receiver_with_resident()
    with pytest.raises(ValueError):
        receiver.process_webhook("yamato", PAYLOAD_SINGLE, "invalid-signature", SECRET)


def test_wrong_secret_raises_value_error():
    receiver, _ = _receiver_with_resident()
    sig = _make_signature(PAYLOAD_SINGLE, "wrong-secret")
    with pytest.raises(ValueError):
        receiver.process_webhook("yamato", PAYLOAD_SINGLE, sig, SECRET)


def test_invalid_signature_no_record_created():
    """署名検証失敗時はレコードが作成されない"""
    receiver, _ = _receiver_with_resident()
    with pytest.raises(ValueError):
        receiver.process_webhook("yamato", PAYLOAD_SINGLE, "bad-sig", SECRET)
    assert len(receiver.get_delivery_records()) == 0


# ──────────────────────────────────────────
# 6. WebhookProcessingLog: カウントが正確
# ──────────────────────────────────────────

def test_processing_log_created_on_success():
    receiver, _ = _receiver_with_resident()
    sig = _make_signature(PAYLOAD_SINGLE, SECRET)
    receiver.process_webhook("yamato", PAYLOAD_SINGLE, sig, SECRET)
    logs = receiver.get_processing_logs()
    assert len(logs) == 1


def test_processing_log_is_correct_type():
    receiver, _ = _receiver_with_resident()
    sig = _make_signature(PAYLOAD_SINGLE, SECRET)
    receiver.process_webhook("yamato", PAYLOAD_SINGLE, sig, SECRET)
    assert isinstance(receiver.get_processing_logs()[0], WebhookProcessingLog)


def test_processing_log_total_count_correct():
    receiver, _ = _receiver_with_resident()
    sig = _make_signature(PAYLOAD_SINGLE, SECRET)
    receiver.process_webhook("yamato", PAYLOAD_SINGLE, sig, SECRET)
    log = receiver.get_processing_logs()[0]
    assert log.total_count == 1


def test_processing_log_success_count_correct():
    receiver, _ = _receiver_with_resident()
    sig = _make_signature(PAYLOAD_SINGLE, SECRET)
    receiver.process_webhook("yamato", PAYLOAD_SINGLE, sig, SECRET)
    log = receiver.get_processing_logs()[0]
    assert log.success_count == 1


def test_processing_log_failure_count_zero_on_full_match():
    receiver, _ = _receiver_with_resident()
    sig = _make_signature(PAYLOAD_SINGLE, SECRET)
    receiver.process_webhook("yamato", PAYLOAD_SINGLE, sig, SECRET)
    log = receiver.get_processing_logs()[0]
    assert log.failure_count == 0


def test_processing_log_carrier_set():
    receiver, _ = _receiver_with_resident()
    sig = _make_signature(PAYLOAD_SINGLE, SECRET)
    receiver.process_webhook("yamato", PAYLOAD_SINGLE, sig, SECRET)
    log = receiver.get_processing_logs()[0]
    assert log.carrier == "yamato"


# ──────────────────────────────────────────
# 7. 混在ケース（一部マッチング成功・一部失敗）
# ──────────────────────────────────────────

def test_mixed_match_success_count():
    """2成功1失敗の混在ケース"""
    receiver = WebhookReceiver()
    receiver.register_resident("R-101", "BLDG-A", 3)
    receiver.register_resident("R-501", "BLDG-B", 5)
    # BLDG-Z フロア9 は未登録
    sig = _make_signature(PAYLOAD_MULTI, SECRET)
    result = receiver.process_webhook("yamato", PAYLOAD_MULTI, sig, SECRET)
    assert result['matched'] == 2


def test_mixed_match_failed_count():
    receiver = WebhookReceiver()
    receiver.register_resident("R-101", "BLDG-A", 3)
    receiver.register_resident("R-501", "BLDG-B", 5)
    sig = _make_signature(PAYLOAD_MULTI, SECRET)
    result = receiver.process_webhook("yamato", PAYLOAD_MULTI, sig, SECRET)
    assert result['failed'] == 1


def test_mixed_match_delivery_records_count():
    receiver = WebhookReceiver()
    receiver.register_resident("R-101", "BLDG-A", 3)
    receiver.register_resident("R-501", "BLDG-B", 5)
    sig = _make_signature(PAYLOAD_MULTI, SECRET)
    receiver.process_webhook("yamato", PAYLOAD_MULTI, sig, SECRET)
    assert len(receiver.get_delivery_records()) == 2


def test_mixed_match_processing_log_total_count():
    receiver = WebhookReceiver()
    receiver.register_resident("R-101", "BLDG-A", 3)
    receiver.register_resident("R-501", "BLDG-B", 5)
    sig = _make_signature(PAYLOAD_MULTI, SECRET)
    receiver.process_webhook("yamato", PAYLOAD_MULTI, sig, SECRET)
    log = receiver.get_processing_logs()[0]
    assert log.total_count == 3


def test_mixed_match_error_codes_has_one_room_not_found():
    receiver = WebhookReceiver()
    receiver.register_resident("R-101", "BLDG-A", 3)
    receiver.register_resident("R-501", "BLDG-B", 5)
    sig = _make_signature(PAYLOAD_MULTI, SECRET)
    result = receiver.process_webhook("yamato", PAYLOAD_MULTI, sig, SECRET)
    assert result['error_codes'].count('ROOM_NOT_FOUND') == 1


def test_mixed_match_raw_data_retained_false():
    receiver = WebhookReceiver()
    receiver.register_resident("R-101", "BLDG-A", 3)
    sig = _make_signature(PAYLOAD_MULTI, SECRET)
    result = receiver.process_webhook("yamato", PAYLOAD_MULTI, sig, SECRET)
    assert result['raw_data_retained'] is False


# ──────────────────────────────────────────
# 8. 追加: 空ペイロード・居住者登録・複数ログ
# ──────────────────────────────────────────

def test_empty_deliveries_returns_zero_counts():
    receiver = WebhookReceiver()
    sig = _make_signature(PAYLOAD_EMPTY, SECRET)
    result = receiver.process_webhook("yamato", PAYLOAD_EMPTY, sig, SECRET)
    assert result['matched'] == 0
    assert result['failed'] == 0


def test_empty_deliveries_log_total_count_zero():
    receiver = WebhookReceiver()
    sig = _make_signature(PAYLOAD_EMPTY, SECRET)
    receiver.process_webhook("yamato", PAYLOAD_EMPTY, sig, SECRET)
    log = receiver.get_processing_logs()[0]
    assert log.total_count == 0


def test_register_resident_returns_resident_stub():
    receiver = WebhookReceiver()
    stub = receiver.register_resident("R-001", "BLDG-X", 2)
    assert isinstance(stub, ResidentStub)
    assert stub.room_id == "R-001"
    assert stub.building_code == "BLDG-X"
    assert stub.floor == 2
    assert stub.is_active is True


def test_multiple_webhooks_accumulate_logs():
    receiver, _ = _receiver_with_resident()
    sig1 = _make_signature(PAYLOAD_SINGLE, SECRET)
    sig2 = _make_signature(PAYLOAD_EMPTY, SECRET)
    receiver.process_webhook("yamato", PAYLOAD_SINGLE, sig1, SECRET)
    receiver.process_webhook("yamato", PAYLOAD_EMPTY, sig2, SECRET)
    assert len(receiver.get_processing_logs()) == 2


def test_delivery_record_has_locker_id():
    receiver, _ = _receiver_with_resident()
    sig = _make_signature(PAYLOAD_SINGLE, SECRET)
    receiver.process_webhook("yamato", PAYLOAD_SINGLE, sig, SECRET)
    record = receiver.get_delivery_records()[0]
    assert record.locker_id != ''


def test_sample_yamato_payload_structure():
    """SAMPLE_YAMATO_PAYLOADが正しい形式であることを確認"""
    assert 'carrier' in SAMPLE_YAMATO_PAYLOAD
    assert 'deliveries' in SAMPLE_YAMATO_PAYLOAD
    assert len(SAMPLE_YAMATO_PAYLOAD['deliveries']) > 0
    delivery = SAMPLE_YAMATO_PAYLOAD['deliveries'][0]
    assert 'building_code' in delivery
    assert 'floor' in delivery
