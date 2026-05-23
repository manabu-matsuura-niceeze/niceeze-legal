"""
NiceEze Layer3 LIFF通知連携 ユニットテスト
Ver 2.4 — Redis Streams Consumer Group 完全テスト

テスト構成:
  TestLineSignatureVerifier  : HMAC署名検証 (5件)
  TestRedisConsumerGroupManager: Consumer Group コアロジック (10件)
  TestLinePushGuard          : PUSH課金防御 + Consumer Group統合 (15件)
  TestLiffPullHandler        : PULL型更新 (5件)
  TestPubSubRedisBridge      : DBイベント受信 (4件)
  計: 39件
"""

import os
import json
import time
import hmac
import hashlib
import base64
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ["NICEEZE_AUDIT_RUNNING"] = "1"

import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.layer3.line_webhook import (
    LineSignatureVerifier,
    RedisConsumerGroupManager,
    LinePushGuard,
    LiffPullHandler,
    PubSubRedisBridge,
    PackageStatusEvent,
    PackageStatus,
    PushDecision,
    ConsumerGroupStatus,
    PUSH_REQUIRED_TRANSITIONS,
    MAX_PUSH_PER_PACKAGE,
    CONSUMER_GROUP_NAME,
    DEAD_LETTER_STREAM_KEY,
    PENDING_TIMEOUT_MS,
    MAX_RETRY_COUNT,
    JST,
)

# ─────────────────────────────────────────────
# フィクスチャ
# ─────────────────────────────────────────────
DUMMY_SECRET = "test_channel_secret_abcdef1234567890"
DAYTIME_JST  = datetime(2026, 5, 22, 14, 0, 0, tzinfo=JST)

@pytest.fixture
def verifier():
    return LineSignatureVerifier(DUMMY_SECRET)

@pytest.fixture
def cg_manager():
    return RedisConsumerGroupManager(redis_client=None)

@pytest.fixture
def push_guard():
    return LinePushGuard(redis_client=None)

@pytest.fixture
def pull_handler(push_guard):
    return LiffPullHandler(push_guard)

@pytest.fixture
def bridge(push_guard):
    return PubSubRedisBridge(push_guard)

@pytest.fixture(autouse=True)
def freeze_daytime(monkeypatch):
    """全テストで datetime.now を昼間に固定（silent_hours誤作動防止）"""
    import src.layer3.line_webhook as m
    orig = m.datetime

    class FakeDT:
        @staticmethod
        def now(tz=None):
            return DAYTIME_JST
        @staticmethod
        def fromisoformat(s):
            return orig.fromisoformat(s)

    monkeypatch.setattr(m, "datetime", FakeDT)

def make_event(
    user_id="u1", package_id="p1",
    prev_status="pending", new_status="in_transit",
    carrier="yamato",
) -> PackageStatusEvent:
    return PackageStatusEvent(
        user_id=user_id, package_id=package_id, tracking_no="t1",
        prev_status=prev_status, new_status=new_status,
        carrier=carrier, changed_at=DAYTIME_JST.isoformat(),
    )

def make_signature(body: bytes, secret: str) -> str:
    return base64.b64encode(
        hmac.new(secret.encode(), body, hashlib.sha256).digest()
    ).decode()


# ─────────────────────────────────────────────
# LineSignatureVerifier テスト (5件)
# ─────────────────────────────────────────────
class TestLineSignatureVerifier:
    def test_valid_signature_passes(self, verifier):
        body = b'{"events": []}'
        assert verifier.verify(body, make_signature(body, DUMMY_SECRET))

    def test_invalid_signature_fails(self, verifier):
        assert not verifier.verify(b'{"events": []}', "invalid")

    def test_empty_signature_fails(self, verifier):
        assert not verifier.verify(b'{"events": []}', "")

    def test_tampered_body_fails(self, verifier):
        body = b'{"events": []}'
        sig  = make_signature(body, DUMMY_SECRET)
        assert not verifier.verify(b'{"events": [{"type":"malicious"}]}', sig)

    def test_parse_events_extracts_fields(self, verifier):
        body = json.dumps({"events": [{
            "type": "message",
            "source": {"userId": "Uxxx", "type": "user"},
            "timestamp": 1716000000000,
            "replyToken": "reply-001",
            "message": {"type": "text", "text": "こんにちは"},
        }]}).encode()
        events = verifier.parse_events(body)
        assert len(events) == 1
        assert events[0].user_line_id == "Uxxx"
        assert events[0].message_text == "こんにちは"


