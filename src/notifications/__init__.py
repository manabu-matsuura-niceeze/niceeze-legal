"""NiceEze 通知エンジン — チャット即時報告（確定方式）"""

# 通知方式: このチャット（claude.ai）への都度報告のみ（確定 2026-06-05）
# Gmail MCPは不要のため削除済み（NOTIFY-002）

KIND_DONE    = '完了'
KIND_PENDING = '判断待ち'
KIND_BLOCKER = 'ブロッカー'
KIND_GATE    = 'ハードゲート承認'

__all__ = ['KIND_DONE', 'KIND_PENDING', 'KIND_BLOCKER', 'KIND_GATE']
