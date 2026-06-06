"""RESEARCH 分析エンジン (Ver 1.0)
価格推移・ランキング・成長アラート・新商品検出
FinOps: 月額¥5,000以内 / PII不使用 / bandit 0件
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime, timezone

from .res_a01 import PriceFetcher, CATEGORIES
from .res_a02 import TrendFetcher

# ──────────────────────────────────────────
# 定数
# ──────────────────────────────────────────

BUILDING_TYPES = ['luxury', 'family', 'student', 'single']
DEFAULT_GROWTH_THRESHOLD = 0.30   # 30%
DEFAULT_NEW_PRODUCT_DAYS = 30
DEFAULT_RANKING_LIMIT = 10

# 建物タイプ別キーワードマッピング
_BUILDING_TYPE_KEYWORDS: dict[str, list[str]] = {
    'luxury': ['高級食材', '高級家電', 'プレミアム美容'],
    'family': ['日用品', '食品', 'ペット用品'],
    'student': ['文房具', '食品・飲料', 'ガジェット'],
    'single': ['日用品・消耗品', '食品・飲料', '家電・ガジェット'],
}

# カテゴリ別代表キーワード
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    '食品・飲料': ['コーラ', 'コーヒー', 'お茶'],
    '日用品・消耗品': ['洗剤', 'トイレットペーパー', 'シャンプー'],
    '家電・ガジェット': ['スマホケース', 'イヤホン', 'モバイルバッテリー'],
    '衣料・ファッション': ['靴下', 'Tシャツ', 'バッグ'],
    '美容・健康': ['日焼け止め', '化粧水', 'サプリメント'],
    'ペット用品': ['ペットフード', 'ペットシーツ', 'おもちゃ'],
    'スポーツ・アウトドア': ['プロテイン', 'ランニングシューズ', 'ヨガマット'],
    'ホーム・インテリア': ['収納ボックス', 'クッション', 'カーテン'],
}

# 新商品候補（カテゴリ別）
_NEW_PRODUCT_KEYWORDS: dict[str, list[str]] = {
    '食品・飲料': ['新作スムージー', '機能性ドリンク', 'プロテインバー'],
    '日用品・消耗品': ['エコ洗剤', '詰め替えパック', '除菌スプレー'],
    '家電・ガジェット': ['スマートウォッチ新型', 'TWS イヤホン', 'USB-C ハブ'],
    '衣料・ファッション': ['サステナブルTシャツ', 'リサイクル素材バッグ', 'エコスニーカー'],
    '美容・健康': ['UV ケアセラム', 'ビタミンC 美容液', '保湿マスク'],
    'ペット用品': ['オーガニックペットフード', 'スマートフィーダー', 'ペット用カメラ'],
    'スポーツ・アウトドア': ['コンプレッションタイツ', 'スマートボトル', 'バランスボード'],
    'ホーム・インテリア': ['スマート照明', 'アロマディフューザー', 'モジュール収納'],
}


# ──────────────────────────────────────────
# データモデル
# ──────────────────────────────────────────

@dataclass
class PriceTrendResult:
    """カテゴリ別価格推移分析結果"""
    keyword: str
    category: str
    current_avg_price: float
    prev_week_avg: float
    prev_month_avg: float
    week_change_pct: float
    month_change_pct: float
    data_points_count: int
    analyzed_at: str

    def to_dict(self) -> dict:
        return {
            'keyword': self.keyword,
            'category': self.category,
            'current_avg_price': self.current_avg_price,
            'prev_week_avg': self.prev_week_avg,
            'prev_month_avg': self.prev_month_avg,
            'week_change_pct': round(self.week_change_pct, 2),
            'month_change_pct': round(self.month_change_pct, 2),
            'data_points_count': self.data_points_count,
            'analyzed_at': self.analyzed_at,
        }


@dataclass
class RankingEntry:
    """売れ筋ランキングエントリ"""
    rank: int
    keyword: str
    category: str
    building_type: str
    bestseller_score: float
    growth_score: float
    unit_price: float

    def to_dict(self) -> dict:
        return {
            'rank': self.rank,
            'keyword': self.keyword,
            'category': self.category,
            'building_type': self.building_type,
            'bestseller_score': round(self.bestseller_score, 3),
            'growth_score': round(self.growth_score, 3),
            'unit_price': round(self.unit_price, 2),
        }


@dataclass
class GrowthAlert:
    """成長アラート"""
    keyword: str
    category: str
    growth_rate: float
    threshold: float
    triggered_at: str

    def to_dict(self) -> dict:
        return {
            'keyword': self.keyword,
            'category': self.category,
            'growth_rate': round(self.growth_rate, 4),
            'threshold': round(self.threshold, 4),
            'triggered_at': self.triggered_at,
        }


@dataclass
class NewProduct:
    """新商品情報"""
    keyword: str
    category: str
    first_seen_date: str
    initial_rank: int
    current_rank: int
    trend_direction: str  # 'rising'|'stable'|'falling'

    def to_dict(self) -> dict:
        return {
            'keyword': self.keyword,
            'category': self.category,
            'first_seen_date': self.first_seen_date,
            'initial_rank': self.initial_rank,
            'current_rank': self.current_rank,
            'trend_direction': self.trend_direction,
        }


# ──────────────────────────────────────────
# 分析エンジン
# ──────────────────────────────────────────

class ResearchAnalytics:
    """RESEARCH 分析エンジン"""

    def __init__(self) -> None:
        self._price_fetcher = PriceFetcher()
        self._trend_fetcher = TrendFetcher()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def price_trend(self, category: str, days: int = 30) -> list[PriceTrendResult]:
        """カテゴリ別価格推移。TrendFetcherとPriceFetcherを使用。"""
        keywords = _CATEGORY_KEYWORDS.get(category, [])
        results: list[PriceTrendResult] = []
        analyzed_at = self._now_iso()

        for keyword in keywords:
            matrix = self._price_fetcher.build_matrix(keyword, category)
            available = [r for r in matrix.records if r.is_available]
            if not available:
                continue

            current_avg = sum(r.unit_price for r in available) / len(available)

            # モックでprev_week / prev_monthをシミュレーション
            import random  # nosec B311 — MVP mock data only
            random.seed(hash(f'{keyword}:{category}:price_trend') % 10000)
            week_factor = 1.0 + random.uniform(-0.15, 0.15)  # nosec B311
            month_factor = 1.0 + random.uniform(-0.25, 0.25)  # nosec B311
            prev_week_avg = current_avg / week_factor if week_factor != 0 else current_avg
            prev_month_avg = current_avg / month_factor if month_factor != 0 else current_avg

            week_change_pct = (
                (current_avg - prev_week_avg) / prev_week_avg * 100
                if prev_week_avg != 0 else 0.0
            )
            month_change_pct = (
                (current_avg - prev_month_avg) / prev_month_avg * 100
                if prev_month_avg != 0 else 0.0
            )

            trend = self._trend_fetcher.fetch(keyword, category, days)

            results.append(PriceTrendResult(
                keyword=keyword,
                category=category,
                current_avg_price=round(current_avg, 2),
                prev_week_avg=round(prev_week_avg, 2),
                prev_month_avg=round(prev_month_avg, 2),
                week_change_pct=week_change_pct,
                month_change_pct=month_change_pct,
                data_points_count=len(trend.data_points),
                analyzed_at=analyzed_at,
            ))

        return results

    def ranking(self, building_type: str, limit: int = DEFAULT_RANKING_LIMIT) -> list[RankingEntry]:
        """建物タイプ別売れ筋ランキング。"""
        if building_type not in BUILDING_TYPES:
            return []

        keywords = _BUILDING_TYPE_KEYWORDS.get(building_type, [])
        entries: list[tuple[float, str, str]] = []  # (combined_score, keyword, category)

        # キーワードに対応するカテゴリを特定
        keyword_to_category: dict[str, str] = {}
        for cat, kws in _CATEGORY_KEYWORDS.items():
            for kw in kws:
                keyword_to_category[kw] = cat

        # building_type キーワードはそのままカテゴリとして扱い、
        # そのカテゴリの代表キーワードからトレンドを取得
        for bt_keyword in keywords:
            # bt_keywordをカテゴリとみなして _CATEGORY_KEYWORDS から探索
            cat_keywords = _CATEGORY_KEYWORDS.get(bt_keyword, [bt_keyword])
            category = bt_keyword if bt_keyword in CATEGORIES else list(CATEGORIES)[0]

            for kw in cat_keywords:
                trend = self._trend_fetcher.fetch(kw, category)
                bs = trend.bestseller_score()
                gs = trend.growth_score()
                matrix = self._price_fetcher.build_matrix(kw, category)
                cheapest = matrix.cheapest()
                unit_price = cheapest.unit_price if cheapest else 0.0
                entries.append((bs + gs, kw, category, bs, gs, unit_price))

        # スコア降順ソート
        entries.sort(key=lambda x: x[0], reverse=True)

        result: list[RankingEntry] = []
        for i, entry in enumerate(entries[:limit]):
            _, kw, cat, bs, gs, up = entry
            result.append(RankingEntry(
                rank=i + 1,
                keyword=kw,
                category=cat,
                building_type=building_type,
                bestseller_score=bs,
                growth_score=gs,
                unit_price=up,
            ))
        return result

    def growth_alerts(self, threshold: float = DEFAULT_GROWTH_THRESHOLD) -> list[GrowthAlert]:
        """週次成長率が閾値を超えた商品を検出。"""
        alerts: list[GrowthAlert] = []
        triggered_at = self._now_iso()

        for category, keywords in _CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                trend = self._trend_fetcher.fetch(keyword, category)
                growth_rate = trend.growth_score()
                if growth_rate >= threshold:
                    alerts.append(GrowthAlert(
                        keyword=keyword,
                        category=category,
                        growth_rate=growth_rate,
                        threshold=threshold,
                        triggered_at=triggered_at,
                    ))

        return alerts

    def new_products(self, days: int = DEFAULT_NEW_PRODUCT_DAYS) -> list[NewProduct]:
        """過去N日以内の新商品。モックではdaysに応じた新商品リストを返す。"""
        if days <= 0:
            return []

        from datetime import date, timedelta
        products: list[NewProduct] = []
        today = date.today()

        import random  # nosec B311 — MVP mock data only
        for category, new_kws in _NEW_PRODUCT_KEYWORDS.items():
            for i, keyword in enumerate(new_kws):
                random.seed(hash(f'{keyword}:{category}:new_product') % 10000)
                days_ago = random.randint(1, days)  # nosec B311
                first_seen = (today - timedelta(days=days_ago)).isoformat()
                initial_rank = random.randint(50, 500)  # nosec B311
                current_rank = random.randint(1, initial_rank)  # nosec B311

                if current_rank < initial_rank * 0.8:
                    direction = 'rising'
                elif current_rank > initial_rank * 1.2:
                    direction = 'falling'
                else:
                    direction = 'stable'

                products.append(NewProduct(
                    keyword=keyword,
                    category=category,
                    first_seen_date=first_seen,
                    initial_rank=initial_rank,
                    current_rank=current_rank,
                    trend_direction=direction,
                ))

        return products

    def export_csv(self, data: dict) -> str:
        """CSV文字列を生成（stdlib csv モジュール使用）"""
        output = io.StringIO()
        items = data.get('data', [])
        if not items:
            return ''
        writer = csv.DictWriter(output, fieldnames=list(items[0].keys()))
        writer.writeheader()
        writer.writerows(items)
        return output.getvalue()

    def export_summary(self, data: dict) -> str:
        """テキストサマリー（PDF代替 — stdlib only）"""
        lines: list[str] = []
        lines.append('=== RESEARCH EXPORT SUMMARY ===')
        lines.append(f"generated_at: {data.get('generated_at', '')}")
        lines.append(f"count: {data.get('count', 0)}")
        lines.append('')
        for i, item in enumerate(data.get('data', []), 1):
            lines.append(f'[{i}] ' + ' / '.join(f'{k}={v}' for k, v in item.items()))
        return '\n'.join(lines)
