# MarketRegimeAnalyzer 重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构 MarketRegimeAnalyzer.analyze() 为多个子方法，用 MarketDataEmbed 替代 dict，移除 pos_mult/buy_mult 全链路

**Architecture:** analyze() 拆分为 6 个子方法，每个设置 MarketDataEmbed 的对应字段。下游 strategy 层、schemas 层、前端同步清理乘数字段。

**Tech Stack:** Python 3.14+, Pydantic, asyncio

---

### Task 1: 精简 MarketDataEmbed 和 ExecutionDailySnapshot

**Files:**
- Modify: `backend/src/trade_alpha/schemas.py:90-102`
- Modify: `backend/src/trade_alpha/dao/execution_daily_snapshot.py`

- [ ] **Step 1: 从 MarketDataEmbed 删除 position_multiplier, buy_threshold_multiplier**

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

- [ ] **Step 2: 从 ExecutionDailySnapshot 删除相同字段**

```python
class ExecutionDailySnapshot(Document):
    ...
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

删除：
- `position_multiplier: float = 1.0`
- `buy_threshold_multiplier: float = 1.0`

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/schemas.py backend/src/trade_alpha/dao/execution_daily_snapshot.py
git commit -m "refactor: remove position_multiplier and buy_threshold_multiplier from MarketDataEmbed"
```

---

### Task 2: 重构 MarketRegimeAnalyzer

**Files:**
- Modify: `backend/src/trade_alpha/execution/market_regime.py`

- [ ] **Step 1: 重命名字段**

在 `__init__()` 中：
```python
self._low_score_pct_buffer: List[float] = []  # 原名 _low_pct_buffer
# ...
self._last_result: Optional[MarketDataEmbed] = None  # 原名 _last_market_data
```

- [ ] **Step 2: 重写 analyze() 为分发方法**

```python
def analyze(
    self,
    stock_map: Dict[str, ScoredStock],
    daily_rebalanced_values: Optional[List[float]] = None,
) -> MarketDataEmbed:
    """Analyze market regime and return structured result."""
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

- [ ] **Step 3: 实现子方法 `_compute_ranking_stats`**

```python
def _compute_ranking_stats(
    self, stock_map: Dict[str, ScoredStock]
) -> bool:
    """Compute ranking_high_pct and ranking_low_pct. Returns False if no valid scores."""
    rank_scores = [
        s.ranking_score for s in stock_map.values()
        if s.ranking_score is not None
    ]
    if not rank_scores:
        return False
    sorted_scores = sorted(rank_scores)
    total_count = len(sorted_scores)
    self._last_result.ranking_high_pct = (
        sum(1 for s in sorted_scores if s > 0.30) / total_count * 100
    )
    self._last_result.ranking_low_pct = (
        sum(1 for s in sorted_scores if s < -0.30) / total_count * 100
    )
    return True
```

- [ ] **Step 4: 实现 `_update_low_score_buffer`**

```python
def _update_low_score_buffer(self) -> None:
    self._low_score_pct_buffer.append(self._last_result.ranking_low_pct)
    if len(self._low_score_pct_buffer) > 50:
        self._low_score_pct_buffer.pop(0)
```

- [ ] **Step 5: 重写 `_detect_phase`（原名 `_compute_phase_multipliers`）**

只设 `self._last_result.market_phase`，不再返回乘数。变量名清理：

```python
def _detect_phase(
    self,
    daily_rebalanced_values: Optional[List[float]] = None,
) -> None:
    """Detect market phase from index returns and low-score proportion.

    Sets self._last_result.market_phase to "up"/"flat"/"down".
    """
    config = self._strategy_config
    if not config or not config.use_phase_strategy:
        self._last_result.market_phase = "flat"
        return
    if not daily_rebalanced_values or len(daily_rebalanced_values) < 2:
        self._last_result.market_phase = "flat"
        return

    # 5-day index return: use available data if less than 6 days
    index_5d_lookback = min(5, len(daily_rebalanced_values) - 1)
    index_5d_return = (
        (daily_rebalanced_values[-1] - daily_rebalanced_values[-1 - index_5d_lookback])
        / daily_rebalanced_values[-1 - index_5d_lookback]
    )

    # 60-day trend: use available data if less than 61 days
    trend_days = min(len(daily_rebalanced_values) - 1, 60)
    index_60d_return = 0.0
    if trend_days >= 1:
        index_60d_return = (
            (daily_rebalanced_values[-1] - daily_rebalanced_values[-1 - trend_days])
            / daily_rebalanced_values[-1 - trend_days]
        )

    low_score_buf = self._low_score_pct_buffer
    low_score_5d_change = (low_score_buf[-1] - low_score_buf[-6]) if len(low_score_buf) >= 6 else 0.0

    peak = max(daily_rebalanced_values)
    trough = min(daily_rebalanced_values)
    current = daily_rebalanced_values[-1]
    drawdown = (current - peak) / peak if peak > 0 else 0.0
    drawup = (current - trough) / trough if trough > 0 else 0.0

    if drawup > 0.02:
        scale = min(3.0, 1.0 + drawup * 5)
    elif drawdown < -0.03:
        scale = max(0.5, 1.0 + drawdown * 2)
    else:
        scale = 1.0

    crash_entry = config.phase_crash_threshold * scale
    recovery_entry = config.phase_recovery_threshold * scale
    decline_trigger = recovery_entry * 0.66 if drawup > 0.02 else 0.0

    if index_5d_return < crash_entry or (index_5d_return < decline_trigger and low_score_5d_change > 0):
        phase = "down"
    elif self._current_phase == "down":
        phase = "down" if index_60d_return < 0.02 else "flat"
    elif self._current_phase == "up":
        phase = "up" if index_60d_return > -0.02 else "flat"
    elif index_60d_return > 0.03 and index_5d_return > 0.01:
        phase = "up"
    elif index_60d_return < -0.03 and index_5d_return < -0.01:
        phase = "down"
    else:
        phase = "flat"

    self._last_result.market_phase = phase
    self._current_phase = phase
