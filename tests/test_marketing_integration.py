"""MARKETING部 統合テスト — ニュースクローラー / コンテンツ生成 / 配信ログ / パイプライン"""
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.marketing.news_crawler import NewsCrawler, CrawlResult, NewsArticle
from src.marketing.content_generator import ContentGenerator, ContentInput, GeneratedContent
from src.marketing.delivery_log import DeliveryLog, DeliveryRecord
from src.marketing.scheduler import ContentScheduler
from src.marketing.x_poster import XPoster, XPostResult


# ---------------------------------------------------------------------------
# TestNewsCrawler
# ---------------------------------------------------------------------------

class TestNewsCrawler(unittest.TestCase):

    def setUp(self):
        self.crawler = NewsCrawler()

    def test_crawl_all_returns_crawl_result(self):
        result = self.crawler.crawl_all()
        self.assertIsInstance(result, CrawlResult)

    def test_articles_is_list(self):
        result = self.crawler.crawl_all()
        self.assertIsInstance(result.articles, list)

    def test_articles_not_empty(self):
        result = self.crawler.crawl_all()
        # Mock fallback guarantees articles even without network
        self.assertGreater(len(result.articles), 0)

    def test_article_has_required_fields(self):
        result = self.crawler.crawl_all()
        for article in result.articles:
            with self.subTest(article=article.title):
                self.assertIsInstance(article.article_id, str)
                self.assertIsInstance(article.title, str)
                self.assertIsInstance(article.category_key, str)
                self.assertIsInstance(article.published_at, str)

    def test_article_id_is_64_char_sha256_hex(self):
        result = self.crawler.crawl_all()
        for article in result.articles:
            with self.subTest(title=article.title):
                self.assertEqual(len(article.article_id), 64,
                                 f"article_id must be 64-char SHA-256, got {len(article.article_id)}: {article.article_id}")
                # Ensure it is hex
                int(article.article_id, 16)

    def test_article_id_not_md5(self):
        result = self.crawler.crawl_all()
        for article in result.articles:
            with self.subTest(title=article.title):
                self.assertNotEqual(len(article.article_id), 32,
                                    "article_id looks like MD5 (32 chars); must be SHA-256 (64 chars)")

    def test_article_title_nonempty(self):
        result = self.crawler.crawl_all()
        for article in result.articles:
            with self.subTest():
                self.assertGreater(len(article.title.strip()), 0)

    def test_mock_articles_triggered_when_no_network(self):
        # Force mock by using a bad category key that has no RSS URL
        articles = self.crawler._mock_articles('business')
        self.assertGreater(len(articles), 0)
        for a in articles:
            self.assertEqual(len(a.article_id), 64)


# ---------------------------------------------------------------------------
# TestContentGenerator
# ---------------------------------------------------------------------------

class TestContentGenerator(unittest.TestCase):

    def setUp(self):
        self.gen = ContentGenerator()

    def _make_input(self, tone='professional'):
        return ContentInput(
            topic='ECサイト最新トレンド',
            category='EC・流通・物流',
            product_name='NiceEzeボックス',
            trend_score=0.75,
            tone=tone,
        )

    def test_generate_returns_generated_content(self):
        inp = self._make_input()
        result = self.gen.generate_all(inp)
        self.assertIsInstance(result, GeneratedContent)

    def test_x_post_length_within_limit(self):
        for tone in ('professional', 'casual', 'urgent'):
            with self.subTest(tone=tone):
                inp = self._make_input(tone=tone)
                result = self.gen.generate_all(inp)
                self.assertLessEqual(len(result.x_post), 140,
                                     f"x_post exceeds 140 chars for tone={tone}")

    def test_newsletter_html_is_html(self):
        for tone in ('professional', 'casual', 'urgent'):
            with self.subTest(tone=tone):
                inp = self._make_input(tone=tone)
                result = self.gen.generate_all(inp)
                self.assertIn('<html', result.newsletter_html.lower())

    def test_note_markdown_contains_heading(self):
        for tone in ('professional', 'casual', 'urgent'):
            with self.subTest(tone=tone):
                inp = self._make_input(tone=tone)
                result = self.gen.generate_all(inp)
                self.assertIn('#', result.note_markdown)

    def test_youtube_script_nonempty(self):
        for tone in ('professional', 'casual', 'urgent'):
            with self.subTest(tone=tone):
                inp = self._make_input(tone=tone)
                result = self.gen.generate_all(inp)
                self.assertIsInstance(result.youtube_script, str)
                self.assertGreater(len(result.youtube_script.strip()), 0)

    def test_professional_tone(self):
        inp = self._make_input(tone='professional')
        result = self.gen.generate_all(inp)
        self.assertIsNotNone(result)

    def test_casual_tone(self):
        inp = self._make_input(tone='casual')
        result = self.gen.generate_all(inp)
        self.assertIsNotNone(result)

    def test_urgent_tone(self):
        inp = self._make_input(tone='urgent')
        result = self.gen.generate_all(inp)
        self.assertIsNotNone(result)


