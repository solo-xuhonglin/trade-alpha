"""快速计算新指标（RSI, ATR, OBV）- 不重复计算已有指标"""

import asyncio
import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pandas as pd
import numpy as np
from beanie import PydanticObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from trade_alpha.config import load_config
from trade_alpha.dao import init_db, StockDaily, StockList
from trade_alpha.logging import setup_logging, get_logger

logger = get_logger("fast_calculate_indicators")


def calc_rsi(series: pd.Series, period: int) -> pd.Series:
    """Calculate RSI for a series of pct_chg values."""
    delta = series.copy()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi[avg_loss == 0] = 100
    return rsi


def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate ATR."""
    prev_close = df["close"].shift(1)

    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - prev_close).abs()
    tr3 = (df["low"] - prev_close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period, min_periods=period).mean()
    return atr


def calc_obv(df: pd.DataFrame) -> pd.Series:
    """Calculate OBV."""
    close_diff = df["close"].diff()
    obv = pd.Series(index=df.index, dtype=float)
    obv.iloc[0] = df["vol"].iloc[0] if df["vol"].iloc[0] > 0 else 0

    for i in range(1, len(df)):
        if close_diff.iloc[i] > 0:
            obv.iloc[i] = obv.iloc[i - 1] + df["vol"].iloc[i]
        elif close_diff.iloc[i] < 0:
            obv.iloc[i] = obv.iloc[i - 1] - df["vol"].iloc[i]
        else:
            obv.iloc[i] = obv.iloc[i - 1]
    return obv


async def main(ts_codes: list[str] | None = None, limit: int | None = None, concurrency: int = 20):
    setup_logging(log_level="INFO")
    await init_db()

    config = load_config()
    client = AsyncIOMotorClient(config.mongodb_uri)
    db = client[config.mongodb_db]
    collection = db["stock_daily"]

    if ts_codes:
        stock_list = await StockList.find(StockList.ts_code.in_(ts_codes)).to_list()
    else:
        stock_list = await StockList.find(StockList.sync_status == "active").to_list()

    if limit:
        stock_list = stock_list[:limit]

    total = len(stock_list)
    semaphore = asyncio.Semaphore(concurrency)

    print(f"Found {total} stocks to process")
    print(f"Concurrency: {concurrency}")
    print("=" * 60)

    success_count = 0
    failed_count = 0
    failed_codes = []
    completed = 0

    async def process_stock(stock):
        nonlocal completed, success_count, failed_count
        ts_code = stock.ts_code

        async with semaphore:
            try:
                records = await StockDaily.find(
                    StockDaily.ts_code == ts_code
                ).sort(StockDaily.trade_date).to_list()

                if not records:
                    async with progress_lock:
                        completed += 1
                        logger.info(f"[{completed}/{total}] {ts_code}: no data")
                    return

                df = pd.DataFrame([r.model_dump() for r in records])
                df = df.sort_values("trade_date").reset_index(drop=True)

                pct_chg_exists = "pct_chg" in df.columns and df["pct_chg"].notna().any()

                if not pct_chg_exists:
                    df["pct_chg"] = df["close"].pct_change() * 100

                rsi_6 = calc_rsi(df["pct_chg"], 6)
                rsi_12 = calc_rsi(df["pct_chg"], 12)
                atr_14 = calc_atr(df, 14)
                obv = calc_obv(df)

                operations = []
                for i, row in df.iterrows():
                    trade_date = row["trade_date"]
                    update_fields = {}
                    val_rsi_6 = rsi_6.iloc[i]
                    val_rsi_12 = rsi_12.iloc[i]
                    val_atr = atr_14.iloc[i]
                    val_obv = obv.iloc[i]

                    if pd.notna(val_rsi_6):
                        update_fields["rsi_6"] = float(val_rsi_6)
                    if pd.notna(val_rsi_12):
                        update_fields["rsi_12"] = float(val_rsi_12)
                    if pd.notna(val_atr):
                        update_fields["atr_14"] = float(val_atr)
                    if pd.notna(val_obv):
                        update_fields["obv"] = float(val_obv)

                    if update_fields:
                        operations.append(
                            collection.update_one(
                                {"ts_code": ts_code, "trade_date": trade_date},
                                {"$set": update_fields}
                            )
                        )

                if operations:
                    await asyncio.gather(*operations)

                async with progress_lock:
                    completed += 1
                    success_count += 1
                    logger.info(f"[{completed}/{total}] {ts_code}: success ({len(operations)} records)")

            except Exception as e:
                async with progress_lock:
                    completed += 1
                    failed_count += 1
                    failed_codes.append(ts_code)
                    logger.error(f"[{completed}/{total}] {ts_code}: failed - {e}")

    progress_lock = asyncio.Lock()
    tasks = [process_stock(stock) for stock in stock_list]
    await asyncio.gather(*tasks)

    print("\n" + "=" * 60)
    print(f"Summary: {success_count} succeeded, {failed_count} failed")
    if failed_codes:
        print(f"Failed stocks: {failed_codes[:10]}{'...' if len(failed_codes) > 10 else ''}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fast calculate new indicators (RSI, ATR, OBV)")
    parser.add_argument("--ts-codes", nargs="+", help="Specific stock codes")
    parser.add_argument("--limit", type=int, help="Limit number of stocks")
    parser.add_argument("--concurrency", type=int, default=20, help="Concurrency (default: 20)")
    args = parser.parse_args()

    asyncio.run(main(ts_codes=args.ts_codes, limit=args.limit, concurrency=args.concurrency))