```

- [ ] **Step 6: 实现 `_compute_market_indicators`（合并留存率+相关性）**

合并两个指标的计算，因为都依赖 `_rank_history` 和 `stock_map`：

```python
def _compute_market_indicators(
    self, stock_map: Dict[str, ScoredStock]
) -> None:
    """Compute retention rate and score-return correlation, raw + smoothed."""
    raw_retention = self._compute_top_n_retention(stock_map)
    self._retention_rate_buffer.append(raw_retention)
    self._last_result.top_n_retention_rate = raw_retention
    self._last_result.top_n_retention_rate_smoothed = smooth_market_indicator(
        self._retention_rate_buffer, self._strategy_config
    )

    raw_corr = self._compute_score_return_correlation(stock_map)
    self._correlation_buffer.append(raw_corr)
    self._last_result.score_return_corr = raw_corr
    self._last_result.score_return_corr_smoothed = smooth_market_indicator(
        self._correlation_buffer, self._strategy_config
    )
```

- [ ] **Step 7: 实现 `_compute_index_cumulative_return`**

```python
def _compute_index_cumulative_return(
    self, daily_rebalanced_values: Optional[List[float]] = None
) -> None:
    """Compute cumulative return of the equal-weight index."""
    if daily_rebalanced_values and len(daily_rebalanced_values) >= 2:
        self._last_result.daily_rebalanced_cum = (
            daily_rebalanced_values[-1] / daily_rebalanced_values[0]
        ) - 1.0
```

- [ ] **Step 8: 实现 `_compute_baseline_volatility`**（变量名清理）

```python
def _compute_baseline_volatility(
    self, daily_rebalanced_values: Optional[List[float]] = None
) -> None:
    """Compute baseline volatility multiplier for adaptive stop-loss."""
    if daily_rebalanced_values and len(daily_rebalanced_values) >= 2:
        cum_value = daily_rebalanced_values[-1]
        if cum_value > 0:
            self._cum_values_buffer.append(cum_value)
    vol_window = getattr(self._strategy_config, 'baseline_vol_window', 20)
    vol_window_mult = getattr(self._strategy_config, 'baseline_vol_ref_multiplier', 3)
    ref_window = vol_window * vol_window_mult
    values = self._cum_values_buffer
    if len(values) > ref_window:
        returns = [(values[i] - values[i - 1]) / values[i - 1] for i in range(-ref_window, 0)]
        rolling_vol = float(np.std(returns[-vol_window:]))
        ref_vol = float(np.std(returns))
        if ref_vol > 0:
            multiplier = rolling_vol / ref_vol
            self._last_result.baseline_vol_multiplier = max(0.5, min(3.0, multiplier))
```

- [ ] **Step 9: 更新 property 和注释**

```python
@property
def last_result(self) -> Optional[MarketDataEmbed]:
    return self._last_result
```

更新类 docstring，清理 `# Phase-based multipliers` 注释段。

- [ ] **Step 10: 删除不再需要的 import**

检查 `import Tuple` 是否还在别处使用。如果 `_compute_phase_multipliers` 不再返回 `Tuple[float, float, str]`，移除 `Tuple` 导入。

- [ ] **Step 11: 提交**

```bash
git add backend/src/trade_alpha/execution/market_regime.py
git commit -m "refactor: restructure analyze() into sub-methods, use MarketDataEmbed, clean variable names"
```

---

### Task 3: 更新流水线适配 last_result

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_pipeline.py`
- Modify: `backend/src/trade_alpha/execution/suggestion_pipeline.py`

- [ ] **Step 1: 更新 backtest_pipeline.py**

`_run_warmup()` 和 `_run_daily_loop()` 中：

```python
# 改前
market_data = MarketDataEmbed(**self.market_analyzer.last_market_data) \
    if self.market_analyzer.last_market_data else None

