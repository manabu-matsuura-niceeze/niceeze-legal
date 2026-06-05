"""GOVモジュール テスト"""
from __future__ import annotations

import pytest
from src.gov.s10_coo_report import COOReportEngine, KPIRecord, BudgetRecord, PMOTask
from src.gov.finops_monitor import FinOpsMonitor, MAX_COST_PER_DELIVERY_JPY, MONTHLY_BUDGET_JPY
from src.gov.ops_log_collector import OpsLogCollector, VALID_SERVICES


# ──────────────────────────────────────────
# TestCOOReport
# ──────────────────────────────────────────

class TestCOOReport:
    def setup_method(self):
        self.engine = COOReportEngine()

    def test_add_kpi_returns_record(self):
        rec = self.engine.add_kpi('月次売上', 1_000_000, 900_000, '円', '2026-06')
        assert isinstance(rec, KPIRecord)
        assert rec.kpi_name == '月次売上'

    def test_kpi_achievement_rate(self):
        rec = self.engine.add_kpi('配送完了率', 100.0, 95.0, '%', '2026-06')
        assert abs(rec.achievement_rate - 0.95) < 1e-9

    def test_kpi_is_achieved_true(self):
        rec = self.engine.add_kpi('KPI', 100.0, 100.0, '件', '2026-06')
        assert rec.is_achieved is True

    def test_kpi_is_achieved_false(self):
        rec = self.engine.add_kpi('KPI', 100.0, 80.0, '件', '2026-06')
        assert rec.is_achieved is False

    def test_kpi_zero_target(self):
        rec = self.engine.add_kpi('KPI', 0.0, 0.0, '件', '2026-06')
        assert rec.achievement_rate == 0.0

    def test_add_budget_returns_record(self):
        rec = self.engine.add_budget('GCPコスト', 5000, 3000, '2026-06')
        assert isinstance(rec, BudgetRecord)
        assert rec.variance_jpy == 2000

    def test_budget_variance_negative_on_overspend(self):
        rec = self.engine.add_budget('費目', 3000, 4000, '2026-06')
        assert rec.variance_jpy == -1000

    def test_budget_execution_rate(self):
        rec = self.engine.add_budget('費目', 5000, 2500, '2026-06')
        assert abs(rec.execution_rate - 0.5) < 1e-9

    def test_add_pmo_task(self):
        task = self.engine.add_pmo_task('SBDS実装', 'G1', 'in_progress', 'SBDS部', '2026-09-30')
        assert isinstance(task, PMOTask)
        assert len(task.task_id) == 16

    def test_update_pmo_task_status(self):
        task = self.engine.add_pmo_task('タスク', 'G2', 'todo', 'GOV', '2026-11-30')
        updated = self.engine.update_pmo_task(task.task_id, 'done')
        assert updated.status == 'done'

    def test_update_pmo_task_invalid_id_raises(self):
        with pytest.raises(KeyError):
            self.engine.update_pmo_task('nonexistent', 'done')

    def test_generate_report_filters_by_month(self):
        self.engine.add_kpi('KPI1', 100, 80, '件', '2026-06')
        self.engine.add_kpi('KPI2', 100, 90, '件', '2026-07')
        report = self.engine.generate_report('2026-06')
        assert len(report.kpis) == 1

    def test_report_kpi_summary(self):
        self.engine.add_kpi('A', 100, 120, '件', '2026-06')
        self.engine.add_kpi('B', 100, 80, '件', '2026-06')
        report = self.engine.generate_report('2026-06')
        summary = report.kpi_summary()
        assert summary['achieved_count'] == 1
        assert summary['total_count'] == 2

    def test_report_to_dict_keys(self):
        report = self.engine.generate_report('2026-06')
        d = report.to_dict()
        assert 'kpi_summary' in d and 'budget_summary' in d and 'pmo_summary' in d


# ──────────────────────────────────────────
# TestFinOpsMonitor
# ──────────────────────────────────────────

