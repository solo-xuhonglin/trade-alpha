# 趋势加分与波动扣分 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 废除旧的趋势左移（分数斜率），替换为基于股价的两个独立功能：趋势加分（R²加权斜率）和波动扣分（日内平均振幅）

**Architecture:** 后端修改 StrategyConfig 模型替换字段，Pipeline 新增两个方法替代旧方法；前端更新配置页面替换旧 UI 区块。算法基于 StockDaily 的 close/open/high/low 数据，通过 peek_history_data 批量获取

**Tech Stack:** Python/FastAPI/Beanie, Vue3/Vuetify, MongoDB

---

### Task 1: 后端模型 — StrategyConfig 替换字段

**Files:**
- Modify: `backend/src/trade_alpha/dao/strategy_config.py:23-37`

- [ ] **Step 1: 修改 StrategyConfig 模型**

删除旧的 4 个字段，新增 10 个字段。

```python
class StrategyConfig(Document):
    # ... 保留所有现有字段 ...
    
    # --- 删除以下 4 个字段 ---
    # use_trend_boost: bool = False     → 删除
    # trend_window: int = 5             → 删除
    # trend_scale: float = 0.5          → 删除
    # max_trend_boost: float = 0.05     → 删除
    
    # --- 新增趋势加分字段 ---
    use_trend_bonus: bool = False
    trend_bonus_window: int = 10
    trend_bonus_scale: float = 0.03
    trend_r2_threshold: float = 0.30
    trend_max_bonus: float = 0.05
    
    # --- 新增波动扣分字段 ---
    use_volatility_penalty: bool = False
    vol_penalty_window: int = 10
    vol_range_tolerance: float = 0.035
    vol_penalty_scale: float = 0.005
    vol_max_penalty: float = 0.05
```

- [ ] **Step 2: 同步修改 StrategyCreateRequest schema**

文件: `backend/src/trade_alpha/schemas.py`（grep 搜索 `use_trend_boost` 定位）

```python
# 删除旧的:
# use_trend_boost: bool = False
# trend_window: int = 5
# trend_scale: float = 0.5
# max_trend_boost: float = 0.05

# 新增:
use_trend_bonus: bool = False
trend_bonus_window: int = 10
trend_bonus_scale: float = 0.03
trend_r2_threshold: float = 0.30
trend_max_bonus: float = 0.05
use_volatility_penalty: bool = False
vol_penalty_window: int = 10
vol_range_tolerance: float = 0.035
vol_penalty_scale: float = 0.005
vol_max_penalty: float = 0.05
```

- [ ] **Step 3: 同步修改 ScoredStock**

文件: `backend/src/trade_alpha/schemas.py`（grep 搜索 `trend_boost`）

```python
# 删除:
# trend_boost: float = 0.0

# 新增:
trend_bonus: float = 0.0
vol_penalty: float = 0.0
```

- [ ] **Step 4: 同步修改 strategy config service**

文件: `backend/src/trade_alpha/strategy_service/service.py`（grep 搜索 `use_trend_boost` 定位）

查找并替换 create_strategy / update_strategy 函数中的字段映射，将旧 4 个参数替换为新 10 个参数。

- [ ] **Step 5: 验证编译通过**

Run: `cd d:\projects\trade-alpha\backend; .venv\Scripts\python -c "from trade_alpha.dao.strategy_config import StrategyConfig; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add backend/src/trade_alpha/dao/strategy_config.py backend/src/trade_alpha/schemas.py backend/src/trade_alpha/strategy_service/service.py
git commit -m "feat: replace trend_boost with trend_bonus + volatility_penalty in models"
```

---

### Task 2: 后端 Pipeline — 新增 _calc_r_squared + 替换趋势加分/波动扣分方法

**Files:**
- Modify: `backend/src/trade_alpha/execution/pipeline.py:38-50, 173-204, init buffer, predict/run_live call sites`

- [ ] **Step 1: 新增 _calc_r_squared 辅助函数（替换 _calc_linear_slope）**

删除旧的 `_calc_linear_slope`（约 38-52 行），替换为：

