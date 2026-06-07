# src/common/gdpr_manager.py
# NiceEze GDPRデータ管理基盤

from __future__ import annotations

import csv
import hashlib
import io
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from .eu_countries import is_gdpr_applicable, GDPR_APPLICABLE_COUNTRIES

VALID_RESTRICTION_TYPES = {
    'object_to_processing',
    'restrict_processing',
    'portability',
    'erasure',
}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _make_request_id(user_id: str, restriction_type: str, created_at: str) -> str:
    raw = f"{user_id}:{restriction_type}:{created_at}:{uuid.uuid4()}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:12]


@dataclass
class ResidentProfile:
    user_id: str
    country_code: str           # ISO 3166-1 alpha-2
    gdpr_applicable: bool       # 自動判定（is_gdpr_applicable()）
    data_records: dict          # ダミーの保有データ（開示請求用）
    created_at: str
    anonymized: bool = False
    anonymized_at: str = ''


@dataclass
class ProcessingRestrictionRequest:
    request_id: str             # SHA-256[:12]
    user_id: str
    restriction_type: str       # 'object_to_processing' | 'restrict_processing' | 'portability' | 'erasure'
    reason: str
    status: str                 # 'pending' | 'in_review' | 'completed'
    created_at: str


class GDPRManager:
    def __init__(self) -> None:
        self._profiles: Dict[str, ResidentProfile] = {}
        self._restriction_requests: List[ProcessingRestrictionRequest] = []
        self._deletion_log: List[dict] = []

    def register_user(
        self,
        user_id: str,
        country_code: str,
        data_records: Optional[dict] = None,
    ) -> ResidentProfile:
        """ユーザー登録: country_codeからgdpr_applicableを自動設定"""
        gdpr = is_gdpr_applicable(country_code)
        profile = ResidentProfile(
            user_id=user_id,
            country_code=country_code.upper(),
            gdpr_applicable=gdpr,
            data_records=data_records if data_records is not None else {},
            created_at=_utcnow_iso(),
        )
        self._profiles[user_id] = profile
        return profile

    def get_my_data(self, user_id: str) -> dict:
        """開示請求: 保有データをdictで返す（gdpr_applicable不問）"""
        profile = self._profiles.get(user_id)
        if profile is None:
            raise ValueError(f"ユーザーが見つかりません: {user_id!r}")
        return {
            'user_id': profile.user_id,
            'country_code': profile.country_code,
            'gdpr_applicable': profile.gdpr_applicable,
            'data_records': profile.data_records,
            'created_at': profile.created_at,
            'anonymized': profile.anonymized,
            'anonymized_at': profile.anonymized_at,
        }

    def delete_my_data(self, user_id: str) -> dict:
        """忘れられる権利: 全データ削除/匿名化

        法令保存義務対象(created_at 1年以内): anonymize
        それ以外: 完全削除
        削除ログを _deletion_log に記録
        """
        profile = self._profiles.get(user_id)
        if profile is None:
            raise ValueError(f"ユーザーが見つかりません: {user_id!r}")

        deleted = []
        anonymized = []
        now = datetime.now(timezone.utc)
        one_year_ago = now - timedelta(days=365)

        try:
            created_dt = datetime.strptime(profile.created_at, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
        except ValueError:
            created_dt = one_year_ago  # パース失敗時は古いものとして扱う

        if created_dt >= one_year_ago:
            # 法令保存義務対象: 匿名化
            profile.data_records = {}
            profile.anonymized = True
            profile.anonymized_at = _utcnow_iso()
            anonymized.append(user_id)
            message = f"ユーザー {user_id} のデータを匿名化しました（法令保存義務対象）"
        else:
            # 完全削除
            del self._profiles[user_id]
            deleted.append(user_id)
            message = f"ユーザー {user_id} のデータを完全削除しました"

        log_entry = {
            'user_id': user_id,
            'action': 'anonymized' if anonymized else 'deleted',
            'timestamp': _utcnow_iso(),
        }
        self._deletion_log.append(log_entry)

        return {
            'deleted': deleted,
            'anonymized': anonymized,
            'message': message,
        }

    def export_my_data_csv(self, user_id: str) -> str:
        """データポータビリティ権: CSV文字列を返す
        gdpr_applicable=False の場合は PermissionError
        """
        profile = self._profiles.get(user_id)
        if profile is None:
            raise ValueError(f"ユーザーが見つかりません: {user_id!r}")
        if not profile.gdpr_applicable:
            raise PermissionError(
                f"ユーザー {user_id!r} はGDPR適用外のためデータエクスポートできません"
            )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['field', 'value'])
        writer.writerow(['user_id', profile.user_id])
        writer.writerow(['country_code', profile.country_code])
        writer.writerow(['gdpr_applicable', profile.gdpr_applicable])
        writer.writerow(['created_at', profile.created_at])
        writer.writerow(['anonymized', profile.anonymized])
        writer.writerow(['anonymized_at', profile.anonymized_at])
        for k, v in profile.data_records.items():
            writer.writerow([f'data_records.{k}', v])

        return output.getvalue()

    def request_processing_restriction(
        self,
        user_id: str,
        restriction_type: str,
        reason: str,
    ) -> ProcessingRestrictionRequest:
        """処理制限権の申請受付（管理者が手動対応するためのレコード作成）"""
        if restriction_type not in VALID_RESTRICTION_TYPES:
            raise ValueError(
                f"無効なrestriction_type: {restriction_type!r}。"
                f"有効値: {sorted(VALID_RESTRICTION_TYPES)}"
            )

        created_at = _utcnow_iso()
        request_id = _make_request_id(user_id, restriction_type, created_at)

        req = ProcessingRestrictionRequest(
            request_id=request_id,
            user_id=user_id,
            restriction_type=restriction_type,
            reason=reason,
            status='pending',
            created_at=created_at,
        )
        self._restriction_requests.append(req)
        return req

    def gdpr_notification_required(self, user_id: str) -> bool:
        """gdpr_applicable=True の場合はUI通知が必要"""
        profile = self._profiles.get(user_id)
        if profile is None:
            return False
        return profile.gdpr_applicable
