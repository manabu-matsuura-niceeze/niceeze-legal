"""
RES-A01: 8社価格比較マトリクス — バックエンドモジュール (Ver 1.0)
Research部 特急MVP Week1
FinOps: 月額¥5,000以内 / PII不使用 / bandit 0件
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ──────────────────────────────────────────
# 定数
# ──────────────────────────────────────────

MAX_SUPPLIERS = 8          # 比較対象サプライヤー数（固定）
CACHE_TTL_SECONDS = 3600   # 価格キャッシュ有効期限 1時間

# 楽天・Yahoo APIエンドポイント（公式HTTPS — B310対象外だがbandit誤検知抑止）
RAKUTEN_API_ENDPOINT = 'https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706'  # nosec B310
YAHOO_API_ENDPOINT = 'https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch'  # nosec B310

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
# 価格取得エンジン（MVP: モックデータ / 環境変数でAPI連携）
# ──────────────────────────────────────────

class PriceFetcher:
    """
    サプライヤー価格取得。
    環境変数が設定されている場合は実APIを呼び出し、未設定またはエラー時はモックにフォールバック。
      - KEEPA_API_KEY: Amazon価格取得（Keepa API）
      - RAKUTEN_APP_ID: 楽天商品検索API（無料）
      - YAHOO_CLIENT_ID: Yahoo!ショッピング商品検索API（無料）
    """

    def __init__(self) -> None:
        self._keepa_api_key: Optional[str] = os.environ.get('KEEPA_API_KEY')
        self._rakuten_app_id: Optional[str] = os.environ.get('RAKUTEN_APP_ID')
        self._yahoo_client_id: Optional[str] = os.environ.get('YAHOO_CLIENT_ID')

    def _mock_record(self, keyword: str, supplier: str) -> PriceRecord:
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

    def _fetch_rakuten(self, keyword: str) -> Optional[PriceRecord]:
        params = urllib.parse.urlencode({
            'applicationId': self._rakuten_app_id,
            'keyword': keyword,
            'hits': 1,
            'sort': '+itemPrice',
        })
        url = f'{RAKUTEN_API_ENDPOINT}?{params}'
        req = urllib.request.Request(url)  # nosec B310
        with urllib.request.urlopen(req, timeout=5) as resp:  # nosec B310
            data = json.loads(resp.read().decode('utf-8'))
        items = data.get('Items', [])
        if not items:
            return None
        item = items[0]['Item']
        return PriceRecord(
            supplier='楽天市場',
            price_jpy=int(item.get('itemPrice', 0)),
            shipping_jpy=0,
            lot_size=1,
            is_available=True,
            url=item.get('itemUrl', ''),
        )

    def _fetch_yahoo(self, keyword: str) -> Optional[PriceRecord]:
        params = urllib.parse.urlencode({
            'appid': self._yahoo_client_id,
            'query': keyword,
            'results': 1,
            'sort': 'price',
        })
        url = f'{YAHOO_API_ENDPOINT}?{params}'
        req = urllib.request.Request(url)  # nosec B310
        with urllib.request.urlopen(req, timeout=5) as resp:  # nosec B310
            data = json.loads(resp.read().decode('utf-8'))
        hits = data.get('hits', [])
        if not hits:
            return None
        hit = hits[0]
        return PriceRecord(
            supplier='Yahoo!ショッピング',
            price_jpy=int(hit.get('price', 0)),
            shipping_jpy=0,
            lot_size=1,
            is_available=hit.get('inStock', False),
            url=hit.get('url', ''),
        )

    def fetch(self, keyword: str, supplier: str) -> Optional[PriceRecord]:
        """
        サプライヤー別に価格を取得する。
        環境変数が設定されている場合は実APIを使用し、エラー時はモックにフォールバック。
        """
        if supplier == 'Amazon' and self._keepa_api_key:
            try:
                from surplus_shift.gate_a import KeepaClient
                client = KeepaClient(api_key=self._keepa_api_key)
                # G3で実ASINルックアップを実装予定。MVP段階ではkeywordをASINとして使用。
                result = client.get_price(keyword)
                if result is not None:
                    price = result if isinstance(result, int) else int(result)
                    return PriceRecord(
                        supplier='Amazon',
                        price_jpy=price,
                        shipping_jpy=0,
                        lot_size=1,
                        is_available=True,
                    )
            except Exception:  # noqa: BLE001 — フォールバック設計
                pass
            return self._mock_record(keyword, supplier)

        if supplier == '楽天市場' and self._rakuten_app_id:
            try:
                result = self._fetch_rakuten(keyword)
                if result is not None:
                    return result
            except Exception:  # noqa: BLE001 — フォールバック設計
                pass
            return self._mock_record(keyword, supplier)

        if supplier == 'Yahoo!ショッピング' and self._yahoo_client_id:
            try:
                result = self._fetch_yahoo(keyword)
                if result is not None:
                    return result
            except Exception:  # noqa: BLE001 — フォールバック設計
                pass
            return self._mock_record(keyword, supplier)

        return self._mock_record(keyword, supplier)

    def build_matrix(self, keyword: str, category: str) -> PriceMatrix:
        matrix = PriceMatrix(keyword=keyword, category=category)
        for supplier in SUPPLIERS:
            record = self.fetch(keyword, supplier)
            if record:
                matrix.records.append(record)
        return matrix
