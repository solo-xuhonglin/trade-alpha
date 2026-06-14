# 回测概览新增市场分析标签页 + 排序分指标存储

## 1. 概述

在回测结果弹窗中新增一个「市场分析」标签页，展示策略累计收益率、基准累计收益率、排序分（ranking_score）相关市场状态指标的时序图表。将排序分中位数、>阈值比例、<-阈值比例、市场模式四个指标预计算并写入 `ExecutionDailySnapshot` 文档。替代 K线图中已有的策略/基准收益率曲线。阈值（0.05、0.30、-0.30）从策略配置中读取，而非硬编码。

**关键设计原则：** 市场分析的计算逻辑放在 Pipeline 层。`PositionManager`（持仓管理）、`MultiStockStrategy`（策略类）不做任何改动。

## 2. 策略配置新增字段与 UI

### 2.1 StrategyConfig DAO 新增字段

文件：`backend/src/trade_alpha/dao/strategy_config.py`

```python
market_trend_threshold: float = 0.05       # 排序分中位数高于此值视为趋势市
market_high_score_threshold: float = 0.30   # 排序分高于此值视为"高分"股票
market_low_score_threshold: float = -0.30   # 排序分低于此值视为"低分"股票
```

### 2.2 后端全链路新增字段

以下文件均需增加 `market_trend_threshold`、`market_high_score_threshold`、`market_low_score_threshold` 参数：

| 文件 | 改动内容 |
|------|---------|
| `backend/src/trade_alpha/api/schemas.py` | `StrategyCreateRequest` 和 `StrategyUpdateRequest` 新增三个可选字段 |
| `backend/src/trade_alpha/api/routers/strategy_config.py` | `_strategy_to_dict()` 序列化、create/update endpoint 传递新字段 |
| `backend/src/trade_alpha/strategy/service.py` | `create_strategy()` 和 `update_strategy()` 新增三个参数 |

### 2.3 策略配置前端新增「市场分析」Tab

文件：`frontend/src/views/StrategyConfigView.vue`

Tab 结构变为：`基本配置 | 多股票配置 | 市场分析 | 排名优化 | 交易优化`

新增内容：

```html
<v-window-item value="market">
  <div>
    <v-row>
      <v-col cols="12" md="6">
        <v-text-field v-model.number="form.market_trend_threshold" type="number" step="0.01"
          label="趋势阈值" hint="排序分中位数高于此值 -> 趋势市（默认 0.05）" persistent-hint />
      </v-col>
      <v-col cols="12" md="6">
        <v-text-field v-model.number="form.market_high_score_threshold" type="number" step="0.01"
          label="高分线" hint="排序分高于此值 -> 算高分股（默认 0.30）" persistent-hint />
      </v-col>
    </v-row>
    <v-row>
      <v-col cols="12" md="6">
        <v-text-field v-model.number="form.market_low_score_threshold" type="number" step="0.01"
          label="低分线" hint="排序分低于此值 -> 算低分股（默认 -0.30）" persistent-hint />
      </v-col>
    </v-row>
  </div>
</v-window-item>
```

同时更新前端 `StrategyConfig` TypeScript 接口（`frontend/src/api/strategyConfig.ts`）包含三个新字段。

## 3. 后端改动

### 3.1 ExecutionDailySnapshot 新增字段

文件：`backend/src/trade_alpha/dao/execution_daily_snapshot.py`

```python
ranking_median: float = 0.0          # 全市场 ranking_score 中位数
ranking_high_pct: float = 0.0        # ranking_score > 高分线的股票占比 (%)
ranking_low_pct: float = 0.0         # ranking_score < 低分线的股票占比 (%)
ranking_regime: str = ""             # 市场模式: "trending" / "sideways" / ""
```

前三个为 float，默认 0.0。`ranking_regime` 为 str，默认空字符串。已有数据读取时为空，兼容旧数据。

### 3.2 计算并写入新增字段（Pipeline 层）

**不修改 `base.py` 和 `multi_stock_strategy.py`。** 计算逻辑放在 Pipeline 的 `_save_snapshot()` 方法中。

文件：`backend/src/trade_alpha/execution/backtest_pipeline.py`，`BacktestPipeline._save_snapshot()`