```python
def _calc_linear_slope(values: List[float]) -> float:
    """Calculate linear regression slope for a list of values."""
    n = len(values)
    if n < 2:
        return 0.0
    x = list(range(n))
    sum_x = sum(x)
    sum_y = sum(values)
    sum_xy = sum(xi * yi for xi, yi in zip(x, values))
    sum_xx = sum(xi * xi for xi in x)
    denom = n * sum_xx - sum_x * sum_x
    if denom == 0:
        return 0.0
    return (n * sum_xy - sum_x * sum_y) / denom


def _calc_r_squared(values: List[float]) -> float:
    """Calculate R² (goodness of fit) for linear regression of a list of values."""
    n = len(values)
    if n < 3:
        return 0.0
    x = list(range(n))
    sum_x = sum(x)
    sum_y = sum(values)
    sum_xy = sum(xi * yi for xi, yi in zip(x, values))
    sum_xx = sum(xi * xi for xi in x)
    denom = n * sum_xx - sum_x * sum_x
    if denom == 0:
        return 0.0
    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    ss_res = sum((values[i] - (slope * x[i] + intercept)) ** 2 for i in range(n))
    ss_tot = sum((v - sum_y / n) ** 2 for v in values)
    if ss_tot == 0:
        return 0.0
    return max(0.0, 1.0 - ss_res / ss_tot)
```

- [ ] **Step 2: 删除旧 _apply_trend_boost 和 _score_buffer_trend**

从 `__init__` 中删除：
```python
# 删除：
self._score_buffer_trend: Dict[str, List[float]] = {}
```

从 pipeline.py 中删除整个 `_apply_trend_boost` 方法（约 173-204 行）。

- [ ] **Step 3: 新增 _apply_trend_bonus 方法**

在旧 `_apply_trend_boost` 位置（或平滑之后的位置）插入：

```python
def _apply_trend_bonus(self, pred_results: Dict[str, Dict],
                       close_prices: Dict[str, List[float]]) -> None:
    """Apply trend bonus based on price R²-weighted linear regression slope.

    Rewards stocks with steady upward price trends (high R²).
    Only applied when strategy config has use_trend_bonus=True.
    """
    if not self.strategy_config or not self.strategy_config.use_trend_bonus:
        for r in pred_results.values():
            r["trend_bonus"] = 0.0
            r["price_slope"] = 0.0
            r["price_r_squared"] = 0.0
        return

    window = self.strategy_config.trend_bonus_window
    scale = self.strategy_config.trend_bonus_scale
    r2_threshold = self.strategy_config.trend_r2_threshold
    max_bonus = self.strategy_config.trend_max_bonus

    for ts_code, r in pred_results.items():
        prices = close_prices.get(ts_code, [])
        if len(prices) < 3:
            r["trend_bonus"] = 0.0
            r["price_slope"] = 0.0
            r["price_r_squared"] = 0.0
            continue

        # Use last N prices matching window
        buf = prices[-(window + 1):] if len(prices) > window else prices
        slope = _calc_linear_slope(buf)
        r_squared = _calc_r_squared(buf)

        if slope > 0 and r_squared >= r2_threshold:
            trend_bonus = max(0.0, min(max_bonus, slope * r_squared * scale))
        else:
            trend_bonus = 0.0

        r["score"] = r["score"] + trend_bonus
        r["trend_bonus"] = trend_bonus
        r["price_slope"] = slope
        r["price_r_squared"] = r_squared
```

- [ ] **Step 4: 新增 _apply_volatility_penalty 方法**

