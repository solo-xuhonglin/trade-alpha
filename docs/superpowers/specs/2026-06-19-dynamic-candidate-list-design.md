# 动态候选股票列表设计文档

## 问题

当前回测功能在未指定 `ts_codes` 时，使用**当前时间**的 `StockList.total_mv` 排序取前 N 名作为候选股票池。这导致历史回测存在两个问题：

1. **幸存者偏差**：会把现在涨起来的股票纳入历史回测，与实际历史情况不符
2. **前视偏差**：用未来的市场信息（市值排名）决定过去的选股

## 方案：运行期动态计算候选列表

### 核心思路

每月第一个交易日，根据**当时的** `StockListHistory`（历史市值快照）查询市值前 N 名，构建 `{月份: [股票列表]}` 映射。回测流水线在逐日迭代时：

- 评分/排名只对**当前月的候选池**内股票进行，确保排名反映候选池内相对强弱
- 买入只考虑候选池内的股票
- 持仓股票落选候选池时自动卖出
- 使用首月候选池初始化买入持有基线，每日重平衡基线使用每月候选池

### 架构总览

```
BacktestRunner
  │
  ├─ CandidateListProvider.get_monthly_candidates(start, end, top_n)
  │     → {YYYYMM: [ts_codes]}
  │
  ├─ union_ts_codes = {c for codes in candidate_map.values() for c in codes}
  │     （数据加载用，DataLoader 缓存共享）
  │
  ├─ first_month_codes = candidate_map[first_month]
  │     （买入持有基线用）
  │
  └─ Pipeline(union_ts_codes, candidate_map, first_month_codes)
         │
         ├─ 数据层：加载 union_ts_codes 全部数据（缓存友好）
         │
         ├─ 买入持有基线：用 first_month_codes 初始化，后续不动
         │
         ├─ 重平衡基线：每月用当前候选池的 close_prices 计算（已解耦）
         │
         ├─ 评分层：只对 current_month_candidates 评分
         │   └─ 候选池外的股票不评分，不占排名位置
         │
         ├─ 策略层：make_orders(候选池评分结果)
         │   └─ 买入只从候选池选
         │
         ├─ 落选持仓检测：持仓落选候选池 → 生成卖出订单
         │
         └─ 快照：不变
```

## 影响范围

### 涉及文件

| # | 文件 | 改动量 | 说明 |
|---|------|-------|------|
| 1 | `backend/src/trade_alpha/execution/candidate_list_provider.py` | **新增** ~80 行 | 动态候选池查询服务 |
| 2 | `backend/src/trade_alpha/task/backtest_runner.py` | ~15 行 | 调用 Provider 生成候选池并传参 |
| 3 | `backend/src/trade_alpha/execution/backtest_pipeline.py` | ~60 行 | `__init__` + 主循环 + `_detect_outdated_positions` |
| 4 | `backend/src/trade_alpha/execution/baseline_tracker.py` | ~1 行（移除） | `track()` 中移除对 `_update_daily_rebalanced` 的自动调用 |
| 5 | `backend/src/trade_alpha/constants.py` | +1 行 | `SELL_REASON_CANDIDATE_EXCLUDED` |
| 6 | `backend/tests/trade_alpha/unit/execution/test_candidate_list_provider.py` | **新增** | 单元测试 |
| 7 | 集成测试 `test_61_backtest_lstm.py` | ~5 行 | 适配新参数 |

### 不涉及改动的文件

| 文件 | 原因 |
|------|------|
| `DataLoader` | 数据加载层面不变，仍是加载 union 范围 |
| `ScoreManager` | 只接收传入的 close_prices，传候选池的就只评候选池 |
| `MultiStockStrategy` | 策略逻辑不变，scored_stocks 少了而已 |
| `MarketRegimeAnalyzer` | 市况分析只依赖 daily_rebalanced_values |
| `SuggestionPipeline` | 仅影响回测，不影响实盘建议 |
| 前端代码 | 无功能改动 |
| API 层 | 无需新增/修改接口 |
| ExecutionResult schema | 无需修改 |

## 模块设计

### 模块 1：CandidateListProvider

```python
# backend/src/trade_alpha/execution/candidate_list_provider.py

class CandidateListProvider:
    """Provide monthly candidate stock list for backtesting.

    For each month in the backtest period, finds the first trading day,
    queries the historical market cap top N stocks from StockListHistory,
    and returns a {YYYYMM: [ts_codes]} mapping.
    """

    async def get_monthly_candidates(
        self,
        start_date: str,
        end_date: str,
        top_n: int = 100,
    ) -> Dict[str, List[str]]:
        """动态计算回测期间每月首个交易日的候选股票列表。"""
```