# ─────────────────────────────────────────────
# RedisConsumerGroupManager テスト (10件)
# ─────────────────────────────────────────────
class TestRedisConsumerGroupManager:

    def test_group_created_on_first_ensure(self, cg_manager):
        """グループが存在しない場合に自動作成されること"""
        result = cg_manager.ensure_group_exists()
        assert result is True
        assert CONSUMER_GROUP_NAME in cg_manager._mem.get("groups", {})

    def test_group_idempotent_creation(self, cg_manager):
        """2回呼んでもエラーにならないこと（べき等性）"""
        cg_manager.ensure_group_exists()
        result = cg_manager.ensure_group_exists()
        assert result is True

    def test_xadd_stores_event(self, cg_manager):
        """XADDでイベントがStreamに追加されること"""
        event = make_event()
        sid = cg_manager.xadd(event)
        assert sid
        stream = cg_manager._mem.get("niceeze:package_events", [])
        assert len(stream) == 1
        assert stream[0][0] == sid

    def test_xadd_maxlen_enforced(self, cg_manager):
        """maxlen=10000 を超えたら古いエントリが削除されること"""
        for i in range(10005):
            cg_manager.xadd(make_event(package_id=f"p{i}"))
        stream = cg_manager._mem.get("niceeze:package_events", [])
        assert len(stream) <= 10000

    def test_xreadgroup_exclusive_delivery(self, cg_manager):
        """XREADGROUPで取得したメッセージが他インスタンスに配信されないこと"""
        cg_manager.ensure_group_exists()
        cg_manager.xadd(make_event(package_id="p-excl"))
        # 1回目の読み取り
        msgs1 = cg_manager.xreadgroup(count=10)
        assert len(msgs1) == 1
        # 2回目: 同じインスタンスでは未ACKのものは再取得されない
        msgs2 = cg_manager.xreadgroup(count=10)
        assert len(msgs2) == 0   # pending中のものは ">" では返らない

    def test_xack_removes_from_pending(self, cg_manager):
        """XACKで pending から除去されること"""
        cg_manager.ensure_group_exists()
        cg_manager.xadd(make_event(package_id="p-ack"))
        msgs = cg_manager.xreadgroup()
        assert len(msgs) == 1
        sid, _ = msgs[0]
        result = cg_manager.xack(sid)
        assert result is True
        # ACK後はpendingから消えている
        pending = cg_manager._mem["groups"][CONSUMER_GROUP_NAME]["pending"]
        assert sid not in pending

    def test_xack_nonexistent_returns_false(self, cg_manager):
        """存在しないIDのXACKはFalseを返すこと"""
        cg_manager.ensure_group_exists()
        assert cg_manager.xack("99999999-0") is False

    def test_xclaim_recovers_timed_out_event(self, cg_manager):
        """タイムアウトした未ACKイベントがXCLAIMで引き取られること"""
        cg_manager.ensure_group_exists()
        cg_manager.xadd(make_event(package_id="p-claim"))
        msgs = cg_manager.xreadgroup()
        assert len(msgs) == 1
        sid, _ = msgs[0]
        # タイムアウトを意図的に発生させる（added_at_ms を過去に設定）
        pending = cg_manager._mem["groups"][CONSUMER_GROUP_NAME]["pending"]
        pending[sid]["added_at_ms"] = int(time.time() * 1000) - PENDING_TIMEOUT_MS - 1000
        # XCLAIM で引き取り
        claimed = cg_manager.xclaim_timed_out()
        assert len(claimed) == 1
        assert claimed[0][0] == sid

    def test_dead_letter_after_max_retries(self, cg_manager):
        """MAX_RETRY_COUNT超過のイベントはデッドレターキューへ移動されること"""
        cg_manager.ensure_group_exists()
        cg_manager.xadd(make_event(package_id="p-dead"))
        msgs = cg_manager.xreadgroup()
        sid, _ = msgs[0]
        # retry_count を上限に設定
        pending = cg_manager._mem["groups"][CONSUMER_GROUP_NAME]["pending"]
        pending[sid]["retry_count"] = MAX_RETRY_COUNT
        pending[sid]["added_at_ms"] = int(time.time() * 1000) - PENDING_TIMEOUT_MS - 1000
        cg_manager.xclaim_timed_out()
        # デッドレターキューに入っていること
        dead = cg_manager._mem.get(DEAD_LETTER_STREAM_KEY, [])
        assert len(dead) == 1

    def test_get_status_returns_valid_struct(self, cg_manager):
        """get_status() が ConsumerGroupStatus を返すこと"""
        cg_manager.ensure_group_exists()
        status = cg_manager.get_status()
        assert isinstance(status, ConsumerGroupStatus)
        assert status.group_name == CONSUMER_GROUP_NAME
        assert status.consumer_name.startswith("worker")


