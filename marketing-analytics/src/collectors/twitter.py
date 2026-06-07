"""X（旧Twitter）API v2 KPI取得モジュール
Phase 1: Bearer Token (App-only) 使用
レート制限: 月15件/15分 → 1日1回のみ実行
"""
import json
import urllib.request
import urllib.error
from dataclasses import dataclass
from datetime import datetime
from src.config import get_secret, JST

@dataclass
class TwitterKPI:
    date: str          # YYYY-MM-DD
    followers: int
    impressions: int
    likes: int
    retweets: int
    replies: int
    tweet_count: int
    engagement_rate: float   # (likes+retweets+replies)/impressions*100
    error: str = ""          # エラー時はここにメッセージ

TWITTER_API_BASE = "https://api.twitter.com/2"  # nosec B105

class TwitterCollector:
    def __init__(self, bearer_token: str = "", dry_run: bool = False):
        self._token = bearer_token or get_secret("X_BEARER_TOKEN")
        self._mock_mode = dry_run or not bool(self._token)
        self._dry_run = dry_run

    def collect(self, date: datetime) -> TwitterKPI:
        """指定日のTwitter KPIを取得する"""
        date_str = date.strftime("%Y-%m-%d")
        if self._mock_mode:
            return self._mock_kpi(date_str)
        try:
            return self._fetch_kpi(date_str)
        except Exception as e:  # noqa: BLE001
            return TwitterKPI(
                date=date_str,
                followers=0, impressions=0, likes=0,
                retweets=0, replies=0, tweet_count=0,
                engagement_rate=0.0,
                error=f"取得失敗: {str(e)[:100]}",
            )

    def _fetch_kpi(self, date_str: str) -> TwitterKPI:
        """X API v2 からKPIを取得"""
        # Step1: ユーザー情報取得
        user_id = self._get_user_id()
        followers = self._get_followers(user_id)
        # Step2: ツイート一覧取得（前日分）
        tweets = self._get_tweets(user_id, date_str)
        impressions = sum(t.get("organic_metrics", {}).get("impression_count", 0) for t in tweets)
        likes = sum(t.get("organic_metrics", {}).get("like_count", 0) for t in tweets)
        retweets = sum(t.get("organic_metrics", {}).get("retweet_count", 0) for t in tweets)
        replies = sum(t.get("organic_metrics", {}).get("reply_count", 0) for t in tweets)
        tweet_count = len(tweets)
        engagement = (likes + retweets + replies) / impressions * 100 if impressions > 0 else 0.0
        return TwitterKPI(
            date=date_str,
            followers=followers,
            impressions=impressions,
            likes=likes,
            retweets=retweets,
            replies=replies,
            tweet_count=tweet_count,
            engagement_rate=round(engagement, 2),
        )

    def _get(self, url: str) -> dict:
        req = urllib.request.Request(url)  # nosec B310
        req.add_header("Authorization", f"Bearer {self._token}")
        with urllib.request.urlopen(req, timeout=15) as resp:  # nosec B310
            return json.loads(resp.read().decode("utf-8"))

    def _get_user_id(self) -> str:
        data = self._get(f"{TWITTER_API_BASE}/users/me")
        return data["data"]["id"]

    def _get_followers(self, user_id: str) -> int:
        data = self._get(f"{TWITTER_API_BASE}/users/{user_id}?user.fields=public_metrics")
        return data["data"]["public_metrics"]["followers_count"]

    def _get_tweets(self, user_id: str, date_str: str) -> list:
        start = f"{date_str}T00:00:00Z"
        end = f"{date_str}T23:59:59Z"
        url = (
            f"{TWITTER_API_BASE}/users/{user_id}/tweets"
            f"?start_time={start}&end_time={end}"
            f"&tweet.fields=organic_metrics&max_results=100"
        )
        try:
            data = self._get(url)
            return data.get("data", [])
        except Exception:  # noqa: BLE001
            return []

    def _mock_kpi(self, date_str: str) -> TwitterKPI:
        """dry-run用モックデータ"""
        return TwitterKPI(
            date=date_str,
            followers=523,
            impressions=12345,
            likes=180,
            retweets=45,
            replies=71,
            tweet_count=2,
            engagement_rate=2.4,
            error="",
        )