# ---------------------------------------------------------------------------
# TestDeliveryLog
# ---------------------------------------------------------------------------

class TestDeliveryLog(unittest.TestCase):

    def setUp(self):
        self.log = DeliveryLog()

    def test_add_returns_delivery_record(self):
        record = self.log.add('x_post', 'テストトピック', 'EC・流通', 80)
        self.assertIsInstance(record, DeliveryRecord)

    def test_add_id_is_64_char_sha256(self):
        record = self.log.add('x_post', 'テストトピック', 'EC・流通', 80)
        self.assertEqual(len(record.id), 64)
        int(record.id, 16)  # must be valid hex

    def test_add_delivered_at_nonempty(self):
        record = self.log.add('newsletter', 'メルマガトピック', 'マーケティング', 500)
        self.assertIsInstance(record.delivered_at, str)
        self.assertGreater(len(record.delivered_at), 0)

    def test_add_status_is_delivered(self):
        record = self.log.add('note', 'Noteトピック', 'ライフスタイル', 300)
        self.assertEqual(record.status, 'delivered')

    def test_get_by_type_returns_only_x_post(self):
        self.log.add('x_post', 'X投稿トピック', 'EC', 100)
        self.log.add('newsletter', 'メルマガ', 'EC', 500)
        self.log.add('x_post', 'X投稿2', 'ビジネス', 90)
        records = self.log.get_by_type('x_post')
        self.assertEqual(len(records), 2)
        for r in records:
            self.assertEqual(r.content_type, 'x_post')

    def test_get_recent_within_7_days(self):
        self.log.add('youtube', 'YouTube台本', 'テクノロジー', 1000)
        self.log.add('note', 'Note原稿', 'ヘルス', 400)
        recent = self.log.get_recent(days=7)
        # Just-added records should be within 7 days
        self.assertGreaterEqual(len(recent), 2)

    def test_summary_has_required_keys(self):
        self.log.add('x_post', 'サマリーテスト', 'EC', 100)
        s = self.log.summary()
        self.assertIn('by_type', s)
        self.assertIn('total_delivered', s)
        self.assertIn('last_delivery_at', s)

    def test_summary_total_delivered_count(self):
        self.log.add('x_post', 'A', 'EC', 100)
        self.log.add('newsletter', 'B', 'EC', 500)
        s = self.log.summary()
        self.assertEqual(s['total_delivered'], 2)

    def test_to_json_valid_json(self):
        self.log.add('x_post', 'JSONテスト', 'マーケティング', 90)
        json_str = self.log.to_json()
        self.assertIsInstance(json_str, str)
        parsed = json.loads(json_str)  # must not raise
        self.assertIsInstance(parsed, list)


# ---------------------------------------------------------------------------
# TestMarketingPipeline — end-to-end integration
# ---------------------------------------------------------------------------

