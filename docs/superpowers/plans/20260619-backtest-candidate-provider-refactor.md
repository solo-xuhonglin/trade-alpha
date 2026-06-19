# Backtest CandidateListProvider 重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将候选池管理统一到 CandidateListProvider，消除 BacktestPipeline 中分散的 ts_codes/candidate_map/周状态，简化 BacktestRunner。

**Architecture:** CandidateListProvider 内部封装固定列表和动态周候选两种模式，通过 initialize() 按需构建；BacktestPipeline 通过 params 接收任务参数，内部创建 Provider 并注入 PipelineContext；Strategy 类运行时从 ctx 获取候选代码。

**Tech Stack:** Python 3.14+, FastAPI, MongoDB (Beanie ODM)

---

### Task 1: 重构 CandidateListProvider

**Files:**
- Modify: `backend/src/trade_alpha/execution/candidate_list_provider.py`

**变更说明：**
- 新增 `__init__(self, params)`，从 params 提取 ts_codes/range_n/top_n/up_n
- 新增 `all_ts_codes` 属性（统一两种模式的代码获取）
- 新增 `initialize(start_date, end_date)` 延迟构建 candidate_map
- 新增 `get_candidates_for_date(date)` 透明处理周切换
- 新增 `get_pending_codes()` 识别非活跃候选股票
- 迁移 `_get_week_key` 方法到此类（从 BacktestPipeline 移入）
- 保留现有 DB 查询方法不变

- [ ] **Step 1: 重写 `__init__`，新增属性和方法**

