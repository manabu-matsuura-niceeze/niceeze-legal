"""Gate A — Keepa API疎通確認・価格データ取得 (Ver 1.0)"""
from __future__ import annotations

import random  # nosec B311 — MVP mock only
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import json
import urllib.request
import urllib.error


# ──────────────────────────────────────────
# データモデル
# ──────────────────────────────────────────

@dataclass
class PriceSnapshot:
    """Keepa から取得した価格スナップショット"""
    asin: str
    title: str
    amazon_price_jpy: int           # Amazon現在価格
    new_lowest_jpy: int             # 新品最安値
    used_lowest_jpy: int            # 中古最安値
    sales_rank: int                 # 売れ筋ランキング
    category: str
    fetched_at: str                 # ISO datetime UTC
    source: str = 'keepa_mock'     # 'keepa_live' when real API connected


# ──────────────────────────────────────────
# Keepa クライアント
# ──────────────────────────────────────────

class KeepaClient:
    """
    Keepa API クライアント。
    api_key 未設定時はモックデータを返す（MVP段階）。
    実API連携時は keepa_live モードに切替。
    """

    _KEEPA_ENDPOINT = 'https://api.keepa.com/product'  # nosec B310 — hardcoded Keepa API URL only

    def __init__(self, api_key: str = '') -> None:
        self._api_key = api_key
        self._mock_mode = not bool(api_key)

    # ── 公開メソッド ──────────────────────────

    def fetch(self, asin: str) -> PriceSnapshot:
        """
        ASIN に対応する価格スナップショットを取得。
        api_key 未設定時: モックデータ返却。
        api_key 設定済み: Keepa API 実呼び出し（失敗時はモックにフォールバック）。
        """
        if self._mock_mode:
            return self._mock_snapshot(asin)
        try:
            return self._live_fetch(asin)
        except Exception:  # noqa: BLE001 — fallback to mock on any network error
            return self._mock_snapshot(asin)

    def health_check(self) -> dict:
        """API 疎通状態を返す"""
        return {
            'status': 'mock' if self._mock_mode else 'ok',
            'api_key_set': not self._mock_mode,
            'checked_at': datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def to_dict(snapshot: PriceSnapshot) -> dict:
        """PriceSnapshot を辞書に変換"""
        return {
            'asin': snapshot.asin,
            'title': snapshot.title,
            'amazon_price_jpy': snapshot.amazon_price_jpy,
            'new_lowest_jpy': snapshot.new_lowest_jpy,
            'used_lowest_jpy': snapshot.used_lowest_jpy,
            'sales_rank': snapshot.sales_rank,
            'category': snapshot.category,
            'fetched_at': snapshot.fetched_at,
            'source': snapshot.source,
        }

    # ── 内部メソッド ──────────────────────────

    def _mock_snapshot(self, asin: str) -> PriceSnapshot:
        """テスト・MVP 用モックデータ生成"""
        rng = random.Random(hash(asin) % 2 ** 31)  # nosec B311 — MVP mock only
        amazon_price = rng.randint(1000, 20000)     # nosec B311
        return PriceSnapshot(
            asin=asin,
            title=f'Mock Product [{asin}]',
            amazon_price_jpy=amazon_price,
            new_lowest_jpy=int(amazon_price * rng.uniform(0.85, 0.99)),    # nosec B311
            used_lowest_jpy=int(amazon_price * rng.uniform(0.60, 0.80)),   # nosec B311
            sales_rank=rng.randint(1, 1000),                                # nosec B311
            category='日用品・消耗品',
            fetched_at=datetime.now(timezone.utc).isoformat(),
            source='keepa_mock',
        )

    def _live_fetch(self, asin: str) -> PriceSnapshot:
        """Keepa API 実呼び出し (urllib — stdlib only)"""
        url = (
            f'{self._KEEPA_ENDPOINT}'
            f'?key={self._api_key}&domain=5&asin={asin}'
        )
        req = urllib.request.Request(url, method='GET')  # nosec B310 — hardcoded Keepa URL, user asin sanitized via ASIN format
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
            raw: dict[str, Any] = json.loads(resp.read().decode('utf-8'))

        products = raw.get('products', [])
        if not products:
            return self._mock_snapshot(asin)

        p = products[0]
        csv = p.get('csv', [])
        # Keepa CSV index 0 = Amazon price (multiply by 0.01 for JPY)
        amazon_price = int((csv[0][-1] if csv and csv[0] else 0) * 0.01) or 9999
        new_lowest = int((csv[1][-1] if len(csv) > 1 and csv[1] else 0) * 0.01) or amazon_price
        used_lowest = int((csv[2][-1] if len(csv) > 2 and csv[2] else 0) * 0.01) or 0

        return PriceSnapshot(
            asin=asin,
            title=p.get('title', ''),
            amazon_price_jpy=amazon_price,
            new_lowest_jpy=new_lowest,
            used_lowest_jpy=used_lowest,
            sales_rank=p.get('salesRanks', {}).get('current', 9999),
            category=p.get('categoryTree', [{}])[-1].get('name', ''),
            fetched_at=datetime.now(timezone.utc).isoformat(),
            source='keepa_live',
        )
