"""Stock list sync job — fetch latest stock list and mark delta stocks as pending.

Runs at 01:00 daily to:
1. Snapshot current top N ts_codes and all existing ts_codes
2. Fetch and merge the latest stock list from Tushare
3. Detect new stocks and newly-ranked stocks
4. Mark newly-ranked stocks as pending (new stocks are already pending by default)

The subsequent stock_data_init job (02:00) will process the pending stocks.
"""

from trade_alpha.dao.stock_list import StockList
from trade_alpha.data.service import fetch_and_store_stock_list
from trade_alpha.config import load_config
from trade_alpha.logging import get_logger

logger = get_logger("stock_list_sync")


async def run_stock_list_sync_job(cfg=None, **kwargs):
    """Execute one stock list sync job.

    Snapshots current state, fetches/merges latest stock list from Tushare,
    detects new and newly-ranked stocks, marks them as pending.
    """
    logger.info("Stock list sync job started")

    config = load_config()
    top_n = config.top_market_cap_stocks

    # Step 1: Snapshot current state
    old_top_n_set = set(await StockList.get_top_n_ts_codes(top_n))
    existing_set = await StockList.get_all_ts_codes()
    logger.info(f"Current stocks: {len(existing_set)}, top {top_n}: {len(old_top_n_set)}")

    # Step 2: Fetch and merge latest stock list from Tushare
    count = await fetch_and_store_stock_list()
    if count == 0:
        logger.warning("No stocks fetched from Tushare, aborting")
        return
    logger.info(f"Merged {count} stocks from Tushare")

    # Step 3: Get the new top N after merge
    new_top_n_set = set(await StockList.get_top_n_ts_codes(top_n))

    # Step 4: Compute delta
    new_stocks = new_top_n_set - existing_set
    newly_ranked = new_top_n_set - old_top_n_set - new_stocks

    logger.info(
        f"Delta: {len(new_stocks)} new stocks, {len(newly_ranked)} newly-ranked stocks"
    )

    # Step 5: Mark newly-ranked stocks as pending (new stocks already default to pending)
    # Only mark stocks that genuinely need data initialization (data_count is None or 0)
    marked_count = 0
    for ts_code in newly_ranked:
        stock = await StockList.find_one(StockList.ts_code == ts_code)
        if not stock:
            continue
        has_data = stock.data_count is not None and stock.data_count > 0
        if has_data:
            if stock.sync_status != "active":
                stock.sync_status = "active"
                await stock.save()
            continue
        if stock.sync_status != "pending":
            stock.sync_status = "pending"
            await stock.save()
            marked_count += 1

    if marked_count:
        logger.info(f"Marked {marked_count} newly-ranked stocks as pending")
    else:
        logger.info("No newly-ranked stocks needed status change")

    logger.info("Stock list sync job completed")
