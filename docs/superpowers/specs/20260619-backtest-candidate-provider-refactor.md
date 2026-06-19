# Backtest CandidateListProvider 重构设计

## 概述

重构回测系统的候选池管理，消除 `BacktestPipeline` 中分散的 `ts_codes`/`candidate_map`/`_current_candidates`/`_last_week_key` 状态，统一由 `CandidateListProvider` 管理候选股票的完整生命周期。

## 要解决的问题

1. **责任分散**：候选池相关逻辑散落在 `BacktestPipeline.__init__`、`run_backtest`、`_run_warmup`、`_run_daily_loop`、`_detect_outdated_positions` 五个位置，且需要分支判断两种模式（固定列表 vs 动态周候选）
2. **Runner 职责过重**：`BacktestRunner.execute` 中包含了候选池创建、数据准备等逻辑，与 runner 的定位不符
3. **策略耦合**：`SingleStockStrategy` 和 `MultiStockStrategy` 在初始化时接收股票代码，导致无法延迟确定候选池

## 架构变化

### Before

```
BacktestRunner.execute()
    ├── CandidateListProvider.get_weekly_candidates()
    ├── union_codes = set(candidate_map)
    ├── active_stock_data(pending_codes)
    └── BacktestPipeline(ts_codes, candidate_map)
            ├── self.ts_codes, self.candidate_map
            ├── self._current_candidates, self._last_week_key
            ├── SingleStockStrategy(target_ts_code=...)
            ├── MultiStockStrategy(ts_codes=...)
            └── run_backtest()
                    ├── self.ctx (无 candidate_provider)
                    ├── _run_warmup() → self.ts_codes, self.candidate_map
                    └── _run_daily_loop() → self.ts_codes, self.candidate_map,
                                             self._current_candidates,
                                             self._last_week_key
```

### After

```
BacktestRunner.execute()
    └── BacktestPipeline(params)
            ├── CandidateListProvider(params) → 同步创建，无 DB 调用
            └── run_backtest()
                    ├── provider.initialize(start_date, end_date)
                    ├── _prepare_candidate_data() → provider.get_pending_codes()
                    ├── ctx.candidate_provider = provider
                    ├── _run_warmup() → provider.get_candidates_for_date()
                    └── _run_daily_loop() → provider.get_candidates_for_date()
```

## 详细设计

### 1. CandidateListProvider

```python
class CandidateListProvider:
    def __init__(self, params: dict):
        # 从 params 提取
        self._ts_codes: Optional[List[str]] = params.get("ts_codes")
        self._range_n: int = params.get("range_n", 500)
        self._top_n: int = params.get("top_n", 100)
        self._up_n: int = params.get("up_n", 50)
        # 内部状态
        self._candidate_map: Dict[str, List[str]] = {}
        self._current_candidates: List[str] = []
        self._last_week_key: Optional[str] = None

    @property
    def all_ts_codes(self) -> List[str]:
        """所有候选代码的并集，用于数据加载。"""
        if self._ts_codes:
            return self._ts_codes
        return list({c for codes in self._candidate_map.values() for c in codes})

    @property
    def candidate_map(self) -> Dict[str, List[str]]:
        """周候选映射，动态模式有值，固定模式为空。"""
        return self._candidate_map

    async def initialize(self, start_date: str, end_date: str) -> None:
        """延迟构建 candidate_map（仅动态模式）。"""
        if not self._ts_codes:
            self._candidate_map = await self._get_weekly_candidates(
                start_date=start_date, end_date=end_date,
                range_n=self._range_n, top_n=self._top_n, up_n=self._up_n,
            )

    def get_candidates_for_date(self, date: str) -> List[str]:
        """获取指定日期的候选列表。内部管理周切换。"""
        if self._ts_codes:
            return self._ts_codes
        week_key = self._get_week_key(date)
        if week_key != self._last_week_key:
            self._current_candidates = self._candidate_map.get(week_key, [])
            self._last_week_key = week_key
        return self._current_candidates

    async def get_pending_codes(self) -> List[str]:
        """返回需要数据准备的非活跃候选代码。"""
        codes = self.all_ts_codes
        if not codes:
            return []
        pending = []
        for code in codes:
            stock = await StockList.find_one(StockList.ts_code == code)
            if stock and stock.sync_status != "active":
                pending.append(code)
        return pending

    # 保留现有私有方法不变
    # _get_trade_calendar(), _resolve_date(), _query_top_stocks()
    # _get_prev_trade_date(), _get_weekly_mv_gainers()
    # _get_weekly_candidates(), _get_week_key()
```

### 2. PipelineContext

```python
class PipelineContext:
    def __init__(
        self,
        data_loader: DataLoader,
        score_manager: ScoreManager,
        market_analyzer: MarketRegimeAnalyzer,
        portfolio: PortfolioManager,
        strategy_config: StrategyConfig,
        model_config: ModelConfig,
        candidate_provider: CandidateListProvider,  # 新增必填参数
        predictor: Any = None,
        account_config: Optional[AccountConfig] = None,
        mode_map: Optional[Dict[str, PhaseMode]] = None,
    ):
        # ... 已有字段 ...
        self.candidate_provider = candidate_provider
```

### 3. BacktestPipeline

