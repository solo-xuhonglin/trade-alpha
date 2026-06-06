# 实盘建议流水线独立 & 移除账户配置

## 概述

将实盘建议逻辑从 `ExecutionPipeline` 分离为独立的 `SuggestionPipeline`，同时移除对 `AccountConfig` 的依赖。`ExecutionPipeline` 重命名为 `backtest_pipeline.py`，仅保留回测逻辑。

## 涉及模块

- `backend/src/trade_alpha/execution/pipeline.py` — 拆分为 3 个文件
- `backend/src/trade_alpha/execution/portfolio.py` — 修改
- `backend/src/trade_alpha/strategy/base.py` — 修改
- `backend/src/trade_alpha/api/routers/live_suggestion.py` — 更新引用 + 去掉 account_config_id
- `backend/src/trade_alpha/task/live_suggestion_runner.py` — 更新引用
- `backend/src/trade_alpha/scripts/run_live_suggestion.py` — 更新引用
- `frontend/src/api/liveSuggestion.ts` — 去掉 account_config_id
- `frontend/src/views/LiveDailySuggestionsView.vue` — 去掉账户选择
- `backend/tests/trade_alpha/integration/test_65_live_suggestion.py` — 更新引用
- `docs/api.md` — 更新文档

## 1. 文件拆分

### 1.1 新建 `execution/scoring.py`

提取 `ExecutionPipeline` 中的 5 个纯评分函数：

```python
def smooth_scores(
    pred_results: Dict[str, Dict],
    strategy_config: StrategyConfig,
    score_buffer: Dict[str, List[float]],
) -> None:
    """EWMA smoothing of composite_score -> ranking_score."""


def apply_momentum_boost(
    pred_results: Dict[str, Dict],
    strategy_config: StrategyConfig,
) -> None:
    """Apply momentum boost based on up_prob changes."""


def apply_trend_bonus(
    pred_results: Dict[str, Dict],
    strategy_config: StrategyConfig,
) -> None:
    """Apply trend bonus based on recent price trends."""


def apply_volatility_penalty(
    pred_results: Dict[str, Dict],
    strategy_config: StrategyConfig,
) -> None:
    """Apply volatility penalty based on recent volatility."""


async def filter_explosions(
    pred_results: Dict[str, Dict],
    strategy_config: StrategyConfig,
) -> None:
    """Filter out stocks with explosion-like price action."""
```

所有函数为纯函数，`strategy_config` 显式传入，无 `self` 依赖。

### 1.2 重命名 `pipeline.py` → `backtest_pipeline.py`

- 去掉 `run_live()` 方法（未使用）
- 去掉 `run_live_suggestion()` 方法（移到 `suggestion_pipeline.py`）
- 去掉 5 个评分函数（移到 `scoring.py`）
- 去掉 `_apply_full_position_sell` 中的 suggestion 相关引用
- 保留：`run_backtest()`、`_create_result`、`_calc_baseline`、`_set_pending_orders`、`_apply_full_position_sell`
- `ExecutionPipeline` 类名不变

### 1.3 新建 `execution/suggestion_pipeline.py`

```python
class SuggestionPipeline:
    """Independent pipeline for generating buy/sell suggestions.

    Does not require AccountConfig. Uses suggestion_mode=True in strategy.
    """

    def __init__(
        self,
        training_id: PydanticObjectId,
        model_config: ModelConfig,
        strategy_config: StrategyConfig,
        ts_codes: Optional[List[str]] = None,
    ):
        self.data_loader = DataLoader(...)
        self.strategy = MultiStockStrategy(
            account_config=None,
            strategy_config=strategy_config,
            mode="multi",
            ts_codes=ts_codes or [],
        )
        ...

    async def run(
        self,
        task_id: Optional[PydanticObjectId] = None,
        universe_limit: int = 50,
    ) -> str:  # returns run_id
        """Run suggestion pipeline across all target dates."""
```

内部逻辑：
1. 初始化 predictor
2. 遍历目标交易日
3. 加载实时持仓（`LivePortfolio`）
4. 预测 + 评分（调用 `scoring.py` 中的函数）
5. 策略决策（`suggestion_mode=True`，已实现）
6. 保存建议到 DB

