"""清理除股票数据外的所有业务数据。

保留的集合:
  - stock_daily (日线数据)
  - stock_list (股票列表)

清理的集合:
  - account_configs (账户配置)
  - strategy_configs (策略配置)
  - model_configs (模型配置)
  - training_results (训练结果)
  - prediction_results (预测结果)
  - signal_results (信号结果)
  - execution_results (回测结果)
  - execution_trades (交易记录)
  - execution_portfolio_dailies (每日持仓)
  - positions (持仓)
  - order_suggestions (订单建议)
  - tasks (异步任务)
"""
import asyncio
from trade_alpha.dao import (
    init_db, close_db,
    AccountConfig, StrategyConfig, ModelConfig,
    TrainingResult, PredictionResult, SignalResult,
    ExecutionResult, ExecutionTrade, ExecutionPortfolioDaily,
    OrderSuggestion, Task,
)

CLEAN_MODELS = [
    (AccountConfig, "account_configs"),
    (StrategyConfig, "strategy_configs"),
    (ModelConfig, "model_configs"),
    (TrainingResult, "training_results"),
    (PredictionResult, "prediction_results"),
    (SignalResult, "signal_results"),
    (ExecutionResult, "execution_results"),
    (ExecutionTrade, "execution_trades"),
    (ExecutionPortfolioDaily, "execution_portfolio_dailies"),
    (OrderSuggestion, "order_suggestions"),
    (Task, "tasks"),
]


async def main():
    await init_db()

    total = 0
    for model, name in CLEAN_MODELS:
        count = await model.count()
        if count > 0:
            await model.find_all().delete()
            print(f"已清理 {name}: {count} 条记录")
            total += count
        else:
            print(f"{name}: 没有记录")

    print(f"\n清理完成，共清理 {total} 条记录")
    print("股票数据 (stock_daily, stock_list) 已保留")

    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
