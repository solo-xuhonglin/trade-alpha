"""Backtest service module for persistence."""

from typing import List
from trade_alpha.dao import MongoDB
from trade_alpha.dao.stock_daily_dao import StockDailyDAO
from trade_alpha.portfolio import Trade
from trade_alpha.backtest.engine import BacktestResult


def save_backtest(result: BacktestResult) -> str:
    """Save backtest result."""
    from bson import ObjectId

    dao = MongoDB()
    collection = dao._get_collection("backtests")

    backtest_doc = {
        "portfolio_id": ObjectId(result.portfolio_id) if result.portfolio_id else None,
        "portfolio_name": result.portfolio_name if hasattr(result, 'portfolio_name') else None,
        "ts_code": result.ts_code,
        "start_date": result.start_date,
        "end_date": result.end_date,
        "strategy": result.strategy,
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

    result_obj = collection.insert_one(backtest_doc)
    backtest_id = str(result_obj.inserted_id)
    result.backtest_id = backtest_id
    dao.close()
    return backtest_id


def save_trades(backtest_id: str, portfolio_id: str, trades: List[Trade], ts_code: str = "") -> None:
    """Save trade records."""
    from bson import ObjectId

    dao = MongoDB()
    collection = dao._get_collection("backtest_trades")

    trade_docs = []
    for trade in trades:
        trade_doc = {
            "backtest_id": ObjectId(backtest_id),
            "portfolio_id": ObjectId(portfolio_id) if portfolio_id else None,
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
        collection.insert_many(trade_docs)

    dao.close()


def run_backtest(
    ts_code: str,
    start_date: str,
    end_date: str,
    strategy: str = "price",
    portfolio_name: str = "default",
    initial_capital: float = 100000,
) -> BacktestResult:
    """Run backtest with the given parameters."""
    from trade_alpha.backtest.engine import BacktestEngine
    from trade_alpha.portfolio import get_or_create_portfolio
    from trade_alpha.strategy import STRATEGIES

    portfolio_id, portfolio = get_or_create_portfolio(portfolio_name, initial_capital)

    dao = StockDailyDAO()
    records = dao.find_by_ts_code(ts_code)
    filtered_records = [
        r for r in records
        if start_date <= r["trade_date"] <= end_date
    ]

    if not filtered_records:
        return BacktestResult(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            strategy=strategy,
            initial_capital=initial_capital,
            final_value=initial_capital,
        )

    strategy_cls = STRATEGIES.get(strategy)
    if strategy_cls is None:
        raise ValueError(f"Unknown strategy: {strategy}")

    strategy_obj = strategy_cls()
    engine = BacktestEngine(ts_code, start_date, end_date, strategy_obj, portfolio)

    result = engine.run(filtered_records)
    result.portfolio_id = portfolio_id
    result.portfolio_name = portfolio_name
    result.strategy = strategy

    backtest_id = save_backtest(result)
    save_trades(backtest_id, portfolio_id, portfolio.trades, ts_code)

    return result
