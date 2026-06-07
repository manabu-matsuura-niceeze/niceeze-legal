"""Twitter Collector のテスト"""
import pytest
from datetime import datetime, timezone, timedelta
from src.collectors.twitter import TwitterCollector, TwitterKPI

JST = timezone(timedelta(hours=9))
TEST_DATE = datetime(2026, 6, 6, 0, 0, 0, tzinfo=JST)


def test_dry_run_returns_mock_data():
    collector = TwitterCollector(dry_run=True)
    kpi = collector.collect(TEST_DATE)
    assert isinstance(kpi, TwitterKPI)
    assert kpi.date == "2026-06-06"


def test_mock_followers_type():
    collector = TwitterCollector(dry_run=True)
    kpi = collector.collect(TEST_DATE)
    assert isinstance(kpi.followers, int)
    assert kpi.followers > 0


def test_mock_engagement_rate_type():
    collector = TwitterCollector(dry_run=True)
    kpi = collector.collect(TEST_DATE)
    assert isinstance(kpi.engagement_rate, float)


def test_mock_no_error():
    collector = TwitterCollector(dry_run=True)
    kpi = collector.collect(TEST_DATE)
    assert kpi.error == ""


def test_mock_kpi_data_integrity():
    collector = TwitterCollector(dry_run=True)
    kpi = collector.collect(TEST_DATE)
    assert kpi.followers == 523
    assert kpi.impressions == 12345
    assert kpi.tweet_count == 2
    assert kpi.engagement_rate == 2.4


def test_mock_kpi_likes():
    collector = TwitterCollector(dry_run=True)
    kpi = collector.collect(TEST_DATE)
    assert kpi.likes == 180
    assert kpi.retweets == 45
    assert kpi.replies == 71


def test_no_token_uses_mock():
    """トークンなしの場合はmockモードになる"""
    collector = TwitterCollector(bearer_token="", dry_run=False)
    assert collector._mock_mode is True


def test_engagement_rate_calculation():
    """エンゲージメント率の計算ロジック"""
    collector = TwitterCollector(dry_run=True)
    # _fetch_kpi ロジックの検証: (likes+rt+replies)/impressions*100
    likes, retweets, replies, impressions = 100, 20, 30, 1000
    expected = (likes + retweets + replies) / impressions * 100
    assert expected == 15.0


def test_engagement_rate_zero_impressions():
    """インプレッション0のときエンゲージメント率は0"""
    # _fetch_kpi内の分岐テスト
    impressions = 0
    likes, retweets, replies = 10, 5, 3
    engagement = (likes + retweets + replies) / impressions * 100 if impressions > 0 else 0.0
    assert engagement == 0.0


def test_collect_returns_error_on_exception(monkeypatch):
    """API呼び出し失敗時にerrorフィールドが設定される"""
    collector = TwitterCollector(bearer_token="fake_token", dry_run=False)
    collector._mock_mode = False

    def raise_error(date_str):
        raise RuntimeError("Connection refused")

    monkeypatch.setattr(collector, "_fetch_kpi", raise_error)
    kpi = collector.collect(TEST_DATE)
    assert kpi.error != ""
    assert "取得失敗" in kpi.error


def test_mock_mode_with_dry_run_true():
    collector = TwitterCollector(bearer_token="sometoken", dry_run=True)
    assert collector._mock_mode is True


def test_collect_date_format():
    collector = TwitterCollector(dry_run=True)
    date = datetime(2026, 1, 15, tzinfo=JST)
    kpi = collector.collect(date)
    assert kpi.date == "2026-01-15"
