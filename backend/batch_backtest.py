import asyncio
import sys
sys.path.insert(0, 'src')
from trade_alpha.dao import init_db
from trade_alpha.predict import config_service, training_service
from trade_alpha.account import service as account_service
from trade_alpha.execution.pipeline import ExecutionPipeline
from trade_alpha.logging import setup_logging

setup_logging(log_level='WARNING')

STOCKS = [
    "000858.SZ",  # 五粮液
    "002594.SZ",  # 比亚迪
    "601318.SH",  # 中国平安
    "300750.SZ",  # 宁德时代
]

async def test_single_stock(ts_code: str):
    from trade_alpha.dao import init_db
    await init_db()
    
    account_config = await account_service.get_account_config_by_name('prod_portfolio')
    model_config = await config_service.get_config_by_name('prod_model_config')
    trainings = await training_service.list_trainings()
    training = next(t for t in trainings if t.name == 'prod_training')
    
    pipeline = ExecutionPipeline(
        account_config=account_config,
        training_id=training.id,
        model_config=model_config,
        mode='single',
        ts_codes=[ts_code],
    )
    
    result = await pipeline.run_backtest('20250101', '20250331')
    
    return {
        "ts_code": ts_code,
        "total_return": result.total_return,
        "baseline_return": result.baseline_return,
        "excess_return": result.excess_return,
        "total_trades": result.total_trades,
        "sharpe_ratio": result.sharpe_ratio,
        "volatility": result.volatility,
        "max_drawdown": result.max_drawdown,
        "baseline_max_drawdown": result.baseline_max_drawdown,
        "avg_hold_days": result.avg_hold_days,
    }

async def main():
    results = []
    for stock in STOCKS:
        print(f"\nTesting {stock}...")
        try:
            result = await test_single_stock(stock)
            results.append(result)
            print(f"  Return: {result['total_return']:.2%} | Baseline: {result['baseline_return']:.2%} | Excess: {result['excess_return']:+.2%}")
            print(f"  Trades: {result['total_trades']} | Sharpe: {result['sharpe_ratio']} | Vol: {result['volatility']:.2%}")
            print(f"  MaxDD: {result['max_drawdown']:.2%} | Baseline MaxDD: {result['baseline_max_drawdown']:.2%}")
        except Exception as e:
            print(f"  Error: {e}")
    
    if results:
        print("\n" + "="*80)
        print("SUMMARY COMPARISON")
        print("="*80)
        print(f"{'Stock':<15} {'Strategy':<10} {'Baseline':<10} {'Excess':<10} {'Trades':<8} {'Sharpe':<8} {'MaxDD':<10} {'B.MDD':<10}")
        print("-"*80)
        for r in results:
            print(f"{r['ts_code']:<15} {r['total_return']:>8.2%} {r['baseline_return']:>8.2%} {r['excess_return']:>+8.2%} {r['total_trades']:>6} {r['sharpe_ratio']:>7.3f} {r['max_drawdown']:>8.2%} {r['baseline_max_drawdown']:>8.2%}")

asyncio.run(main())
