# Backtest Pipeline 重构 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构 `ExecutionPipeline`：移除 `single_stock_ts_code`、删除 `top_n/max_positions` 参数、提取 11 个私有方法使 `run_backtest()` 精简为~50行编排、将股票池查询移到调用方。

**Architecture:** 一次改完 `pipeline.py`（构造器 + 提取方法），再改两个调用方（`backtest_runner.py`、`test_61_backtest_lstm.py`）。测试通过后提交。

**Tech Stack:** Python 3.14+, FastAPI, Beanie (MongoDB)

---

### Task 1: 重构构造函数

**Files:**
- Modify: `backend/src/trade_alpha/execution/pipeline.py:41-95`
- Check: `backend/src/trade_alpha/execution/pipeline.py` (整文件了解现有状态)

- [ ] **Step 1: 修改 `__init__` 签名和主体**

将当前（约 44-95 行）：

```python
    def __init__(
        self,
        account_config: AccountConfig,
        training_id: PydanticObjectId,
        model_config: ModelConfig,
        strategy_config: Optional[StrategyConfig] = None,
        mode: str = "multi",
        ts_codes: List[str] = None,
        max_positions: int = 10,
        top_n: int = 100,
        single_stock_ts_code: Optional[str] = None,
    ):
        self.account_config = account_config
        self.training_id = training_id
        self.model_config = model_config
        self.strategy_config = strategy_config
        self.mode = mode
        self.ts_codes = ts_codes or []
        self.max_positions = max_positions
        self.top_n = top_n
        self.single_stock_ts_code = single_stock_ts_code

        self._config = model_config

        self.data_loader = DataLoader()
        self.predictor = None  # 延迟初始化
        
        # Initialize strategy based on mode
        if mode == "single":
            # For backward compatibility, support single_stock_ts_code
            target_code = single_stock_ts_code or (ts_codes[0] if ts_codes else None)
            if not target_code:
                raise ValueError("single mode requires ts_codes or single_stock_ts_code")
            self.strategy = SingleStockStrategy(
                account_config=account_config,
                strategy_config=strategy_config,
                target_ts_code=target_code,
            )
            self.single_stock_ts_code = target_code
        else:
            self.strategy = MultiStockStrategy(
                account_config=account_config,
                strategy_config=strategy_config,
                max_positions=max_positions,
                ts_codes=ts_codes,
            )

        self.cash: float = account_config.initial_capital
        self.positions: Dict[str, PositionEmbed] = {}
        self.prev_total_value: Optional[float] = None
        self.pending_orders: List[PendingOrder] = []
        self._score_buffer: Dict[str, List[float]] = {}  # ts_code -> EWMA history
```

改为：

```python
    def __init__(
        self,
        account_config: AccountConfig,
        training_id: PydanticObjectId,
        model_config: ModelConfig,
        strategy_config: Optional[StrategyConfig] = None,
        mode: str = "multi",
        ts_codes: Optional[List[str]] = None,
    ):
        self.account_config = account_config
        self.training_id = training_id
        self.model_config = model_config
        self.strategy_config = strategy_config
        self.mode = mode
        self.ts_codes = ts_codes or []
        if not self.ts_codes:
            raise ValueError("ts_codes is required for pipeline initialization")

        self._config = model_config

        self.data_loader = DataLoader()
        self.predictor = None  # 延迟初始化
        
        # Initialize strategy based on mode
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

        self.cash: float = account_config.initial_capital
        self.positions: Dict[str, PositionEmbed] = {}
        self.prev_total_value: Optional[float] = None
        self.pending_orders: List[PendingOrder] = []
        self._score_buffer: Dict[str, List[float]] = {}
```

- [ ] **Step 2: 删除 `_smooth_scores`/`_record_ranks` 中对 `single_stock_ts_code` 的引用**

在 `_record_ranks` 文档字符串中删除 "Single-stock mode: rank stays 1, harmless." 这一行（仅文档，无实际逻辑影响）。

- [ ] **Step 3: 运行单元测试验证**

```bash
cd d:\projects\trade-alpha\backend
pytest tests/trade_alpha/unit/ -v
```

Expected: 63 passed

- [ ] **Step 4: 提交**

```bash
git add backend/src/trade_alpha/execution/pipeline.py
git commit -m "refactor: remove single_stock_ts_code, max_positions, top_n from constructor"
```

---

### Task 2: 提取子方法 + 重写 `run_backtest()`

**Files:**
- Modify: `backend/src/trade_alpha/execution/pipeline.py:96-474`

- [ ] **Step 1: 添加 `_create_result()` 方法**

在当前 `_record_ranks` 方法之后、`async def run_backtest` 之前添加：

