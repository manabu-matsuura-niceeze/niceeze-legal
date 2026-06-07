"""AIサポート会話ログ匿名化モジュール

個人識別情報（PII）を正規表現でマスクする。
TASK-6: AIサポートログ匿名化（保持期間90日）
"""

import re
from typing import Dict, List, Optional

MASK_PATTERNS: Dict[str, str] = {
    "name_ja": r"[ぁ-んァ-ン一-龥]{2,4}[\s　][ぁ-んァ-ン一-龥]{1,4}",  # 日本人名
    "phone": r"0\d{1,4}[-－]\d{1,4}[-－]\d{4}",
    "email": r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    "qr_token": r"[A-Za-z0-9_\-]{32,}",  # QRトークン（32文字以上）
    "credit_card": r"\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}",
}

MASK_REPLACEMENT = "[MASKED]"


class Anonymizer:
    """テキストおよびレコード内のPIIをマスクするクラス

    Args:
        patterns: カスタムパターン辞書（未指定時は MASK_PATTERNS を使用）
    """

    def __init__(self, patterns: Optional[Dict[str, str]] = None) -> None:
        self._patterns = patterns if patterns is not None else MASK_PATTERNS
        # コンパイル済み正規表現をキャッシュ
        self._compiled: Dict[str, re.Pattern] = {
            name: re.compile(pattern)
            for name, pattern in self._patterns.items()
        }

    def mask(self, text: str) -> str:
        """テキスト内のPIIパターンを [MASKED] に置換する

        パターンは定義順に適用される。クレジットカード番号は
        電話番号・QRトークンより優先的に適用するため先に処理する。
        """
        if not text:
            return text

        result = text
        # credit_card を先に処理（数字パターンが他と重複する可能性があるため）
        priority_keys = ["credit_card", "phone", "email", "qr_token", "name_ja"]
        ordered_keys = priority_keys + [k for k in self._compiled if k not in priority_keys]

        for key in ordered_keys:
            if key in self._compiled:
                result = self._compiled[key].sub(MASK_REPLACEMENT, result)
        return result

    def mask_record(self, record: dict, fields: List[str]) -> dict:
        """レコード辞書の指定フィールドをマスクして返す（元レコードは変更しない）

        Args:
            record: 対象レコード辞書
            fields: マスクするフィールド名リスト
        """
        result = dict(record)
        for field in fields:
            if field in result and isinstance(result[field], str):
                result[field] = self.mask(result[field])
        return result
