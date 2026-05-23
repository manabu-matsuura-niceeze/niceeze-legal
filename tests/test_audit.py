"""
NiceEze 多層監査エンジン ユニットテスト Ver 2.2
再帰防止フラグ NICEEZE_AUDIT_RUNNING=1 を全テストで設定し、
pytest が subprocess で二重起動されないことを保証する。

実行: pytest tests/test_audit.py -v --tb=short
"""

import os
import sys
import pytest
from pathlib import Path

# ── 再帰防止フラグ（最優先で設定） ────────────────────────────────────────
os.environ["NICEEZE_AUDIT_RUNNING"] = "1"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.audit.multi_layer_audit import (
    MultiLayerAuditOrchestrator,
    Layer1SystemGuard,
    Layer2MetaCognitiveGuard,
    Layer3ReportSyncer,
    AuditReport,
    AuditStatus,
    HallucinationCheck,
    FINOPS_COST_CEILING,
    TARGET_HOUSEHOLDS,
)
from src.finops.cost_calculator import (
    FinOpsCostEstimate,
    simulate_scale_costs,
    PACKAGES_PER_HOUSEHOLD,
)
from src.gdrive.gdrive_syncer import MockGoogleDriveSyncer


# ─────────────────────────────────────────────
# フィクスチャ
# ─────────────────────────────────────────────
@pytest.fixture
def mock_syncer(tmp_path, monkeypatch):
    monkeypatch.setattr(MockGoogleDriveSyncer, "MOCK_DIR", tmp_path / "gdrive_mock")
    return MockGoogleDriveSyncer()

@pytest.fixture
def cost_estimate():
    return FinOpsCostEstimate()

@pytest.fixture
def full_spec_checklist():
    return [
        "個人情報の暗号化（AES-256）",
        "Row Level Security（RLS）の実装",
        "DBテーブル定義の完全性",
        "APIレート制限の実装",
        "FinOps予算枠（Inputs_Master.csv）との整合",
        "指数関数的スケール対応（パーティショニング）",
    ]

@pytest.fixture(autouse=True)
def ensure_audit_flag():
    """全テストで再帰防止フラグを確実に保持"""
    os.environ["NICEEZE_AUDIT_RUNNING"] = "1"
    yield
    os.environ["NICEEZE_AUDIT_RUNNING"] = "1"


# ─────────────────────────────────────────────
# FinOps テスト (9件)
# ─────────────────────────────────────────────
class TestFinOps:
    def test_5yen_wall_cleared(self, cost_estimate):
        assert cost_estimate.finops_cleared, \
            f"5円の壁超過: {cost_estimate.cost_per_package_jpy}円"

    def test_cost_per_package_positive(self, cost_estimate):
        assert cost_estimate.cost_per_package_jpy > 0

    def test_monthly_packages_correct(self, cost_estimate):
        assert cost_estimate.monthly_packages == TARGET_HOUSEHOLDS * PACKAGES_PER_HOUSEHOLD

    def test_scale_simulation_returns_all_points(self, cost_estimate):
        points  = [1_000, 5_000, 10_000, 30_000, 100_000]
        results = simulate_scale_costs(cost_estimate, points)
        assert len(results) == len(points)

    def test_total_monthly_cost_increases_with_scale(self, cost_estimate):
        results = simulate_scale_costs(cost_estimate, [10_000, 30_000, 100_000])
        assert results[0]["total_monthly_jpy"] < results[1]["total_monthly_jpy"] < results[2]["total_monthly_jpy"]

    def test_cost_per_package_decreases_with_scale(self, cost_estimate):
        results = simulate_scale_costs(cost_estimate, [10_000, 100_000])
        assert results[0]["cost_per_pkg_jpy"] > results[1]["cost_per_pkg_jpy"]

    def test_to_dict_has_required_keys(self, cost_estimate):
        d = cost_estimate.to_dict()
        for key in ["db_cost_monthly_yen", "api_cost_monthly_yen",
                    "storage_cost_monthly_yen", "monthly_packages"]:
            assert key in d

    def test_report_text_includes_wall_status(self, cost_estimate):
        text = cost_estimate.report_text()
        assert "5円の壁" in text and "クリア" in text

    def test_zero_packages_does_not_crash(self):
        est = FinOpsCostEstimate(monthly_packages=0)
        assert est.cost_per_package_jpy == float("inf")
        assert not est.finops_cleared


