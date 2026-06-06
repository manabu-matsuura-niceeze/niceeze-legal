"""手ぶら旅行 AIサポートセンター骨格 (Ver 1.0)
SBDS部門 MVP
Claude API 多言語対応（ja/en/zh/ko）
G3でClaude API実連携予定。MVPはテンプレートベース。
FinOps: Claude API費用はG3以降（MVP: ¥0）
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List

SUPPORTED_LANGUAGES = ['ja', 'en', 'zh', 'ko']
DEFAULT_LANGUAGE = 'ja'

# FAQ カテゴリ
FAQ_CATEGORIES = [
    'baggage_tracking',    # 荷物追跡
    'delivery_schedule',   # 配送スケジュール
    'lost_baggage',        # 荷物紛失
    'hub_location',        # 拠点案内
    'general',             # 一般問い合わせ
]

RESPONSE_TEMPLATES: dict[str, dict[str, str]] = {
    'baggage_tracking': {
        'ja': 'お荷物の追跡情報：QRコード [{qr_id}] の荷物は現在 [{status}] の状態です。',
        'en': 'Baggage tracking: Your baggage [QR: {qr_id}] is currently [{status}].',
        'zh': '行李追踪：您的行李 [QR: {qr_id}] 当前状态为 [{status}]。',
        'ko': '수하물 추적: 귀하의 수하물 [QR: {qr_id}]의 현재 상태는 [{status}]입니다.',
    },
    'lost_baggage': {
        'ja': 'お荷物が見つからない場合は、到着拠点スタッフへお申し出ください。QRコード [{qr_id}] をご提示ください。',
        'en': 'If your baggage is missing, please contact arrival hub staff. Please show QR code [{qr_id}].',
        'zh': '如果您的行李丢失，请联系到达站工作人员。请出示QR码 [{qr_id}]。',
        'ko': '수하물이 없는 경우 도착 거점 직원에게 문의하세요. QR코드 [{qr_id}]를 제시하세요.',
    },
    'general': {
        'ja': 'お問い合わせありがとうございます。担当スタッフが対応いたします。',
        'en': 'Thank you for your inquiry. Our staff will assist you.',
        'zh': '感谢您的咨询。我们的工作人员将为您提供帮助。',
        'ko': '문의해 주셔서 감사합니다. 담당 직원이 도와드리겠습니다.',
    },
}

_STATUS_UNKNOWN: dict[str, str] = {
    'ja': '不明',
    'en': 'unknown',
    'zh': '未知',
    'ko': '알 수 없음',
}


@dataclass
class SupportRequest:
    request_id: str     # SHA-256[:16]
    language: str       # 'ja'|'en'|'zh'|'ko'
    category: str       # FAQ_CATEGORIES
    message: str        # ユーザーメッセージ（最大500文字）
    qr_id: str = ''     # 関連QR（オプション）
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class SupportResponse:
    request_id: str
    language: str
    response_text: str
    source: str         # 'template'（MVP） | 'claude_api'（G3以降）
    responded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            'request_id': self.request_id,
            'language': self.language,
            'response_text': self.response_text,
            'source': self.source,
            'responded_at': self.responded_at,
        }


class AISupportCenter:
    """AIサポートセンター（MVP: テンプレートベース）"""

    def __init__(self) -> None:
        api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        self._mock_mode: bool = not bool(api_key)
        self._history: list[tuple[SupportRequest, SupportResponse]] = []

    def respond(self, request: SupportRequest) -> SupportResponse:
        """問い合わせに対して応答を生成する"""
        if self._mock_mode:
            response = self._template_respond(request)
        else:
            response = self._claude_api_respond(request)
        self._history.append((request, response))
        return response

    def _template_respond(self, request: SupportRequest) -> SupportResponse:
        """テンプレートベースの応答生成"""
        lang = request.language if request.language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
        # カテゴリが未定義の場合は 'general' にフォールバック
        category = request.category if request.category in RESPONSE_TEMPLATES else 'general'
        template_map = RESPONSE_TEMPLATES[category]
        template = template_map.get(lang, template_map.get(DEFAULT_LANGUAGE, ''))

        qr_id_val = request.qr_id if request.qr_id else 'N/A'
        status_val = _STATUS_UNKNOWN.get(lang, 'unknown') if not request.qr_id else 'active'

        text = template.format(qr_id=qr_id_val, status=status_val)
        return SupportResponse(
            request_id=request.request_id,
            language=lang,
            response_text=text,
            source='template',
        )

    def _claude_api_respond(self, request: SupportRequest) -> SupportResponse:
        """Claude API呼び出し（G3以降実装予定）"""
        raise NotImplementedError('Claude API integration is planned for G3.')

    def create_request(
        self,
        language: str,
        category: str,
        message: str,
        qr_id: str = '',
    ) -> SupportRequest:
        """SupportRequestを生成する"""
        lang = language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
        now = datetime.now(timezone.utc).isoformat()
        request_id = hashlib.sha256(f'{lang}:{message}:{now}'.encode()).hexdigest()[:16]
        return SupportRequest(
            request_id=request_id,
            language=lang,
            category=category,
            message=message[:500],
            qr_id=qr_id,
            created_at=now,
        )

    def get_history(self) -> List[tuple[SupportRequest, SupportResponse]]:
        """問い合わせ履歴を返す"""
        return list(self._history)

    def health_check(self) -> dict:
        """ヘルスチェック"""
        return {
            'status': 'template' if self._mock_mode else 'claude_api_ready',
            'supported_languages': SUPPORTED_LANGUAGES,
            'mock_mode': self._mock_mode,
        }
