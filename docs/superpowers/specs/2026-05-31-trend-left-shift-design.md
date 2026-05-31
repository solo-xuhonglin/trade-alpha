# 趋势左移（Trend Left Shift）设计文档

## 1. 概述

### 1.1 问题背景

现有的排名策略包含三个处理阶段：

1. **EWMA 平滑** — 降噪，消除随机波动
2. **动量加成** — 奖励持续正分股票，提升排名稳定性
3. **暴涨排除** — 排除价格+成交量异常放量的股票

但这三个阶段都是**静态或历史统计型的**，缺乏对**分数变化趋势（方向 + 强度）**的感知。具体表现为：

- 分数从低到高攀升时，等到分数超过阈值才买入，**错过早期介入点**
- 分数从高到低回落时，等到分数跌破阈值才卖出，**反应滞后**
- 动量加成只看"正分天数占比"，不区分是"缓慢改善"还是"急速恶化"

### 1.2 目标

增加**趋势左移（Trend Left Shift）**机制，通过检测分数的**变化斜率**，将趋势信息提前反映到排名中：

- 分数上升趋势 → 排名提前（更早买入）
- 分数下降趋势 → 排名延后（更早卖出）
- 调整幅度受上限控制，不造成大幅突破

---

## 2. 数学原理

### 2.1 线性回归斜率

对过去 N 天的平滑后分数序列 `scores[0..N-1]`，拟合线性回归：

```
斜率 = (N * Σ(x*y) - Σx * Σy) / (N * Σ(x²) - (Σx)²)
```

其中 `x = [0, 1, 2, ..., N-1]` 表示时间偏移，`y` 为分数值。

**计算示例**（window=5）：

| t | score |
|---|-------|
| T-4 | 0.10 |
| T-3 | 0.15 |
| T-2 | 0.12 |
| T-1 | 0.18 |
| T   | 0.22 |

```
N = 5
Σx = 0+1+2+3+4 = 10
Σy = 0.10+0.15+0.12+0.18+0.22 = 0.77
Σxy = 0*0.10 + 1*0.15 + 2*0.12 + 3*0.18 + 4*0.22 = 0+0.15+0.24+0.54+0.88 = 1.81
Σx² = 0+1+4+9+16 = 30

slope = (5*1.81 - 10*0.77) / (5*30 - 10²) = (9.05 - 7.70) / (150 - 100) = 1.35 / 50 = 0.027
```

斜率 0.027 表示每交易日分数平均上升 0.027。

### 2.2 趋势加成计算

```
trend_boost = clamp(slope * trend_scale, -max_trend_boost, +max_trend_boost)
composite_score = score + momentum_bonus + trend_boost
```

其中：
- `score` — EWMA 平滑后的分数
- `momentum_bonus` — 动量加成（已有）
- `trend_boost` — 趋势加成（新）
- `trend_scale` — 斜率放大系数（默认 0.5）
- `max_trend_boost` — 单方向最大加成/减成（默认 0.05）

### 2.3 限制条件

- **输入是平滑后分数**：trend 在 `_smooth_scores` 之后、`_apply_momentum_boost` 之前计算，使用平滑后的分数计算斜率，避免原始噪声被放大
- **独立于动量加成**：动量加成衡量"正分稳定性"，趋势加成衡量"变化方向"，两者互补
- **买卖双向影响**：由于卖出判断也使用 composite_score，上升趋势会降低卖出概率，下降趋势会增加卖出概率，符合直觉

---

## 3. Pipeline 修改

### 3.1 新增方法 `_apply_trend_boost`

```python
def _apply_trend_boost(self, pred_results: Dict[str, Dict]) -> None:
    """Apply trend left shift based on score slope over recent window.

    Uses linear regression slope of smoothed scores to detect trend.
    Only applied when strategy config has use_trend_boost=True.
    """
    if not self.strategy_config or not self.strategy_config.use_trend_boost:
        for r in pred_results.values():
            r["trend_boost"] = 0.0
            r["score_slope"] = 0.0
        return

    window = self.strategy_config.trend_window
    scale = self.strategy_config.trend_scale
    max_boost = self.strategy_config.max_trend_boost

    for ts_code, r in pred_results.items():
        raw = r["score"]
        buf = self._score_buffer_trend.setdefault(ts_code, [])
        buf.append(raw)
        if len(buf) > window:
            buf.pop(0)

        if len(buf) >= 3:
            slope = _calc_linear_slope(buf)
        else:
            slope = 0.0

        trend_boost = max(-max_boost, min(max_boost, slope * scale))
        r["score"] = raw + trend_boost
        r["trend_boost"] = trend_boost
        r["score_slope"] = slope
```

### 3.2 新增辅助函数

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
```

### 3.3 调用顺序

修改 `_predict` 和 `run_live`，在 `_smooth_scores` 之后、`_apply_momentum_boost` 之前插入：

```
_prediction / run_live:
  1. compute_scores (原始分数)
  2. _smooth_scores (EWMA 平滑)
→ 3. _apply_trend_boost (趋势左移)  ← NEW
  4. _apply_momentum_boost (动量加成)
  5. _filter_explosions (暴涨排除)
  6. _record_ranks (记录排名)
