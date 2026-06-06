"""
NiceEze RESEARCH部 ユニットテスト (Ver 1.0)
RES-A01（8社価格マトリクス）/ RES-A02（トレンドスコア）

実行: python -m unittest tests.test_research -v
stdlib unittest のみ使用（pip install 不要）
bandit 準拠: subprocess なし / eval なし / hashlib.sha256 のみ
"""

import hashlib
import sys
import unittest
from pathlib import Path

# プロジェクトルートをパスに追加
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.research.res_a01 import (
    PriceFetcher,
    PriceMatrix,
    PriceRecord,
    SUPPLIERS,
)
from src.research.res_a02 import (
    TrendDataPoint,
    TrendFetcher,
    ProductTrend,
    TREND_WINDOW_DAYS,
)


# ─────────────────────────────────────────────
# PriceRecord テスト
# ─────────────────────────────────────────────
class TestPriceRecord(unittest.TestCase):
    def setUp(self):
        self.record = PriceRecord(
            supplier='Amazon',
            price_jpy=1000,
            shipping_jpy=500,
            lot_size=6,
            is_available=True,
        )

    def test_unit_price_calculation(self):
        """unit_price = (price_jpy + shipping_jpy) / lot_size"""
        expected = (1000 + 500) / 6
        self.assertAlmostEqual(self.record.unit_price, expected)

    def test_unit_price_lot_size_one(self):
        """lot_size=1 のとき unit_price = total_price"""
        r = PriceRecord(
            supplier='テスト',
            price_jpy=2000,
            shipping_jpy=200,
            lot_size=1,
            is_available=True,
        )
        self.assertAlmostEqual(r.unit_price, 2200.0)

    def test_unit_price_lot_size_zero_safe(self):
        """lot_size=0 でも ZeroDivisionError にならない（max(lot_size,1) 保護）"""
        r = PriceRecord(
            supplier='テスト',
            price_jpy=1000,
            shipping_jpy=0,
            lot_size=0,
            is_available=True,
        )
        self.assertAlmostEqual(r.unit_price, 1000.0)

    def test_case_price(self):
        """case_price = float(total_price)"""
        self.assertAlmostEqual(self.record.case_price, float(1500))

    def test_is_available_true(self):
        self.assertTrue(self.record.is_available)

    def test_is_available_false(self):
        r = PriceRecord(
            supplier='ヤマダ電機',
            price_jpy=800,
            shipping_jpy=0,
            lot_size=1,
            is_available=False,
        )
        self.assertFalse(r.is_available)


# ─────────────────────────────────────────────
# PriceMatrix テスト
# ─────────────────────────────────────────────
class TestPriceMatrix(unittest.TestCase):
    def setUp(self):
        self.matrix = PriceMatrix(keyword='トイレットペーパー', category='日用品・消耗品')
        self.matrix.records = [
            PriceRecord('Amazon', 1000, 0, 1, True),
            PriceRecord('楽天市場', 1500, 200, 1, True),
            PriceRecord('Yahoo!ショッピング', 900, 550, 1, True),
            PriceRecord('ヨドバシカメラ', 2000, 0, 6, True),
            PriceRecord('Qoo10', 800, 400, 1, False),  # 在庫なし
        ]

    def test_cheapest_returns_lowest_unit_price(self):
        """cheapest() は在庫ありの中で unit_price 最小を返す"""
        cheapest = self.matrix.cheapest()
        self.assertIsNotNone(cheapest)
        available = [r for r in self.matrix.records if r.is_available]
        min_price = min(r.unit_price for r in available)
        self.assertAlmostEqual(cheapest.unit_price, min_price)

    def test_cheapest_ignores_unavailable(self):
        """cheapest() は is_available=False を除外する"""
        cheapest = self.matrix.cheapest()
        self.assertTrue(cheapest.is_available)

    def test_cheapest_returns_none_when_no_available(self):
        matrix = PriceMatrix(keyword='テスト', category='食品・飲料')
        matrix.records = [
            PriceRecord('A', 1000, 0, 1, False),
        ]
        self.assertIsNone(matrix.cheapest())

    def test_sorted_by_unit_price_ordering(self):
        """sorted_by_unit_price() は unit_price 昇順、在庫なしは末尾"""
        sorted_records = self.matrix.sorted_by_unit_price()
        # 在庫ありレコードが先
        available_end = next(
            (i for i, r in enumerate(sorted_records) if not r.is_available),
            len(sorted_records)
        )
        available_sorted = sorted_records[:available_end]
        for i in range(len(available_sorted) - 1):
            self.assertLessEqual(
                available_sorted[i].unit_price,
                available_sorted[i + 1].unit_price
            )

    def test_price_gap_percent_positive(self):
        """price_gap_percent() > 0（在庫あり2社以上で最安と最高に差がある）"""
        gap = self.matrix.price_gap_percent()
        self.assertIsNotNone(gap)
        self.assertGreater(gap, 0.0)

    def test_price_gap_percent_none_when_one_available(self):
        matrix = PriceMatrix(keyword='テスト', category='食品・飲料')
        matrix.records = [
            PriceRecord('A', 1000, 0, 1, True),
            PriceRecord('B', 2000, 0, 1, False),
        ]
        self.assertIsNone(matrix.price_gap_percent())

    def test_cache_key_is_sha256_hex_32_chars(self):
        """cache_key は SHA-256 hexdigest の先頭32文字"""
        # __post_init__ で hexdigest()[:32] が設定される
        self.assertEqual(len(self.matrix.cache_key), 32)
        # すべて16進文字であることを確認
        int(self.matrix.cache_key, 16)  # ValueError なければOK

    def test_cache_key_matches_sha256_computation(self):
        """cache_key の値が手動計算と一致する"""
        expected = hashlib.sha256(
            'トイレットペーパー:日用品・消耗品'.encode()
        ).hexdigest()[:32]
        self.assertEqual(self.matrix.cache_key, expected)

    def test_to_dict_structure(self):
        d = self.matrix.to_dict()
        for key in ['keyword', 'category', 'cache_key', 'created_at',
                    'cheapest_supplier', 'cheapest_unit_price', 'price_gap_percent', 'records']:
            self.assertIn(key, d)


