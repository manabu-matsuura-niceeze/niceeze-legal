"""
NiceEze 即時通知エンジン (Ver 1.0)
報連相体制アップグレード対応 — 松浦CEO承認 2026-06-05
Gmail SMTP経由で即時メール通知を送信する。
FinOps: 月額¥0（Gmail SMTP無料）/ PII最小化 / bandit 0件
"""
from __future__ import annotations

import os
import smtplib
import ssl
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional


# ──────────────────────────────────────────
# 定数
# ──────────────────────────────────────────

CEO_EMAIL = 'manabu.matsuura@niceeze.com'
SENDER_EMAIL = 'niceeze.code.notify@gmail.com'   # 送信用Gmailアカウント
SMTP_HOST = 'smtp.gmail.com'
SMTP_PORT = 587

# 種別定数
KIND_DONE    = '完了'
KIND_PENDING = '判断待ち'
KIND_BLOCKER = 'ブロッカー'
KIND_GATE    = 'ハードゲート承認'

# レベル定数（Lv.0〜3）
LV_AUTO     = 0  # Code自律処理（報告不要）
LV_NOTIFY   = 1  # 完了報告のみ
LV_ESCALATE = 2  # Code→補佐→CEO
LV_URGENT   = 3  # 即時エスカレーション


# ──────────────────────────────────────────
# 報告データモデル
# ──────────────────────────────────────────

@dataclass
class NotifyPayload:
    """即時報告ペイロード"""
    kind: str                  # KIND_DONE / KIND_PENDING / KIND_BLOCKER / KIND_GATE
    content: str               # 1〜2行の内容
    next_action: str           # 次にCodeがやること
    ceo_decision_required: bool = False
    level: int = LV_NOTIFY
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime('%H:%M')
    )

    @property
    def subject(self) -> str:
        """メール件名フォーマット"""
        summary = self.content[:30].replace('\n', ' ')
        return f'[NiceEze CODE] {self.kind} - {summary} {self.timestamp}'

    @property
    def chat_message(self) -> str:
        """チャット用フォーマット（爆速簡略版）"""
        ceo_flag = '要' if self.ceo_decision_required else '不要'
        return (
            f'【即時報告】{self.timestamp}\n'
            f'種別：{self.kind}\n'
            f'内容：{self.content}\n'
            f'次アクション：{self.next_action}\n'
            f'CEO判断：{ceo_flag}'
        )

    @property
    def email_body(self) -> str:
        """メール本文（HTML）"""
        ceo_flag = '🔴 要' if self.ceo_decision_required else '✅ 不要'
        level_label = ['Lv.0 自律', 'Lv.1 通知', 'Lv.2 エスカレ', 'Lv.3 緊急'][self.level]
        return f"""<!DOCTYPE html>
<html lang="ja">
<head><meta charset="UTF-8"></head>
<body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px;color:#1e293b;">
  <div style="background:#1a3a5c;padding:16px;border-radius:8px 8px 0 0;">
    <h1 style="color:white;font-size:16px;margin:0;">NiceEze CODE — 即時報告</h1>
    <p style="color:#bfd7ed;font-size:11px;margin:4px 0 0;">{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
  </div>
  <div style="background:#f0f4f8;padding:16px;border-radius:0 0 8px 8px;">
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <tr><td style="padding:6px 0;font-weight:700;width:130px;">種別</td><td style="padding:6px 0;">{self.kind}</td></tr>
      <tr><td style="padding:6px 0;font-weight:700;">エスカレLv</td><td style="padding:6px 0;">{level_label}</td></tr>
      <tr><td style="padding:6px 0;font-weight:700;">内容</td><td style="padding:6px 0;">{self.content.replace(chr(10), '<br>')}</td></tr>
      <tr><td style="padding:6px 0;font-weight:700;">次アクション</td><td style="padding:6px 0;">{self.next_action}</td></tr>
      <tr><td style="padding:6px 0;font-weight:700;">CEO判断</td><td style="padding:6px 0;font-weight:700;color:{'#dc2626' if self.ceo_decision_required else '#16a34a'};">{ceo_flag}</td></tr>
    </table>
  </div>
  <p style="font-size:10px;color:#94a3b8;margin-top:12px;">
    本メールはNiceEze自律経営執行システム v14.2 が自動送信しました。<br>
    返信不要。チャット（claude.ai）で最新状況を確認してください。
  </p>
</body>
</html>"""


