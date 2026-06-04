"""
4フォーマット自動生成エンジン (Ver 1.0)
MARKETING部 特急MVP Week1
X投稿 / メルマガHTML / Note原稿 / YouTube台本
FinOps: 月額¥5,000以内 / PII不使用 / bandit 0件
判断①確定: note.com自動投稿G4以降保留 / 判断②確定: YouTube台本のみ（アップロード手動）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ──────────────────────────────────────────
# 定数
# ──────────────────────────────────────────

X_CHAR_LIMIT = 140          # X（旧Twitter）文字数制限
NEWSLETTER_MAX_CHARS = 5000 # メルマガ本文最大文字数


# ──────────────────────────────────────────
# データモデル
# ──────────────────────────────────────────

@dataclass
class ContentInput:
    """コンテンツ生成の入力"""
    topic: str                    # テーマ・キーワード
    category: str                 # カテゴリ（8カテゴリ）
    product_name: Optional[str] = None  # 商品名（オプション）
    trend_score: float = 0.5      # RES-A02トレンドスコア連携（0.0〜1.0）
    tone: str = 'professional'    # professional / casual / urgent


@dataclass
class GeneratedContent:
    """生成された4フォーマットコンテンツ"""
    input_ref: ContentInput
    x_post: str = ''
    x_hashtags: list[str] = field(default_factory=list)
    newsletter_subject: str = ''
    newsletter_html: str = ''
    note_markdown: str = ''
    youtube_title: str = ''
    youtube_description: str = ''
    youtube_script: str = ''
    youtube_tags: list[str] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def x_full_text(self) -> str:
        tags = ' '.join(f'#{t}' for t in self.x_hashtags)
        return f'{self.x_post}\n{tags}'[:X_CHAR_LIMIT]

    def to_dict(self) -> dict:
        return {
            'topic': self.input_ref.topic,
            'category': self.input_ref.category,
            'generated_at': self.generated_at,
            'x': {
                'post': self.x_post,
                'hashtags': self.x_hashtags,
                'full_text': self.x_full_text,
                'char_count': len(self.x_full_text),
            },
            'newsletter': {
                'subject': self.newsletter_subject,
                'html_length': len(self.newsletter_html),
            },
            'note': {
                'markdown_length': len(self.note_markdown),
            },
            'youtube': {
                'title': self.youtube_title,
                'description': self.youtube_description[:200],
                'script_length': len(self.youtube_script),
                'tags': self.youtube_tags,
            },
        }


# ──────────────────────────────────────────
# 生成エンジン（MVP: テンプレートベース / G3でClaude API連携）
# ──────────────────────────────────────────

class ContentGenerator:
    """
    4フォーマット自動生成エンジン。
    MVP: 構造化テンプレートで高品質なドラフトを生成。
    G3: Cloud Run proxy経由でClaude APIにより品質向上。
    FinOps: MVPはGCPコスト0円。G3でClaudeAPI費用発生（月額¥2,250〜4,500想定）。
    """

    # ── X投稿 ──────────────────────────────

    def generate_x(self, inp: ContentInput) -> tuple[str, list[str]]:
        trend_emoji = '🚀' if inp.trend_score > 0.7 else '📊' if inp.trend_score > 0.4 else '💡'
        if inp.product_name:
            body = f'{trend_emoji}【{inp.category}】{inp.product_name}が注目されています。\n{inp.topic}に関する最新トレンドをお届けします。'
        else:
            body = f'{trend_emoji}【{inp.category}】{inp.topic}の最新動向をご紹介。NiceEzeが厳選した情報をお届けします。'
        hashtags = [
            inp.category.replace('・', '').replace(' ', ''),
            'NiceEze',
            'EC',
            inp.topic.split('　')[0][:10].replace(' ', ''),
        ]
        return body[:100], [h for h in hashtags if h][:4]

    # ── メルマガ ─────────────────────────────

    def generate_newsletter(self, inp: ContentInput) -> tuple[str, str]:
        subject = f'【NiceEze】{inp.category}トレンド速報 | {inp.topic}'
        html = f"""<!DOCTYPE html>
<html lang="ja">
<head><meta charset="UTF-8"><title>{subject}</title></head>
<body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px;color:#1e293b;">
  <div style="background:#1a3a5c;padding:20px;border-radius:8px 8px 0 0;">
    <h1 style="color:white;font-size:18px;margin:0;">NiceEze マーケティングレポート</h1>
    <p style="color:#bfd7ed;font-size:12px;margin:4px 0 0;">{datetime.now(timezone.utc).strftime('%Y年%m月%d日')}</p>
  </div>
  <div style="background:#f0f4f8;padding:20px;border-radius:0 0 8px 8px;">
    <h2 style="color:#1a3a5c;font-size:16px;">📊 {inp.category}トレンド: {inp.topic}</h2>
    <p>トレンドスコア: <strong style="color:#f5a623;">{inp.trend_score:.0%}</strong></p>
    <p>本週の{inp.category}分野では、<strong>{inp.topic}</strong>に関する動向が注目されています。</p>
    {'<p>対象商品: <strong>' + inp.product_name + '</strong></p>' if inp.product_name else ''}
    <hr style="border:1px solid #cbd5e1;">
    <h3 style="color:#1a3a5c;">今週のポイント</h3>
    <ul>
      <li>{inp.topic}に関連する需要が高まっています</li>
      <li>競合他社の動向を継続的にモニタリング中</li>
      <li>仕入れタイミングの最適化をご検討ください</li>
    </ul>
    <div style="background:#1a3a5c;padding:15px;border-radius:6px;margin-top:20px;">
      <p style="color:white;font-size:12px;margin:0;">
        © 2026 株式会社NiceEze | 配信停止はこちら<br>
        本メールはNiceEze自律マーケティングシステムが自動生成しました。
      </p>
    </div>
  </div>
