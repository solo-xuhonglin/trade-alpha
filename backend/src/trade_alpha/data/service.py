"""Data service module."""

import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple
from trade_alpha.data.fetcher import fetch_stock_data, fetch_stock_list, fetch_daily_basic, fetch_trading_calendar
from trade_alpha.dao import StockDaily, StockList, TradeCalendar
from trade_alpha.dao.mongodb import get_database
from trade_alpha.config import load_config
from trade_alpha.logging import get_logger

logger = get_logger("data_service")


async def fetch_and_store_stock_daily(ts_code: str, start_date: str, end_date: str) -> int:
    """Fetch stock daily data from Tushare and store to MongoDB."""

    logger.info(f"Fetching daily data for {ts_code} from {start_date} to {end_date}")
    df = fetch_stock_data(ts_code, start_date, end_date)
    if df is None or df.empty:
        logger.warning(f"No data fetched for {ts_code} from {start_date} to {end_date}")
        return 0

    logger.info(f"Successfully fetched {len(df)} records for {ts_code}")

    records = df.to_dict("records")
    for record in records:
        record["trade_date"] = str(record["trade_date"])

    REQUIRED_FIELDS = ["open", "high", "low", "close", "vol", "amount"]
    before = len(records)
    records = [
        r for r in records
        if all(r.get(f) is not None and not (isinstance(r.get(f), float) and pd.isna(r.get(f))) for f in REQUIRED_FIELDS)
    ]
    skipped = before - len(records)
    if skipped:
        logger.warning(f"Skipped {skipped} records with null OHLC values for {ts_code}")

    existing = await StockDaily.find(StockDaily.ts_code == ts_code).to_list()
    existing_dates = {r.trade_date for r in existing}

    new_records = [r for r in records if r["trade_date"] not in existing_dates]

    if new_records:
        await StockDaily.insert_many([StockDaily(**r) for r in new_records])

    return len(new_records)


async def fetch_and_store_stock_list() -> int:
    """Fetch stock list from Tushare and store to MongoDB."""

    logger.info("Fetching stock list from Tushare")
    stock_df = fetch_stock_list()
    if stock_df is None or stock_df.empty:
        logger.warning("No stock list data fetched from Tushare")
        return 0

    basic_df = fetch_daily_basic()
    if basic_df is not None and not basic_df.empty:
        stock_df = pd.merge(stock_df, basic_df, on="ts_code", how="left")
    else:
        stock_df["total_mv"] = None
        stock_df["pe"] = None
        stock_df["pb"] = None

    count = 0
    for _, row in stock_df.iterrows():
        existing = await StockList.find_one(StockList.ts_code == row["ts_code"])
        stock = StockList(
            ts_code=row["ts_code"],
            name=row["name"],
            industry=str(row["industry"]) if pd.notna(row.get("industry")) else None,
            list_date=str(row["list_date"]) if pd.notna(row.get("list_date")) else None,
            market=str(row["market"]) if pd.notna(row.get("market")) else None,
            total_mv=float(row["total_mv"]) if pd.notna(row.get("total_mv")) else None,
            pe=float(row["pe"]) if pd.notna(row.get("pe")) else None,
            pb=float(row["pb"]) if pd.notna(row.get("pb")) else None,
            updated_at=datetime.now(timezone.utc),
        )
        if existing:
            for key, value in stock.model_dump(exclude={"id"}).items():
                setattr(existing, key, value)
            await existing.save()
        else:
            await stock.insert()
        count += 1

    logger.info(f"Successfully stored {count} stocks")
    return count


async def list_stocks(page: int = 1, page_size: int = 20) -> Tuple[List[StockList], int]:
    """List stocks with pagination."""
    total = await StockList.count()
    skip = (page - 1) * page_size
    stocks = await StockList.find_all().sort(-StockList.total_mv).skip(skip).limit(page_size).to_list()
    return stocks, total


async def list_stocks_by_mv_rank(start_rank: int = 1, end_rank: int = 3000) -> List[StockList]:
    """List stocks by market value rank from start_rank to end_rank (1-based)."""
    start_idx = max(0, start_rank - 1)
    limit = max(0, end_rank - start_rank + 1)
    stocks = await StockList.find_all().sort(-StockList.total_mv).skip(start_idx).limit(limit).to_list()
    return stocks


async def get_downloaded_summary() -> list[dict]:
    """Get summary of downloaded data per stock from StockList stored fields."""
    stocks = await StockList.find_all().to_list()
    return [
        {
            "ts_code": s.ts_code,
            "count": s.data_count,
            "latest_date": s.latest_date,
        }
        for s in stocks
        if s.data_count is not None
    ]


async def update_stock_data_count():
    """Aggregate stock_daily collection and update data_count/latest_date on StockList."""
    pipeline = [
        {"$group": {
            "_id": "$ts_code",
            "count": {"$sum": 1},
            "latest_date": {"$max": "$trade_date"}
        }}
    ]
    db = await get_database()
    updated = 0
    async for doc in db.stock_daily.aggregate(pipeline):
        stock = await StockList.find_one(StockList.ts_code == doc["_id"])
        if stock:
            stock.data_count = doc["count"]
            stock.latest_date = doc["latest_date"]
            await stock.save()
            updated += 1
    logger.info(f"update_stock_data_count", f"Updated {updated} stocks")
    return updated