```python
def _apply_volatility_penalty(self, pred_results: Dict[str, Dict],
                               ohlc_data: Dict[str, List[Dict]]) -> None:
    """Apply volatility penalty based on daily range ratio (OHLC).

    Penalizes stocks with large intraday fluctuations (high avg daily range).
    Only applied when strategy config has use_volatility_penalty=True.
    """
    if not self.strategy_config or not self.strategy_config.use_volatility_penalty:
        for r in pred_results.values():
            r["vol_penalty"] = 0.0
            r["price_avg_range"] = 0.0
        return

    window = self.strategy_config.vol_penalty_window
    tolerance = self.strategy_config.vol_range_tolerance
    scale = self.strategy_config.vol_penalty_scale
    max_penalty = self.strategy_config.vol_max_penalty

    for ts_code, r in pred_results.items():
        records = ohlc_data.get(ts_code, [])
        if len(records) < 3:
            r["vol_penalty"] = 0.0
            r["price_avg_range"] = 0.0
            continue

        buf = records[-(window + 1):] if len(records) > window else records
        daily_ranges = [
            (d["high"] - d["low"]) / d["close"]
            for d in buf if d["close"] > 0
        ]
        if not daily_ranges:
            r["vol_penalty"] = 0.0
            r["price_avg_range"] = 0.0
            continue

        avg_range = sum(daily_ranges) / len(daily_ranges)
        if avg_range > tolerance:
            vol_penalty = max(0.0, min(max_penalty, (avg_range - tolerance) * scale))
        else:
            vol_penalty = 0.0

        r["score"] = r["score"] - vol_penalty
        r["vol_penalty"] = vol_penalty
        r["price_avg_range"] = avg_range
```

- [ ] **Step 5: 更新 __init__ — 删除 _score_buffer_trend**

```python
# __init__ 中删除这一行:
# self._score_buffer_trend: Dict[str, List[float]] = {}
```

- [ ] **Step 6: 更新 _predict 和 run_live 的调用**

搜索 `_apply_trend_boost` 的所有调用处（约 423 行和 634 行），替换为：

```python
# 获取价格数据
lookback = max(self.strategy_config.trend_bonus_window if self.strategy_config.use_trend_bonus else 0,
               self.strategy_config.vol_penalty_window if self.strategy_config.use_volatility_penalty else 0)
if lookback > 0:
    history_data = await self.data_loader.peek_history_data(
        trade_date, list(pred_results.keys()), lookback + 5
    )
    close_prices: Dict[str, List[float]] = {}
    ohlc_data: Dict[str, List[Dict]] = {}
    for ts_code, records in history_data.items():
        close_prices[ts_code] = [r.close for r in records if r.close is not None]
        ohlc_data[ts_code] = [
            {"open": r.open, "high": r.high, "low": r.low, "close": r.close}
            for r in records if r.close is not None
        ]
    self._apply_trend_bonus(pred_results, close_prices)
    self._apply_volatility_penalty(pred_results, ohlc_data)
else:
    # 两个都没启用，设置默认值
    for r in pred_results.values():
        r["trend_bonus"] = 0.0
        r["price_slope"] = 0.0
        r["price_r_squared"] = 0.0
        r["vol_penalty"] = 0.0
        r["price_avg_range"] = 0.0
```

**重要**：`_predict` 和 `run_live` 都是 async 方法，所以 `await self.data_loader.peek_history_data(...)` 是 OK 的。

具体修改位置：
- `_predict` 中：`_smooth_scores` 之后、`_apply_momentum_boost` 之前（约 420 行区域）
- `run_live` 中：同样位置（约 630 行区域）

注意：由于需要 await，调用要放在 async 方法内。`_apply_trend_bonus` 和 `_apply_volatility_penalty` 保持同步方法。

- [ ] **Step 7: 更新 ScoredStock 和 snapshot 的字段引用**

搜索 `trend_boost` 在 pipeline.py 中的其他引用（约 432 行和 648 行的 snapshot 保存部分）：

```python
# 旧代码:
# trend_boost=r.get("trend_boost", 0.0),

# 新代码:
trend_bonus=r.get("trend_bonus", 0.0),
vol_penalty=r.get("vol_penalty", 0.0),
price_slope=r.get("price_slope", 0.0),
price_r_squared=r.get("price_r_squared", 0.0),
price_avg_range=r.get("price_avg_range", 0.0),
```

- [ ] **Step 8: 验证编译**

Run: `cd d:\projects\trade-alpha\backend; .venv\Scripts\python -c "from trade_alpha.execution.pipeline import BacktestPipeline; print('OK')"`
Expected: `OK`

- [ ] **Step 9: Commit**

```bash
git add backend/src/trade_alpha/execution/pipeline.py
git commit -m "feat: implement trend_bonus (R² slope) and volatility_penalty (daily range) in pipeline"
```

---

