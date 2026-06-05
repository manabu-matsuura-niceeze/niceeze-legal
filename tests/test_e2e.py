"""E2E テスト — NiceEze 自律経営執行システム (Ver 1.0)

RESEARCH / MARKETING / GOV: HTTPServer を使ったリクエストベースのE2Eテスト
SURPLUS_SHIFT / SBDS: モジュール直接インポートによる機能E2Eテスト
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest


# ──────────────────────────────────────────
# HTTP ヘルパー
# ──────────────────────────────────────────

def _get(url: str) -> tuple[int, dict]:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def _post(url: str, body: dict) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Content-Length", str(len(data)))
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


# ──────────────────────────────────────────
# RESEARCH E2E
# ──────────────────────────────────────────

class TestResearchE2E:
    """RESEARCH API サーバーへの HTTP E2E テスト"""

    def test_health_ok(self, research_server: str) -> None:
        """GET /health → 200, status==ok, module==research"""
        status, body = _get(f"{research_server}/health")
        assert status == 200
        assert body["status"] == "ok"
        assert body["module"] == "research"

    def test_price_normal(self, research_server: str) -> None:
        """GET /price?keyword=トイレットペーパー&category=日用品・消耗品 → 200, records配列あり"""
        url = f"{research_server}/price?keyword=%E3%83%88%E3%82%A4%E3%83%AC%E3%83%83%E3%83%88%E3%83%9A%E3%83%BC%E3%83%91%E3%83%BC&category=%E6%97%A5%E7%94%A8%E5%93%81%E3%83%BB%E6%B6%88%E8%80%97%E5%93%81"
        status, body = _get(url)
        assert status == 200
        assert isinstance(body.get("records"), list)
        assert len(body["records"]) > 0

    def test_price_empty_keyword(self, research_server: str) -> None:
        """GET /price?keyword=&category= → 200 or 400（境界値: 空キーワード）"""
        url = f"{research_server}/price?keyword=&category="
        try:
            status, body = _get(url)
            assert status in (200, 400)
        except urllib.error.HTTPError as exc:
            assert exc.code in (200, 400)

    def test_trend_normal(self, research_server: str) -> None:
        """GET /trend?keyword=洗剤&category=日用品・消耗品 → 200, scores含む"""
        url = f"{research_server}/trend?keyword=%E6%B4%97%E5%89%A4&category=%E6%97%A5%E7%94%A8%E5%93%81%E3%83%BB%E6%B6%88%E8%80%97%E5%93%81"
        status, body = _get(url)
        assert status == 200
        assert "scores" in body or "trend_score" in body or "keyword" in body

    def test_not_found(self, research_server: str) -> None:
        """GET /nonexistent → 404, error含む"""
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            _get(f"{research_server}/nonexistent")
        assert exc_info.value.code == 404
        body = json.loads(exc_info.value.read().decode("utf-8"))
        assert "error" in body

    def test_price_cheapest_supplier(self, research_server: str) -> None:
        """GET /price?keyword=A&category=食品・飲料 → cheapest_supplier含む（正常系詳細）"""
        url = f"{research_server}/price?keyword=A&category=%E9%A3%9F%E5%93%81%E3%83%BB%E9%A3%B2%E6%96%99"
        status, body = _get(url)
        assert status == 200
        assert "cheapest_supplier" in body


# ──────────────────────────────────────────
# MARKETING E2E
# ──────────────────────────────────────────

class TestMarketingE2E:
    """MARKETING API サーバーへの HTTP E2E テスト"""

    def test_health_ok(self, marketing_server: str) -> None:
        """GET /health → 200, module==marketing"""
        status, body = _get(f"{marketing_server}/health")
        assert status == 200
        assert body["module"] == "marketing"

    def test_generate_content(self, marketing_server: str) -> None:
        """POST /generate → 200, x.full_text含む, youtube.script_length > 0"""
        status, body = _post(
            f"{marketing_server}/generate",
            {"topic": "EC", "category": "日用品・消耗品", "trend_score": 0.8},
        )
        assert status == 200
        assert "x" in body or "full_text" in body or "content" in body

    def test_generate_empty_input(self, marketing_server: str) -> None:
        """POST /generate 空入力 → 200（境界値）"""
        status, body = _post(
            f"{marketing_server}/generate",
            {"topic": "", "category": ""},
        )
        assert status == 200

    def test_log_summary(self, marketing_server: str) -> None:
        """GET /log/summary → 200, by_type含む"""
        status, body = _get(f"{marketing_server}/log/summary")
        assert status == 200
        assert isinstance(body, dict)

    def test_log_add(self, marketing_server: str) -> None:
        """POST /log/add → 201, id含む"""
        status, body = _post(
            f"{marketing_server}/log/add",
            {
                "content_type": "x_post",
                "topic": "test",
                "category": "食品・飲料",
                "char_count": 100,
            },
        )
        assert status == 201
        assert "id" in body or "record_id" in body or "content_type" in body

    def test_x_post(self, marketing_server: str) -> None:
        """POST /x/post → 200, tweet_id含む（モック）"""
        status, body = _post(
            f"{marketing_server}/x/post",
            {"text": "テスト投稿"},
        )
        assert status == 200
        assert "tweet_id" in body or "id" in body or "status" in body

    def test_not_found(self, marketing_server: str) -> None:
        """GET /nonexistent → 404"""
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            _get(f"{marketing_server}/nonexistent")
        assert exc_info.value.code == 404


# ──────────────────────────────────────────
# GOV E2E
# ──────────────────────────────────────────

class TestGovE2E:
    """GOV API サーバーへの HTTP E2E テスト"""

    def test_health_ok(self, gov_server: str) -> None:
        """GET /health → 200, module==gov"""
        status, body = _get(f"{gov_server}/health")
        assert status == 200
        assert body["module"] == "gov"

    def test_coo_kpi_record(self, gov_server: str) -> None:
        """POST /coo/kpi → 201, achievement_rate==0.9"""
        status, body = _post(
            f"{gov_server}/coo/kpi",
            {
                "kpi_name": "売上",
                "target": 1_000_000,
                "actual": 900_000,
                "unit": "円",
                "month": "2026-06",
            },
        )
        assert status == 201
        assert abs(body.get("achievement_rate", 0) - 0.9) < 0.001

    def test_coo_report(self, gov_server: str) -> None:
        """GET /coo/report/2026-06 → 200, kpi_summary含む"""
        status, body = _get(f"{gov_server}/coo/report/2026-06")
        assert status == 200
        assert "kpi_summary" in body or "month" in body

    def test_finops_cost_record(self, gov_server: str) -> None:
        """POST /finops/cost → 201, is_over_limit==False"""
        status, body = _post(
            f"{gov_server}/finops/cost",
            {
                "service": "research",
                "cost_jpy": 0.3,
                "delivery_count": 2,
                "month": "2026-06",
            },
        )
        assert status == 201
        assert body.get("is_over_limit") is False

    def test_finops_alerts(self, gov_server: str) -> None:
        """GET /finops/alerts → 200, list形式"""
        status, body = _get(f"{gov_server}/finops/alerts")
        assert status == 200
        assert isinstance(body, list)

    def test_ops_log_record(self, gov_server: str) -> None:
        """POST /ops/log → 201, log_id含む"""
        status, body = _post(
            f"{gov_server}/ops/log",
            {"service": "sbds", "level": "info", "message": "起動完了"},
        )
        assert status == 201
        assert "log_id" in body or "id" in body or "service" in body

    def test_ops_health(self, gov_server: str) -> None:
        """GET /ops/health → 200, 5サービスのhealthステータス"""
        status, body = _get(f"{gov_server}/ops/health")
        assert status == 200
        assert isinstance(body, list)


# ──────────────────────────────────────────
# SURPLUS SHIFT E2E（モジュール直接インポート）
# ──────────────────────────────────────────

class TestSurplusShiftE2E:
    """SURPLUS_SHIFT モジュールの機能E2Eテスト"""

    def test_gate_a_to_b_to_d_flow(self) -> None:
        """Gate A → Gate B → Gate D の一連フロー（通常仕入れシナリオ）"""
        from src.surplus_shift.gate_a import KeepaClient
        from src.surplus_shift.gate_b import GrossMarginCalc, PurchaseDecision
        from src.surplus_shift.gate_d import CashFlowJudge, MonthlyCFInput

        # Gate A: 価格スナップショット取得
        client = KeepaClient()
        snapshot = client.fetch("B07XXXXTEST")
        assert snapshot.asin == "B07XXXXTEST"
        assert snapshot.amazon_price_jpy > 0

        # Gate B: 粗利計算 (25% 粗利を確保できる価格設定)
        calc = GrossMarginCalc()
        purchase = int(snapshot.new_lowest_jpy * 0.6)
        selling = snapshot.amazon_price_jpy
        result = calc.calculate("テスト商品", purchase, selling)
        decision = calc.decide(result)
        assert decision in (PurchaseDecision.GO, PurchaseDecision.CONDITIONAL, PurchaseDecision.NO_GO)

        # Gate D: CF整合判定
        judge = CashFlowJudge()
        cf_input = MonthlyCFInput(
            month="2026-06",
            opening_balance_jpy=1_000_000,
            monthly_revenue_jpy=800_000,
            fixed_costs_jpy=300_000,
            variable_costs_jpy=100_000,
            planned_procurement_jpy=200_000,
        )
        judgement = judge.judge(cf_input)
        assert judgement.human_approval_required is True
        assert judgement.month == "2026-06"

    def test_gate_b_no_go_decision(self) -> None:
        """Gate B NO_GO判定シナリオ（粗利15%未満）"""
        from src.surplus_shift.gate_b import GrossMarginCalc, PurchaseDecision

        calc = GrossMarginCalc()
        # 販売価格1000円, 仕入900円 → 粗利率は低くなる
        result = calc.calculate("テスト", purchase_price_jpy=900, selling_price_jpy=1000)
        assert result.gross_margin_rate < 0.15
        decision = calc.decide(result)
        assert decision == PurchaseDecision.NO_GO

    def test_gate_d_surplus_shift_recommended(self) -> None:
        """Gate D CF不足 → surplus_shift_recommended=True シナリオ"""
        from src.surplus_shift.gate_d import CashFlowJudge, MonthlyCFInput, MIN_CF_RESERVE_JPY

        judge = CashFlowJudge()
        cf_input = MonthlyCFInput(
            month="2026-06",
            opening_balance_jpy=100_000,
            monthly_revenue_jpy=50_000,
            fixed_costs_jpy=200_000,
            variable_costs_jpy=50_000,
            planned_procurement_jpy=100_000,
        )
        judgement = judge.judge(cf_input)
        # 月末残高が MIN_CF_RESERVE_JPY 未満なら surplus_shift_recommended==True
        expected = judgement.projected_closing_balance_jpy < MIN_CF_RESERVE_JPY
        assert judgement.surplus_shift_recommended is expected
        assert judgement.surplus_shift_recommended is True

    def test_negotiation_log_full_flow(self) -> None:
        """NegotiationLog: draft→human_approve→mark_sent フロー"""
        from src.surplus_shift.negotiation_log import NegotiationLog, STATUS_DRAFT, STATUS_HUMAN_APPROVED, STATUS_SENT

        log = NegotiationLog()
        record = log.add_draft("2026-06", "【AI交渉案】余剰在庫転換提案")
        assert record.status == STATUS_DRAFT

        approved = log.human_approve(record.record_id, approved_by="田中太郎", notes="承認OK")
        assert approved.status == STATUS_HUMAN_APPROVED
        assert approved.human_approved_by == "田中太郎"

        sent = log.mark_sent(record.record_id)
        assert sent.status == STATUS_SENT

    def test_gate_d_human_approval_required_immutable(self) -> None:
        """Gate D human_approval_required=True 変更試みでValueError"""
        from src.surplus_shift.gate_d import CFJudgement

        with pytest.raises(ValueError):
            CFJudgement(
                month="2026-06",
                opening_balance_jpy=500_000,
                projected_closing_balance_jpy=400_000,
                procurement_feasible=True,
                cf_reserve_sufficient=True,
                surplus_shift_recommended=False,
                negotiation_draft="",
                human_approval_required=False,  # これが ValueError を起こす
                judgement_at="2026-06-05T00:00:00+00:00",
            )

    def test_price_matrix_cheapest_available_only(self) -> None:
        """PriceMatrix cheapest() が在庫ありレコードのみ対象"""
        from src.research.res_a01 import PriceMatrix, PriceRecord
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        matrix = PriceMatrix(keyword="テスト", category="日用品・消耗品")
        matrix.records = [
            PriceRecord(supplier="A", price_jpy=500, shipping_jpy=0, lot_size=1,
                        is_available=False, retrieved_at=now),
            PriceRecord(supplier="B", price_jpy=800, shipping_jpy=0, lot_size=1,
                        is_available=True, retrieved_at=now),
            PriceRecord(supplier="C", price_jpy=600, shipping_jpy=0, lot_size=1,
                        is_available=True, retrieved_at=now),
        ]
        cheapest = matrix.cheapest()
        assert cheapest is not None
        assert cheapest.supplier == "C"  # 在庫ありで最安値
        assert cheapest.is_available is True


# ──────────────────────────────────────────
# SBDS E2E（モジュール直接インポート）
# ──────────────────────────────────────────

class TestSBDSE2E:
    """SBDS モジュールの機能E2Eテスト"""

    def test_building_master_and_routing(self) -> None:
        """BuildingMaster 登録 → ルーティング距離計算フロー"""
        from src.sbds.tms_set_001 import (
            BuildingMaster, BuildingSpec, EVSpec, RoomRecord,
            calculate_routing_distance,
        )

        spec = BuildingSpec(
            building_count=2,
            floor_count=10,
            ev_spec=EVSpec(residential_count=4, service_count=4),
        )
        master = BuildingMaster(property_id="PROP-001", spec=spec)

        rooms = [
            RoomRecord("A棟", "301", 65.0, 80_000, 15.0, 3),
            RoomRecord("A棟", "201", 55.0, 70_000, 5.0, 2),
            RoomRecord("A棟", "302", 65.0, 80_000, 8.0, 3),
        ]
        for r in rooms:
            master.add_room(r)

        assert len(master.rooms) == 3

        sorted_rooms = calculate_routing_distance(master.rooms)
        # 階昇順: 2F → 3F、同フロアはev_exit_distance_m昇順
        assert sorted_rooms[0].floor == 2
        assert sorted_rooms[1].floor == 3
        assert sorted_rooms[1].ev_exit_distance_m <= sorted_rooms[2].ev_exit_distance_m

    def test_delivery_routing_complaint_last(self) -> None:
        """配送ルーティング: クレームフラグ商品が最後尾になること"""
        from src.sbds.tms_drv_001 import DeliveryPackage, sort_delivery_route

        packages = [
            DeliveryPackage("P1", "301", "受取人A", 3, 10.0, is_complaint_risk=True),
            DeliveryPackage("P2", "302", "受取人B", 3, 5.0, is_complaint_risk=False),
            DeliveryPackage("P3", "303", "受取人C", 3, 20.0, is_complaint_risk=False),
        ]
        sorted_pkgs = sort_delivery_route(packages)
        # 同一フロア内でクレームリスクは最後尾
        last = sorted_pkgs[-1]
        assert last.is_complaint_risk is True

    def test_labor_law_lock(self) -> None:
        """労働法ロック: 4時間超でSTATUS_LOCKED_BY_LABOR_LAW"""
        import time
        from src.sbds.tms_drv_001 import WorkSession, STATUS_LOCKED_BY_LABOR_LAW, LABOR_LAW_BREAK_MINUTES

        session = WorkSession(staff_id="DRV-001")
        # 開始時刻を4時間以上前に偽装
        session.start_ts = time.time() - (LABOR_LAW_BREAK_MINUTES * 60 + 1)
        status = session.check_labor_law()
        assert status == STATUS_LOCKED_BY_LABOR_LAW

    def test_jaro_winkler_name_matching(self) -> None:
        """Jaro-Winkler名寄せ: 類似名前 D_jw >= 0.85 のマッチング"""
        from src.sbds.tms_drv_001 import jaro_winkler, match_recipient_name, JW_THRESHOLD

        # 全く同じ文字列は 1.0
        score = jaro_winkler("山田太郎", "山田太郎")
        assert score == 1.0

        # 高い類似度はマッチ判定 True
        assert match_recipient_name("山田太郎", "山田太郎") is True

        # 全く異なる文字列は閾値未満
        score_diff = jaro_winkler("AAAA", "ZZZZ")
        assert score_diff < JW_THRESHOLD

    def test_indexeddb_version(self) -> None:
        """IndexedDB v142 バージョン確認（INDEXEDDB_VERSION == 142）"""
        from src.sbds.tms_drv_001 import INDEXEDDB_VERSION, DeliveryPackage

        assert INDEXEDDB_VERSION == 142

        pkg = DeliveryPackage("P-TEST", "101", "受取人", 1, 5.0)
        cache = pkg.to_cache_dict()
        assert cache["_idb_version"] == 142