# ─────────────────────────────────────────────
# PriceFetcher テスト
# ─────────────────────────────────────────────
class TestPriceFetcher(unittest.TestCase):
    def setUp(self):
        self.fetcher = PriceFetcher()

    def test_fetch_returns_price_record(self):
        record = self.fetcher.fetch('コーラ', 'Amazon')
        self.assertIsInstance(record, PriceRecord)

    def test_build_matrix_returns_price_matrix(self):
        matrix = self.fetcher.build_matrix('コーラ', '食品・飲料')
        self.assertIsInstance(matrix, PriceMatrix)

    def test_build_matrix_has_8_suppliers(self):
        """SUPPLIERS リストに合わせて 8 社分のレコードが返る"""
        self.assertEqual(len(SUPPLIERS), 8)
        matrix = self.fetcher.build_matrix('コーラ', '食品・飲料')
        self.assertEqual(len(matrix.records), 8)

    def test_build_matrix_keyword_category_set(self):
        matrix = self.fetcher.build_matrix('コーラ', '食品・飲料')
        self.assertEqual(matrix.keyword, 'コーラ')
        self.assertEqual(matrix.category, '食品・飲料')

    def test_price_record_fields_valid(self):
        record = self.fetcher.fetch('洗剤', '楽天市場')
        self.assertIsInstance(record.price_jpy, int)
        self.assertGreater(record.price_jpy, 0)
        self.assertGreaterEqual(record.shipping_jpy, 0)
        self.assertGreater(record.lot_size, 0)
        self.assertIsInstance(record.is_available, bool)


# ─────────────────────────────────────────────
# ProductTrend テスト
# ─────────────────────────────────────────────
class _make_trend:
    """テスト用 ProductTrend ファクトリ（安定ランク 50 付近の14日分）"""
    @staticmethod
    def stable(days: int = 14) -> 'ProductTrend':
        trend = ProductTrend(keyword='テスト商品', category='日用品・消耗品')
        for i in range(days):
            from datetime import date, timedelta
            day = (date.today() - timedelta(days=days - i)).isoformat()
            trend.data_points.append(TrendDataPoint(
                date=day,
                rank=50 + (i % 3),  # 50〜52 で安定
                search_volume=1000,
            ))
        return trend


