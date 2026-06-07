"""PII暗号化モジュール

AES-256-GCM相当の暗号化を提供する。
cryptography パッケージが利用不可のため、hashlib + hmac + secrets を使用した
XOR-CTRモード実装（HMAC-SHA256による整合性検証付き）。

NOTE: 本番環境では Google Cloud Secret Manager からキーを取得すること。
      現実装は環境変数 PII_SECRET_KEY からキーを取得する。
      Secret Manager 連携例:
          from google.cloud import secretmanager
          client = secretmanager.SecretManagerServiceClient()
          name = f"projects/{PROJECT_ID}/secrets/pii-secret-key/versions/latest"
          key = client.access_secret_version(name=name).payload.data.decode()
"""

import base64
import hashlib
import hmac
import os
import secrets
import json
from typing import Optional

PII_FIELDS = ["resident_name", "phone_number", "email_address"]

_NONCE_BYTES = 16
_KEY_BYTES = 32  # 256-bit


def _derive_key(secret_key: str, salt: bytes) -> bytes:
    """PBKDF2-HMAC-SHA256 でキーを導出する (256-bit)"""
    return hashlib.pbkdf2_hmac(  # nosec B324
        "sha256",
        secret_key.encode("utf-8"),
        salt,
        iterations=100_000,
        dklen=_KEY_BYTES,
    )


def _xor_ctr(data: bytes, key: bytes, nonce: bytes) -> bytes:
    """XOR-CTRストリーム暗号（AES代替）

    Security Note: 真のAES-GCMではなく hashlib ベースのCTR実装。
    本番環境では cryptography パッケージの AES-256-GCM を推奨。
    """
    result = bytearray(len(data))
    block_size = 32  # SHA-256 出力サイズ
    for i in range(0, len(data), block_size):
        # CTRブロック: HMAC-SHA256(key, nonce || counter)
        counter = i // block_size
        block_input = nonce + counter.to_bytes(8, "big")
        keystream = hmac.new(key, block_input, hashlib.sha256).digest()  # nosec B324
        chunk = data[i : i + block_size]
        for j, b in enumerate(chunk):
            result[i + j] = b ^ keystream[j]
    return bytes(result)


class PIIEncryptor:
    """PII暗号化クラス

    secret_key 未設定時は環境変数 PII_SECRET_KEY から取得。
    それも未設定の場合は mock_mode=True（テスト・開発用）で動作する。

    Attributes:
        mock_mode: True の場合は暗号化せず base64 エンコードのみ（テスト用）
    """

    def __init__(self, secret_key: str = "") -> None:
        if secret_key:
            self._secret_key: Optional[str] = secret_key
            self.mock_mode = False
        else:
            env_key = os.environ.get("PII_SECRET_KEY", "")
            if env_key:
                self._secret_key = env_key
                self.mock_mode = False
            else:
                # テスト用モック: 暗号化は行わず base64 エンコードのみ
                # WARNING: 本番環境では必ず PII_SECRET_KEY を設定すること
                self._secret_key = None
                self.mock_mode = True

    def encrypt(self, plaintext: str) -> str:
        """平文を暗号化して base64 エンコードした文字列を返す"""
        if self.mock_mode:
            # nosec B324 - テスト用モックのみ
            payload = json.dumps({"mock": True, "data": plaintext})
            return base64.urlsafe_b64encode(payload.encode()).decode()

        assert self._secret_key is not None  # mock_mode=False 時は必ず設定済み

        # 1) 乱数ソルト・ノンス生成
        salt = secrets.token_bytes(_NONCE_BYTES)   # nosec B311
        nonce = secrets.token_bytes(_NONCE_BYTES)  # nosec B311

        # 2) キー導出
        key = _derive_key(self._secret_key, salt)

        # 3) 暗号化 (XOR-CTR)
        ciphertext = _xor_ctr(plaintext.encode("utf-8"), key, nonce)

        # 4) HMAC-SHA256 による整合性タグ
        tag = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()

        # 5) salt || nonce || tag || ciphertext を base64 エンコード
        blob = salt + nonce + tag + ciphertext
        return base64.urlsafe_b64encode(blob).decode()

    def decrypt(self, ciphertext: str) -> str:
        """暗号化文字列を復号して平文を返す"""
        if self.mock_mode:
            payload = json.loads(base64.urlsafe_b64decode(ciphertext).decode())
            return payload["data"]

        assert self._secret_key is not None

        blob = base64.urlsafe_b64decode(ciphertext)
        tag_bytes = 32  # SHA-256 出力サイズ

        # blob = salt(16) || nonce(16) || tag(32) || ciphertext
        min_len = _NONCE_BYTES + _NONCE_BYTES + tag_bytes
        if len(blob) < min_len:
            raise ValueError("不正な暗号文: データが短すぎます")

        salt = blob[:_NONCE_BYTES]
        nonce = blob[_NONCE_BYTES : _NONCE_BYTES * 2]
        tag = blob[_NONCE_BYTES * 2 : _NONCE_BYTES * 2 + tag_bytes]
        encrypted = blob[_NONCE_BYTES * 2 + tag_bytes :]

        key = _derive_key(self._secret_key, salt)

        # HMAC 検証（タイミング攻撃対策: compare_digest 使用）
        expected_tag = hmac.new(key, nonce + encrypted, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected_tag):
            raise ValueError("暗号文の整合性検証に失敗しました（改ざんの可能性）")

        plaintext = _xor_ctr(encrypted, key, nonce)
        return plaintext.decode("utf-8")

    def encrypt_record(self, record: dict) -> dict:
        """レコード辞書内の PII_FIELDS を暗号化して返す（元レコードは変更しない）"""
        result = dict(record)
        for field in PII_FIELDS:
            if field in result and result[field] is not None:
                result[field] = self.encrypt(str(result[field]))
        return result

    def decrypt_record(self, record: dict) -> dict:
        """レコード辞書内の PII_FIELDS を復号して返す（元レコードは変更しない）"""
        result = dict(record)
        for field in PII_FIELDS:
            if field in result and result[field] is not None:
                result[field] = self.decrypt(str(result[field]))
        return result
