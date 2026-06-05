"""Gate D — 月次CF整合判定 A案：実数値設定 (Ver 1.0)
【重要】自律商談の最終送信は必ず人間担当者が承認してから実行すること。
AIは交渉案作成・提示までに留める（自動送信禁止）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


# ──────────────────────────────────────────
# 定数
# ──────────────────────────────────────────

MAX_MONTHLY_PROCUREMENT_JPY = 500_000   # 月次仕入れ上限 ¥50万
MIN_CF_RESERVE_JPY = 200_000            # CF最低留保額 ¥20万
SURPLUS_SHIFT_COMMISSION_RATE = 0.05    # 余剰転換手数料率 5%


# ──────────────────────────────────────────
# データモデル
# ──────────────────────────────────────────

@dataclass
class MonthlyCFInput:
    """月次CF入力データ（A案：実数値設定）"""
    month: str                              # 'YYYY-MM' format
    opening_balance_jpy: int               # 月初CF残高（実数値 A案）
    monthly_revenue_jpy: int               # 月次売上（実数値 A案）
    fixed_costs_jpy: int                   # 固定費（実数値 A案）
    variable_costs_jpy: int                # 変動費（実数値 A案）
    planned_procurement_jpy: int           # 計画仕入れ額（実数値 A案）
    surplus_shift_revenue_jpy: int = 0     # 余剰転換収入


@dataclass
class CFJudgement:
    """CF整合判定結果"""
    month: str
    opening_balance_jpy: int
    projected_closing_balance_jpy: int     # 月末CF予測残高
    procurement_feasible: bool             # 仕入れ実行可否
    cf_reserve_sufficient: bool            # CF留保額充足
    surplus_shift_recommended: bool        # 余剰転換推奨（CF不足時）
    negotiation_draft: str                 # 【AI生成】交渉案文（提示のみ・送信禁止）
    human_approval_required: bool          # 常にTrue — 自動送信禁止
    judgement_at: str                      # ISO datetime UTC

    def __setattr__(self, name: str, value: object) -> None:
        """human_approval_required は常に True — 変更禁止"""
        if name == 'human_approval_required' and value is not True:
            raise ValueError(
                'human_approval_required は常に True です。'
                '自律商談の自動送信は禁止されています。'
            )
        super().__setattr__(name, value)


# ──────────────────────────────────────────
# CF判定エンジン
# ──────────────────────────────────────────

class CashFlowJudge:
    """
    月次CF整合判定クラス。

    【重要】negotiation_draft は AI が生成した交渉案文です。
    最終送信は必ず人間担当者が確認・承認してから実行してください。
    自動送信は禁止されています。
    """

    def judge(self, cf_input: MonthlyCFInput) -> CFJudgement:
        """
        月次CF整合を判定し CFJudgement を返す。

        projected_closing = opening_balance + monthly_revenue
                            - fixed_costs - variable_costs
                            - planned_procurement + surplus_shift_revenue
        """
        projected_closing = (
            cf_input.opening_balance_jpy
            + cf_input.monthly_revenue_jpy
            - cf_input.fixed_costs_jpy
            - cf_input.variable_costs_jpy
            - cf_input.planned_procurement_jpy
            + cf_input.surplus_shift_revenue_jpy
        )

        procurement_feasible = (
            cf_input.planned_procurement_jpy <= MAX_MONTHLY_PROCUREMENT_JPY
            and projected_closing >= MIN_CF_RESERVE_JPY
        )
        cf_reserve_sufficient = projected_closing >= MIN_CF_RESERVE_JPY
        surplus_shift_recommended = not cf_reserve_sufficient

        negotiation_draft = self._build_negotiation_draft(
            cf_input=cf_input,
            projected_closing=projected_closing,
            surplus_shift_recommended=surplus_shift_recommended,
        )

        return CFJudgement(
            month=cf_input.month,
            opening_balance_jpy=cf_input.opening_balance_jpy,
            projected_closing_balance_jpy=projected_closing,
            procurement_feasible=procurement_feasible,
            cf_reserve_sufficient=cf_reserve_sufficient,
            surplus_shift_recommended=surplus_shift_recommended,
            negotiation_draft=negotiation_draft,
            human_approval_required=True,  # 変更禁止
            judgement_at=datetime.now(timezone.utc).isoformat(),
        )

    def monthly_summary(self, cf_input: MonthlyCFInput) -> dict:
        """CF判定結果のフルサマリー辞書を返す"""
        judgement = self.judge(cf_input)
        result = self.to_dict(judgement)
        result['input'] = {
            'month': cf_input.month,
            'opening_balance_jpy': cf_input.opening_balance_jpy,
            'monthly_revenue_jpy': cf_input.monthly_revenue_jpy,
            'fixed_costs_jpy': cf_input.fixed_costs_jpy,
            'variable_costs_jpy': cf_input.variable_costs_jpy,
            'planned_procurement_jpy': cf_input.planned_procurement_jpy,
            'surplus_shift_revenue_jpy': cf_input.surplus_shift_revenue_jpy,
        }
        result['constants'] = {
            'max_monthly_procurement_jpy': MAX_MONTHLY_PROCUREMENT_JPY,
            'min_cf_reserve_jpy': MIN_CF_RESERVE_JPY,
            'surplus_shift_commission_rate': SURPLUS_SHIFT_COMMISSION_RATE,
        }
        return result

    @staticmethod
    def to_dict(judgement: CFJudgement) -> dict:
        """CFJudgement を辞書に変換"""
        return {
            'month': judgement.month,
            'opening_balance_jpy': judgement.opening_balance_jpy,
            'projected_closing_balance_jpy': judgement.projected_closing_balance_jpy,
            'procurement_feasible': judgement.procurement_feasible,
            'cf_reserve_sufficient': judgement.cf_reserve_sufficient,
            'surplus_shift_recommended': judgement.surplus_shift_recommended,
            'negotiation_draft': judgement.negotiation_draft,
            'human_approval_required': judgement.human_approval_required,
            'judgement_at': judgement.judgement_at,
        }

    # ── 内部メソッド ──────────────────────────

    @staticmethod
    def _build_negotiation_draft(
        cf_input: MonthlyCFInput,
        projected_closing: int,
        surplus_shift_recommended: bool,
    ) -> str:
        """
        AI交渉案文を生成する。
        CF充足時は空文字列、不足時は余剰在庫転換提案文を返す。
        最終送信は必ず人間担当者が承認してから実行すること。
        """
        if not surplus_shift_recommended:
            return '（CF充足 — 余剰転換交渉案不要）'

        shortfall = MIN_CF_RESERVE_JPY - projected_closing
        estimated_surplus_items = max(1, shortfall // 5000)
        commission = int(shortfall * SURPLUS_SHIFT_COMMISSION_RATE)

        draft = (
            '【AI交渉案 — 人間承認必須・自動送信禁止】\n'
            '余剰在庫転換提案：\n\n'
            f'対象月: {cf_input.month}\n'
            f'CF不足額（概算）: ¥{shortfall:,}\n'
            f'推定余剰在庫転換点数: 約 {estimated_surplus_items} 点\n'
            f'転換手数料（概算 {SURPLUS_SHIFT_COMMISSION_RATE:.0%}）: ¥{commission:,}\n\n'
            '提案内容:\n'
            '　弊社では現在、余剰在庫を保有しており、貴社のプラットフォームを通じた\n'
            '　販売転換をご提案申し上げます。迅速な在庫回転と双方のキャッシュフロー改善を\n'
            '　実現できると考えております。\n\n'
            '　詳細条件については別途ご相談させていただけますと幸いです。\n\n'
            '【人間担当者承認後に送信すること】\n'
            '※ この交渉案は AI が自動生成したドラフトです。\n'
            '※ 内容を必ずご確認・修正の上、担当者が手動で送信してください。\n'
            '※ システムによる自動送信は行いません。'
        )
        return draft
