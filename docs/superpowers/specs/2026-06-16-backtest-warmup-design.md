# Backtest Warmup Phase Design

## Background

回测过程中，`ScoreManager` 持有多个跨日缓冲区（EWMA 平滑、排名历史、相关系数等），这些缓冲区在回测初期处于"冷启动"状态。冷启动期间窗口参数（如 `market_smooth_window`）的差异会导致初始仓位和持仓组合出现分叉，进而影响全年回测结果的可比性和稳定性。

## Goals

- 在正式回测开始前，增加一段 warmup 预热期
- Warmup 期间正常跑 `predict_and_score()` 和 `compute_market_regime()`，填充所有缓冲区
- Warmup 期间**不产生交易、不存储快照、不影响持仓状态**
- Warmup 天数自动从策略配置计算，不给用户增加配置负担

## Warmup Days Calculation

### 需要覆盖的缓冲区

| 缓冲区 | 对应配置字段 | 典型值 |
|:-------|:------------|:------|
| `_score_buffer` (个股score EWMA) | `ranking_smooth_window` | 8 |
| `_ranking_median_buffer` (市场median EWMA) | `market_smooth_window` | 5 |
| `_retention_rate_buffer` (留存率 EWMA) | `market_smooth_window` | 5 |
| `_correlation_buffer` (相关性 EWMA) | `market_smooth_window` | 5 |
| `_rank_history` (排名历史) | `retention_days`, `correlation_window` | 5 |
| `_ranking_median_buffer` 缓冲裁剪 | `market_smooth_window × 2` | 10 |

### 不需要覆盖的参数

| 参数 | 原因 |
|:----|:-----|
| `full_position_score_window` (20) | Warmup 无持仓，不涉及满仓卖出 |
| `trend_bonus_window` (15) | 通过 `peek_history_data()` 从 DB 加载历史价格，不依赖缓冲区 |
| `momentum_window` (12) | 同上，DB 加载 |
| `explosion_window` (5) | 同上，DB 加载 |

### 计算公式

```python
def _compute_warmup_days(strategy_config) -> int:
    windows = [
        getattr(strategy_config, 'ranking_smooth_window', 5),
        getattr(strategy_config, 'market_smooth_window', 5),
        getattr(strategy_config, 'retention_days', 5),
        getattr(strategy_config, 'correlation_window', 5),
    ]
    return max(windows) + 10
```

默认值为 `max(8, 5, 5, 5) + 10 = 18` 个交易日。

### Warmup Start Date

直接用日历推，乘以 3 倍保证够覆盖周末和假期：

```python
def _calc_warmup_start(start_date: str, warmup_days: int) -> str:
    dt = datetime.strptime(start_date, "%Y%m%d")
    dt -= timedelta(days=warmup_days * 3)
    return dt.strftime("%Y%m%d")
```

Warmup 循环里的 `_skip_non_trading_day` 会自然跳过非交易日，`_load_day_data` 没有数据也会跳过，所以最终实际处理的交易日 >= warmup_days。

## Pipeline Changes (backtest_pipeline.py)

```python
class BacktestPipeline:

    @staticmethod
    def _compute_warmup_days(strategy_config: Optional[StrategyConfig]) -> int:
        if strategy_config is None:
            return 0
        windows = [
            getattr(strategy_config, 'ranking_smooth_window', 5),
            getattr(strategy_config, 'market_smooth_window', 5),
            getattr(strategy_config, 'retention_days', 5),
            getattr(strategy_config, 'correlation_window', 5),
        ]
        return max(windows) + 10

    def _find_warmup_start(
        self,
        start_date: str,
        warmup_days: int,
    ) -> str:
        dt = datetime.strptime(start_date, "%Y%m%d")
        dt -= timedelta(days=warmup_days * 3)
        return dt.strftime("%Y%m%d")

    async def _run_warmup(self, warmup_start: str, actual_start: str,
                          warmup_days: int, task_id: Optional[PydanticObjectId]) -> None:
        """Run warmup phase: fill ScoreManager buffers without trading."""
        date = warmup_start
        day_count = 0
        while date < actual_start:
            if self._skip_non_trading_day(date):
                date = _next_date(date)
                continue

            day_data = await self._load_day_data(date, self.ts_codes, self.data_loader)
            if not day_data:
                date = _next_date(date)
                continue
            close_prices = day_data["close"]

            stock_map = await self.score_manager.predict_and_score(
                predictor=self.predictor,
                data_loader=self.data_loader,
                date=date,
                close_prices=close_prices,
                start_date=date,
                vol_prices=day_data.get("vol", {}),
            )
            if not stock_map:
                date = _next_date(date)
                continue

            self.score_manager.compute_market_regime(stock_map)
            day_count += 1
            await TaskService.update_progress(
                task_id,
                5 + day_count / warmup_days * 10,
                f"正在预热 {date}...",
            )
            date = _next_date(date)

    async def run_backtest(self, ...) -> ExecutionResult:
        result = await self._create_result(start_date, end_date, name)
        await self._ensure_predictor(task_id)

        # Warmup phase (before trading starts)
        warmup_days = self._compute_warmup_days(self.strategy_config)
        if warmup_days > 0:
            warmup_start = self._find_warmup_start(start_date, warmup_days)
            logger.info(
                f"Warmup {warmup_days} trading days: {warmup_start}+ "
                f"(before {start_date})"
            )
            await self._run_warmup(warmup_start, start_date, warmup_days, task_id)

        # Original main loop (unchanged)
        await TaskService.update_progress(task_id, 20, "正在加载股票列表...")
        baseline_tracker = BaselineTracker(self.ts_codes, result.initial_capital)
        daily_values, daily_returns, total_trades, total_fees = await self._run_daily_loop(
            start_date, end_date, result.id, task_id, baseline_tracker,
        )
        result = await self._finalize_result(...)
        return result
```

## Key Design Decisions

1. **纯预热，不产生副作用** — Warmup 循环不调用 `_settle_orders`、`make_orders`、`_save_snapshot`、`BaselineTracker.track`。PortfolioManager 的持仓状态和 cash 保持不变，没有执行轨迹写入 DB。

2. **不修改 ScoreManager** — `predict_and_score()` 和 `compute_market_regime()` 的内部副作用（填充缓冲区）就是 warmup 想要的效果，直接复用现有逻辑。

3. **重新相同预测器** — Warmup 使用与主循环相同的 `self.predictor`（已训练完毕），不需要重新训练模型。

4. **Warmup 期间的 `start_date` 参数** — 传给 `predict_and_score()` 的 `start_date` 设为 warmup 当天日期，保证日志中不出现"First day"的误报。

5. **自动适应配置变更** — 如果后续增加新的窗口参数，只需在 `_compute_warmup_days` 的列表中加上即可。

## Test Plan

- 验证 `_compute_warmup_days` 计算逻辑：输入不同的 config，输出正确的天数
- 验证 warmup 期间不产生 trade、snapshot、portfolio 变化
- 对比有/无 warmup 场景下 ScoreManager 缓冲区的初始状态
- 集成测试中增加 warmup 场景验证（可选）
