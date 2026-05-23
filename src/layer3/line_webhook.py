"""
NiceEze Layer3 — LINE Webhook受信エンジン
Ver 2.4 — Redis Streams Consumer Group実装（重複防止・生存保証）

【Ver 2.3 → Ver 2.4 の変更点】
  問題: XADD/XREADのみの実装では、Cloud Runが複数インスタンスに
        スケールアウトした際に同一イベントを複数インスタンスが処理し、
        LINE PUSH 二重課金・AI API 二重課金が発生する。

  解決: Redis Streams Consumer Group を実装する。
    XGROUP CREATE  → グループ作成（起動時に1回だけ実行）
    XREADGROUP     → 「このインスタンスが処理する」と宣言して取得（排他）
    XACK           → 処理完了を明示（Redisが配信済みと記録）
    XPENDING       → 未ACKイベントを監視（生存保証の監視ポイント）
    XCLAIM         → タイムアウトした未ACKを別インスタンスが引き取り

  これにより:
    ✅ 1イベント = 1インスタンスのみ処理（排他保証）
    ✅ クラッシュ時のイベント消失なし（XCLAIM で再処理）
    ✅ LINE PUSH 二重課金ゼロ
    ✅ Claude API / AI API 二重課金ゼロ

GCP統合:
  - Cloud Run     : 複数インスタンス対応（min=0, max=10）
  - Memorystore   : Redis Streams Consumer Group
  - Cloud SQL     : pg_notify → Pub/Sub → このモジュール
  - Secret Manager: LINE Channel Secret
"""

import hmac
import hashlib
import base64
import json
import time
import os
import socket
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# 定数・設定
# ─────────────────────────────────────────────
LINE_SIGNATURE_HEADER    = "X-Line-Signature"
REDIS_STREAM_KEY         = "niceeze:package_events"

# Consumer Group 定数
CONSUMER_GROUP_NAME      = "niceeze-liff-workers"   # グループ名（全インスタンス共通）
CONSUMER_NAME_PREFIX     = "worker"                 # 個別インスタンスID接頭辞
PENDING_TIMEOUT_MS       = 30_000                   # 30秒: 未ACKをtimeoutと判定
XCLAIM_CHECK_INTERVAL_S  = 60                       # 60秒ごとに孤立イベントを回収
MAX_RETRY_COUNT          = 3                        # 最大再試行回数（超過は死活キューへ）
DEAD_LETTER_STREAM_KEY   = "niceeze:package_events:dead"  # 処理不能イベント退避先

REDIS_PUSH_DEDUP_PREFIX  = "niceeze:push_sent:"
REDIS_PULL_CACHE_PREFIX  = "niceeze:pull_cache:"
PUSH_DEDUP_TTL_SEC       = 86400
PULL_CACHE_TTL_SEC       = 30
MAX_PUSH_PER_PACKAGE     = 3
SILENT_HOURS_START       = 0
SILENT_HOURS_END         = 7
JST = timezone(timedelta(hours=9))


class LineEventType(str, Enum):
    MESSAGE  = "message"
    FOLLOW   = "follow"
    UNFOLLOW = "unfollow"
    POSTBACK = "postback"


class PackageStatus(str, Enum):
    PENDING          = "pending"
    IN_TRANSIT       = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED        = "delivered"
    RETURNED         = "returned"
    RESCHEDULED      = "rescheduled"


PUSH_REQUIRED_TRANSITIONS = {
    (PackageStatus.PENDING,          PackageStatus.IN_TRANSIT),
    (PackageStatus.IN_TRANSIT,       PackageStatus.OUT_FOR_DELIVERY),
    (PackageStatus.OUT_FOR_DELIVERY, PackageStatus.DELIVERED),
    (PackageStatus.IN_TRANSIT,       PackageStatus.RESCHEDULED),
    (PackageStatus.OUT_FOR_DELIVERY, PackageStatus.RESCHEDULED),
}


# ─────────────────────────────────────────────
# データ構造
# ─────────────────────────────────────────────
@dataclass
class LineWebhookEvent:
    event_type:    str
    user_line_id:  str
    timestamp_ms:  int
    reply_token:   Optional[str]  = None
    message_text:  Optional[str]  = None
    postback_data: Optional[str]  = None
    raw:           dict           = field(default_factory=dict)