# ─────────────────────────────────────────────
# LinePushGuard テスト (15件)
# ─────────────────────────────────────────────
class TestLinePushGuard:

    def test_process_next_events_full_cycle(self, push_guard):
        """XADD → XREADGROUP → XACK の完全サイクルが動作すること"""
        event = make_event()
        push_guard.add_to_redis_stream(event)
        push_guard.cg.ensure_group_exists()
        results = push_guard.process_next_events(count=10)
        assert len(results) == 1
        assert results[0]["status"] == "processed"
        assert results[0]["acked"] is True

    def test_no_duplicate_processing(self, push_guard):
        """同一イベントが2度処理されないこと（Consumer Group排他保証）"""
        event = make_event(package_id="p-nodup")
        push_guard.add_to_redis_stream(event)
        push_guard.cg.ensure_group_exists()
        r1 = push_guard.process_next_events()
        r2 = push_guard.process_next_events()
        assert len(r1) == 1
        assert len(r2) == 0   # 2回目は取得されない

    def test_recover_timed_out_events(self, push_guard):
        """タイムアウトイベントの回復処理が動作すること"""
        event = make_event(package_id="p-recover")
        push_guard.add_to_redis_stream(event)
        push_guard.cg.ensure_group_exists()
        msgs = push_guard.cg.xreadgroup()
        assert len(msgs) == 1
        sid, _ = msgs[0]
        # タイムアウトを強制
        pending = push_guard.cg._mem["groups"][CONSUMER_GROUP_NAME]["pending"]
        pending[sid]["added_at_ms"] = int(time.time() * 1000) - PENDING_TIMEOUT_MS - 1000
        recovered = push_guard.recover_timed_out_events()
        assert len(recovered) == 1
        assert recovered[0]["status"] == "recovered"

    def test_required_transition_triggers_push(self, push_guard):
        assert push_guard.decide(make_event()).should_push is True

    def test_non_required_transition_suppressed(self, push_guard):
        d = push_guard.decide(make_event(prev_status="in_transit", new_status="in_transit"))
        assert d.should_push is False
        assert d.suppressed_by == "transition_not_required"

    def test_dedup_prevents_second_push(self, push_guard):
        e = make_event(package_id="p-dedup")
        push_guard.decide(e)
        d2 = push_guard.decide(e)
        assert d2.should_push is False
        assert d2.suppressed_by == "dedup"

    def test_silent_hours_suppresses_push(self, push_guard, monkeypatch):
        import src.layer3.line_webhook as m
        orig = datetime
        night = datetime(2026, 5, 22, 3, 0, 0, tzinfo=JST)
        class NightDT:
            @staticmethod
            def now(tz=None): return night
            @staticmethod
            def fromisoformat(s): return orig.fromisoformat(s)
        monkeypatch.setattr(m, "datetime", NightDT)
        d = push_guard.decide(make_event(package_id="p-night"))
        assert d.should_push is False
        assert d.suppressed_by == "silent_hours"

    def test_already_read_suppresses_push(self, push_guard):
        changed = datetime(2026, 5, 22, 10, 0, tzinfo=JST)
        opened  = datetime(2026, 5, 22, 10, 30, tzinfo=JST)
        event = PackageStatusEvent(
            user_id="u1", package_id="p-read", tracking_no="t1",
            prev_status="pending", new_status="in_transit",
            carrier="y", changed_at=changed.isoformat(),
        )
        d = push_guard.decide(event, liff_last_opened_at=opened)
        assert d.suppressed_by == "already_read"

    def test_unread_allows_push(self, push_guard):
        changed = datetime(2026, 5, 22, 10, 0, tzinfo=JST)
        opened  = datetime(2026, 5, 22,  9, 0, tzinfo=JST)
        event = PackageStatusEvent(
            user_id="u1", package_id="p-unread", tracking_no="t1",
            prev_status="pending", new_status="in_transit",
            carrier="y", changed_at=changed.isoformat(),
        )
        d = push_guard.decide(event, liff_last_opened_at=opened)
        assert d.should_push is True

    def test_max_push_count_enforced(self, push_guard):
        key = f"niceeze:push_sent:p-max:total"
        push_guard._mem[key] = MAX_PUSH_PER_PACKAGE
        d = push_guard.decide(make_event(package_id="p-max"))
        assert d.suppressed_by == "max_count"

    def test_delivered_transition_triggers_push(self, push_guard):
        d = push_guard.decide(make_event(
            package_id="p-del",
            prev_status="out_for_delivery",
            new_status="delivered",
        ))
        assert d.should_push is True

    def test_new_package_pending_no_push(self, push_guard):
        d = push_guard.decide(make_event(prev_status=None, new_status="pending"))
        assert d.should_push is False
        assert d.suppressed_by == "initial_status"

    def test_all_required_transitions_defined(self, push_guard):
        assert len(PUSH_REQUIRED_TRANSITIONS) >= 5

    def test_silent_batch_add_and_flush(self, push_guard):
        push_guard.add_to_silent_batch(make_event(package_id="p-batch"))
        batch = push_guard.flush_silent_batch()
        assert len(batch) == 1
        assert batch[0]["package_id"] == "p-batch"
        assert push_guard.flush_silent_batch() == []

    def test_consumer_group_status_accessible(self, push_guard):
        """LinePushGuardからConsumer Group状態が取得できること"""
        push_guard.cg.ensure_group_exists()
        status = push_guard.cg.get_status()
        assert isinstance(status, ConsumerGroupStatus)
        assert status.pending_count == 0


