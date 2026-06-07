"""reporter モジュールテスト"""
import unittest
from datetime import datetime, timezone, timedelta
from src.config import JST
from src.reporter.markdown import generate_report
from src.reporter.drive import DriveReporter
from src.reporter.notifier import SlackNotifier
from src.alerting.threshold import Alert

SAMPLE_DATE = datetime(2026, 6, 6, 0, 0, 0, tzinfo=JST)

SAMPLE_KPI = {
    "twitter": {
        "followers": 523, "impressions": 12345, "likes": 180,
        "retweets": 45, "replies": 71, "tweet_count": 2,
        "engagement_rate": 2.4, "error": "",
    }
}


class TestMarkdownReporter(unittest.TestCase):
    def test_generate_returns_string(self):
        result = generate_report(SAMPLE_DATE, SAMPLE_KPI, [])
        self.assertIsInstance(result, str)

    def test_title_in_report(self):
        result = generate_report(SAMPLE_DATE, SAMPLE_KPI, [])
        self.assertIn("NiceEze マーケティング KPI 日次報告", result)

    def test_date_formatted_ja(self):
        result = generate_report(SAMPLE_DATE, SAMPLE_KPI, [])
        self.assertIn("2026年06月06日", result)

    def test_followers_in_report(self):
        result = generate_report(SAMPLE_DATE, SAMPLE_KPI, [])
        self.assertIn("523", result)

    def test_engagement_rate_in_report(self):
        result = generate_report(SAMPLE_DATE, SAMPLE_KPI, [])
        self.assertIn("2.4", result)

    def test_no_alert_shows_ok(self):
        result = generate_report(SAMPLE_DATE, SAMPLE_KPI, [])
        self.assertIn("✅", result)

    def test_alert_shows_warning(self):
        alert = Alert(
            metric_key="twitter_engagement_rate",
            current_value=1.2, threshold=1.6, unit="%",
            message="Xエンゲージメント率: 1.2% (目標 1.6% 未達)",
        )
        result = generate_report(SAMPLE_DATE, SAMPLE_KPI, [alert])
        self.assertIn("⚠️", result)
        self.assertIn("1.2%", result)

    def test_error_in_twitter_shows_message(self):
        kpi = {"twitter": {"error": "取得失敗: 401 Unauthorized"}}
        result = generate_report(SAMPLE_DATE, kpi, [])
        self.assertIn("取得失敗", result)

    def test_action_section_present(self):
        result = generate_report(SAMPLE_DATE, SAMPLE_KPI, [])
        self.assertIn("翌日のアクション", result)


class TestDriveReporter(unittest.TestCase):
    def test_dry_run_returns_dry_run_str(self):
        dr = DriveReporter(dry_run=True)
        result = dr.upload("MKT_KPI_20260606.md", "# test", "Marketing_KPI/2026-06")
        self.assertIn("[DRY-RUN]", result)

    def test_dry_run_contains_filename(self):
        dr = DriveReporter(dry_run=True)
        result = dr.upload("MKT_KPI_20260606.md", "# test", "Marketing_KPI/2026-06")
        self.assertIn("MKT_KPI_20260606.md", result)


class TestSlackNotifier(unittest.TestCase):
    def test_dry_run_no_alerts_returns_true(self):
        n = SlackNotifier(dry_run=True)
        self.assertTrue(n.send_alert([], SAMPLE_DATE))

    def test_dry_run_with_alerts_returns_true(self):
        n = SlackNotifier(dry_run=True)
        alert = Alert("twitter_engagement_rate", 1.2, 1.6, "%", "テスト")
        self.assertTrue(n.send_alert([alert], SAMPLE_DATE, "https://drive.google.com/test"))

    def test_dry_run_failure_alert_returns_true(self):
        n = SlackNotifier(dry_run=True)
        self.assertTrue(n.send_failure_alert("全件取得失敗"))


if __name__ == "__main__":
    unittest.main()