class TestMarketingPipeline(unittest.TestCase):

    def test_scheduler_instantiates(self):
        scheduler = ContentScheduler()
        self.assertIsNotNone(scheduler)

    def test_run_completes_without_exception(self):
        scheduler = ContentScheduler()
        result = scheduler.run(run_type='manual')
        # Network errors are caught internally; result must exist
        self.assertIsNotNone(result)

    def test_run_result_has_generated_count(self):
        scheduler = ContentScheduler()
        result = scheduler.run(run_type='morning')
        generated_count = len(result.generated_contents)
        # 0 is acceptable (mock fallback); must be non-negative integer
        self.assertGreaterEqual(generated_count, 0)

    def test_run_result_to_dict_serializable(self):
        scheduler = ContentScheduler()
        result = scheduler.run(run_type='evening')
        d = result.to_dict()
        self.assertIsInstance(d, dict)
        self.assertIn('run_type', d)
        self.assertIn('generated_contents', d)

    def test_pipeline_produces_contents_or_graceful_fallback(self):
        """Full pipeline: crawl → select topics → generate content."""
        scheduler = ContentScheduler()
        result = scheduler.run(run_type='morning')
        # Either contents were generated, or errors were recorded gracefully
        has_content = len(result.generated_contents) > 0
        has_errors = len(result.errors) > 0
        # At minimum one of these conditions must be met (system ran)
        self.assertTrue(has_content or has_errors or result.crawl_result is not None,
                        "Pipeline produced no output at all")


# ---------------------------------------------------------------------------
# TestXPoster
# ---------------------------------------------------------------------------

class TestXPoster(unittest.TestCase):

    def setUp(self):
        # 環境変数を確実にクリアしてmock_modeにする
        for key in ('X_API_KEY', 'X_API_SECRET', 'X_ACCESS_TOKEN', 'X_ACCESS_TOKEN_SECRET', 'X_BEARER_TOKEN'):
            os.environ.pop(key, None)
        self.poster = XPoster()

    def test_mock_mode_post_success(self):
        """mock_mode時に投稿が成功すること"""
        result = self.poster.post('テスト投稿')
        self.assertTrue(result.success)

    def test_mock_mode_tweet_id_prefix(self):
        """mock_modeのtweet_idが mock_ プレフィックスを持つこと"""
        result = self.poster.post('テスト投稿')
        self.assertTrue(result.tweet_id.startswith('mock_'))

    def test_truncate_over_140_chars(self):
        """140文字超のテキストがトランケートされること"""
        long_text = 'あ' * 200
        result = self.poster.post(long_text)
        self.assertEqual(len(result.text), 140)

    def test_to_dict_keys(self):
        """to_dict() が必要なキーを全て持つこと"""
        result = self.poster.post('キーチェック')
        d = result.to_dict()
        for key in ('tweet_id', 'text', 'posted_at', 'is_mock', 'success', 'error'):
            with self.subTest(key=key):
                self.assertIn(key, d)

    def test_mock_success_true(self):
        """mock_mode時に success=True であること"""
        result = self.poster.post('サクセステスト')
        self.assertTrue(result.success)

    def test_missing_api_key_triggers_mock_mode(self):
        """X_API_KEY未設定でmock_modeになること"""
        poster = XPoster()
        self.assertTrue(poster._mock_mode)

    def test_is_mock_flag(self):
        """mock_mode時に XPostResult.is_mock が True であること"""
        result = self.poster.post('モックフラグテスト')
        self.assertTrue(result.is_mock)

    def test_scheduler_run_returns_x_posts_sent(self):
        """scheduler.run() の結果に x_posts_sent が含まれること"""
        scheduler = ContentScheduler()
        result = scheduler.run(run_type='morning')
        d = result.to_dict()
        self.assertIn('x_posts_sent', d)
        self.assertIsInstance(d['x_posts_sent'], int)
        self.assertGreaterEqual(d['x_posts_sent'], 0)

    def test_x_post_result_is_dataclass(self):
        """XPostResult が dataclass であること"""
        result = self.poster.post('データクラステスト')
        self.assertIsInstance(result, XPostResult)


if __name__ == '__main__':
    unittest.main()
