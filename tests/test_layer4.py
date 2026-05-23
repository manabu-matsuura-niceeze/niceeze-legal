"""
NiceEze Layer4 テスト Ver 3.1
松浦CEO承認内容を全てテストで確証する。

テスト構成:
  TestOCRPrecisionGuard      : 精度制御 (8件)
  TestOCRRecalibrationEngine : 再キャリブレーション (5件)
  TestDataflowMigrationAssessor: 移行トリガー3条件 (7件)
  TestBigQueryArchivePipeline: アーカイブパイプライン (4件)
  計: 24件
"""

import os, sys, pytest
from pathlib import Path

os.environ["NICEEZE_AUDIT_RUNNING"] = "1"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.layer4.bigquery_pipeline import (
    OCRPrecisionGuard, OCRRecalibrationEngine,
    DataflowMigrationAssessor, BigQueryArchivePipeline,
    OCRResult, OCRModel, OCRDecision, DataflowTrigger,
    OCR_PRECISION_THRESHOLD_HAIKU, OCR_HAIKU_INITIAL_SUCCESS_RATE,
    DATAFLOW_TRIGGER_MONTHLY_ROWS, DATAFLOW_TRIGGER_BATCH_COST_USD,
    OCR_RECALIBRATION_MIN_SAMPLES, XCLAIM_TIMEOUT_CONSISTENCY_MS,
    BQ_DATASET_ID, BQ_TABLE_ID,
)


# ─────────────────────────────────────────────
# OCRPrecisionGuard テスト (8件)
# ─────────────────────────────────────────────
class TestOCRPrecisionGuard:
    def setup_method(self):
        self.guard = OCRPrecisionGuard()

    def test_threshold_is_95_percent(self):
        """閾値が松浦CEO決定の95%であること"""
        assert OCR_PRECISION_THRESHOLD_HAIKU == 0.95

    def test_haiku_above_threshold_accepted(self):
        """Haikuが95%以上の場合ACCEPTされること"""
        result = OCRResult(model=OCRModel.HAIKU, raw_text="", anonymized_text="",
                           confidence=0.96, cost_yen=0.05)
        d = self.guard.evaluate(result)
        assert d.decision == OCRDecision.ACCEPT

    def test_haiku_below_threshold_escalates(self):
        """Haikuが95%未満の場合Sonnetにエスカレーションされること"""
        result = OCRResult(model=OCRModel.HAIKU, raw_text="", anonymized_text="",
                           confidence=0.88, cost_yen=0.05)
        d = self.guard.evaluate(result)
        assert d.decision == OCRDecision.ESCALATE
        assert d.escalated is True

    def test_sonnet_below_threshold_human_review(self):
        """Sonnetも95%未満の場合人間レビューへ"""
        result = OCRResult(model=OCRModel.SONNET, raw_text="", anonymized_text="",
                           confidence=0.93, cost_yen=0.20)
        d = self.guard.evaluate(result)
        assert d.decision == OCRDecision.HUMAN_REVIEW

    def test_exact_threshold_accepted(self):
        """境界値: 95.0%ちょうどはACCEPTされること"""
        result = OCRResult(model=OCRModel.HAIKU, raw_text="", anonymized_text="",
                           confidence=0.95, cost_yen=0.05)
        d = self.guard.evaluate(result)
        assert d.decision == OCRDecision.ACCEPT

    def test_monthly_cost_within_5yen_wall(self):
        """月間コストが5円の壁を超えないこと"""
        cost = self.guard.estimate_monthly_cost(monthly_packages=120_000)
        assert cost["within_5yen_wall"] is True
        assert cost["cost_per_pkg_yen"] < 5.0

    def test_initial_haiku_success_rate(self):
        """初期Haiku成功率が85%（松浦CEO承認値）であること"""
        assert OCR_HAIKU_INITIAL_SUCCESS_RATE == 0.85

    def test_human_review_cost_added(self):
        """人間レビュー時に¥50が加算されること"""
        result = OCRResult(model=OCRModel.SONNET, raw_text="", anonymized_text="",
                           confidence=0.90, cost_yen=0.20)
        d = self.guard.evaluate(result)
        assert d.cost_yen == 0.20 + 50.0


# ─────────────────────────────────────────────
# OCRRecalibrationEngine テスト (5件)
# ─────────────────────────────────────────────
class TestOCRRecalibrationEngine:
    def setup_method(self):
        self.guard   = OCRPrecisionGuard()
        self.recalib = OCRRecalibrationEngine(self.guard)

    def test_insufficient_samples_deferred(self):
        """サンプル不足時は再キャリブレーションを延期すること"""
        r = self.recalib.recalibrate(actual_success_count=800, total_sample_count=999)
        assert r.delta == 0.0
        assert "不足" in r.recommendation

    def test_success_rate_updated_after_calibration(self):
        """1000件以上で成功率が実測値に更新されること"""
        r = self.recalib.recalibrate(actual_success_count=900, total_sample_count=1_000)
        assert r.new_success_rate == pytest.approx(0.90)
        assert self.guard._haiku_success_rate == pytest.approx(0.90)

    def test_positive_delta_recommends_update(self):
        """成功率向上（±5%超）は更新推奨が出ること"""
        r = self.recalib.recalibrate(actual_success_count=950, total_sample_count=1_000)
        assert r.delta > 0
        assert "更新を推奨" in r.recommendation

    def test_negative_delta_escalation_warning(self):
        """成功率低下（±5%超）は警告が出ること"""
        r = self.recalib.recalibrate(actual_success_count=750, total_sample_count=1_000)
        assert r.delta < 0
        assert "松浦CEO" in r.recommendation

    def test_small_delta_maintain_current(self):
        """変化軽微（±5%未満）は現行設定維持を推奨"""
        r = self.recalib.recalibrate(actual_success_count=870, total_sample_count=1_000)
        assert abs(r.delta) < 0.05
        assert "維持" in r.recommendation


