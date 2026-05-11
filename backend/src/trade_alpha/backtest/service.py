"""Backtest service module."""

from datetime import datetime, timezone
from typing import List, Optional, Any
from beanie import PydanticObjectId
from trade_alpha.dao import BacktestResult, BacktestTrade, StockDaily
from trade_alpha.logging import get_logger
from trade_alpha.portfolio import get_portfolio_by_id, PortfolioManager
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
    """Delete backtest and its trades."""
    backtest = await BacktestResult.get(backtest_id)
    if not backtest:
        return False

    await BacktestTrade.find(BacktestTrade.backtest_id == backtest_id).delete()
    await backtest.delete()
    logger.info(f"Backtest deleted: id={backtest_id}")
    return True


async def save_backtest(result: EngineBacktestResult) -> BacktestResult:
    """Save backtest result."""
    logger.info("Saving backtest result")

    backtest = BacktestResult(
        portfolio_id=PydanticObjectId(result.portfolio_id) if result.portfolio_id else None,
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
        created_at=datetime.now(timezone.utc),
    )

    await backtest.insert()
    result.backtest_id = str(backtest.id)
    logger.info(f"Backtest result saved: id={backtest.id}")
    return backtest


async def save_trades(
    backtest_id: PydanticObjectId,
    portfolio_id: PydanticObjectId,
    trades: List[Any],
    ts_code: str = "",
    strategy_id: Optional[PydanticObjectId] = None,
    training_id: Optional[PydanticObjectId] = None
) -> int:
    """Save trade records."""
    logger.info(f"Saving {len(trades)} trades for backtest: {backtest_id}")

    trade_docs = []
    for trade in trades:
        trade_doc = BacktestTrade(
            backtest_id=backtest_id,
            portfolio_id=portfolio_id,
            strategy_id=strategy_id,
            training_id=training_id,
            ts_code=ts_code,
            trade_date=trade.date,
            action=trade.action,
            price=trade.price,
            shares=trade.shares,
            fee=trade.fee,
            cash_after=trade.cash_after,
            position_after=trade.position_after,
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
    portfolio_id: PydanticObjectId,
    strategy_id: PydanticObjectId,
    training_id: PydanticObjectId,
) -> EngineBacktestResult:
    """Run backtest with the given parameters."""
    logger.info(f"Starting backtest for {ts_code} from {start_date} to {end_date}")

    portfolio = await get_portfolio_by_id(portfolio_id)
    if not portfolio:
        raise ValueError(f"Portfolio not found: {portfolio_id}")

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
            initial_capital=portfolio.initial_capital,
            final_value=portfolio.initial_capital,
        )

    strategy_obj = await get_strategy_instance(strategy_id)

    logger.debug(f"Using strategy: {strategy_id}")

    portfolio_obj = PortfolioManager(
        initial_capital=portfolio.initial_capital,
        buy_fee_rate=portfolio.buy_fee_rate,
        sell_fee_rate=portfolio.sell_fee_rate,
        stamp_tax_rate=portfolio.stamp_tax_rate,
        min_fee=portfolio.min_fee,
    )

    engine = BacktestEngine(ts_code, start_date, end_date, strategy_obj, portfolio_obj)

    result = engine.run([r.model_dump() for r in records])
    result.portfolio_id = str(portfolio_id)
    result.strategy_id = str(strategy_id)
    result.training_id = str(training_id)

    backtest = await save_backtest(result)
    await save_trades(
        backtest.id,
        portfolio_id,
        portfolio_obj.trades,
        ts_code,
        strategy_id,
        training_id
    )

    logger.info(f"Backtest completed: {ts_code}, return rate: {result.total_return:.2%}")
    return result


async def list_portfolios_for_filter() -> List[dict]:
    """List portfolios for filter options."""
    from trade_alpha.portfolio.service import list_portfolios
    portfolios = await list_portfolios()
    return [{"id": str(p.id), "name": p.name} for p in portfolios]


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
    portfolio_id: PydanticObjectId = None,
    strategy_id: PydanticObjectId = None,
    training_id: PydanticObjectId = None,
    ts_code: str = None,
) -> tuple[List[BacktestTrade], int]:
    """List trades with pagination and filtering."""
    query = BacktestTrade.find_all()

    if portfolio_id:
        query = query.filter(BacktestTrade.portfolio_id == portfolio_id)
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