class TestProductTrend(unittest.TestCase):
    def setUp(self):
        self.trend = _make_trend.stable(14)

    def test_data_points_count(self):
        self.assertEqual(len(self.trend.data_points), 14)

    def test_growth_score_range(self):
        score = self.trend.growth_score()
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_bestseller_score_range(self):
        score = self.trend.bestseller_score()
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_retention_score_non_negative(self):
        score = self.trend.retention_score()
        self.assertGreaterEqual(score, 0.0)

    def test_is_staple_returns_bool(self):
        result = self.trend.is_staple()
        self.assertIsInstance(result, bool)

    def test_recommendation_non_empty(self):
        rec = self.trend.recommendation()
        self.assertIsInstance(rec, str)
        self.assertGreater(len(rec), 0)

    def test_to_dict_required_keys(self):
        d = self.trend.to_dict()
        for key in ['keyword', 'category', 'scores', 'is_staple', 'recommendation']:
            self.assertIn(key, d, f"to_dict() に '{key}' キーがありません")

    def test_to_dict_scores_subkeys(self):
        scores = self.trend.to_dict()['scores']
        for key in ['growth', 'bestseller', 'retention']:
            self.assertIn(key, scores)

    def test_growth_score_few_data_points(self):
        """データが7件未満の場合 growth_score() は 0.0"""
        trend = ProductTrend(keyword='テスト', category='食品・飲料')
        trend.data_points = [
            TrendDataPoint(date='2026-01-01', rank=100, search_volume=500)
        ]
        self.assertEqual(trend.growth_score(), 0.0)

    def test_bestseller_score_empty(self):
        """データなしの場合 bestseller_score() は 0.0"""
        trend = ProductTrend(keyword='テスト', category='食品・飲料')
        self.assertEqual(trend.bestseller_score(), 0.0)

    def test_high_rank_product_lower_bestseller(self):
        """ランクが高い（数字が大きい）ほど bestseller_score が低い"""
        trend_good = ProductTrend(keyword='A', category='食品・飲料')
        trend_bad = ProductTrend(keyword='B', category='食品・飲料')
        for i in range(14):
            from datetime import date, timedelta
            day = (date.today() - timedelta(days=14 - i)).isoformat()
            trend_good.data_points.append(TrendDataPoint(date=day, rank=5, search_volume=9999))
            trend_bad.data_points.append(TrendDataPoint(date=day, rank=900, search_volume=100))
        self.assertGreater(trend_good.bestseller_score(), trend_bad.bestseller_score())


# ─────────────────────────────────────────────
# TrendFetcher テスト
# ─────────────────────────────────────────────
class TestTrendFetcher(unittest.TestCase):
    def setUp(self):
        self.fetcher = TrendFetcher()

    def test_fetch_returns_product_trend(self):
        trend = self.fetcher.fetch('洗剤', '日用品・消耗品')
        self.assertIsInstance(trend, ProductTrend)

    def test_fetch_default_days(self):
        """days 省略時は TREND_WINDOW_DAYS (30) 日分のデータ"""
        trend = self.fetcher.fetch('洗剤', '日用品・消耗品')
        self.assertEqual(len(trend.data_points), TREND_WINDOW_DAYS)

    def test_fetch_custom_days(self):
        """days=14 を指定すると 14 件のデータポイントが返る"""
        trend = self.fetcher.fetch('洗剤', '日用品・消耗品', days=14)
        self.assertEqual(len(trend.data_points), 14)

    def test_fetch_days_7(self):
        trend = self.fetcher.fetch('コーヒー', '食品・飲料', days=7)
        self.assertEqual(len(trend.data_points), 7)

    def test_fetch_keyword_category_stored(self):
        trend = self.fetcher.fetch('シャンプー', '美容・健康')
        self.assertEqual(trend.keyword, 'シャンプー')
        self.assertEqual(trend.category, '美容・健康')

    def test_data_points_have_valid_ranks(self):
        trend = self.fetcher.fetch('靴下', '衣料・ファッション', days=30)
        for dp in trend.data_points:
            self.assertGreaterEqual(dp.rank, 1)
            self.assertGreater(dp.search_volume, 0)

    def test_analyze_batch(self):
        keywords = ['コーラ', '洗剤', 'シャンプー']
        results = self.fetcher.analyze_batch(keywords, '日用品・消耗品')
        self.assertEqual(len(results), 3)
        for trend in results:
            self.assertIsInstance(trend, ProductTrend)
            self.assertEqual(len(trend.data_points), TREND_WINDOW_DAYS)


# ─────────────────────────────────────────────
# ResearchAnalytics テスト
# ─────────────────────────────────────────────
from src.research.analytics import (
    ResearchAnalytics,
    PriceTrendResult,
    RankingEntry,
    GrowthAlert,
    NewProduct,
)


