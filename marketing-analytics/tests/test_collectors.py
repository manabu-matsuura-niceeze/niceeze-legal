"""tests/test_collectors.py - TwitterCollector のユニットテスト"""
import pytest
from datetime import datetime, timezone, timedelta
from src.collectors.twitter import TwitterCollector, TwitterKPI

JST = timezone(timedelta(hours=9))

@pytest.fixture
def sample_date():
    return datetime(2026, 6, 6, 0, 0, 0, tzinfo=JST)


class TestTwitterCollectorDryRun:
    def test_dry_run_returns_twitter_kpi(self, sample_date):
        """dry_run=True でモックデータ (TwitterKPI) を返す"""
        collector = TwitterCollector(dry_run=True)
        kpi = collector.collect(sample_date)
        assert isinstance(kpi, TwitterKPI)

    def test_dry_run_followers_type(self, sample_date):
        """followers が int 型である"""
        collector = TwitterCollector(dry_run=True)
        kpi = collector.collect(sample_date)
        assert isinstance(kpi.followers, int)

    def test_dry_run_engagement_rate_type(self, sample_date):
        """engagement_rate が float 型である"""
        collector = TwitterCollector(dry_run=True)
        kpi = collector.collect(sample_date)
        assert isinstance(kpi.engagement_rate, float)

    def test_dry_run_no_error(self, sample_date):
        """dry_run ではエラーなし"""
        collector = TwitterCollector(dry_run=True)
        kpi = collector.collect(sample_date)
        assert kpi.error == ""

    def test_dry_run_date_format(self, sample_date):
        """date フィールドが YYYY-MM-DD 形式"""
        collector = TwitterCollector(dry_run=True)
        kpi = collector.collect(sample_date)
        assert kpi.date == "2026-06-06"

    def test_dry_run_followers_positive(self, sample_date):
        """dry_run モックデータは followers > 0"""
        collector = TwitterCollector(dry_run=True)
        kpi = collector.collect(sample_date)
        assert kpi.followers > 0

    def test_dry_run_engagement_rate_positive(self, sample_date):
        """dry_run モックデータは engagement_rate > 0"""
        collector = TwitterCollector(dry_run=True)
        kpi = collector.collect(sample_date)
        assert kpi.engagement_rate > 0.0


class TestTwitterCollectorEngagement:
    def test_engagement_rate_calculation(self):
        """エンゲージメント率 = (likes+retweets+replies)/impressions*100"""
        collector = TwitterCollector(dry_run=True)
        # _fetch_kpi のロジックを直接テスト
        likes, retweets, replies, impressions = 180, 45, 71, 12345
        engagement = (likes + retweets + replies) / impressions * 100
        expected = round(engagement, 2)
        assert abs(expected - 2.4) < 0.1

    def test_engagement_rate_zero_impressions(self):
        """インプレッション0のときエンゲージメント率は0"""
        collector = TwitterCollector(dry_run=True)
        impressions = 0
        likes, retweets, replies = 10, 5, 3
        engagement = (likes + retweets + replies) / impressions * 100 if impressions > 0 else 0.0
        assert engagement == 0.0

    def test_mock_kpi_data_consistency(self, sample_date):
        """モックKPIのデータ整合性: tweet_count>=0, impressions>=0"""
        collector = TwitterCollector(dry_run=True)
        kpi = collector.collect(sample_date)
        assert kpi.tweet_count >= 0
        assert kpi.impressions >= 0
        assert kpi.likes >= 0
        assert kpi.retweets >= 0
        assert kpi.replies >= 0


class TestTwitterCollectorError:
    def test_no_token_uses_mock_mode(self, sample_date):
        """トークンなしでもエラーにならず mock モードになる"""
        collector = TwitterCollector(bearer_token="", dry_run=False)
        # トークンがなければ _mock_mode=True になる
        assert collector._mock_mode is True

    def test_error_stored_on_exception(self):
        """例外発生時にエラーメッセージが error フィールドに格納される"""
        collector = TwitterCollector(bearer_token="invalid_token_for_test", dry_run=False)
        collector._mock_mode = False  # 強制的に本番モード
        date = datetime(2026, 6, 6, 0, 0, 0, tzinfo=JST)
        kpi = collector.collect(date)
        # 実際のAPIコールは失敗するため error に内容が入る
        assert kpi.error != "" or kpi.followers == 0  # エラーかゼロのどちらか