```

**为什么在动量加成之前？**

趋势左移的输入应该是**平滑后但未加成的原始分数**，这样：
- 动量加成的是"趋势调整后的分数"，动量加成看到的分数已经包含了趋势信息
- 如果反过来（先动量后趋势），趋势左移看到的分数会被动量加成扭曲

### 3.4 新增缓冲区

`__init__` 中新增：

```python
self._score_buffer_trend: Dict[str, List[float]] = {}  # ts_code -> trend window
```

---

## 4. 数据模型修改

### 4.1 StrategyConfig 新增字段

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `use_trend_boost` | bool | false | 启用趋势左移 |
| `trend_window` | int | 5 | 斜率计算窗口（交易日） |
| `trend_scale` | float | 0.5 | 斜率放大系数 |
| `max_trend_boost` | float | 0.05 | 单方向最大加成 |

### 4.2 ScoredStock 新增字段

```python
class ScoredStock:
    ts_code: str
    stock_name: str
    close: float
    up_prob_3d: float
    up_prob_5d: float
    score: float
    is_excluded: bool = False
    trend_boost: float = 0.0  # NEW
```

### 4.3 PendingOrder 新增字段

不需要修改。

### 4.4 ExecutionDailySnapshot.predictions 新增字段

每个 prediction 对象新增：
- `trend_boost: float` — 趋势加成值
- `score_slope: float` — 原始斜率值（用于分析）

---

## 5. API 修改

### 5.1 StrategyConfig API

- `schemas.py`：`StrategyCreateRequest` 新增前述 4 个字段
- `service.py`：`create_strategy` / `update_strategy` 新增参数
- `router.py`：传递新字段

### 5.2 前端配置页面（StrategyConfigView.vue）

参照已有"排名优化"tab 中动量加成的模式，在暴涨排除下方新增趋势左移配置区：

```html
<!-- 排名优化 tab 内，暴涨排除之后 -->
<v-divider class="my-4"></v-divider>

<div class="d-flex align-center mb-2">
  <v-switch v-model="form.use_trend_boost" hide-details density="compact" color="primary"
    class="mr-2" label="趋势左移"></v-switch>
  <v-chip size="x-small" variant="outlined" color="info">分数趋势提前反映</v-chip>
</div>
<v-row>
  <v-col cols="12" md="4">
    <v-text-field v-model.number="form.trend_window" type="number"
      label="窗口天数" hint="斜率计算的天数" persistent-hint
      :disabled="!form.use_trend_boost"></v-text-field>
  </v-col>
  <v-col cols="12" md="4">
    <v-text-field v-model.number="form.trend_scale" type="number" step="0.1"
      label="斜率系数" hint="斜率×系数=趋势加成" persistent-hint
      :disabled="!form.use_trend_boost"></v-text-field>
  </v-col>
  <v-col cols="12" md="4">
    <v-text-field v-model.number="form.max_trend_boost" type="number" step="0.01"
      label="最大加成" hint="上下限，防止过度干预" persistent-hint
      :disabled="!form.use_trend_boost"></v-text-field>
  </v-col>
</v-row>
```

**form 对象新增字段：**

```typescript
use_trend_boost: false,
trend_window: 5,
trend_scale: 0.5,
max_trend_boost: 0.05,
```

**Strategy 接口新增字段（strategyConfig.ts）：**

```typescript
export interface Strategy {
  // ... 已有字段
  use_trend_boost?: boolean
  trend_window?: number
  trend_scale?: number
  max_trend_boost?: number
}
```

### 5.3 回测分析页面（BacktestRecordsView.vue）

**不新增独立 tab。** 趋势左移的效果通过已有 PredictionChart 的原始分和复合分双线对比即可观察：

- **原始分**（灰色虚线）— EWMA 平滑后分数
- **复合分**（蓝色实线）— 平滑 + 趋势左移 + 动量加成的最终分数

当趋势左移启用时，两条线的差距就是 `trend_boost + momentum_bonus` 的叠加效果。不需要新增独立的趋势分析统计表或 API 端点。

---

## 6. 参数建议

| 参数 | 默认值 | 激进 | 保守 | 说明 |
|------|--------|------|------|------|
| trend_window | 5 | 3 | 10 | 窗口越小越敏感，越大越平滑 |
| trend_scale | 0.5 | 1.0 | 0.2 | 系数越大趋势影响越大 |
| max_trend_boost | 0.05 | 0.10 | 0.02 | 上限防止过度干预 |

---

## 7. 与已有机制的交互

| 机制 | 相互作用 |
|------|----------|
| **EWMA 平滑** | trend 基于平滑后分数计算，避免噪声放大 |
| **动量加成** | 互补关系：动量看"历史正分占比"，趋势看"近期变化方向" |
| **暴涨排除** | 独立：trend_boost 影响 composite_score，explosion 独立排除候选 |
| **原始评分卖出** | 卖出判断使用 composite_score，trend_boost 向下时会自然触发更早卖出 |
| **单股持仓上限** | 不受影响，PortfolioManager 独立管理 |