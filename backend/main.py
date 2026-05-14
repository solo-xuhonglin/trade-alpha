"""Main entry point for stock prediction and trading signal."""

import asyncio
import argparse
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from beanie import PydanticObjectId
from trade_alpha.dao import init_db, StockList, StockDaily
from trade_alpha.dao.execution import ExecutionResult
from trade_alpha.account import service as account_service
from trade_alpha.predict import config_service, training_service
from trade_alpha.execution.pipeline import ExecutionPipeline
from trade_alpha.logging import get_logger

logger = get_logger("main")


async def get_active_stocks() -> List[StockList]:
    """Get all active stocks, excluding test stock."""
    return await StockList.find(
        StockList.sync_status == "active",
        StockList.ts_code != "002594.SZ"
    ).sort(-StockList.total_mv).to_list()


async def check_stock_data(ts_code: str, start_date: str, end_date: str, min_records: int = 30) -> bool:
    """Check if a stock has sufficient data in the date range."""
    count = await StockDaily.find(
        StockDaily.ts_code == ts_code,
        StockDaily.trade_date >= start_date,
        StockDaily.trade_date <= end_date
    ).count()
    return count >= min_records


async def filter_stocks_with_data(stocks: List[StockList], train_start: str, train_end: str, backtest_start: str, backtest_end: str) -> List[str]:
    """Filter stocks that have data in both training and backtest periods."""
    valid_stocks = []
    for stock in stocks:
        has_train_data = await check_stock_data(stock.ts_code, train_start, train_end)
        has_backtest_data = await check_stock_data(stock.ts_code, backtest_start, backtest_end)
        if has_train_data and has_backtest_data:
            valid_stocks.append(stock.ts_code)
    return valid_stocks


async def train_model(
    ts_codes: List[str],
    train_start: str,
    train_end: str,
    model_config_id: PydanticObjectId,
    training_name: str = "prod_training"
) -> Tuple:
    """Train model and return training record with duration.

    Args:
        ts_codes: List of stock codes to train on
        train_start: Training start date
        train_end: Training end date
        model_config_id: Model config ID
        training_name: Name for the training record

    Returns:
        Tuple of (training_record, duration_seconds)
    """
    trainings = await training_service.list_trainings(config_id=model_config_id)
    training = next((t for t in trainings if t.name == training_name), None)

    if not training:
        train_start_time = datetime.now()
        logger.info(f"Training model on {len(ts_codes)} stocks from {train_start} to {train_end}")
        training = await training_service.create_training(
            config_id=model_config_id,
            name=training_name,
            ts_codes=ts_codes,
            start_date=train_start,
            end_date=train_end
        )
        train_end_time = datetime.now()
        duration = (train_end_time - train_start_time).total_seconds()
        logger.info(f"Training completed in {duration:.2f}s, training_id={training.id}")
        return training, duration
    else:
        logger.info(f"Using existing training: {training.id}")
        return training, None


async def run_portfolio_backtest(
    training_id: PydanticObjectId,
    account_config_id: PydanticObjectId,
    model_config_id: PydanticObjectId,
    start_date: str,
    end_date: str,
    ts_codes: List[str],
    max_positions: int = 10,
    name: str = "prod_backtest"
) -> Tuple[ExecutionResult, float]:
    """Run portfolio backtest and return results with duration.

    Args:
        training_id: Training record ID
        account_config_id: Account config ID
        model_config_id: Model config ID
        start_date: Backtest start date
        end_date: Backtest end date
        ts_codes: List of stock codes to trade
        max_positions: Maximum number of positions
        name: Backtest name

    Returns:
        Tuple of (ExecutionResult, duration_seconds)
    """
    logger.info(f"Running portfolio backtest: {start_date} to {end_date}, max_positions={max_positions}")

    account_config = await account_service.get_account_config_by_id(account_config_id)
    model_config = await config_service.get_config_by_id(model_config_id)

    pipeline = ExecutionPipeline(
        account_config=account_config,
        training_id=training_id,
        model_config=model_config,
        mode="portfolio",
        ts_codes=ts_codes,
        max_positions=max_positions
    )

    backtest_start_time = datetime.now()
    backtest_result = await pipeline.run_backtest(
        start_date=start_date,
        end_date=end_date,
        name=name
    )
    backtest_end_time = datetime.now()
    duration = (backtest_end_time - backtest_start_time).total_seconds()

    logger.info(f"Portfolio backtest completed in {duration:.2f}s, return={backtest_result.total_return:.2%}")

    return backtest_result, duration


