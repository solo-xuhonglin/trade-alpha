# Backtest Pipeline 重构 — 设计文档

## 动机

当前 [pipeline.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/execution/pipeline.py) 有两个问题：

1. **`single_stock_ts_code` 冗余字段** — 单/多股票本质差异在策略行为，其余流程（基线、预测、快照）应统一，但当前用 `self.single_stock_ts_code` 散落在 11 处做分支，代码复制多、维护成本高
2. **`run_backtest()` 过长**（~350 行）— 循环体内逻辑平铺、临时变量混在一起，难以独立测试和推理

## 设计原则

- 单/多模式只在策略对象这一处分支，其余统一
- 每个方法职责单一、入参明确、不通过 `self` 隐式传递循环变量
- 删除 pipeline 中的 `top_n` — ts_codes 由调用方负责查询传入

## 文件变更

| 文件 | 改动 |
|------|------|
| `execution/pipeline.py` | 核心重构 |
| `task/backtest_runner.py` | 调用 `StockList` 查询 ts_codes |
| `api/routers/backtest.py` | 传递 `ts_codes` 参数 |
| `tests/.../test_61_backtest_lstm.py` | 适配新构造签名 |

---

### 1. 构造函数

```python
from trade_alpha.dao.stock_name_cache import get_stock_names

class ExecutionPipeline:
    def __init__(
        self,
        account_config: AccountConfig,
        training_id: PydanticObjectId,
        model_config: ModelConfig,
        strategy_config: Optional[StrategyConfig] = None,
        mode: str = "multi",
        ts_codes: Optional[List[str]] = None,
    ):
        self.mode = mode
        self.ts_codes = ts_codes or []
        if not self.ts_codes:
            raise ValueError("ts_codes is required for pipeline initialization")

        if mode == "single":
            self.strategy = SingleStockStrategy(
                account_config=account_config,
                strategy_config=strategy_config,
                target_ts_code=self.ts_codes[0],
            )
        else:
            self.strategy = MultiStockStrategy(
                account_config=account_config,
                strategy_config=strategy_config,
                max_positions=10,
                ts_codes=self.ts_codes,
            )

        self.cash = account_config.initial_capital
        self.positions: Dict[str, PositionEmbed] = {}
        self.prev_total_value: Optional[float] = None
        self.pending_orders: List[PendingOrder] = []
        self._score_buffer: Dict[str, List[float]] = {}

        # Baseline tracking — single/multi unified
        self._baseline_daily_values: List[float] = []
        self._baseline_prev_close: Dict[str, float] = {}
```

删除：`single_stock_ts_code`、`max_positions`、`top_n`。

### 2. `run_backtest()` 主编排

```python
async def run_backtest(self, start_date, end_date, name=None, task_id=None):
    result = await self._create_result(start_date, end_date, name)
    await self._ensure_predictor(task_id)
    name_map = await get_stock_names(self.ts_codes)

    self._init_baseline(result.initial_capital)

    daily_values, daily_returns, total_trades, total_fees = \
        await self._run_daily_loop(start_date, end_date, result.id, name_map, task_id)

    await self._finalize_result(result, daily_values, daily_returns,
                                total_trades, total_fees)
    return result
```

`len(self.ts_codes) == 1` 不是模式判断，是数据维度判断。单股票时数据库需要有 `ts_code` 字段。

### 3. 子方法

所有方法接收明确参数，不通过 `self` 传递循环变量。

#### `_create_result()`

```python
async def _create_result(self, start_date, end_date, name) -> ExecutionResult:
    """Create and persist initial ExecutionResult."""
    backtest_name = name or f"backtest_{start_date}_{end_date}"
    result = ExecutionResult(
        account_config_id=self.account_config.id,
        training_id=self.training_id,
        name=backtest_name,
        mode="backtest",
        start_date=start_date,
        end_date=end_date,
        initial_capital=self.account_config.initial_capital,
        final_value=0.0,
        total_return=0.0,
        account_snapshot=AccountSnapshotEmbed(
            name=self.account_config.name,
            initial_capital=self.account_config.initial_capital,
            buy_fee_rate=self.account_config.buy_fee_rate,
            sell_fee_rate=self.account_config.sell_fee_rate,
            stamp_tax_rate=self.account_config.stamp_tax_rate,
            min_fee=self.account_config.min_fee,
        ),
        model_snapshot=ModelSnapshotEmbed(**{
            k: v for k, v in self.model_config.model_dump().items()
            if k in {f for f in ModelSnapshotEmbed.model_fields}
        }) if self.model_config else None,
        strategy_snapshot=StrategySnapshotEmbed(**{
            k: v for k, v in self.strategy_config.model_dump().items()
            if k in {f for f in StrategySnapshotEmbed.model_fields}
        }) if self.strategy_config else None,
        status="running",
    )
    await result.insert()
    logger.info(f"Backtest {result.id} started: {start_date} -> {end_date}")
    return result
```

