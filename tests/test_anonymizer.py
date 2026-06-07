"""
TASK-PP5: src/common/anonymizer.py および scripts/data_retention.py のテスト
"""

import hashlib
import sqlite3
import sys
import os
from datetime import datetime, timezone, timedelta

import pytest

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.common.anonymizer import (
    ANON_NAME,
    ANON_EMAIL,
    ANON_QR_PREFIX,
    anonymize_name,
    anonymize_email,
    anonymize_phone,
    anonymize_address,
    anonymize_qr_token,
    anonymize_record,
    is_anonymized,
)
from scripts.data_retention import DataRetentionBatch, RETENTION_RULES


# ---------------------------------------------------------------------------
# anonymize_name
# ---------------------------------------------------------------------------

class TestAnonymizeName:
    def test_japanese_name(self):
        assert anonymize_name("山田太郎") == ANON_NAME

    def test_english_name(self):
        assert anonymize_name("John Doe") == ANON_NAME

    def test_empty_string(self):
        assert anonymize_name("") == ANON_NAME

    def test_single_char(self):
        assert anonymize_name("A") == ANON_NAME

    def test_returns_constant(self):
        assert anonymize_name("佐藤花子") == "***"


# ---------------------------------------------------------------------------
# anonymize_email
# ---------------------------------------------------------------------------

class TestAnonymizeEmail:
    def test_standard_email(self):
        assert anonymize_email("user@example.com") == ANON_EMAIL

    def test_subdomain_email(self):
        assert anonymize_email("admin@mail.company.co.jp") == ANON_EMAIL

    def test_empty_string(self):
        assert anonymize_email("") == ANON_EMAIL

    def test_returns_constant(self):
        assert anonymize_email("foo@bar.baz") == "***@***.***"

    def test_different_inputs_same_output(self):
        assert anonymize_email("a@b.com") == anonymize_email("x@y.org")


# ---------------------------------------------------------------------------
# anonymize_phone
# ---------------------------------------------------------------------------

class TestAnonymizePhone:
    def test_standard_japanese_phone(self):
        result = anonymize_phone("090-1234-5678")
        assert result == "****-****-5678"

    def test_last4_preserved(self):
        result = anonymize_phone("03-9999-1111")
        assert result.endswith("1111")

    def test_format_prefix(self):
        result = anonymize_phone("080-0000-9999")
        assert result.startswith("****-****-")

    def test_no_hyphens(self):
        result = anonymize_phone("09012345678")
        assert result == "****-****-5678"

    def test_short_number_fallback(self):
        # 4桁未満の場合はゼロパディング
        result = anonymize_phone("123")
        assert result == "****-****-1230"

    def test_exactly_4_digits(self):
        result = anonymize_phone("1234")
        assert result == "****-****-1234"

    def test_international_format(self):
        result = anonymize_phone("+81-90-1234-5678")
        assert result.endswith("5678")


# ---------------------------------------------------------------------------
# anonymize_address
# ---------------------------------------------------------------------------

class TestAnonymizeAddress:
    def test_tokyo_to(self):
        assert anonymize_address("東京都新宿区1-1") == "東京都"

    def test_osaka_fu(self):
        assert anonymize_address("大阪府大阪市北区梅田1-1") == "大阪府"

    def test_kyoto_fu(self):
        assert anonymize_address("京都府京都市中京区") == "京都府"

    def test_hokkaido_do(self):
        assert anonymize_address("北海道札幌市中央区北1条西2丁目") == "北海道"

    def test_kanagawa_ken(self):
        assert anonymize_address("神奈川県横浜市中区山下町") == "神奈川県"

    def test_no_match_returns_stars(self):
        assert anonymize_address("unknown") == "***"

    def test_empty_string_returns_stars(self):
        assert anonymize_address("") == "***"

    def test_only_prefecture(self):
        assert anonymize_address("愛知県") == "愛知県"


# ---------------------------------------------------------------------------
# anonymize_qr_token
# ---------------------------------------------------------------------------

