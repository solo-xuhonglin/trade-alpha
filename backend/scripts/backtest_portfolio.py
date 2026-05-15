"""Evaluate portfolio strategy performance."""
import asyncio
from datetime import datetime

from beanie.odm.operators.find.comparison import NotIn

from trade_alpha.dao import init_db, StockList, StockDaily
from trade_alpha.predict import training_service, config_service
from trade_alpha.account import service as account_service
from trade_alpha.execution.pipeline import ExecutionPipeline
from trade_alpha.logging import setup_logging, get_logger
from trade_alpha.test_config import (
    PROD_TRAINING_NAME, PROD_ACCOUNT_CONFIG_NAME, PROD_MODEL_CONFIG_NAME,
    TEST_EXCLUDED_TS_CODES,
)

logger = get_logger("backtest_portfolio")


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


async def ensure_account_config():
    config = await account_service.get_account_config_by_name(PROD_ACCOUNT_CONFIG_NAME)
    if not config:
        config = await account_service.create_account_config(
            name=PROD_ACCOUNT_CONFIG_NAME,
            initial_capital=100000.0,
        )
        print(f"Created account config: {config.id}")
    else:
        print(f"Using account config: {config.id}")
    return config


def print_results(result, duration, train_duration=None):
    print()
    print("=" * 60)
    print("PORTFOLIO BACKTEST RESULTS")
    print("=" * 60)
    print(f"Initial Capital:   ${result.initial_capital:,.2f}")
    print(f"Final Value:       ${result.final_value:,.2f}")
    print(f"Total Return:      {result.total_return:.2%}")
    print(f"Max Drawdown:      {result.max_drawdown:.2%}")
    print(f"Sharpe Ratio:      {result.sharpe_ratio:.2f}" if result.sharpe_ratio else "")
    print(f"Volatility:        {result.volatility:.2%}" if result.volatility else "")
    print(f"Win Rate:          {result.win_rate:.2%}")
    print(f"Total Trades:      {result.total_trades}")
    print(f"Total Fees:        ${result.total_fees:,.2f}")

    if result.baseline_return is not None:
        print()
        print("-" * 60)
        print("BASELINE COMPARISON (Buy-and-Hold)")
        print("-" * 60)
        print(f"Baseline Return:   {result.baseline_return:.2%}")
        print(f"Excess Return:     {result.excess_return:.2%}")
        print(f"Baseline Max DD:   {result.baseline_max_drawdown:.2%}")

    print()
    if train_duration:
        print(f"Training time:     {train_duration:.2f}s")
    print(f"Backtest time:     {duration:.2f}s")
    print("=" * 60)


async def main():
    setup_logging(log_level="INFO")

    import argparse
    parser = argparse.ArgumentParser(description="Portfolio strategy evaluation")
    parser.add_argument("--backtest-start", type=str, default="20250101")
    parser.add_argument("--backtest-end", type=str, default="20250331")
    parser.add_argument("--max-positions", type=int, default=10)
    args = parser.parse_args()

    await init_db()

    training = await training_service.get_training_by_name(PROD_TRAINING_NAME)
    if not training:
        print(f"ERROR: Training '{PROD_TRAINING_NAME}' not found. Run train_model.py first.")
        return
    print(f"Using training: {training.id}")

    account_config = await ensure_account_config()
    model_config = await config_service.get_config_by_name(PROD_MODEL_CONFIG_NAME)

    all_stocks = await get_active_stocks()
    valid_ts_codes = await get_stocks_with_data(
        all_stocks, args.backtest_start, args.backtest_end,
    )
    print(f"Found {len(valid_ts_codes)} stocks with data")

    pipeline = ExecutionPipeline(
        account_config=account_config,
        training_id=training.id,
        model_config=model_config,
        mode="portfolio",
        ts_codes=valid_ts_codes,
        max_positions=args.max_positions,
    )

    backtest_start = datetime.now()
    result = await pipeline.run_backtest(
        start_date=args.backtest_start,
        end_date=args.backtest_end,
    )
    duration = (datetime.now() - backtest_start).total_seconds()

    print_results(result, duration)


if __name__ == "__main__":
    asyncio.run(main())
