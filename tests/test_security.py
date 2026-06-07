"""セキュリティモジュールテスト (TASK-6)

25件以上のテストケース:
- PIIEncryptor: encrypt/decrypt往復、encrypt_record/decrypt_record、mock_mode
- DataRetentionBatch: dry_run=True で件数カウント、RETENTION_RULESの確認
- AccessLogMiddleware: record / get_logs / purge_old_logs
- Anonymizer: 各パターンのマスキング、mask_record
"""

import sqlite3
import sys
import os
from datetime import datetime, timezone, timedelta

import pytest

# src ディレクトリをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.security import (
    PIIEncryptor,
    PII_FIELDS,
    AccessLogMiddleware,
    AccessLogEntry,
    ACCESS_LOG_RETENTION_DAYS,
    Anonymizer,
    MASK_PATTERNS,
    MASK_REPLACEMENT,
)
from src.security.pii_encryptor import _derive_key, _xor_ctr

# scripts ディレクトリをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from data_retention import DataRetentionBatch, RETENTION_RULES


# =============================================================================
# PIIEncryptor テスト
# =============================================================================

class TestPIIEncryptorMockMode:
    """mock_mode=True (キー未設定) のテスト"""

    def test_mock_mode_enabled_without_key(self, monkeypatch):
        monkeypatch.delenv("PII_SECRET_KEY", raising=False)
        enc = PIIEncryptor()
        assert enc.mock_mode is True

    def test_mock_mode_encrypt_returns_string(self, monkeypatch):
        monkeypatch.delenv("PII_SECRET_KEY", raising=False)
        enc = PIIEncryptor()
        result = enc.encrypt("テスト太郎")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_mock_mode_roundtrip(self, monkeypatch):
        monkeypatch.delenv("PII_SECRET_KEY", raising=False)
        enc = PIIEncryptor()
        original = "テスト太郎"
        assert enc.decrypt(enc.encrypt(original)) == original

    def test_mock_mode_encrypt_record(self, monkeypatch):
        monkeypatch.delenv("PII_SECRET_KEY", raising=False)
        enc = PIIEncryptor()
        record = {"resident_name": "山田太郎", "phone_number": "090-1234-5678", "other": "keep"}
        encrypted = enc.encrypt_record(record)
        assert encrypted["resident_name"] != "山田太郎"
        assert encrypted["phone_number"] != "090-1234-5678"
        assert encrypted["other"] == "keep"

    def test_mock_mode_decrypt_record(self, monkeypatch):
        monkeypatch.delenv("PII_SECRET_KEY", raising=False)
        enc = PIIEncryptor()
        record = {"resident_name": "山田太郎", "phone_number": "090-1234-5678", "email_address": "t@example.com"}
        decrypted = enc.decrypt_record(enc.encrypt_record(record))
        assert decrypted["resident_name"] == "山田太郎"
        assert decrypted["phone_number"] == "090-1234-5678"
        assert decrypted["email_address"] == "t@example.com"


class TestPIIEncryptorWithKey:
    """secret_key 指定時のテスト"""

    def test_not_mock_mode_with_key(self):
        enc = PIIEncryptor(secret_key="test_secret_key_32chars_padding!!")
        assert enc.mock_mode is False

    def test_encrypt_returns_string(self):
        enc = PIIEncryptor(secret_key="my_secret_key")
        result = enc.encrypt("hello world")
        assert isinstance(result, str)

    def test_encrypt_decrypt_roundtrip(self):
        enc = PIIEncryptor(secret_key="my_secret_key")
        plaintext = "山田太郎"
        assert enc.decrypt(enc.encrypt(plaintext)) == plaintext

    def test_encrypt_different_each_time(self):
        enc = PIIEncryptor(secret_key="my_secret_key")
        c1 = enc.encrypt("same text")
        c2 = enc.encrypt("same text")
        # 乱数ソルト/ノンスにより毎回異なるはず
        assert c1 != c2

    def test_wrong_key_raises(self):
        enc1 = PIIEncryptor(secret_key="key_one")
        enc2 = PIIEncryptor(secret_key="key_two")
        ciphertext = enc1.encrypt("secret data")
        with pytest.raises(ValueError):
            enc2.decrypt(ciphertext)

    def test_encrypt_record_with_key(self):
        enc = PIIEncryptor(secret_key="test_key")
        record = {
            "resident_name": "佐藤花子",
            "phone_number": "03-1234-5678",
            "email_address": "hanako@example.com",
            "unrelated": "data",
        }
        encrypted = enc.encrypt_record(record)
        assert encrypted["resident_name"] != "佐藤花子"
        assert encrypted["unrelated"] == "data"

    def test_decrypt_record_roundtrip_with_key(self):
        enc = PIIEncryptor(secret_key="test_key")
        record = {
            "resident_name": "鈴木一郎",
            "phone_number": "080-9999-0000",
            "email_address": "ichiro@example.com",
        }
        assert enc.decrypt_record(enc.encrypt_record(record)) == record

    def test_pii_fields_constant(self):
        assert "resident_name" in PII_FIELDS
        assert "phone_number" in PII_FIELDS
        assert "email_address" in PII_FIELDS

    def test_none_field_not_encrypted(self):
        enc = PIIEncryptor(secret_key="test_key")
        record = {"resident_name": None, "other": "value"}
        result = enc.encrypt_record(record)
        assert result["resident_name"] is None

    def test_env_key(self, monkeypatch):
        monkeypatch.setenv("PII_SECRET_KEY", "env_secret_key")
        enc = PIIEncryptor()
        assert enc.mock_mode is False
        plaintext = "env key test"
        assert enc.decrypt(enc.encrypt(plaintext)) == plaintext


