# MarketRegimeAnalyzer 重构设计

## 1. 目标

对 `MarketRegimeAnalyzer` 进行二次重构：

1. **`analyze()` 拆分** — 将 89 行的臃肿方法拆分为多个单一职责的子方法
2. **`dict` → `MarketDataEmbed`** — 用现成 Pydantic 模型替代无类型 dict
3. **变量名清理** — 消除缩写和含义模糊的局部变量名
4. **移除 `pos_mult`/`buy_mult`** — 全链路清理这两个已废弃的乘数

## 2. 变更详述

### 2.1 `MarketDataEmbed` 精简

**文件:** `backend/src/trade_alpha/schemas.py`

删除 `position_multiplier` 和 `buy_threshold_multiplier` 两个字段：

```python
class MarketDataEmbed(BaseModel):
    """Market regime and ranking statistics for strategy decisions."""
    ranking_high_pct: float = 0.0
    ranking_low_pct: float = 0.0
    top_n_retention_rate: float = 0.0
    top_n_retention_rate_smoothed: float = 0.0
    score_return_corr: float = 0.0
    score_return_corr_smoothed: float = 0.0
    daily_rebalanced_cum: float = 0.0
    market_phase: str = ""
    baseline_vol_multiplier: float = 1.0
```

### 2.2 `MarketRegimeAnalyzer.analyze()` 重构

`analyze()` 内部拆分为多个无返回值的子方法，每个子方法直接操作 `self._last_result`：

```python
def analyze(self, stock_map, daily_rebalanced_values=None) -> MarketDataEmbed:
    if not stock_map:
        self._last_result = None
        return MarketDataEmbed()

    self._last_result = MarketDataEmbed()
    if not self._compute_ranking_stats(stock_map):
        self._last_result = None
        return MarketDataEmbed()

    self._update_low_score_buffer()
    self._detect_phase(daily_rebalanced_values)
    self._compute_market_indicators(stock_map)
    self._compute_index_cumulative_return(daily_rebalanced_values)
    self._compute_baseline_volatility(daily_rebalanced_values)
    return self._last_result
```

### 2.3 子方法

#### `_compute_ranking_stats(stock_map) -> bool`

返回 bool 标识是否有有效数据。内部设置 `self._last_result.ranking_high_pct` / `ranking_low_pct`。如果排名分为空，返回 False。

#### `_detect_phase(daily_rebalanced_values)`

只设置 `self._last_result.market_phase`。移除了 `pos_mult`/`buy_mult` 返回值。变量名清理：

| 旧名 | 新名 |
|------|------|
| `rebalanced_5d` | `index_5d_return` |
| `trend_60d` | `index_60d_return` |
| `lp_buffer` / `self._low_pct_buffer` | `self._low_score_pct_buffer` |
| `low_5d` | `low_score_5d_change` |
| `crash_th` | `crash_entry` |
| `recovery_th` | `recovery_entry` |
| `decline_bar` | `decline_trigger` |
| `three_phase` | `phase` |
| `n` | `total_count` |

#### `_compute_market_indicators(stock_map)`

设置 `top_n_retention_rate`、`top_n_retention_rate_smoothed`、`score_return_corr`、`score_return_corr_smoothed`。

#### `_compute_index_cumulative_return(daily_rebalanced_values)`

设置 `self._last_result.daily_rebalanced_cum`。

#### `_compute_baseline_volatility(daily_rebalanced_values)`

设置 `self._last_result.baseline_vol_multiplier`。变量名清理：

| 旧名 | 新名 |
|------|------|
| `window` | `vol_window` |
| `ref_mult` | `vol_window_multiplier` |
| `buf` | `values` |

### 2.4 字段重命名

| 旧名 | 新名 | 原因 |
|------|------|------|
| `self._low_pct_buffer` | `self._low_score_pct_buffer` | 明确是低分百分比 |
| `self._last_market_data` | `self._last_result` | 对应新类型 `MarketDataEmbed` |
| `self._rebalanced_cum_buffer` | `self._cum_values_buffer` | （已在上次重构中改过） |

