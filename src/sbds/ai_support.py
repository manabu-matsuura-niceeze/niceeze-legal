"""手ぶら旅行 AIサポートセンター (Ver 2.0)
SBDS部門
Claude API 多言語対応（10言語）
FinOps: ANTHROPIC_API_KEY未設定時はテンプレートベース（¥0）
"""
from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List

SUPPORTED_LANGUAGES = ['ja', 'en', 'zh-CN', 'zh-TW', 'ko', 'th', 'fr', 'de', 'es', 'pt']
DEFAULT_LANGUAGE = 'ja'

CLAUDE_MODEL = 'claude-sonnet-4-20250514'
CLAUDE_API_URL = 'https://api.anthropic.com/v1/messages'  # nosec B310

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
        'zh-CN': '行李追踪：您的行李 [QR: {qr_id}] 当前状态为 [{status}]。',
        'zh-TW': '行李追蹤：您的行李 [QR: {qr_id}] 目前狀態為 [{status}]。',
        'ko': '수하물 추적: 귀하의 수하물 [QR: {qr_id}]의 현재 상태는 [{status}]입니다.',
        'th': 'ติดตามกระเป๋า: กระเป๋าของคุณ [QR: {qr_id}] สถานะปัจจุบัน [{status}]',
        'fr': 'Suivi des bagages: Vos bagages [QR: {qr_id}] sont actuellement [{status}].',
        'de': 'Gepäckverfolgung: Ihr Gepäck [QR: {qr_id}] ist aktuell [{status}].',
        'es': 'Seguimiento de equipaje: Su equipaje [QR: {qr_id}] está [{status}].',
        'pt': 'Rastreamento de bagagem: Sua bagagem [QR: {qr_id}] está [{status}].',
    },
    'lost_baggage': {
        'ja': 'お荷物が見つからない場合は、到着拠点スタッフへお申し出ください。QRコード [{qr_id}] をご提示ください。',
        'en': 'If your baggage is missing, please contact arrival hub staff. Please show QR code [{qr_id}].',
        'zh-CN': '如果您的行李丢失，请联系到达站工作人员。请出示QR码 [{qr_id}]。',
        'zh-TW': '若您的行李遺失，請聯繫到達站工作人員。請出示QR碼 [{qr_id}]。',
        'ko': '수하물이 없는 경우 도착 거점 직원에게 문의하세요. QR코드 [{qr_id}]를 제시하세요.',
        'th': 'หากกระเป๋าของคุณสูญหาย โปรดติดต่อเจ้าหน้าที่ที่จุดมาถึง แสดง QR [{qr_id}]',
        'fr': 'Si vos bagages sont manquants, contactez le personnel. Montrez le QR [{qr_id}].',
        'de': 'Falls Ihr Gepäck fehlt, wenden Sie sich ans Personal. Zeigen Sie QR [{qr_id}].',
        'es': 'Si falta su equipaje, contacte al personal. Muestre el QR [{qr_id}].',
        'pt': 'Se sua bagagem estiver faltando, contate a equipe. Mostre o QR [{qr_id}].',
    },
    'general': {
        'ja': 'お問い合わせありがとうございます。担当スタッフが対応いたします。',
        'en': 'Thank you for your inquiry. Our staff will assist you.',
        'zh-CN': '感谢您的咨询。我们的工作人员将为您提供帮助。',
        'zh-TW': '感謝您的詢問。我們的工作人員將為您提供協助。',
        'ko': '문의해 주셔서 감사합니다. 담당 직원이 도와드리겠습니다.',
        'th': 'ขอบคุณสำหรับคำถามของคุณ เจ้าหน้าที่ของเราจะช่วยเหลือคุณ',
        'fr': 'Merci pour votre demande. Notre personnel vous assistera.',
        'de': 'Vielen Dank für Ihre Anfrage. Unser Personal wird Ihnen helfen.',
        'es': 'Gracias por su consulta. Nuestro personal le asistirá.',
        'pt': 'Obrigado pela sua consulta. Nossa equipe irá ajudá-lo.',
    },
    'unlock_request': {
        'ja': 'QRコードの確認が完了しました。管理者の承認をお待ちください。',
        'en': 'QR verification complete. Please wait for administrator approval.',
        'zh-CN': 'QR验证完成。请等待管理员审批。',
        'zh-TW': 'QR驗證完成。請等待管理員審批。',
        'ko': 'QR 확인 완료. 관리자 승인을 기다려 주세요.',
        'th': 'ยืนยัน QR เสร็จสิ้น โปรดรอการอนุมัติจากผู้ดูแลระบบ',
        'fr': "Vérification QR terminée. Veuillez attendre l'approbation de l'administrateur.",
        'de': 'QR-Überprüfung abgeschlossen. Bitte auf Admin-Genehmigung warten.',
        'es': 'Verificación QR completada. Espere la aprobación del administrador.',
        'pt': 'Verificação QR concluída. Aguarde aprovação do administrador.',
    },
}

_STATUS_UNKNOWN: dict[str, str] = {
    'ja': '不明',
    'en': 'unknown',
    'zh-CN': '未知',
    'zh-TW': '未知',
    'ko': '알 수 없음',
    'th': 'ไม่ทราบ',
    'fr': 'inconnu',
    'de': 'unbekannt',
    'es': 'desconocido',
    'pt': 'desconhecido',
}


