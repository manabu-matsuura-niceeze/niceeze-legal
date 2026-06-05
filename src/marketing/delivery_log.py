"""MARKETING配信ログ — 配信履歴・成果追跡 (Ver 1.0)"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DeliveryRecord:
    id: str
    content_type: str  # 'x_post' | 'newsletter' | 'note' | 'youtube'
    topic: str
    category: str
    delivered_at: str  # ISO 8601 UTC datetime string
    char_count: int
    status: str  # 'delivered' | 'draft' | 'failed'


@dataclass
class DeliveryStats:
    total: int
    by_type: dict
    last_7days: int
    last_delivery_at: Optional[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_CONTENT_TYPES = {"x_post", "newsletter", "note", "youtube"}
_VALID_STATUSES = {"delivered", "draft", "failed"}


def _generate_id(topic: str, delivered_at: str) -> str:
    """Return a SHA-256 hex digest of topic + delivered_at."""
    raw = (topic + delivered_at).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# DeliveryLog
# ---------------------------------------------------------------------------

class DeliveryLog:
    """In-memory delivery history store for the Marketing department."""

    def __init__(self) -> None:
        self.records: list[DeliveryRecord] = []

    # ------------------------------------------------------------------
    # Mutating operations
    # ------------------------------------------------------------------

    def add(
        self,
        content_type: str,
        topic: str,
        category: str,
        char_count: int,
        status: str = "delivered",
    ) -> DeliveryRecord:
        """Create and append a new DeliveryRecord; return it.

        Parameters
        ----------
        content_type : str
            One of 'x_post', 'newsletter', 'note', 'youtube'.
        topic : str
            Subject / title of the delivered content.
        category : str
            Business category label (free text).
        char_count : int
            Character count of the content body.
        status : str, optional
            One of 'delivered', 'draft', 'failed'. Defaults to 'delivered'.
        """
        if content_type not in _VALID_CONTENT_TYPES:
            raise ValueError(
                f"Invalid content_type '{content_type}'. "
                f"Must be one of {_VALID_CONTENT_TYPES}."
            )
        if status not in _VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. "
                f"Must be one of {_VALID_STATUSES}."
            )

        delivered_at = _now_utc_iso()
        record_id = _generate_id(topic, delivered_at)

        record = DeliveryRecord(
            id=record_id,
            content_type=content_type,
            topic=topic,
            category=category,
            delivered_at=delivered_at,
            char_count=char_count,
            status=status,
        )
        self.records.append(record)
        return record

    # ------------------------------------------------------------------
    # Query operations
    # ------------------------------------------------------------------

    def get_by_type(self, content_type: str) -> list[DeliveryRecord]:
        """Return all records whose content_type matches."""
        return [r for r in self.records if r.content_type == content_type]

    def get_recent(self, days: int = 7) -> list[DeliveryRecord]:
        """Return records delivered within the last *days* days (UTC)."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result: list[DeliveryRecord] = []
        for r in self.records:
            try:
                dt = datetime.fromisoformat(r.delivered_at)
                # Ensure tz-aware for comparison
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt >= cutoff:
                    result.append(r)
            except ValueError:
                continue
        return result

    def summary(self) -> dict:
        """Return a summary dict with counts per content_type, total_delivered,
        and last_delivery_at (ISO string or None)."""
        by_type: dict[str, int] = {ct: 0 for ct in _VALID_CONTENT_TYPES}
        total_delivered = 0
        last_delivery_at: Optional[str] = None
        last_dt: Optional[datetime] = None

        for r in self.records:
            by_type[r.content_type] = by_type.get(r.content_type, 0) + 1
            if r.status == "delivered":
                total_delivered += 1
            try:
                dt = datetime.fromisoformat(r.delivered_at)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if last_dt is None or dt > last_dt:
                    last_dt = dt
                    last_delivery_at = r.delivered_at
            except ValueError:
                continue

        return {
            "by_type": by_type,
            "total_delivered": total_delivered,
            "last_delivery_at": last_delivery_at,
        }

    def to_json(self) -> str:
        """Return a JSON string of all records (list of dicts)."""
        return json.dumps(
            [asdict(r) for r in self.records],
            ensure_ascii=False,
            indent=2,
        )
