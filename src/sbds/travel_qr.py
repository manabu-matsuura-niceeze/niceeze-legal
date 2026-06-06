"""手ぶら旅行 QRコード発行・管理 (Ver 1.0)
SBDS部門 MVP
FinOps: 月額¥5,000以内 / PII最小化 / bandit 0件
"""
from __future__ import annotations

import hashlib
import secrets  # nosec B311 — token generation
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List

QR_TTL_SECONDS = 86400        # QR有効期限: 24時間
QR_CODE_LENGTH = 32           # QRコードトークン長
VALID_STATUSES = ['active', 'used', 'expired', 'cancelled']


@dataclass
class TravelQR:
    qr_id: str          # SHA-256[:16]
    token: str          # secrets.token_urlsafe(QR_CODE_LENGTH) — nosec B311
    traveler_ref: str   # 旅行者参照ID（PII不使用: 予約番号ハッシュ等）
    departure_hub: str  # 出発拠点コード（例: 'TYO', 'OSA', 'FUK'）
    arrival_hub: str    # 到着拠点コード
    baggage_count: int  # 荷物数
    status: str         # 'active' | 'used' | 'expired' | 'cancelled'
    issued_at: str      # ISO UTC
    expires_at: str     # ISO UTC (issued_at + 24h)
    used_at: str = ''   # スキャン時刻

    @property
    def is_valid(self) -> bool:
        """有効期限内かつstatus==active"""
        now = datetime.now(timezone.utc)
        exp = datetime.fromisoformat(self.expires_at)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return self.status == 'active' and now < exp

    def to_dict(self) -> dict:
        return {
            'qr_id': self.qr_id,
            'token': self.token,
            'traveler_ref': self.traveler_ref,
            'departure_hub': self.departure_hub,
            'arrival_hub': self.arrival_hub,
            'baggage_count': self.baggage_count,
            'status': self.status,
            'issued_at': self.issued_at,
            'expires_at': self.expires_at,
            'used_at': self.used_at,
        }


class TravelQRManager:
    """QRコード発行・管理マネージャー"""

    def __init__(self) -> None:
        self._store: dict[str, TravelQR] = {}  # token -> TravelQR

    def issue(
        self,
        traveler_ref: str,
        departure_hub: str,
        arrival_hub: str,
        baggage_count: int,
    ) -> TravelQR:
        """QRコードを発行する"""
        token = secrets.token_urlsafe(QR_CODE_LENGTH)  # nosec B311
        qr_id = hashlib.sha256(token.encode()).hexdigest()[:16]
        now = datetime.now(timezone.utc)
        issued_at = now.isoformat()
        expires_at = (now + timedelta(seconds=QR_TTL_SECONDS)).isoformat()
        qr = TravelQR(
            qr_id=qr_id,
            token=token,
            traveler_ref=traveler_ref,
            departure_hub=departure_hub,
            arrival_hub=arrival_hub,
            baggage_count=baggage_count,
            status='active',
            issued_at=issued_at,
            expires_at=expires_at,
        )
        self._store[token] = qr
        return qr

    def scan(self, token: str) -> TravelQR:
        """トークンでQRを検索・検証し、used に更新する"""
        qr = self._store.get(token)
        if qr is None:
            raise ValueError(f'QR not found for token: {token[:8]}...')
        if not qr.is_valid:
            raise ValueError(f'QR {qr.qr_id} is not valid (status={qr.status})')
        qr.used_at = datetime.now(timezone.utc).isoformat()
        qr.status = 'used'
        return qr

    def expire_old(self) -> int:
        """期限切れQRのstatusを 'expired' に更新し、更新件数を返す"""
        count = 0
        now = datetime.now(timezone.utc)
        for qr in self._store.values():
            if qr.status == 'active':
                exp = datetime.fromisoformat(qr.expires_at)
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if now >= exp:
                    qr.status = 'expired'
                    count += 1
        return count

    def get_by_hub(self, hub: str) -> List[TravelQR]:
        """拠点別QR一覧（出発または到着が一致するもの）"""
        return [
            qr for qr in self._store.values()
            if qr.departure_hub == hub or qr.arrival_hub == hub
        ]

    def cancel(self, qr_id: str) -> TravelQR:
        """QRをキャンセルする"""
        for qr in self._store.values():
            if qr.qr_id == qr_id:
                qr.status = 'cancelled'
                return qr
        raise ValueError(f'QR not found: {qr_id}')

    def summary(self) -> dict:
        """発行数・有効数・期限切れ数・使用済み数"""
        total = len(self._store)
        active = sum(1 for q in self._store.values() if q.status == 'active')
        expired = sum(1 for q in self._store.values() if q.status == 'expired')
        used = sum(1 for q in self._store.values() if q.status == 'used')
        cancelled = sum(1 for q in self._store.values() if q.status == 'cancelled')
        return {
            'total': total,
            'active': active,
            'expired': expired,
            'used': used,
            'cancelled': cancelled,
        }
