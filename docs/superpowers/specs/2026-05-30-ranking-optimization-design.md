# 组合排名策略优化设计

## 概述

在组合排名策略中，纯评分排序导致两个问题：排名波动大、容易追高。新增两个独立机制——**动量加权**和**暴涨排除**——来稳定排名，减少追高买入。均有独立开关，逐步验证效果。

## 背景

当前排名流程：

1. 模型预测 → `compute_scores` 生成各股票评分
2. `_smooth_scores`（3 日 EWMA，alpha=0.5）平滑
3. `multi_stock_strategy.make_decisions` 中按评分降序排列，取 top N 买入
4. 卖出判断基于原始评分（阈值 + 排名出局 + 持仓天数 + 止损）

两个问题的根因：

- **排名波动大**：平滑窗口只有 3 天，alpha=0.5，最新一天仍占主导，评分日间跳动大
- **追高**：某日评分突然飙升的股票直接冲到前列被买入，而评分可能昙花一现

## 数据流架构

```
现有流程（平滑后 score）：
  model → compute_scores → raw_score → _smooth_scores(3d EWMA) → sort → buy
                                                                        ↑
                                                                  卖出用 score_map

新流程：
  model → compute_scores → raw_score → _smooth_scores(3d EWMA) → smoothed_score
                                                                      ↓
                                                    ┌── 动量加权 bonus ──┐
                                                    │ composite = score + bonus │
                                                    │ 暴涨检查 → 标记排除       │
                                                    └──────────┬──────────────┘
                                                               ↓
                                        multi_stock_strategy.make_decisions()
                                          ├─ 买入候选：composite 排序，排除 is_excluded
                                          └─ 卖出判断：原始 smoothed_score（不受影响）
```

关键设计原则：

- **原始评分独立**：卖出判断始终用原始 `score_map`（smoothed_score），不受动量加成影响，确保评分骤降时快速卖出
- **动量加成在 pipeline 层完成**：不在策略层做，保持策略逻辑干净
- **两个功能独立开关**：互不干扰，可单独开启验证

## 动量加权（Momentum Boost）

### 位置

`pipeline.py`，`_predict` 方法中生成 `scored` 列表之后调用 `_apply_momentum_boost`

### 缓冲池

新增 `_score_buffer_momentum: Dict[str, List[float]]`，长度为 `momentum_window`（默认 8），只存平滑后的 score，用于统计正分天数占比。

现有 `_score_buffer`（3 天 EWMA 用）不动。

### 公式

```
positive_ratio = count(score_i > 0 for i in window) / window_size
bonus = positive_ratio * max_momentum_bonus
composite_score = score + bonus
```

### 行为示例（window=8, max_bonus=0.1）

- 连续 6 天评分 > 0 → `ratio=0.75` → `bonus=0.075` → `composite = score + 0.075`
- 仅 2 天评分 > 0 → `ratio=0.25` → `bonus=0.025` → 排名几乎不变
- 评分骤降为负 → 下一日窗口向前滑动，`ratio` 即刻下降，排名迅速反应

### 参数（StrategyConfig）

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `use_momentum_boost` | bool | false | 总开关 |
| `momentum_window` | int | 8 | 统计窗口天数 |
| `max_momentum_bonus` | float | 0.1 | 最大动量加成 |

## 暴涨排除（Explosion Filter）

### 位置

`pipeline.py`，`_predict` 方法中生成 `scored` 列表之后调用 `_filter_explosions`

### 判定逻辑

价格涨幅 **和** 成交量同时异常才标记排除，避免误杀缩量上涨的强势股：

```
price_surge_pct = close / avg_close_window - 1
volume_ratio = vol / avg_vol_window
is_excluded = price_surge_pct > threshold AND volume_ratio > volume_ratio_threshold
```

### 原理

放量暴涨意味着多空分歧大，短期脉冲买盘大量消耗，后续买盘衰竭风险高。LSTM 模型对这种极端行情预测可靠性降低，均值回归倾向显著。

### 数据来源

`DataLoader` 从 `StockDaily` 按 `ts_code` 和时间范围拉取 close 和 vol。数据不足 `explosion_window` 天时不标记排除。

### 标记方式

`ScoredStock` 新增 `is_excluded: bool = False` 字段。

### 买入决策中的使用

`multi_stock_strategy.make_decisions` 中增加一行过滤（排在评分阈值过滤之后）：

```python
scored_stocks = [s for s in scored_stocks if not s.is_excluded]
```

排除只影响**买入候选池**，不影响已持仓股票。