class TestFinOpsMonitor:
    def setup_method(self):
        self.monitor = FinOpsMonitor()

    def test_record_cost_returns_record(self):
        rec = self.monitor.record_cost('research', 1.0, 5, '2026-06')
        assert rec.service == 'research'
        assert rec.delivery_count == 5

    def test_cost_per_delivery_calculation(self):
        rec = self.monitor.record_cost('sbds', 3.0, 10, '2026-06')
        assert abs(rec.cost_per_delivery - 0.3) < 1e-9

    def test_is_over_limit_true(self):
        rec = self.monitor.record_cost('marketing', 5.0, 2, '2026-06')
        assert rec.is_over_limit is True

    def test_is_over_limit_false(self):
        rec = self.monitor.record_cost('marketing', 0.5, 2, '2026-06')
        assert rec.is_over_limit is False

    def test_alert_cost_per_delivery_exceeded(self):
        self.monitor.record_cost('sbds', 10.0, 1, '2026-06')
        alerts = self.monitor.check_alerts()
        types = [a.alert_type for a in alerts]
        assert 'cost_per_delivery_exceeded' in types

    def test_no_alert_when_under_limit(self):
        self.monitor.record_cost('research', 0.3, 2, '2026-06')
        alerts = [a for a in self.monitor.check_alerts() if a.alert_type == 'cost_per_delivery_exceeded']
        assert len(alerts) == 0

    def test_monthly_budget_warning_at_80pct(self):
        self.monitor.record_cost('gov', 4100.0, 1, '2026-06')
        alerts = self.monitor.check_alerts()
        types = [a.alert_type for a in alerts]
        assert 'monthly_budget_warning' in types or 'monthly_budget_exceeded' in types

    def test_monthly_budget_exceeded(self):
        self.monitor.record_cost('marketing', 5001.0, 1, '2026-06')
        alerts = self.monitor.check_alerts()
        types = [a.alert_type for a in alerts]
        assert 'monthly_budget_exceeded' in types

    def test_monthly_summary_keys(self):
        self.monitor.record_cost('research', 100.0, 200, '2026-06')
        summary = self.monitor.monthly_summary('2026-06')
        assert 'total_cost_jpy' in summary and 'budget_remaining_jpy' in summary

    def test_to_dict_structure(self):
        self.monitor.record_cost('sbds', 1.0, 2, '2026-06')
        d = self.monitor.to_dict()
        assert 'records' in d and 'total_records' in d


# ──────────────────────────────────────────
# TestOpsLogCollector
# ──────────────────────────────────────────

class TestOpsLogCollector:
    def setup_method(self):
        self.collector = OpsLogCollector()

    def test_record_info(self):
        entry = self.collector.record('sbds', 'info', 'テスト起動')
        assert entry.level == 'info'
        assert entry.service == 'sbds'

    def test_record_error(self):
        entry = self.collector.record('research', 'error', 'API失敗')
        assert entry.level == 'error'

    def test_record_with_metadata(self):
        entry = self.collector.record('marketing', 'info', 'X投稿完了', {'tweet_id': 'abc123'})
        assert entry.metadata == {'tweet_id': 'abc123'}

    def test_invalid_service_raises(self):
        with pytest.raises(ValueError):
            self.collector.record('invalid_svc', 'info', 'msg')

    def test_invalid_level_raises(self):
        with pytest.raises(ValueError):
            self.collector.record('sbds', 'debug', 'msg')

    def test_get_by_service(self):
        self.collector.record('sbds', 'info', 'a')
        self.collector.record('research', 'info', 'b')
        results = self.collector.get_by_service('sbds')
        assert len(results) == 1
        assert results[0].service == 'sbds'

    def test_get_errors(self):
        self.collector.record('gov', 'info', 'ok')
        self.collector.record('gov', 'error', 'fail')
        errors = self.collector.get_errors()
        assert len(errors) == 1

    def test_health_status_all_services(self):
        statuses = self.collector.health_status()
        services = [s.service for s in statuses]
        for svc in VALID_SERVICES:
            assert svc in services

    def test_health_status_is_healthy_false_on_error(self):
        self.collector.record('sbds', 'error', 'crash')
        statuses = {s.service: s for s in self.collector.health_status()}
        assert statuses['sbds'].is_healthy is False

    def test_health_status_is_healthy_true_no_errors(self):
        self.collector.record('research', 'info', 'ok')
        statuses = {s.service: s for s in self.collector.health_status()}
        assert statuses['research'].is_healthy is True

    def test_summary_keys(self):
        self.collector.record('gov', 'warning', 'slow')
        summary = self.collector.summary()
        assert 'total_logs' in summary and 'by_level' in summary and 'by_service' in summary