```python
    async def _create_result(self, start_date: str, end_date: str, name: Optional[str] = None) -> ExecutionResult:
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

    async def _ensure_predictor(self, task_id: Optional[PydanticObjectId] = None) -> None:
        """Lazy-init predictor."""
        if self.predictor is None:
            training = await get_training_by_id(self.training_id)
            config = await get_config_by_id(training.config_id)
            classifier = create_classifier(config, training.model_path)
            self.predictor = create_predictor(config, classifier, data_loader=self.data_loader)

    def _init_baseline(self, initial_capital: float) -> None:
        self._baseline_daily_values = [initial_capital]
        self._baseline_prev_close: Dict[str, float] = {}

    @staticmethod
    def _skip_non_trading_day(date: str) -> bool:
        return datetime.strptime(date, "%Y%m%d").weekday() >= 5

    @staticmethod
    async def _update_progress(task_id: Optional[PydanticObjectId], date: str,
                                year_months: list, total_months: int, last_idx: int) -> int:
        current_ym = (int(date[:4]), int(date[4:6]) if len(date) >= 6 else 1)
        for idx, (y, m) in enumerate(year_months):
            if y == current_ym[0] and m == current_ym[1] and idx >= last_idx:
                await TaskService.update_progress(task_id, 40 + idx / total_months * 50, f"正在回测 {y}年{m}月...")
                return idx + 1
        return last_idx

    @staticmethod
    async def _load_day_data(date: str, ts_codes: List[str], data_loader: DataLoader):
        """Load OHLC data for a single day. Returns None if no data."""
        day_df = await data_loader.load_day_data(date, ts_codes)
        if day_df.empty:
            return None
        return {
            "open": dict(zip(day_df["ts_code"], day_df["open"])),
            "high": dict(zip(day_df["ts_code"], day_df["high"])),
            "low": dict(zip(day_df["ts_code"], day_df["low"])),
            "close": dict(zip(day_df["ts_code"], day_df["close"])),
        }

    def _track_baseline(self, close_prices: Dict[str, float]) -> None:
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

    async def _settle_orders(self, date: str, backtest_id: PydanticObjectId,
                              name_map: Dict[str, str], day_data: Dict) -> Tuple[int, float]:
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
        return len(filled_trades), total_fees

    async def _predict(self, date: str, close_prices: Dict[str, float],
                        name_map: Dict[str, str], start_date: str):
        """Predict T+1 signals, smooth scores, rank, return scored stocks."""
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

        if date == start_date:
            logger.info(f"First day {date}: {len(pred_results)} predictions, {len(scored)} with score > 0")
            if scored:
                top5 = sorted(scored, key=lambda s: s.score, reverse=True)[:5]
                logger.info(f"Top 5 stocks: " + ", ".join([f"{s.ts_code}({s.score:.3f})" for s in top5]))

        return scored, pred_results

    async def _make_orders(self, scored: List[ScoredStock],
                            close_prices: Dict[str, float], date: str) -> None:
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

- [ ] **Step 2: 重写 `run_backtest()`**

```python
    async def run_backtest(
        self,
        start_date: str,
        end_date: str,
        name: Optional[str] = None,
        task_id: Optional[PydanticObjectId] = None,
    ) -> ExecutionResult:
        """Run backtest from start_date to end_date (inclusive)."""
        result = await self._create_result(start_date, end_date, name)
        await self._ensure_predictor(task_id)
        name_map = await get_stock_names(self.ts_codes)

        await TaskService.update_progress(task_id, 20, "正在加载股票列表...")

        self._init_baseline(result.initial_capital)

        daily_values, daily_returns, total_trades, total_fees = \
            await self._run_daily_loop(start_date, end_date, result.id, name_map, task_id)

        await self._finalize_result(result, daily_values, daily_returns, total_trades, total_fees)
        return result
```

- [ ] **Step 3: 添加 `_run_daily_loop()`**

在 `run_backtest()` 之后、`run_live()` 之前添加：

```python
    async def _run_daily_loop(self, start_date, end_date, backtest_id, name_map, task_id):
        """Main daily loop. Returns (daily_values, daily_returns, total_trades, total_fees)."""
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

            last_idx = await self._update_progress(task_id, date, year_months, total_months, last_idx)
            day_data = await self._load_day_data(date, self.ts_codes, self.data_loader)
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

- [ ] **Step 4: 添加 `_finalize_result()`**