### 2.5 `last_market_data` property → `last_result`

```python
@property
def last_result(self) -> Optional[MarketDataEmbed]:
    return self._last_result
```

### 2.6 下游 — `pos_mult`/`buy_mult` 全链路移除

| 文件 | 改动 |
|------|------|
| `schemas.py` | `MarketDataEmbed` 删除 2 字段 |
| `dao/execution_daily_snapshot.py` | 删除 2 字段定义 |
| `execution/backtest_service.py` | 删除 2 字段序列化 |
| `strategy/multi_stock_strategy.py` | 删除 `_market_multipliers()`，`_process_candidates` 中 `max(1, int(...))` 改为直接 `self.max_positions`，`should_add_to_holdings` 中 `threshold *= pos_mult` 移除 |
| `strategy/modes/trend_mode.py` | `pos_mult`/`buy_mult` 读取和计算全部移除，直接使用 `config.buy_threshold` 和 `config.max_positions` |
| `strategy/modes/rotation_mode.py` | (不动) |
| `frontend/src/components/OverviewChart.vue` | 删除相关 chart 引用 |
| `frontend/src/views/BacktestRecordsView.vue` | 删除展示 |
| `frontend/src/api/backtestRecord.ts` | 删除类型定义 |

### 2.7 流水线对接 — `last_market_data` → `last_result`

| 文件 | 改前 | 改后 |
|------|------|------|
| `backtest_pipeline.py` | `MarketDataEmbed(**self.market_analyzer.last_market_data)` | `self.market_analyzer.last_result` |
| `backtest_pipeline.py` | `if self.market_analyzer.last_market_data: updates = dict(...)` | `if self.market_analyzer.last_result: updates = self.market_analyzer.last_result.model_dump()` |
| `suggestion_pipeline.py` | `MarketDataEmbed(**self.market_analyzer.last_market_data)` | `self.market_analyzer.last_result` |
| `suggestion_pipeline.py` | `self.market_analyzer.last_market_data` | `self.market_analyzer.last_result` |

### 2.8 内部变量名清理范围

仅清理 `_detect_phase` 和 `_compute_baseline_volatility` 内部的局部变量。不影响 `strategy_config` 参数名（按之前约定，参数不改名）。

## 3. 不受影响的部分

- `record_ranking_scores()`、`compute_rank_improvement()`、`get_rank_history()` — 不动
- MongoDB 已存回测数据 — 字段在数据库中仍存在，Python 模型删除后不再读取
- `StrategyConfig` 参数名 — 不动
- 前端 `execute_by_date` 等操作逻辑 — 不动
- 集成测试 — 只需适配 `last_market_data` → `last_result`

## 4. 涉及文件列表

| 文件 | 改动类型 |
|------|---------|
| `backend/src/trade_alpha/execution/market_regime.py` | 重构 |
| `backend/src/trade_alpha/schemas.py` | 删 2 字段 |
| `backend/src/trade_alpha/dao/execution_daily_snapshot.py` | 删 2 字段 |
| `backend/src/trade_alpha/execution/backtest_service.py` | 删 2 引用 |
| `backend/src/trade_alpha/execution/backtest_pipeline.py` | 适配 last_result |
| `backend/src/trade_alpha/execution/suggestion_pipeline.py` | 适配 last_result |
| `backend/src/trade_alpha/strategy/multi_stock_strategy.py` | 删 market_multipliers + 化简 |
| `backend/src/trade_alpha/strategy/modes/trend_mode.py` | 删 pos_mult/buy_mult |
| `frontend/src/components/OverviewChart.vue` | 删字段引用 |
| `frontend/src/views/BacktestRecordsView.vue` | 删字段引用 |
| `frontend/src/api/backtestRecord.ts` | 删类型定义 |