async def run_single_stock_backtest(
    ts_code: str,
    training_id: PydanticObjectId,
    account_config_id: PydanticObjectId,
    model_config_id: PydanticObjectId,
    start_date: str,
    end_date: str,
    all_ts_codes: List[str],
    name: str = None
) -> Tuple[ExecutionResult, float]:
    """Run single-stock backtest with baseline comparison.

    Args:
        ts_code: Target stock code
        training_id: Training record ID
        account_config_id: Account config ID
        model_config_id: Model config ID
        start_date: Backtest start date
        end_date: Backtest end date
        all_ts_codes: All stock codes for cross-sectional normalization
        name: Backtest name (auto-generated if None)

    Returns:
        Tuple of (ExecutionResult, duration_seconds)
    """
    stock = await StockList.find_one(StockList.ts_code == ts_code)
    stock_name = stock.name if stock else ts_code

    if name is None:
        name = f"single_{ts_code}_{start_date}_{end_date}"

    logger.info(f"Running single-stock backtest for {ts_code} ({stock_name}): {start_date} to {end_date}")

    account_config = await account_service.get_account_config_by_id(account_config_id)
    model_config = await config_service.get_config_by_id(model_config_id)

    pipeline = ExecutionPipeline(
        account_config=account_config,
        training_id=training_id,
        model_config=model_config,
        mode="single",
        ts_codes=[ts_code],
    )

    backtest_start_time = datetime.now()
    backtest_result = await pipeline.run_backtest(
        start_date=start_date,
        end_date=end_date,
        name=name
    )
    backtest_end_time = datetime.now()
    duration = (backtest_end_time - backtest_start_time).total_seconds()

    logger.info(f"Single-stock backtest completed in {duration:.2f}s, return={backtest_result.total_return:.2%}")

    return backtest_result, duration