逻辑：
1. 从 `TradeCalendar` 获取 `start_date~end_date` 所有 `is_open==1` 的交易日
2. 按月份分组，取每月的第一个交易日
3. 对每个交易日调用 `resolve_and_fetch_historical_date` 确保 `StockListHistory` 有数据
4. 从 `StockListHistory` 按 `total_mv DESC` 取 `top_n` 只股票
5. 返回 `{YYYYMM: [ts_codes]}` 映射

### 模块 2：BacktestRunner 变更

```python
# backtest_runner.py:55-61 替换为

ts_codes = params.get("ts_codes")
if not ts_codes:
    provider = CandidateListProvider()
    candidate_map = await provider.get_monthly_candidates(
        start_date=params["start_date"],
        end_date=params["end_date"],
        top_n=params.get("top_n", 100),
    )
    union_codes = list({c for codes in candidate_map.values() for c in codes})
    ts_codes = union_codes
else:
    candidate_map = None  # 手动选股模式下跳过

pipeline = BacktestPipeline(
    ...,
    ts_codes=ts_codes,
    candidate_map=candidate_map,
)
```

### 模块 3：BacktestPipeline 变更

#### `__init__`

```python
class BacktestPipeline:
    def __init__(self, ..., candidate_map: Optional[Dict[str, List[str]]] = None):
        ...
        self.candidate_map = candidate_map or {}
        self._current_candidates: List[str] = []
```

#### `run_backtest()`

- 从 `candidate_map` 获取首月候选池
- `BaselineTracker(first_month_codes, initial_capital)` 初始化买入持有基线
- 预热阶段使用首月候选池计算重平衡基线和评分

#### `_run_warmup()`

预热期间，候选池固定在首月候选池，确保重平衡基线和评分预热一致：
- `track_daily_rebalanced_only(candidate_close)` 用候选池 close
- `predict_and_score(close_prices=candidate_close)` 用候选池 close

#### `_run_daily_loop()` 主循环

```
  ① current_month = date[:6]
     → self._current_candidates = self.candidate_map[current_month]

  ② baseline_tracker.track(close_prices)
     （买入持有基线，用全部 close 但只计算首月已买入的部分）

  ③ baseline_tracker.track_daily_rebalanced_only(candidate_close)
     （重平衡基线，只计算候选池内股票）

  ④ stock_map = predict_and_score(close_prices=candidate_close)
     （评分排名只在候选池内）

  ⑤ pending_orders = strategy.make_orders(scored_stocks=list(stock_map.values()))
     （买入只考虑候选池）

  ⑥ outdated_orders = _detect_outdated_positions(date, close_prices)
     pending_orders.extend(outdated_orders)
     （持仓落选 → 卖出）
```

#### `_detect_outdated_positions()`

遍历 `self.portfolio.positions`，任何 `ts_code not in self._current_candidates` 的持仓生成全量卖出订单：

```python
PendingOrder(
    ts_code=ts_code,
    order_shares=-pos.shares,
    order_price=close_prices.get(ts_code, 0),
    reason=SELL_REASON_CANDIDATE_EXCLUDED,
)
```

### 模块 4：BaselineTracker 变更

`track()` 方法中移除对 `_update_daily_rebalanced()` 的调用，让调用方分别控制：

```python
def track(self, close_prices: Dict[str, float]) -> None:
    # 买入持有计算（不变）
    ...
    # 移除: self._update_daily_rebalanced(close_prices)
```

主循环中改为显式分别调用：
- `baseline_tracker.track(all_close_prices)` → 买入持有（首月候选池初始化）
- `baseline_tracker.track_daily_rebalanced_only(candidate_close)` → 每日重平衡（每月候选池）

### 模块 5：常量

```python
# constants.py
SELL_REASON_CANDIDATE_EXCLUDED = "candidate_excluded"
```

### 模块 6：预热阶段

预热阶段（回测正式开始前的数据填充期）：
- 候选池固定在**首月**候选池
- 重平衡基线和评分都在首月候选池上计算
- 买入持有基线不初始化（它在 `run_backtest()` 中已初始化）

## 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 评分排名范围 | 仅候选池 | 排名准确反映候选池内相对强弱，100 名即真实的 top 100 |
| 买入持有基线 | 首月候选池 | 代表"回测开始的被动持有"，与历史实际相符 |
| 重平衡基线 | 每月候选池 | 代表"每月追逐最新 top N"的被动策略 |
| 落选持仓 | 自动卖出 | 策略不处理"候选池外的持仓"，由 Pipeline 兜底 |
| 手动选股 | `candidate_map=None` | 向后兼容，单股票模式直接忽略 |
| 卖出原因 | 新增常量 | 便于在快照和交易记录中区分"是落选卖出还是策略卖出" |