#### `_init_baseline()`

```python
def _init_baseline(self, initial_capital: float) -> None:
    self._baseline_daily_values = [initial_capital]
    self._baseline_prev_close = {}
```

#### `_skip_non_trading_day()`

```python
@staticmethod
def _skip_non_trading_day(date: str) -> bool:
    return datetime.strptime(date, "%Y%m%d").weekday() >= 5
```

#### `_update_progress()`

```python
@staticmethod
async def _update_progress(task_id, date, year_months, total_months, last_idx) -> int:
    current_ym = (int(date[:4]), int(date[4:6]) if len(date) >= 6 else 1)
    for idx, (y, m) in enumerate(year_months):
        if y == current_ym[0] and m == current_ym[1] and idx >= last_idx:
            await TaskService.update_progress(task_id, 40 + idx / total_months * 50, f"正在回测 {y}年{m}月...")
            return idx + 1
    return last_idx
```

#### `_run_daily_loop()`

```python
async def _run_daily_loop(self, start_date, end_date, backtest_id, name_map, task_id):
    daily_values: List[float] = []
    daily_returns: List[float] = []
    total_trades = 0
    total_fees = 0.0
    year_months = get_year_months(start_date, end_date)
    total_months = len(year_months)
    last_idx = 0

    await TaskService.update_progress(task_id, 40, "正在执行回测...")
    date = start_date
    while date <= end_date:
        if self._skip_non_trading_day(date):
            date = _next_date(date)
            continue

        last_idx = self._update_progress(task_id, date, year_months, total_months, last_idx)
        day_data = await self._load_day_data(date)
        if not day_data:
            date = _next_date(date)
            continue
        close_prices = day_data["close"]

        self._track_baseline(close_prices)

        trades_add, fees_add = await self._settle_orders(date, backtest_id, name_map, day_data)
        total_trades += trades_add
        total_fees += fees_add

        scored, pred_results = await self._predict(date, close_prices, name_map, start_date)
        if not scored:
            date = _next_date(date)
            continue

        await self._make_orders(scored, close_prices, date)
        day_val, day_ret = await self._save_snapshot(date, backtest_id, close_prices, pred_results)
        daily_values.append(day_val)
        if day_ret is not None:
            daily_returns.append(day_ret)

        date = _next_date(date)

    return daily_values, daily_returns, total_trades, total_fees
```

#### `_load_day_data()`

加载当日行情，返回所有行情字典。供 `_settle_orders` 和 `_predict` 使用。

```python
async def _load_day_data(self, date: str):
    day_df = await self.data_loader.load_day_data(date, self.ts_codes)
    if day_df.empty:
        return None
    return {
        "open": dict(zip(day_df["ts_code"], day_df["open"])),
        "high": dict(zip(day_df["ts_code"], day_df["high"])),
        "low": dict(zip(day_df["ts_code"], day_df["low"])),
        "close": dict(zip(day_df["ts_code"], day_df["close"])),
    }
```

#### `_track_baseline()`

```python
def _track_baseline(self, close_prices: Dict[str, float]) -> None:
    """Equal-weighted baseline — works for both single and multi stock."""
    returns = []
    for code in self.ts_codes:
        prev = self._baseline_prev_close.get(code)
        cur = close_prices.get(code)
        if prev and prev > 0 and cur:
            returns.append((cur - prev) / prev)
        self._baseline_prev_close[code] = cur or 0.0
    if returns:
        avg = sum(returns) / len(returns)
        self._baseline_daily_values.append(self._baseline_daily_values[-1] * (1 + avg))
```

#### `_settle_orders()`

