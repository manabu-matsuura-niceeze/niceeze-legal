"""APIアクセスログ共通ミドルウェア

全APIエンドポイントのアクセスを記録し、180日間保持する。
TASK-6: アクセスログ保持期間管理
"""

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Any, List, Optional

ACCESS_LOG_RETENTION_DAYS = 180


@dataclass
class AccessLogEntry:
    """アクセスログエントリ

    Attributes:
        log_id: UUID の先頭8文字
        operator_id: リクエストヘッダー X-Operator-ID、未設定は 'anonymous'
        timestamp_utc: ISO 8601 形式の UTC タイムスタンプ
        ip_address: X-Forwarded-For または RemoteAddr
        endpoint: リクエストパス
        method: HTTP メソッド (GET/POST 等)
        response_code: HTTP レスポンスコード
    """

    log_id: str
    operator_id: str
    timestamp_utc: str
    ip_address: str
    endpoint: str
    method: str
    response_code: int

    def to_dict(self) -> dict:
        return asdict(self)


def _extract_operator_id(headers: dict) -> str:
    """リクエストヘッダーから X-Operator-ID を抽出する。未設定は 'anonymous'"""
    return headers.get("X-Operator-ID", headers.get("x-operator-id", "anonymous"))


def _extract_ip(headers: dict, remote_addr: str = "") -> str:
    """X-Forwarded-For または RemoteAddr から IP アドレスを取得する"""
    forwarded = headers.get("X-Forwarded-For", headers.get("x-forwarded-for", ""))
    if forwarded:
        # 最初の IP を使用（プロキシチェーンの場合）
        return forwarded.split(",")[0].strip()
    return remote_addr or "unknown"


class AccessLogMiddleware:
    """APIアクセスログミドルウェア

    インメモリでアクセスログを保持する。
    本番環境では DB への永続化を推奨（Cloud SQL / BigQuery）。
    """

    def __init__(self) -> None:
        self._logs: List[AccessLogEntry] = []

    def record(
        self,
        method: str,
        endpoint: str,
        response_code: int,
        headers: Optional[dict] = None,
        remote_addr: str = "",
        timestamp_utc: Optional[datetime] = None,
    ) -> AccessLogEntry:
        """アクセスログエントリを記録して返す

        Args:
            method: HTTP メソッド
            endpoint: リクエストパス
            response_code: HTTP レスポンスコード
            headers: リクエストヘッダー辞書（X-Operator-ID, X-Forwarded-For を含む）
            remote_addr: リモートアドレス（ヘッダーに X-Forwarded-For がない場合に使用）
            timestamp_utc: タイムスタンプ（指定なしは現在時刻）
        """
        if headers is None:
            headers = {}

        ts = timestamp_utc or datetime.now(timezone.utc)
        entry = AccessLogEntry(
            log_id=str(uuid.uuid4())[:8],
            operator_id=_extract_operator_id(headers),
            timestamp_utc=ts.isoformat(),
            ip_address=_extract_ip(headers, remote_addr),
            endpoint=endpoint,
            method=method.upper(),
            response_code=response_code,
        )
        self._logs.append(entry)
        return entry

    def get_logs(self, since_days: int = ACCESS_LOG_RETENTION_DAYS) -> List[AccessLogEntry]:
        """指定日数以内のログを返す

        Args:
            since_days: 何日前までのログを取得するか（デフォルト180日）
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
        result = []
        for entry in self._logs:
            try:
                ts = datetime.fromisoformat(entry.timestamp_utc)
                if ts >= cutoff:
                    result.append(entry)
            except ValueError:
                # パース不可のエントリはスキップ
                pass
        return result

    def purge_old_logs(self) -> int:
        """保持期間（180日）を超えたログを削除する

        Returns:
            削除したエントリ数
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=ACCESS_LOG_RETENTION_DAYS)
        before = len(self._logs)
        kept = []
        for entry in self._logs:
            try:
                ts = datetime.fromisoformat(entry.timestamp_utc)
                if ts >= cutoff:
                    kept.append(entry)
            except ValueError:
                kept.append(entry)  # パース不可は保持
        self._logs = kept
        return before - len(self._logs)
