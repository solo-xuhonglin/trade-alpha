"""Backtest service module."""

from datetime import datetime, timezone
from typing import List, Optional, Any
from beanie import PydanticObjectId
from trade_alpha.dao import BacktestResult, BacktestTrade, BacktestPortfolioDaily, StockDaily
from trade_alpha.dao.backtest import AccountSnapshotEmbed, StrategySnapshotEmbed
from trade_alpha.dao.backtest_portfolio_daily import Position
from trade_alpha.logging import get_logger
from trade_alpha.account import get_account_config_by_id, AccountManager
from trade_alpha.strategy import get_strategy_instance
from trade_alpha.backtest.engine import BacktestEngine, BacktestResult as EngineBacktestResult

logger = get_logger("backtest_service")


async def get_backtest_by_id(backtest_id: PydanticObjectId) -> Optional[BacktestResult]:
    """Get backtest by ID."""
    return await BacktestResult.get(backtest_id)


async def list_backtests(page: int = 1, page_size: int = 20) -> tuple[List[BacktestResult], int]:
    """List backtests with pagination."""
    total = await BacktestResult.count()
    skip = (page - 1) * page_size
    results = await BacktestResult.find_all().sort(-BacktestResult.id).skip(skip).limit(page_size).to_list()
    return results, total


async def delete_backtest(backtest_id: PydanticObjectId) -> bool:
    """Delete backtest, trades, and daily snapshots."""
    backtest = await BacktestResult.get(backtest_id)
    if not backtest:
        return False

    await BacktestTrade.find(BacktestTrade.backtest_id == backtest_id).delete()
    await BacktestPortfolioDaily.find(BacktestPortfolioDaily.backtest_id == backtest_id).delete()
    await backtest.delete()
    logger.info(f"Backtest deleted: id={backtest_id}")
    return True


async def save_backtest(
    result: EngineBacktestResult,
    account_config: Any,
    strategy: Any,
) -> BacktestResult:
    """Save backtest result with configuration snapshots."""
    logger.info("Saving backtest result")

    backtest = BacktestResult(
        account_config_id=PydanticObjectId(result.account_config_id) if result.account_config_id else None,
        strategy_id=PydanticObjectId(result.strategy_id) if result.strategy_id else None,
        training_id=PydanticObjectId(result.training_id) if result.training_id else None,
        ts_code=result.ts_code,
        start_date=result.start_date,
        end_date=result.end_date,
        initial_capital=result.initial_capital,
        final_value=result.final_value,
        total_return=result.total_return,
        annual_return=result.annual_return,
        benchmark_return=result.benchmark_return,
        max_drawdown=result.max_drawdown,
        sharpe_ratio=result.sharpe_ratio,
        win_rate=result.win_rate,
        total_trades=result.total_trades,
        total_fees=result.total_fees,
        account_snapshot=AccountSnapshotEmbed(
            name=account_config.name,
            initial_capital=account_config.initial_capital,
            buy_fee_rate=account_config.buy_fee_rate,
            sell_fee_rate=account_config.sell_fee_rate,
            stamp_tax_rate=account_config.stamp_tax_rate,
            min_fee=account_config.min_fee,
        ),
        strategy_snapshot=StrategySnapshotEmbed(
            name=strategy.name,
            type=strategy.type,
            config=strategy.config,
        ),
        created_at=datetime.now(timezone.utc),
    )

    await backtest.insert()
    result.backtest_id = str(backtest.id)
    logger.info(f"Backtest result saved: id={backtest.id}")
    return backtest


async def save_daily_snapshots(
    backtest_id: PydanticObjectId,
    daily_snapshots: List[Any],
) -> int:
    """Save daily portfolio snapshots."""
    if not daily_snapshots:
        return 0

    snapshot_docs = []
    for snapshot in daily_snapshots:
        positions = [
            Position(ts_code=p.ts_code, shares=p.shares)
            for p in snapshot.positions
        ]
        doc = BacktestPortfolioDaily(
            backtest_id=backtest_id,
            date=snapshot.date,
            cash=snapshot.cash,
            positions=positions,
            market_value=snapshot.market_value,
            total_value=snapshot.total_value,
            position_ratio=snapshot.position_ratio,
        )
        snapshot_docs.append(doc)

    await BacktestPortfolioDaily.insert_many(snapshot_docs)
    logger.info(f"Saved {len(snapshot_docs)} daily snapshots for backtest: {backtest_id}")
    return len(snapshot_docs)


async def save_trades(
    backtest_id: PydanticObjectId,
    account_config_id: PydanticObjectId,
    trades: List[Any],
    ts_code: str = "",
    strategy_id: Optional[PydanticObjectId] = None,
    training_id: Optional[PydanticObjectId] = None
) -> int:
    """Save trade records."""
    logger.info(f"Saving {len(trades)} trades for backtest: {backtest_id}")

    trade_docs = []
    for trade_record in trades:
        trade_doc = BacktestTrade(
            backtest_id=backtest_id,
            portfolio_id=account_config_id,
            strategy_id=strategy_id,
            training_id=training_id,
            ts_code=ts_code,
            trade_date=trade_record.date,
            action=trade_record.action,
            price=trade_record.price,
            shares=trade_record.shares,
            fee=trade_record.fee,
            cash_after=trade_record.cash_after,
            position_after=trade_record.position_after,
        )
        trade_docs.append(trade_doc)

    if trade_docs:
        await BacktestTrade.insert_many(trade_docs)
        return len(trade_docs)
    return 0


