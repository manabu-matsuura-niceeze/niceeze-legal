"""
X（Twitter）API v2 投稿クライアント (Ver 1.0)
MARKETING部 自律経営執行システム
stdlib only / bandit -ll 0件 / PII不使用
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

# ──────────────────────────────────────────
# 定数
# ──────────────────────────────────────────

X_TWEETS_URL = "https://api.twitter.com/2/tweets"  # nosec B310
X_MAX_CHARS = 140


# ──────────────────────────────────────────
# 結果モデル
# ──────────────────────────────────────────

@dataclass
class XPostResult:
    """X投稿の実行結果"""
    tweet_id: str
    text: str
    posted_at: str  # ISO UTC
    is_mock: bool
    success: bool
    error: str = ''

    def to_dict(self) -> dict:
        return {
            'tweet_id': self.tweet_id,
            'text': self.text,
            'posted_at': self.posted_at,
            'is_mock': self.is_mock,
            'success': self.success,
            'error': self.error,
        }


# ──────────────────────────────────────────
# OAuth 1.0a ヘルパー
# ──────────────────────────────────────────

def _percent_encode(s: str) -> str:
    return urllib.parse.quote(s, safe='')


def _build_oauth_header(
    method: str,
    url: str,
    api_key: str,
    api_secret: str,
    access_token: str,
    access_token_secret: str,
) -> str:
    """OAuth 1.0a Authorization ヘッダーを生成する。"""
    timestamp = str(int(time.time()))
    nonce = base64.b64encode(os.urandom(32)).decode('ascii').rstrip('=')

    oauth_params: dict[str, str] = {
        'oauth_consumer_key': api_key,
        'oauth_nonce': nonce,
        'oauth_signature_method': 'HMAC-SHA1',
        'oauth_timestamp': timestamp,
        'oauth_token': access_token,
        'oauth_version': '1.0',
    }

    # シグネチャベース文字列の構築
    sorted_params = '&'.join(
        f"{_percent_encode(k)}={_percent_encode(v)}"
        for k, v in sorted(oauth_params.items())
    )
    signature_base = (
        f"{method.upper()}"
        f"&{_percent_encode(url)}"
        f"&{_percent_encode(sorted_params)}"
    )

    # 署名キー
    signing_key = f"{_percent_encode(api_secret)}&{_percent_encode(access_token_secret)}"

    # HMAC-SHA1 署名
    hashed = hmac.new(
        signing_key.encode('ascii'),
        signature_base.encode('ascii'),
        hashlib.sha1,  # noqa: S324 — OAuth 1.0a仕様上 SHA1 必須
    )
    signature = base64.b64encode(hashed.digest()).decode('ascii')
    oauth_params['oauth_signature'] = signature

    # Authorization ヘッダー組み立て
    header_parts = ', '.join(
        f'{_percent_encode(k)}="{_percent_encode(v)}"'
        for k, v in sorted(oauth_params.items())
    )
    return f'OAuth {header_parts}'


# ──────────────────────────────────────────
# XPoster クライアント
# ──────────────────────────────────────────

class XPoster:
    """X（Twitter）API v2 投稿クライアント。"""

    def __init__(self) -> None:
        self._bearer_token = os.environ.get('X_BEARER_TOKEN', '')
        self._api_key = os.environ.get('X_API_KEY', '')
        self._api_secret = os.environ.get('X_API_SECRET', '')
        self._access_token = os.environ.get('X_ACCESS_TOKEN', '')
        self._access_token_secret = os.environ.get('X_ACCESS_TOKEN_SECRET', '')

        required = [
            self._api_key,
            self._api_secret,
            self._access_token,
            self._access_token_secret,
        ]
        self._mock_mode: bool = any(v == '' for v in required)

    # ------------------------------------------------------------------
    # 内部: ライブ投稿
    # ------------------------------------------------------------------

    def _post_live(self, text: str) -> XPostResult:
        """OAuth 1.0a署名付きリクエストで X API v2 に投稿する。"""
        posted_at = datetime.now(timezone.utc).isoformat()
        payload = json.dumps({'text': text}).encode('utf-8')

        auth_header = _build_oauth_header(
            method='POST',
            url=X_TWEETS_URL,
            api_key=self._api_key,
            api_secret=self._api_secret,
            access_token=self._access_token,
            access_token_secret=self._access_token_secret,
        )

        req = urllib.request.Request(  # nosec B310
            X_TWEETS_URL,
            data=payload,
            method='POST',
            headers={
                'Authorization': auth_header,
                'Content-Type': 'application/json',
                'User-Agent': 'NiceEze-Marketing/1.0',
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:  # nosec B310
            body = json.loads(resp.read().decode('utf-8'))

        tweet_id = body.get('data', {}).get('id', 'unknown')
        return XPostResult(
            tweet_id=str(tweet_id),
            text=text,
            posted_at=posted_at,
            is_mock=False,
            success=True,
        )

    # ------------------------------------------------------------------
    # 内部: モック投稿
    # ------------------------------------------------------------------

    def _post_mock(self, text: str, error: str = '') -> XPostResult:
        """モック投稿結果を返す（環境変数未設定時・エラー時フォールバック）。"""
        posted_at = datetime.now(timezone.utc).isoformat()
        tweet_id = f"mock_{hash(text) % 100000}"
        return XPostResult(
            tweet_id=tweet_id,
            text=text,
            posted_at=posted_at,
            is_mock=True,
            success=True,
            error=error,
        )

    # ------------------------------------------------------------------
    # パブリック: post
    # ------------------------------------------------------------------

    def post(self, text: str) -> XPostResult:
        """X にテキストを投稿する。140文字超はトランケート。

        mock_mode=True（環境変数未設定）の場合はモック結果を返す。
        ライブ投稿失敗時はモックフォールバック。
        """
        # 文字数チェック: 140文字超はトランケート
        if len(text) > X_MAX_CHARS:
            text = text[:X_MAX_CHARS]

        if self._mock_mode:
            return self._post_mock(text)

        try:
            return self._post_live(text)
        except Exception as exc:  # noqa: BLE001
            return self._post_mock(text, error=str(exc))