```python
"""CandidateListProvider — provides weekly dynamic candidate stock pools for backtesting."""

from typing import Dict, List, Optional
from datetime import datetime, timedelta

from trade_alpha.dao import TradeCalendar, StockListHistory, StockList
from trade_alpha.data.service import resolve_and_fetch_historical_date
from trade_alpha.logging import get_logger

logger = get_logger("execution.candidate_list_provider")


class CandidateListProvider:
    """Unified provider for candidate stock lists (fixed or weekly dynamic).

    Fixed mode: when params includes ts_codes, returns that list always.
    Dynamic mode: when ts_codes is absent, builds weekly candidate_map via
    _get_weekly_candidates() and returns the appropriate week's candidates
    per date.
    """

    def __init__(self, params: dict):
        # Fixed-list mode
        self._ts_codes: Optional[List[str]] = params.get("ts_codes")
        # Dynamic weekly mode params
        self._range_n: int = params.get("range_n", 500)
        self._top_n: int = params.get("top_n", 100)
        self._up_n: int = params.get("up_n", 50)
        # Internal state
        self._candidate_map: Dict[str, List[str]] = {}
        self._current_candidates: List[str] = []
        self._last_week_key: Optional[str] = None

    @property
    def all_ts_codes(self) -> List[str]:
        """Union of all candidate codes for data loading."""
        if self._ts_codes:
            return self._ts_codes
        return list({c for codes in self._candidate_map.values() for c in codes})

    @property
    def candidate_map(self) -> Dict[str, List[str]]:
        """Weekly candidate map (populated only in dynamic mode)."""
        return self._candidate_map

    async def initialize(self, start_date: str, end_date: str) -> None:
        """Build candidate_map lazily if in dynamic mode."""
        if not self._ts_codes:
            self._candidate_map = await self._get_weekly_candidates(
                start_date=start_date, end_date=end_date,
                range_n=self._range_n, top_n=self._top_n, up_n=self._up_n,
            )

    def get_candidates_for_date(self, date: str) -> List[str]:
        """Return candidates for given date. Handles week tracking internally."""
        if self._ts_codes:
            return self._ts_codes
        week_key = self._get_week_key(date)
        if week_key != self._last_week_key:
            self._current_candidates = self._candidate_map.get(week_key, [])
            self._last_week_key = week_key
        return self._current_candidates

    async def get_pending_codes(self) -> List[str]:
        """Return non-active candidate codes that need data preparation."""
        codes = self.all_ts_codes
        if not codes:
            return []
        pending = []
        for code in codes:
            stock = await StockList.find_one(StockList.ts_code == code)
            if stock and stock.sync_status != "active":
                pending.append(code)
        if pending:
            logger.info(
                f"{len(pending)} non-active candidates need data preparation"
            )
        return pending

    @staticmethod
    def _get_week_key(date: str, candidate_map: Dict[str, List[str]]) -> Optional[str]:
        """Find the week key (YYYYMMDD) that contains the given date."""
        sorted_keys = sorted(candidate_map.keys())
        for key in reversed(sorted_keys):
            if date >= key:
                return key
        return None

    # ==== 以下方法保持原样不变 ====

    async def _get_trade_calendar(
        self, start_date: str, end_date: str,
    ) -> List:
        return await TradeCalendar.find(
            TradeCalendar.cal_date >= start_date,
            TradeCalendar.cal_date <= end_date,
            TradeCalendar.is_open == 1,
        ).sort(TradeCalendar.cal_date).to_list()

    async def _resolve_date(self, trade_date: str) -> Optional[str]:
        return await resolve_and_fetch_historical_date(trade_date)

    async def _query_top_stocks(
        self, trade_date: str, top_n: int,
    ) -> List:
        return await StockListHistory.find(
            StockListHistory.trade_date == trade_date,
            StockListHistory.total_mv != None,
        ).sort(-StockListHistory.total_mv).limit(top_n).to_list()

    async def _get_prev_trade_date(self, trade_date: str) -> Optional[str]:
        dt = datetime.strptime(trade_date, "%Y%m%d")
        lookback_start = (dt - timedelta(days=14)).strftime("%Y%m%d")
        lookback_end = (dt - timedelta(days=7)).strftime("%Y%m%d")
        days = await TradeCalendar.find(
            TradeCalendar.cal_date >= lookback_start,
            TradeCalendar.cal_date <= lookback_end,
            TradeCalendar.is_open == 1,
        ).sort(-TradeCalendar.cal_date).limit(1).to_list()
        return days[0].cal_date if days else None

    async def _get_weekly_mv_gainers(
        self, trade_date: str, prev_trade_date: str,
        universe_codes: List[str], up_n: int,
    ) -> List[str]:
        if not prev_trade_date:
            return []
        current_records = await StockListHistory.find(
            StockListHistory.trade_date == trade_date,
            StockListHistory.ts_code.is_in(universe_codes),
            StockListHistory.total_mv != None,
        ).to_list()
        current_mv = {r.ts_code: r.total_mv for r in current_records}
        prev_records = await StockListHistory.find(
            StockListHistory.trade_date == prev_trade_date,
            StockListHistory.ts_code.is_in(universe_codes),
            StockListHistory.total_mv != None,
        ).to_list()
        prev_mv = {r.ts_code: r.total_mv for r in prev_records}
        changes = []
        for ts_code in universe_codes:
            cur = current_mv.get(ts_code)
            prv = prev_mv.get(ts_code)
            if cur is not None and prv is not None and prv > 0:
                change = (cur - prv) / prv
                changes.append((change, ts_code))
        changes.sort(key=lambda x: x[0], reverse=True)
        return [ts_code for _, ts_code in changes[:up_n]]

    async def _get_weekly_candidates(
        self, start_date: str, end_date: str,
        range_n: int = 500, top_n: int = 100, up_n: int = 50,
    ) -> Dict[str, List[str]]:
        logger.info(
            f"Computing weekly candidates: {start_date}~{end_date}, "
            f"range_n={range_n}, top_n={top_n}, up_n={up_n}"
        )
        calendar_days = await self._get_trade_calendar(start_date, end_date)
        if not calendar_days:
            logger.warning(f"No trading days found in range {start_date}~{end_date}")
            return {}
        weekly: Dict[str, str] = {}
        for day in calendar_days:
            dt = datetime.strptime(day.cal_date, "%Y%m%d")
            iso = dt.isocalendar()
            week_key = f"{iso.year}W{iso.week:02d}"
            if week_key not in weekly:
                weekly[week_key] = day.cal_date
        result: Dict[str, List[str]] = {}
        prev_base: List[str] = []
        for week_key, first_trade_date in sorted(weekly.items()):
            resolved = await self._resolve_date(first_trade_date)
            if not resolved:
                continue
            universe_records = await self._query_top_stocks(resolved, range_n)
            if not universe_records:
                continue
            universe_codes = [r.ts_code for r in universe_records]
            mv_group = universe_codes[:top_n]
            prev_trade = await self._get_prev_trade_date(resolved)
            if prev_trade:
                up_group = await self._get_weekly_mv_gainers(
                    resolved, prev_trade, universe_codes, up_n,
                )
            else:
                up_group = []
            current_base = list(dict.fromkeys(mv_group + up_group))
            final = list(dict.fromkeys(current_base + prev_base))
            result[resolved] = final
            prev_base = current_base
        logger.info(
            f"Weekly candidates computed: {len(result)} weeks"
        )
        return result
```

