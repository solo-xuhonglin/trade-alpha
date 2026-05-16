"""Data service module."""

import pandas as pd
from datetime import datetime, timezone
from trade_alpha.data.fetcher import fetch_stock_data, fetch_stock_list, fetch_daily_basic
from trade_alpha.dao import StockDaily, StockList
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
            industry=row.get("industry"),
            list_date=str(row["list_date"]) if pd.notna(row.get("list_date")) else None,
            market=row.get("market"),
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
    from trade_alpha.dao.mongodb import get_database
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
    start_date: str = None,
    end_date: str = None,
) -> list[StockDaily]:
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