class TestAnonymizeQrToken:
    def test_prefix(self):
        result = anonymize_qr_token("TOKEN-001")
        assert result.startswith(ANON_QR_PREFIX)

    def test_hash_length(self):
        result = anonymize_qr_token("TOKEN-001")
        # ANON_QR_PREFIX + 12文字
        assert len(result) == len(ANON_QR_PREFIX) + 12

    def test_deterministic(self):
        token = "my-secret-token"
        assert anonymize_qr_token(token) == anonymize_qr_token(token)

    def test_different_tokens_different_hashes(self):
        assert anonymize_qr_token("token-A") != anonymize_qr_token("token-B")

    def test_hash_is_sha256_prefix(self):
        token = "test-token"
        expected_hash = hashlib.sha256(token.encode()).hexdigest()[:12]
        assert anonymize_qr_token(token) == ANON_QR_PREFIX + expected_hash

    def test_empty_token(self):
        result = anonymize_qr_token("")
        assert result.startswith(ANON_QR_PREFIX)
        assert len(result) == len(ANON_QR_PREFIX) + 12


# ---------------------------------------------------------------------------
# anonymize_record
# ---------------------------------------------------------------------------

class TestAnonymizeRecord:
    def _sample_record(self):
        return {
            "resident_name": "田中次郎",
            "phone_number": "090-1111-2222",
            "email_address": "tanaka@example.com",
            "address": "埼玉県さいたま市大宮区",
            "qr_token": "QR-TOKEN-XYZ",
            "tracking_number": "TRACK-001",
            "country_code": "JP",
            "some_other_field": "value",
        }

    def test_default_name_anonymized(self):
        result = anonymize_record(self._sample_record())
        assert result["resident_name"] == ANON_NAME

    def test_default_email_anonymized(self):
        result = anonymize_record(self._sample_record())
        assert result["email_address"] == ANON_EMAIL

    def test_default_phone_anonymized(self):
        result = anonymize_record(self._sample_record())
        assert result["phone_number"].endswith("2222")

    def test_default_address_anonymized(self):
        result = anonymize_record(self._sample_record())
        assert result["address"] == "埼玉県"

    def test_default_qr_token_anonymized(self):
        result = anonymize_record(self._sample_record())
        assert result["qr_token"].startswith(ANON_QR_PREFIX)

    def test_default_tracking_number_deleted(self):
        result = anonymize_record(self._sample_record())
        assert "tracking_number" not in result

    def test_country_code_preserved(self):
        result = anonymize_record(self._sample_record())
        assert result["country_code"] == "JP"

    def test_unspecified_field_preserved(self):
        result = anonymize_record(self._sample_record())
        assert result["some_other_field"] == "value"

    def test_custom_config(self):
        record = {"username": "Alice", "score": 100}
        config = {"username": "name"}
        result = anonymize_record(record, fields_config=config)
        assert result["username"] == ANON_NAME
        assert result["score"] == 100

    def test_custom_config_delete(self):
        record = {"secret": "abc123", "public": "visible"}
        config = {"secret": "delete"}
        result = anonymize_record(record, fields_config=config)
        assert "secret" not in result
        assert result["public"] == "visible"

    def test_country_code_always_preserved_with_custom_config(self):
        record = {"country_code": "US", "name": "Bob"}
        config = {"name": "name", "country_code": "delete"}
        result = anonymize_record(record, fields_config=config)
        # country_code は常に保持
        assert result["country_code"] == "US"


# ---------------------------------------------------------------------------
# is_anonymized
# ---------------------------------------------------------------------------

class TestIsAnonymized:
    def test_anonymized_by_resident_name(self):
        record = {"resident_name": "***", "email_address": "real@example.com"}
        assert is_anonymized(record) is True

    def test_anonymized_by_email(self):
        record = {"resident_name": "田中", "email_address": "***@***.***"}
        assert is_anonymized(record) is True

    def test_not_anonymized(self):
        record = {"resident_name": "田中太郎", "email_address": "tanaka@example.com"}
        assert is_anonymized(record) is False

    def test_empty_record(self):
        assert is_anonymized({}) is False

    def test_partial_anonymized_record(self):
        result = anonymize_record({
            "resident_name": "山本一郎",
            "email_address": "yamamoto@test.com",
        })
        assert is_anonymized(result) is True


# ---------------------------------------------------------------------------
# RETENTION_RULES
# ---------------------------------------------------------------------------

