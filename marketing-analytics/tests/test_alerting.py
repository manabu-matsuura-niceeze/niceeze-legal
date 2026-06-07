"""alerting モジュールテスト"""
import unittest
from src.alerting.threshold import check_thresholds, Alert

class TestThresholds(unittest.TestCase):
    def test_engagement_below_threshold_fires_alert(self):
        kpi = {"twitter": {"engagement_rate": 1.2}}
        alerts = check_thresholds(kpi)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].metric_key, "twitter_engagement_rate")

    def test_engagement_above_threshold_no_alert(self):
        kpi = {"twitter": {"engagement_rate": 2.5}}
        alerts = check_thresholds(kpi)
        self.assertEqual(len(alerts), 0)

    def test_engagement_at_threshold_no_alert(self):
        kpi = {"twitter": {"engagement_rate": 1.6}}
        alerts = check_thresholds(kpi)
        self.assertEqual(len(alerts), 0)

    def test_youtube_below_threshold_fires_alert(self):
        kpi = {"youtube": {"subscribers": 50}}
        alerts = check_thresholds(kpi)
        keys = [a.metric_key for a in alerts]
        self.assertIn("youtube_subscribers", keys)

    def test_youtube_above_threshold_no_alert(self):
        kpi = {"youtube": {"subscribers": 100}}
        alerts = check_thresholds(kpi)
        self.assertEqual(len(alerts), 0)

    def test_empty_kpi_no_alert(self):
        alerts = check_thresholds({})
        self.assertEqual(len(alerts), 0)

    def test_multiple_alerts(self):
        kpi = {
            "twitter": {"engagement_rate": 0.5},
            "youtube": {"subscribers": 10},
        }
        alerts = check_thresholds(kpi)
        self.assertGreaterEqual(len(alerts), 2)

    def test_alert_has_message(self):
        kpi = {"twitter": {"engagement_rate": 1.0}}
        alerts = check_thresholds(kpi)
        self.assertTrue(len(alerts[0].message) > 0)

    def test_alert_current_value(self):
        kpi = {"twitter": {"engagement_rate": 1.2}}
        alerts = check_thresholds(kpi)
        self.assertEqual(alerts[0].current_value, 1.2)

    def test_alert_threshold_value(self):
        kpi = {"twitter": {"engagement_rate": 1.2}}
        alerts = check_thresholds(kpi)
        self.assertEqual(alerts[0].threshold, 1.6)

    def test_none_value_ignored(self):
        kpi = {"twitter": {"engagement_rate": None}}
        alerts = check_thresholds(kpi)
        self.assertEqual(len(alerts), 0)

if __name__ == "__main__":
    unittest.main()
