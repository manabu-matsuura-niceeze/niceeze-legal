"""
TMS-SET-001: 初期設定・マスタ管理モジュール (Ver 1.0)
SBDS部 — 建物マスタ・フロアグリッドエディタ バックエンド
LAYOUT_MASTER.md TMS-SET-001定義準拠
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timezone


# ──────────────────────────────────────────
# データモデル
# ──────────────────────────────────────────

@dataclass
class EVSpec:
    """EV（エレベーター）仕様"""
    residential_count: int   # 居住者用EV基数 (0-20)
    service_count: int       # 業務用EV基数 (最低4基)

    def __post_init__(self) -> None:
        if not (0 <= self.residential_count <= 20):
            raise ValueError(f"居住者用EV基数は0-20の範囲: {self.residential_count}")
        if self.service_count < 4:
            raise ValueError(f"業務用EVは4基以上必須: {self.service_count}")


@dataclass
class BuildingSpec:
    """建物基本スペック (TMS-SET-001 上部エリア)"""
    building_count: int        # 棟数 (1-20)
    floor_count: int           # 階数 (1-100)
    ev_spec: EVSpec
    procedure_delays_min: list[int] = field(default_factory=list)  # 手続き遅延時間(分)

    def __post_init__(self) -> None:
        if not (1 <= self.building_count <= 20):
            raise ValueError(f"棟数は1-20の範囲: {self.building_count}")
        if not (1 <= self.floor_count <= 100):
            raise ValueError(f"階数は1-100の範囲: {self.floor_count}")


@dataclass
class RoomRecord:
    """フロアグリッドエディタ 1行レコード (TMS-SET-001 中央エリア)"""
    building_name: str          # 棟名
    room_number: str            # 部屋番号
    area_sqm: float             # 専有面積(㎡)
    rent_jpy: int               # 家賃(円)
    ev_exit_distance_m: float   # EV出口距離(m)
    floor: int                  # 階

    def __post_init__(self) -> None:
        if not self.building_name.strip():
            raise ValueError("棟名は必須")
        if not re.match(r"^\d{3,4}[A-Za-z]?$", self.room_number):
            raise ValueError(f"部屋番号フォーマット不正: {self.room_number}")
        if self.area_sqm <= 0:
            raise ValueError(f"専有面積は正値: {self.area_sqm}")
        if self.rent_jpy < 0:
            raise ValueError(f"家賃は0以上: {self.rent_jpy}")
        if self.ev_exit_distance_m < 0:
            raise ValueError(f"EV出口距離は0以上: {self.ev_exit_distance_m}")


@dataclass
class BuildingMaster:
    """建物マスタ — TMS-SET-001 全データ"""
    property_id: str
    spec: BuildingSpec
    rooms: list[RoomRecord] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def add_room(self, room: RoomRecord) -> None:
        self.rooms.append(room)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "property_id": self.property_id,
            "spec": {
                "building_count": self.spec.building_count,
                "floor_count": self.spec.floor_count,
                "ev_residential": self.spec.ev_spec.residential_count,
                "ev_service": self.spec.ev_spec.service_count,
                "procedure_delays_min": self.spec.procedure_delays_min,
            },
            "rooms": [
                {
                    "building_name": r.building_name,
                    "room_number": r.room_number,
                    "area_sqm": r.area_sqm,
                    "rent_jpy": r.rent_jpy,
                    "ev_exit_distance_m": r.ev_exit_distance_m,
                    "floor": r.floor,
                }
                for r in self.rooms
            ],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ──────────────────────────────────────────
# Firestore永続化（Cloud Run環境）
# ──────────────────────────────────────────

class BuildingMasterRepository:
    """BuildingMaster の Firestore CRUD"""

    COLLECTION = "building_masters"

    def __init__(self, db) -> None:
        self._db = db

    def save(self, master: BuildingMaster) -> str:
        doc_ref = self._db.collection(self.COLLECTION).document(master.property_id)
        doc_ref.set(master.to_dict())
        return master.property_id

    def get(self, property_id: str) -> Optional[dict]:
        doc = self._db.collection(self.COLLECTION).document(property_id).get()
        return doc.to_dict() if doc.exists else None

    def delete(self, property_id: str) -> None:
        self._db.collection(self.COLLECTION).document(property_id).delete()


# ──────────────────────────────────────────
# ルーティング距離計算
# ──────────────────────────────────────────

def calculate_routing_distance(rooms: list[RoomRecord]) -> list[RoomRecord]:
    """
    EV出口距離でソートした最適配送順路を返す。
    同一フロア内はev_exit_distance_m昇順、フロア間は階昇順。
    """
    return sorted(rooms, key=lambda r: (r.floor, r.ev_exit_distance_m))
