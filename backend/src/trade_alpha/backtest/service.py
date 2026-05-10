"""Backtest service module for persistence."""

from typing import List
from bson import ObjectId
from trade_alpha.dao import (
    BacktestDAO,
    BacktestTradeDAO,
    PortfolioDAO,
    StrategyDAO,
    StockDailyDAO,
)
from trade_alpha.logging import get_logger
from trade_alpha.portfolio import Trade, Portfolio
from trade_alpha.backtest.engine import BacktestResult

logger = get_logger("backtest_service")


def save_backtest(result: BacktestResult) -> str:
    """Save backtest result."""
    logger.info("Saving backtest result")

    dao = BacktestDAO()

    backtest_doc = {
        "portfolio_id": ObjectId(result.portfolio_id) if result.portfolio_id else None,
        "strategy_id": ObjectId(result.strategy_id) if result.strategy_id else None,
        "training_id": ObjectId(result.training_id) if result.training_id else None,
        "ts_code": result.ts_code,
        "start_date": result.start_date,
        "end_date": result.end_date,
        "initial_capital": result.initial_capital,
        "final_value": result.final_value,
        "total_return": result.total_return,
        "annual_return": result.annual_return,
        "benchmark_return": result.benchmark_return,
        "max_drawdown": result.max_drawdown,
        "sharpe_ratio": result.sharpe_ratio,
        "win_rate": result.win_rate,
        "total_trades": result.total_trades,
        "total_fees": result.total_fees,
    }

    backtest_id = dao.insert(backtest_doc)
    result.backtest_id = backtest_id
    logger.info(f"Backtest result saved: {backtest_id}")
    return backtest_id


def save_trades(
    backtest_id: str,
    portfolio_id: str,
    trades: List[Trade],
    ts_code: str = "",
    strategy_id: str = "",
    training_id: str = ""
) -> None:
    """Save trade records."""
    logger.info(f"Saving {len(trades)} trades for backtest: {backtest_id}")

    dao = BacktestTradeDAO()

    trade_docs = []
    for trade in trades:
        trade_doc = {
            "backtest_id": ObjectId(backtest_id),
            "portfolio_id": ObjectId(portfolio_id) if portfolio_id else None,
            "strategy_id": ObjectId(strategy_id) if strategy_id else None,
            "training_id": ObjectId(training_id) if training_id else None,
            "ts_code": ts_code,
            "trade_date": trade.date,
            "action": trade.action,
            "price": trade.price,
            "shares": trade.shares,
            "fee": trade.fee,
            "cash_after": trade.cash_after,
            "position_after": trade.position_after,
        }
        trade_docs.append(trade_doc)

    if trade_docs:
        dao.insert_many(trade_docs)


def get_portfolio_by_id(portfolio_id: str) -> Portfolio:
    """Get portfolio by ID."""
    from bson.errors import InvalidId

    try:
        ObjectId(portfolio_id)
    except InvalidId:
        raise ValueError(f"Invalid portfolio ID: {portfolio_id}")

    dao = PortfolioDAO()
    doc = dao.find_by_id(portfolio_id)

    if not doc:
        raise ValueError(f"Portfolio not found: {portfolio_id}")

    return Portfolio(
        initial_capital=doc.get("initial_capital", 100000),
        buy_fee_rate=doc.get("buy_fee_rate", 0.0003),
        sell_fee_rate=doc.get("sell_fee_rate", 0.0003),
        stamp_tax_rate=doc.get("stamp_tax_rate", 0.001),
        min_fee=doc.get("min_fee", 5.0),
    )


def get_strategy_by_id(strategy_id: str):
    """Get strategy class by ID."""
    from bson.errors import InvalidId

    try:
        ObjectId(strategy_id)
    except InvalidId:
        raise ValueError(f"Invalid strategy ID: {strategy_id}")

    dao = StrategyDAO()
    doc = dao.find_by_id(strategy_id)

    if not doc:
        raise ValueError(f"Strategy not found: {strategy_id}")

    strategy_type = doc.get("type", "price")
    from trade_alpha.strategy import STRATEGIES

    strategy_cls = STRATEGIES.get(strategy_type)
    if strategy_cls is None:
        raise ValueError(f"Unknown strategy type: {strategy_type}")

    return strategy_cls


def run_backtest(
    ts_code: str,
    start_date: str,
    end_date: str,
    portfolio_id: str,
    strategy_id: str,
    training_id: str,
) -> BacktestResult:
    """Run backtest with the given parameters."""
    logger.info(f"Starting backtest for {ts_code} from {start_date} to {end_date}")
    from trade_alpha.backtest.engine import BacktestEngine

    portfolio = get_portfolio_by_id(portfolio_id)

    dao = StockDailyDAO()
    records = dao.find_by_ts_code(ts_code)
    filtered_records = [
        r for r in records
        if start_date <= r["trade_date"] <= end_date
    ]

    if not filtered_records:
        logger.warning(f"No data available for backtest: {ts_code} from {start_date} to {end_date}")
        return BacktestResult(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            strategy_id=strategy_id,
            training_id=training_id,
            initial_capital=portfolio.initial_capital,
            final_value=portfolio.initial_capital,
        )

    strategy_cls = get_strategy_by_id(strategy_id)

    logger.debug(f"Using strategy: {strategy_id}")
    strategy_obj = strategy_cls()
    engine = BacktestEngine(ts_code, start_date, end_date, strategy_obj, portfolio)

    result = engine.run(filtered_records)
    result.portfolio_id = portfolio_id
    result.strategy_id = strategy_id
    result.training_id = training_id

    backtest_id = save_backtest(result)
    save_trades(backtest_id, portfolio_id, portfolio.trades, ts_code, strategy_id, training_id)

    logger.info(f"Backtest completed: {ts_code}, return rate: {result.total_return:.2%}")
    return result