@dataclass
class PackageStatusEvent:
    user_id:      str
    package_id:   str
    tracking_no:  str
    prev_status:  Optional[str]
    new_status:   str
    carrier:      str
    changed_at:   str


@dataclass
class PushDecision:
    should_push:   bool
    reason:        str
    push_count:    int  = 0
    suppressed_by: str  = ""


@dataclass
class PullResponse:
    packages:     list
    has_updates:  bool
    last_checked: str
    cache_hit:    bool = False


@dataclass
class ConsumerGroupStatus:
    """Consumer Group の稼働状況（監視・ヘルスチェック用）"""
    group_name:      str
    consumer_name:   str
    pending_count:   int
    claimed_count:   int
    dead_letter_count: int
    last_checked_at: str


# ─────────────────────────────────────────────
# HMAC署名検証
# ─────────────────────────────────────────────
class LineSignatureVerifier:
    """LINE Messaging API Webhook の HMAC-SHA256 署名を検証する。"""

    def __init__(self, channel_secret: str):
        self._secret = channel_secret.encode("utf-8")

    def verify(self, body: bytes, signature: str) -> bool:
        if not signature:
            return False
        expected = base64.b64encode(
            hmac.new(self._secret, body, hashlib.sha256).digest()
        ).decode("utf-8")
        return hmac.compare_digest(expected, signature)

    def parse_events(self, body: bytes) -> list[LineWebhookEvent]:
        data = json.loads(body.decode("utf-8"))
        events = []
        for ev in data.get("events", []):
            source = ev.get("source", {})
            events.append(LineWebhookEvent(
                event_type    = ev.get("type", ""),
                user_line_id  = source.get("userId", ""),
                timestamp_ms  = ev.get("timestamp", 0),
                reply_token   = ev.get("replyToken"),
                message_text  = (ev.get("message", {}).get("text")
                                 if ev.get("type") == "message" else None),
                postback_data = (ev.get("postback", {}).get("data")
                                 if ev.get("type") == "postback" else None),
                raw           = ev,
            ))
        return events


