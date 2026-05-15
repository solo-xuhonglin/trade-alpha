"""Evaluate single-stock strategy performance."""
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

logger = get_logger("backtest_single")


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


async def run_single_backtest(ts_code, training_id, account_config, model_config, backtest_start, backtest_end):
    stock = await StockList.find_one(StockList.ts_code == ts_code)
    stock_name = stock.name if stock else ts_code

    pipeline = ExecutionPipeline(
        account_config=account_config,
        training_id=training_id,
        model_config=model_config,
        mode="single",
        ts_codes=[ts_code],
    )

    result = await pipeline.run_backtest(
        start_date=backtest_start,
        end_date=backtest_end,
    )

    return result, stock_name


def print_single_result(result, stock_name, duration):
    print()
    print("-" * 60)
    print(f"{stock_name} ({result.ts_code})")
    print("-" * 60)
    print(f"Strategy Return:     {result.total_return:.2%}")
    print(f"Baseline Return:     {result.baseline_return:.2%}" if result.baseline_return else "")
    print(f"Excess Return:       {result.excess_return:.2%}" if result.excess_return else "")
    print(f"Max Drawdown:        {result.max_drawdown:.2%}")
    print(f"Baseline Max DD:     {result.baseline_max_drawdown:.2%}" if result.baseline_max_drawdown else "")
    print(f"Sharpe Ratio:        {result.sharpe_ratio:.2f}" if result.sharpe_ratio else "")
    print(f"Volatility:          {result.volatility:.2%}" if result.volatility else "")
    print(f"Total Trades:        {result.total_trades}")
    print(f"Avg Hold Days:       {result.avg_hold_days:.1f}" if result.avg_hold_days else "")
    print(f"Duration:            {duration:.2f}s")


def print_batch_summary(results):
    print()
    print("=" * 80)
    print("BATCH SINGLE-STOCK BACKTEST SUMMARY")
    print("=" * 80)
    print(f"{'Stock':<15} {'Strategy':<10} {'Baseline':<10} {'Excess':<10} {'Trades':<8} {'Sharpe':<8}")
    print("-" * 80)
    for r in sorted(results, key=lambda x: x["excess_return"] or 0, reverse=True):
        strategy = f"{r['total_return']:.2%}" if r["total_return"] else "N/A"
        baseline = f"{r['baseline_return']:.2%}" if r["baseline_return"] else "N/A"
        excess = f"{r['excess_return']:.2%}" if r["excess_return"] else "N/A"
        print(f"{r['ts_code']:<15} {strategy:>8} {baseline:>8} {excess:>8} {r['total_trades']:>6} {r['sharpe']:>7.2f}")
    print("=" * 80)


async def main():
    setup_logging(log_level="WARNING")

    import argparse
    parser = argparse.ArgumentParser(description="Single-stock strategy evaluation")
    parser.add_argument("--ts-code", type=str, default=None, help="Stock code (omit for batch mode)")
    parser.add_argument("--backtest-start", type=str, default="20250101")
    parser.add_argument("--backtest-end", type=str, default="20250331")
    args = parser.parse_args()

    await init_db()

    training = await training_service.get_training_by_name(PROD_TRAINING_NAME)
    if not training:
        print(f"ERROR: Training '{PROD_TRAINING_NAME}' not found. Run train_model.py first.")
        return
    print(f"Using training: {training.id}")

    account_config = await ensure_account_config()
    model_config = await config_service.get_config_by_name(PROD_MODEL_CONFIG_NAME)

    if args.ts_code:
        print(f"\nRunning single backtest for {args.ts_code}...")
        start = datetime.now()
        result, stock_name = await run_single_backtest(
            args.ts_code, training.id, account_config, model_config,
            args.backtest_start, args.backtest_end,
        )
        duration = (datetime.now() - start).total_seconds()
        print_single_result(result, stock_name, duration)
    else:
        print("\nRunning batch single-stock backtest...")
        all_stocks = await get_active_stocks()
        valid_ts_codes = await get_stocks_with_data(
            all_stocks, args.backtest_start, args.backtest_end,
        )
        print(f"Testing {len(valid_ts_codes)} stocks...")

        results = []
        for i, ts_code in enumerate(valid_ts_codes):
            print(f"  [{i+1}/{len(valid_ts_codes)}] {ts_code}...", end=" ")
            try:
                start = datetime.now()
                result, stock_name = await run_single_backtest(
                    ts_code, training.id, account_config, model_config,
                    args.backtest_start, args.backtest_end,
                )
                duration = (datetime.now() - start).total_seconds()
                results.append({
                    "ts_code": ts_code,
                    "total_return": result.total_return,
                    "baseline_return": result.baseline_return,
                    "excess_return": result.excess_return,
                    "total_trades": result.total_trades,
                    "sharpe": result.sharpe_ratio or 0,
                })
                print(f"return={result.total_return:.2%} ({duration:.1f}s)")
            except Exception as e:
                print(f"ERROR: {e}")

        print_batch_summary(results)


if __name__ == "__main__":
    asyncio.run(main())