```python
async def _save_snapshot(self, date: str, backtest_id: PydanticObjectId,
                          close_prices: Dict[str, float],
                          pred_results: Dict[str, Dict]) -> Tuple[float, Optional[float]]:
    baseline_value = self._baseline_daily_values[-1] if len(self._baseline_daily_values) > 0 else self.portfolio.cash
    snapshot = await self.strategy.daily_snapshot(
        backtest_id=backtest_id, date=date, cash=self.portfolio.cash,
        positions=self.portfolio.positions, close_prices=close_prices,
        prev_total_value=self.prev_total_value, predictions=pred_results,
        baseline_value=baseline_value,
    )

    # 计算市场状态指标（无需修改 PositionManager）
    rank_scores = [
        p.get("ranking_score", 0) for p in pred_results.values()
        if isinstance(p, dict) and p.get("ranking_score") is not None
    ]
    if rank_scores:
        rank_scores_sorted = sorted(rank_scores)
        n = len(rank_scores_sorted)
        ranking_median = float(rank_scores_sorted[n // 2])
        high_th = self.strategy_config.market_high_score_threshold
        low_th = self.strategy_config.market_low_score_threshold
        ranking_high_pct = sum(1 for s in rank_scores_sorted if s > high_th) / n * 100
        ranking_low_pct = sum(1 for s in rank_scores_sorted if s < low_th) / n * 100
        trend_th = self.strategy_config.market_trend_threshold
        ranking_regime = "trending" if ranking_median > trend_th else "sideways"

        await snapshot.update({
            "$set": {
                "ranking_median": ranking_median,
                "ranking_high_pct": ranking_high_pct,
                "ranking_low_pct": ranking_low_pct,
                "ranking_regime": ranking_regime,
            }
        })

    self.prev_total_value = snapshot.total_value
    return snapshot.total_value, snapshot.day_return
```

同样的逻辑也需在 `SuggestionPipeline` 的对应快照方法中添加（文件 `backend/src/trade_alpha/execution/suggestion_pipeline.py`）。

### 3.3 API 返回新字段

文件：`backend/src/trade_alpha/execution/backtest_service.py`，`get_daily_snapshots()`

```python
{
    "date": s.date,
    "total_value": s.total_value,
    "baseline_value": s.baseline_value,
    "day_return": s.day_return,
    "ranking_median": s.ranking_median,
    "ranking_high_pct": s.ranking_high_pct,
    "ranking_low_pct": s.ranking_low_pct,
    "ranking_regime": s.ranking_regime,
}
```

### 3.4 前端 TypeScript 类型更新

文件：`frontend/src/api/backtestRecord.ts`，`DailySnapshot` 接口

```typescript
export interface DailySnapshot {
  date: string
  total_value: number
  baseline_value: number
  day_return: number
  ranking_median: number
  ranking_high_pct: number
  ranking_low_pct: number
  ranking_regime: string
}
```

## 4. 前端改动

### 4.1 回测结果弹窗新增「市场分析」标签页

文件：`frontend/src/views/BacktestRecordsView.vue`

Tab 结构从 `概览 | 盈亏分析 | 交易优化` 改为 `概览 | 市场分析 | 盈亏分析 | 交易优化`。

新增 `v-window-item value="market"`，引用新的 `OverviewChart` 组件。概览 TAB 不再包含图表（只保留指标表格）。

### 4.2 新建 OverviewChart 组件

文件：`frontend/src/components/OverviewChart.vue`

ECharts 图表，参数：

| Prop | 类型 | 说明 |
|------|------|------|
| `data` | `OverviewChartItem[]` | 每日数据数组 |
| `trendThreshold` | `number` | 趋势阈值（来自 strategy_snapshot.market_trend_threshold） |

```typescript
export interface OverviewChartItem {
  date: string
  strategy_return: number        // 策略累计收益率 (%)
  baseline_return: number        // 基准累计收益率 (%)
  ranking_median: number         // 排序分中位数
  ranking_high_pct: number       // ranking_score > 高分线比例 (%)
  ranking_low_pct: number        // ranking_score < 低分线比例 (%)
  ranking_regime: string         // 市场模式: trending / sideways
}
```

Y 轴设计（同一图表，多 Y 轴）：

```
左 Y 轴 (策略/基准收益率)：范围自适应，标签"收益率(%)"
内嵌右 Y 轴 (排序分中位数)：范围 -0.5 ~ +0.5（硬编码），标签"排序分"
右 Y 轴 (>高分线% / <低分线%)：范围 0~max，标签"占比(%)"
```

曲线（五条线，默认全部显示）：

