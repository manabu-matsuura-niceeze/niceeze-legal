"""S10 COO業務報告（KPI・予実・PMO）(Ver 1.0)
GOV部門 MVP
FinOps: 月額¥5,000以内 / PII不使用 / bandit 0件
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class KPIRecord:
    """KPI記録"""
    kpi_name: str
    target: float
    actual: float
    unit: str
    month: str  # 'YYYY-MM'

    @property
    def achievement_rate(self) -> float:
        """達成率 (actual / target)"""
        if self.target == 0:
            return 0.0
        return self.actual / self.target

    @property
    def is_achieved(self) -> bool:
        """達成判定（達成率 >= 1.0）"""
        return self.achievement_rate >= 1.0

    def to_dict(self) -> dict:
        return {
            "kpi_name": self.kpi_name,
            "target": self.target,
            "actual": self.actual,
            "unit": self.unit,
            "month": self.month,
            "achievement_rate": self.achievement_rate,
            "is_achieved": self.is_achieved,
        }


@dataclass
class BudgetRecord:
    """予実記録"""
    item_name: str
    budget_jpy: int
    actual_jpy: int
    month: str  # 'YYYY-MM'

    @property
    def variance_jpy(self) -> int:
        """差異（budget - actual）。正=予算内、負=超過"""
        return self.budget_jpy - self.actual_jpy

    @property
    def execution_rate(self) -> float:
        """執行率 (actual / budget)"""
        if self.budget_jpy == 0:
            return 0.0
        return self.actual_jpy / self.budget_jpy

    def to_dict(self) -> dict:
        return {
            "item_name": self.item_name,
            "budget_jpy": self.budget_jpy,
            "actual_jpy": self.actual_jpy,
            "month": self.month,
            "variance_jpy": self.variance_jpy,
            "execution_rate": self.execution_rate,
        }


VALID_GATES = {"G0", "G1", "G2", "G3", "G4"}
VALID_STATUSES = {"todo", "in_progress", "done", "blocked"}


@dataclass
class PMOTask:
    """PMOタスク"""
    task_id: str           # SHA-256[:16]
    task_name: str
    gate: str              # 'G0' | 'G1' | 'G2' | 'G3' | 'G4'
    status: str            # 'todo' | 'in_progress' | 'done' | 'blocked'
    owner: str
    due_date: str          # 'YYYY-MM-DD'
    created_at: str
    updated_at: str

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "gate": self.gate,
            "status": self.status,
            "owner": self.owner,
            "due_date": self.due_date,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class COOReport:
    """COO月次レポート"""
    report_month: str           # 'YYYY-MM'
    kpis: list[KPIRecord]
    budgets: list[BudgetRecord]
    pmo_tasks: list[PMOTask]
    generated_at: str

    def kpi_summary(self) -> dict:
        """KPI達成率サマリー"""
        total = len(self.kpis)
        achieved = sum(1 for k in self.kpis if k.is_achieved)
        avg_rate = (
            sum(k.achievement_rate for k in self.kpis) / total
            if total > 0 else 0.0
        )
        return {
            "achieved_count": achieved,
            "total_count": total,
            "achievement_rate_avg": avg_rate,
        }

    def budget_summary(self) -> dict:
        """予実サマリー（合計予算・合計実績・差異）"""
        total_budget = sum(b.budget_jpy for b in self.budgets)
        total_actual = sum(b.actual_jpy for b in self.budgets)
        return {
            "total_budget_jpy": total_budget,
            "total_actual_jpy": total_actual,
            "total_variance_jpy": total_budget - total_actual,
        }

    def pmo_summary(self) -> dict:
        """PMOタスクサマリー（gate別・status別件数）"""
        gate_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        for t in self.pmo_tasks:
            gate_counts[t.gate] = gate_counts.get(t.gate, 0) + 1
            status_counts[t.status] = status_counts.get(t.status, 0) + 1
        return {
            "total_tasks": len(self.pmo_tasks),
            "by_gate": gate_counts,
            "by_status": status_counts,
        }

    def to_dict(self) -> dict:
        return {
            "report_month": self.report_month,
            "kpis": [k.to_dict() for k in self.kpis],
            "budgets": [b.to_dict() for b in self.budgets],
            "pmo_tasks": [t.to_dict() for t in self.pmo_tasks],
            "generated_at": self.generated_at,
            "kpi_summary": self.kpi_summary(),
            "budget_summary": self.budget_summary(),
            "pmo_summary": self.pmo_summary(),
        }


class COOReportEngine:
    """COO業務報告エンジン"""

    def __init__(self) -> None:
        self._kpis: list[KPIRecord] = []
        self._budgets: list[BudgetRecord] = []
        self._pmo_tasks: dict[str, PMOTask] = {}

    def add_kpi(
        self,
        kpi_name: str,
        target: float,
        actual: float,
        unit: str,
        month: str,
    ) -> KPIRecord:
        record = KPIRecord(
            kpi_name=kpi_name,
            target=target,
            actual=actual,
            unit=unit,
            month=month,
        )
        self._kpis.append(record)
        return record

    def add_budget(
        self,
        item_name: str,
        budget_jpy: int,
        actual_jpy: int,
        month: str,
    ) -> BudgetRecord:
        record = BudgetRecord(
            item_name=item_name,
            budget_jpy=budget_jpy,
            actual_jpy=actual_jpy,
            month=month,
        )
        self._budgets.append(record)
        return record

    def add_pmo_task(
        self,
        task_name: str,
        gate: str,
        status: str,
        owner: str,
        due_date: str,
    ) -> PMOTask:
        if gate not in VALID_GATES:
            raise ValueError(f"Invalid gate: {gate}. Must be one of {VALID_GATES}")
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}. Must be one of {VALID_STATUSES}")
        task_id = hashlib.sha256(f"{task_name}:{due_date}".encode()).hexdigest()[:16]
        now = _now_iso()
        task = PMOTask(
            task_id=task_id,
            task_name=task_name,
            gate=gate,
            status=status,
            owner=owner,
            due_date=due_date,
            created_at=now,
            updated_at=now,
        )
        self._pmo_tasks[task_id] = task
        return task

    def update_pmo_task(self, task_id: str, status: str) -> PMOTask:
        if task_id not in self._pmo_tasks:
            raise KeyError(f"Task not found: {task_id}")
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}. Must be one of {VALID_STATUSES}")
        task = self._pmo_tasks[task_id]
        task.status = status
        task.updated_at = _now_iso()
        return task

    def generate_report(self, month: str) -> COOReport:
        """月次レポート生成"""
        kpis = [k for k in self._kpis if k.month == month]
        budgets = [b for b in self._budgets if b.month == month]
        pmo_tasks = list(self._pmo_tasks.values())
        return COOReport(
            report_month=month,
            kpis=kpis,
            budgets=budgets,
            pmo_tasks=pmo_tasks,
            generated_at=_now_iso(),
        )

    def to_dict(self, report: COOReport) -> dict:
        return report.to_dict()