class TestResearchAnalytics(unittest.TestCase):
    def setUp(self):
        self.analytics = ResearchAnalytics()

    def test_price_trend_returns_list_of_price_trend_result(self):
        results = self.analytics.price_trend('日用品・消耗品', 30)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertIsInstance(r, PriceTrendResult)

    def test_price_trend_week_change_pct_is_float(self):
        results = self.analytics.price_trend('食品・飲料', 30)
        for r in results:
            self.assertIsInstance(r.week_change_pct, float)

    def test_ranking_returns_ranking_entry_list(self):
        results = self.analytics.ranking('family', 10)
        self.assertIsInstance(results, list)
        for entry in results:
            self.assertIsInstance(entry, RankingEntry)

    def test_ranking_is_sorted_by_rank(self):
        results = self.analytics.ranking('family', 10)
        ranks = [e.rank for e in results]
        self.assertEqual(ranks, sorted(ranks))

    def test_ranking_invalid_building_type_returns_empty(self):
        results = self.analytics.ranking('invalid', 10)
        self.assertEqual(results, [])

    def test_growth_alerts_returns_list_of_growth_alert(self):
        results = self.analytics.growth_alerts()
        self.assertIsInstance(results, list)
        for alert in results:
            self.assertIsInstance(alert, GrowthAlert)

    def test_growth_alerts_threshold_zero_returns_all(self):
        results = self.analytics.growth_alerts(threshold=0.0)
        self.assertGreater(len(results), 0)

    def test_growth_alerts_threshold_respected(self):
        threshold = 0.5
        results = self.analytics.growth_alerts(threshold=threshold)
        for alert in results:
            self.assertGreaterEqual(alert.growth_rate, threshold)

    def test_new_products_returns_list_of_new_product(self):
        results = self.analytics.new_products(30)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        for p in results:
            self.assertIsInstance(p, NewProduct)

    def test_new_products_days_zero_returns_empty(self):
        results = self.analytics.new_products(0)
        self.assertEqual(results, [])

    def test_export_csv_returns_str_with_comma(self):
        results = self.analytics.price_trend('日用品・消耗品', 30)
        data = {'data': [r.to_dict() for r in results], 'count': len(results), 'generated_at': '2026-06-06'}
        csv_str = self.analytics.export_csv(data)
        self.assertIsInstance(csv_str, str)
        self.assertIn(',', csv_str)

    def test_export_summary_returns_str(self):
        results = self.analytics.price_trend('日用品・消耗品', 30)
        data = {'data': [r.to_dict() for r in results], 'count': len(results), 'generated_at': '2026-06-06'}
        summary = self.analytics.export_summary(data)
        self.assertIsInstance(summary, str)
        self.assertGreater(len(summary), 0)

    def test_price_trend_unknown_category_returns_empty(self):
        results = self.analytics.price_trend('存在しないカテゴリ', 30)
        self.assertEqual(results, [])

    def test_new_products_trend_direction_valid(self):
        results = self.analytics.new_products(30)
        for p in results:
            self.assertIn(p.trend_direction, ('rising', 'stable', 'falling'))

    def test_ranking_limit_respected(self):
        results = self.analytics.ranking('family', 2)
        self.assertLessEqual(len(results), 2)


# ─────────────────────────────────────────────
# TestResearchAPIv1 (HTTP Server tests)
# ─────────────────────────────────────────────
import json
import threading
import urllib.parse
import urllib.request
import urllib.error
from http.server import HTTPServer
from src.research.api import ResearchHandler

_API_PORT = 18090


def _start_test_server() -> HTTPServer:
    server = HTTPServer(('127.0.0.1', _API_PORT), ResearchHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


class TestResearchAPIv1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = _start_test_server()
        import time
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _get(self, path: str) -> tuple[int, dict]:
        url = f'http://127.0.0.1:{_API_PORT}{path}'
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode('utf-8'))

    def _post(self, path: str, body: dict, token: str = '') -> tuple[int, dict]:
        url = f'http://127.0.0.1:{_API_PORT}{path}'
        data = json.dumps(body).encode('utf-8')
        headers = {'Content-Type': 'application/json', 'Content-Length': str(len(data))}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode('utf-8'))

    def test_price_trend_returns_200_with_data(self):
        qs = urllib.parse.urlencode({'category': '日用品・消耗品', 'days': 30})
        status, body = self._get(f'/api/v1/research/price-trend?{qs}')
        self.assertEqual(status, 200)
        self.assertIn('data', body)
        self.assertIsInstance(body['data'], list)

    def test_ranking_returns_200_with_data(self):
        status, body = self._get('/api/v1/research/ranking?building_type=family')
        self.assertEqual(status, 200)
        self.assertIn('data', body)
        self.assertIsInstance(body['data'], list)

    def test_growth_alert_returns_200(self):
        status, body = self._get('/api/v1/research/growth-alert')
        self.assertEqual(status, 200)
        self.assertIn('data', body)

    def test_new_products_returns_200(self):
        status, body = self._get('/api/v1/research/new-products')
        self.assertEqual(status, 200)
        self.assertIn('data', body)

    def test_export_with_valid_token_returns_200(self):
        status, body = self._post(
            '/api/v1/research/export',
            {'format': 'csv', 'category': '日用品・消耗品', 'days': 30},
            token='demo-token',
        )
        self.assertEqual(status, 200)
        self.assertIn('content', body)

    def test_export_without_token_returns_401(self):
        status, body = self._post(
            '/api/v1/research/export',
            {'format': 'csv', 'category': '日用品・消耗品', 'days': 30},
            token='',
        )
        self.assertEqual(status, 401)


if __name__ == '__main__':
    unittest.main()
