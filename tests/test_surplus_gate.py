"""
Unit tests for SURPLUS SHIFT Gate A〜D logic.
stdlib unittest only — no additional dependencies.
"""
from __future__ import annotations

import unittest

from src.surplus_shift.gate_a import KeepaClient, PriceSnapshot
from src.surplus_shift.gate_b import (
    GrossMarginCalc,
    GrossMarginResult,
    PurchaseDecision,
    MIN_GROSS_MARGIN_RATE,
    CONDITIONAL_MARGIN_RATE,
)
from src.surplus_shift.gate_c import InventoryScorer, DEMAND_SCORE_THRESHOLD
from src.surplus_shift.gate_d import (
    CashFlowJudge,
    MonthlyCFInput,
    MAX_MONTHLY_PROCUREMENT_JPY,
    MIN_CF_RESERVE_JPY,
)


# ──────────────────────────────────────────
# Gate A Tests
# ──────────────────────────────────────────

class TestGateA(unittest.TestCase):

    def setUp(self) -> None:
        self.client = KeepaClient()  # mock mode (no api_key)

    def test_health_check_mock_status(self) -> None:
        result = self.client.health_check()
        self.assertEqual(result['status'], 'mock')

    def test_health_check_api_key_not_set(self) -> None:
        result = self.client.health_check()
        self.assertFalse(result['api_key_set'])

    def test_fetch_returns_price_snapshot(self) -> None:
        snap = self.client.fetch('B08N5WRWNW')
        self.assertIsInstance(snap, PriceSnapshot)

    def test_fetch_prices_positive(self) -> None:
        snap = self.client.fetch('B08N5WRWNW')
        self.assertGreater(snap.amazon_price_jpy, 0)
        self.assertGreater(snap.new_lowest_jpy, 0)

    def test_fetch_sales_rank_positive(self) -> None:
        snap = self.client.fetch('B08N5WRWNW')
        self.assertGreater(snap.sales_rank, 0)

    def test_fetch_source_is_mock(self) -> None:
        snap = self.client.fetch('B08N5WRWNW')
        self.assertEqual(snap.source, 'keepa_mock')

    def test_fetch_fetched_at_non_empty(self) -> None:
        snap = self.client.fetch('B08N5WRWNW')
        self.assertTrue(snap.fetched_at)

    def test_to_dict_contains_required_keys(self) -> None:
        snap = self.client.fetch('B08N5WRWNW')
        d = KeepaClient.to_dict(snap)
        required_keys = {
            'asin', 'title', 'amazon_price_jpy', 'new_lowest_jpy',
            'used_lowest_jpy', 'sales_rank', 'category', 'fetched_at', 'source',
        }
        self.assertTrue(required_keys.issubset(d.keys()))


# ──────────────────────────────────────────
# Gate B Tests
# ──────────────────────────────────────────