# ──────────────────────────────────────────
# 通知エンジン
# ──────────────────────────────────────────

class GmailNotifier:
    """
    Gmail SMTP経由で即時通知メールを送信する。

    認証情報の取得優先順位:
      1. 環境変数 GMAIL_APP_PASSWORD
      2. GCP Secret Manager: projects/{PROJECT_ID}/secrets/gmail_app_password
         （G3実装時: google-cloud-secret-manager パッケージ使用）

    セットアップ手順（松浦CEO向け）:
      1. niceeze.code.notify@gmail.com でGmailアカウント作成
         または既存のGmailアカウントを使用
      2. Google Account > セキュリティ > 2段階認証を有効化
      3. Google Account > セキュリティ > アプリパスワードを生成
         (アプリ: メール, デバイス: NiceEze Code)
      4. 生成された16桁パスワードを環境変数またはSecret Managerに保存:
         export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
         または
         gcloud secrets create gmail_app_password --data-file=-

    bandit対応: ssl.create_default_context()でTLS必須 / パスワードは環境変数のみ
    """

    def __init__(self, app_password: Optional[str] = None) -> None:
        self.app_password = app_password or os.environ.get('GMAIL_APP_PASSWORD', '')
        self.enabled = bool(self.app_password)

    def send(self, payload: NotifyPayload) -> bool:
        """
        メール送信。失敗時はFalseを返す（例外を上に伝播させない）。
        チャット報告は必ず行うため、メール失敗でも処理を止めない。
        """
        if not self.enabled:
            return False

        msg = MIMEMultipart('alternative')
        msg['Subject'] = payload.subject
        msg['From'] = SENDER_EMAIL
        msg['To'] = CEO_EMAIL
        msg.attach(MIMEText(payload.email_body, 'html', 'utf-8'))

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.ehlo()
                server.starttls(context=context)
                server.login(SENDER_EMAIL, self.app_password)
                server.sendmail(SENDER_EMAIL, CEO_EMAIL, msg.as_string())
            return True
        except Exception:
            return False

    def notify(self, payload: NotifyPayload) -> None:
        """
        即時通知エントリポイント。
        ①チャット用メッセージを標準出力（Claude Codeが拾う）
        ②Gmail送信
        """
        print(payload.chat_message)
        self.send(payload)


# ──────────────────────────────────────────
# 便利関数（ワンライナー呼び出し用）
# ──────────────────────────────────────────

_notifier: Optional[GmailNotifier] = None

def _get_notifier() -> GmailNotifier:
    global _notifier
    if _notifier is None:
        _notifier = GmailNotifier()
    return _notifier


def notify_done(content: str, next_action: str, ceo_required: bool = False) -> None:
    """完了通知"""
    _get_notifier().notify(NotifyPayload(
        kind=KIND_DONE, content=content,
        next_action=next_action, ceo_decision_required=ceo_required,
    ))


def notify_pending(content: str, next_action: str) -> None:
    """判断待ち通知（CEO判断必要）"""
    _get_notifier().notify(NotifyPayload(
        kind=KIND_PENDING, content=content,
        next_action=next_action, ceo_decision_required=True,
        level=LV_ESCALATE,
    ))


def notify_blocker(content: str, next_action: str) -> None:
    """ブロッカー通知"""
    _get_notifier().notify(NotifyPayload(
        kind=KIND_BLOCKER, content=content,
        next_action=next_action, ceo_decision_required=True,
        level=LV_URGENT,
    ))


def notify_gate(content: str, next_action: str) -> None:
    """ハードゲート承認通知"""
    _get_notifier().notify(NotifyPayload(
        kind=KIND_GATE, content=content,
        next_action=next_action, ceo_decision_required=False,
        level=LV_NOTIFY,
    ))
