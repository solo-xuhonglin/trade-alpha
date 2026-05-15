"""Train model with all active stocks."""
import asyncio
from datetime import datetime

from beanie.odm.operators.find.comparison import NotIn

from trade_alpha.dao import init_db, StockList, StockDaily
from trade_alpha.predict import config_service, training_service
from trade_alpha.logging import setup_logging, get_logger
from trade_alpha.test_config import (
    PROD_TRAINING_NAME, PROD_MODEL_CONFIG_NAME, TEST_EXCLUDED_TS_CODES,
)

logger = get_logger("train_model")


async def get_active_stocks():
    return await StockList.find(
        StockList.sync_status == "active",
        NotIn(StockList.ts_code, TEST_EXCLUDED_TS_CODES)
    ).sort(-StockList.total_mv).to_list()


async def get_stocks_with_data(stocks, start_date, end_date, min_records=30):
    valid = []
    for stock in stocks:
        count = await StockDaily.find(
            StockDaily.ts_code == stock.ts_code,
            StockDaily.trade_date >= start_date,
            StockDaily.trade_date <= end_date,
        ).count()
        if count >= min_records:
            valid.append(stock.ts_code)
    return valid


async def main():
    setup_logging(log_level="INFO")

    print("=" * 60)
    print("TRAIN MODEL")
    print("=" * 60)

    import argparse
    parser = argparse.ArgumentParser(description="Train prediction model")
    parser.add_argument("--train-start", type=str, default="20160101")
    parser.add_argument("--train-end", type=str, default="20241231")
    args = parser.parse_args()

    await init_db()

    all_stocks = await get_active_stocks()
    print(f"Active stocks: {len(all_stocks)}")

    valid_ts_codes = await get_stocks_with_data(all_stocks, args.train_start, args.train_end)
    print(f"Stocks with data: {len(valid_ts_codes)}")
    if not valid_ts_codes:
        print("ERROR: No stocks with sufficient data")
        return

    model_config = await config_service.get_config_by_name(PROD_MODEL_CONFIG_NAME)
    if not model_config:
        model_config = await config_service.create_config(
            name=PROD_MODEL_CONFIG_NAME,
            model_type="xgboost",
            classification_horizons=[3, 5],
            classification_threshold=0.02,
        )
        print(f"Created model config: {model_config.id}")
    else:
        print(f"Using model config: {model_config.id}")

    deleted = await training_service.delete_training_by_name(PROD_TRAINING_NAME)
    if deleted:
        print(f"Deleted old training: {PROD_TRAINING_NAME}")

    train_start_time = datetime.now()
    print(f"Training {len(valid_ts_codes)} stocks from {args.train_start} to {args.train_end}...")
    training = await training_service.create_training(
        config_id=model_config.id,
        name=PROD_TRAINING_NAME,
        ts_codes=valid_ts_codes,
        start_date=args.train_start,
        end_date=args.train_end,
    )
    duration = (datetime.now() - train_start_time).total_seconds()

    print()
    print("=" * 60)
    print("TRAINING COMPLETED")
    print("=" * 60)
    print(f"Training ID: {training.id}")
    print(f"Duration:    {duration:.2f}s")
    print(f"Samples:     {training.metrics.get('sample_count', 'N/A')}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