- [ ] **Step 2: 运行现有测试确认未破坏**

Run: `cd backend && .venv\Scripts\pytest tests/ -v -m "not integration" -k "candidate"` （如果有相关单元测试的话，没有则跳过）

Expected: No tests yet for new methods, but file parses correctly.

```bash
cd backend && .venv\Scripts\python -c "from trade_alpha.execution.candidate_list_provider import CandidateListProvider; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/candidate_list_provider.py
git commit -m "refactor: restructure CandidateListProvider with unified fixed/dynamic modes"
```

---

### Task 2: 更新 PipelineContext

**Files:**
- Modify: `backend/src/trade_alpha/execution/context.py`

- [ ] **Step 1: 添加导入和必填字段**

在 `from trade_alpha.execution.scoring import ScoreManager` 之后添加：
```python
from trade_alpha.execution.candidate_list_provider import CandidateListProvider
```

修改 `__init__` 签名，添加 `candidate_provider` 为必填参数（放在 strategy_config 和 model_config 之间，或其他已有参数之后、mode_map 之前）：
```python
    def __init__(
        self,
        data_loader: DataLoader,
        score_manager: ScoreManager,
        market_analyzer: MarketRegimeAnalyzer,
        portfolio: PortfolioManager,
        strategy_config: StrategyConfig,
        model_config: ModelConfig,
        candidate_provider: CandidateListProvider,  # <-- 新增必填
        predictor: Any = None,
        account_config: Optional[AccountConfig] = None,
        mode_map: Optional[Dict[str, PhaseMode]] = None,
    ):
```

在 `self.mode_map = mode_map or {}` 之前添加：
```python
        self.candidate_provider = candidate_provider
```

- [ ] **Step 2: 验证文件语法**

```bash
cd backend && .venv\Scripts\python -c "from trade_alpha.execution.context import PipelineContext; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/context.py
git commit -m "refactor: add candidate_provider field to PipelineContext"
```

---

### Task 3: 重构 BacktestPipeline — __init__

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_pipeline.py`

- [ ] **Step 1: 修改 `__init__` 签名，移除 ts_codes/candidate_map，新增 params**

```python
class BacktestPipeline:
    def __init__(
        self,
        params: dict,
        account_config: AccountConfig,
        training_id: PydanticObjectId,
        model_config: ModelConfig,
        strategy_config: Optional[StrategyConfig] = None,
    ):
        self.params = params
        self.mode = params.get("mode", "multi")

        # 同步创建 Provider（无 DB 操作）
        provider = CandidateListProvider(params)
```

移除旧的 `ts_codes` 和 `candidate_map` 参数声明、`self.ts_codes = ...`、`self.candidate_map = ...`、`self._current_candidates`、`self._last_week_key` 以及 `if not self.ts_codes and mode != "live"` 校验。

修改策略初始化，不再传入股票代码：
```python
        if self.mode == "single":
            self.strategy = SingleStockStrategy(
                strategy_config=strategy_config,
            )
        else:
            self.strategy = MultiStockStrategy(
                strategy_config=strategy_config,
            )
