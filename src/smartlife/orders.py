"""SmartLife — グループ予約・ゼロ在庫発注モジュール

Gate D制約: human_approval_required=True は変更禁止（自動発注禁止）。
発注はあくまで人間担当者の承認後に実行すること。
"""
from __future__ import annotations

import json
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


ORDER_STATUSES = ('pending', 'confirmed', 'ordered', 'delivered', 'cancelled')


def _new_short_id() -> str:
    return str(uuid.uuid4())[:8]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class OrderItem:
    """注文明細"""
    product_id: str
    qty: int
    unit_price_jpy: int

    def to_dict(self) -> dict:
        return {
            'product_id': self.product_id,
            'qty': self.qty,
            'unit_price_jpy': self.unit_price_jpy,
        }


@dataclass
class GroupOrder:
    """グループ予約"""
    order_id: str
    building_code: str
    items: List[OrderItem]
    status: str
    delivery_date: str
    deadline: str
    created_at: str

    def to_dict(self) -> dict:
        return {
            'order_id': self.order_id,
            'building_code': self.building_code,
            'items': [item.to_dict() for item in self.items],
            'status': self.status,
            'delivery_date': self.delivery_date,
            'deadline': self.deadline,
            'created_at': self.created_at,
        }


class GroupOrderStore:
    """グループ予約ストア（インメモリ）"""

    def __init__(self) -> None:
        self._store: Dict[str, GroupOrder] = {}

    def create(
        self,
        building_code: str,
        items: List[OrderItem],
        delivery_date: str,
        deadline: str,
    ) -> GroupOrder:
        order = GroupOrder(
            order_id=_new_short_id(),
            building_code=building_code,
            items=items,
            status='pending',
            delivery_date=delivery_date,
            deadline=deadline,
            created_at=_now_iso(),
        )
        self._store[order.order_id] = order
        return order

    def get(self, order_id: str) -> Optional[GroupOrder]:
        return self._store.get(order_id)

    def list(self, building_code: Optional[str] = None) -> List[GroupOrder]:
        if building_code:
            return [o for o in self._store.values() if o.building_code == building_code]
        return list(self._store.values())

    def confirm_order(self, order_id: str) -> Optional[GroupOrder]:
        order = self._store.get(order_id)
        if order is None:
            return None
        if order.status != 'pending':
            raise ValueError(f"Cannot confirm order with status '{order.status}'. Only 'pending' orders can be confirmed.")
        order.status = 'confirmed'
        return order

    def cancel(self, order_id: str) -> Optional[GroupOrder]:
        order = self._store.get(order_id)
        if order is None:
            return None
        if order.status in ('delivered', 'cancelled'):
            raise ValueError(f"Cannot cancel order with status '{order.status}'.")
        order.status = 'cancelled'
        return order


class ZeroStockTrigger:
    """ゼロ在庫発注トリガー

    Gate D制約: human_approval_required=True は変更禁止。
    発注トリガーは人間担当者の承認後に実行されることを前提とする。
    """

    human_approval_required: bool = True

    def __setattr__(self, name: str, value: object) -> None:
        """human_approval_required は常に True — 変更禁止"""
        if name == 'human_approval_required':
            raise AttributeError(
                "human_approval_required cannot be changed. "
                "Gate D constraint: human approval is always required for supplier orders."
            )
        super().__setattr__(name, value)

    def trigger_supplier_order(self, order: GroupOrder, surplus_api_url: str) -> dict:
        """注文確定時に発注先URLへPOST送信

        Gate D制約により human_approval_required=True を常にペイロードに含める。
        実際の送信前に人間担当者の承認を得ること。
        """
        payload = {
            'source': 'smartlife',
            'building_code': order.building_code,
            'items': [item.to_dict() for item in order.items],
            'human_approval_required': True,
        }
        payload_bytes = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(
            surplus_api_url,
            data=payload_bytes,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
            response_body = resp.read().decode('utf-8')
            try:
                return json.loads(response_body)
            except json.JSONDecodeError:
                return {'raw': response_body, 'status_code': resp.status}
