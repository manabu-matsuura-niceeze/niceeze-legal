"""稼働ログ収集 — SBDS/SURPLUS/RESEARCH/MARKETING稼働ログ (Ver 1.0)
GOV部門 MVP
FinOps: 月額¥5,000以内 / PII不使用 / bandit 0件
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional


VALID_SERVICES = ['sbds', 'surplus_shift', 'research', 'marketing', 'gov']
VALID_LOG_LEVELS = ['info', 'warning', 'error']


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class OpsLogEntry:
    log_id: str
    service: str
    level: str
    message: str
    metadata: dict = field(default_factory=dict)
    recorded_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict:
        return {
            'log_id': self.log_id,
            'service': self.service,
            'level': self.level,
            'message': self.message,
            'metadata': self.metadata,
            'recorded_at': self.recorded_at,
        }


@dataclass
class ServiceHealthStatus:
    service: str
    total_logs: int
    error_count: int
    warning_count: int
    last_log_at: Optional[str]
    is_healthy: bool

    def to_dict(self) -> dict:
        return {
            'service': self.service,
            'total_logs': self.total_logs,
            'error_count': self.error_count,
            'warning_count': self.warning_count,
            'last_log_at': self.last_log_at,
            'is_healthy': self.is_healthy,
        }


class OpsLogCollector:
    def __init__(self) -> None:
        self._logs: list[OpsLogEntry] = []

    def record(self, service: str, level: str, message: str, metadata: Optional[dict] = None) -> OpsLogEntry:
        if service not in VALID_SERVICES:
            raise ValueError(f"Invalid service '{service}'. Must be one of {VALID_SERVICES}")
        if level not in VALID_LOG_LEVELS:
            raise ValueError(f"Invalid level '{level}'. Must be one of {VALID_LOG_LEVELS}")
        recorded_at = _now_iso()
        log_id = hashlib.sha256(f"{service}:{message}:{recorded_at}".encode()).hexdigest()[:16]
        entry = OpsLogEntry(log_id=log_id, service=service, level=level, message=message,
                            metadata=metadata or {}, recorded_at=recorded_at)
        self._logs.append(entry)
        return entry

    def get_by_service(self, service: str) -> list[OpsLogEntry]:
        return [e for e in self._logs if e.service == service]

    def get_errors(self) -> list[OpsLogEntry]:
        return [e for e in self._logs if e.level == 'error']

    def get_recent(self, minutes: int = 60) -> list[OpsLogEntry]:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        result = []
        for e in self._logs:
            try:
                dt = datetime.fromisoformat(e.recorded_at)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt >= cutoff:
                    result.append(e)
            except ValueError:
                continue
        return result

    def health_status(self) -> list[ServiceHealthStatus]:
        statuses = []
        for svc in VALID_SERVICES:
            logs = self.get_by_service(svc)
            errors = [e for e in logs if e.level == 'error']
            warnings = [e for e in logs if e.level == 'warning']
            statuses.append(ServiceHealthStatus(
                service=svc,
                total_logs=len(logs),
                error_count=len(errors),
                warning_count=len(warnings),
                last_log_at=logs[-1].recorded_at if logs else None,
                is_healthy=len(errors) == 0,
            ))
        return statuses

    def summary(self) -> dict:
        by_level = {lvl: 0 for lvl in VALID_LOG_LEVELS}
        by_service = {svc: 0 for svc in VALID_SERVICES}
        for e in self._logs:
            by_level[e.level] = by_level.get(e.level, 0) + 1
            by_service[e.service] = by_service.get(e.service, 0) + 1
        return {'total_logs': len(self._logs), 'by_level': by_level, 'by_service': by_service}
