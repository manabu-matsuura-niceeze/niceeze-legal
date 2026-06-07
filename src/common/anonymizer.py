"""
個人情報保護法・GDPR対応 構造化データ匿名化モジュール
法令保存義務対象データを完全削除せず統計利用可能な形で匿名化
"""

import hashlib
import re
from typing import Dict, Optional

# 匿名化後の置換値
ANON_NAME = '***'
ANON_EMAIL = '***@***.***'
ANON_PHONE_SUFFIX_CHARS = 4        # 下4桁のみ保持
ANON_ADDRESS_LEVEL = 'prefecture'  # 都道府県レベルのみ保持
ANON_QR_PREFIX = 'ANON-'          # ハッシュ化IDのみ保持

# デフォルトフィールド設定
_DEFAULT_FIELDS_CONFIG: Dict[str, str] = {
    'resident_name': 'name',
    'phone_number': 'phone',
    'email_address': 'email',
    'address': 'address',
    'qr_token': 'qr_token',
    'tracking_number': 'delete',
}


def anonymize_name(name: str) -> str:
    """氏名 → '***'"""
    return ANON_NAME


def anonymize_email(email: str) -> str:
    """メールアドレス → '***@***.***'"""
    return ANON_EMAIL


def anonymize_phone(phone: str) -> str:
    """電話番号 → 下4桁のみ保持 '****-****-1234'"""
    digits = ''.join(c for c in phone if c.isdigit())
    last4 = digits[-4:] if len(digits) >= 4 else digits.ljust(4, '0')
    return f'****-****-{last4}'


def anonymize_address(address: str) -> str:
    """住所 → 都道府県レベルのみ保持"""
    # 都道府県パターン: 府・道・県の後に市区町村が続く場合を優先しつつ都を考慮
    # 「京都府」「大阪府」のように「府」が後に来るケースを優先するため
    # 府・道・県を先に試み、次に都を試みる
    match = (
        re.match(r'^(.*?(?:道|府|県))', address)
        or re.match(r'^(.*?都)', address)
    )
    return match.group(1) if match else '***'


def anonymize_qr_token(token: str) -> str:
    """QRトークン → SHA-256ハッシュの先頭12文字"""
    return ANON_QR_PREFIX + hashlib.sha256(token.encode()).hexdigest()[:12]


def anonymize_record(record: dict, fields_config: Optional[Dict[str, str]] = None) -> dict:
    """
    レコード（dict）の指定フィールドを匿名化する汎用関数

    Args:
        record: 匿名化対象のレコード
        fields_config: {field_name: 'name'|'email'|'phone'|'address'|'qr_token'|'delete'}
                       未指定フィールドはそのまま保持
                       'delete' の場合はキーを削除
                       country_code は常に保持（統計用）

    デフォルト設定（fields_config=Noneの場合）:
        {
            'resident_name': 'name',
            'phone_number': 'phone',
            'email_address': 'email',
            'address': 'address',
            'qr_token': 'qr_token',
            'tracking_number': 'delete',
        }
    """
    if fields_config is None:
        fields_config = _DEFAULT_FIELDS_CONFIG

    _anonymizers = {
        'name': anonymize_name,
        'email': anonymize_email,
        'phone': anonymize_phone,
        'address': anonymize_address,
        'qr_token': anonymize_qr_token,
    }

    result = {}
    for key, value in record.items():
        # country_code は常に保持
        if key == 'country_code':
            result[key] = value
            continue

        if key not in fields_config:
            result[key] = value
            continue

        action = fields_config[key]
        if action == 'delete':
            # キーを削除（resultに追加しない）
            continue
        elif action in _anonymizers:
            result[key] = _anonymizers[action](str(value) if value is not None else '')
        else:
            result[key] = value

    return result


def is_anonymized(record: dict) -> bool:
    """レコードが匿名化済みかどうかを確認"""
    # resident_name='***' または email_address='***@***.***' で判定
    if record.get('resident_name') == ANON_NAME:
        return True
    if record.get('email_address') == ANON_EMAIL:
        return True
    return False
