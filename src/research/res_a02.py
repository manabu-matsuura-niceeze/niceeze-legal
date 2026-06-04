"""
RES-A02: 売れ筋・急成長・定番残存スコア — バックエンドモジュール (Ver 1.0)
Research部 特急MVP Week1
FinOps: 月額¥5,000以内 / PII不使用 / bandit 0件
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ──────────────────────────────────────────
# スコア定数
# ──────────────────────────────────────────

TREND_WINDOW_DAYS = 30     # トレンド計算ウィンドウ（日）
RETENTION_THRESHOLD = 0.6  # 定番残存スコア閾値（これ以上を「定番」と判定）

# 8カテゴリ（RES-A01と共通）
CATEGORIES = [
    '食品・飲料', '日用品・消耗品', '家電・ガジェット', '衣料・ファッション',
    '美容・健康', 'ペット用品', 'スポーツ・アウトドア', 'ホーム・インテリア',
]


# ──────────────────────────────────────────
# データモデル
# ──────────────────────────────────────────

@dataclass
class TrendDataPoint:
    """日次販売データポイント"""
    date: str           # ISO date
    rank: int           # ランキング順位（低いほど売れ筋）
    search_volume: int  # 検索ボリューム（推定）


@dataclass
class ProductTrend:
    """商品トレンド分析結果"""
    keyword: str
    category: str
    data_points: list[TrendDataPoint] = field(default_factory=list)
    analyzed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # ── スコア計算 ──────────────────────────

    def growth_score(self) -> float:
        """
        急成長スコア (0.0〜1.0):
        直近7日のランク変化率から算出。
        ランクが下がる（数字が小さくなる）ほどスコアが高い。
        """
        if len(self.data_points) < 7:
            return 0.0
        recent = self.data_points[-7:]
        older = self.data_points[-14:-7] if len(self.data_points) >= 14 else self.data_points[:7]
        avg_recent = sum(p.rank for p in recent) / len(recent)
        avg_older = sum(p.rank for p in older) / len(older)
        if avg_older == 0:
            return 0.0
        improvement = (avg_older - avg_recent) / avg_older
        return max(0.0, min(1.0, improvement))

    def bestseller_score(self) -> float:
        """
        売れ筋スコア (0.0〜1.0):
        平均ランクから算出。ランク1位 → 1.0、ランク1000位以下 → 0.0。
        """
        if not self.data_points:
            return 0.0
        avg_rank = sum(p.rank for p in self.data_points) / len(self.data_points)
        return max(0.0, 1.0 - (avg_rank - 1) / 999)

    def retention_score(self) -> float:
        """
        定番残存スコア S_retention (0.0〜1.0):
        ランキング変動の安定性から算出。
        標準偏差が小さいほど（安定したランキング）スコアが高い。
        """
        if len(self.data_points) < 2:
            return 0.0
        ranks = [p.rank for p in self.data_points]
        mean = sum(ranks) / len(ranks)
        variance = sum((r - mean) ** 2 for r in ranks) / len(ranks)
        std_dev = math.sqrt(variance)
        # 標準偏差50以下を安定とみなしスコア化
        stability = max(0.0, 1.0 - std_dev / 50)
        return round(stability * self.bestseller_score(), 3)

    def is_staple(self) -> bool:
        """定番商品判定（S_retention ≥ RETENTION_THRESHOLD）"""
        return self.retention_score() >= RETENTION_THRESHOLD

    def recommendation(self) -> str:
        """仕入れ推奨コメント"""
        g = self.growth_score()
        b = self.bestseller_score()
        r = self.retention_score()
        if g > 0.7 and b > 0.5:
            return '🚀 急成長中 — 早期仕入れ推奨'
        if r >= RETENTION_THRESHOLD:
            return '✅ 定番商品 — 安定仕入れ推奨'
        if b > 0.7:
            return '⭐ 売れ筋 — 通常仕入れ推奨'
        if g < 0.2 and b < 0.3:
            return '⚠️ 下降トレンド — 仕入れ見直し推奨'
        return '📊 要観察 — 継続モニタリング'

    def to_dict(self) -> dict:
        return {
            'keyword': self.keyword,
            'category': self.category,
            'analyzed_at': self.analyzed_at,
            'scores': {
                'growth': round(self.growth_score(), 3),
                'bestseller': round(self.bestseller_score(), 3),
                'retention': self.retention_score(),
            },
            'is_staple': self.is_staple(),
            'recommendation': self.recommendation(),
            'data_points_count': len(self.data_points),
        }


# ──────────────────────────────────────────
# トレンドデータ取得エンジン
# ──────────────────────────────────────────

class TrendFetcher:
    """
    トレンドデータ取得。
    MVP段階ではモックデータ。G2でKeepa / Google Trends API連携予定。
    【松浦CEO要件定義待ち】実API連携先の選定。
    """

    def fetch(self, keyword: str, category: str, days: int = TREND_WINDOW_DAYS) -> ProductTrend:
        import random  # nosec B311 — MVP mock data only, not used for security
        random.seed(hash(f'{keyword}:{category}') % 10000)

        from datetime import date, timedelta
        trend = ProductTrend(keyword=keyword, category=category)
        base_rank = random.randint(10, 500)  # nosec B311
        trend_direction = random.choice([-1, -1, 1])  # nosec B311 — 下降トレンド多め

        for i in range(days):
            day = (date.today() - timedelta(days=days - i)).isoformat()
            noise = random.randint(-20, 20)  # nosec B311
            rank = max(1, base_rank + trend_direction * i * 2 + noise)
            trend.data_points.append(TrendDataPoint(
                date=day,
                rank=rank,
                search_volume=max(100, int(10000 / rank) + random.randint(-100, 100)),  # nosec B311
            ))
        return trend

    def analyze_batch(self, keywords: list[str], category: str) -> list[ProductTrend]:
        return [self.fetch(kw, category) for kw in keywords]
