# src/common/consent_manager.py
# NiceEze 全サービス共通 同意管理基盤
# PII最小化: ip_addressはSHA-256ハッシュ化して保存

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple


VALID_CONSENT_TYPES = [
    'terms_of_service',
    'privacy_policy',
    'delivery_preference',
    'line_integration',
    'ai_learning',
    'location_info_travel',
    'marketing_communication',
    'cookie_analytics',
    'gdpr_rights_acknowledged',
]

VALID_SERVICES = ['sbds', 'smartlife', 'travel', 'research', 'marketing', 'gov']


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _hash_ip(ip_address: str) -> str:
    """IPアドレスをSHA-256ハッシュ化して返す（PII最小化）"""
    if not ip_address:
        return ''
    return hashlib.sha256(ip_address.encode('utf-8')).hexdigest()


def _make_record_id(user_id: str, service: str, consent_type: str, granted_at: str) -> str:
    """SHA-256の先頭12文字をrecord_idとして使用"""
    raw = f"{user_id}:{service}:{consent_type}:{granted_at}:{uuid.uuid4()}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:12]


@dataclass
class ConsentRecord:
    record_id: str          # SHA-256[:12]
    user_id: str            # ユーザーID（匿名化済み識別子）
    service: str            # VALID_SERVICES のいずれか
    consent_type: str       # VALID_CONSENT_TYPES のいずれか
    granted: bool           # True=同意, False=不同意
    granted_at: str         # ISO 8601 UTC
    revoked_at: str = ''    # 撤回日時（撤回済みの場合）
    ip_address: str = ''    # IPアドレス（ハッシュ化して保存）
    user_agent: str = ''    # User-Agent（先頭100文字のみ）
    ai_learning_excluded: bool = False  # AI学習除外フラグ


# ストレージキー: (user_id, service, consent_type)
_ConsentKey = Tuple[str, str, str]


class ConsentManager:
    """全サービス共通 同意管理クラス"""

    def __init__(self) -> None:
        # アクティブなコンセントレコード（最新状態のみ）
        self._records: Dict[_ConsentKey, ConsentRecord] = {}
        # 履歴（全変更を保存）
        self._history: List[ConsentRecord] = []
        # AI学習除外ユーザーセット
        self._ai_learning_excluded: set = set()

    def grant(
        self,
        user_id: str,
        service: str,
        consent_type: str,
        ip_address: str = '',
        user_agent: str = '',
    ) -> ConsentRecord:
        """同意を付与する。既存レコードがある場合は更新する。"""
        if consent_type not in VALID_CONSENT_TYPES:
            raise ValueError(f"無効なconsent_type: {consent_type!r}。有効値: {VALID_CONSENT_TYPES}")
        if service not in VALID_SERVICES:
            raise ValueError(f"無効なservice: {service!r}。有効値: {VALID_SERVICES}")

        granted_at = _utcnow_iso()
        record_id = _make_record_id(user_id, service, consent_type, granted_at)
        hashed_ip = _hash_ip(ip_address)
        truncated_ua = user_agent[:100]

        key = (user_id, service, consent_type)
        existing = self._records.get(key)

        if existing is not None:
            # 既存レコードを更新
            existing.granted = True
            existing.granted_at = granted_at
            existing.revoked_at = ''
            existing.ip_address = hashed_ip
            existing.user_agent = truncated_ua
            existing.ai_learning_excluded = user_id in self._ai_learning_excluded
            record = existing
        else:
            record = ConsentRecord(
                record_id=record_id,
                user_id=user_id,
                service=service,
                consent_type=consent_type,
                granted=True,
                granted_at=granted_at,
                revoked_at='',
                ip_address=hashed_ip,
                user_agent=truncated_ua,
                ai_learning_excluded=user_id in self._ai_learning_excluded,
            )
            self._records[key] = record

        # 履歴に追加（スナップショット）
        self._history.append(ConsentRecord(
            record_id=record.record_id,
            user_id=record.user_id,
            service=record.service,
            consent_type=record.consent_type,
            granted=record.granted,
            granted_at=record.granted_at,
            revoked_at=record.revoked_at,
            ip_address=record.ip_address,
            user_agent=record.user_agent,
            ai_learning_excluded=record.ai_learning_excluded,
        ))

        return record

    def revoke(self, user_id: str, service: str, consent_type: str) -> ConsentRecord:
        """同意を撤回する。"""
        if consent_type not in VALID_CONSENT_TYPES:
            raise ValueError(f"無効なconsent_type: {consent_type!r}。有効値: {VALID_CONSENT_TYPES}")
        if service not in VALID_SERVICES:
            raise ValueError(f"無効なservice: {service!r}。有効値: {VALID_SERVICES}")

        key = (user_id, service, consent_type)
        existing = self._records.get(key)

        revoked_at = _utcnow_iso()

        if existing is not None:
            existing.granted = False
            existing.revoked_at = revoked_at
            record = existing
        else:
            # レコードが存在しない場合でも撤回レコードを作成
            record_id = _make_record_id(user_id, service, consent_type, revoked_at)
            record = ConsentRecord(
                record_id=record_id,
                user_id=user_id,
                service=service,
                consent_type=consent_type,
                granted=False,
                granted_at=revoked_at,
                revoked_at=revoked_at,
            )
            self._records[key] = record

        # AI学習撤回時の特別処理
        if consent_type == 'ai_learning':
            self._apply_ai_learning_exclusion(user_id)

        # 履歴に追加（スナップショット）
        self._history.append(ConsentRecord(
            record_id=record.record_id,
            user_id=record.user_id,
            service=record.service,
            consent_type=record.consent_type,
            granted=record.granted,
            granted_at=record.granted_at,
            revoked_at=record.revoked_at,
            ip_address=record.ip_address,
            user_agent=record.user_agent,
            ai_learning_excluded=record.ai_learning_excluded,
        ))

        return record

    def get_status(self, user_id: str, service: Optional[str] = None) -> List[ConsentRecord]:
        """現在のコンセント状態を返す。service指定なしの場合は全サービス。"""
        result = []
        for (uid, svc, _ct), record in self._records.items():
            if uid != user_id:
                continue
            if service is not None and svc != service:
                continue
            result.append(record)
        return result

    def get_history(self, user_id: str) -> List[ConsentRecord]:
        """全コンセント履歴（撤回済み含む）をgranted_at降順で返す。"""
        user_history = [r for r in self._history if r.user_id == user_id]
        user_history.sort(key=lambda r: r.granted_at, reverse=True)
        return user_history

    def is_granted(self, user_id: str, service: str, consent_type: str) -> bool:
        """現在有効な同意があるかチェック。"""
        key = (user_id, service, consent_type)
        record = self._records.get(key)
        if record is None:
            return False
        return record.granted and record.revoked_at == ''

    def _apply_ai_learning_exclusion(self, user_id: str) -> None:
        """AI学習撤回時: 該当ユーザーの全レコードにai_learning_excluded=Trueをセット。
        実際のDB更新はここでDBクライアントを呼び出す（例: db.execute(UPDATE ...)）。
        """
        self._ai_learning_excluded.add(user_id)
        for (uid, _svc, _ct), record in self._records.items():
            if uid == user_id:
                record.ai_learning_excluded = True

    def get_ai_learning_excluded_users(self) -> List[str]:
        """AI学習除外ユーザーIDリストを返す。"""
        return list(self._ai_learning_excluded)
