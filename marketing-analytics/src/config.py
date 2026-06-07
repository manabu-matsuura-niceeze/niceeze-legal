import os
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
APP_VERSION = "1.0.0"

ALERT_THRESHOLDS = {
    "twitter_engagement_rate": {"warn": 1.6, "unit": "%"},
    "twitter_followers_monthly": {"warn": 400, "unit": "人（月末見込み）"},
    "instagram_reach_monthly": {"warn": 8000, "unit": "人/月"},
    "note_pv_monthly": {"warn": 400, "unit": "PV/月"},
    "youtube_subscribers": {"warn": 80, "unit": "人"},
    "budget_usage_rate": {"warn": 90, "unit": "% （予算消化率）"},
}

DRIVE_FOLDER_ID_AUDIT = os.environ.get("DRIVE_FOLDER_ID_AUDIT", "1Q3ahaND6cUQ8fBU5amwx8C79HC9JMxHI")
NOTE_USERNAME = os.environ.get("NOTE_USERNAME", "niceeze")
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "serene-bonbon-236821")

def get_jst_yesterday() -> datetime:
    """JSTの前日日付を返す"""
    now_jst = datetime.now(JST)
    yesterday_jst = now_jst - timedelta(days=1)
    return yesterday_jst.replace(hour=0, minute=0, second=0, microsecond=0)

def get_secret(secret_name: str) -> str:
    """環境変数からSecretを取得（本番はGCP Secret Manager）"""
    val = os.environ.get(secret_name, "")
    return val
