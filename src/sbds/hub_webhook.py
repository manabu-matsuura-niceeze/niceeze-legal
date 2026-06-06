"""手ぶら旅行 拠点間Webhook連携 (Ver 1.0)
SBDS部門 MVP
出発拠点 → 中央サーバー → 到着拠点の荷物転送通知
FinOps: 月額¥5,000以内 / PII最小化 / bandit 0件
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List

from .travel_qr import TravelQR

WEBHOOK_TIMEOUT_SECONDS = 10
EVENT_TYPES = ['baggage_dispatched', 'baggage_arrived', 'baggage_ready', 'baggage_issue']
HUB_ENDPOINTS: dict[str, str] = {}  # 本番時は環境変数から読み込み


@dataclass
class WebhookEvent:
    event_id: str       # SHA-256[:16]
    event_type: str     # EVENT_TYPES のいずれか
    qr_id: str          # TravelQR.qr_id
    source_hub: str     # 送信元拠点
    target_hub: str     # 送信先拠点
    payload: dict       # 任意のイベントデータ（PII不可）
    sent_at: str
    delivered: bool = False
    delivered_at: str = ''
    error: str = ''

    def to_dict(self) -> dict:
        return {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'qr_id': self.qr_id,
            'source_hub': self.source_hub,
            'target_hub': self.target_hub,
            'payload': self.payload,
            'sent_at': self.sent_at,
            'delivered': self.delivered,
            'delivered_at': self.delivered_at,
            'error': self.error,
        }


@dataclass
class WebhookDeliveryResult:
    event_id: str
    success: bool
    status_code: int = 0
    response_body: str = ''
    error: str = ''
    attempted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            'event_id': self.event_id,
            'success': self.success,
            'status_code': self.status_code,
            'response_body': self.response_body,
            'error': self.error,
            'attempted_at': self.attempted_at,
        }


class HubWebhookClient:
    """拠点間Webhook送信クライアント"""

    def __init__(self) -> None:
        self._endpoints: dict[str, str] = {}
        raw = os.environ.get('HUB_WEBHOOK_URLS', '')
        if raw:
            for pair in raw.split(','):
                pair = pair.strip()
                if '=' in pair:
                    hub, url = pair.split('=', 1)
                    self._endpoints[hub.strip()] = url.strip()
        self._mock_mode: bool = len(self._endpoints) == 0
        self._history: list[WebhookEvent] = []

    def _make_event(
        self,
        event_type: str,
        qr_id: str,
        source_hub: str,
        target_hub: str,
        payload: dict,
    ) -> WebhookEvent:
        if event_type not in EVENT_TYPES:
            raise ValueError(f'Invalid event_type: {event_type}. Must be one of {EVENT_TYPES}')
        now = datetime.now(timezone.utc).isoformat()
        seed = f'{event_type}:{qr_id}:{now}'
        event_id = hashlib.sha256(seed.encode()).hexdigest()[:16]
        return WebhookEvent(
            event_id=event_id,
            event_type=event_type,
            qr_id=qr_id,
            source_hub=source_hub,
            target_hub=target_hub,
            payload=payload,
            sent_at=now,
        )

    def dispatch(self, event: WebhookEvent) -> WebhookDeliveryResult:
        """Webhookイベントを送信する"""
        self._history.append(event)

        if self._mock_mode:
            event.delivered = True
            event.delivered_at = datetime.now(timezone.utc).isoformat()
            return WebhookDeliveryResult(
                event_id=event.event_id,
                success=True,
                status_code=200,
                response_body='{"mock":true}',
            )

        url = self._endpoints.get(event.target_hub, '')
        if not url:
            event.error = f'No endpoint configured for hub: {event.target_hub}'
            return WebhookDeliveryResult(
                event_id=event.event_id,
                success=False,
                error=event.error,
            )

        body = json.dumps(event.to_dict(), ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(  # nosec B310
            url,
            data=body,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=WEBHOOK_TIMEOUT_SECONDS) as resp:  # nosec B310
                status_code = resp.status
                response_body = resp.read().decode('utf-8', errors='replace')
            event.delivered = True
            event.delivered_at = datetime.now(timezone.utc).isoformat()
            return WebhookDeliveryResult(
                event_id=event.event_id,
                success=True,
                status_code=status_code,
                response_body=response_body,
            )
        except Exception as exc:
            event.error = str(exc)
            return WebhookDeliveryResult(
                event_id=event.event_id,
                success=False,
                error=str(exc),
            )

    def notify_dispatch(self, qr: TravelQR, baggage_details: dict) -> WebhookDeliveryResult:
        """荷物発送通知"""
        event = self._make_event(
            event_type='baggage_dispatched',
            qr_id=qr.qr_id,
            source_hub=qr.departure_hub,
            target_hub=qr.arrival_hub,
            payload={
                'baggage_count': qr.baggage_count,
                'baggage_details': baggage_details,
            },
        )
        return self.dispatch(event)

    def notify_arrival(self, qr: TravelQR) -> WebhookDeliveryResult:
        """荷物到着通知"""
        event = self._make_event(
            event_type='baggage_arrived',
            qr_id=qr.qr_id,
            source_hub=qr.arrival_hub,
            target_hub=qr.departure_hub,
            payload={'baggage_count': qr.baggage_count},
        )
        return self.dispatch(event)

    def get_history(self) -> List[WebhookEvent]:
        """送信履歴を返す"""
        return list(self._history)

    def summary(self) -> dict:
        """イベント数・配信成功率"""
        total = len(self._history)
        delivered = sum(1 for e in self._history if e.delivered)
        rate = (delivered / total * 100) if total > 0 else 0.0
        return {
            'total_events': total,
            'delivered': delivered,
            'failed': total - delivered,
            'delivery_rate_pct': round(rate, 2),
            'mock_mode': self._mock_mode,
        }