# ─────────────────────────────────────────────
# DataflowMigrationAssessor テスト (7件)
# ─────────────────────────────────────────────
class TestDataflowMigrationAssessor:
    def setup_method(self):
        self.assessor = DataflowMigrationAssessor()

    def test_trigger_values_are_ceo_approved(self):
        """トリガー値が松浦CEO承認値であること"""
        assert DATAFLOW_TRIGGER_MONTHLY_ROWS   == 100_000
        assert DATAFLOW_TRIGGER_BATCH_COST_USD == 200.0

    def test_monthly_rows_trigger_fires_at_100k(self):
        """月間10万件到達でトリガーが発火すること"""
        a = self.assessor.assess(monthly_rows=100_000, batch_cost_usd=10.0)
        assert a.triggered is True
        assert a.trigger_reason == DataflowTrigger.MONTHLY_ROWS

    def test_monthly_rows_trigger_not_below_100k(self):
        """10万件未満ではトリガーが発火しないこと"""
        a = self.assessor.assess(monthly_rows=99_999, batch_cost_usd=10.0)
        assert a.triggered is False

    def test_batch_cost_trigger_fires_at_200usd(self):
        """月200ドル超過でトリガーが発火すること"""
        a = self.assessor.assess(monthly_rows=50_000, batch_cost_usd=200.0)
        assert a.triggered is True
        assert a.trigger_reason == DataflowTrigger.BATCH_COST

    def test_realtime_request_trigger_fires(self):
        """リアルタイム分析要求でトリガーが発火すること"""
        a = self.assessor.assess(monthly_rows=50_000, batch_cost_usd=10.0,
                                 realtime_requested=True)
        assert a.triggered is True
        assert a.trigger_reason == DataflowTrigger.REALTIME_REQUEST

    def test_priority_rows_over_cost(self):
        """行数・コスト同時発火時は行数が優先されること"""
        a = self.assessor.assess(monthly_rows=100_000, batch_cost_usd=200.0)
        assert a.trigger_reason == DataflowTrigger.MONTHLY_ROWS

    def test_current_scale_30k_households_triggers(self):
        """
        【重要な発見】
        現在の目標スケール（3万世帯=12万件/月）は
        すでにDataflowトリガー条件1（10万件）を超えている。
        松浦CEOへのアラート対象であることをテストで確証する。
        """
        current_monthly = 30_000 * 4  # 3万世帯 × 4荷物
        assert current_monthly == 120_000
        assert current_monthly >= DATAFLOW_TRIGGER_MONTHLY_ROWS
        a = self.assessor.assess(monthly_rows=current_monthly, batch_cost_usd=3.0)
        assert a.triggered is True
        assert a.trigger_reason == DataflowTrigger.MONTHLY_ROWS


# ─────────────────────────────────────────────
# BigQueryArchivePipeline テスト (4件)
# ─────────────────────────────────────────────
class TestBigQueryArchivePipeline:
    def setup_method(self):
        self.pipeline = BigQueryArchivePipeline()

    def test_build_query_valid_format(self):
        """正常なYYYY-MMでクエリが生成されること"""
        q = self.pipeline.build_bq_load_query("2026-02")
        assert "@archive_month" in q
        assert "packages_archive_candidates" in q
        # PII列はコメントで「除外」と明記されており、SELECT列には含まれないこと
        assert "-- ZONE2 PII列は除外" in q
        assert "address_encrypted" in q   # コメントとして除外理由が明記されている
        # SELECT句に address_encrypted が実際の列として存在しないこと
        lines = q.splitlines()
        select_lines = [l for l in lines if not l.strip().startswith("--")]
        assert not any("address_encrypted" in l for l in select_lines)

    def test_build_query_invalid_format_raises(self):
        """不正なフォーマットはValueErrorを発生させること"""
        with pytest.raises(ValueError):
            self.pipeline.build_bq_load_query("2026/02")
        with pytest.raises(ValueError):
            self.pipeline.build_bq_load_query("'; DROP TABLE packages;--")

    def test_simulate_archive_run_success(self):
        """シミュレーション実行が成功ステータスを返すこと"""
        job = self.pipeline.simulate_archive_run("2026-02")
        assert job.status == "success"
        assert job.rows_archived == 120_000
        assert BQ_DATASET_ID in job.bq_table

    def test_xclaim_timeout_consistency(self):
        """
        Layer3のXCLAIM Timeout（30秒）とLayer4の定数が一致すること。
        コールドスタート（最大10秒）+ 安全マージン20秒 = 30秒（松浦CEO承認）。
        """
        assert XCLAIM_TIMEOUT_CONSISTENCY_MS == 30_000
        # layer3の定数と整合確認
        from src.layer3.line_webhook import PENDING_TIMEOUT_MS
        assert PENDING_TIMEOUT_MS == XCLAIM_TIMEOUT_CONSISTENCY_MS
