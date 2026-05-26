"""Stock name cache - in-memory cache for ts_code -> stock_name lookup."""

from typing import Dict, List
from beanie.odm.operators.find.comparison import In
from trade_alpha.dao.stock_list import StockList

_cache: Dict[str, str] = {}


async def get_stock_name(ts_code: str) -> str:
    """Get stock name by ts_code, using in-memory cache."""
    if ts_code not in _cache:
        stock = await StockList.find_one(StockList.ts_code == ts_code)
        _cache[ts_code] = stock.name if stock else ts_code
    return _cache[ts_code]


async def get_stock_names(ts_codes: List[str]) -> Dict[str, str]:
    """Get stock names for multiple ts_codes in batch."""
    missing = [c for c in ts_codes if c not in _cache]
    if missing:
        stocks = await StockList.find(In(StockList.ts_code, missing)).to_list()
        _cache.update({s.ts_code: s.name for s in stocks})
        for c in missing:
            _cache.setdefault(c, c)
    return {c: _cache[c] for c in ts_codes}