### Task 3: 后端 API — 更新 StrategyConfig 路由

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/strategy_config.py`

- [ ] **Step 1: 查找并替换字段引用**

grep 搜索 `use_trend_boost` / `trend_window` / `trend_scale` / `max_trend_boost` 在 strategy_config 路由文件中的引用，替换为新字段名。

- [ ] **Step 2: 验证编译**

Run: `cd d:\projects\trade-alpha\backend; .venv\Scripts\python -c "from trade_alpha.api.routers.strategy_config import router; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/api/routers/strategy_config.py
git commit -m "feat: update strategy config API with trend_bonus/vol_penalty fields"
```

---

### Task 4: 前端 — 策略配置页面替换 UI 区块

**Files:**
- Modify: `frontend/src/views/BacktestManageView.vue`
- Modify: `frontend/src/api/strategyConfig.ts`
- Modify: `frontend/src/views/BacktestRecordsView.vue`（配置弹窗显示）

- [ ] **Step 1: 更新前端 Strategy 类型**

grep 搜索 `use_trend_boost` 在 `frontend/src/api/strategyConfig.ts`：

```typescript
// 删除:
// use_trend_boost?: boolean
// trend_window?: number
// trend_scale?: number
// max_trend_boost?: number

// 新增:
use_trend_bonus?: boolean
trend_bonus_window?: number
trend_bonus_scale?: number
trend_r2_threshold?: number
trend_max_bonus?: number
use_volatility_penalty?: boolean
vol_penalty_window?: number
vol_range_tolerance?: number
vol_penalty_scale?: number
vol_max_penalty?: number
```

- [ ] **Step 2: 更新 BacktestManageView 配置表单**

搜索 `use_trend_boost` 在 `BacktestManageView.vue` 中的位置，替换整个"趋势左移"区块为"趋势加分"和"波动扣分"两个独立区块。

找到以下结构（在排名优化 tab 内）：
```
<!-- 趋势左移区块 (约 900-980 行) -->
<v-divider class="my-4"></v-divider>
<div class="d-flex align-center mb-2">
  <v-switch v-model="form.use_trend_boost" ...>趋势左移</v-switch>
  <v-chip>分数趋势提前反映</v-chip>
</div>
<v-row>
  ... 3个text-field (trend_window, trend_scale, max_trend_boost)
</v-row>
```

替换为：

```html
<!-- 趋势加分区块 -->
<v-divider class="my-4"></v-divider>
<div class="d-flex align-center mb-2">
  <v-switch v-model="form.use_trend_bonus" hide-details density="compact" color="primary"
    class="mr-2" label="趋势加分"></v-switch>
  <v-chip size="x-small" variant="outlined" color="info">基于股价趋势的稳定加分</v-chip>
</div>
<v-row>
  <v-col cols="12" md="3">
    <v-text-field v-model.number="form.trend_bonus_window" type="number"
      label="窗口天数" hint="价格观察窗口" persistent-hint
      :disabled="!form.use_trend_bonus"></v-text-field>
  </v-col>
  <v-col cols="12" md="3">
    <v-text-field v-model.number="form.trend_bonus_scale" type="number" step="0.01"
      label="加分系数" hint="斜率×R²×系数" persistent-hint
      :disabled="!form.use_trend_bonus"></v-text-field>
  </v-col>
  <v-col cols="12" md="3">
    <v-text-field v-model.number="form.trend_r2_threshold" type="number" step="0.05"
      label="R²阈值" hint="低于此值不给加分" persistent-hint
      :disabled="!form.use_trend_bonus"></v-text-field>
  </v-col>
  <v-col cols="12" md="3">
    <v-text-field v-model.number="form.trend_max_bonus" type="number" step="0.01"
      label="最大加分" hint="加分上限" persistent-hint
      :disabled="!form.use_trend_bonus"></v-text-field>
  </v-col>
</v-row>

<!-- 波动扣分区块 -->
<v-divider class="my-4"></v-divider>
<div class="d-flex align-center mb-2">
  <v-switch v-model="form.use_volatility_penalty" hide-details density="compact" color="primary"
    class="mr-2" label="波动扣分"></v-switch>
  <v-chip size="x-small" variant="outlined" color="info">识别日内剧烈波动并减分</v-chip>