```

在 `self.ctx = PipelineContext(` 的调用中添加 `candidate_provider=provider`：
```python
        self.ctx = PipelineContext(
            data_loader=self.data_loader,
            score_manager=self.score_manager,
            market_analyzer=self.market_analyzer,
            portfolio=self.portfolio,
            predictor=self.predictor,
            strategy_config=self.strategy_config,
            model_config=self.model_config,
            account_config=self.account_config,
            candidate_provider=provider,
            mode_map={...},
        )
```

- [ ] **Step 2: 验证语法**

```bash
cd backend && .venv\Scripts\python -c "from trade_alpha.execution.backtest_pipeline import BacktestPipeline; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/backtest_pipeline.py
git commit -m "refactor: update BacktestPipeline.__init__ to accept params dict"
```

---

### Task 4: 重构 BacktestPipeline — run_backtest 和 _prepare_candidate_data

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_pipeline.py`

- [ ] **Step 1: 添加新导入**

在文件顶部添加（已有时忽略）：
```python
import asyncio
from trade_alpha.dao import StockList
from trade_alpha.data.service import active_stock_data
```

- [ ] **Step 2: 重写 `run_backtest` 方法**

```python
    async def run_backtest(
        self,
        task_id: Optional[PydanticObjectId] = None,
    ) -> ExecutionResult:
        start_date = self.params["start_date"]
        end_date = self.params["end_date"]
        name = self.params.get("name")

        result = await self._create_result(start_date, end_date, name)
        await self._ensure_predictor(task_id)

        await TaskService.update_progress(task_id, 0, "正在初始化候选股票列表...")

        # 1. 延迟初始化 Provider
        provider = self.ctx.candidate_provider
        await provider.initialize(start_date, end_date)

        # 2. 数据准备
        await self._prepare_candidate_data(task_id)

        # 3. Baseline tracker
        first_week_codes = provider.get_candidates_for_date(start_date)
        if provider.candidate_map:
            baseline_codes = first_week_codes
        else:
            baseline_codes = provider.all_ts_codes
        baseline_tracker = BaselineTracker(baseline_codes, result.initial_capital)

        # 4. Warmup
        warmup_days = self._compute_warmup_days(self.strategy_config)
        if warmup_days > 0:
            warmup_start = self._find_warmup_start(start_date, warmup_days)
            logger.info(
                f"Warmup {warmup_days} trading days: {warmup_start}+ "
                f"(before {start_date})"
            )
            await self._run_warmup(
                warmup_start, start_date, warmup_days, task_id, baseline_tracker,
            )
            baseline_tracker.reset_daily_rebalanced_anchor()

        await TaskService.update_progress(task_id, 20, "正在加载股票列表...")

        # 5. Daily loop
        daily_values, daily_returns, total_trades, total_fees = await self._run_daily_loop(
            start_date, end_date, result.id, task_id, baseline_tracker,
        )

        # 6. Finalize
        result = await self._finalize_result(
            result, daily_values, daily_returns, total_trades, total_fees, baseline_tracker,
        )
        return result
```

- [ ] **Step 3: 添加 `_prepare_candidate_data` 方法**

在 `run_backtest` 方法之后添加：

```python
    async def _prepare_candidate_data(
        self,
        task_id: Optional[PydanticObjectId],
    ) -> None:
        """Activate non-active candidate stocks for data readiness."""
        provider = self.ctx.candidate_provider
        pending_codes = await provider.get_pending_codes()
        if not pending_codes:
            return

        logger.info(
            f"Preparing data for {len(pending_codes)} non-active "
            f"candidate stocks..."
        )
        total = len(pending_codes)
        for i, code in enumerate(pending_codes):
            await TaskService.update_progress(
                task_id,
                10 + (i / total) * 10,
                f"正在准备数据 {code} ({i+1}/{total})",
            )
            await asyncio.sleep(0.2)
            success = await active_stock_data(code)
            if not success:
                logger.warning(
                    f"Data preparation failed for {code}, "
                    f"may be excluded from scoring"
                )
```

- [ ] **Step 4: 验证语法**

```bash
cd backend && .venv\Scripts\python -c "from trade_alpha.execution.backtest_pipeline import BacktestPipeline; print('OK')"
```
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/src/trade_alpha/execution/backtest_pipeline.py
git commit -m "refactor: refactor run_backtest and add _prepare_candidate_data"
```

---

### Task 5: 更新 _run_warmup 和 _run_daily_loop

**Files:**
- Modify: `backend/src/trade_alpha/execution/backtest_pipeline.py`

将所有 `self.ts_codes` / `self.candidate_map` / `self._current_candidates` / `self._last_week_key` 替换为通过 provider 获取。

- [ ] **Step 1: 重写 `_run_warmup`**

```python
    async def _run_warmup(
        self,
        warmup_start: str,
        actual_start: str,
        warmup_days: int,
        task_id: Optional[PydanticObjectId],
        baseline_tracker: BaselineTracker,
    ) -> None:
        provider = self.ctx.candidate_provider
        all_ts_codes = provider.all_ts_codes
        first_week_codes = provider.get_candidates_for_date(actual_start)

        date = warmup_start
        day_count = 0

        while date < actual_start:
            if self._skip_non_trading_day(date):
                date = _next_date(date)
                continue

            day_data = await self._load_day_data(date, all_ts_codes, self.data_loader)
            if not day_data:
                date = _next_date(date)
                continue
            close_prices = day_data["close"]

            if first_week_codes:
                warmup_close = {k: v for k, v in close_prices.items()
                                if k in first_week_codes}
            else:
                warmup_close = close_prices

            baseline_tracker.track_daily_rebalanced_only(warmup_close)

            stock_map = await self.score_manager.predict_and_score(
                predictor=self.predictor,
                data_loader=self.data_loader,
                date=date,
                close_prices=warmup_close,
                market_analyzer=self.market_analyzer,
            )
            if not stock_map:
                date = _next_date(date)
                continue

            self.market_analyzer.analyze(
                stock_map, daily_rebalanced_values=baseline_tracker.daily_rebalanced_values,
            )
            day_count += 1
            await TaskService.update_progress(
                task_id,
                5 + day_count / warmup_days * 10,
                f"正在预热 {date[:4]}年{date[4:6]}月{date[6:8]}日...",
            )
            date = _next_date(date)
```

- [ ] **Step 2: 重写 `_run_daily_loop`**

```python
    async def _run_daily_loop(
        self, start_date, end_date, backtest_id, task_id, baseline_tracker,
    ):
        provider = self.ctx.candidate_provider
        all_ts_codes = provider.all_ts_codes

        prev_total_value: Optional[float] = None
        pending_orders: List[PendingOrder] = []
        daily_values: List[float] = []
        daily_returns: List[float] = []
        total_trades = 0
        total_fees = 0.0
        cal_days = (datetime.strptime(end_date, "%Y%m%d") - datetime.strptime(start_date, "%Y%m%d")).days
        total_days_est = max(1, int(cal_days * 5 / 7))
        day_count = 0

        await TaskService.update_progress(task_id, 40, "正在执行回测...")
        date = start_date
        while date <= end_date:
            if self._skip_non_trading_day(date):
                date = _next_date(date)
                continue

            day_count += 1
            await self._update_progress(task_id, date, day_count, total_days_est)
            day_data = await self._load_day_data(date, all_ts_codes, self.data_loader)
            if not day_data:
                date = _next_date(date)
                continue
            close_prices = day_data["close"]

            candidates = provider.get_candidates_for_date(date)

            baseline_tracker.track(close_prices)

            if provider.candidate_map:
                candidate_close = {k: v for k, v in close_prices.items()
                                   if k in candidates}
            else:
                candidate_close = close_prices

            baseline_tracker.track_daily_rebalanced_only(candidate_close)

            trades_add, fees_add = await self._settle_orders(
                pending_orders, date, backtest_id, day_data,
            )
            total_trades += trades_add
            total_fees += fees_add

            stock_map = await self.score_manager.predict_and_score(
                predictor=self.predictor,
                data_loader=self.data_loader,
                date=date,
                close_prices=candidate_close,
                market_analyzer=self.market_analyzer,
            )
            if not stock_map:
                date = _next_date(date)
                continue

            self.market_analyzer.analyze(
                stock_map,
                daily_rebalanced_values=baseline_tracker.daily_rebalanced_values,
            )

            market_data = self.market_analyzer.last_result
            atr_values = day_data.get("atr_14", {})

            pending_orders = await self.strategy.make_orders(
                scored_stocks=list(stock_map.values()),
                trade_date=date,
                ctx=self.ctx,
                close_prices=close_prices,
                market_data=market_data,
                atr_values=atr_values,
            )

            # Mark forced-sell orders
            for o in pending_orders:
                if o.order_shares < 0 and o.reason == SELL_REASON_FULL_POSITION:
                    if o.ts_code in stock_map:
                        stock_map[o.ts_code].is_forced_sell = True
                        stock_map[o.ts_code].forced_sell_reason = "full_position"

            if provider.candidate_map and candidates:
                outdated_orders = self._detect_outdated_positions(
                    date, close_prices, candidates,
                )
                pending_orders.extend(outdated_orders)

            day_val, day_ret = await self._save_snapshot(
                date, backtest_id, close_prices, stock_map,
                prev_total_value, baseline_tracker.latest_value,
                baseline_tracker.daily_rebalanced_cum,
            )
            prev_total_value = day_val
            daily_values.append(day_val)
            if day_ret is not None:
                daily_returns.append(day_ret)

            date = _next_date(date)

        return daily_values, daily_returns, total_trades, total_fees
```

- [ ] **Step 3: 更新 `_detect_outdated_positions` 签名**

```python
    def _detect_outdated_positions(
        self,
        date: str,
        close_prices: Dict[str, float],
        candidates: List[str],
    ) -> List[PendingOrder]:
        """Detect positions whose stocks have fallen out of the current candidate pool."""
        sell_orders: List[PendingOrder] = []
        for ts_code, pos in list(self.portfolio.positions.items()):
            if ts_code not in candidates:
                cp = close_prices.get(ts_code, 0.0)
                sell_orders.append(PendingOrder(
                    ts_code=ts_code,
                    stock_name=pos.stock_name or ts_code,
                    order_shares=-pos.shares,
                    order_price=cp,
                    entry_score=pos.entry_score,
                    trade_date=date,
                    settle_date=date,
                    reason=SELL_REASON_CANDIDATE_EXCLUDED,
                    up_prob_3d=pos.entry_3d_prob,
                    up_prob_5d=pos.entry_5d_prob,
                    up_prob_10d=pos.entry_10d_prob,
                    up_prob_20d=pos.entry_20d_prob,
                ))
        if sell_orders:
            logger.info(
                f"{date}: {len(sell_orders)} positions excluded from candidate pool, "
                f"generating sell orders: {[o.ts_code for o in sell_orders]}"
            )
        return sell_orders
```

- [ ] **Step 4: 删除 `_get_week_key` 静态方法**

直接删除 `_get_week_key` 方法（已移入 Provider）。

- [ ] **Step 5: 更新 `_finalize_result` 中 `self.ts_codes` 的引用**

找到 `result.ts_codes = self.ts_codes`，改为：
```python
        result.ts_codes = self.ctx.candidate_provider.all_ts_codes
```

- [ ] **Step 6: 验证语法**

```bash
cd backend && .venv\Scripts\python -c "from trade_alpha.execution.backtest_pipeline import BacktestPipeline; print('OK')"
```
Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add backend/src/trade_alpha/execution/backtest_pipeline.py
git commit -m "refactor: migrate candidate state to Provider in warmup/daily_loop"
```

---

### Task 6: 更新策略类

**Files:**
- Modify: `backend/src/trade_alpha/strategy/single_stock.py`
- Modify: `backend/src/trade_alpha/strategy/multi_stock_strategy.py`

- [ ] **Step 1: 修改 `SingleStockStrategy`**

移除 `target_ts_code` 参数：

```python
class SingleStockStrategy(BaseStrategy):
    def __init__(
        self,
        strategy_config: StrategyConfig,
    ):
        super().__init__(
            max_positions=1,
            max_position_pct=0.95,
            min_order_value=strategy_config.min_order_value,
            stop_loss_pct=strategy_config.stop_loss_pct,
            max_hold_days=strategy_config.max_hold_days,
            buy_threshold=strategy_config.buy_threshold,
            sell_threshold=strategy_config.sell_threshold,
        )
```

在 `make_orders` 方法中，将 `self.target_ts_code` 替换为从 ctx 获取：
```python
        provider = ctx.candidate_provider
        all_codes = provider.all_ts_codes
        target_ts_code = all_codes[0] if all_codes else ""
        target_stock = next((s for s in scored_stocks if s.ts_code == target_ts_code), None)
```

- [ ] **Step 2: 修改 `MultiStockStrategy`**

移除 `ts_codes` 参数：

```python
class MultiStockStrategy(BaseStrategy):
    def __init__(
        self,
        strategy_config: StrategyConfig,
    ):
        super().__init__(
            buy_threshold=strategy_config.buy_threshold,
            sell_threshold=strategy_config.sell_threshold,
            min_order_value=strategy_config.min_order_value,
            stop_loss_pct=strategy_config.stop_loss_pct,
            min_hold_days=strategy_config.min_hold_days,
            max_hold_days=strategy_config.max_hold_days,
            max_positions=strategy_config.max_positions,
            max_position_pct=strategy_config.max_position_pct,
        )
        self.strategy_config = strategy_config
        self._full_position_consecutive_days = 0
        self.full_position_score_window = strategy_config.full_position_score_window
```

移除 `self.ts_codes = ts_codes or []`。

在 `make_orders` 中，将 `if self.ts_codes:` 过滤替换为：
```python
        provider = ctx.candidate_provider
        scored_stocks = [s for s in scored_stocks if s.ts_code in provider.all_ts_codes]
```

- [ ] **Step 3: 验证语法**

```bash
cd backend && .venv\Scripts\python -c "from trade_alpha.strategy.single_stock import SingleStockStrategy; from trade_alpha.strategy.multi_stock_strategy import MultiStockStrategy; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/strategy/single_stock.py backend/src/trade_alpha/strategy/multi_stock_strategy.py
git commit -m "refactor: remove ts_codes from strategy constructors, use ctx provider"
```

---

### Task 7: 简化 BacktestRunner

**Files:**
- Modify: `backend/src/trade_alpha/task/backtest_runner.py`

- [ ] **Step 1: 重写 `execute` 方法**

```python
"""Backtest runner for subprocess execution."""

import asyncio

from beanie import PydanticObjectId

from trade_alpha.task.runner import BaseRunner
from trade_alpha.task.service import TaskService
from trade_alpha.models import training as training_module
from trade_alpha.execution.backtest_pipeline import BacktestPipeline
from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.strategy.service import get_strategy_by_id
from trade_alpha.logging import get_logger

logger = get_logger("task.backtest_runner")


class BacktestRunner(BaseRunner):
    """Runner for backtest tasks."""

    async def execute(self) -> None:
        """Execute backtest."""
        task = await TaskService.get_task(self.task_id)
        if not task:
            logger.error(f"Task {self.task_id} not found")
            return

        params = task.params
        logger.info(f"Starting backtest task {self.task_id}")

        try:
            account_config = await AccountConfig.get(PydanticObjectId(params["account_config_id"]))
            if not account_config:
                await TaskService.fail_task(
                    self.task_id, f"Account config not found: {params['account_config_id']}"
                )
                return

            training_record = await training_module.get_training_by_id(
                PydanticObjectId(params["training_id"])
            )
            if not training_record:
                await TaskService.fail_task(
                    self.task_id, f"Training not found: {params['training_id']}"
                )
                return

            model_config = training_record.model_snapshot
            if not model_config:
                await TaskService.fail_task(
                    self.task_id,
                    f"Training result has no model snapshot: {params['training_id']}",
                )
                return

            strategy_config = None
            if params.get("strategy_config_id"):
                strategy_config = await get_strategy_by_id(
                    PydanticObjectId(params["strategy_config_id"])
                )
                if not strategy_config:
                    await TaskService.fail_task(
                        self.task_id,
                        f"Strategy config not found: {params['strategy_config_id']}",
                    )
                    return

            pipeline = BacktestPipeline(
                params=params,
                account_config=account_config,
                training_id=PydanticObjectId(params["training_id"]),
                model_config=model_config,
                strategy_config=strategy_config,
            )

            result = await pipeline.run_backtest(
                task_id=self.task_id,
            )

            await TaskService.complete_task(self.task_id, str(result.id))
            logger.info(f"Backtest task {self.task_id} completed: result_id={result.id}")

        except Exception as e:
            logger.error(f"Backtest task {self.task_id} failed: {e}")
            await TaskService.fail_task(self.task_id, str(e))
```

注意：移除 `CandidateListProvider`, `StockList`, `active_stock_data`, `data.service` 的导入（`from trade_alpha.data.service import active_stock_data` 和 `from trade_alpha.dao import StockList`）。

- [ ] **Step 2: 运行现有单元测试检查是否报错**

```bash
cd backend && .venv\Scripts\pytest tests/trade_alpha/unit/execution/test_backtest_warmup.py -v
```
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/task/backtest_runner.py
git commit -m "refactor: simplify BacktestRunner, delegate candidate logic to pipeline"
```

---

### Task 8: 更新集成测试

**Files:**
- Modify: `backend/tests/trade_alpha/integration/test_61_backtest_lstm.py`

- [ ] **Step 1: 修改 `test_run_backtest` 方法**

将 pipeline 构造改为通过 params 传入：

```python
    @pytest.mark.asyncio
    async def test_run_backtest(self):
        """Run LSTM backtest once and store result for subsequent tests."""
        if not all([self.account_config, self.strategy_config, self.training, self.model_config]):
            pytest.skip("Missing dependencies")

        if TestBacktestLSTM._backtest_result is not None:
            pytest.skip("Backtest already executed")

        await delete_execution_by_name(self.backtest_name)

        pipeline = BacktestPipeline(
            params={
                "mode": "single",
                "ts_codes": [self.ts_code],
                "start_date": "20240101",
                "end_date": "20240131",
                "name": self.backtest_name,
            },
            account_config=self.account_config,
            training_id=self.training.id,
            model_config=self.model_config,
            strategy_config=self.strategy_config,
        )

        result = await pipeline.run_backtest()
        # ... 后续不变
```

- [ ] **Step 2: 运行集成测试检查**

```bash
cd backend && .venv\Scripts\pytest tests/trade_alpha/integration/test_61_backtest_lstm.py -v
```
Expected: PASS（可能需要先运行 test_53 创建训练数据）

- [ ] **Step 3: Commit**

```bash
git add backend/tests/trade_alpha/integration/test_61_backtest_lstm.py
git commit -m "test: update backtest integration test for new Pipeline interface"
```

---

### Task 9: 清理 API 路由中的未使用导入

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/backtest.py`

- [ ] **Step 1: 移除未使用的 `BacktestPipeline` 导入**

如果 `BacktestPipeline` 在 `backtest.py` 中未直接使用（仅在子进程中间接使用），移除该导入：
```python
# 删除这一行:
# from trade_alpha.execution.backtest_pipeline import BacktestPipeline
```

同时检查是否还有其他未使用的导入需要清理。

- [ ] **Step 2: 验证语法**

```bash
cd backend && .venv\Scripts\python -c "from trade_alpha.api.routers.backtest import router; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/api/routers/backtest.py
git commit -m "cleanup: remove unused import in backtest API router"
```

---

### Task 10: 完整集成测试

- [ ] **Step 1: 运行全量集成测试**

```bash
cd backend && .venv\Scripts\pytest tests/trade_alpha/integration/ -v
```
Expected: 全部 PASS

- [ ] **Step 2: 运行单元测试**

```bash
cd backend && .venv\Scripts\pytest tests/ -v -m "not integration"
```
Expected: 全部 PASS

- [ ] **Step 3: 最终提交**

```bash
git add -A
git commit -m "refactor: unify candidate pool management under CandidateListProvider"
```
