"""SmartLife — 商品マスタ管理モジュール

SURPLUS SHIFTからの自動商品登録受信、建物タイプ別商品管理を提供する。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

BUILDING_TYPES = ['luxury', 'family', 'student', 'single']
CATEGORIES = ['daily_goods', 'food', 'cleaning', 'furniture', 'electronics', 'other']


@dataclass
class Product:
    """商品マスタ"""
    id: str
    name: str
    building_type: str
    category: str
    price_jpy: int
    min_order_qty: int
    supplier_code: str
    created_at: str

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'building_type': self.building_type,
            'category': self.category,
            'price_jpy': self.price_jpy,
            'min_order_qty': self.min_order_qty,
            'supplier_code': self.supplier_code,
            'created_at': self.created_at,
        }


def _new_short_id() -> str:
    return str(uuid.uuid4())[:8]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProductStore:
    """商品マスタストア（インメモリ）"""

    def __init__(self) -> None:
        self._store: Dict[str, Product] = {}

    def add(self, product: Product) -> Product:
        if product.building_type not in BUILDING_TYPES:
            raise ValueError(f"Invalid building_type: {product.building_type}. Must be one of {BUILDING_TYPES}")
        if product.category not in CATEGORIES:
            raise ValueError(f"Invalid category: {product.category}. Must be one of {CATEGORIES}")
        self._store[product.id] = product
        return product

    def get(self, product_id: str) -> Optional[Product]:
        return self._store.get(product_id)

    def update(self, product_id: str, updates: dict) -> Optional[Product]:
        product = self._store.get(product_id)
        if product is None:
            return None
        allowed = {'name', 'building_type', 'category', 'price_jpy', 'min_order_qty', 'supplier_code'}
        for key, value in updates.items():
            if key not in allowed:
                continue
            if key == 'building_type' and value not in BUILDING_TYPES:
                raise ValueError(f"Invalid building_type: {value}")
            if key == 'category' and value not in CATEGORIES:
                raise ValueError(f"Invalid category: {value}")
            setattr(product, key, value)
        return product

    def list_by_building_type(self, building_type: str) -> List[Product]:
        return [p for p in self._store.values() if p.building_type == building_type]

    def list_all(self) -> List[Product]:
        return list(self._store.values())


def register_from_surplus(negotiation_dict: dict) -> Product:
    """SURPLUS SHIFTからの自動登録受信

    negotiation statusが agreed または closed_won のみ受付。
    それ以外はValueErrorを送出する。
    """
    status = negotiation_dict.get('status', '')
    if status not in ('agreed', 'closed_won'):
        raise ValueError(
            f"Cannot register product: negotiation status '{status}' is not accepted. "
            "Only 'agreed' or 'closed_won' are allowed."
        )

    product_id = negotiation_dict.get('product_id') or _new_short_id()
    if len(product_id) > 8:
        product_id = product_id[:8]

    building_type = negotiation_dict.get('building_type', 'family')
    if building_type not in BUILDING_TYPES:
        building_type = 'family'

    category = negotiation_dict.get('category', 'other')
    if category not in CATEGORIES:
        category = 'other'

    return Product(
        id=product_id,
        name=negotiation_dict.get('product_name', ''),
        building_type=building_type,
        category=category,
        price_jpy=int(negotiation_dict.get('agreed_price_jpy', 0)),
        min_order_qty=int(negotiation_dict.get('min_order_qty', 1)),
        supplier_code=negotiation_dict.get('supplier_code', ''),
        created_at=_now_iso(),
    )