async def run_backtest(
    ts_code: str,
    start_date: str,
    end_date: str,
    account_config_id: PydanticObjectId,
    strategy_id: PydanticObjectId,
    training_id: PydanticObjectId,
) -> EngineBacktestResult:
    """Run backtest with the given parameters."""
    logger.info(f"Starting backtest for {ts_code} from {start_date} to {end_date}")

    account_config = await get_account_config_by_id(account_config_id)
    if not account_config:
        raise ValueError(f"Account config not found: {account_config_id}")

    records = await StockDaily.find(
        StockDaily.ts_code == ts_code,
        StockDaily.trade_date >= start_date,
        StockDaily.trade_date <= end_date,
    ).sort(StockDaily.trade_date).to_list()

    if not records:
        logger.warning(f"No data available for backtest: {ts_code} from {start_date} to {end_date}")
        return EngineBacktestResult(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            strategy_id=str(strategy_id),
            training_id=str(training_id),
            initial_capital=account_config.initial_capital,
            final_value=account_config.initial_capital,
        )

    from trade_alpha.strategy.service import get_strategy_by_id
    strategy_config = await get_strategy_by_id(strategy_id)
    if not strategy_config:
        raise ValueError(f"Strategy config not found: {strategy_id}")

    strategy_obj = await get_strategy_instance(strategy_id)

    logger.debug(f"Using strategy: {strategy_id}")

    portfolio_obj = AccountManager(
        initial_capital=account_config.initial_capital,
        buy_fee_rate=account_config.buy_fee_rate,
        sell_fee_rate=account_config.sell_fee_rate,
        stamp_tax_rate=account_config.stamp_tax_rate,
        min_fee=account_config.min_fee,
    )

    engine = BacktestEngine(ts_code, start_date, end_date, strategy_obj, portfolio_obj)

    result = engine.run([r.model_dump() for r in records])
    result.account_config_id = str(account_config_id)
    result.strategy_id = str(strategy_id)
    result.training_id = str(training_id)

    backtest = await save_backtest(result, account_config, strategy_config)

    await save_trades(
        backtest.id,
        account_config_id,
        portfolio_obj.trades,
        ts_code,
        strategy_id,
        training_id
    )

    await save_daily_snapshots(backtest.id, result.daily_snapshots)

    logger.info(f"Backtest completed: {ts_code}, return rate: {result.total_return:.2%}")
    return result


async def list_account_configs_for_filter() -> List[dict]:
    """List account configs for filter options."""
    from trade_alpha.account.service import list_account_configs
    account_configs = await list_account_configs()
    return [{"id": str(a.id), "name": a.name} for a in account_configs]


async def list_strategies_for_filter() -> List[dict]:
    """List strategies for filter options."""
    from trade_alpha.strategy.service import list_strategies
    strategies = await list_strategies()
    return [{"id": str(s.id), "name": s.name} for s in strategies]


async def list_trainings_for_filter() -> List[dict]:
    """List trainings for filter options."""
    from trade_alpha.predict.training_service import list_trainings
    trainings = await list_trainings()
    return [{"id": str(t.id), "name": t.name} for t in trainings]


async def get_distinct_ts_codes() -> List[str]:
    """Get distinct ts_codes from trades."""
    docs = await BacktestTrade.find_all().to_list()
    return sorted(set(doc.ts_code for doc in docs if doc.ts_code))


async def list_trades(
    page: int = 1,
    page_size: int = 20,
    account_config_id: PydanticObjectId = None,
    strategy_id: PydanticObjectId = None,
    training_id: PydanticObjectId = None,
    ts_code: str = None,
) -> tuple[List[BacktestTrade], int]:
    """List trades with pagination and filtering."""
    query = BacktestTrade.find_all()

    if account_config_id:
        query = query.filter(BacktestTrade.account_config_id == account_config_id)
    if strategy_id:
        query = query.filter(BacktestTrade.strategy_id == strategy_id)
    if training_id:
        query = query.filter(BacktestTrade.training_id == training_id)
    if ts_code:
        query = query.filter(BacktestTrade.ts_code == ts_code)

    total = await query.count()
    skip = (page - 1) * page_size
    results = await query.sort(-BacktestTrade.trade_date).skip(skip).limit(page_size).to_list()
    return results, total


async def list_trades_by_backtest_id(
    backtest_id: PydanticObjectId,
    page: int = 1,
    page_size: int = 20,
) -> tuple[List[BacktestTrade], int]:
    """List trades for a specific backtest."""
    query = BacktestTrade.find(BacktestTrade.backtest_id == backtest_id)
    total = await query.count()
    skip = (page - 1) * page_size
    results = await query.sort(-BacktestTrade.trade_date).skip(skip).limit(page_size).to_list()
    return results, total


async def list_daily_snapshots(
    backtest_id: PydanticObjectId,
    page: int = 1,
    page_size: int = 20,
) -> tuple[List[BacktestPortfolioDaily], int]:
    """List daily snapshots for a backtest."""
    query = BacktestPortfolioDaily.find(BacktestPortfolioDaily.backtest_id == backtest_id)
    total = await query.count()
    skip = (page - 1) * page_size
    results = await query.sort(BacktestPortfolioDaily.date).skip(skip).limit(page_size).to_list()
    return results, total
