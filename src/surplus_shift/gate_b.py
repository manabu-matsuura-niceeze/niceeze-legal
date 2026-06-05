"""Gate B — 粗利計算・仕入判断ロジック (Ver 1.0)"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


# ──────────────────────────────────────────
# 定数
# ──────────────────────────────────────────

PLATFORM_FEE_RATE = 0.10        # プラットフォーム手数料率 10%
FBA_FEE_DEFAULT_JPY = 400       # FBA手数料デフォルト
MIN_GROSS_MARGIN_RATE = 0.20    # 最低粗利率 20%（仕入判断閾値）
CONDITIONAL_MARGIN_RATE = 0.15  # 条件付き粗利率下限 15%


# ──────────────────────────────────────────
# データモデル
# ──────────────────────────────────────────

class PurchaseDecision(str, Enum):
    GO = 'GO'
    NO_GO = 'NO_GO'
    CONDITIONAL = 'CONDITIONAL'     # 条件付き（粗利率 15〜20%）


@dataclass
class GrossMarginResult:
    """粗利計算結果"""
    keyword: str
    purchase_price_jpy: int         # 仕入れ価格
    selling_price_jpy: int          # 販売価格
    platform_fee_jpy: int           # プラットフォーム手数料
    fba_fee_jpy: int                # FBA手数料
    gross_profit_jpy: int           # 粗利額
    gross_margin_rate: float        # 粗利率 (0.0〜1.0)
    is_viable: bool                 # 仕入れ判断（粗利率 ≥ MIN_GROSS_MARGIN_RATE）
    recommendation: str             # 推奨コメント
    calculated_at: str              # ISO datetime UTC


# ──────────────────────────────────────────
# 粗利計算エンジン
# ──────────────────────────────────────────

class GrossMarginCalc:
    """粗利率計算・仕入判断クラス"""

    def calculate(
        self,
        keyword: str,
        purchase_price_jpy: int,
        selling_price_jpy: int,
        fba_fee_jpy: int = FBA_FEE_DEFAULT_JPY,
    ) -> GrossMarginResult:
        """
        粗利計算を実行し GrossMarginResult を返す。

        粗利額 = 販売価格 - 仕入価格 - プラットフォーム手数料 - FBA手数料
        粗利率 = 粗利額 / 販売価格
        """
        platform_fee = int(selling_price_jpy * PLATFORM_FEE_RATE)
        gross_profit = (
            selling_price_jpy
            - purchase_price_jpy
            - platform_fee
            - fba_fee_jpy
        )
        gross_margin_rate = (
            gross_profit / selling_price_jpy if selling_price_jpy > 0 else 0.0
        )
        is_viable = gross_margin_rate >= MIN_GROSS_MARGIN_RATE

        # 推奨コメント
        if gross_margin_rate >= MIN_GROSS_MARGIN_RATE:
            recommendation = (
                f'GO — 粗利率 {gross_margin_rate:.1%} (≥{MIN_GROSS_MARGIN_RATE:.0%}) 仕入推奨'
            )
        elif gross_margin_rate >= CONDITIONAL_MARGIN_RATE:
            recommendation = (
                f'CONDITIONAL — 粗利率 {gross_margin_rate:.1%} '
                f'({CONDITIONAL_MARGIN_RATE:.0%}〜{MIN_GROSS_MARGIN_RATE:.0%}) 条件次第で仕入可'
            )
        else:
            recommendation = (
                f'NO_GO — 粗利率 {gross_margin_rate:.1%} (<{CONDITIONAL_MARGIN_RATE:.0%}) 仕入非推奨'
            )

        return GrossMarginResult(
            keyword=keyword,
            purchase_price_jpy=purchase_price_jpy,
            selling_price_jpy=selling_price_jpy,
            platform_fee_jpy=platform_fee,
            fba_fee_jpy=fba_fee_jpy,
            gross_profit_jpy=gross_profit,
            gross_margin_rate=round(gross_margin_rate, 4),
            is_viable=is_viable,
            recommendation=recommendation,
            calculated_at=datetime.now(timezone.utc).isoformat(),
        )

    def decide(self, result: GrossMarginResult) -> PurchaseDecision:
        """粗利率から仕入判断を返す"""
        if result.gross_margin_rate >= MIN_GROSS_MARGIN_RATE:
            return PurchaseDecision.GO
        if result.gross_margin_rate >= CONDITIONAL_MARGIN_RATE:
            return PurchaseDecision.CONDITIONAL
        return PurchaseDecision.NO_GO

    @staticmethod
    def to_dict(result: GrossMarginResult) -> dict:
        """GrossMarginResult を辞書に変換"""
        return {
            'keyword': result.keyword,
            'purchase_price_jpy': result.purchase_price_jpy,
            'selling_price_jpy': result.selling_price_jpy,
            'platform_fee_jpy': result.platform_fee_jpy,
            'fba_fee_jpy': result.fba_fee_jpy,
            'gross_profit_jpy': result.gross_profit_jpy,
            'gross_margin_rate': result.gross_margin_rate,
            'is_viable': result.is_viable,
            'recommendation': result.recommendation,
            'calculated_at': result.calculated_at,
        }