```python
    async def _finalize_result(self, result, daily_values, daily_returns, total_trades, total_fees):
        """Compute final metrics, persist and return result."""
        final_value = daily_values[-1] if daily_values else self.cash
        total_return = (final_value - self.account_config.initial_capital) / self.account_config.initial_capital

        max_drawdown = self._calc_max_drawdown(daily_values)
        win_rate = await self._calc_win_rate(result.id)

        metrics = self.strategy.calculate_metrics(daily_returns)
        result.sharpe_ratio = round(metrics["sharpe_ratio"], 4) if metrics["sharpe_ratio"] else None
        result.volatility = round(metrics["volatility"], 4) if metrics["volatility"] else None
        result.annual_return = round(metrics["annual_return"], 4) if metrics.get("annual_return") else None

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

- [ ] **Step 5: 添加缺失的 import**

在文件顶部 import 中添加 `Tuple`：

```python
from typing import Dict, List, Optional, Tuple
```

在文件顶部 import 中添加 `get_stock_names`：

```python
from trade_alpha.dao.stock_name_cache import get_stock_names
```

- [ ] **Step 6: 删除旧的 `run_backtest()` 代码**

Task 2 Step 2 已经用新代码覆盖了旧的 `run_backtest()`。确保旧方法体（约 133-474 行）完全被替换。

- [ ] **Step 7: 运行单元测试验证**

```bash
cd d:\projects\trade-alpha\backend
pytest tests/trade_alpha/unit/ -v
```

Expected: 63 passed

- [ ] **Step 8: 提交**

```bash
git add backend/src/trade_alpha/execution/pipeline.py
git commit -m "refactor: extract methods, reduce run_backtest to 50-line orchestration"
```

---

### Task 3: 修改调用方 — backtest_runner.py

**Files:**
- Modify: `backend/src/trade_alpha/task/backtest_runner.py:52-59`

- [ ] **Step 1: 修改 pipeline 构造前的参数准备**

将：

```python
            pipeline = ExecutionPipeline(
                account_config=account_config,
                training_id=PydanticObjectId(params["training_id"]),
                model_config=model_config,
                strategy_config=strategy_config,
                mode=params["mode"],
                ts_codes=params.get("ts_codes"),
                top_n=params.get("top_n", 100),
            )
```

改为：

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
                training_id=PydanticObjectId(params["training_id"]),
                model_config=model_config,
                strategy_config=strategy_config,
                mode=params["mode"],
                ts_codes=ts_codes,
            )
```

- [ ] **Step 2: 添加缺失 import**

确保文件顶部有 `from trade_alpha.dao import StockList` 和 `from trade_alpha.test_config import TEST_EXCLUDED_TS_CODES`。如果没有，添加：

```python
from trade_alpha.dao import StockList
from trade_alpha.test_config import TEST_EXCLUDED_TS_CODES
```

- [ ] **Step 3: 运行集成测试验证**

```bash
cd d:\projects\trade-alpha\backend
pytest tests/trade_alpha/integration/test_60_task_subprocess.py -v
```

Expected: all passed

- [ ] **Step 4: 提交**

```bash
git add backend/src/trade_alpha/task/backtest_runner.py
git commit -m "refactor: move StockList query to backtest_runner, pass ts_codes to pipeline"
```

---

### Task 4: 修改调用方 — test_61_backtest_lstm.py

**Files:**
- Modify: `backend/tests/trade_alpha/integration/test_61_backtest_lstm.py:59-67`

- [ ] **Step 1: 修改测试中的 pipeline 构造**

将：

```python
        pipeline = ExecutionPipeline(
            account_config=self.account_config,
            training_id=self.training.id,
            model_config=self.model_config,
            strategy_config=self.strategy_config,
            mode="single",
            ts_codes=[self.ts_code],
            max_positions=10,
        )
```

改为：

```python
        pipeline = ExecutionPipeline(
            account_config=self.account_config,
            training_id=self.training.id,
            model_config=self.model_config,
            strategy_config=self.strategy_config,
            mode="single",
            ts_codes=[self.ts_code],
        )
```

- [ ] **Step 2: 运行集成测试验证**

```bash
cd d:\projects\trade-alpha\backend
pytest tests/trade_alpha/integration/test_61_backtest_lstm.py -v
```

Expected: 4 passed

- [ ] **Step 3: 提交**

```bash
git add backend/tests/trade_alpha/integration/test_61_backtest_lstm.py
git commit -m "refactor: remove max_positions from test pipeline constructor call"
```

---

### Task 5: 全量回归测试 + 最终提交

- [ ] **Step 1: 运行全部测试**

```bash
cd d:\projects\trade-alpha\backend
pytest tests/trade_alpha/unit/ -v
pytest tests/trade_alpha/integration/ -v
```

Expected: 63 + 87 passed

- [ ] **Step 2: 重启服务验证 API**

```bash
cd d:\projects\trade-alpha
& .\service.bat stop
Start-Sleep -Seconds 2
& .\service.bat start
Start-Sleep -Seconds 10
```

然后检查 `/api/backtest/tasks` 和 `/api/backtests` 端点正常返回。

- [ ] **Step 3: 最终提交（spec + plan）**

```bash
git add docs/superpowers/specs/2026-05-26-backtest-pipeline-refactor.md
git add docs/superpowers/plans/2026-05-26-backtest-pipeline-refactor.md
git commit -m "docs: add pipeline refactor spec and implementation plan"
```