# 改后
market_data = self.market_analyzer.last_result
```

`_save_snapshot()` 中：

```python
# 改前
if self.market_analyzer.last_market_data:
    updates = dict(self.market_analyzer.last_market_data)

# 改后
if self.market_analyzer.last_result:
    updates = self.market_analyzer.last_result.model_dump()
```

- [ ] **Step 2: 更新 suggestion_pipeline.py**

```python
# 改前
market_data = MarketDataEmbed(**self.market_analyzer.last_market_data) \
    if self.market_analyzer.last_market_data else None

# 改后
market_data = self.market_analyzer.last_result
```

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/execution/backtest_pipeline.py backend/src/trade_alpha/execution/suggestion_pipeline.py
git commit -m "refactor: adapt pipelines to use last_result (MarketDataEmbed) instead of raw dict"
```

---

### Task 4: 清理 strategy 层乘数引用

**Files:**
- Modify: `backend/src/trade_alpha/strategy/multi_stock_strategy.py`
- Modify: `backend/src/trade_alpha/strategy/modes/trend_mode.py`

- [ ] **Step 1: 更新 multi_stock_strategy.py**

删除 `_market_multipliers()` 方法：

```python
# 删除整个方法
def _market_multipliers(self, market_data: Optional[MarketDataEmbed]) -> Tuple[float, float]:
    if market_data:
        return (market_data.position_multiplier, market_data.buy_threshold_multiplier)
    return (1.0, 1.0)
```

`_process_candidates()` 中：

```python
# 改前
pos_mult, _ = self._market_multipliers(market_data)
top_n = max(1, int(self.max_positions * pos_mult))
...
max_position_scalar=pos_mult,

# 改后
top_n = self.max_positions
...
# 删除 max_position_scalar=pos_mult 参数
```

`should_add_to_holdings()` 中：

```python
# 改前
pos_mult, _ = self._market_multipliers(market_data)
threshold *= pos_mult

# 改后
# 删除这两行，threshold 直接用原值
```

- [ ] **Step 2: 更新 trend_mode.py**

```python
# 改前
pos_mult = 1.0
buy_mult = 1.0
if market_data:
    pos_mult = market_data.position_multiplier
    buy_mult = market_data.buy_threshold_multiplier
effective_threshold = config.buy_threshold * buy_mult
effective_max = max(1, int(config.max_positions * pos_mult))

# 改后 — 直接使用 config 原始值
```

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/strategy/multi_stock_strategy.py backend/src/trade_alpha/strategy/modes/trend_mode.py
git commit -m "refactor: remove pos_mult/buy_mult from strategy layer"
```

---

### Task 5: 清理 backtest_service.py

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_service.py`

- [ ] **Step 1: 删除 position_multiplier/buy_threshold_multiplier 序列化**

在 backtest_service.py 中找到：
```python
"position_multiplier": s.position_multiplier,
"buy_threshold_multiplier": s.buy_threshold_multiplier,
```
删除这两行。

- [ ] **Step 2: 提交**

```bash
git add backend/src/trade_alpha/execution/backtest_service.py
git commit -m "refactor: remove pos_mult/buy_mult from backtest service serialization"
```

---

### Task 6: 清理前端引用

**Files:**
- Modify: `frontend/src/api/backtestRecord.ts`
- Modify: `frontend/src/views/BacktestRecordsView.vue`
- Modify: `frontend/src/components/OverviewChart.vue`

- [ ] **Step 1: 更新 backtestRecord.ts**

删除 `positionMultiplier` 和 `buyThresholdMultiplier` 类型定义（如果有）。

- [ ] **Step 2: 更新 BacktestRecordsView.vue**

删除展示 `position_multiplier` / `buy_threshold_multiplier` 的列或字段。

- [ ] **Step 3: 更新 OverviewChart.vue**

删除引用 `positionMultiplier` / `buyThresholdMultiplier` 的 chart 数据。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/api/backtestRecord.ts frontend/src/views/BacktestRecordsView.vue frontend/src/components/OverviewChart.vue
git commit -m "refactor: remove pos_mult/buy_mult from frontend"
```

---

### Task 7: 运行测试验证

- [ ] **Step 1: 运行后端集成测试**

```powershell
cd backend
.venv\Scripts\pytest tests\trade_alpha\integration\ -v
```

Expected: all tests pass.

- [ ] **Step 2: 提交最终 commit**

```bash
git add docs/superpowers/specs/2026-06-18-market-regime-refactor-design.md
git add docs/superpowers/plans/2026-06-18-market-regime-refactor-plan.md
git commit -m "docs: add market regime refactor spec and plan"
```

- [ ] **Step 3: 推送**

```bash
git push
```