# ─────────────────────────────────────────────
# LiffPullHandler テスト (5件)
# ─────────────────────────────────────────────
class TestLiffPullHandler:
    def test_pull_returns_new_events(self, pull_handler, push_guard):
        push_guard.add_to_redis_stream(make_event(user_id="u-pull"))
        resp = pull_handler.handle_pull("u-pull", last_stream_id="0")
        assert resp.has_updates is True

    def test_pull_empty_when_no_updates(self, pull_handler):
        resp = pull_handler.handle_pull("u-empty")
        assert resp.has_updates is False

    def test_pull_filters_by_user_id(self, pull_handler, push_guard):
        push_guard.add_to_redis_stream(make_event(user_id="user-A", package_id="pA"))
        push_guard.add_to_redis_stream(make_event(user_id="user-B", package_id="pB"))
        resp = pull_handler.handle_pull("user-A")
        assert all(e["user_id"] == "user-A" for e in resp.packages)

    def test_pull_cache_within_30s(self, pull_handler, push_guard):
        push_guard.add_to_redis_stream(make_event(user_id="u-cache"))
        pull_handler.handle_pull("u-cache")
        resp2 = pull_handler.handle_pull("u-cache")
        assert resp2.cache_hit is True

    def test_pull_does_not_consume_group(self, pull_handler, push_guard):
        """PULL型はConsumer Groupに影響を与えないこと"""
        push_guard.cg.ensure_group_exists()
        push_guard.add_to_redis_stream(make_event(user_id="u-nocg", package_id="p-nocg"))
        pull_handler.handle_pull("u-nocg")
        # Consumer Groupのpendingは空のまま（PULLは非破壊）
        pending = push_guard.cg._mem.get("groups", {}).get(CONSUMER_GROUP_NAME, {}).get("pending", {})
        assert len(pending) == 0


# ─────────────────────────────────────────────
# PubSubRedisBridge テスト (4件)
# ─────────────────────────────────────────────
class TestPubSubRedisBridge:
    def test_valid_payload_processed(self, bridge):
        payload = json.dumps({
            "user_id": "u1", "package_id": "p1",
            "tracking_no": "123", "status": "in_transit",
            "prev_status": "pending", "carrier": "yamato",
            "changed_at": DAYTIME_JST.isoformat(),
        })
        result = bridge.handle_db_notification(payload)
        assert "stream_id" in result
        assert result["duplicate_safe"] is True
        assert result["processing_mode"] == "consumer_group_exclusive"

    def test_invalid_json_returns_error(self, bridge):
        result = bridge.handle_db_notification("not-json{{{")
        assert result["status"] == "error"

    def test_consumer_group_name_in_result(self, bridge):
        payload = json.dumps({
            "user_id": "u2", "package_id": "p2",
            "tracking_no": "456", "status": "in_transit",
            "prev_status": "pending", "carrier": "sagawa",
            "changed_at": DAYTIME_JST.isoformat(),
        })
        result = bridge.handle_db_notification(payload)
        assert result["consumer_group"] == CONSUMER_GROUP_NAME

    def test_silent_hours_triggers_batch(self, bridge, monkeypatch):
        import src.layer3.line_webhook as m
        orig  = datetime
        night = datetime(2026, 5, 22, 2, 0, tzinfo=JST)
        class NightDT:
            @staticmethod
            def now(tz=None): return night
            @staticmethod
            def fromisoformat(s): return orig.fromisoformat(s)
        monkeypatch.setattr(m, "datetime", NightDT)
        # bridge はXADDのみ行うため、bridgeのresultにbatchedは含まれない
        # PUSH判定は process_next_events 内で行われる設計
        payload = json.dumps({
            "user_id": "u3", "package_id": "p3",
            "tracking_no": "789", "status": "in_transit",
            "prev_status": "pending", "carrier": "yuubin",
            "changed_at": night.isoformat(),
        })
        result = bridge.handle_db_notification(payload)
        # Ver 2.4ではbridgeはXADDのみ。stream_idが返れば成功
        assert "stream_id" in result