class TestGateB(unittest.TestCase):

    def setUp(self) -> None:
        self.calc = GrossMarginCalc()

    def test_gross_margin_positive(self) -> None:
        result = self.calc.calculate('テスト商品', 1000, 2000)
        self.assertGreater(result.gross_margin_rate, 0)

    def test_is_viable_true_when_margin_sufficient(self) -> None:
        # 買値1000/売値2000 → margin well above 20%
        result = self.calc.calculate('テスト商品', 1000, 2000)
        self.assertTrue(result.is_viable)

    def test_is_viable_false_when_margin_low(self) -> None:
        # 買値1800/売値2000 → margin too low
        result = self.calc.calculate('テスト商品', 1800, 2000)
        self.assertFalse(result.is_viable)

    def test_decide_go_when_viable(self) -> None:
        result = self.calc.calculate('テスト商品', 1000, 2000)
        decision = self.calc.decide(result)
        self.assertEqual(decision, PurchaseDecision.GO)

    def test_decide_no_go_when_very_low_margin(self) -> None:
        # buying price 1950/selling price 2000 → very low margin
        result = self.calc.calculate('テスト商品', 1950, 2000)
        decision = self.calc.decide(result)
        self.assertEqual(decision, PurchaseDecision.NO_GO)

    def test_decide_conditional_when_between_thresholds(self) -> None:
        # Aim for gross_margin_rate between 0.15 and 0.20
        # selling=2000, platform_fee=200, fba=400
        # gross_profit = 2000 - purchase - 200 - 400 = 1400 - purchase
        # rate = (1400 - purchase) / 2000 = 0.17 → purchase = 1060
        result = self.calc.calculate('テスト商品', 1060, 2000)
        self.assertGreaterEqual(result.gross_margin_rate, CONDITIONAL_MARGIN_RATE)
        self.assertLess(result.gross_margin_rate, MIN_GROSS_MARGIN_RATE)
        decision = self.calc.decide(result)
        self.assertEqual(decision, PurchaseDecision.CONDITIONAL)

    def test_platform_fee_calculation(self) -> None:
        result = self.calc.calculate('テスト商品', 1000, 2000)
        self.assertEqual(result.platform_fee_jpy, int(2000 * 0.10))

    def test_to_dict_contains_required_keys(self) -> None:
        result = self.calc.calculate('テスト商品', 1000, 2000)
        d = GrossMarginCalc.to_dict(result)
        required_keys = {
            'keyword', 'purchase_price_jpy', 'selling_price_jpy',
            'platform_fee_jpy', 'fba_fee_jpy', 'gross_profit_jpy',
            'gross_margin_rate', 'is_viable', 'recommendation', 'calculated_at',
        }
        self.assertTrue(required_keys.issubset(d.keys()))

    def test_gross_profit_formula(self) -> None:
        # Verify the formula: gross_profit = sell - buy - platform_fee - fba
        result = self.calc.calculate('テスト商品', 1000, 2000, fba_fee_jpy=400)
        expected = 2000 - 1000 - int(2000 * 0.10) - 400
        self.assertEqual(result.gross_profit_jpy, expected)

    def test_zero_selling_price_no_division_error(self) -> None:
        result = self.calc.calculate('テスト商品', 0, 0)
        self.assertEqual(result.gross_margin_rate, 0.0)


# ──────────────────────────────────────────
# Gate C Tests
# ──────────────────────────────────────────

class TestGateC(unittest.TestCase):

    def setUp(self) -> None:
        self.scorer = InventoryScorer()

    def test_turnover_days_calculation(self) -> None:
        result = self.scorer.score('テスト商品', '日用品', stock_qty=100, avg_daily_sales=10.0)
        self.assertEqual(result.demand_forecast.turnover_days, 10.0)

    def test_surplus_risk_low_when_fast_turnover(self) -> None:
        result = self.scorer.score('テスト商品', '日用品', stock_qty=10, avg_daily_sales=2.0)
        self.assertEqual(result.surplus_risk, 'low')

    def test_surplus_risk_high_when_slow_turnover(self) -> None:
        result = self.scorer.score('テスト商品', '日用品', stock_qty=200, avg_daily_sales=1.0)
        self.assertEqual(result.surplus_risk, 'high')

    def test_demand_score_in_range(self) -> None:
        result = self.scorer.score('テスト商品', '日用品', stock_qty=100, avg_daily_sales=10.0)
        self.assertGreaterEqual(result.inventory_score, 0.0)
        self.assertLessEqual(result.inventory_score, 1.0)

    def test_is_recommended_true_when_high_demand(self) -> None:
        # High demand: top rank=1, very fast turnover
        result = self.scorer.score('テスト商品', '日用品', stock_qty=5, avg_daily_sales=5.0, sales_rank=1)
        self.assertGreaterEqual(result.inventory_score, DEMAND_SCORE_THRESHOLD)
        self.assertTrue(result.is_recommended)

    def test_batch_score_returns_list(self) -> None:
        items = [
            {'keyword': '商品A', 'category': '日用品', 'stock_qty': 50, 'avg_daily_sales': 5.0},
            {'keyword': '商品B', 'category': '食品', 'stock_qty': 100, 'avg_daily_sales': 2.0, 'sales_rank': 200},
        ]
        results = self.scorer.batch_score(items)
        self.assertEqual(len(results), 2)

    def test_to_dict_returns_dict(self) -> None:
        result = self.scorer.score('テスト商品', '日用品', stock_qty=50, avg_daily_sales=5.0)
        d = InventoryScorer.to_dict(result)
        self.assertIsInstance(d, dict)
        self.assertIn('inventory_score', d)
        self.assertIn('demand_forecast', d)

    def test_zero_daily_sales_no_error(self) -> None:
        result = self.scorer.score('テスト商品', '日用品', stock_qty=100, avg_daily_sales=0.0)
        self.assertEqual(result.surplus_risk, 'high')


