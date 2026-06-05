"""Research部 — RES-A01（8社価格マトリクス）/ RES-A02（トレンドスコア）"""
from .res_a01 import PriceFetcher, PriceMatrix, PriceRecord
from .res_a02 import TrendFetcher, ProductTrend, TrendDataPoint

__all__ = [
    'PriceFetcher', 'PriceMatrix', 'PriceRecord',
    'TrendFetcher', 'ProductTrend', 'TrendDataPoint',
]
