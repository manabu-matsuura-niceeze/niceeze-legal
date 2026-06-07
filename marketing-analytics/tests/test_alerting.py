"""Alerting モジュールのテスト"""
import pytest
from src.alerting.threshold import check_thresholds, Alert


def test_low_engagement_triggers_alert():
    """エンゲージメント率が閾値未満でアラート発火"""
    kpi_data = {"twitter": {"engagement_rate": 1.0}}
    alerts = check_thresholds(kpi_data)
    assert len(alerts) == 1
    assert alerts[0].metric_key == "twitter_engagement_rate"


def test_high_engagement_no_alert():
    """エンゲージメント率が閾値以上でアラートなし"""
    kpi_data = {"twitter": {"engagement_rate": 2.0}}
    alerts = check_thresholds(kpi_data)
    assert len(alerts) == 0


def test_exact_threshold_no_alert():
    """エンゲージメント率が閾値ちょうどでアラートなし"""
    kpi_data = {"twitter": {"engagement_rate": 1.6}}
    alerts = check_thresholds(kpi_data)
    assert len(alerts) == 0


def test_low_youtube_subs_triggers_alert():
    """YouTube登録者数が閾値未満でアラート発火"""
    kpi_data = {"youtube": {"subscribers": 50}}
    alerts = check_thresholds(kpi_data)
    assert len(alerts) == 1
    assert alerts[0].metric_key == "youtube_subscribers"


def test_high_youtube_subs_no_alert():
    """YouTube登録者数が閾値以上でアラートなし"""
    kpi_data = {"youtube": {"subscribers": 100}}
    alerts = check_thresholds(kpi_data)
    assert len(alerts) == 0


def test_empty_kpi_no_alerts():
    """空KPIデータでアラートなし"""
    alerts = check_thresholds({})
    assert alerts == []


def test_multiple_alerts():
    """複数指標が閾値未満で複数アラート"""
    kpi_data = {
        "twitter": {"engagement_rate": 0.5},
        "youtube": {"subscribers": 10},
    }
    alerts = check_thresholds(kpi_data)
    assert len(alerts) == 2


def test_alert_message_content():
    """アラートメッセージの内容確認"""
    kpi_data = {"twitter": {"engagement_rate": 1.0}}
    alerts = check_thresholds(kpi_data)
    assert "Xエンゲージメント率" in alerts[0].message
    assert "未達" in alerts[0].message


def test_alert_threshold_value():
    """アラートの閾値フィールド確認"""
    kpi_data = {"twitter": {"engagement_rate": 1.0}}
    alerts = check_thresholds(kpi_data)
    assert alerts[0].threshold == 1.6


def test_alert_current_value():
    """アラートの現在値フィールド確認"""
    kpi_data = {"twitter": {"engagement_rate": 1.2}}
    alerts = check_thresholds(kpi_data)
    assert alerts[0].current_value == 1.2


def test_youtube_alert_message():
    """YouTube アラートメッセージ確認"""
    kpi_data = {"youtube": {"subscribers": 60}}
    alerts = check_thresholds(kpi_data)
    assert "YouTube登録者数" in alerts[0].message


def test_no_twitter_key_no_twitter_alert():
    """twitterキーなしのKPIはTwitterアラートを発火しない"""
    kpi_data = {"youtube": {"subscribers": 200}}
    alerts = check_thresholds(kpi_data)
    assert all(a.metric_key != "twitter_engagement_rate" for a in alerts)


def test_alert_dataclass_fields():
    """Alertデータクラスのフィールド確認"""
    alert = Alert(
        metric_key="twitter_engagement_rate",
        current_value=1.0,
        threshold=1.6,
        unit="%",
        message="テスト",
    )
    assert alert.metric_key == "twitter_engagement_rate"
    assert alert.unit == "%"
