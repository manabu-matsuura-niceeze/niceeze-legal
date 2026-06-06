"""SURPLUS SHIFT 商談サポートAPI (Ver 1.0)
商談進捗管理 / PDF出力 / SmartLife連携
Gate D制約維持: AIは提案生成まで。最終送信は人間担当者が承認後に手動実行。
FinOps: 月額¥5,000以内 / PII最小化 / bandit 0件
"""
from __future__ import annotations

import hashlib
import html
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

# ──────────────────────────────────────────
# 商談ステータス定数
# ──────────────────────────────────────────

STATUS_INITIAL_CONTACT = 'initial_contact'  # 初回接触
STATUS_PROPOSAL        = 'proposal'          # 提案済み
STATUS_NEGOTIATING     = 'negotiating'       # 交渉中
STATUS_AGREED          = 'agreed'            # 合意
STATUS_CLOSED_WON      = 'closed_won'        # 成約
STATUS_CLOSED_LOST     = 'closed_lost'       # 失注

VALID_STATUSES = [
    STATUS_INITIAL_CONTACT, STATUS_PROPOSAL, STATUS_NEGOTIATING,
    STATUS_AGREED, STATUS_CLOSED_WON, STATUS_CLOSED_LOST,
]

SMARTLIFE_CATEGORY_MAP = {
    '食品・飲料': 'food_beverage',
    '日用品・消耗品': 'daily_goods',
    '家電・ガジェット': 'electronics',
    '衣料・ファッション': 'fashion',
    '美容・健康': 'beauty_health',
    'ペット用品': 'pet_supplies',
    'スポーツ・アウトドア': 'sports_outdoor',
    'ホーム・インテリア': 'home_interior',
}


# ──────────────────────────────────────────
# データモデル
# ──────────────────────────────────────────

@dataclass
class NegotiationEntry:
    """商談エントリ（詳細版）"""
    negotiation_id: str      # SHA-256[:16]
    counterparty: str        # 商談相手（社名）
    product_name: str        # 商品名
    category: str            # 8カテゴリ
    proposed_price_jpy: int  # 提示価格
    quantity: int            # 数量
    status: str              # VALID_STATUSES
    notes: str               # 備考
    created_at: str
    updated_at: str
    agreed_price_jpy: int = 0   # 合意価格（agreed/closed_won時）
    agreed_at: str = ''

    def to_dict(self) -> dict:
        return {
            'negotiation_id': self.negotiation_id,
            'counterparty': self.counterparty,
            'product_name': self.product_name,
            'category': self.category,
            'proposed_price_jpy': self.proposed_price_jpy,
            'quantity': self.quantity,
            'status': self.status,
            'notes': self.notes,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'agreed_price_jpy': self.agreed_price_jpy,
            'agreed_at': self.agreed_at,
        }


@dataclass
class SmartLifeProduct:
    """SmartLife商品マスタ登録エントリ"""
    product_id: str          # SHA-256[:16]
    negotiation_id: str      # 元の商談ID
    product_name: str
    category: str
    smartlife_category: str  # SMARTLIFE_CATEGORY_MAP変換後
    purchase_price_jpy: int  # 仕入価格（agreed_price_jpy）
    quantity: int
    registered_at: str
    status: str              # 'pending_review' | 'active' | 'rejected'
    human_review_required: bool = True  # 常にTrue — 自動登録禁止 — 人間レビュー後に有効化

    def __setattr__(self, name: str, value: object) -> None:
        """human_review_required は常に True — 変更禁止"""
        if name == 'human_review_required' and value is not True:
            raise ValueError(
                'human_review_required は常に True です。'
                '自動登録禁止 — 人間レビュー後に有効化してください。'
            )
        super().__setattr__(name, value)

    def to_dict(self) -> dict:
        return {
            'product_id': self.product_id,
            'negotiation_id': self.negotiation_id,
            'product_name': self.product_name,
            'category': self.category,
            'smartlife_category': self.smartlife_category,
            'purchase_price_jpy': self.purchase_price_jpy,
            'quantity': self.quantity,
            'registered_at': self.registered_at,
            'status': self.status,
            'human_review_required': self.human_review_required,
        }


