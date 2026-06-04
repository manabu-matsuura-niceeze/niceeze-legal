"""
TMS-DRV-001: 配送員スマホ・ルーティングモジュール (Ver 1.0)
SBDS部 — Jaro-Winkler名寄せ / IndexedDB v142 / 労働法ロック
LAYOUT_MASTER.md TMS-DRV-001定義準拠
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ──────────────────────────────────────────
# 定数
# ──────────────────────────────────────────

INDEXEDDB_VERSION = 142          # niceeze_cache_v142 (v14.0=140から移行)
JW_THRESHOLD = 0.85              # Jaro-Winkler名寄せ閾値
LABOR_LAW_BREAK_MINUTES = 240    # 4時間 = 240分
STATUS_LOCKED_BY_LABOR_LAW = "STATUS_LOCKED_BY_LABOR_LAW"
PULL_NOTIFY_SECONDS_BEFORE = 60  # 1分前PULL通知


# ──────────────────────────────────────────
# Jaro-Winkler 名寄せエンジン
# ──────────────────────────────────────────

def _jaro(s1: str, s2: str) -> float:
    if s1 == s2:
        return 1.0
    len1, len2 = len(s1), len(s2)
    if len1 == 0 or len2 == 0:
        return 0.0

    match_dist = max(len1, len2) // 2 - 1
    if match_dist < 0:
        match_dist = 0

    s1_matches = [False] * len1
    s2_matches = [False] * len2
    matches = 0
    transpositions = 0

    for i, c1 in enumerate(s1):
        start = max(0, i - match_dist)
        end = min(i + match_dist + 1, len2)
        for j in range(start, end):
            if s2_matches[j] or c1 != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1

    return (matches / len1 + matches / len2 + (matches - transpositions / 2) / matches) / 3


def jaro_winkler(s1: str, s2: str, p: float = 0.1) -> float:
    """Jaro-Winkler距離 (0.0〜1.0)。p=接頭一致ボーナス係数。"""
    jaro_score = _jaro(s1, s2)
    prefix = 0
    for c1, c2 in zip(s1, s2):
        if c1 == c2:
            prefix += 1
        else:
            break
        if prefix == 4:
            break
    return jaro_score + prefix * p * (1 - jaro_score)


def match_recipient_name(candidate: str, reference: str) -> bool:
    """宛名名寄せ: D_jw >= JW_THRESHOLD で同一人物と判定"""
    score = jaro_winkler(candidate.strip(), reference.strip())
    return score >= JW_THRESHOLD


# ──────────────────────────────────────────
# 労働法ロック
# ──────────────────────────────────────────

@dataclass
class WorkSession:
    """配送スタッフの作業セッション管理"""
    staff_id: str
    start_ts: float = field(default_factory=time.time)
    status: str = "ACTIVE"

    def elapsed_minutes(self) -> float:
        return (time.time() - self.start_ts) / 60

    def check_labor_law(self) -> str:
        """4時間超過時に STATUS_LOCKED_BY_LABOR_LAW を返す"""
        if self.elapsed_minutes() >= LABOR_LAW_BREAK_MINUTES:
            self.status = STATUS_LOCKED_BY_LABOR_LAW
        return self.status

    def reset(self) -> None:
        """休憩後に再開"""
        self.start_ts = time.time()
        self.status = "ACTIVE"


# ──────────────────────────────────────────
# 配送パッケージ
# ──────────────────────────────────────────

@dataclass
class DeliveryPackage:
    """配送1件のデータ"""
    package_id: str
    room_number: str
    recipient_name: str           # 「配送スタッフ」表記統一済（「佐藤」禁止）
    floor: int
    ev_exit_distance_m: float
    is_frozen: bool = False       # 冷凍フラグ
    is_refrigerated: bool = False # 冷蔵フラグ
    is_complaint_risk: bool = False  # クレーム要注意フラグ
    status: str = "PENDING"
    estimated_arrival_ts: Optional[float] = None

    @property
    def requires_direct_handoff(self) -> bool:
        return self.is_frozen or self.is_refrigerated

    def complete(self) -> None:
        self.status = "COMPLETED"

    def to_cache_dict(self) -> dict:
        """IndexedDB v142 用シリアライズ"""
        return {
            "package_id": self.package_id,
            "room_number": self.room_number,
            "recipient_name": self.recipient_name,
            "floor": self.floor,
            "ev_exit_distance_m": self.ev_exit_distance_m,
            "is_frozen": self.is_frozen,
            "is_refrigerated": self.is_refrigerated,
            "is_complaint_risk": self.is_complaint_risk,
            "status": self.status,
            "estimated_arrival_ts": self.estimated_arrival_ts,
            "_idb_version": INDEXEDDB_VERSION,
        }


# ──────────────────────────────────────────
# ルーティングエンジン
# ──────────────────────────────────────────

def sort_delivery_route(packages: list[DeliveryPackage]) -> list[DeliveryPackage]:
    """
    最適配送順路ソート:
    - 同一フロア内: EV出口距離昇順
    - フロア間: 階昇順
    - クレーム要注意は同フロア最後尾へ
    - 処理速度目標: ≤ 0.7秒 (IndexedDB活用)
    """
    def sort_key(p: DeliveryPackage) -> tuple:
        return (p.floor, p.is_complaint_risk, p.ev_exit_distance_m)

    return sorted(packages, key=sort_key)


def estimate_arrival_times(
    packages: list[DeliveryPackage],
    walking_speed_ms: float = 1.2,     # 歩行速度 m/s
    ev_wait_sec: float = 30.0,         # EV待ち時間(秒)
) -> list[DeliveryPackage]:
    """各パッケージの推定到着時刻を計算してセット"""
    now = time.time()
    current_floor = 1
    current_ts = now

    for pkg in packages:
        if pkg.floor != current_floor:
            current_ts += ev_wait_sec
            current_floor = pkg.floor
        travel_time = pkg.ev_exit_distance_m / walking_speed_ms
        current_ts += travel_time
        pkg.estimated_arrival_ts = current_ts

    return packages


def should_send_pull_notify(pkg: DeliveryPackage) -> bool:
    """到着1分前にLINE PULL通知を発火すべきか判定"""
    if pkg.estimated_arrival_ts is None:
        return False
    remaining = pkg.estimated_arrival_ts - time.time()
    return 0 < remaining <= PULL_NOTIFY_SECONDS_BEFORE
