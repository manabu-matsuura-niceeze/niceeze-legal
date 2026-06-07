"""
各サービス初回利用時の同意取得フロー共通処理
ConsentManager と GDPRManager を組み合わせて使う
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .consent_manager import ConsentManager, VALID_CONSENT_TYPES
from .eu_countries import is_gdpr_applicable

# 必須同意（未同意では登録不可）
REQUIRED_CONSENTS: Dict[str, List[str]] = {
    'sbds':       ['privacy_policy'],
    'smartlife':  ['privacy_policy'],
    'travel':     ['privacy_policy'],
}

# 任意同意（スキップ可能）
OPTIONAL_CONSENTS: Dict[str, List[str]] = {
    'sbds':       ['delivery_preference', 'line_integration'],
    'smartlife':  ['ai_learning', 'marketing_communication'],
    'travel':     ['location_info_travel'],
}

# GDPR対象国の追加必須同意
GDPR_REQUIRED_CONSENTS: List[str] = ['gdpr_rights_acknowledged']

# 保護者同意が必要な年齢
MINOR_AGE_THRESHOLD = 16
VALID_GUARDIAN_METHODS = ['accompanied', 'written']


@dataclass
class RegistrationRequest:
    user_id: str
    service: str                    # 'sbds' | 'smartlife' | 'travel'
    country_code: str               # ISO 3166-1 alpha-2
    consents: Dict[str, bool]       # consent_type → granted
    age_confirmed: bool = True      # 16歳以上確認
    is_minor: bool = False          # 16歳未満フラグ
    guardian_consent_method: str = ''   # 'accompanied' | 'written'
    guardian_name: str = ''


@dataclass
class RegistrationResult:
    success: bool
    user_id: str
    service: str
    granted_consents: List[str]
    skipped_consents: List[str]
    gdpr_applicable: bool
    errors: List[str]               # バリデーションエラー一覧


class ConsentFlowProcessor:
    def __init__(self, consent_manager: ConsentManager = None):
        self._cm = consent_manager or ConsentManager()

    def get_required_consents(self, service: str, country_code: str) -> List[str]:
        """サービス + 国コードに応じた必須同意リストを返す"""
        required = list(REQUIRED_CONSENTS.get(service, []))
        if is_gdpr_applicable(country_code):
            for ct in GDPR_REQUIRED_CONSENTS:
                if ct not in required:
                    required.append(ct)
        return required

    def validate_minor(self, req: RegistrationRequest) -> List[str]:
        """未成年バリデーション。エラーリストを返す（空リスト=OK）"""
        errors: List[str] = []
        if not req.is_minor:
            return errors
        if req.guardian_consent_method not in VALID_GUARDIAN_METHODS:
            errors.append(
                'is_minor=True の場合、guardian_consent_method は '
                f'{VALID_GUARDIAN_METHODS} のいずれかを指定してください'
            )
        if not req.guardian_name or not req.guardian_name.strip():
            errors.append('is_minor=True の場合、guardian_name は必須です')
        return errors

    def process_registration(self, req: RegistrationRequest) -> RegistrationResult:
        """
        サービス登録時の同意フロー処理
        1. 必須同意の確認（未同意→errors追加してsuccess=False）
        2. 任意同意の処理（未同意でも続行、skipped_consentsに追加）
        3. GDPR対象国の場合: gdpr_rights_acknowledged 必須チェック
        4. 未成年チェック: is_minor=True の場合 guardian_consent_method / guardian_name 必須
        5. ConsentManager.grant() を呼んで記録
        """
        errors: List[str] = []
        gdpr_applicable = is_gdpr_applicable(req.country_code)
        required = self.get_required_consents(req.service, req.country_code)
        optional = list(OPTIONAL_CONSENTS.get(req.service, []))

        # 1 & 3: 必須同意チェック（GDPR含む）
        for ct in required:
            if not req.consents.get(ct, False):
                errors.append(f'必須同意が未取得です: {ct}')

        # 4: 未成年チェック
        minor_errors = self.validate_minor(req)
        errors.extend(minor_errors)

        if errors:
            return RegistrationResult(
                success=False,
                user_id=req.user_id,
                service=req.service,
                granted_consents=[],
                skipped_consents=[],
                gdpr_applicable=gdpr_applicable,
                errors=errors,
            )

        # 5: ConsentManager に記録
        granted_consents: List[str] = []
        skipped_consents: List[str] = []

        # 必須同意を記録
        for ct in required:
            self._cm.grant(req.user_id, req.service, ct)
            granted_consents.append(ct)

        # 任意同意の処理
        for ct in optional:
            if req.consents.get(ct, False):
                self._cm.grant(req.user_id, req.service, ct)
                granted_consents.append(ct)
            else:
                skipped_consents.append(ct)

        return RegistrationResult(
            success=True,
            user_id=req.user_id,
            service=req.service,
            granted_consents=granted_consents,
            skipped_consents=skipped_consents,
            gdpr_applicable=gdpr_applicable,
            errors=[],
        )
