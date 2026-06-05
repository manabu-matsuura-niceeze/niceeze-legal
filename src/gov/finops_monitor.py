"""FinOps監視 — 1配送¥0.5円上限アラート (Ver 1.0)
GOV部門 MVP
FinOps: 月額¥5,000以内 / PII不使用 / bandit 0件
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone


MAX_COST_PER_DELIVERY_JPY: float = 0.5   # 1配送あたり上限コスト（¥0.5）
MONTHLY_BUDGET_JPY: int = 5000            # 月次予算上限 ¥5,000
ALERT_THRESHOLD_RATE: float = 0.8        # アラート閾値（予算の80%消化でアラート）


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DeliveryCostRecord:
    """配送コスト記録"""
    delivery_id: str
    service: str        # 'sbds' | 'surplus_shift' | 'research' | 'marketing' | 'gov'
    cost_jpy: float     # 実コスト（GCPコスト）
    delivery_count: int # 処理件数
    month: str
    recorded_at: str

    @property
    def cost_per_delivery(self) -> float:
        return self.cost_jpy / max(self.delivery_count, 1)

    @property
    def is_over_limit(self) -> bool:
        return self.cost_per_delivery > MAX_COST_PER_DELIVERY_JPY

    def to_dict(self) -> dict:
        return {
            "delivery_id": self.delivery_id,
            "service": self.service,
            "cost_jpy": self.cost_jpy,
            "delivery_count": self.delivery_count,
            "month": self.month,
            "recorded_at": self.recorded_at,
            "cost_per_delivery": self.cost_per_delivery,
            "is_over_limit": self.is_over_limit,
        }


@dataclass
class FinOpsAlert:
    """FinOpsアラート"""
    alert_type: str    # 'cost_per_delivery_exceeded' | 'monthly_budget_warning' | 'monthly_budget_exceeded'
    service: str
    message: str
    value: float
    threshold: float
    triggered_at: str

    def to_dict(self) -> dict:
        return {
            "alert_type": self.alert_type,
            "service": self.service,
            "message": self.message,
            "value": self.value,
            "threshold": self.threshold,
            "triggered_at": self.triggered_at,
        }


class FinOpsMonitor:
    """FinOps監視エンジン"""

    def __init__(self) -> None:
        self._records: list[DeliveryCostRecord] = []

    def record_cost(
        self,
        service: str,
        cost_jpy: float,
        delivery_count: int,
        month: str,
    ) -> DeliveryCostRecord:
        """コスト記録"""
        recorded_at = _now_iso()
        delivery_id = hashlib.sha256(
            f"{service}:{month}:{recorded_at}".encode()
        ).hexdigest()[:16]
        record = DeliveryCostRecord(
            delivery_id=delivery_id,
            service=service,
            cost_jpy=cost_jpy,
            delivery_count=delivery_count,
            month=month,
            recorded_at=recorded_at,
        )
        self._records.append(record)
        return record

    def check_alerts(self) -> list[FinOpsAlert]:
        """全レコードをチェックしてアラートリスト返却"""
        alerts: list[FinOpsAlert] = []
        now = _now_iso()

        # 1配送コスト超過チェック
        for rec in self._records:
            if rec.is_over_limit:
                alerts.append(FinOpsAlert(
                    alert_type="cost_per_delivery_exceeded",
                    service=rec.service,
                    message=(
                        f"{rec.service} の1配送コスト ¥{rec.cost_per_delivery:.4f} が"
                        f"上限 ¥{MAX_COST_PER_DELIVERY_JPY} を超過しています"
                    ),
                    value=rec.cost_per_delivery,
                    threshold=MAX_COST_PER_DELIVERY_JPY,
                    triggered_at=now,
                ))

        # 月次予算チェック（月ごと・サービスを跨いだ合計）
        month_totals: dict[str, float] = {}
        for rec in self._records:
            month_totals[rec.month] = month_totals.get(rec.month, 0.0) + rec.cost_jpy

        for month, total in month_totals.items():
            budget_warning = MONTHLY_BUDGET_JPY * ALERT_THRESHOLD_RATE
            if total > MONTHLY_BUDGET_JPY:
                alerts.append(FinOpsAlert(
                    alert_type="monthly_budget_exceeded",
                    service="all",
                    message=(
                        f"{month} の月次合計コスト ¥{total:.2f} が"
                        f"予算上限 ¥{MONTHLY_BUDGET_JPY} を超過しています"
                    ),
                    value=total,
                    threshold=float(MONTHLY_BUDGET_JPY),
                    triggered_at=now,
                ))
            elif total > budget_warning:
                alerts.append(FinOpsAlert(
                    alert_type="monthly_budget_warning",
                    service="all",
                    message=(
                        f"{month} の月次合計コスト ¥{total:.2f} が"
                        f"予算の{int(ALERT_THRESHOLD_RATE * 100)}% (¥{budget_warning:.0f}) を超えました"
                    ),
                    value=total,
                    threshold=budget_warning,
                    triggered_at=now,
                ))

        return alerts

    def monthly_summary(self, month: str) -> dict:
        """月次FinOpsサマリー"""
        records = [r for r in self._records if r.month == month]
        total_cost = sum(r.cost_jpy for r in records)
        total_deliveries = sum(r.delivery_count for r in records)
        avg_cost = total_cost / max(total_deliveries, 1)
        alerts = [a for a in self.check_alerts() if month in a.message or a.service != "all"]
        # count alerts related to this month
        month_alerts = [
            a for a in self.check_alerts()
            if month in a.message
        ]
        return {
            "month": month,
            "total_cost_jpy": total_cost,
            "total_deliveries": total_deliveries,
            "avg_cost_per_delivery": avg_cost,
            "alerts_count": len(month_alerts),
            "budget_remaining_jpy": MONTHLY_BUDGET_JPY - total_cost,
        }

    def to_dict(self) -> dict:
        """全レコード辞書化"""
        return {
            "records": [r.to_dict() for r in self._records],
            "total_records": len(self._records),
        }