```python
async def _settle_orders(self, date: str, backtest_id: PydanticObjectId,
                         name_map: Dict[str, str], day_data: Dict):
    """Settle T-1 pending orders with T's OHLC."""
    if not self.pending_orders:
        return 0, 0.0

    filled_trades, unfilled_orders, net_cash = await self.strategy.settle_orders(
        orders=self.pending_orders,
        date=date,
        open_prices=day_data["open"],
        high_prices=day_data["high"],
        low_prices=day_data["low"],
        backtest_id=backtest_id,
    )
    self.cash += net_cash
    total_trades = len(filled_trades)

    all_trades = filled_trades + [
        ExecutionTrade(
            backtest_id=backtest_id,
            ts_code=order.ts_code,
            trade_date=date,
            action="buy" if order.order_shares > 0 else "sell",
            price=0.0, shares=0, fee=0.0, cash_after=0.0,
            status="cancelled", reason="cancelled",
            entry_score=order.score,
            up_prob_3d=order.up_prob_3d,
            up_prob_5d=order.up_prob_5d,
        )
        for order in unfilled_orders
    ]
    await ExecutionTrade.insert_many(all_trades)

    total_fees = 0.0
    for t in filled_trades:
        total_fees += t.fee
        if t.action == "sell":
            total_fees += abs(t.shares) * t.price * self.account_config.stamp_tax_rate

    for t in filled_trades:
        if t.action == "sell":
            self.positions.pop(t.ts_code, None)
        elif t.action == "buy":
            self.positions[t.ts_code] = PositionEmbed(
                ts_code=t.ts_code,
                stock_name=name_map.get(t.ts_code, ""),
                buy_date=date, buy_price=t.price,
                shares=t.shares, fee=t.fee,
                entry_score=t.entry_score or 0,
                entry_3d_prob=t.up_prob_3d or 0,
                entry_5d_prob=t.up_prob_5d or 0,
                hold_days=0,
            )

    self.pending_orders.clear()
    return total_trades, total_fees
```

#### `_predict()`

```python
async def _predict(self, date: str, close_prices: Dict[str, float], name_map: Dict[str, str], start_date: str):
    target_names = [f"label_{h}d" for h in self._config.classification_horizons]
    pred_results_raw = await self.predictor.predict_batch(self.ts_codes, target_names, date)
    pred_results = {}
    for ts_code, probs in pred_results_raw.items():
        close_price = close_prices.get(ts_code, 0)
        pred_results[ts_code] = compute_scores(probs, close_price, self._config.classification_horizons)
    if not pred_results:
        return [], {}

    self._smooth_scores(pred_results)

    scored = [
        ScoredStock(
            ts_code=ts_code,
            stock_name=name_map.get(ts_code, ts_code),
            close=r["close"],
            up_prob_3d=r["up_prob_3d"],
            up_prob_5d=r["up_prob_5d"],
            score=r["score"],
        )
        for ts_code, r in pred_results.items()
    ]

    self._record_ranks(scored, pred_results)

    # Log first day predictions for debugging
    if date == start_date:
        logger.info(f"First day {date}: {len(pred_results)} predictions, {len(scored)} with score > 0")
        if scored:
            top5 = sorted(scored, key=lambda s: s.score, reverse=True)[:5]
            logger.info(f"Top 5 stocks: " + ", ".join([f"{s.ts_code}({s.score:.3f})" for s in top5]))

    return scored, pred_results
```

#### `_make_orders()`

```python
async def _make_orders(self, scored, close_prices, date):
    pending_orders = await self.strategy.make_decisions(
        scored_stocks=scored,
        current_positions=self.positions,
        cash=self.cash,
        trade_date=date,
        close_prices=close_prices,
    )
    for order in pending_orders:
        order.trade_date = date
        order.settle_date = _next_date(date)
    self.pending_orders = pending_orders
```

#### `_save_snapshot()`

```python
async def _save_snapshot(self, date: str, backtest_id: PydanticObjectId,
                         close_prices: Dict[str, float],
                         pred_results: Dict[str, Dict]) -> Tuple[float, Optional[float]]:
    snapshot = await self.strategy.daily_snapshot(
        backtest_id=backtest_id,
        date=date,
        cash=self.cash,
        positions=self.positions,
        close_prices=close_prices,
        prev_total_value=self.prev_total_value,
        predictions=pred_results,
    )
    self.prev_total_value = snapshot.total_value
    return snapshot.total_value, snapshot.day_return
```