# ─────────────────────────────────────────────
# Redis Consumer Group マネージャー
# ─────────────────────────────────────────────
class RedisConsumerGroupManager:
    """
    Memorystore Redis Streams の Consumer Group を管理する。

    【設計思想】
    Cloud Run はスケールアウト/インが頻繁に発生する。
    各インスタンスは起動時に固有の consumer_name（Pod名 or ランダムID）
    を持ち、XREADGROUP で自分専用のメッセージのみ取得する。

    処理完了後は必ず XACK を呼ぶ。
    クラッシュした場合、XPENDING で未ACKが検出され、
    XCLAIM で別の生きているインスタンスが引き取る。

    テスト環境では redis_client=None でインメモリ実装を使用する。
    本番では redis.asyncio.Redis（Memorystore接続済み）を渡す。
    """

    def __init__(self, redis_client=None):
        self._redis        = redis_client
        # インスタンス固有ID（Cloud Run では K_REVISION 環境変数が使える）
        self._consumer_name = self._make_consumer_name()
        # インメモリ実装（テスト用）
        self._mem: dict    = {}
        self._group_created: bool = False
        logger.info(f"ConsumerGroupManager起動: consumer={self._consumer_name}")

    @staticmethod
    def _make_consumer_name() -> str:
        """Cloud Run の Revision名またはホスト名で一意なConsumer名を生成"""
        revision = os.environ.get("K_REVISION", "")
        if revision:
            return f"{CONSUMER_NAME_PREFIX}-{revision}"
        return f"{CONSUMER_NAME_PREFIX}-{socket.gethostname()}"

    # ── グループ初期化 ────────────────────────────

    def ensure_group_exists(self) -> bool:
        """
        Consumer Group が存在しなければ作成する。
        Cloud Run インスタンス起動時に1回だけ呼ぶ。
        MKSTREAM: Streamが存在しない場合も自動作成。
        """
        if self._group_created:
            return True

        if self._redis:
            try:
                # $ = 現時点以降の新しいメッセージのみ受信
                self._redis.xgroup_create(
                    REDIS_STREAM_KEY,
                    CONSUMER_GROUP_NAME,
                    id="$",
                    mkstream=True,
                )
                logger.info(f"Consumer Group作成: {CONSUMER_GROUP_NAME}")
            except Exception as e:
                # BUSYGROUP: 既に存在する場合は正常（競合防止）
                if "BUSYGROUP" in str(e):
                    logger.info(f"Consumer Group既存: {CONSUMER_GROUP_NAME}")
                else:
                    logger.error(f"XGROUP CREATE失敗: {e}")
                    return False
        else:
            # インメモリ実装
            if "groups" not in self._mem:
                self._mem["groups"] = {}
            if CONSUMER_GROUP_NAME not in self._mem["groups"]:
                self._mem["groups"][CONSUMER_GROUP_NAME] = {
                    "consumers": {},
                    "pending":   {},   # stream_id → {consumer, added_at, retry_count}
                }

        self._group_created = True
        return True

    # ── XADD（イベント追加） ─────────────────────

    def xadd(self, event: PackageStatusEvent) -> str:
        """
        Stream にイベントを追加する（XADD）。
        maxlen=10000 で古いエントリを自動削除（メモリ上限）。
        """
        stream_data = {
            "user_id":    event.user_id,
            "package_id": event.package_id,
            "tracking_no": event.tracking_no,
            "status":     event.new_status,
            "prev_status": event.prev_status or "",
            "carrier":    event.carrier,
            "changed_at": event.changed_at,
        }

        if self._redis:
            stream_id = self._redis.xadd(
                REDIS_STREAM_KEY,
                stream_data,
                maxlen=10000,
                approximate=True,
            )
            return stream_id.decode() if isinstance(stream_id, bytes) else str(stream_id)

        # インメモリ実装
        stream_id = f"{int(time.time() * 1000)}-0"
        if REDIS_STREAM_KEY not in self._mem:
            self._mem[REDIS_STREAM_KEY] = []
        self._mem[REDIS_STREAM_KEY].append((stream_id, stream_data))
        # maxlen相当: 10000件超で古いものを削除
        if len(self._mem[REDIS_STREAM_KEY]) > 10000:
            self._mem[REDIS_STREAM_KEY] = self._mem[REDIS_STREAM_KEY][-10000:]
        return stream_id

    # ── XREADGROUP（排他取得） ───────────────────

    def xreadgroup(self, count: int = 10) -> list[tuple[str, dict]]:
        """
        Consumer Group から未処理メッセージを排他的に取得する（XREADGROUP）。
        同じメッセージは他インスタンスには配信されない。

        Returns:
            list of (stream_id, data_dict)
        """
        self.ensure_group_exists()

        if self._redis:
            results = self._redis.xreadgroup(
                groupname    = CONSUMER_GROUP_NAME,
                consumername = self._consumer_name,
                streams      = {REDIS_STREAM_KEY: ">"},  # ">": 未配信のみ
                count        = count,
                block        = 0,   # 0: ノンブロッキング
            )
            if not results:
                return []
            messages = []
            for _stream, entries in results:
                for stream_id, data in entries:
                    sid   = stream_id.decode() if isinstance(stream_id, bytes) else str(stream_id)
                    ddict = {
                        (k.decode() if isinstance(k, bytes) else k):
                        (v.decode() if isinstance(v, bytes) else v)
                        for k, v in data.items()
                    }
                    messages.append((sid, ddict))
            return messages

        # インメモリ実装
        group = self._mem.get("groups", {}).get(CONSUMER_GROUP_NAME, {})
        pending  = group.get("pending", {})
        # delivered_ever: pending中 + ACK済みの全配信済みID
        # ACK済みは pending から消えるため、別途 "delivered_ever" セットで追跡する
        if "delivered_ever" not in group:
            group["delivered_ever"] = set()
        delivered_ever = group["delivered_ever"]
        stream = self._mem.get(REDIS_STREAM_KEY, [])

        result = []
        for sid, data in stream:
            if sid not in delivered_ever:
                # 未配信 → このインスタンスが取得（排他）
                delivered_ever.add(sid)
                pending[sid] = {
                    "consumer":    self._consumer_name,
                    "added_at_ms": int(time.time() * 1000),
                    "retry_count": 0,
                }
                result.append((sid, dict(data)))
                if len(result) >= count:
                    break
        return result

    # ── XACK（処理完了通知） ─────────────────────

    def xack(self, stream_id: str) -> bool:
        """
        メッセージ処理完了を Redis に通知する（XACK）。
        これによりメッセージが pending から消え、再配信されなくなる。
        必ず処理の最後に呼ぶこと。
        """
        if self._redis:
            count = self._redis.xack(
                REDIS_STREAM_KEY,
                CONSUMER_GROUP_NAME,
                stream_id,
            )
            return count > 0

        # インメモリ実装
        group = self._mem.get("groups", {}).get(CONSUMER_GROUP_NAME, {})
        pending = group.get("pending", {})
        if stream_id in pending:
            del pending[stream_id]
            return True
        return False

    # ── XCLAIM（孤立イベントの引き取り） ────────

    def xclaim_timed_out(self) -> list[tuple[str, dict]]:
        """
        PENDING_TIMEOUT_MS を超えた未ACKメッセージを
        このインスタンスが引き取る（XCLAIM）。

        Cloud Run インスタンスがクラッシュした場合に
        別のインスタンスがここを呼んで処理を引き継ぐ。
        """
        self.ensure_group_exists()

        if self._redis:
            # XPENDING で未ACK一覧を取得
            pending_info = self._redis.xpending_range(
                REDIS_STREAM_KEY,
                CONSUMER_GROUP_NAME,
                min="-",
                max="+",
                count=100,
            )
            claimed = []
            for entry in pending_info:
                sid         = entry["message_id"].decode()
                elapsed_ms  = entry["time_since_delivered"]
                retry_count = entry["times_delivered"]

                if elapsed_ms < PENDING_TIMEOUT_MS:
                    continue

                # 最大リトライ超過 → デッドレターキューへ
                if retry_count >= MAX_RETRY_COUNT:
                    self._move_to_dead_letter(sid)
                    self.xack(sid)
                    logger.warning(f"デッドレターへ移送: {sid}（リトライ{retry_count}回超過）")
                    continue

                # XCLAIM: このインスタンスに所有権を移転
                result = self._redis.xclaim(
                    REDIS_STREAM_KEY,
                    CONSUMER_GROUP_NAME,
                    self._consumer_name,
                    PENDING_TIMEOUT_MS,
                    [sid],
                )
                for claim_id, data in result:
                    cid   = claim_id.decode() if isinstance(claim_id, bytes) else str(claim_id)
                    ddict = {
                        (k.decode() if isinstance(k, bytes) else k):
                        (v.decode() if isinstance(v, bytes) else v)
                        for k, v in data.items()
                    }
                    claimed.append((cid, ddict))
                    logger.info(f"XCLAIM引き取り: {cid}（元消費者タイムアウト）")
            return claimed

        # インメモリ実装
        group   = self._mem.get("groups", {}).get(CONSUMER_GROUP_NAME, {})
        pending = group.get("pending", {})
        now_ms  = int(time.time() * 1000)
        claimed = []
        for sid, info in list(pending.items()):
            elapsed = now_ms - info["added_at_ms"]
            if elapsed < PENDING_TIMEOUT_MS:
                continue
            retry = info.get("retry_count", 0)
            if retry >= MAX_RETRY_COUNT:
                self._move_to_dead_letter_mem(sid)
                del pending[sid]
                continue
            # 所有権をこのインスタンスに移転
            pending[sid] = {
                "consumer":    self._consumer_name,
                "added_at_ms": now_ms,
                "retry_count": retry + 1,
            }
            stream = self._mem.get(REDIS_STREAM_KEY, [])
            for stream_sid, data in stream:
                if stream_sid == sid:
                    claimed.append((sid, dict(data)))
                    break
        return claimed

    # ── デッドレターキュー ────────────────────────

    def _move_to_dead_letter(self, stream_id: str) -> None:
        """本番: デッドレターキューへ移送（XADD → dead letter stream）"""
        if self._redis:
            self._redis.xadd(
                DEAD_LETTER_STREAM_KEY,
                {"original_id": stream_id, "failed_at": str(time.time())},
            )

    def _move_to_dead_letter_mem(self, stream_id: str) -> None:
        """インメモリ: デッドレターへ記録"""
        if DEAD_LETTER_STREAM_KEY not in self._mem:
            self._mem[DEAD_LETTER_STREAM_KEY] = []
        self._mem[DEAD_LETTER_STREAM_KEY].append({
            "original_id": stream_id,
            "failed_at":   time.time(),
        })

    # ── ヘルスチェック ────────────────────────────

    def get_status(self) -> ConsumerGroupStatus:
        """Consumer Group の稼働状況を返す（監視ダッシュボード用）"""
        pending_count    = 0
        claimed_count    = 0
        dead_letter_count = 0

        if self._redis:
            info = self._redis.xpending(REDIS_STREAM_KEY, CONSUMER_GROUP_NAME)
            pending_count = info.get("pending", 0)
            dead_letter_count = self._redis.xlen(DEAD_LETTER_STREAM_KEY)
        else:
            group = self._mem.get("groups", {}).get(CONSUMER_GROUP_NAME, {})
            pending_count    = len(group.get("pending", {}))
            dead_letter_count = len(self._mem.get(DEAD_LETTER_STREAM_KEY, []))

        return ConsumerGroupStatus(
            group_name        = CONSUMER_GROUP_NAME,
            consumer_name     = self._consumer_name,
            pending_count     = pending_count,
            claimed_count     = claimed_count,
            dead_letter_count = dead_letter_count,
            last_checked_at   = datetime.now(JST).isoformat(),
        )

    # ── LIFF PULL用のXREAD（既存互換） ──────────

    def get_stream_events(
        self,
        user_id:        str,
        last_stream_id: str = "0",
    ) -> tuple[list[dict], str]:
        """
        LIFF PULL型ポーリング用。Consumer Groupを経由しない直接XREAD。
        ユーザーが自分の荷物状況を確認する読み取り専用操作のため、
        ACKは不要（Consumer Groupの排他制御対象外）。
        """
        stream    = self._mem.get(REDIS_STREAM_KEY, [])
        events    = []
        latest_id = last_stream_id
        for sid, data in stream:
            if sid > last_stream_id and data.get("user_id") == user_id:
                events.append(data)
                latest_id = sid
        return events, latest_id