class TestRetentionRules:
    def test_residents_has_anonymize_flag(self):
        assert "anonymize_instead_of_delete" in RETENTION_RULES["resident"]

    def test_residents_anonymize_true(self):
        assert RETENTION_RULES["resident"]["anonymize_instead_of_delete"] is True

    def test_delivery_history_anonymize_false(self):
        assert RETENTION_RULES["delivery_history"]["anonymize_instead_of_delete"] is False

    def test_support_log_anonymize_false(self):
        assert RETENTION_RULES["ai_support_log"]["anonymize_instead_of_delete"] is False

    def test_access_log_anonymize_false(self):
        assert RETENTION_RULES["access_log"]["anonymize_instead_of_delete"] is False

    def test_all_rules_have_flag(self):
        for rule_name, rule in RETENTION_RULES.items():
            assert "anonymize_instead_of_delete" in rule, f"{rule_name} に anonymize_instead_of_delete がありません"


# ---------------------------------------------------------------------------
# DataRetentionBatch._anonymize_record
# ---------------------------------------------------------------------------

class TestDataRetentionBatchAnonymize:
    def test_anonymize_record_uses_common_anonymizer(self):
        batch = DataRetentionBatch()
        record = {
            "resident_name": "テスト太郎",
            "email_address": "test@example.com",
            "phone_number": "090-0000-1234",
        }
        result = batch._anonymize_record(record, "residents")
        assert result["resident_name"] == ANON_NAME
        assert result["email_address"] == ANON_EMAIL

    def test_anonymize_irreversible_name(self):
        """匿名化後の値から元の氏名を復元不可"""
        original_name = "復元不可テスト"
        batch = DataRetentionBatch()
        record = {"resident_name": original_name, "email_address": "x@x.com"}
        result = batch._anonymize_record(record, "residents")
        assert original_name not in result["resident_name"]
        assert original_name not in str(result.values())

    def test_anonymize_irreversible_email(self):
        """匿名化後の値から元のメールアドレスを復元不可"""
        original_email = "secret.user@private-domain.com"
        batch = DataRetentionBatch()
        record = {"email_address": original_email, "resident_name": "A"}
        result = batch._anonymize_record(record, "residents")
        assert original_email not in result["email_address"]

    def test_anonymize_irreversible_phone(self):
        """匿名化後の電話番号から上位桁を復元不可"""
        original_phone = "090-9876-5432"
        batch = DataRetentionBatch()
        record = {"phone_number": original_phone, "resident_name": "A", "email_address": "a@a.com"}
        result = batch._anonymize_record(record, "residents")
        # 上位桁（090, 9876）は含まれない
        assert "9876" not in result["phone_number"]
        assert "090" not in result["phone_number"]


# ---------------------------------------------------------------------------
# DataRetentionBatch.run() with anonymize
# ---------------------------------------------------------------------------

class TestDataRetentionBatchRun:
    def _make_conn_with_residents(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE residents (id INTEGER PRIMARY KEY, resident_name TEXT, "
            "email_address TEXT, phone_number TEXT, address TEXT, qr_token TEXT, "
            "tracking_number TEXT, country_code TEXT, deleted_at TEXT)"
        )
        cutoff = datetime.now(timezone.utc) - timedelta(days=3 * 365 + 1)
        cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO residents VALUES (1, '田中太郎', 'tanaka@example.com', "
            "'090-1234-5678', '東京都新宿区1-1', 'QR-001', 'TRACK-001', 'JP', ?)",
            (cutoff_str,),
        )
        conn.commit()
        return conn

    def test_run_anonymizes_residents(self):
        conn = self._make_conn_with_residents()
        batch = DataRetentionBatch(conn=conn)
        result = batch.run(dry_run=False)
        row = conn.execute("SELECT resident_name, email_address FROM residents WHERE id=1").fetchone()
        assert row[0] == ANON_NAME
        assert row[1] == ANON_EMAIL

    def test_run_result_action_anonymize(self):
        conn = self._make_conn_with_residents()
        batch = DataRetentionBatch(conn=conn)
        result = batch.run(dry_run=False)
        assert result["tables"]["resident"]["action"] == "anonymize"

    def test_dry_run_does_not_modify(self):
        conn = self._make_conn_with_residents()
        batch = DataRetentionBatch(conn=conn)
        batch.run(dry_run=True)
        row = conn.execute("SELECT resident_name FROM residents WHERE id=1").fetchone()
        assert row[0] == "田中太郎"