| 曲线 | 颜色 | Y轴 | 线型 |
|------|------|-----|------|
| 策略累计收益率 | `#ff9800` 橙色 | 左Y | 实线 2px |
| 基准累计收益率 | `#9c27b0` 紫色 | 左Y | 虚线 2px |
| 排序分中位数 | `#2196F3` 蓝色 | 内嵌Y | 实线 1.5px |
| >高分线比例 | `#4caf50` 绿色 | 右Y | 实线 1px |
| <低分线比例 | `#f44336` 红色 | 右Y | 实线 1px |

根据传入的 `trendThreshold` prop，在排序分 Y 轴上用 `markLine` 绘制一条辅助虚线（灰色，1px）。tooltip 中显示当前日期的 `ranking_regime`。legend 可切换曲线显示。

### 4.3 从 K 线图中移除策略/基准收益率

文件：`frontend/src/components/StockKlineChart.vue`

- 删除 `strategyReturns` / `baselineReturns` / `dailySnapshots` 三个 prop
- 删除对应的 `yAxisId: 'returns'` Y轴配置
- 删除 `series` 中"策略收益率"和"基准收益率"两条曲线
- 删除 tooltip 中 `showReturns` 逻辑
- 删除 `props.strategyReturns.length > 0` 条件判断和排名轴 offset 调整

文件：`frontend/src/components/PredictionChart.vue`

- 删除 `dailySnapshots`、`strategyReturns`、`baselineReturns` 相关变量和方法
- 删除 `calculateReturns()` 方法
- 删除加载 `dailySnapshots` 的 try/catch 块
- StockKlineChart 不再传入 `strategy-returns` 和 `baseline-returns` prop

### 4.4 数据加载流程

`viewResult()` 在打开弹窗时：

1. 调用 `getDailySnapshots(result_id)` 获取每日数据（含四个新字段）
2. 用 `calculateReturns()` 将 total_value / baseline_value 转为累计收益率
3. 从 `selectedResult.strategy_snapshot.market_trend_threshold` 获取趋势阈值（旧回测无此字段时默认 0.05）
4. 将组装后的 `OverviewChartItem[]` 和趋势阈值传入 `OverviewChart` 组件

K线弹窗不再额外加载 dailySnapshots。

## 5. 涉及文件清单

| 文件 | 改动类型 |
|------|---------|
| `backend/src/trade_alpha/dao/strategy_config.py` | 新增 3 个阈值字段 |
| `backend/src/trade_alpha/dao/execution_daily_snapshot.py` | 新增 4 个预计算字段 |
| `backend/src/trade_alpha/execution/backtest_pipeline.py` | `_save_snapshot()` 新增计算逻辑 |
| `backend/src/trade_alpha/execution/suggestion_pipeline.py` | 对应快照方法新增计算逻辑 |
| `backend/src/trade_alpha/execution/backtest_service.py` | `get_daily_snapshots()` 返回新字段 |
| `backend/src/trade_alpha/api/schemas.py` | StrategyCreate/UpdateRequest 新增字段 |
| `backend/src/trade_alpha/api/routers/strategy_config.py` | 序列化 + create/update 传递 |
| `backend/src/trade_alpha/strategy/service.py` | create/update 新增参数 |
| `frontend/src/api/backtestRecord.ts` | DailySnapshot 接口新增 4 字段 |
| `frontend/src/api/strategyConfig.ts` | StrategyConfig 接口新增 3 字段 |
| `frontend/src/views/BacktestRecordsView.vue` | 新增「市场分析」Tab + 数据加载 |
| `frontend/src/views/StrategyConfigView.vue` | 新增「市场分析」Tab 表单 |
| `frontend/src/components/OverviewChart.vue` | **新建** ECharts 图表组件 |
| `frontend/src/components/StockKlineChart.vue` | 删除策略/基准收益率曲线 |
| `frontend/src/components/PredictionChart.vue` | 删除快照加载和收益率计算 |

## 6. 测试

- 打开已完成的回测，确认概览 TAB 保持不变
- 打开已完成的回测，确认市场分析 TAB 显示五条曲线，图例切换正常
- 打开策略配置编辑页，确认「市场分析」Tab 显示三个参数
- 新建/编辑策略配置，保存后回读确认参数持久化
- 运行一次新回测，确认每日快照中写入新字段、市场模式计算正确
- 打开已完成的回测，确认 K 线弹窗不再显示收益率曲线