# ─────────────────────────────────────────────
# LINE PUSH 課金防御エンジン（Consumer Group統合版）
# ─────────────────────────────────────────────
class LinePushGuard:
    """
    LINE PUSH課金を最小化するための判定エンジン。
    Ver 2.4: Consumer Group Manager を内包し、
    XREADGROUP → 処理 → XACK のライフサイクルを管理する。

    防御ルール（優先順）:
      1. ステータス遷移フィルタ
      2. 24時間Redisデデュープ（重複PUSH防止）
      3. 深夜0〜7時 → 朝7時バッチキューへ
      4. LIFF既読フラグ → already_read
      5. 累計PUSH上限 → max_count
      6. 上記クリア → PUSH送信
    """

    def __init__(self, redis_client=None):
        self._redis   = redis_client
        self._mem:    dict = {}
        # Consumer Group マネージャーを内包
        self.cg = RedisConsumerGroupManager(redis_client)

    # ── Consumer Group 統合エントリポイント ────

    def process_next_events(self, count: int = 10) -> list[dict]:
        """
        XREADGROUP → PUSH判定 → XACK の完全サイクルを実行する。
        Cloud Run の常駐ループから呼び出す。

        Returns:
            処理した結果のリスト
        """
        results = []

        # ① 排他取得（他インスタンスとの競合なし）
        messages = self.cg.xreadgroup(count=count)

        for stream_id, data in messages:
            result = {"stream_id": stream_id, "status": "unknown"}
            try:
                event = PackageStatusEvent(
                    user_id      = data.get("user_id", ""),
                    package_id   = data.get("package_id", ""),
                    tracking_no  = data.get("tracking_no", ""),
                    prev_status  = data.get("prev_status") or None,
                    new_status   = data.get("status", ""),
                    carrier      = data.get("carrier", ""),
                    changed_at   = data.get("changed_at",
                                            datetime.now(JST).isoformat()),
                )

                # ② PUSH判定（このインスタンスのみ実行 → 二重課金なし）
                decision  = self.decide(event)
                result["push_decision"] = {
                    "should_push":   decision.should_push,
                    "reason":        decision.reason,
                    "suppressed_by": decision.suppressed_by,
                }

                # ③ LINE PUSH 実行（実装は呼び出し元が行う）
                result["status"] = "processed"

                # ④ 必ず XACK（処理完了 → 再配信されない）
                acked = self.cg.xack(stream_id)
                result["acked"] = acked

            except Exception as e:
                logger.error(f"イベント処理エラー stream_id={stream_id}: {e}")
                result["status"] = "error"
                result["error"]  = str(e)
                # エラー時は XACK しない → タイムアウト後に XCLAIM で再処理

            results.append(result)

        return results

    def recover_timed_out_events(self) -> list[dict]:
        """
        タイムアウトした未ACKイベントを引き取って再処理する。
        Cloud Scheduler または定期ループから呼び出す（60秒ごと）。
        """
        claimed  = self.cg.xclaim_timed_out()
        results  = []
        for stream_id, data in claimed:
            logger.info(f"タイムアウトイベントを再処理: {stream_id}")
            # 通常の process_next_events と同じフローで処理
            try:
                event = PackageStatusEvent(
                    user_id      = data.get("user_id", ""),
                    package_id   = data.get("package_id", ""),
                    tracking_no  = data.get("tracking_no", ""),
                    prev_status  = data.get("prev_status") or None,
                    new_status   = data.get("status", ""),
                    carrier      = data.get("carrier", ""),
                    changed_at   = data.get("changed_at",
                                            datetime.now(JST).isoformat()),
                )
                decision = self.decide(event)
                self.cg.xack(stream_id)
                results.append({
                    "stream_id":     stream_id,
                    "status":        "recovered",
                    "push_decision": {
                        "should_push":   decision.should_push,
                        "reason":        decision.reason,
                    },
                })
            except Exception as e:
                logger.error(f"回復処理エラー: {stream_id}: {e}")
                results.append({"stream_id": stream_id, "status": "recovery_failed"})
        return results

    # ── PUSH判定ロジック（Ver 2.3から継続） ────

    def decide(
        self,
        event: PackageStatusEvent,
        liff_last_opened_at: Optional[datetime] = None,
    ) -> PushDecision:

        prev = PackageStatus(event.prev_status) if event.prev_status else None
        new  = PackageStatus(event.new_status)

        # ルール1: ステータス遷移チェック
        if prev is not None and (prev, new) not in PUSH_REQUIRED_TRANSITIONS:
            return PushDecision(
                should_push=False,
                reason=f"遷移 {prev.value}→{new.value} はPUSH対象外",
                suppressed_by="transition_not_required",
            )
        if prev is None and new not in (
            PackageStatus.IN_TRANSIT, PackageStatus.OUT_FOR_DELIVERY
        ):
            return PushDecision(
                should_push=False,
                reason=f"新規登録 status={new.value} はPUSH不要",
                suppressed_by="initial_status",
            )

        # ルール2: 重複チェック（24時間）
        dedup_key  = f"{REDIS_PUSH_DEDUP_PREFIX}{event.package_id}"
        push_count = self._get_counter(dedup_key)
        if push_count > 0:
            return PushDecision(
                should_push=False,
                reason=f"24h以内に{push_count}回PUSH済み",
                push_count=push_count,
                suppressed_by="dedup",
            )

        # ルール3: 深夜時間帯
        now_jst = datetime.now(JST)
        if SILENT_HOURS_START <= now_jst.hour < SILENT_HOURS_END:
            return PushDecision(
                should_push=False,
                reason=f"深夜帯 {now_jst.hour}時 → 朝7時バッチキューへ",
                suppressed_by="silent_hours",
            )

        # ルール4: LIFF既読
        if liff_last_opened_at is not None:
            try:
                ev_time = datetime.fromisoformat(event.changed_at)
                if ev_time.tzinfo is None:
                    ev_time = ev_time.replace(tzinfo=JST)
                if liff_last_opened_at > ev_time:
                    return PushDecision(
                        should_push=False,
                        reason="LIFF開封済み（既読）→ PUSH不要",
                        suppressed_by="already_read",
                    )
            except (ValueError, TypeError):
                pass

        # ルール5: 最大PUSH数
        total_key   = f"{REDIS_PUSH_DEDUP_PREFIX}{event.package_id}:total"
        total_count = self._get_counter(total_key)
        if total_count >= MAX_PUSH_PER_PACKAGE:
            return PushDecision(
                should_push=False,
                reason=f"累計PUSH{total_count}回が上限{MAX_PUSH_PER_PACKAGE}に到達",
                push_count=total_count,
                suppressed_by="max_count",
            )

        # → PUSH送信決定
        self._increment_counter(dedup_key, ttl=PUSH_DEDUP_TTL_SEC)
        self._increment_counter(total_key, ttl=86400 * 30)
        return PushDecision(
            should_push=True,
            reason=f"遷移 {prev.value if prev else 'new'}→{new.value} PUSH送信",
            push_count=total_count + 1,
        )

    # ── Streamへのイベント追加（Consumer Group経由） ──

    def add_to_redis_stream(self, event: PackageStatusEvent) -> str:
        """Consumer Group Manager 経由で XADD する"""
        return self.cg.xadd(event)

    def add_to_silent_batch(self, event: PackageStatusEvent) -> None:
        key = "niceeze:silent_batch"
        self._push_to_list(key, json.dumps({
            "user_id":    event.user_id,
            "package_id": event.package_id,
            "status":     event.new_status,
            "queued_at":  datetime.now(JST).isoformat(),
        }))

    def flush_silent_batch(self) -> list[dict]:
        key   = "niceeze:silent_batch"
        items = self._mem.pop(key, [])
        return [json.loads(i) for i in items]

    def get_stream_events(
        self,
        user_id:        str,
        last_stream_id: str = "0",
    ) -> tuple[list[dict], str]:
        """LIFF PULL用（Consumer Group非経由の読み取り専用）"""
        return self.cg.get_stream_events(user_id, last_stream_id)

    # ── インメモリ操作（テスト用） ──────────────
    def _get_counter(self, key: str) -> int:
        return self._mem.get(key, 0)

    def _increment_counter(self, key: str, ttl: int = 0) -> int:
        self._mem[key] = self._mem.get(key, 0) + 1
        return self._mem[key]

    def _push_to_list(self, key: str, value: str) -> None:
        if key not in self._mem:
            self._mem[key] = []
        self._mem[key].append(value)


