"""SmartLife EC — 居住者向けグループ購買・ゼロ在庫発注システム (port 8086)

SURPLUS SHIFTと連携し、マンション居住者向けにグループ予約・共同購入を提供する。
Gate D制約: human_approval_required=True は変更禁止（自動発注禁止）。
"""
from .products import (
    Product,
    ProductStore,
    register_from_surplus,
    BUILDING_TYPES,
    CATEGORIES,
)
from .orders import (
    OrderItem,
    GroupOrder,
    GroupOrderStore,
    ZeroStockTrigger,
)

__all__ = [
    'Product',
    'ProductStore',
    'register_from_surplus',
    'BUILDING_TYPES',
    'CATEGORIES',
    'OrderItem',
    'GroupOrder',
    'GroupOrderStore',
    'ZeroStockTrigger',
]
