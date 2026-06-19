"""Data service module."""

import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple
from beanie.odm.operators.find.comparison import In
from trade_alpha.data.fetcher import fetch_stock_data, fetch_stock_list, fetch_daily_basic, fetch_trading_calendar
from trade_alpha.dao import StockDaily, StockList, TradeCalendar, StockListHistory
from trade_alpha.dao.mongodb import get_database
from trade_alpha.config import load_config
from trade_alpha.logging import get_logger
from trade_alpha.test_config import TEST_EXCLUDED_TS_CODES

logger = get_logger("data_service")

TUSHARE_STOCK_FIELDS = {"name", "industry", "list_date", "market", "total_mv", "pe", "pb", "updated_at"}


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
                if key in TUSHARE_STOCK_FIELDS:
                    setattr(existing, key, value)
            await existing.save()
        else:
            await stock.insert()
        count += 1

    logger.info(f"Successfully stored {count} stocks")
    return count


async def fetch_and_store_market_caps(trade_date: str) -> int:
    """Fetch daily basic data for a given trade date and store to StockListHistory.

    Skips already-existing (ts_code, trade_date) pairs.
    Returns number of new records inserted.
    """
    logger.info(f"Fetching market cap data for {trade_date}")
    df = fetch_daily_basic(trade_date)
    if df is None or df.empty:
        logger.warning(f"No market cap data for {trade_date}")
        return 0

    existing_records = await StockListHistory.find(
        StockListHistory.trade_date == trade_date
    ).to_list()
    existing_keys = {(r.ts_code, r.trade_date) for r in existing_records}

    records = []
    for _, row in df.iterrows():
        if (str(row["ts_code"]), trade_date) in existing_keys:
            continue
        records.append(StockListHistory(
            ts_code=str(row["ts_code"]),
            trade_date=trade_date,
            total_mv=float(row["total_mv"]) if pd.notna(row.get("total_mv")) else None,
            pe=float(row["pe"]) if pd.notna(row.get("pe")) else None,
            pb=float(row["pb"]) if pd.notna(row.get("pb")) else None,
        ))

    if records:
        await StockListHistory.insert_many(records)

    logger.info(f"Stored {len(records)} market cap records for {trade_date}")
    return len(records)


async def resolve_and_fetch_historical_date(date_str: str) -> Optional[str]:
    """Resolve a date to the nearest trading day (within 20 days) and ensure market cap data exists.

    If the resolved trading day has no cached data in StockListHistory,
    automatically fetches it from Tushare.

    Returns the resolved trading day in YYYYMMDD, or None if no trading day found.
    """
    from datetime import datetime, timedelta
    start = datetime.strptime(date_str, "%Y%m%d")
    resolved = None
    for i in range(20):
        check = (start + timedelta(days=i)).strftime("%Y%m%d")
        day = await TradeCalendar.find_one(
            TradeCalendar.cal_date == check,
            TradeCalendar.is_open == 1,
        )
        if day:
            resolved = day.cal_date
            break

    if not resolved:
        return None

    existing = await StockListHistory.find(
        StockListHistory.trade_date == resolved
    ).first_or_none()
    if not existing:
        await fetch_and_store_market_caps(resolved)

    return resolved


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


async def get_stocks_for_sync(
    sync_status: str = "active",
    top_limit: Optional[int] = None,
    include_backtest: bool = True,
) -> list[StockList]:
    """Get stocks for sync in a single query, optionally including backtest stocks.

    Returns top N stocks by total_mv, plus any backtest stocks
    (is_active_for_backtest=true) outside the top N. Deduplicated by ts_code.
    """
    if top_limit is None:
        config = load_config()
        top_limit = config.top_market_cap_stocks

    all_stocks = await StockList.find(
        StockList.sync_status == sync_status,
    ).sort(-StockList.total_mv).to_list()

    all_stocks = [s for s in all_stocks if s.ts_code not in TEST_EXCLUDED_TS_CODES]

    result = all_stocks[:top_limit]
    seen = {s.ts_code for s in result}

    if include_backtest:
        for s in all_stocks:
            if s.is_active_for_backtest and s.ts_code not in seen:
                result.append(s)
                seen.add(s.ts_code)

    return result


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
    logger.info("update_stock_data_count", f"Updated {updated} stocks")
    return updated


async def active_stock_data(ts_code: str) -> bool:
    """Ensure a stock has daily data and indicators calculated.

    If the stock already has sync_status='active', returns True immediately.
    Otherwise fetches daily data from Tushare, calculates all indicators,
    marks sync_status='active', and updates data_count/latest_date.
    """
    stock = await StockList.find_one(StockList.ts_code == ts_code)
    if not stock:
        logger.warning(f"Stock not found in StockList: {ts_code}")
        return False
    if stock.sync_status == "active":
        return True

    try:
        from trade_alpha.scheduler.stock_data_init_job import get_data_period
        from trade_alpha.indicators.service import calculate_all_indicators

        start_date, end_date = get_data_period()
        count = await fetch_and_store_stock_daily(ts_code, start_date, end_date)
        logger.info(f"Fetched {count} daily records for {ts_code}")

        await calculate_all_indicators(ts_code)
        logger.info(f"Calculated indicators for {ts_code}")

        stock.sync_status = "active"
        await stock.save()

        db = await get_database()
        pipeline = [
            {"$match": {"ts_code": ts_code}},
            {"$group": {
                "_id": "$ts_code",
                "count": {"$sum": 1},
                "latest_date": {"$max": "$trade_date"}
            }}
        ]
        async for doc in db.stock_daily.aggregate(pipeline):
            stock.data_count = doc["count"]
            stock.latest_date = doc["latest_date"]
            await stock.save()
            break

        return True
    except Exception as e:
        logger.error(f"Failed to prepare data for {ts_code}: {e}")
        return False


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


async def list_stocks_with_filters(
    page: int = 1,
    page_size: int = 20,
    industries: Optional[list[str]] = None,
    historical_date: Optional[str] = None,
    status_filter: Optional[str] = None,
) -> Tuple[List[StockList], int, int, int]:
    """List stocks with industry filter and optional historical market cap.

    Returns (stocks, total_count, active_count, backtest_count).
    """
    query_conditions = []
    if industries:
        query_conditions.append(In(StockList.industry, industries))

    base_query = StockList.find(*query_conditions)

    active_cond = [StockList.sync_status == "active"]
    if industries:
        active_cond.append(In(StockList.industry, industries))
    active_count = await StockList.find(*active_cond).count()

    bt_cond = [StockList.is_active_for_backtest == True]
    if industries:
        bt_cond.append(In(StockList.industry, industries))
    backtest_count = await StockList.find(*bt_cond).count()

    if historical_date:
        historical_records = await StockListHistory.find(
            StockListHistory.trade_date == historical_date
        ).to_list()
        hist_map = {r.ts_code: r.total_mv for r in historical_records}

        stocks = await base_query.sort(-StockList.total_mv).to_list()
        stocks.sort(key=lambda s: hist_map.get(s.ts_code, 0) if hist_map.get(s.ts_code) is not None else -1, reverse=True)
    else:
        stocks = await base_query.sort(-StockList.total_mv).to_list()

    if status_filter == "backtest":
        stocks = [s for s in stocks if s.is_active_for_backtest]

    total = len(stocks)

    skip = (page - 1) * page_size
    paginated = stocks[skip:skip + page_size]

    return paginated, total, active_count, backtest_count
