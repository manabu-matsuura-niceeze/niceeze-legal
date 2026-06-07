#!/usr/bin/env python3
"""データ保存期間管理バッチ

GitHub Actions cron 毎日 0:00 JST で実行。
  UTC 15:00 = JST 0:00

使用例:
    python scripts/data_retention.py --dry-run   # ドライラン（削除対象件数のみ表示）
    python scripts/data_retention.py             # 実削除実行

環境変数:
    DB_URL: 接続先データベースURL（未設定時は SQLite インメモリ）
            例) postgresql://user:pass@host/dbname (Cloud SQL)
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

# ---------------------------------------------------------------------------
# 保持期間ルール定義
# ---------------------------------------------------------------------------
RETENTION_RULES: Dict[str, Dict[str, Any]] = {
    "resident": {"days": 3 * 365, "table": "residents"},           # 退会後3年
    "delivery_history": {"days": 2 * 365, "table": "delivery_records"},  # 最終利用から2年
    "ai_support_log": {"days": 90, "table": "support_logs"},       # 90日
    "access_log": {"days": 180, "table": "access_logs"},           # 180日
}

# ---------------------------------------------------------------------------
# ログ出力ヘルパー
# ---------------------------------------------------------------------------

def _log(level: str, message: str, **kwargs: Any) -> None:
    """JSON 形式で標準出力にログを出力する"""
    entry = {
        "level": level,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "message": message,
        **kwargs,
    }
    print(json.dumps(entry, ensure_ascii=False), flush=True)


# ---------------------------------------------------------------------------
# DataRetentionBatch
# ---------------------------------------------------------------------------

class DataRetentionBatch:
    """データ保持期間管理バッチ

    Args:
        db_url: データベース URL（未指定時は環境変数 DB_URL、それも未設定なら SQLite インメモリ）
        conn: テスト用の既存 sqlite3 接続（指定時は db_url を無視）
    """

    def __init__(self, db_url: str = "", conn: Any = None) -> None:
        self._external_conn = conn
        if conn is not None:
            self._db_url = ""
        else:
            self._db_url = db_url or os.environ.get("DB_URL", "")

    def _get_connection(self) -> sqlite3.Connection:
        """DB 接続を返す（テスト用外部接続優先）"""
        if self._external_conn is not None:
            return self._external_conn  # type: ignore[return-value]

        if self._db_url and not self._db_url.startswith("sqlite"):
            # 本番: Cloud SQL（psycopg2 等）
            # NOTE: 本番環境では google-cloud-sql-connector または psycopg2 を使用
            raise NotImplementedError(
                f"Cloud SQL 接続は本番環境で psycopg2 を使用してください: {self._db_url}"
            )

        # SQLite（テスト・ローカル開発用）
        db_path = self._db_url.replace("sqlite:///", "") if self._db_url else ":memory:"
        return sqlite3.connect(db_path)

    @staticmethod
    def check_dry_run() -> bool:
        """コマンドライン引数から --dry-run フラグを確認する"""
        return "--dry-run" in sys.argv

    def run(self, dry_run: bool = True) -> Dict[str, Any]:
        """保持期間超過レコードの削除（または件数カウント）を実行する

        Args:
            dry_run: True の場合は削除対象件数のみカウント（実削除しない）

        Returns:
            各テーブルの削除件数を含む結果辞書
        """
        mode = "dry_run" if dry_run else "execute"
        _log("INFO", "データ保持期間バッチ開始", mode=mode)

        conn = self._get_connection()
        result: Dict[str, Any] = {"mode": mode, "tables": {}}

        try:
            for rule_name, rule in RETENTION_RULES.items():
                table = rule["table"]
                days = rule["days"]
                cutoff = datetime.now(timezone.utc) - timedelta(days=days)
                cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

                try:
                    # テーブルが存在するか確認
                    conn.execute(f"SELECT 1 FROM {table} LIMIT 1")  # nosec B608
                except sqlite3.OperationalError:
                    _log("WARN", f"テーブルが存在しません: {table}", rule=rule_name)
                    result["tables"][rule_name] = {"table": table, "count": 0, "skipped": True}
                    continue

                # 削除対象件数を取得
                cursor = conn.execute(  # nosec B608
                    f"SELECT COUNT(*) FROM {table} WHERE deleted_at <= ?",
                    (cutoff_str,),
                )
                count = cursor.fetchone()[0]

                if dry_run:
                    _log(
                        "INFO",
                        f"[DRY RUN] 削除対象",
                        rule=rule_name,
                        table=table,
                        retention_days=days,
                        cutoff=cutoff_str,
                        target_count=count,
                    )
                else:
                    conn.execute(  # nosec B608
                        f"DELETE FROM {table} WHERE deleted_at <= ?",
                        (cutoff_str,),
                    )
                    conn.commit()
                    _log(
                        "INFO",
                        f"削除完了",
                        rule=rule_name,
                        table=table,
                        retention_days=days,
                        cutoff=cutoff_str,
                        deleted_count=count,
                    )

                result["tables"][rule_name] = {
                    "table": table,
                    "retention_days": days,
                    "cutoff": cutoff_str,
                    "count": count,
                }

        finally:
            # 外部から渡された接続は閉じない
            if self._external_conn is None:
                conn.close()

        _log("INFO", "データ保持期間バッチ完了", result=result)
        return result


# ---------------------------------------------------------------------------
# エントリーポイント
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="データ保存期間管理バッチ")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="ドライラン: 削除対象件数のみカウント（実削除しない）",
    )
    args = parser.parse_args()

    batch = DataRetentionBatch()
    batch.run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
