"""
ニュースクローラー — 8カテゴリ・24時間監視 (Ver 1.0)
MARKETING部 特急MVP Week1
FinOps: 月額¥5,000以内 / PII不使用 / bandit 0件
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ──────────────────────────────────────────
# 8カテゴリ定義
# ──────────────────────────────────────────

NEWS_CATEGORIES = {
    'business':    'ビジネス・経済',
    'technology':  'テクノロジー・IT',
    'lifestyle':   'ライフスタイル・トレンド',
    'food':        '食品・グルメ',
    'health':      '健康・ウェルネス',
    'ecommerce':   'EC・流通・物流',
    'marketing':   'マーケティング・SNS',
    'realestate':  '不動産・住宅',
}

CRAWL_INTERVAL_HOURS = 24   # クロール間隔（24時間監視）
MAX_ARTICLES_PER_CAT = 20   # カテゴリあたり最大記事数


# ──────────────────────────────────────────
# データモデル
# ──────────────────────────────────────────

@dataclass
class NewsArticle:
    """ニュース記事1件"""
    title: str
    summary: str
    url: str
    category_key: str
    published_at: str
    source: str
    relevance_score: float = 0.0   # 0.0〜1.0（関連度スコア）
    article_id: str = ''

    def __post_init__(self) -> None:
        if not self.article_id:
            self.article_id = hashlib.sha256(
                f'{self.url}:{self.published_at}'.encode()
            ).hexdigest()

    @property
    def category_label(self) -> str:
        return NEWS_CATEGORIES.get(self.category_key, self.category_key)

    def to_dict(self) -> dict:
        return {
            'article_id': self.article_id,
            'title': self.title,
            'summary': self.summary,
            'url': self.url,
            'category_key': self.category_key,
            'category_label': self.category_label,
            'published_at': self.published_at,
            'source': self.source,
            'relevance_score': self.relevance_score,
        }


@dataclass
class CrawlResult:
    """クロール結果（全カテゴリ）"""
    articles: list[NewsArticle] = field(default_factory=list)
    crawled_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def by_category(self, category_key: str) -> list[NewsArticle]:
        return [a for a in self.articles if a.category_key == category_key]

    def top_articles(self, n: int = 5) -> list[NewsArticle]:
        return sorted(self.articles, key=lambda a: a.relevance_score, reverse=True)[:n]

    def to_dict(self) -> dict:
        return {
            'crawled_at': self.crawled_at,
            'total_articles': len(self.articles),
            'by_category': {
                k: len(self.by_category(k)) for k in NEWS_CATEGORIES
            },
            'top_5': [a.to_dict() for a in self.top_articles(5)],
        }


# ──────────────────────────────────────────
# クローラーエンジン
# ──────────────────────────────────────────

class NewsCrawler:
    """
    ニュースクローラー。
    MVP段階: RSS/Google News RSS（認証不要・無料）を使用。
    G3でClaudeAPI連携による要約・関連度スコアリングを追加。
    FinOps: RSS取得はGCPコスト0円（Cloud Functions）。

    【松浦CEO要件定義待ち】
    - NewsAPI.org連携（月10万リクエスト無料プランあり）の採用可否
    - 独自スクレイピング（利用規約確認要）の採用可否
    """

    RSS_SOURCES = {
        'business':   'https://news.google.com/rss/search?q=EC+物流+ビジネス&hl=ja&gl=JP',
        'technology': 'https://news.google.com/rss/search?q=テクノロジー+AI+DX&hl=ja&gl=JP',
        'lifestyle':  'https://news.google.com/rss/search?q=ライフスタイル+トレンド&hl=ja&gl=JP',
        'food':       'https://news.google.com/rss/search?q=食品+グルメ+流通&hl=ja&gl=JP',
        'health':     'https://news.google.com/rss/search?q=健康+ウェルネス&hl=ja&gl=JP',
        'ecommerce':  'https://news.google.com/rss/search?q=EC+通販+楽天+Amazon&hl=ja&gl=JP',
        'marketing':  'https://news.google.com/rss/search?q=マーケティング+SNS+X+Instagram&hl=ja&gl=JP',
        'realestate': 'https://news.google.com/rss/search?q=不動産+マンション+住宅&hl=ja&gl=JP',
    }

    def crawl_rss(self, category_key: str) -> list[NewsArticle]:
        """
        Google News RSS から記事を取得。
        本番ではCloud Functions（CRAWL_INTERVAL_HOURS=24）から呼出し。
        MVP: urllib標準ライブラリのみ使用（pip不要）。
        """
        import urllib.request
        import xml.etree.ElementTree as ET  # nosec B405 — hardcoded Google News RSS, no user input

        articles = []
        url = self.RSS_SOURCES.get(category_key, '')
        if not url:
            return articles

        try:
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'NiceEze-NewsCrawler/1.0 (niceeze.com)'}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310 — URL from hardcoded RSS_SOURCES dict
                tree = ET.parse(resp)  # nosec B314 — hardcoded Google News RSS, not user-supplied XML
            root = tree.getroot()
            channel = root.find('channel')
            if channel is None:
                return articles
            for item in channel.findall('item')[:MAX_ARTICLES_PER_CAT]:
                title = item.findtext('title', '')
                desc = item.findtext('description', '')
                link = item.findtext('link', '')
                pub = item.findtext('pubDate', datetime.now(timezone.utc).isoformat())
                # 簡易関連度スコア（タイトル文字数ベース / G3でClaudeAPI置換）
                score = min(1.0, len(title) / 80)
                articles.append(NewsArticle(
                    title=title,
                    summary=desc[:200] if desc else '',
                    url=link,
                    category_key=category_key,
                    published_at=pub,
                    source='Google News RSS',
                    relevance_score=round(score, 3),
                ))
        except Exception:
            # ネットワークエラー時はモックデータで代替（MVP）
            articles = self._mock_articles(category_key)
        return articles

    def _mock_articles(self, category_key: str) -> list[NewsArticle]:
        """ネットワーク非接続時のモックデータ"""
        label = NEWS_CATEGORIES.get(category_key, category_key)
        return [
            NewsArticle(
                title=f'【{label}】サンプル記事{i+1}: トレンド情報',
                summary=f'{label}に関する最新動向。詳細はURLを参照。',
                url=f'https://example.com/{category_key}/{i+1}',
                category_key=category_key,
                published_at=datetime.now(timezone.utc).isoformat(),
                source='Mock',
                relevance_score=round(0.9 - i * 0.1, 1),
            )
            for i in range(3)
        ]

    def crawl_all(self) -> CrawlResult:
        """全8カテゴリをクロール"""
        result = CrawlResult()
        for category_key in NEWS_CATEGORIES:
            articles = self.crawl_rss(category_key)
            result.articles.extend(articles)
        return result