# ──────────────────────────────────────────
# Gate D Tests
# ──────────────────────────────────────────

class TestGateD(unittest.TestCase):

    def _healthy_input(self) -> MonthlyCFInput:
        """CF充足な入力データ"""
        return MonthlyCFInput(
            month='2026-06',
            opening_balance_jpy=1_000_000,
            monthly_revenue_jpy=800_000,
            fixed_costs_jpy=200_000,
            variable_costs_jpy=100_000,
            planned_procurement_jpy=300_000,
        )

    def _low_balance_input(self) -> MonthlyCFInput:
        """CF不足な入力データ"""
        return MonthlyCFInput(
            month='2026-06',
            opening_balance_jpy=100_000,
            monthly_revenue_jpy=100_000,
            fixed_costs_jpy=200_000,
            variable_costs_jpy=100_000,
            planned_procurement_jpy=300_000,
        )

    def setUp(self) -> None:
        self.judge = CashFlowJudge()

    def test_healthy_cf_procurement_feasible(self) -> None:
        result = self.judge.judge(self._healthy_input())
        self.assertTrue(result.procurement_feasible)
        self.assertTrue(result.cf_reserve_sufficient)

    def test_low_balance_procurement_not_feasible(self) -> None:
        result = self.judge.judge(self._low_balance_input())
        self.assertFalse(result.procurement_feasible)

    def test_human_approval_required_always_true(self) -> None:
        result = self.judge.judge(self._healthy_input())
        self.assertTrue(result.human_approval_required)

    def test_human_approval_required_cannot_be_false(self) -> None:
        from src.surplus_shift.gate_d import CFJudgement
        from datetime import datetime, timezone
        with self.assertRaises(ValueError):
            CFJudgement(
                month='2026-06',
                opening_balance_jpy=1_000_000,
                projected_closing_balance_jpy=1_000_000,
                procurement_feasible=True,
                cf_reserve_sufficient=True,
                surplus_shift_recommended=False,
                negotiation_draft='',
                human_approval_required=False,  # Must raise ValueError
                judgement_at=datetime.now(timezone.utc).isoformat(),
            )

    def test_surplus_shift_recommended_when_cf_insufficient(self) -> None:
        result = self.judge.judge(self._low_balance_input())
        self.assertTrue(result.surplus_shift_recommended)

    def test_negotiation_draft_contains_warning(self) -> None:
        result = self.judge.judge(self._low_balance_input())
        self.assertIn('【人間担当者承認後に送信すること】', result.negotiation_draft)

    def test_negotiation_draft_not_empty_when_surplus_recommended(self) -> None:
        result = self.judge.judge(self._low_balance_input())
        self.assertTrue(result.surplus_shift_recommended)
        self.assertTrue(result.negotiation_draft)

    def test_projected_closing_calculation(self) -> None:
        cf_input = self._healthy_input()
        result = self.judge.judge(cf_input)
        expected = (
            cf_input.opening_balance_jpy
            + cf_input.monthly_revenue_jpy
            - cf_input.fixed_costs_jpy
            - cf_input.variable_costs_jpy
            - cf_input.planned_procurement_jpy
            + cf_input.surplus_shift_revenue_jpy
        )
        self.assertEqual(result.projected_closing_balance_jpy, expected)

    def test_monthly_summary_returns_dict_with_all_keys(self) -> None:
        summary = self.judge.monthly_summary(self._healthy_input())
        required_keys = {
            'month', 'projected_closing_balance_jpy', 'procurement_feasible',
            'cf_reserve_sufficient', 'surplus_shift_recommended',
            'negotiation_draft', 'human_approval_required', 'input', 'constants',
        }
        self.assertTrue(required_keys.issubset(summary.keys()))

    def test_zero_surplus_shift_revenue_works(self) -> None:
        cf_input = MonthlyCFInput(
            month='2026-06',
            opening_balance_jpy=500_000,
            monthly_revenue_jpy=300_000,
            fixed_costs_jpy=100_000,
            variable_costs_jpy=50_000,
            planned_procurement_jpy=200_000,
            surplus_shift_revenue_jpy=0,
        )
        result = self.judge.judge(cf_input)
        self.assertIsNotNone(result)

    def test_max_monthly_procurement_enforced(self) -> None:
        cf_input = MonthlyCFInput(
            month='2026-06',
            opening_balance_jpy=2_000_000,
            monthly_revenue_jpy=1_000_000,
            fixed_costs_jpy=100_000,
            variable_costs_jpy=100_000,
            planned_procurement_jpy=MAX_MONTHLY_PROCUREMENT_JPY + 1,  # Exceeds limit
        )
        result = self.judge.judge(cf_input)
        self.assertFalse(result.procurement_feasible)


