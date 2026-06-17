# PipelineContext 设计文档

## 1. 问题

回测和建议管道的传参链长且重复：

```
pipeline.make_orders(scored_stocks, date, portfolio, close_prices, market_data, score_manager, suggestion_mode)
  → strategy.make_orders(...同上 8 个参数...)
    → mode.settle_mode_orders(...同上 8 个参数...)
      → _apply_full_position_sell(scored_stocks, portfolio, close_prices, trade_date, market_data, score_manager)
      → _score_not_declining(ts_code, score_manager)
```

问题：
- 参数链 8 层深，全是重复透传
- `Optional["ScoreManager"]` 前向引用（字符串注解）出现 6 处
- `portfolio`、`score_manager` 是运行时状态，不应每日重复传入
- 循环引用导致 `from trade_alpha.strategy.multi_stock_strategy import MultiStockStrategy` 在 mode 中放在函数内部

## 2. 方案：PipelineContext

新增 `execution/context.py`，将运行时状态类打包成一个不可变上下文对象。

### PipelineContext 定义

```python
from typing import Any, Optional
from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.dao.model_config import ModelConfig
from trade_alpha.execution.data_loader import DataLoader
from trade_alpha.execution.portfolio import PortfolioManager
from trade_alpha.execution.scoring import ScoreManager


class PipelineContext:
    """Runtime context for pipeline execution.

    Bundles all stateful objects (data_loader, score_manager, portfolio, etc.)
    so they can be passed as a single parameter instead of chained individual
    params. Eliminates Optional["ScoreManager"] forward references.
    """

    def __init__(
        self,
        data_loader: DataLoader,
        score_manager: ScoreManager,
        portfolio: PortfolioManager,
        strategy_config: StrategyConfig,
        model_config: ModelConfig,
        predictor: Any = None,
        account_config: Optional[AccountConfig] = None,
    ):
        self.data_loader = data_loader
        self.score_manager = score_manager
        self.portfolio = portfolio
        self.predictor = predictor
        self.strategy_config = strategy_config
        self.model_config = model_config
        self.account_config = account_config
```

## 3. 受影响的文件和方法

### 3.1 改签名的 9 个方法

| 文件 | 方法 | 当前参数 | 新参数 |
|------|------|---------|--------|
| `base.py` | `make_orders` | `scored_stocks, trade_date, portfolio, close_prices?, market_data?, score_manager?, suggestion_mode` | `scored_stocks, trade_date, ctx, close_prices?, market_data?, suggestion_mode` |
| `multi_stock_strategy.py` | `make_orders` | 同上 | 同上 |
| `single_stock.py` | `make_orders` | 同上 | 同上 |
| `modes/base.py (PhaseMode)` | `settle_mode_orders` | `scored_stocks, trade_date, portfolio, close_prices, market_data, score_manager, suggestion_mode` | `scored_stocks, trade_date, ctx, close_prices, market_data, suggestion_mode` |
| `modes/trend_mode.py` | `settle_mode_orders` | 同上 | 同上 |
| `modes/mean_reversion_mode.py` | `settle_mode_orders` | 同上 | 同上 |
| `modes/defensive_mode.py` | `settle_mode_orders` | 同上 | 同上 |
| `multi_stock_strategy.py` | `_score_not_declining` | `ts_code, score_manager?` | `ts_code, ctx` |
| `multi_stock_strategy.py` | `_apply_full_position_sell` | `scored_stocks, portfolio, close_prices, trade_date, market_data?, score_manager?` | `scored_stocks, close_prices, trade_date, ctx, market_data?` |

### 3.2 内部调用的变化

方法内部使用 `ctx.portfolio`、`ctx.score_manager` 替代原来的 `portfolio`、`score_manager` 参数。

- `MultiStockStrategy.make_orders` → 转发给 `mode.settle_mode_orders` 时不再传 `portfolio` 和 `score_manager`
- `TrendMode.settle_mode_orders` → 调用 `_apply_full_position_sell` 改为传 `ctx`
- `TrendMode.settle_mode_orders` → 调用 `_score_not_declining` 改为传 `ctx`
- `MeanReversionMode.settle_mode_orders` → 同上
- `DefensiveMode.settle_mode_orders` → 同上

### 3.3 不动的 14 个方法

这些方法因纯计算、static、或专属数据参数不适合收进 ctx：

**base.py:** `calc_buy_fee`, `match_order`, `settle_orders`, `daily_snapshot`, `_next_trade_date`, `calculate_metrics`, `calculate_max_drawdown`, `calculate_baseline_metrics`, `calculate_trade_metrics`

**multi_stock_strategy.py:** `_build_order`, `_market_multipliers`, `_is_stop_loss_triggered`, `check_common_sell`, `_check_sell`

**single_stock.py:** `_should_buy`, `_should_sell`

**defensive_mode.py:** `_check_sell_defensive`

## 4. Pipeline 创建 Context

### BacktestPipeline

```python
# __init__ 中
self.ctx = PipelineContext(
    data_loader=self.data_loader,
    score_manager=self.score_manager,
    portfolio=self.portfolio,
    predictor=self.predictor,
    strategy_config=self.strategy_config,
    model_config=self.model_config,
    account_config=self.account_config,
)

# run_daily_loop 中调用
pending_orders = await self.strategy.make_orders(
    scored_stocks=list(stock_map.values()),
    trade_date=date,
    ctx=self.ctx,
    close_prices=close_prices,
    market_data=market_data,
)
```

### SuggestionPipeline

```python
# __init__ 中
self.ctx = PipelineContext(
    data_loader=self.data_loader,
    score_manager=self.score_manager,
    portfolio=self.portfolio,
    predictor=self.predictor,
    strategy_config=self.strategy_config,
    model_config=self.model_config,
)

# run 中调用
pending_orders = await self.strategy.make_orders(
    scored_stocks=list(stock_map.values()),
    trade_date=date,
    ctx=self.ctx,
    close_prices=close_prices,
    market_data=market_data,
    suggestion_mode=True,
)
```

## 5. 解决的问题

- **`Optional["ScoreManager"]` 前向引用**消除 → 通过 `ctx.score_manager` 访问，导入 `PipelineContext` 即可
- **参数链缩短**：`make_orders` 8 参 → 5 参，`settle_mode_orders` 8 参 → 5 参，`_apply_full_position_sell` 7 参 → 4 参
- **mode 中循环导入消除**：`MeanReversionMode` 和 `DefensiveMode` 中不再需要 `from trade_alpha.strategy.multi_stock_strategy import MultiStockStrategy` 局部导入
- **类型安全**：`ctx.portfolio` 是 `PortfolioManager` 而非字符串注解，IDE 可获得完整类型提示

## 6. 未涉及的范围

- 每日变动的 `close_prices`、`market_data`、`day_data` 仍作为单独参数传入（它们是每日数据，不是运行时状态）
- `settle_orders`、`daily_snapshot` 等专属数据方法保持原签名
- 无新增依赖，无性能影响