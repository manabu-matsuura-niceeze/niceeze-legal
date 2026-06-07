# src/common/eu_countries.py
# EU/EEA加盟国リスト (ISO 3166-1 alpha-2)

EU_MEMBER_STATES = {
    'AT', 'BE', 'BG', 'CY', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI',
    'FR', 'GR', 'HR', 'HU', 'IE', 'IT', 'LT', 'LU', 'LV', 'MT',
    'NL', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK',
}
EEA_ADDITIONAL = {'IS', 'LI', 'NO'}
GDPR_APPLICABLE_COUNTRIES = EU_MEMBER_STATES | EEA_ADDITIONAL


def is_gdpr_applicable(country_code: str) -> bool:
    """GDPRが適用される国かどうかを判定する"""
    return country_code.upper() in GDPR_APPLICABLE_COUNTRIES
