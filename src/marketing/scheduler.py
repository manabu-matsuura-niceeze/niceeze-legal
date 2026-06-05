"""
配信スケジューラー — 朝8:00 / 夜19:00 (Ver 1.0)
MARKETING部 特急MVP Week1
Cloud Functions エントリポイント（HTTP trigger）
FinOps: 月額¥5,000以内 / PII不使用 / bandit 0件
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .news_crawler import NewsCrawler, CrawlResult, NEWS_CATEGORIES
from .content_generator import ContentGenerator, ContentInput, GeneratedContent
from .delivery_log import DeliveryLog
from .x_poster import XPoster


# ──────────────────────────────────────────
# スケジュール定数
# ──────────────────────────────────────────

MORNING_HOUR_JST = 8   # 朝配信: 08:00 JST
EVENING_HOUR_JST = 19  # 夜配信: 19:00 JST
JST_OFFSET_HOURS = 9   # UTC+9

# MVP対象カテゴリ（スケジューラー起動ごとに全カテゴリ処理）
SCHEDULE_CATEGORIES = list(NEWS_CATEGORIES.keys())


# ──────────────────────────────────────────
# 実行結果モデル
# ──────────────────────────────────────────

@dataclass
class ScheduleRun:
    """スケジューラー1回の実行結果"""
    run_type: str              # 'morning' | 'evening' | 'manual'
    triggered_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    crawl_result: Optional[CrawlResult] = None
    generated_contents: list[GeneratedContent] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    x_posts_sent: int = 0

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> dict:
        return {
            'run_type': self.run_type,
            'triggered_at': self.triggered_at,
            'success': self.success,
            'crawled_articles': len(self.crawl_result.articles) if self.crawl_result else 0,
            'generated_contents': len(self.generated_contents),
            'x_posts_sent': self.x_posts_sent,
            'errors': self.errors,
            'top_topics': [
                {
                    'topic': c.input_ref.topic,
                    'category': c.input_ref.category,
                    'trend_score': c.input_ref.trend_score,
                }
                for c in self.generated_contents[:3]
            ],
        }


# ──────────────────────────────────────────
# スケジューラーエンジン
# ──────────────────────────────────────────

class ContentScheduler:
    """
    朝夕配信スケジューラー。
    Cloud Functions HTTP triggerから呼び出す。
    FinOps: Cloud Functions無料枠（月200万回）内で運用。
    G3でClaude APIによる品質向上予定。
    """

    def __init__(self) -> None:
        self.crawler = NewsCrawler()
        self.generator = ContentGenerator()
        self.delivery_log = DeliveryLog()
        self.x_poster = XPoster()

    def detect_run_type(self) -> str:
        """現在時刻からmoring/eveningを判定（UTC→JST変換）"""
        now_jst_hour = (datetime.now(timezone.utc).hour + JST_OFFSET_HOURS) % 24
        if now_jst_hour < 12:
            return 'morning'
        return 'evening'

    def _select_top_topics(self, crawl_result: CrawlResult, max_topics: int = 3) -> list[tuple[str, str, float]]:
        """
        クロール結果から配信トピックを選定。
        戻り値: [(topic, category_label, trend_score), ...]
        """
        top = crawl_result.top_articles(max_topics)
        topics = []
        for article in top:
            topic = article.title[:40].strip()
            category_label = article.category_label
            trend_score = min(1.0, article.relevance_score)
            topics.append((topic, category_label, trend_score))
        return topics

    def run(self, run_type: Optional[str] = None) -> ScheduleRun:
        """
        スケジューラーメイン実行。
        Cloud Functions HTTP trigger → run() → ScheduleRun結果を返す。
        """
        if run_type is None:
            run_type = self.detect_run_type()

        result = ScheduleRun(run_type=run_type)

        # Step 1: ニュースクロール
        try:
            result.crawl_result = self.crawler.crawl_all()
        except Exception as exc:
            result.errors.append(f'crawl_error: {exc}')
            return result

        # Step 2: トピック選定 → コンテンツ生成
        try:
            topics = self._select_top_topics(result.crawl_result)
            for topic, category_label, trend_score in topics:
                inp = ContentInput(
                    topic=topic,
                    category=category_label,
                    trend_score=trend_score,
                    tone='professional' if run_type == 'morning' else 'casual',
                )
                content = self.generator.generate_all(inp)
                result.generated_contents.append(content)
        except Exception as exc:
            result.errors.append(f'generation_error: {exc}')

        # Step 3: X投稿文をX APIに投稿
        try:
            for content in result.generated_contents:
                x_result = self.x_poster.post(content.x_post)
                if x_result.success:
                    self.delivery_log.add(
                        content_type='x_post',
                        topic=content.input_ref.topic,
                        category=content.input_ref.category,
                        char_count=len(x_result.text),
                    )
                    result.x_posts_sent += 1
        except Exception as exc:
            result.errors.append(f'x_post_error: {exc}')

        return result


# ──────────────────────────────────────────
# Cloud Functions HTTP エントリポイント
# ──────────────────────────────────────────

def run_schedule(request=None) -> dict:
    """
    Cloud Functions HTTP trigger エントリポイント。
    Cloud Schedulerから朝8:00/夜19:00(JST)に呼び出す。

    デプロイ設定（G3実装時）:
      gcloud functions deploy marketing-scheduler
        --runtime python312
        --trigger-http
        --entry-point run_schedule
        --region asia-northeast1
        --memory 256MB
        --timeout 120s

    Cloud Scheduler設定:
      朝: cron "0 23 * * *" (UTC) = 08:00 JST
      夜: cron "0 10 * * *" (UTC) = 19:00 JST
    """
    run_type = None
    if request is not None and hasattr(request, 'args'):
        run_type = request.args.get('run_type')

    scheduler = ContentScheduler()
    result = scheduler.run(run_type=run_type)
    return result.to_dict()
