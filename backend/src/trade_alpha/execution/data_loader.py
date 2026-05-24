"""DataLoader for backtest execution pipeline."""

from typing import List, Dict, Optional
import pandas as pd
from datetime import datetime, timedelta
from beanie.odm.operators.find.comparison import In
from trade_alpha.dao import StockList, StockDaily
from trade_alpha.logging import get_logger

logger = get_logger("execution.data_loader")


class DataLoader:
    """Load stock data for backtest execution."""

    def __init__(self):
        self._history_cache: Dict[str, List] = {}

    def _get_cache_start(self, ts_code: str):
        """Get the earliest date in cache for a stock."""
        if ts_code not in self._history_cache or not self._history_cache[ts_code]:
            return None
        return self._history_cache[ts_code][0].trade_date

    def _get_cache_end(self, ts_code: str):
        """Get the latest date in cache for a stock."""
        if ts_code not in self._history_cache or not self._history_cache[ts_code]:
            return None
        return self._history_cache[ts_code][-1].trade_date

    def _trim_cache(self, ts_code: str, keep_days: int):
        """Trim cache to keep only the most recent keep_days records."""
        if ts_code not in self._history_cache:
            return
        if len(self._history_cache[ts_code]) > keep_days:
            trim_count = len(self._history_cache[ts_code]) - keep_days
            self._history_cache[ts_code] = self._history_cache[ts_code][trim_count:]

    def _calc_start_date(self, end_date: str, days: int):
        """Calculate start date, accounting for weekends."""
        end_dt = datetime.strptime(end_date, "%Y%m%d")
        start_dt = end_dt - timedelta(days=days * 2)
        return start_dt.strftime("%Y%m%d")

    def _next_date(self, date_str: str):
        """Get the next calendar date."""
        dt = datetime.strptime(date_str, "%Y%m%d")
        dt += timedelta(days=1)
        return dt.strftime("%Y%m%d")

    async def get_top_stocks(self, date: str, limit: int = 300) -> List[Dict]:
        records = await StockList.find(
            StockList.sync_status == "active"
        ).sort(-StockList.total_mv).limit(limit).to_list()
        result = []
        for r in records:
            daily = await StockDaily.find_one(
                StockDaily.ts_code == r.ts_code,
                StockDaily.trade_date == date,
            )
            if daily:
                result.append({
                    "ts_code": r.ts_code,
                    "name": r.name,
                    "close": daily.close,
                })
        return result

    async def load_day_data(self, date: str, ts_codes: List[str]) -> pd.DataFrame:
        records = await StockDaily.find(
            StockDaily.trade_date == date,
            In(StockDaily.ts_code, ts_codes),
        ).to_list()
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame([r.model_dump() for r in records])
        df = df.sort_values("ts_code")
        return df

    async def _load_from_db(self, start_date: str, end_date: str, ts_codes: List[str]):
        """Load data from database for the specified time range."""
        records = await StockDaily.find(
            StockDaily.trade_date >= start_date,
            StockDaily.trade_date <= end_date,
            In(StockDaily.ts_code, ts_codes),
        ).sort(StockDaily.ts_code, StockDaily.trade_date).to_list()
        return records

    async def load_history_data(self, end_date: str, ts_codes: List[str], days: int) -> pd.DataFrame:
        """Load historical data for multiple stocks from end_date back by days."""
        end_dt = datetime.strptime(end_date, "%Y%m%d")
        start_dt = end_dt - timedelta(days=days * 2)  # load extra to account for weekends
        start_date = start_dt.strftime("%Y%m%d")
        
        records = await StockDaily.find(
            StockDaily.trade_date >= start_date,
            StockDaily.trade_date <= end_date,
            In(StockDaily.ts_code, ts_codes),
        ).sort(StockDaily.ts_code, StockDaily.trade_date).to_list()
        
        if not records:
            return pd.DataFrame()
        
        df = pd.DataFrame([r.model_dump() for r in records])
        return df

    async def load_day_low(self, date: str, ts_codes: List[str]) -> Dict[str, float]:
        records = await StockDaily.find(
            StockDaily.trade_date == date,
            In(StockDaily.ts_code, ts_codes),
        ).to_list()
        return {r.ts_code: r.low for r in records if r.low is not None}

    async def load_day_close(self, date: str, ts_codes: List[str]) -> Dict[str, float]:
        records = await StockDaily.find(
            StockDaily.trade_date == date,
            In(StockDaily.ts_code, ts_codes),
        ).to_list()
        return {r.ts_code: r.close for r in records if r.close is not None}

    async def load_day_high(self, date: str, ts_codes: List[str]) -> Dict[str, float]:
        records = await StockDaily.find(
            StockDaily.trade_date == date,
            In(StockDaily.ts_code, ts_codes),
        ).to_list()
        return {r.ts_code: r.high for r in records if r.high is not None}
