"""KPIアラート判定モジュール"""
from dataclasses import dataclass
from src.config import ALERT_THRESHOLDS

@dataclass
class Alert:
    metric_key: str
    current_value: float
    threshold: float
    unit: str
    message: str

def check_thresholds(kpi_data: dict) -> list[Alert]:
    """KPIデータをアラート閾値と比較して発火リストを返す"""
    alerts = []
    
    # Twitter エンゲージメント率
    eng = kpi_data.get("twitter", {}).get("engagement_rate")
    if eng is not None:
        thr = ALERT_THRESHOLDS["twitter_engagement_rate"]["warn"]
        unit = ALERT_THRESHOLDS["twitter_engagement_rate"]["unit"]
        if eng < thr:
            alerts.append(Alert(
                metric_key="twitter_engagement_rate",
                current_value=eng,
                threshold=thr,
                unit=unit,
                message=f"Xエンゲージメント率: {eng}{unit} (目標 {thr}{unit} 未達)",
            ))
    
    # YouTube登録者数
    yt_subs = kpi_data.get("youtube", {}).get("subscribers")
    if yt_subs is not None:
        thr = ALERT_THRESHOLDS["youtube_subscribers"]["warn"]
        unit = ALERT_THRESHOLDS["youtube_subscribers"]["unit"]
        if yt_subs < thr:
            alerts.append(Alert(
                metric_key="youtube_subscribers",
                current_value=yt_subs,
                threshold=thr,
                unit=unit,
                message=f"YouTube登録者数: {yt_subs}{unit} (目標 {thr}{unit} 未達)",
            ))
    
    return alerts