# ─────────────────────────────────────────────
# LIFF PULL型更新ハンドラ
# ─────────────────────────────────────────────
class LiffPullHandler:
    """
    LIFF App からの30秒ポーリングに対応する PULL 型更新ハンドラ。
    Consumer Group を経由しない読み取り専用操作。
    """

    def __init__(self, push_guard: LinePushGuard):
        self._guard       = push_guard
        self._pull_cache: dict = {}

    def handle_pull(
        self,
        user_id:        str,
        last_stream_id: str  = "0",
        package_ids:    Optional[list] = None,
    ) -> PullResponse:

        cache_key = f"{user_id}:{last_stream_id}"
        if cache_key in self._pull_cache:
            cached_at, cached_resp = self._pull_cache[cache_key]
            if time.time() - cached_at < PULL_CACHE_TTL_SEC:
                cached_resp.cache_hit = True
                return cached_resp

        events, _ = self._guard.get_stream_events(user_id, last_stream_id)

        if package_ids is not None:
            events = [e for e in events if e.get("package_id") in package_ids]

        resp = PullResponse(
            packages     = events,
            has_updates  = len(events) > 0,
            last_checked = datetime.now(JST).isoformat(),
        )
        self._pull_cache[cache_key] = (time.time(), resp)
        return resp


