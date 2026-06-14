# 市场状态指导交易逻辑

## 1. 概述

在已有市场分析功能的基础上，将市场模式（trending_up / sideways / trending_down）的计算前移到 `make_decisions()` 之前，使策略的买卖决策可以感知当前市场状态。新增一个开关 `use_market_aware_trading`，开启后：

- **trending_down（下跌趋势）**：不新买入任何股票
- **sideways（横盘）**：最小持仓时间翻倍（min_hold_days × 2）
- **trending_up（上涨趋势）**：不做额外限制，按原逻辑交易

## 2. StrategyConfig 新增字段

文件：`backend/src/trade_alpha/dao/strategy_config.py`

在 `market_low_score_threshold` 后面新增：

```python
use_market_aware_trading: bool = False      # 开关：市场状态指导交易
```

后端全链路（schemas / router / service）增加此 `Optional[bool]` 字段的传递。

## 3. Pipeline 层：regime 计算前移

### 3.1 新增 _compute_market_regime() 方法

文件：`backend/src/trade_alpha/execution/backtest_pipeline.py`

```python
def _compute_market_regime(self, pred_results: Dict[str, Dict]) -> str:
    rank_scores = [
        p.get("ranking_score", 0) for p in pred_results.values()
        if isinstance(p, dict) and p.get("ranking_score") is not None
    ]
    if not rank_scores:
        return ""
    rank_scores_sorted = sorted(rank_scores)
    median = float(rank_scores_sorted[len(rank_scores_sorted) // 2])
    trend_th = self.strategy_config.market_trend_threshold
    if median > trend_th:
        return "trending_up"
    elif median < -trend_th:
        return "trending_down"
    return "sideways"
```

### 3.2 主循环改动

执行顺序从：

```
_predict() → _save_snapshot()（算 regime） → _make_orders()
```

改为：

```
_predict() → 算 regime → 传给 strategy → _make_orders() → _save_snapshot()
```

具体改动：

```python
# 计算市场模式
market_regime = self._compute_market_regime(pred_results)
self.strategy.market_regime = market_regime

# 快照（regime 已算好，不再重复计算）
day_val, day_ret = await self._save_snapshot(date, backtest_id, close_prices, pred_results)
daily_values.append(day_val)
if day_ret is not None:
    daily_returns.append(day_ret)

# 下单（此时 strategy.market_regime 已可用）
await self._make_orders(scored, close_prices, date)
```

### 3.3 _save_snapshot() 简化

删除原有的大段 rank_scores 计算逻辑（不再重新计算 regime），改为：

```python
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
    # regime 从 strategy 取，不再重复计算
    await snapshot.update({
        "$set": {
            "ranking_median": ranking_median,
            "ranking_high_pct": ranking_high_pct,
            "ranking_low_pct": ranking_low_pct,
            "ranking_regime": self.strategy.market_regime,
        }
    })
```

## 4. 策略层：交易决策受市场模式影响

### 4.1 PositionManager 新增属性

文件：`backend/src/trade_alpha/strategy/base.py`

```python
# 在 __init__() 末尾或作为类属性
self.market_regime: str = ""                  # pipeline 在每次 make_decisions 前设置
self.use_market_aware_trading: bool = False   # 从策略配置传入
```

### 4.2 MultiStockStrategy.__init__() 读取配置

文件：`backend/src/trade_alpha/strategy/multi_stock_strategy.py`

```python
self.use_market_aware_trading = strategy_config.use_market_aware_trading if strategy_config else False
```

### 4.3 make_decisions() 跳过买入（下跌趋势）

在 Phase 1（rank-up priority buy）和 Phase 2（normal fill）外面包一层条件：

```python
can_buy = not (self.use_market_aware_trading and self.market_regime == "trending_down")

# Phase 1
if can_buy and self.use_rank_up_priority and self.rank_up_count > 0:
    ...  # 不变

# Phase 2
if can_buy and remaining_slots > 0:
    ...  # 不变
```

被跳过的场景包括 suggestion_mode（建议模式）。下跌趋势时连买入建议也不生成。

### 4.4 _check_sell() 翻倍 min_hold_days（横盘）

在方法开头计算有效最小持有天数：

```python
def _check_sell(self, position, top_ts_codes, sell_rank_ts_codes, score_map, close_prices=None):
    effective_min_hold = self.min_hold_days
    if self.use_market_aware_trading and self.market_regime == "sideways":
        effective_min_hold = self.min_hold_days * 2

    if position.hold_days < effective_min_hold:
        # 止损检查不变
        if close_prices and position.ts_code in close_prices:
            ...
        return False, ""
    # 后续逻辑不变
```

注意：止损（stop_loss）在 hold_days 不足时仍会执行，不受横盘翻倍影响。

## 5. 前端改动

### 5.1 StrategyConfig TypeScript 接口

文件：`frontend/src/api/strategyConfig.ts`

```typescript
use_market_aware_trading?: boolean
```

### 5.2 StrategyConfigView 市场分析 Tab

在市场分析 Tab 的阈值字段上方新增：

```html
<v-switch v-model="form.use_market_aware_trading" hide-details density="compact"
  color="primary" label="市场状态指导交易"
  hint="下跌趋势不新买入，横盘期间最小持仓天数翻倍" persistent-hint />
```

## 6. 涉及文件清单

| 文件 | 改动 |
|------|------|
| `backend/src/trade_alpha/dao/strategy_config.py` | 新增 `use_market_aware_trading` |
| `backend/src/trade_alpha/api/schemas.py` | Create/UpdateRequest 新增 |
| `backend/src/trade_alpha/api/routers/strategy_config.py` | 序列化 + 传递 |
| `backend/src/trade_alpha/strategy/service.py` | create/update 参数 |
| `backend/src/trade_alpha/strategy/base.py` | PositionManager 新增属性 |
| `backend/src/trade_alpha/strategy/multi_stock_strategy.py` | __init__ 读取；make_decisions 加跳动逻辑；_check_sell 翻倍 |
| `backend/src/trade_alpha/execution/backtest_pipeline.py` | regime 前移 + _save_snapshot 简化 |
| `frontend/src/api/strategyConfig.ts` | 接口新增字段 |
| `frontend/src/views/StrategyConfigView.vue` | 开关 UI |

## 7. 测试

- 开关关闭时，策略行为与之前完全一致（回归）
- 开启开关时 trending_up 状态下无影响
- 开启开关时 trending_down 状态下不生成买入订单（包括建议模式）
- 开启开关时 sideways 状态下持仓最小天数翻倍
- 横盘翻倍不影响止损检查
- 新建/编辑策略配置保存后回读验证 use_market_aware_trading 持久化