</body>
</html>"""
        return subject, html

    # ── Note原稿 ──────────────────────────────

    def generate_note(self, inp: ContentInput) -> str:
        trend_level = '急成長中' if inp.trend_score > 0.7 else '注目中' if inp.trend_score > 0.4 else '定点観測中'
        return f"""# {inp.category}トレンド分析: {inp.topic}

**カテゴリ**: {inp.category}
**トレンドレベル**: {trend_level}（スコア: {inp.trend_score:.0%}）
**公開日**: {datetime.now(timezone.utc).strftime('%Y年%m月%d日')}

---

## はじめに

{inp.topic}について、NiceEzeのリサーチシステム（RES-A01/A02）が分析したデータをもとに解説します。

## 現在の市場動向

{inp.category}分野において、{inp.topic}は現在**{trend_level}**のステータスにあります。

{'対象商品「' + inp.product_name + '」は特に注目度が高い状況です。' if inp.product_name else ''}

## データから見るポイント

- **トレンドスコア**: {inp.trend_score:.0%}（NiceEze独自指標）
- **分析期間**: 直近30日間のデータを基に算出
- **対象カテゴリ**: {inp.category}

## まとめ

{inp.topic}に関するトレンドを継続的にモニタリングし、最適なタイミングでの意思決定をサポートします。

---

*本記事はNiceEze自律マーケティングシステムが生成しました。*
*※ note.com への投稿は手動で行ってください（自動投稿はG4以降対応予定）*
"""

    # ── YouTube台本 ───────────────────────────

    def generate_youtube(self, inp: ContentInput) -> tuple[str, str, str, list[str]]:
        title = f'【{inp.category}】{inp.topic} — NiceEzeトレンド分析{datetime.now(timezone.utc).strftime("%Y年%m月")}'
        description = f"""{inp.topic}に関する最新トレンドをNiceEzeが分析・解説します。

📊 本動画の内容:
- {inp.category}の最新市場動向
- トレンドスコア分析（NiceEze独自指標）
- 仕入れ・マーケティングへの活用方法

🔔 チャンネル登録で最新情報をお届け！

#NiceEze #{inp.category.replace('・', '')} #{inp.topic.split('　')[0][:15]}

© 2026 株式会社NiceEze
※ 本動画はNiceEze自律マーケティングシステムが台本を自動生成しました。アップロードは手動で行ってください。"""

        script = f"""【YouTube台本】{title}
作成日: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}
※ このファイルはNiceEze自律マーケティングシステムが自動生成した台本です。
※ YouTube Data APIによる自動アップロードは対象外（手動アップロード）です。

---

【オープニング: 0:00〜0:30】
「こんにちは、NiceEzeです。今日は{inp.category}の最新トレンド、特に{inp.topic}について詳しく解説していきます。」
「このチャンネルでは、EC・物流・マーケティングに役立つデータ分析をお届けしています。チャンネル登録がまだの方はぜひよろしくお願いします。」

---

【本編1: トレンド概況 0:30〜2:00】
「まず、現在の{inp.category}市場の概況からお伝えします。」
「NiceEzeの独自指標によると、{inp.topic}のトレンドスコアは現在{inp.trend_score:.0%}を記録しています。」
「{'' if inp.trend_score <= 0.7 else 'これは急成長ゾーンに相当し、早期の対応が推奨されます。'}」
{'「今回注目の商品は「' + inp.product_name + '」です。」' if inp.product_name else ''}

---

【本編2: データ分析 2:00〜4:00】
「次に、具体的なデータを見ていきましょう。」
「直近30日間のランキングデータと検索ボリュームを分析したところ——」
「（グラフ・図表を挿入してください）」
「このトレンドは、{inp.category}全体の動向とも一致しており——」

---

【本編3: 活用方法 4:00〜5:30】
「では、このデータをどう活用すればよいでしょうか。」
「1つ目は、仕入れタイミングの最適化です。」
「2つ目は、マーケティングコンテンツへの活用です。」
「3つ目は、競合他社との差別化です。」

---

【クロージング: 5:30〜6:00】
「今日は{inp.topic}のトレンド分析をお届けしました。」
「チャンネル登録・高評価をよろしくお願いします。次回もお楽しみに！」

---
【サムネイル案】
- 背景: NiceEzeブランドカラー（濃紺 #1a3a5c）
- テキスト: 「{inp.topic}」（オレンジ #f5a623 大文字）
- スコア表示: 「トレンド {inp.trend_score:.0%}」
"""
        tags = [
            inp.category.replace('・', ''),
            'NiceEze', 'EC', 'トレンド分析', 'マーケティング',
            inp.topic.split('　')[0][:15],
        ]
        return title, description, script, tags[:6]

    # ── 統合生成 ────────────────────────────

    def generate_all(self, inp: ContentInput) -> GeneratedContent:
        content = GeneratedContent(input_ref=inp)
        content.x_post, content.x_hashtags = self.generate_x(inp)
        content.newsletter_subject, content.newsletter_html = self.generate_newsletter(inp)
        content.note_markdown = self.generate_note(inp)
        (content.youtube_title, content.youtube_description,
         content.youtube_script, content.youtube_tags) = self.generate_youtube(inp)
        return content