# ──────────────────────────────────────────
# 商談マネージャ
# ──────────────────────────────────────────

class NegotiationManager:
    """
    商談サポートAPIコアクラス。
    インメモリストレージ（MVP）。G3でFirestore永続化予定。

    【Gate D制約】
    - AIは提案生成まで。最終送信は人間担当者が承認後に手動実行。
    - SmartLife自動登録禁止 — human_review_required は常に True。
    - pending_review ステータスで停止、人間レビュー待ち。
    """

    def __init__(self) -> None:
        self._negotiations: dict[str, NegotiationEntry] = {}
        self._smartlife_products: list[SmartLifeProduct] = []

    # ── CRUD ──────────────────────────────

    def create(
        self,
        counterparty: str,
        product_name: str,
        category: str,
        proposed_price_jpy: int,
        quantity: int,
        notes: str = '',
    ) -> NegotiationEntry:
        """商談エントリを新規作成する"""
        now = datetime.now(timezone.utc).isoformat()
        negotiation_id = hashlib.sha256(
            f'{counterparty}:{product_name}:{now}'.encode()
        ).hexdigest()[:16]

        entry = NegotiationEntry(
            negotiation_id=negotiation_id,
            counterparty=counterparty,
            product_name=product_name,
            category=category,
            proposed_price_jpy=proposed_price_jpy,
            quantity=quantity,
            status=STATUS_INITIAL_CONTACT,
            notes=notes,
            created_at=now,
            updated_at=now,
        )
        self._negotiations[negotiation_id] = entry
        return entry

    def get(self, negotiation_id: str) -> NegotiationEntry:
        """IDで商談エントリを取得する。見つからない場合は KeyError。"""
        if negotiation_id not in self._negotiations:
            raise KeyError(f'negotiation_id not found: {negotiation_id}')
        return self._negotiations[negotiation_id]

    def update_status(
        self,
        negotiation_id: str,
        status: str,
        notes: str = '',
    ) -> NegotiationEntry:
        """商談ステータスを更新する。無効ステータスは ValueError。"""
        if status not in VALID_STATUSES:
            raise ValueError(f'Invalid status: {status!r}. Must be one of {VALID_STATUSES}')
        entry = self.get(negotiation_id)
        entry.status = status
        if notes:
            entry.notes = notes
        entry.updated_at = datetime.now(timezone.utc).isoformat()
        return entry

    def agree(self, negotiation_id: str, agreed_price_jpy: int) -> NegotiationEntry:
        """合意価格を設定し、ステータスを agreed に変更する。"""
        entry = self.get(negotiation_id)
        now = datetime.now(timezone.utc).isoformat()
        entry.status = STATUS_AGREED
        entry.agreed_price_jpy = agreed_price_jpy
        entry.agreed_at = now
        entry.updated_at = now
        return entry

    def list_all(self, status: Optional[str] = None) -> list[NegotiationEntry]:
        """全商談を返す。status 指定時はフィルタリングする。"""
        entries = list(self._negotiations.values())
        if status is not None:
            entries = [e for e in entries if e.status == status]
        return entries

    # ── PDF出力（HTML形式）────────────────

    def export_pdf_html(self, negotiation_id: str) -> str:
        """商談レポートをHTML形式で生成（stdlib only / 印刷用）。
        内容: 商談相手・日付・提示条件・合意内容・備考。
        ヘッダーに「NiceEze SURPLUS SHIFT 商談レポート」。
        @media print CSS付き。
        """
        entry = self.get(negotiation_id)

        def esc(v: object) -> str:
            return html.escape(str(v))

        agreed_section = ''
        if entry.agreed_price_jpy:
            agreed_section = f'''
        <tr><th>合意価格</th><td>¥{esc(entry.agreed_price_jpy):}</td></tr>
        <tr><th>合意日時</th><td>{esc(entry.agreed_at)}</td></tr>
'''

        report_html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <title>NiceEze SURPLUS SHIFT 商談レポート</title>
  <style>
    body {{ font-family: "Noto Sans JP", sans-serif; margin: 40px; color: #222; }}
    h1 {{ font-size: 1.4em; border-bottom: 2px solid #333; padding-bottom: 8px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
    th, td {{ border: 1px solid #ccc; padding: 8px 12px; text-align: left; }}
    th {{ background: #f5f5f5; width: 30%; }}
    .notes {{ margin-top: 20px; padding: 12px; background: #fafafa; border: 1px solid #ddd; }}
    .footer {{ margin-top: 40px; font-size: 0.8em; color: #888; }}
    @media print {{
      body {{ margin: 20mm; }}
      .no-print {{ display: none; }}
    }}
  </style>
</head>
<body>
  <h1>NiceEze SURPLUS SHIFT 商談レポート</h1>
  <table>
    <tr><th>商談ID</th><td>{esc(entry.negotiation_id)}</td></tr>
    <tr><th>商談相手</th><td>{esc(entry.counterparty)}</td></tr>
    <tr><th>商品名</th><td>{esc(entry.product_name)}</td></tr>
    <tr><th>カテゴリ</th><td>{esc(entry.category)}</td></tr>
    <tr><th>提示価格</th><td>¥{esc(entry.proposed_price_jpy)}</td></tr>
    <tr><th>数量</th><td>{esc(entry.quantity)}</td></tr>
    <tr><th>ステータス</th><td>{esc(entry.status)}</td></tr>
    <tr><th>作成日時</th><td>{esc(entry.created_at)}</td></tr>
    <tr><th>更新日時</th><td>{esc(entry.updated_at)}</td></tr>
    {agreed_section}
  </table>
  <div class="notes">
    <strong>備考:</strong><br>
    {esc(entry.notes) if entry.notes else '（なし）'}
  </div>
  <div class="footer">
    NiceEze SURPLUS SHIFT — 商談レポート自動生成 (Ver 1.0)<br>
    ※ 最終送信は必ず人間担当者が承認後に手動実行してください。
  </div>
</body>
</html>'''
        return report_html

    # ── SmartLife連携 ─────────────────────

    def to_smartlife(self, negotiation_id: str) -> SmartLifeProduct:
        """
        合意済み商談をSmartLife商品マスタへ登録。
        status が agreed/closed_won 以外は ValueError。
        human_review_required: True を常に設定。
        自動登録禁止 — 人間レビュー後に有効化。
        SmartLife実APIはG3実装予定 — MVPはローカル保存のみ。
        """
        entry = self.get(negotiation_id)
        if entry.status not in (STATUS_AGREED, STATUS_CLOSED_WON):
            raise ValueError(
                f'商談ステータスが agreed または closed_won ではありません: {entry.status!r}'
            )

        now = datetime.now(timezone.utc).isoformat()
        product_id = hashlib.sha256(
            f'{negotiation_id}:{now}'.encode()
        ).hexdigest()[:16]

        # SmartLifeカテゴリへのマッピング（未知のカテゴリは'unknown'）
        smartlife_category = SMARTLIFE_CATEGORY_MAP.get(entry.category, 'unknown')

        # 自動登録禁止 — 人間レビュー後に有効化
        product = SmartLifeProduct(
            product_id=product_id,
            negotiation_id=negotiation_id,
            product_name=entry.product_name,
            category=entry.category,
            smartlife_category=smartlife_category,
            purchase_price_jpy=entry.agreed_price_jpy,
            quantity=entry.quantity,
            registered_at=now,
            status='pending_review',   # 人間レビュー待ち — 自動有効化禁止
            human_review_required=True,  # 常にTrue — 変更禁止
        )
        self._smartlife_products.append(product)
        return product

    def get_smartlife_products(self) -> list[SmartLifeProduct]:
        """登録済みSmartLife商品マスタエントリ一覧を返す"""
        return list(self._smartlife_products)

    def summary(self) -> dict:
        """商談数、ステータス別件数、SmartLife登録数を返す"""
        status_counts = {s: 0 for s in VALID_STATUSES}
        for entry in self._negotiations.values():
            if entry.status in status_counts:
                status_counts[entry.status] += 1
        return {
            'total_negotiations': len(self._negotiations),
            'by_status': status_counts,
            'smartlife_registered': len(self._smartlife_products),
        }