@dataclass
class SupportRequest:
    request_id: str     # SHA-256[:16]
    language: str       # SUPPORTED_LANGUAGES のいずれか
    category: str       # FAQ_CATEGORIES
    message: str        # ユーザーメッセージ（最大500文字）
    qr_id: str = ''     # 関連QR（オプション）
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class SupportResponse:
    request_id: str
    language: str
    response_text: str
    source: str         # 'template' | 'claude_api'
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
    """AIサポートセンター（10言語対応・Claude API連携）"""

    def __init__(self) -> None:
        self._api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        self._mock_mode: bool = not bool(self._api_key)
        self._history: list[tuple[SupportRequest, SupportResponse]] = []

    def respond(self, request: SupportRequest) -> SupportResponse:
        """問い合わせに対して応答を生成する"""
        if self._mock_mode:
            response = self._template_respond(request)
        else:
            try:
                text = self._call_claude_api(request)
                response = SupportResponse(
                    request_id=request.request_id,
                    language=request.language,
                    response_text=text,
                    source='claude_api',
                )
            except Exception:  # noqa: BLE001
                response = self._template_respond(request)
        self._history.append((request, response))
        return response

    def _template_respond(self, request: SupportRequest) -> SupportResponse:
        """テンプレートベースの応答生成"""
        lang = request.language if request.language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
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

    def _call_claude_api(self, request: SupportRequest) -> str:
        """Claude API呼び出し（urllib stdlib only）。
        失敗時はテンプレートにフォールバック（except Exception: # noqa: BLE001）。
        """
        import json
        import urllib.request
        import urllib.error

        system_prompt = (
            f"You are a multilingual baggage support assistant for NiceEze hand-carry-free travel service. "
            f"Respond in {request.language} language. Be concise and helpful. "
            f"Do not share personal information."
        )
        user_msg = request.message
        if request.qr_id:
            user_msg += f" [Reference QR: {request.qr_id}]"

        payload = {
            "model": CLAUDE_MODEL,
            "max_tokens": 300,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_msg}],
        }
        body = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(  # nosec B310
            CLAUDE_API_URL,
            data=body,
            method='POST',
        )
        req.add_header('Content-Type', 'application/json')
        req.add_header('x-api-key', self._api_key)
        req.add_header('anthropic-version', '2023-06-01')

        with urllib.request.urlopen(req, timeout=15) as resp:  # nosec B310
            data = json.loads(resp.read().decode('utf-8'))
        return data['content'][0]['text']

    def create_request(
        self,
        language: str,
        category: str,
        message: str,
        qr_id: str = '',
        accept_language: str = '',
    ) -> SupportRequest:
        """SupportRequestを生成する。

        言語決定の優先順位:
        1. language 引数（SUPPORTED_LANGUAGES に含まれる場合）
        2. accept_language ヘッダー解析
        3. DEFAULT_LANGUAGE ('ja') へフォールバック
        """
        lang = self._resolve_language(language, accept_language)
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

    def _resolve_language(self, language: str, accept_language: str = '') -> str:
        """言語コードを解決する。"""
        # language 引数を優先
        if language in SUPPORTED_LANGUAGES:
            return language

        # Accept-Language ヘッダーを解析
        if accept_language:
            for part in accept_language.split(','):
                lang_tag = part.split(';')[0].strip()
                # 完全一致（zh-CN, zh-TW 等）
                if lang_tag in SUPPORTED_LANGUAGES:
                    return lang_tag
                # 短縮形一致（zh -> zh-CN, etc.）
                base = lang_tag.split('-')[0].lower()
                for supported in SUPPORTED_LANGUAGES:
                    if supported.lower() == base or supported.lower().startswith(base + '-'):
                        return supported

        return DEFAULT_LANGUAGE

    def unlock_request(
        self,
        qr_token: str,
        requester_language: str = 'ja',
        auto_approve: bool = False,
    ) -> dict:
        """
        AIが本人確認（QRコード照合）後に解錠リクエストを送信。
        管理者承認フローが必要（auto_approve=False がデフォルト）。

        Returns:
            {
                'request_id': str,
                'qr_valid': bool,
                'unlock_approved': bool,  # auto_approve=Trueかつ有効QRのみTrue
                'message': str,           # 多言語メッセージ
                'admin_approval_required': bool,
                'created_at': str,
            }
        """
        from .travel_qr import TravelQRManager

        lang = requester_language if requester_language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE

        # QR検証
        qr_manager = TravelQRManager.__new__(TravelQRManager)
        # 同一プロセス内のシングルトンにアクセスするためモジュールレベルのインスタンスを使う
        # travel_api.py 側のシングルトンは別インスタンスなので、ここでは独立検証を行う
        # qr_token が存在する独立したマネージャーから検証する
        # 実際の運用では DI でマネージャーを渡すが、MVP では travel_api のシングルトンを参照
        try:
            import importlib
            travel_api_mod = importlib.import_module('src.sbds.travel_api')
            qr_mgr = travel_api_mod._qr_manager
            qr = qr_mgr._store.get(qr_token)
            qr_valid = qr is not None and qr.is_valid
        except Exception:  # noqa: BLE001
            qr_valid = False

        unlock_approved = auto_approve and qr_valid
        admin_approval_required = not auto_approve or not qr_valid

        # 多言語メッセージ
        msg_map = RESPONSE_TEMPLATES['unlock_request']
        message = msg_map.get(lang, msg_map[DEFAULT_LANGUAGE])

        # ログ記録（実際の解錠コマンドは送信しない）
        request_id = hashlib.sha256(
            f'unlock:{qr_token[:8]}:{lang}:{datetime.now(timezone.utc).isoformat()}'.encode()
        ).hexdigest()[:16]

        return {
            'request_id': request_id,
            'qr_valid': qr_valid,
            'unlock_approved': unlock_approved,
            'message': message,
            'admin_approval_required': admin_approval_required,
            'created_at': datetime.now(timezone.utc).isoformat(),
        }

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
