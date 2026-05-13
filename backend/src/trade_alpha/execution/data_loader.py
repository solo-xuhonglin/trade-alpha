"""DataLoader for backtest execution pipeline."""

from typing import List, Dict
import pandas as pd
from trade_alpha.dao import StockList, StockDaily
from trade_alpha.logging import get_logger

logger = get_logger("execution.data_loader")


class DataLoader:
    """Load stock data for backtest execution."""

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
            StockDaily.ts_code.is_in(ts_codes),
        ).to_list()
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame([r.model_dump() for r in records])
        df = df.sort_values("ts_code")
        return df

    async def load_day_low(self, date: str, ts_codes: List[str]) -> Dict[str, float]:
        records = await StockDaily.find(
            StockDaily.trade_date == date,
            StockDaily.ts_code.is_in(ts_codes),
        ).to_list()
        return {r.ts_code: r.low for r in records if r.low is not None}

    async def load_day_close(self, date: str, ts_codes: List[str]) -> Dict[str, float]:
        records = await StockDaily.find(
            StockDaily.trade_date == date,
            StockDaily.ts_code.is_in(ts_codes),
        ).to_list()
        return {r.ts_code: r.close for r in records if r.close is not None}

    async def load_day_high(self, date: str, ts_codes: List[str]) -> Dict[str, float]:
        records = await StockDaily.find(
            StockDaily.trade_date == date,
            StockDaily.ts_code.is_in(ts_codes),
        ).to_list()
        return {r.ts_code: r.high for r in records if r.high is not None}