# =============================================================================
# DataRetentionBatch テスト
# =============================================================================

def _make_test_db():
    """テスト用 SQLite インメモリ DB を作成して返す"""
    conn = sqlite3.connect(":memory:")
    for rule in RETENTION_RULES.values():
        table = rule["table"]
        conn.execute(
            f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, deleted_at TEXT)"
        )
    conn.commit()
    return conn


class TestDataRetentionBatch:

    def test_retention_rules_keys(self):
        assert "resident" in RETENTION_RULES
        assert "delivery_history" in RETENTION_RULES
        assert "ai_support_log" in RETENTION_RULES
        assert "access_log" in RETENTION_RULES

    def test_retention_rules_days(self):
        assert RETENTION_RULES["resident"]["days"] == 3 * 365
        assert RETENTION_RULES["delivery_history"]["days"] == 2 * 365
        assert RETENTION_RULES["ai_support_log"]["days"] == 90
        assert RETENTION_RULES["access_log"]["days"] == 180

    def test_retention_rules_tables(self):
        assert RETENTION_RULES["resident"]["table"] == "residents"
        assert RETENTION_RULES["ai_support_log"]["table"] == "support_logs"

    def test_dry_run_counts_without_deleting(self):
        conn = _make_test_db()
        # ai_support_log は90日保持 → 100日前のデータは期限切れ
        old_date = (datetime.now(timezone.utc) - timedelta(days=100)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("INSERT INTO support_logs (deleted_at) VALUES (?)", (old_date,))
        conn.execute("INSERT INTO support_logs (deleted_at) VALUES (?)", (old_date,))
        conn.commit()

        batch = DataRetentionBatch(conn=conn)
        result = batch.run(dry_run=True)

        assert result["mode"] == "dry_run"
        # 件数は2件のはず
        assert result["tables"]["ai_support_log"]["count"] == 2
        # 実際には削除されていない
        cursor = conn.execute("SELECT COUNT(*) FROM support_logs")
        assert cursor.fetchone()[0] == 2

    def test_execute_deletes_records(self):
        conn = _make_test_db()
        # ai_support_log は90日保持 → 100日前のデータは期限切れ
        old_date = (datetime.now(timezone.utc) - timedelta(days=100)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("INSERT INTO support_logs (deleted_at) VALUES (?)", (old_date,))
        conn.commit()

        batch = DataRetentionBatch(conn=conn)
        result = batch.run(dry_run=False)

        assert result["mode"] == "execute"
        cursor = conn.execute("SELECT COUNT(*) FROM support_logs")
        assert cursor.fetchone()[0] == 0

    def test_recent_records_not_deleted(self):
        conn = _make_test_db()
        recent_date = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("INSERT INTO access_logs (deleted_at) VALUES (?)", (recent_date,))
        conn.commit()

        batch = DataRetentionBatch(conn=conn)
        batch.run(dry_run=False)

        cursor = conn.execute("SELECT COUNT(*) FROM access_logs")
        assert cursor.fetchone()[0] == 1


# =============================================================================
# AccessLogMiddleware テスト
# =============================================================================

class TestAccessLogMiddleware:

    def test_record_returns_entry(self):
        mid = AccessLogMiddleware()
        entry = mid.record("GET", "/api/v1/test", 200)
        assert isinstance(entry, AccessLogEntry)

    def test_record_operator_id_from_header(self):
        mid = AccessLogMiddleware()
        entry = mid.record("POST", "/api/v1/submit", 201, headers={"X-Operator-ID": "op123"})
        assert entry.operator_id == "op123"

    def test_record_anonymous_when_no_header(self):
        mid = AccessLogMiddleware()
        entry = mid.record("GET", "/api/v1/test", 200, headers={})
        assert entry.operator_id == "anonymous"

    def test_record_ip_from_forwarded_for(self):
        mid = AccessLogMiddleware()
        entry = mid.record("GET", "/test", 200, headers={"X-Forwarded-For": "192.168.1.1, 10.0.0.1"})
        assert entry.ip_address == "192.168.1.1"

    def test_record_ip_from_remote_addr(self):
        mid = AccessLogMiddleware()
        entry = mid.record("GET", "/test", 200, remote_addr="203.0.113.5")
        assert entry.ip_address == "203.0.113.5"

    def test_get_logs_returns_recent(self):
        mid = AccessLogMiddleware()
        mid.record("GET", "/test", 200)
        logs = mid.get_logs(since_days=1)
        assert len(logs) == 1

    def test_get_logs_excludes_old(self):
        mid = AccessLogMiddleware()
        old_ts = datetime.now(timezone.utc) - timedelta(days=200)
        mid.record("GET", "/old", 200, timestamp_utc=old_ts)
        mid.record("GET", "/new", 200)
        logs = mid.get_logs(since_days=180)
        assert len(logs) == 1
        assert logs[0].endpoint == "/new"

    def test_purge_old_logs_removes_expired(self):
        mid = AccessLogMiddleware()
        old_ts = datetime.now(timezone.utc) - timedelta(days=200)
        mid.record("GET", "/old", 200, timestamp_utc=old_ts)
        mid.record("GET", "/new", 200)
        deleted = mid.purge_old_logs()
        assert deleted == 1
        assert len(mid._logs) == 1

    def test_purge_old_logs_keeps_within_retention(self):
        mid = AccessLogMiddleware()
        mid.record("GET", "/recent1", 200)
        mid.record("GET", "/recent2", 200)
        deleted = mid.purge_old_logs()
        assert deleted == 0
        assert len(mid._logs) == 2

    def test_access_log_retention_days_constant(self):
        assert ACCESS_LOG_RETENTION_DAYS == 180

    def test_log_id_is_8_chars(self):
        mid = AccessLogMiddleware()
        entry = mid.record("GET", "/test", 200)
        assert len(entry.log_id) == 8

    def test_to_dict(self):
        mid = AccessLogMiddleware()
        entry = mid.record("DELETE", "/api/v1/item/1", 204)
        d = entry.to_dict()
        assert d["method"] == "DELETE"
        assert d["response_code"] == 204


# =============================================================================
# Anonymizer テスト
# =============================================================================

class TestAnonymizer:

    def test_mask_phone_hyphen(self):
        anon = Anonymizer()
        result = anon.mask("電話番号は090-1234-5678です")
        assert "[MASKED]" in result
        assert "090-1234-5678" not in result

    def test_mask_email(self):
        anon = Anonymizer()
        result = anon.mask("連絡先: user@example.com まで")
        assert "[MASKED]" in result
        assert "user@example.com" not in result

    def test_mask_qr_token(self):
        anon = Anonymizer()
        token = "abcdefghijklmnopqrstuvwxyz123456"  # 32文字
        result = anon.mask(f"トークン: {token}")
        assert "[MASKED]" in result
        assert token not in result

    def test_mask_credit_card(self):
        anon = Anonymizer()
        result = anon.mask("カード番号: 1234-5678-9012-3456")
        assert "[MASKED]" in result
        assert "1234-5678-9012-3456" not in result

    def test_mask_credit_card_no_separator(self):
        anon = Anonymizer()
        result = anon.mask("カード: 1234567890123456")
        assert "[MASKED]" in result

    def test_mask_empty_string(self):
        anon = Anonymizer()
        assert anon.mask("") == ""

    def test_mask_no_pii(self):
        anon = Anonymizer()
        text = "このテキストにはPIIが含まれていません"
        assert anon.mask(text) == text

    def test_mask_record_masks_specified_fields(self):
        anon = Anonymizer()
        record = {
            "message": "電話: 03-1234-5678",
            "other": "clean text",
        }
        result = anon.mask_record(record, fields=["message"])
        assert "[MASKED]" in result["message"]
        assert result["other"] == "clean text"

    def test_mask_record_skips_non_string(self):
        anon = Anonymizer()
        record = {"count": 42, "name": "test@example.com"}
        result = anon.mask_record(record, fields=["count", "name"])
        assert result["count"] == 42
        assert "[MASKED]" in result["name"]

    def test_mask_record_does_not_modify_original(self):
        anon = Anonymizer()
        original = {"msg": "090-0000-1111"}
        anon.mask_record(original, fields=["msg"])
        assert original["msg"] == "090-0000-1111"

    def test_mask_patterns_constant(self):
        assert "phone" in MASK_PATTERNS
        assert "email" in MASK_PATTERNS
        assert "qr_token" in MASK_PATTERNS
        assert "credit_card" in MASK_PATTERNS
        assert "name_ja" in MASK_PATTERNS

    def test_mask_replacement_constant(self):
        assert MASK_REPLACEMENT == "[MASKED]"

    def test_custom_patterns(self):
        anon = Anonymizer(patterns={"custom": r"\d{5}"})
        result = anon.mask("postal code: 12345")
        assert "[MASKED]" in result
        # デフォルトパターンは使われない
        assert "user@example.com" in anon.mask("user@example.com")