def print_backtest_results(backtest_result: ExecutionResult, duration: float = None, train_duration: float = None):
    """Print backtest results in formatted table."""
    print()
    print("=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)
    print(f"Initial Capital: ${backtest_result.initial_capital:,.2f}")
    print(f"Final Value:     ${backtest_result.final_value:,.2f}")
    print(f"Total Return:    {backtest_result.total_return:.2%}")
    print(f"Max Drawdown:    {backtest_result.max_drawdown:.2%}")
    print(f"Sharpe Ratio:    {backtest_result.sharpe_ratio:.2f}" if backtest_result.sharpe_ratio else "")
    print(f"Volatility:      {backtest_result.volatility:.2%}" if backtest_result.volatility else "")
    print(f"Avg Hold Days:   {backtest_result.avg_hold_days:.1f}" if backtest_result.avg_hold_days else "")
    print(f"Win Rate:        {backtest_result.win_rate:.2%}")
    print(f"Total Trades:    {backtest_result.total_trades}")
    print(f"Total Fees:      ${backtest_result.total_fees:,.2f}")
    print(f"Status:          {backtest_result.status}")

    if backtest_result.baseline_return is not None:
        print()
        print("-" * 60)
        print("BASELINE COMPARISON (Buy-and-Hold)")
        print("-" * 60)
        print(f"Baseline Return: {backtest_result.baseline_return:.2%}")
        print(f"Excess Return:  {backtest_result.excess_return:.2%}")
        print(f"Baseline Max DD:{backtest_result.baseline_max_drawdown:.2%}")

    print()
    if train_duration:
        print(f"Training time:   {train_duration:.2f}s")
    if duration:
        print(f"Backtest time:   {duration:.2f}s")
    print("=" * 60)


async def main():
    """Main entry point with CLI support."""
    parser = argparse.ArgumentParser(description="Stock prediction and backtest")
    parser.add_argument("--mode", type=str, default="full",
                        choices=["full", "train", "portfolio", "single", "single-batch"],
                        help="Execution mode")
    parser.add_argument("--training-id", type=str, default=None,
                        help="Existing training ID")
    parser.add_argument("--ts-code", type=str, default=None,
                        help="Stock code for single mode")
    parser.add_argument("--train-start", type=str, default="20160101",
                        help="Training start date (YYYYMMDD)")
    parser.add_argument("--train-end", type=str, default="20241231",
                        help="Training end date (YYYYMMDD)")
    parser.add_argument("--backtest-start", type=str, default="20250101",
                        help="Backtest start date (YYYYMMDD)")
    parser.add_argument("--backtest-end", type=str, default="20250331",
                        help="Backtest end date (YYYYMMDD)")
    parser.add_argument("--max-positions", type=int, default=10,
                        help="Maximum number of positions")

    args = parser.parse_args()

    from trade_alpha.logging import setup_logging
    setup_logging(log_level="INFO")

    await init_db()

    print("=" * 60)
    print("STOCK PREDICTION & BACKTEST SYSTEM")
    print("=" * 60)
    print(f"Mode: {args.mode}")
    print(f"Training period: {args.train_start} - {args.train_end}")
    print(f"Backtest period: {args.backtest_start} - {args.backtest_end}")
    print()

    if args.mode == "full":
        all_stocks = await get_active_stocks()
        print(f"Found {len(all_stocks)} active stocks")

        valid_ts_codes = await filter_stocks_with_data(
            all_stocks, args.train_start, args.train_end, args.backtest_start, args.backtest_end
        )
        print(f"Found {len(valid_ts_codes)} stocks with complete data")
        if not valid_ts_codes:
            print("ERROR: No valid stocks found!")
            return

        account_config = await account_service.get_account_config_by_name("prod_portfolio")
        if not account_config:
            account_config = await account_service.create_account_config(
                name="prod_portfolio",
                initial_capital=100000.0
            )
            print(f"Created account config: {account_config.id}")
        else:
            print(f"Using account config: {account_config.id}")

        model_config = await config_service.get_config_by_name("prod_model_config")
        if not model_config:
            model_config = await config_service.create_config(
                name="prod_model_config",
                model_type="xgboost",
                classification_horizons=[3, 5],
                classification_threshold=0.02
            )
            print(f"Created model config: {model_config.id}")
        else:
            print(f"Using model config: {model_config.id}")

        training, train_duration = await train_model(
            valid_ts_codes, args.train_start, args.train_end,
            model_config.id, "prod_training"
        )

        backtest_result, backtest_duration = await run_portfolio_backtest(
            training.id, account_config.id, model_config.id,
            args.backtest_start, args.backtest_end, valid_ts_codes,
            args.max_positions, "prod_backtest"
        )

        print_backtest_results(backtest_result, backtest_duration, train_duration)

    elif args.mode == "train":
        all_stocks = await get_active_stocks()
        print(f"Found {len(all_stocks)} active stocks")

        valid_ts_codes = await filter_stocks_with_data(
            all_stocks, args.train_start, args.train_end, args.backtest_start, args.backtest_end
        )
        print(f"Found {len(valid_ts_codes)} stocks with complete data")
        if not valid_ts_codes:
            print("ERROR: No valid stocks found!")
            return

        model_config = await config_service.get_config_by_name("prod_model_config")
        if not model_config:
            model_config = await config_service.create_config(
                name="prod_model_config",
                model_type="xgboost",
                classification_horizons=[3, 5],
                classification_threshold=0.02
            )
            print(f"Created model config: {model_config.id}")
        else:
            print(f"Using model config: {model_config.id}")

        training, duration = await train_model(
            valid_ts_codes, args.train_start, args.train_end,
            model_config.id, "prod_training"
        )

        print()
        print("=" * 60)
        print("TRAINING RESULTS")
        print("=" * 60)
        print(f"Training ID: {training.id}")
        if duration:
            print(f"Duration: {duration:.2f}s")
        print("=" * 60)

    elif args.mode == "portfolio":
        if not args.training_id:
            print("ERROR: --training-id is required for portfolio mode")
            return

        from beanie import PydanticObjectId
        training_id = PydanticObjectId(args.training_id)

        all_stocks = await get_active_stocks()
        valid_ts_codes = await filter_stocks_with_data(
            all_stocks, args.train_start, args.train_end, args.backtest_start, args.backtest_end
        )
        print(f"Found {len(valid_ts_codes)} stocks with complete data")

        account_config = await account_service.get_account_config_by_name("prod_portfolio")
        if not account_config:
            account_config = await account_service.create_account_config(
                name="prod_portfolio",
                initial_capital=100000.0
            )

        model_config = await config_service.get_config_by_name("prod_model_config")

        backtest_result, duration = await run_portfolio_backtest(
            training_id, account_config.id, model_config.id,
            args.backtest_start, args.backtest_end, valid_ts_codes,
            args.max_positions, "prod_backtest"
        )

        print_backtest_results(backtest_result, duration)

    elif args.mode == "single":
        if not args.training_id or not args.ts_code:
            print("ERROR: --training-id and --ts-code are required for single mode")
            return

        from beanie import PydanticObjectId
        training_id = PydanticObjectId(args.training_id)

        all_stocks = await get_active_stocks()
        valid_ts_codes = await filter_stocks_with_data(
            all_stocks, args.train_start, args.train_end, args.backtest_start, args.backtest_end
        )

        account_config = await account_service.get_account_config_by_name("prod_portfolio")
        if not account_config:
            account_config = await account_service.create_account_config(
                name="prod_portfolio",
                initial_capital=100000.0
            )

        model_config = await config_service.get_config_by_name("prod_model_config")

        backtest_result, duration = await run_single_stock_backtest(
            args.ts_code, training_id, account_config.id, model_config.id,
            args.backtest_start, args.backtest_end, valid_ts_codes
        )

        print_backtest_results(backtest_result, duration)

    elif args.mode == "single-batch":
        if not args.training_id:
            print("ERROR: --training-id is required for single-batch mode")
            return

        from beanie import PydanticObjectId
        training_id = PydanticObjectId(args.training_id)

        all_stocks = await get_active_stocks()
        valid_ts_codes = await filter_stocks_with_data(
            all_stocks, args.train_start, args.train_end, args.backtest_start, args.backtest_end
        )
        print(f"Found {len(valid_ts_codes)} stocks for single-stock backtest")

        account_config = await account_service.get_account_config_by_name("prod_portfolio")
        if not account_config:
            account_config = await account_service.create_account_config(
                name="prod_portfolio",
                initial_capital=100000.0
            )

        model_config = await config_service.get_config_by_name("prod_model_config")

        results = []
        for i, ts_code in enumerate(valid_ts_codes):
            print(f"[{i+1}/{len(valid_ts_codes)}] Running backtest for {ts_code}...")
            try:
                backtest_result, duration = await run_single_stock_backtest(
                    ts_code, training_id, account_config.id, model_config.id,
                    args.backtest_start, args.backtest_end, valid_ts_codes
                )
                results.append(backtest_result)
            except Exception as e:
                print(f"  ERROR: {e}")

        print()
        print("=" * 60)
        print("BATCH SINGLE-STOCK BACKTEST RESULTS")
        print("=" * 60)
        print(f"{'Code':<12} {'Strategy':<12} {'Baseline':<12} {'Excess':<12}")
        print("-" * 60)
        for r in sorted(results, key=lambda x: x.excess_return or 0, reverse=True):
            strategy = f"{r.total_return:.2%}" if r.total_return else "N/A"
            baseline = f"{r.baseline_return:.2%}" if r.baseline_return else "N/A"
            excess = f"{r.excess_return:.2%}" if r.excess_return else "N/A"
            print(f"{r.ts_code:<12} {strategy:<12} {baseline:<12} {excess:<12}")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