</div>
<v-row>
  <v-col cols="12" md="3">
    <v-text-field v-model.number="form.vol_penalty_window" type="number"
      label="窗口天数" hint="价格观察窗口" persistent-hint
      :disabled="!form.use_volatility_penalty"></v-text-field>
  </v-col>
  <v-col cols="12" md="3">
    <v-text-field v-model.number="form.vol_range_tolerance" type="number" step="0.005"
      label="振幅容忍度" hint="低于此值不扣分" persistent-hint
      :disabled="!form.use_volatility_penalty"></v-text-field>
  </v-col>
  <v-col cols="12" md="3">
    <v-text-field v-model.number="form.vol_penalty_scale" type="number" step="0.001"
      label="扣分力度" hint="每超1%振幅的扣分" persistent-hint
      :disabled="!form.use_volatility_penalty"></v-text-field>
  </v-col>
  <v-col cols="12" md="3">
    <v-text-field v-model.number="form.vol_max_penalty" type="number" step="0.01"
      label="最大扣分" hint="扣分上限" persistent-hint
      :disabled="!form.use_volatility_penalty"></v-text-field>
  </v-col>
</v-row>
```

更新 form 初始化：
```typescript
// 删除旧:
// use_trend_boost: false,
// trend_window: 5,
// trend_scale: 0.5,
// max_trend_boost: 0.05,

// 新增:
use_trend_bonus: false,
trend_bonus_window: 10,
trend_bonus_scale: 0.03,
trend_r2_threshold: 0.30,
trend_max_bonus: 0.05,
use_volatility_penalty: false,
vol_penalty_window: 10,
vol_range_tolerance: 0.035,
vol_penalty_scale: 0.005,
vol_max_penalty: 0.05,
```

- [ ] **Step 3: 更新回测历史配置弹窗的显示**

在 `BacktestRecordsView.vue` 中，搜索 `use_trend_boost` 相关显示代码（策略配置tab中），替换为两个新功能的展示：

```html
<!-- 趋势加分 -->
<v-list-item v-if="backtestStrategyConfig?.use_trend_bonus">
  <template v-slot:title>
    <v-icon color="success" size="small" class="mr-1">mdi-trending-up</v-icon>
    趋势加分
  </template>
  <template v-slot:subtitle>
    窗口={{ backtestStrategyConfig.trend_bonus_window }} |
    系数={{ backtestStrategyConfig.trend_bonus_scale }} |
    R²阈值={{ backtestStrategyConfig.trend_r2_threshold }} |
    上限={{ backtestStrategyConfig.trend_max_bonus }}
  </template>
</v-list-item>

<!-- 波动扣分 -->
<v-list-item v-if="backtestStrategyConfig?.use_volatility_penalty">
  <template v-slot:title>
    <v-icon color="warning" size="small" class="mr-1">mdi-wave</v-icon>
    波动扣分
  </template>
  <template v-slot:subtitle>
    窗口={{ backtestStrategyConfig.vol_penalty_window }} |
    振幅容忍={{ backtestStrategyConfig.vol_range_tolerance }} |
    力度={{ backtestStrategyConfig.vol_penalty_scale }} |
    上限={{ backtestStrategyConfig.vol_max_penalty }}
  </template>
</v-list-item>
```

删除旧的 `use_trend_boost` 相关 `<v-list-item>` 代码。

- [ ] **Step 4: 验证前端编译**

Run: `cd d:\projects\trade-alpha\frontend; npx vue-tsc --noEmit`
Expected: No type errors

Run: `cd d:\projects\trade-alpha\frontend; npx vite build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/strategyConfig.ts frontend/src/views/BacktestManageView.vue frontend/src/views/BacktestRecordsView.vue
git commit -m "feat: update frontend config UI for trend_bonus + volatility_penalty"
```

---

### Task 5: 集成验证

- [ ] **Step 1: 运行后端集成测试**

Run: `cd d:\projects\trade-alpha\backend; .venv\Scripts\pytest tests\trade_alpha\integration\ -v --timeout=60`
Expected: All tests pass (87 tests). Note: StrategyConfig 字段变更不会影响已有集成测试。

- [ ] **Step 2: 最终 Commit**

```bash
git add docs/superpowers/specs/2026-05-31-trend-weighting-design.md
git commit -m "docs: add trend weighting design spec"
```