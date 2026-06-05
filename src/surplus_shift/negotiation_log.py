"""自律商談履歴ログ — 交渉案生成・人間承認フロー管理 (Ver 1.0)
【重要】最終送信は必ず人間担当者が承認してから実行すること。自動送信禁止。
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


STATUS_DRAFT = 'draft'              # AI生成済み・未承認
STATUS_HUMAN_APPROVED = 'human_approved'  # 人間が承認済み
STATUS_SENT = 'sent'                # 人間が手動送信済み
STATUS_REJECTED = 'rejected'        # 人間が却下


@dataclass
class NegotiationRecord:
    """交渉案1件の記録"""
    record_id: str          # SHA-256 by content+timestamp
    month: str              # 'YYYY-MM'
    draft_text: str         # AI生成交渉案文
    status: str             # draft / human_approved / sent / rejected
    created_at: str         # ISO datetime UTC
    updated_at: str         # ISO datetime UTC
    human_approved_by: str = ''   # 承認者名（人間が入力）
    approved_at: str = ''         # 承認日時
    notes: str = ''               # 備考

    def __post_init__(self) -> None:
        if self.status not in (STATUS_DRAFT, STATUS_HUMAN_APPROVED, STATUS_SENT, STATUS_REJECTED):
            raise ValueError(f'Invalid status: {self.status}')

    def to_dict(self) -> dict:
        return {
            'record_id': self.record_id,
            'month': self.month,
            'draft_text': self.draft_text,
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'human_approved_by': self.human_approved_by,
            'approved_at': self.approved_at,
            'notes': self.notes,
            'human_approval_required': True,  # 常にTrue
        }


class NegotiationLog:
    """
    交渉案履歴ログ管理。
    インメモリストレージ（MVP）。G3でFirestore永続化予定。
    【重要】approve()は人間担当者の手動操作を記録するのみ。自動送信は禁止。
    """

    def __init__(self) -> None:
        self._records: list[NegotiationRecord] = []

    def add_draft(self, month: str, draft_text: str) -> NegotiationRecord:
        """AI生成交渉案をdraftステータスで追加"""
        now = datetime.now(timezone.utc).isoformat()
        record_id = hashlib.sha256(
            f'{month}:{draft_text}:{now}'.encode()
        ).hexdigest()
        record = NegotiationRecord(
            record_id=record_id,
            month=month,
            draft_text=draft_text,
            status=STATUS_DRAFT,
            created_at=now,
            updated_at=now,
        )
        self._records.append(record)
        return record

    def human_approve(self, record_id: str, approved_by: str, notes: str = '') -> NegotiationRecord:
        """
        人間担当者が交渉案を承認する。
        【重要】この操作は承認の記録のみ。送信は担当者が手動で行うこと。
        """
        record = self._find(record_id)
        now = datetime.now(timezone.utc).isoformat()
        record.status = STATUS_HUMAN_APPROVED
        record.human_approved_by = approved_by
        record.approved_at = now
        record.updated_at = now
        record.notes = notes
        return record

    def mark_sent(self, record_id: str) -> NegotiationRecord:
        """人間が手動送信完了した記録（自動送信ではない）"""
        record = self._find(record_id)
        if record.status != STATUS_HUMAN_APPROVED:
            raise ValueError('送信前に人間承認が必要です。')
        record.status = STATUS_SENT
        record.updated_at = datetime.now(timezone.utc).isoformat()
        return record

    def reject(self, record_id: str, notes: str = '') -> NegotiationRecord:
        """人間担当者が交渉案を却下"""
        record = self._find(record_id)
        record.status = STATUS_REJECTED
        record.notes = notes
        record.updated_at = datetime.now(timezone.utc).isoformat()
        return record

    def get_all(self) -> list[NegotiationRecord]:
        return list(self._records)

    def get_by_status(self, status: str) -> list[NegotiationRecord]:
        return [r for r in self._records if r.status == status]

    def get_by_month(self, month: str) -> list[NegotiationRecord]:
        return [r for r in self._records if r.month == month]

    def summary(self) -> dict:
        return {
            'total': len(self._records),
            'draft': len(self.get_by_status(STATUS_DRAFT)),
            'human_approved': len(self.get_by_status(STATUS_HUMAN_APPROVED)),
            'sent': len(self.get_by_status(STATUS_SENT)),
            'rejected': len(self.get_by_status(STATUS_REJECTED)),
            'human_approval_required': True,  # 常にTrue
        }

    def _find(self, record_id: str) -> NegotiationRecord:
        for r in self._records:
            if r.record_id == record_id:
                return r
        raise KeyError(f'record_id not found: {record_id}')