#### `_finalize_result()`

```python
async def _finalize_result(self, result, daily_values, daily_returns,
                           total_trades, total_fees):
    final_value = daily_values[-1] if daily_values else self.cash
    total_return = (final_value - self.account_config.initial_capital) / self.account_config.initial_capital
    max_drawdown = self._calc_max_drawdown(daily_values)
    win_rate = await self._calc_win_rate(result.id)

    # Strategy metrics
    metrics = self.strategy.calculate_metrics(daily_returns)
    result.sharpe_ratio = round(metrics["sharpe_ratio"], 4) if metrics["sharpe_ratio"] else None
    result.volatility = round(metrics["volatility"], 4) if metrics["volatility"] else None
    result.annual_return = round(metrics["annual_return"], 4) if metrics.get("annual_return") else None

    # Calculate average hold days
    trade_metrics = await self.strategy.calculate_trade_metrics(
        await ExecutionTrade.find(ExecutionTrade.backtest_id == result.id).to_list(),
        []
    )
    result.avg_hold_days = round(trade_metrics["avg_hold_days"], 2) if trade_metrics["avg_hold_days"] else None

    # Baseline metrics — single/multi unified
    if len(self._baseline_daily_values) > 1:
        baseline_ret = (self._baseline_daily_values[-1] - self._baseline_daily_values[0]) / self._baseline_daily_values[0]
        result.baseline_return = round(baseline_ret, 4)
        result.baseline_max_drawdown = round(self._calc_max_drawdown(self._baseline_daily_values), 4)
        result.excess_return = round(total_return - baseline_ret, 4)

    result.final_value = round(final_value, 2)
    result.total_return = round(total_return, 4)
    result.max_drawdown = round(max_drawdown, 4)
    result.win_rate = round(win_rate, 4)
    result.total_trades = total_trades
    result.total_fees = round(total_fees, 2)
    result.status = "completed"
    await result.save()

    logger.info(f"Backtest {result.id} completed: return={total_return:.2%}, "
                f"drawdown={max_drawdown:.2%}, trades={total_trades}")
    if result.baseline_return is not None:
        logger.info(f"  Baseline return: {result.baseline_return:.2%}, "
                    f"Excess return: {result.excess_return:.2%}")
    if result.sharpe_ratio is not None:
        logger.info(f"  Sharpe: {result.sharpe_ratio:.2f}, Volatility: {result.volatility:.2%}")

    return result
```

### 4. 调用方

**`backtest_runner.py`** — 加载 ts_codes 后传入：

```python
ts_codes = params.get("ts_codes")
if not ts_codes:
    from beanie.odm.operators.find.comparison import NotIn
    stocks = await StockList.find(
        StockList.sync_status == "active",
        NotIn(StockList.ts_code, TEST_EXCLUDED_TS_CODES),
    ).sort(-StockList.total_mv).limit(params.get("top_n", 100)).to_list()
    ts_codes = [s.ts_code for s in stocks]

pipeline = ExecutionPipeline(
    account_config=account_config,
    training_id=...,
    model_config=model_config,
    strategy_config=strategy_config,
    mode=params["mode"],
    ts_codes=ts_codes,
)
```

**`backtest.py`** — 请求体不变，只是 `top_n` 现在直接存入 task params。

### 5. 测试

**`test_61_backtest_lstm.py`** 调用改为：

```python
pipeline = ExecutionPipeline(
    account_config=...,
    training_id=...,
    model_config=...,
    strategy_config=...,
    mode="single",
    ts_codes=[self.ts_code],
)
```

### 6. 增量 `smooth_scores` / `record_ranks`

这两个方法已经在当前代码中，保持不动。

## 总结

| 指标 | 改前 | 改后 |
|------|------|------|
| `run_backtest()` 行数 | ~350 | ~50（编排） |
| `single_stock_ts_code` 引用 | 11 处 | 0 处 |
| 基线代码分支 | 两套（if/elif） | 一套（无 if mode） |
| `__init__` 参数 | 7 个 | 5 个 |
| ts_codes 空检查 | 限 single 模式 | 所有模式统一入口 |