# ─────────────────────────────────────────────
# Layer1 テスト (4件) — subprocess 再帰なし
# ─────────────────────────────────────────────
class TestLayer1SystemGuard:
    def test_already_running_flag_skips_subprocess(self):
        """NICEEZE_AUDIT_RUNNING=1 のとき pytest subprocess を起動しないこと"""
        from src.audit.multi_layer_audit import Layer1Result
        guard  = Layer1SystemGuard()
        result = Layer1Result()
        result = guard._run_pytest(ROOT, result, already_running=True)
        # subprocess を起動しないため '省略' または '再帰防止' メッセージが含まれる
        assert any("省略" in d or "再帰防止" in d for d in result.details), \
            f"再帰防止メッセージが見当たりません: {result.details}"

    def test_bandit_runs_and_returns_result(self):
        """bandit が実行されて結果が返ること"""
        guard  = Layer1SystemGuard()
        from src.audit.multi_layer_audit import Layer1Result
        result = guard._run_bandit(ROOT, Layer1Result())
        assert len(result.details) > 0

    def test_pip_audit_runs_and_returns_result(self):
        """pip-audit が実行されて結果が返ること"""
        guard  = Layer1SystemGuard()
        from src.audit.multi_layer_audit import Layer1Result
        result = guard._run_pip_audit(ROOT, Layer1Result())
        assert len(result.details) > 0

    def test_no_vulnerabilities_found(self):
        """既知の脆弱性がゼロであること"""
        guard  = Layer1SystemGuard()
        from src.audit.multi_layer_audit import Layer1Result
        r = Layer1Result()
        r = guard._run_bandit(ROOT, r)
        r = guard._run_pip_audit(ROOT, r)
        assert r.vulnerability_count == 0, \
            f"脆弱性検出: {r.vulnerability_count} 件\n詳細: {r.details}"


# ─────────────────────────────────────────────
# Layer2 テスト (5件)
# ─────────────────────────────────────────────
class TestLayer2MetaCognitiveGuard:
    def setup_method(self):
        self.guard = Layer2MetaCognitiveGuard()

    def test_full_checklist_no_violations(self, full_spec_checklist):
        from src.audit.multi_layer_audit import Layer2Result
        r = Layer2Result()
        r = self.guard._check_spec_compliance(r, full_spec_checklist)
        assert len(r.spec_violations) == 0

    def test_missing_spec_creates_violation(self):
        from src.audit.multi_layer_audit import Layer2Result
        r = Layer2Result()
        r = self.guard._check_spec_compliance(r, [])
        assert len(r.spec_violations) > 0

    def test_finops_pass_within_ceiling(self):
        from src.audit.multi_layer_audit import Layer2Result
        r = Layer2Result()
        cost = {"db_cost_monthly_yen": 11250, "api_cost_monthly_yen": 18000,
                "storage_cost_monthly_yen": 750, "monthly_packages": 120000}
        r = self.guard._check_finops_cost(r, cost)
        assert r.finops_cleared
        assert r.cost_audit_status == AuditStatus.PASS

    def test_finops_fail_above_ceiling(self):
        from src.audit.multi_layer_audit import Layer2Result
        r = Layer2Result()
        cost = {"db_cost_monthly_yen": 9_999_999, "api_cost_monthly_yen": 0,
                "storage_cost_monthly_yen": 0, "monthly_packages": 1}
        r = self.guard._check_finops_cost(r, cost)
        assert not r.finops_cleared
        assert r.cost_audit_status == AuditStatus.FAIL

    def test_hallucination_check_finds_rls_in_sql(self):
        """SQLマイグレーションファイルからRLSエビデンスを検出できること"""
        from src.audit.multi_layer_audit import Layer2Result
        r = Layer2Result()
        r = self.guard._check_hallucinations(r)
        # 001_initial_schema.sql に ENABLE ROW LEVEL SECURITY が存在する
        assert r.hallucination.rls_found, \
            "RLSが検出されませんでした。001_initial_schema.sql を確認してください"
        assert r.hallucination.rls_evidence_line > 0
        assert "ENABLE ROW LEVEL SECURITY" in r.hallucination.rls_evidence_text.upper() \
            or "ROW LEVEL SECURITY" in r.hallucination.rls_evidence_text.upper()


