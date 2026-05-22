"""Script to calculate new trend indicators for active stocks.

Only calculates indicators for stocks that haven't been computed yet.
Does not modify sync_status to avoid conflicts with the sync scheduler.
"""
import asyncio
import sys
from datetime import datetime

from trade_alpha.dao import init_db, StockList, StockDaily
from trade_alpha.indicators.service import calculate_all_indicators
from trade_alpha.logging import get_logger

logger = get_logger("calculate_trend_indicators")


async def calculate_trend_for_active_stocks(batch_size: int = 100):
    """Calculate trend indicators for active stocks that haven't been computed yet."""
    await init_db()
    
    # Get total active stocks
    total_active = await StockList.find(StockList.sync_status == "active").count()
    logger.info(f"Total active stocks: {total_active}")
    
    processed = 0
    updated = 0
    skipped = 0
    errors = 0
    
    # Process in batches
    skip = 0
    while True:
        # Get a batch of active stocks
        stocks = await StockList.find(
            StockList.sync_status == "active"
        ).skip(skip).limit(batch_size).to_list()
        
        if not stocks:
            break
        
        for stock in stocks:
            try:
                # Check if trend indicators are already computed
                latest_record = await StockDaily.find_one(
                    StockDaily.ts_code == stock.ts_code,
                    sort=[("trade_date", -1)]
                )
                
                if latest_record is None:
                    logger.warning(f"No daily records for {stock.ts_code}, skipping")
                    skipped += 1
                    continue
                
                # Check if trend_indicators are already computed
                if latest_record.trend_arrangement_5 is not None:
                    skipped += 1
                    continue
                
                # Calculate indicators (only computes new ones)
                await calculate_all_indicators(stock.ts_code)
                updated += 1
                
                if updated % 50 == 0:
                    logger.info(f"Progress: {updated} stocks updated, {skipped} skipped")
                
            except Exception as e:
                logger.error(f"Error processing {stock.ts_code}: {e}")
                errors += 1
        
        skip += batch_size
        processed += len(stocks)
        logger.info(f"Batch processed: {processed}/{total_active}")
    
    logger.info(f"Done. Updated: {updated}, Skipped: {skipped}, Errors: {errors}")
    return updated, skipped, errors


if __name__ == "__main__":
    start_time = datetime.now()
    logger.info(f"Starting trend indicators calculation at {start_time}")
    
    updated, skipped, errors = asyncio.run(calculate_trend_for_active_stocks())
    
    end_time = datetime.now()
    duration = end_time - start_time
    logger.info(f"Completed at {end_time}, duration: {duration}")
    print(f"\nSummary: Updated={updated}, Skipped={skipped}, Errors={errors}, Duration={duration}")
