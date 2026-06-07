# src/common/__init__.py
# NiceEze 全サービス共通モジュール

from .consent_manager import ConsentManager, ConsentRecord, VALID_CONSENT_TYPES, VALID_SERVICES

__all__ = [
    'ConsentManager',
    'ConsentRecord',
    'VALID_CONSENT_TYPES',
    'VALID_SERVICES',
]