# ─────────────────────────────────────────────
# Layer3 テスト (4件)
# ─────────────────────────────────────────────
class TestLayer3ReportSyncer:
    def test_local_file_created(self, tmp_path, mock_syncer, monkeypatch):
        import src.audit.multi_layer_audit as m
        monkeypatch.setattr(m, "LOCAL_AUDIT_DIR", tmp_path / "audit")
        syncer = Layer3ReportSyncer(gdrive_syncer=mock_syncer)
        report = AuditReport(task_name="テスト", implementation_summary="概要")
        syncer.run(report)
        files = list((tmp_path / "audit").glob("AUDIT_*.md"))
        assert len(files) == 1

    def test_report_contains_required_sections(self, tmp_path, mock_syncer, monkeypatch):
        import src.audit.multi_layer_audit as m
        monkeypatch.setattr(m, "LOCAL_AUDIT_DIR", tmp_path / "audit")
        syncer = Layer3ReportSyncer(gdrive_syncer=mock_syncer)
        report = AuditReport(task_name="DBスキーマ実装", implementation_summary="RLS + AES-256")
        syncer.run(report)
        content = list((tmp_path / "audit").glob("AUDIT_*.md"))[0].read_text()
        for section in ["実施タスク", "実装の概要", "多層監査の証跡", "FinOps", "Gemini", "5円の壁",
                        "差し戻し対応完了チェックリスト", "Ver 2.2"]:
            assert section in content, f"必須セクション '{section}' がレポートに存在しません"

    def test_gdrive_mock_returns_docs_url(self, tmp_path, mock_syncer, monkeypatch):
        """MockSyncer が docs.google.com URL を返すこと"""
        import src.audit.multi_layer_audit as m
        monkeypatch.setattr(m, "LOCAL_AUDIT_DIR", tmp_path / "audit")
        syncer = Layer3ReportSyncer(gdrive_syncer=mock_syncer)
        report = AuditReport(task_name="テスト", implementation_summary="概要")
        report = syncer.run(report)
        assert "docs.google.com" in report.gdrive_doc_url, \
            f"Google Docs URL が返されていません: {report.gdrive_doc_url}"

    def test_gdrive_url_stored_in_report(self, tmp_path, mock_syncer, monkeypatch):
        """レポートオブジェクトに gdrive_doc_url が保存されること"""
        import src.audit.multi_layer_audit as m
        monkeypatch.setattr(m, "LOCAL_AUDIT_DIR", tmp_path / "audit")
        syncer = Layer3ReportSyncer(gdrive_syncer=mock_syncer)
        report = AuditReport(task_name="テスト", implementation_summary="概要")
        report = syncer.run(report)
        assert report.gdrive_doc_url != ""
        assert "ERROR" not in report.gdrive_doc_url


# ─────────────────────────────────────────────
# オーケストレーター統合テスト (2件)
# ─────────────────────────────────────────────
class TestMultiLayerAuditOrchestrator:
    def test_orchestrator_completes_all_layers(
        self, tmp_path, mock_syncer, monkeypatch, full_spec_checklist, cost_estimate
    ):
        import src.audit.multi_layer_audit as m
        monkeypatch.setattr(m, "LOCAL_AUDIT_DIR", tmp_path / "audit")
        orch   = MultiLayerAuditOrchestrator(gdrive_syncer=mock_syncer)
        report = orch.run(
            task_name="統合テスト Ver 2.2",
            implementation_summary="全差し戻し項目対応完了",
            cost_estimate=cost_estimate.to_dict(),
            spec_checklist=full_spec_checklist,
            project_root=str(ROOT),
        )
        assert report.overall_status in [AuditStatus.PASS, AuditStatus.WARN, AuditStatus.FAIL]
        assert report.gdrive_doc_url != ""
        assert "docs.google.com" in report.gdrive_doc_url

    def test_overall_fail_when_cost_explodes(
        self, tmp_path, mock_syncer, monkeypatch, full_spec_checklist
    ):
        import src.audit.multi_layer_audit as m
        monkeypatch.setattr(m, "LOCAL_AUDIT_DIR", tmp_path / "audit")
        orch   = MultiLayerAuditOrchestrator(gdrive_syncer=mock_syncer)
        report = orch.run(
            task_name="コスト超過テスト",
            implementation_summary="テスト",
            cost_estimate={"db_cost_monthly_yen": 99_999_999,
                           "api_cost_monthly_yen": 99_999_999,
                           "storage_cost_monthly_yen": 99_999_999,
                           "monthly_packages": 1},
            spec_checklist=full_spec_checklist,
            project_root=str(ROOT),
        )
        assert report.layer2.status == AuditStatus.FAIL
        assert report.overall_status == AuditStatus.FAIL


# ─────────────────────────────────────────────
# MockGoogleDriveSyncer テスト (2件)
# ─────────────────────────────────────────────
class TestMockGoogleDriveSyncer:
    def test_upload_creates_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(MockGoogleDriveSyncer, "MOCK_DIR", tmp_path)
        syncer = MockGoogleDriveSyncer()
        url = syncer.upload_as_google_doc(
            content="# テスト\n本文", filename="AUDIT_TEST_001"
        )
        assert "docs.google.com" in url

    def test_mock_file_content_matches_input(self, tmp_path, monkeypatch):
        monkeypatch.setattr(MockGoogleDriveSyncer, "MOCK_DIR", tmp_path)
        syncer   = MockGoogleDriveSyncer()
        content  = "# NiceEze監査レポート\n## FinOps: 0.29円/荷物"
        syncer.upload_as_google_doc(content=content, filename="AUDIT_CONTENT_TEST")
        saved_files = list(tmp_path.rglob("*.md"))
        assert len(saved_files) == 1
        assert saved_files[0].read_text(encoding="utf-8") == content