```python
class BacktestPipeline:
    def __init__(
        self,
        params: dict,                              # 新增：完整任务参数
        account_config: AccountConfig,
        training_id: PydanticObjectId,
        model_config: ModelConfig,
        strategy_config: Optional[StrategyConfig] = None,
    ):
        self.params = params
        self.mode = params.get("mode", "multi")
        # 移除：ts_codes, candidate_map, _current_candidates, _last_week_key

        # Provider 同步创建
        provider = CandidateListProvider(params)

        # 策略不再传入股票代码
        if self.mode == "single":
            self.strategy = SingleStockStrategy(strategy_config=strategy_config)
        else:
            self.strategy = MultiStockStrategy(strategy_config=strategy_config)

        self.ctx = PipelineContext(
            ...
            candidate_provider=provider,
        )

    async def run_backtest(self, task_id=None):
        """执行回测。"""
        start_date = self.params["start_date"]
        end_date = self.params["end_date"]

        result = await self._create_result(...)
        await self._ensure_predictor(task_id)
        await TaskService.update_progress(task_id, 0, "正在初始化候选股票列表...")

        # 1. 延迟初始化 Provider
        await self.ctx.candidate_provider.initialize(start_date, end_date)

        # 2. 数据准备（非活跃股票激活）
        await self._prepare_candidate_data(task_id)

        # 3. Baseline & Warmup
        provider = self.ctx.candidate_provider
        first_week_codes = provider.get_candidates_for_date(start_date)
        baseline_tracker = BaselineTracker(
            first_week_codes if provider.candidate_map else provider.all_ts_codes,
            result.initial_capital,
        )
        warmup_days = self._compute_warmup_days(self.strategy_config)
        if warmup_days > 0:
            warmup_start = self._find_warmup_start(start_date, warmup_days)
            await self._run_warmup(warmup_start, start_date, warmup_days, task_id, baseline_tracker)
            baseline_tracker.reset_daily_rebalanced_anchor()

        # 4. 日常循环
        daily_values, daily_returns, total_trades, total_fees = await self._run_daily_loop(
            start_date, end_date, result.id, task_id, baseline_tracker,
        )

        # 5. 完成
        result = await self._finalize_result(
            result, daily_values, daily_returns, total_trades, total_fees, baseline_tracker,
        )
        return result

    async def _prepare_candidate_data(self, task_id):
        """激活非活跃候选股票数据。"""
        provider = self.ctx.candidate_provider
        pending_codes = await provider.get_pending_codes()
        if not pending_codes:
            return
        total = len(pending_codes)
        for i, code in enumerate(pending_codes):
            await TaskService.update_progress(
                task_id, 10 + (i / total) * 10,
                f"正在准备数据 {code} ({i+1}/{total})",
            )
            await asyncio.sleep(0.2)
            success = await active_stock_data(code)
            if not success:
                logger.warning(f"Data preparation failed for {code}")

    # _run_warmup / _run_daily_loop 中：
    #   self.ts_codes → provider.all_ts_codes
    #   self.candidate_map → provider.candidate_map
    #   self._current_candidates / self._last_week_key → provider.get_candidates_for_date()
    #   _get_week_key(date, self.candidate_map) → provider._get_week_key(date)（移入 provider）
    # _detect_outdated_positions(date, close_prices) → candidates 由调用方传入
    # 删除：_get_week_key 静态方法
```

### 4. 策略类变更

`SingleStockStrategy`：移除 `target_ts_code`，`make_orders` 中通过 `ctx.candidate_provider.all_ts_codes[0]` 获取。

`MultiStockStrategy`：移除 `ts_codes`，`make_orders` 中通过 `ctx.candidate_provider.all_ts_codes` 过滤。

### 5. BacktestRunner

Runner 不再创建 Provider、不再调用 `get_weekly_candidates`、不再激活股票数据。只负责获取配置 → 创建 Pipeline → 调用 `run_backtest`。

### 6. 集成测试

构造 `params` dict 传入 `BacktestPipeline`，移除 `ts_codes` 和 `candidate_map` 参数。

## 受影响文件

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `candidate_list_provider.py` | 重构 | 合并两种模式，新增 `initialize()` / `get_candidates_for_date()` / `get_pending_codes()` |
| `context.py` | 修改 | 新增必填字段 `candidate_provider` |
| `backtest_pipeline.py` | 重构 | 移除 ts_codes/candidate_map/周状态，新增 params 参数，提取 _prepare_candidate_data |
| `backtest_runner.py` | 简化 | 移除候选池相关逻辑 |
| `single_stock.py` | 修改 | 移除 target_ts_code |
| `multi_stock_strategy.py` | 修改 | 移除 ts_codes |
| `test_61_backtest_lstm.py` | 修改 | 适配新构造方式 |

## 不变的部分

- `CandidateListProvider` 内部 DB 查询方法（_get_trade_calendar, _query_top_stocks 等）
- `PipelineContext` 其他已有字段
- API 路由层（`backtest.py`，task params 结构不变）
- 回测计算结果和存储格式

## 兼容性

- 通过 `params` 传入，原有 task 的 `params` dict 字段不变
- 测试中 mode="single"+ts_codes 固定列表模式保持行为一致
- 所有已有 task 兼容，无需数据迁移
