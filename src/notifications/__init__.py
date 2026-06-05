"""NiceEze 即時通知エンジン — Gmail SMTP / 報連相体制"""
from .gmail_notifier import (
    GmailNotifier, NotifyPayload,
    notify_done, notify_pending, notify_blocker, notify_gate,
    KIND_DONE, KIND_PENDING, KIND_BLOCKER, KIND_GATE,
)

__all__ = [
    'GmailNotifier', 'NotifyPayload',
    'notify_done', 'notify_pending', 'notify_blocker', 'notify_gate',
    'KIND_DONE', 'KIND_PENDING', 'KIND_BLOCKER', 'KIND_GATE',
]
