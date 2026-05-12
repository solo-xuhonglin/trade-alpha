"""DataLoader module for execution pipeline."""

import pandas as pd
from typing import List, Literal
from trade_alpha.data.service import find_stock_daily_by_ts_code


class DataLoader:
    """Data loader for fetching stock data for execution pipeline."""

    async def load(
        self,
        ts_codes: List[str],
        start_date: str,
        end_date: str,
        mode: Literal["backtest", "live"] = "backtest",
    ) -> pd.DataFrame:
        """
        Load stock daily data for given stock codes and date range.
        
        Args:
            ts_codes: List of stock codes to fetch data for
            start_date: Start date in format 'YYYYMMDD'
            end_date: End date in format 'YYYYMMDD'
            mode: Execution mode ('backtest' or 'live'). Both modes return
                  the same data; live mode handling for current day data
                  is done in the pipeline layer.
        
        Returns:
            pandas DataFrame containing stock daily data
        """
        all_dfs = []
        
        for ts_code in ts_codes:
            records = await find_stock_daily_by_ts_code(ts_code, start_date, end_date)
            if records:
                df = pd.DataFrame([r.model_dump() for r in records])
                all_dfs.append(df)
        
        if not all_dfs:
            return pd.DataFrame()
        
        return pd.concat(all_dfs, ignore_index=True)