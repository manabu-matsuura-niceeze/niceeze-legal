"""
RES-A01: 8社価格比較マトリクス — バックエンドモジュール (Ver 1.0)
Research部 特急MVP Week1
FinOps: 月額¥5,000以内 / PII不使用 / bandit 0件
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ──────────────────────────────────────────
# 定数
# ──────────────────────────────────────────

MAX_SUPPLIERS = 8          # 比較対象サプライヤー数（固定）
CACHE_TTL_SECONDS = 3600   # 価格キャッシュ有効期限 1時間

# 対応カテゴリ（MVP 8カテゴリ）
CATEGORIES = [
    '食品・飲料',
    '日用品・消耗品',
    '家電・ガジェット',
    '衣料・ファッション',
    '美容・健康',
    'ペット用品',
    'スポーツ・アウトドア',
    'ホーム・インテリア',
]

# サプライヤーリスト（MVP 8社 — 実際のAPI連携はG2で実装）
SUPPLIERS = [
    'Amazon',
    '楽天市場',
    'Yahoo!ショッピング',
    'au PAY マーケット',
    'Qoo10',
    'ヨドバシカメラ',
    'ビックカメラ',
    'ヤマダ電機',
]


# ──────────────────────────────────────────
# データモデル
# ──────────────────────────────────────────

@dataclass
class PriceRecord:
    """サプライヤー1社の価格情報"""
    supplier: str
    price_jpy: int           # 税込価格
    shipping_jpy: int        # 送料
    lot_size: int            # ロットサイズ（個数）
    is_available: bool       # 在庫あり
    url: str = ''
    retrieved_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def total_price(self) -> int:
        return self.price_jpy + self.shipping_jpy

    @property
    def unit_price(self) -> float:
        """1個あたり単価"""
        return self.total_price / max(self.lot_size, 1)

    @property
    def case_price(self) -> float:
        """1ケースあたり価格（lot_size単位）"""
        return float(self.total_price)


@dataclass
class PriceMatrix:
    """8社比較マトリクス"""
    keyword: str
    category: str
    records: list[PriceRecord] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    cache_key: str = ''

    def __post_init__(self) -> None:
        self.cache_key = hashlib.sha256(
            f'{self.keyword}:{self.category}'.encode()
        ).hexdigest()[:32]

    def cheapest(self) -> Optional[PriceRecord]:
        available = [r for r in self.records if r.is_available]
        return min(available, key=lambda r: r.unit_price) if available else None

    def sorted_by_unit_price(self) -> list[PriceRecord]:
        return sorted(self.records, key=lambda r: (not r.is_available, r.unit_price))

    def price_gap_percent(self) -> Optional[float]:
        """最安値と最高値の価格差（%）"""
        available = [r for r in self.records if r.is_available]
        if len(available) < 2:
            return None
        min_p = min(r.unit_price for r in available)
        max_p = max(r.unit_price for r in available)
        return round((max_p - min_p) / min_p * 100, 1) if min_p > 0 else None

    def to_dict(self) -> dict:
        return {
            'keyword': self.keyword,
            'category': self.category,
            'cache_key': self.cache_key,
            'created_at': self.created_at,
            'cheapest_supplier': self.cheapest().supplier if self.cheapest() else None,
            'cheapest_unit_price': self.cheapest().unit_price if self.cheapest() else None,
            'price_gap_percent': self.price_gap_percent(),
            'records': [
                {
                    'supplier': r.supplier,
                    'price_jpy': r.price_jpy,
                    'shipping_jpy': r.shipping_jpy,
                    'lot_size': r.lot_size,
                    'unit_price': round(r.unit_price, 2),
                    'case_price': r.case_price,
                    'is_available': r.is_available,
                    'retrieved_at': r.retrieved_at,
                }
                for r in self.sorted_by_unit_price()
            ],
        }


# ──────────────────────────────────────────
# 価格取得エンジン（MVP: モックデータ / G2でAPI連携）
# ──────────────────────────────────────────

class PriceFetcher:
    """
    サプライヤー価格取得。
    MVP段階ではモックデータを返す。
    G2でKeepa API / 楽天商品検索API等に切替予定。
    """

    def fetch(self, keyword: str, supplier: str) -> Optional[PriceRecord]:
        """
        【松浦CEO要件定義待ち】
        実API連携先は以下を想定するが、契約・キー取得はG2判断。
          - Keepa API（Amazon価格履歴）
          - 楽天商品検索API（無料）
          - Yahoo!ショッピング商品検索API（無料）
          - その他: スクレイピング（利用規約確認要）
        MVP段階ではキーワード+サプライヤーのモックデータを返す。
        """
        import random  # nosec B311 — MVP mock data only, not used for security
        random.seed(hash(f'{keyword}:{supplier}') % 10000)
        base_price = random.randint(800, 5000)  # nosec B311
        return PriceRecord(
            supplier=supplier,
            price_jpy=base_price,
            shipping_jpy=0 if base_price >= 2000 else 550,
            lot_size=random.choice([1, 6, 12, 24]),  # nosec B311
            is_available=random.random() > 0.15,  # nosec B311
        )

    def build_matrix(self, keyword: str, category: str) -> PriceMatrix:
        matrix = PriceMatrix(keyword=keyword, category=category)
        for supplier in SUPPLIERS:
            record = self.fetch(keyword, supplier)
            if record:
                matrix.records.append(record)
        return matrix
