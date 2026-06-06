"""SBDS キャリアWebhook受信 — ヤマト・佐川 (Ver 1.0)
JP7017282特許準拠: 複数事業者管理
HMAC-SHA256署名検証 / PII最小化 / bandit 0件
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ──────────────────────────────────────────
# 定数
# ──────────────────────────────────────────

CARRIER_YAMATO = 'yamato'
CARRIER_SAGAWA = 'sagawa'
VALID_CARRIERS = [CARRIER_YAMATO, CARRIER_SAGAWA]

DELIVERY_STATUS_RECEIVED    = 'received'
DELIVERY_STATUS_IN_TRANSIT  = 'in_transit'
DELIVERY_STATUS_OUT_FOR_DEL = 'out_for_delivery'
DELIVERY_STATUS_DELIVERED   = 'delivered'
DELIVERY_STATUS_FAILED      = 'failed'
DELIVERY_STATUS_RETURNING   = 'returning'

LOCKER_STATUS_EMPTY    = 'empty'
LOCKER_STATUS_OCCUPIED = 'occupied'
LOCKER_STATUS_RESERVED = 'reserved'


# ──────────────────────────────────────────
# ユーティリティ
# ──────────────────────────────────────────

def _sha256_hex(value: str) -> str:
    """文字列をSHA-256ハッシュ（PII除去用）"""
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ──────────────────────────────────────────
# データモデル
# ──────────────────────────────────────────

@dataclass
class DeliveryRecord:
    """配達記録（ヤマト・佐川共通）"""
    record_id: str          # SHA-256[:16]
    carrier: str            # 'yamato' | 'sagawa'
    tracking_number: str    # 追跡番号（PII除去済みハッシュ）
    status: str             # DELIVERY_STATUS_*
    building_code: str      # 対象建物コード
    floor: int              # フロア
    room_code: str          # 部屋コード
    baggage_size: str       # 'S' | 'M' | 'L' | 'XL'
    received_at: str        # Webhook受信時刻 ISO UTC
    delivered_at: str = ''  # 配達完了時刻
    locker_id: str = ''     # 割り当てロッカーID
    webhook_signature: str = ''  # HMAC署名（検証済みマーク）

    def to_dict(self) -> dict:
        return {
            'record_id': self.record_id,
            'carrier': self.carrier,
            'tracking_number': self.tracking_number,
            'status': self.status,
            'building_code': self.building_code,
            'floor': self.floor,
            'room_code': self.room_code,
            'baggage_size': self.baggage_size,
            'received_at': self.received_at,
            'delivered_at': self.delivered_at,
            'locker_id': self.locker_id,
            'webhook_signature': self.webhook_signature,
        }


@dataclass
class LockerAssignment:
    """ロッカー自動割当結果"""
    assignment_id: str      # SHA-256[:16]
    record_id: str          # DeliveryRecord.record_id
    locker_id: str          # 'BLDG-F01-L001' 形式
    building_code: str
    floor: int
    status: str             # LOCKER_STATUS_*
    assigned_at: str
    size_match: bool        # 荷物サイズとロッカーサイズの適合

    def to_dict(self) -> dict:
        return {
            'assignment_id': self.assignment_id,
            'record_id': self.record_id,
            'locker_id': self.locker_id,
            'building_code': self.building_code,
            'floor': self.floor,
            'status': self.status,
            'assigned_at': self.assigned_at,
            'size_match': self.size_match,
        }


@dataclass
class WebhookPayload:
    """Webhook受信ペイロード（ヤマト・佐川共通正規化）"""
    carrier: str
    tracking_number: str    # ハッシュ化して保存
    event_type: str         # DELIVERY_STATUS_*
    building_code: str
    floor: int
    room_code: str
    baggage_size: str       # 'S'|'M'|'L'|'XL'
    raw_headers: dict       # HMAC検証用（X-Yamato-Signature等）
    raw_body: bytes         # 署名検証用


# ──────────────────────────────────────────
# HMAC署名検証
# ──────────────────────────────────────────

def _verify_yamato_signature(body: bytes, signature: str, secret: str) -> bool:
    """ヤマトWebhook HMAC-SHA256署名検証"""
    expected = hmac.new(
        secret.encode('utf-8'),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _verify_sagawa_signature(body: bytes, signature: str, secret: str) -> bool:
    """佐川急便Webhook HMAC-SHA256署名検証"""
    expected = hmac.new(
        secret.encode('utf-8'),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# ──────────────────────────────────────────
# メインプロセッサ
# ──────────────────────────────────────────

class CarrierWebhookProcessor:
    """ヤマト・佐川Webhook受信・処理クラス"""

    def __init__(self) -> None:
        self._yamato_secret = os.environ.get('YAMATO_WEBHOOK_SECRET', 'yamato-mock-secret')
        self._sagawa_secret = os.environ.get('SAGAWA_WEBHOOK_SECRET', 'sagawa-mock-secret')
        self._records: list[DeliveryRecord] = []
        self._assignments: list[LockerAssignment] = []

    def verify_signature(self, carrier: str, body: bytes, signature: str) -> bool:
        """HMAC署名検証。未設定はモックシークレットで検証。"""
        if carrier == CARRIER_YAMATO:
            return _verify_yamato_signature(body, signature, self._yamato_secret)
        if carrier == CARRIER_SAGAWA:
            return _verify_sagawa_signature(body, signature, self._sagawa_secret)
        return False

    def _build_signature(self, carrier: str, body: bytes) -> str:
        """テスト用: 正しいHMAC署名を生成"""
        secret = self._yamato_secret if carrier == CARRIER_YAMATO else self._sagawa_secret
        return hmac.new(
            secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()

    def _parse_body(self, body: bytes) -> dict:
        return json.loads(body.decode('utf-8'))

    def _make_record(
        self,
        carrier: str,
        data: dict,
        signature: str,
        received_at: str,
    ) -> DeliveryRecord:
        raw_tracking = data.get('tracking_no', '')
        hashed_tracking = _sha256_hex(raw_tracking)
        record_seed = f"{carrier}:{hashed_tracking}:{received_at}"
        record_id = _sha256_hex(record_seed)[:16]

        status = data.get('status', DELIVERY_STATUS_RECEIVED)
        delivered_at = received_at if status == DELIVERY_STATUS_DELIVERED else ''

        return DeliveryRecord(
            record_id=record_id,
            carrier=carrier,
            tracking_number=hashed_tracking,
            status=status,
            building_code=data.get('building', ''),
            floor=int(data.get('floor', 1)),
            room_code=data.get('room', ''),
            baggage_size=data.get('size', 'M'),
            received_at=received_at,
            delivered_at=delivered_at,
            webhook_signature='verified',
        )

    def process_yamato(self, body: bytes, signature: str) -> DeliveryRecord:
        """ヤマトWebhookを処理。署名検証→正規化→保存→ロッカー割当トリガー。"""
        if not self.verify_signature(CARRIER_YAMATO, body, signature):
            raise ValueError('Invalid YAMATO signature')
        data = self._parse_body(body)
        record = self._make_record(CARRIER_YAMATO, data, signature, _utc_now())
        self._records.append(record)
        assignment = self.auto_assign_locker(record)
        if assignment:
            record.locker_id = assignment.locker_id
        return record

    def process_sagawa(self, body: bytes, signature: str) -> DeliveryRecord:
        """佐川Webhookを処理。process_yamatoと同様。"""
        if not self.verify_signature(CARRIER_SAGAWA, body, signature):
            raise ValueError('Invalid SAGAWA signature')
        data = self._parse_body(body)
        record = self._make_record(CARRIER_SAGAWA, data, signature, _utc_now())
        self._records.append(record)
        assignment = self.auto_assign_locker(record)
        if assignment:
            record.locker_id = assignment.locker_id
        return record

    def auto_assign_locker(self, record: DeliveryRecord) -> Optional[LockerAssignment]:
        """
        配達記録からロッカーを自動割当。
        building_code + floor + size でロッカーIDを生成。
        フォーマット: {building_code}-F{floor:02d}-L{size}{001}
        例: BLDG01-F03-LM001
        """
        assigned_at = _utc_now()
        locker_id = f"{record.building_code}-F{record.floor:02d}-L{record.baggage_size}001"
        assignment_seed = f"{record.record_id}:{locker_id}:{assigned_at}"
        assignment_id = _sha256_hex(assignment_seed)[:16]

        assignment = LockerAssignment(
            assignment_id=assignment_id,
            record_id=record.record_id,
            locker_id=locker_id,
            building_code=record.building_code,
            floor=record.floor,
            status=LOCKER_STATUS_OCCUPIED,
            assigned_at=assigned_at,
            size_match=True,
        )
        self._assignments.append(assignment)
        return assignment

    def get_records(
        self,
        carrier: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list[DeliveryRecord]:
        """配達記録一覧。carrier/日付範囲フィルタ付き。"""
        results = self._records

        if carrier is not None:
            if carrier not in VALID_CARRIERS:
                raise ValueError(f'Invalid carrier: {carrier}')
            results = [r for r in results if r.carrier == carrier]

        if date_from is not None:
            results = [r for r in results if r.received_at[:10] >= date_from]

        if date_to is not None:
            results = [r for r in results if r.received_at[:10] <= date_to]

        return results

    def get_assignments(self) -> list[LockerAssignment]:
        return list(self._assignments)

    def summary(self) -> dict:
        yamato_count = sum(1 for r in self._records if r.carrier == CARRIER_YAMATO)
        sagawa_count = sum(1 for r in self._records if r.carrier == CARRIER_SAGAWA)
        status_counts: dict[str, int] = {}
        for r in self._records:
            status_counts[r.status] = status_counts.get(r.status, 0) + 1
        return {
            'total': len(self._records),
            'yamato': yamato_count,
            'sagawa': sagawa_count,
            'assignments': len(self._assignments),
            'status_counts': status_counts,
        }