## 2. AccountConfig 可选化

### 2.1 `execution/portfolio.py` — `PortfolioManager`

```python
def __init__(
    self,
    account_config: Optional[AccountConfig] = None,  # 改为可选
    initial_capital: float = 100000.0,
    ...
):
```

- `_account_config` 为 `None` 时，`calc_buy_fee` / `calc_sell_fee` / `calc_stamp_tax` 返回 0
- `reset()` 且 `_account_config` 为 `None` 时，`_cash_available = 0`

### 2.2 `strategy/base.py` — `PositionManager`

```python
def __init__(
    self,
    account_config: Optional[AccountConfig] = None,  # 改为可选
    ...
):
```

- `calc_buy_fee(price, rate, min_fee)` 中 `account_config` 为 `None` 时直接用参数（不从配置读）

## 3. API 和前端变更

### 3.1 后端 API `live_suggestion.py`

请求体 `run_suggestion` 去掉 `account_config_id`：

```python
class RunSuggestionRequest(BaseModel):
    training_id: str
    model_config_id: str
    strategy_config_id: str
    ts_codes: Optional[List[str]] = None
    universe_limit: int = 50
```

内部创建 `SuggestionPipeline` 替代 `ExecutionPipeline`。

### 3.2 `LiveSuggestionRun` DAO

`account_config_id` 改为 `Optional`：

```python
class LiveSuggestionRun(Document):
    account_config_id: Optional[PydanticObjectId] = None  # 可为 None
    ...
```

### 3.3 前端 `liveSuggestionApi.runSuggestion`

请求参数去掉 `account_config_id`。

### 3.4 前端弹窗

「发起实盘建议」弹窗不再需要选择账户配置，只保留：
- 训练任务（training）
- 模型配置
- 策略配置
- 股票范围

## 4. 引用更新

| 文件 | 改后 import |
|------|-------------|
| `task/live_suggestion_runner.py` | `from ..execution.suggestion_pipeline import SuggestionPipeline` |
| `task/backtest_runner.py` | `from ..execution.backtest_pipeline import ExecutionPipeline` |
| `api/routers/live_suggestion.py` | `from ...execution.suggestion_pipeline import SuggestionPipeline` |
| `api/routers/backtest.py` | `from ...execution.backtest_pipeline import ExecutionPipeline` |
| `scripts/run_live_suggestion.py` | `from execution.suggestion_pipeline import SuggestionPipeline` |
| `tests/test_65_live_suggestion.py` | `from ...execution.suggestion_pipeline import SuggestionPipeline` |
| `tests/test_61_backtest_lstm.py` | `from ...execution.backtest_pipeline import ExecutionPipeline` |

## 5. 测试

- `test_65_live_suggestion.py` — 更新 import + 去掉 account_config 创建步骤
- `test_61_backtest_lstm.py` — 只改 import 路径，逻辑不变
- `test_46_live_portfolio.py` — 不变

## 6. 影响范围

| 文件 | 操作 | 改动量 |
|------|------|--------|
| `execution/scoring.py` | 新建 | ~100 行 |
| `execution/suggestion_pipeline.py` | 新建 | ~300 行 |
| `execution/pipeline.py` → `backtest_pipeline.py` | 重命名 + 精简 | -200 行 |
| `execution/portfolio.py` | 修改 | ~10 行 |
| `strategy/base.py` | 修改 | ~10 行 |
| `api/routers/live_suggestion.py` | 修改 | ~30 行 |
| `task/live_suggestion_runner.py` | 修改 | ~5 行 |
| `scripts/run_live_suggestion.py` | 修改 | ~5 行 |
| `dao/live_suggestion_run.py` | 修改 | ~2 行 |
| `frontend/src/api/liveSuggestion.ts` | 修改 | ~5 行 |
| 前端弹窗 | 修改 | ~30 行 |
| 测试 2 个 | 修改 | ~20 行 |
| 文档 | 更新 | ~20 行 |

## 7. 不涉及

- 回测逻辑完全不变
- `MultiStockStrategy` 建议模式已实现（`suggestion_mode=True`）
- `LivePortfolio` 和仓位管理不变
- `scoring.py` 中的函数不改变现有回测行为