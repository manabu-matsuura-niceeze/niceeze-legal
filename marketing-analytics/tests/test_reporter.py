"""Reporter モジュールのテスト"""
import pytest
from datetime import datetime, timezone, timedelta
from src.reporter.markdown import generate_report, WEEKDAY_JA
from src.reporter.drive import DriveReporter
from src.reporter.notifier import SlackNotifier
from src.alerting.threshold import Alert

JST = timezone(timedelta(hours=9))
TEST_DATE = datetime(2026, 6, 6, 0, 0, 0, tzinfo=JST)  # 土曜日

SAMPLE_KPI = {
    "twitter": {
        "followers": 523,
        "impressions": 12345,
        "likes": 180,
        "retweets": 45,
        "replies": 71,
        "tweet_count": 2,
        "engagement_rate": 2.4,
        "error": "",
    }
}

SAMPLE_ALERT = Alert(
    metric_key="twitter_engagement_rate",
    current_value=1.2,
    threshold=1.6,
    unit="%",
    message="Xエンゲージメント率: 1.2% (目標 1.6% 未達)",
)


def test_generate_report_returns_string():
    result = generate_report(TEST_DATE, SAMPLE_KPI, [])
    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_report_contains_header():
    result = generate_report(TEST_DATE, SAMPLE_KPI, [])
    assert "NiceEze マーケティング KPI 日次報告" in result


def test_date_format_japanese():
    result = generate_report(TEST_DATE, SAMPLE_KPI, [])
    assert "2026年06月06日" in result


def test_date_includes_weekday():
    result = generate_report(TEST_DATE, SAMPLE_KPI, [])
    # 2026-06-06 は土曜日
    assert "土" in result


def test_no_alerts_shows_check():
    result = generate_report(TEST_DATE, SAMPLE_KPI, [])
    assert "✅ 全KPI目標値クリア" in result


def test_with_alerts_shows_warning():
    result = generate_report(TEST_DATE, SAMPLE_KPI, [SAMPLE_ALERT])
    assert "⚠️" in result


def test_alert_message_in_report():
    result = generate_report(TEST_DATE, SAMPLE_KPI, [SAMPLE_ALERT])
    assert "Xエンゲージメント率" in result


def test_twitter_impressions_in_report():
    result = generate_report(TEST_DATE, SAMPLE_KPI, [])
    assert "12,345" in result


def test_twitter_engagement_in_report():
    result = generate_report(TEST_DATE, SAMPLE_KPI, [])
    assert "2.4%" in result


def test_app_version_in_report():
    from src.config import APP_VERSION
    result = generate_report(TEST_DATE, SAMPLE_KPI, [])
    assert APP_VERSION in result


def test_drive_reporter_dry_run_returns_dry_run_string():
    reporter = DriveReporter(dry_run=True)
    result = reporter.upload("test.md", "content", "Marketing_KPI/2026-06")
    assert "[DRY-RUN]" in result


def test_drive_reporter_dry_run_contains_filename():
    reporter = DriveReporter(dry_run=True)
    result = reporter.upload("MKT_KPI_20260606.md", "content", "Marketing_KPI/2026-06")
    assert "MKT_KPI_20260606.md" in result


def test_slack_notifier_dry_run_returns_true():
    notifier = SlackNotifier(dry_run=True)
    result = notifier.send_alert([SAMPLE_ALERT], TEST_DATE, "http://example.com")
    assert result is True


def test_slack_no_alerts_returns_true():
    notifier = SlackNotifier(dry_run=True)
    result = notifier.send_alert([], TEST_DATE, "")
    assert result is True


def test_slack_failure_alert_dry_run():
    notifier = SlackNotifier(dry_run=True)
    result = notifier.send_failure_alert("エラーが発生しました")
    assert result is True


def test_twitter_error_shows_warning_in_report():
    kpi_with_error = {"twitter": {"error": "Connection failed"}}
    result = generate_report(TEST_DATE, kpi_with_error, [])
    assert "取得失敗" in result


def test_report_contains_action_section():
    result = generate_report(TEST_DATE, SAMPLE_KPI, [])
    assert "翌日のアクション" in result