async def find_stock_daily_by_ts_code(
    ts_code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[StockDaily]:
    """Find stock daily records by ts_code with optional date filter, sorted by trade_date ascending."""
    conditions = [StockDaily.ts_code == ts_code]
    if start_date:
        conditions.append(StockDaily.trade_date >= start_date)
    if end_date:
        conditions.append(StockDaily.trade_date <= end_date)
    query = StockDaily.find(*conditions)
    return await query.sort(StockDaily.trade_date).to_list()


async def find_stock_daily_paginated(
    ts_code: str,
    page: int = 1,
    page_size: int = 500,
) -> Tuple[list[StockDaily], int]:
    """Find stock daily records with pagination, sorted by trade_date descending (newest first)."""
    query = StockDaily.find(StockDaily.ts_code == ts_code).sort(-StockDaily.trade_date)
    total = await query.count()
    skip = (page - 1) * page_size
    records = await query.skip(skip).limit(page_size).to_list()
    return records, total


async def delete_stock_daily_by_ts_code(ts_code: str) -> int:
    """Delete stock daily records by ts_code."""
    result = await StockDaily.find(StockDaily.ts_code == ts_code).delete()
    return result.deleted_count


fetch_and_store = fetch_and_store_stock_daily
update_stock_list = fetch_and_store_stock_list


async def fetch_and_store_trade_calendar() -> dict:
    """Fetch trading calendar from Tushare and store to MongoDB."""
    config = load_config()
    now = datetime.now()
    data_years = config.data_years
    start_date = (now - timedelta(days=365 * data_years)).strftime("%Y%m%d")
    end_date = (now + timedelta(days=365)).strftime("%Y%m%d")

    logger.info("fetch_trade_calendar", f"Fetching calendar from {start_date} to {end_date}")
    df = fetch_trading_calendar(start_date, end_date)
    if df is None or df.empty:
        raise ValueError("No trading calendar data fetched")

    records = df.to_dict("records")
    for r in records:
        r["cal_date"] = str(r["cal_date"])
        r["pretrade_date"] = str(r["pretrade_date"]) if r.get("pretrade_date") else None

    existing = await TradeCalendar.find_all().to_list()
    existing_keys = {(e.cal_date, e.exchange) for e in existing}

    new_records = [
        TradeCalendar(**r, updated_at=datetime.now(timezone.utc))
        for r in records
        if (r["cal_date"], r["exchange"]) not in existing_keys
    ]

    if new_records:
        await TradeCalendar.insert_many(new_records)

    return {
        "start_date": start_date,
        "end_date": end_date,
        "stored_count": len(new_records),
    }


async def get_trade_calendar_records(start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[dict]:
    """Query trade calendar records with real-time stock_count and indicator_rate.

    Stats are computed on-the-fly via MongoDB aggregation on stock_daily,
    using ma_5 as a proxy for indicator completeness (all indicators are
    computed in batch, so if ma_5 is set, others are too).
    """
    query = TradeCalendar.find_all()
    if start_date:
        query = TradeCalendar.find(TradeCalendar.cal_date >= start_date)
    if end_date:
        query = TradeCalendar.find(TradeCalendar.cal_date <= end_date)
    if start_date and end_date:
        query = TradeCalendar.find(
            TradeCalendar.cal_date >= start_date,
            TradeCalendar.cal_date <= end_date,
        )

    records = await query.sort(TradeCalendar.cal_date).to_list()

    # Real-time aggregation: stock_count + indicator_ready per trade_date
    day_stats: dict[str, dict] = {}
    if start_date and end_date:
        db = await get_database()
        pipeline = [
            {"$match": {"trade_date": {"$gte": start_date, "$lte": end_date}}},
            {"$group": {
                "_id": "$trade_date",
                "stock_count": {"$sum": 1},
                "indicator_ready": {
                    "$sum": {"$cond": [{"$ne": ["$ma_5", None]}, 1, 0]}
                },
            }},
        ]
        async for doc in db.stock_daily.aggregate(pipeline):
            td = doc["_id"]
            cnt = doc["stock_count"]
            ready = doc["indicator_ready"]
            day_stats[td] = {
                "stock_count": cnt,
                "indicator_rate": round(ready / cnt, 4) if cnt > 0 else 0.0,
            }

    result = []
    for r in records:
        item = {
            "exchange": r.exchange,
            "cal_date": r.cal_date,
            "is_open": r.is_open,
            "pretrade_date": r.pretrade_date,
        }
        stats = day_stats.get(r.cal_date)
        if stats:
            item["stock_count"] = stats["stock_count"]
            item["indicator_rate"] = stats["indicator_rate"]
        result.append(item)

    return result