class TestNegotiationLog(unittest.TestCase):
    def setUp(self):
        from src.surplus_shift.negotiation_log import NegotiationLog, STATUS_DRAFT, STATUS_HUMAN_APPROVED, STATUS_SENT, STATUS_REJECTED
        self.log = NegotiationLog()
        self.STATUS_DRAFT = STATUS_DRAFT
        self.STATUS_HUMAN_APPROVED = STATUS_HUMAN_APPROVED
        self.STATUS_SENT = STATUS_SENT
        self.STATUS_REJECTED = STATUS_REJECTED

    def test_add_draft_returns_record(self):
        rec = self.log.add_draft('2026-06', '交渉案テキスト')
        self.assertEqual(rec.status, self.STATUS_DRAFT)

    def test_draft_id_is_64_char_sha256(self):
        rec = self.log.add_draft('2026-06', '交渉案テキスト')
        self.assertEqual(len(rec.record_id), 64)

    def test_human_approve_changes_status(self):
        rec = self.log.add_draft('2026-06', '交渉案')
        approved = self.log.human_approve(rec.record_id, '松浦CEO')
        self.assertEqual(approved.status, self.STATUS_HUMAN_APPROVED)
        self.assertEqual(approved.human_approved_by, '松浦CEO')

    def test_mark_sent_requires_human_approval(self):
        rec = self.log.add_draft('2026-06', '交渉案')
        with self.assertRaises(ValueError):
            self.log.mark_sent(rec.record_id)

    def test_mark_sent_after_approve(self):
        rec = self.log.add_draft('2026-06', '交渉案')
        self.log.human_approve(rec.record_id, '松浦CEO')
        sent = self.log.mark_sent(rec.record_id)
        self.assertEqual(sent.status, self.STATUS_SENT)

    def test_reject_changes_status(self):
        rec = self.log.add_draft('2026-06', '交渉案')
        rejected = self.log.reject(rec.record_id, '内容修正必要')
        self.assertEqual(rejected.status, self.STATUS_REJECTED)

    def test_get_by_status(self):
        self.log.add_draft('2026-06', 'draft1')
        rec2 = self.log.add_draft('2026-06', 'draft2')
        self.log.human_approve(rec2.record_id, '松浦CEO')
        self.assertEqual(len(self.log.get_by_status(self.STATUS_DRAFT)), 1)
        self.assertEqual(len(self.log.get_by_status(self.STATUS_HUMAN_APPROVED)), 1)

    def test_get_by_month(self):
        self.log.add_draft('2026-06', 'draft1')
        self.log.add_draft('2026-07', 'draft2')
        self.assertEqual(len(self.log.get_by_month('2026-06')), 1)

    def test_summary_has_required_keys(self):
        s = self.log.summary()
        for k in ('total', 'draft', 'human_approved', 'sent', 'rejected', 'human_approval_required'):
            self.assertIn(k, s)

    def test_summary_human_approval_required_always_true(self):
        s = self.log.summary()
        self.assertTrue(s['human_approval_required'])

    def test_to_dict_has_human_approval_required(self):
        rec = self.log.add_draft('2026-06', '交渉案')
        d = rec.to_dict()
        self.assertTrue(d['human_approval_required'])


if __name__ == '__main__':
    unittest.main()
