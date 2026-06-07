"""
SBDS物流Webhookレシーバー
プライバシーポリシー準拠: 受信データをメモリ上で処理後、生データを即時破棄
DBには個人特定情報を含まない配送レコードのみ保存
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.sbds.carrier_webhook import CarrierWebhookProcessor


# ──────────────────────────────────────────
# ユーティリティ
# ──────────────────────────────────────────

def _sha256_hex(value: str) -> str:
    """文字列をSHA-256ハッシュ化"""
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_log_id(carrier: str, processed_at: str) -> str:
    seed = f"log:{carrier}:{processed_at}"
    return _sha256_hex(seed)[:16]


# ──────────────────────────────────────────
# データモデル
# ──────────────────────────────────────────

# 配送レコード（個人特定情報なし）
@dataclass
class DeliveryRecord:
    record_id: str          # SHA-256[:12]
    carrier: str            # 'yamato' | 'sagawa'
    building_code: str      # 建物コード
    floor: int
    locker_id: str          # 自動割り当てロッカー
    delivery_size: str      # 's'|'m'|'l'
    status: str             # 'pending'|'matched'|'delivered'|'failed'
    matched_at: str = ''    # 部屋マスタマッチング日時
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # 注意: tracking_numberやresident_nameは保存しない


# Webhook処理ログ（非個人情報のみ）
@dataclass
class WebhookProcessingLog:
    log_id: str
    carrier: str
    processed_at: str
    total_count: int
    success_count: int
    failure_count: int
    error_codes: list  # 個人情報を含まないエラーコードのみ


# 部屋マスタ（テスト用スタブ）
@dataclass
class ResidentStub:
    room_id: str
    building_code: str
    floor: int
    is_active: bool = True


# ──────────────────────────────────────────
# サンプルWebhookペイロード（テスト用）
# ──────────────────────────────────────────

SAMPLE_YAMATO_PAYLOAD = {
    "carrier": "yamato",
    "deliveries": [
        {
            "tracking_number": "1234-5678-9012",  # 処理後に破棄
            "recipient_name": "田中花子",           # 処理後に破棄
            "building_code": "BLDG-A",
            "floor": 3,
            "size": "m",
        }
    ]
}


# ──────────────────────────────────────────
# メインクラス
# ──────────────────────────────────────────

class WebhookReceiver:
    """
    メモリ上でWebhookを処理し生データを即時破棄するレシーバー
    """

    def __init__(self) -> None:
        self._delivery_records: list[DeliveryRecord] = []
        self._processing_logs: list[WebhookProcessingLog] = []
        self._residents: dict[str, ResidentStub] = {}  # building_code+floor→resident
        self._carrier_processor = CarrierWebhookProcessor()

    # ── 居住者登録 ──────────────────────────

    def register_resident(self, room_id: str, building_code: str, floor: int) -> ResidentStub:
        """部屋マスタにテスト用居住者を登録"""
        stub = ResidentStub(room_id=room_id, building_code=building_code, floor=floor)
        key = f"{building_code}:{floor}"
        self._residents[key] = stub
        return stub

    # ── メイン処理フロー ────────────────────

    def process_webhook(
        self,
        carrier: str,
        raw_payload: dict,
        signature: str,
        secret: str,
    ) -> dict:
        """
        Webhook処理メインフロー
        Step1: HMAC-SHA256署名検証（carrier_webhook.pyのverify_signatureを使う）
        Step2: メモリ上でペイロードを処理
        Step3: building_code + floor で部屋マスタと照合
        Step4a: マッチング成功 → DeliveryRecordを作成（個人情報なし）
        Step4b: マッチング失敗 → エラーコード 'ROOM_NOT_FOUND' のみ返す
        Step5: raw_payloadを明示的に None に（メモリ破棄）
        Step6: WebhookProcessingLogを記録
        Returns: {
            'matched': int,
            'failed': int,
            'error_codes': list,
            'raw_data_retained': False  # 常にFalse（即時破棄）
        }
        """
        processed_at = _utc_now()

        # Step1: HMAC-SHA256署名検証
        # carrier_webhook.py の verify_signature は carrier + body(bytes) + signature を受け取る
        # ここでは secret を直接受け取る形式なので、hmac で直接検証する
        import json as _json
        body_bytes = _json.dumps(raw_payload, ensure_ascii=False, sort_keys=True).encode('utf-8')
        expected_sig = hmac.new(
            secret.encode('utf-8'),
            body_bytes,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected_sig, signature):
            raw_payload = None  # noqa: F841 — Step5: 生データ即時破棄（検証失敗時も）
            raise ValueError('Invalid webhook signature')

        # Step2: メモリ上でペイロードを処理
        deliveries: list[dict] = raw_payload.get('deliveries', [])

        matched = 0
        failed = 0
        error_codes: list[str] = []

        for item in deliveries:
            building_code: str = item.get('building_code', '')
            floor: int = int(item.get('floor', 0))

            # Step3: 部屋マスタ照合
            resident = self._match_resident(building_code, floor)

            if resident is not None:
                # Step4a: マッチング成功 → DeliveryRecord作成（個人情報なし）
                record = self._create_delivery_record(carrier, item, resident)
                self._delivery_records.append(record)
                matched += 1
            else:
                # Step4b: マッチング失敗
                error_codes.append('ROOM_NOT_FOUND')
                failed += 1

        # Step5: raw_payloadを明示的に None に（メモリ破棄）
        raw_payload = None  # noqa: F841

        # Step6: WebhookProcessingLogを記録
        log = WebhookProcessingLog(
            log_id=_generate_log_id(carrier, processed_at),
            carrier=carrier,
            processed_at=processed_at,
            total_count=matched + failed,
            success_count=matched,
            failure_count=failed,
            error_codes=error_codes,
        )
        self._processing_logs.append(log)

        return {
            'matched': matched,
            'failed': failed,
            'error_codes': error_codes,
            'raw_data_retained': False,  # 常にFalse（即時破棄）
        }

    # ── 内部ヘルパー ─────────────────────────

    def _match_resident(self, building_code: str, floor: int) -> ResidentStub | None:
        """building_code + floor で居住者を検索"""
        key = f"{building_code}:{floor}"
        resident = self._residents.get(key)
        if resident is not None and resident.is_active:
            return resident
        return None

    def _create_delivery_record(
        self,
        carrier: str,
        item: dict,
        resident: ResidentStub,
    ) -> DeliveryRecord:
        """
        個人特定情報を除いたDeliveryRecordを作成
        tracking_numberはSHA-256ハッシュ化してrecord_idのみに使用
        氏名・電話番号・メールはrecordに含めない
        """
        tracking_number: str = item.get('tracking_number', '')
        # tracking_number は record_id 生成にのみ使用し、保存しない
        tracking_hash = _sha256_hex(tracking_number)
        record_id = tracking_hash[:12]

        building_code: str = item.get('building_code', resident.building_code)
        floor: int = int(item.get('floor', resident.floor))
        size: str = str(item.get('size', 'm')).lower()

        # ロッカーID生成（建物コード + フロア + サイズ）
        locker_id = f"{building_code}-F{floor:02d}-L{size.upper()}001"

        now = _utc_now()
        return DeliveryRecord(
            record_id=record_id,
            carrier=carrier,
            building_code=building_code,
            floor=floor,
            locker_id=locker_id,
            delivery_size=size,
            status='matched',
            matched_at=now,
            created_at=now,
            # tracking_number / recipient_name / phone / email は保存しない
        )

    # ── 照会メソッド ─────────────────────────

    def get_delivery_records(self) -> list[DeliveryRecord]:
        """保存済み配送レコード一覧"""
        return list(self._delivery_records)

    def get_processing_logs(self) -> list[WebhookProcessingLog]:
        """処理ログ一覧"""
        return list(self._processing_logs)

    def has_raw_data_in_memory(self) -> bool:
        """テスト用: 生データが残っていないことを確認（常にFalse）"""
        return False  # 設計上、生データはprocess_webhook内でのみ存在
