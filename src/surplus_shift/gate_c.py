"""Gate C — 在庫回転・需要予測スコアリング (Ver 1.0)"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ──────────────────────────────────────────
# 定数
# ──────────────────────────────────────────

TURNOVER_THRESHOLD_DAYS = 30    # 在庫回転目標日数（30日以内）
DEMAND_SCORE_THRESHOLD = 0.6    # 需要予測スコア閾値


# ──────────────────────────────────────────
# データモデル
# ──────────────────────────────────────────

@dataclass
class DemandForecast:
    """需要予測データ"""
    keyword: str
    category: str
    avg_daily_sales: float          # 推定日次販売数
    stock_qty: int                  # 現在在庫数
    turnover_days: float            # 推定回転日数（stock_qty / avg_daily_sales）
    demand_score: float             # 需要スコア (0.0〜1.0)
    trend_direction: str            # 'rising'/'stable'/'declining'
    forecast_at: str                # ISO datetime UTC


@dataclass
class InventoryScore:
    """在庫スコアリング結果"""
    keyword: str
    demand_forecast: DemandForecast
    inventory_score: float          # 総合在庫スコア (0.0〜1.0)
    is_recommended: bool            # True if inventory_score >= DEMAND_SCORE_THRESHOLD
    surplus_risk: str               # 'low'/'medium'/'high'
    action: str                     # 推奨アクション


# ──────────────────────────────────────────
# 在庫スコアリングエンジン
# ──────────────────────────────────────────

class InventoryScorer:
    """在庫回転・需要予測スコアリングクラス"""

    def score(
        self,
        keyword: str,
        category: str,
        stock_qty: int,
        avg_daily_sales: float,
        sales_rank: int = 500,
    ) -> InventoryScore:
        """
        在庫スコアを算出する。

        rank_score     = max(0.0, 1.0 - (sales_rank - 1) / 999)
        turnover_score = max(0.0, 1.0 - turnover_days / TURNOVER_THRESHOLD_DAYS)
        demand_score   = (rank_score + turnover_score) / 2
        """
        turnover_days = (
            stock_qty / avg_daily_sales if avg_daily_sales > 0 else 9999.0
        )

        rank_score = max(0.0, 1.0 - (sales_rank - 1) / 999)
        turnover_score = max(0.0, 1.0 - turnover_days / TURNOVER_THRESHOLD_DAYS)
        demand_score = round((rank_score + turnover_score) / 2, 3)

        # トレンド方向（簡易判定: スコアベース）
        if demand_score >= 0.7:
            trend_direction = 'rising'
        elif demand_score >= 0.4:
            trend_direction = 'stable'
        else:
            trend_direction = 'declining'

        # 余剰リスク判定
        if turnover_days > 60:
            surplus_risk = 'high'
        elif turnover_days > 30:
            surplus_risk = 'medium'
        else:
            surplus_risk = 'low'

        is_recommended = demand_score >= DEMAND_SCORE_THRESHOLD

        # 推奨アクション
        action = self._build_action(surplus_risk, demand_score, is_recommended)

        forecast = DemandForecast(
            keyword=keyword,
            category=category,
            avg_daily_sales=avg_daily_sales,
            stock_qty=stock_qty,
            turnover_days=round(turnover_days, 1),
            demand_score=demand_score,
            trend_direction=trend_direction,
            forecast_at=datetime.now(timezone.utc).isoformat(),
        )

        return InventoryScore(
            keyword=keyword,
            demand_forecast=forecast,
            inventory_score=demand_score,
            is_recommended=is_recommended,
            surplus_risk=surplus_risk,
            action=action,
        )

    def batch_score(self, items: list[dict[str, Any]]) -> list[InventoryScore]:
        """
        複数アイテムを一括スコアリング。

        各 dict: keyword, category, stock_qty, avg_daily_sales, sales_rank(optional)
        """
        results: list[InventoryScore] = []
        for item in items:
            results.append(self.score(
                keyword=item['keyword'],
                category=item['category'],
                stock_qty=int(item['stock_qty']),
                avg_daily_sales=float(item['avg_daily_sales']),
                sales_rank=int(item.get('sales_rank', 500)),
            ))
        return results

    @staticmethod
    def to_dict(score: InventoryScore) -> dict:
        """InventoryScore を辞書に変換"""
        f = score.demand_forecast
        return {
            'keyword': score.keyword,
            'inventory_score': score.inventory_score,
            'is_recommended': score.is_recommended,
            'surplus_risk': score.surplus_risk,
            'action': score.action,
            'demand_forecast': {
                'keyword': f.keyword,
                'category': f.category,
                'avg_daily_sales': f.avg_daily_sales,
                'stock_qty': f.stock_qty,
                'turnover_days': f.turnover_days,
                'demand_score': f.demand_score,
                'trend_direction': f.trend_direction,
                'forecast_at': f.forecast_at,
            },
        }

    # ── 内部メソッド ──────────────────────────

    @staticmethod
    def _build_action(surplus_risk: str, demand_score: float, is_recommended: bool) -> str:
        if surplus_risk == 'high':
            return '余剰リスク高 — 早期に余剰転換（SURPLUS SHIFT）を検討してください'
        if surplus_risk == 'medium' and not is_recommended:
            return '余剰リスク中 — 追加仕入れを抑制し在庫消化を優先してください'
        if is_recommended:
            return f'需要スコア {demand_score:.2f} — 通常仕入れ推奨'
        return f'需要スコア {demand_score:.2f} — 要観察。追加仕入れは慎重に判断してください'