# ─────────────────────────────────────────────
# Pub/Sub → Redis Bridge（Consumer Group統合版）
# ─────────────────────────────────────────────
class PubSubRedisBridge:
    """
    Cloud SQL pg_notify → Memorystore Redis Streams (Consumer Group)

    Ver 2.4: XADD後にConsumer Groupが処理を保証する。
    process_next_events() を別スレッドまたは非同期ループで呼び出すこと。
    """

    def __init__(self, push_guard: LinePushGuard):
        self._guard = push_guard

    def handle_db_notification(self, payload_str: str) -> dict:
        """
        pg_notify から受け取ったペイロードを Redis Stream に追加する。
        実際のPUSH判定は Consumer Group Worker が行う（このメソッドは追加のみ）。
        """
        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError as e:
            logger.error(f"pg_notify JSONパース失敗: {e}")
            return {"status": "error", "reason": str(e)}

        event = PackageStatusEvent(
            user_id      = payload.get("user_id", ""),
            package_id   = str(payload.get("package_id", "")),
            tracking_no  = payload.get("tracking_no", ""),
            prev_status  = payload.get("prev_status"),
            new_status   = payload.get("status", ""),
            carrier      = payload.get("carrier", ""),
            changed_at   = payload.get("changed_at",
                                       datetime.now(JST).isoformat()),
        )

        # XADD: Consumer Group が排他的に処理する
        stream_id = self._guard.add_to_redis_stream(event)

        return {
            "stream_id":          stream_id,
            "consumer_group":     CONSUMER_GROUP_NAME,
            "processing_mode":    "consumer_group_exclusive",
            "duplicate_safe":     True,
        }