### 参数（StrategyConfig）

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `use_explosion_filter` | bool | false | 总开关 |
| `explosion_price_threshold` | float | 0.15 | 价格涨幅阈值（参考均价的 15%） |
| `explosion_volume_ratio` | float | 3.0 | 成交量倍数阈值（当前量/均量 > 3） |
| `explosion_window` | int | 5 | 参考窗口天数 |

## StrategyConfig 新增字段

```python
# 动量加权
use_momentum_boost: bool = False
momentum_window: int = 8
max_momentum_bonus: float = 0.1

# 暴涨排除
use_explosion_filter: bool = False
explosion_price_threshold: float = 0.15
explosion_volume_ratio: float = 3.0
explosion_window: int = 5
```

所有新增参数默认关闭，不影响现有回测。

## StrategySnapshotEmbed 新增字段

同名同类型字段，确保快照能保存新参数。

## ScoredStock 新增字段

```python
@dataclass
class ScoredStock:
    ts_code: str
    stock_name: str
    close: float
    up_prob_3d: float
    up_prob_5d: float
    score: float
    is_excluded: bool = False  # 新增
```

## 后端 API 改动

### 回测预测 API（已存在的 `/backtests/{id}/predictions/{tsCode}`）

返回数据增加字段：`raw_score`（原始平滑后评分）、`composite_score`（动量加权后评分）、`momentum_bonus`（动量加成值）、`is_excluded`（是否被排除）。

这些字段在 `pipeline.py` 中写入 `pred_results`，已被快照持久化到 `ExecutionDailySnapshot.predictions`。

### 新增暴涨排除统计 API

`GET /backtests/{id}/excluded-stocks`

从 `ExecutionDailySnapshot.predictions` 汇总各日排除记录：

```json
{
  "items": [
    {
      "ts_code": "002594.SZ",
      "stock_name": "比亚迪",
      "excluded_count": 3,
      "excluded_dates": [
        {"date": "20250601", "price_surge_pct": 0.18, "volume_ratio": 3.5}
      ]
    }
  ]
}
```

## 代码改动清单

| 文件 | 改动 |
|------|------|
| `dao/strategy_config.py` | StrategyConfig 新增 7 个字段 |
| `dao/execution.py` | StrategySnapshotEmbed 新增 7 个字段 |
| `schemas.py` | ScoredStock 增加 `is_excluded: bool = False` |
| `execution/pipeline.py` | 新增 `_score_buffer_momentum`、`_apply_momentum_boost()`、`_filter_explosions()` 方法；`_predict` 中编排调用；`compute_scores` 后额外写入 `raw_score` |
| `strategy/multi_stock_strategy.py` | `make_decisions` 中增加 `is_excluded` 过滤 |
| `api/routers/backtest_records.py` | `get_stock_predictions` 返回 `raw_score` / `composite_score` / `is_excluded`；新增 `get_excluded_stocks` 汇总接口 |
| `frontend/src/api/strategyConfig.ts` | Strategy 类型增加 7 个字段 |
| `frontend/src/views/StrategyConfigView.vue` | 新增第三个 tab「排名优化」，包含动量加权和暴涨排除的开关和参数 |
| `frontend/src/views/BacktestRecordsView.vue` | 概览 tab 的 ECharts 增加 raw_score / composite_score 双曲线对比（用 `PredictionChart` 组件改造）；新增「暴涨排除统计」dialog，展示被排除股票的统计表 |
| `frontend/src/api/backtestRecord.ts` | Backtest 类型增加排除统计相关接口 |

## 前端改动详情

### 策略配置 — 新增「排名优化」tab

`StrategyConfigView.vue`：

- 第三个 `v-tab value="ranking"`：排名优化
- 包含两个区域：
  - 动量加权（use_momentum_boost switch + momentum_window / max_momentum_bonus 数字输入）
  - 暴涨排除（use_explosion_filter switch + explosion_price_threshold / explosion_volume_ratio / explosion_window 数字输入）

### 回测分析 — 评分曲线对比

`PredictionChart.vue`（或直接内嵌 ECharts）：

- 在评分时间序列图中用双线（实线 composite_score + 虚线 raw_score），图例区分
- 排名曲线同理，双线对比

### 回测分析 — 暴涨排除统计

`BacktestRecordsView.vue` 结果弹窗新增 tab "暴涨排除"：

- 表格列：股票名称、排除次数、最近排除日期、排除时涨幅、排除时量比
- 数据来源：`GET /backtests/{id}/excluded-stocks`