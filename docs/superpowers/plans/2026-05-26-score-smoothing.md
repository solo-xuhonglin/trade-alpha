# 预测信号平滑 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在多股票 pipeline 中引入分数 EWMA 平滑和排名回写，降低排名波动导致的频繁交易。

**Architecture:** 在 `ExecutionPipeline` 中新增两个私有方法 `_smooth_scores()` 和 `_record_ranks()`，在 `run_backtest()` 主循环的 Predict 步骤后、`make_decisions` 前依次调用。平滑用 `Dict[ts_code, List[float]]` 跨日缓冲区做 EWMA(span=3)，排名在排序后回写到 `pred_results` 并随快照持久化。

**Tech Stack:** Python 3.14+, FastAPI, Beanie (MongoDB)

---

### Task 1: 在 pipeline 中添加信号平滑和排名记录

**Files:**
- Modify: `backend/src/trade_alpha/execution/pipeline.py`

- [ ] **Step 1: 在 `__init__` 中新增分数缓冲区**

在 `self.pending_orders` 后面（现有代码约 94 行）添加：

```python
        self._score_buffer: Dict[str, List[float]] = {}  # ts_code -> EWMA history
```

- [ ] **Step 2: 添加 `_smooth_scores()` 方法**

在 `run_backtest()` 方法之前（或 `_next_date()` 等辅助方法附近）添加：

```python
    def _smooth_scores(self, pred_results: Dict[str, Dict]) -> None:
        """Apply EWMA smoothing to scores in-place on pred_results.

        Maintains a cross-day buffer per stock. When buffer has < 3 values,
        uses raw score (no smoothing yet).
        """
        alpha = 0.5  # = 2 / (span=3 + 1)
        for ts_code, r in pred_results.items():
            raw = r["score"]
            buf = self._score_buffer.setdefault(ts_code, [])
            buf.append(raw)
            if len(buf) > 3:
                buf.pop(0)
            if len(buf) >= 3:
                smoothed = buf[0]
                for v in buf[1:]:
                    smoothed = alpha * v + (1 - alpha) * smoothed
                r["score"] = smoothed
```

- [ ] **Step 3: 添加 `_record_ranks()` 方法**

紧挨 `_smooth_scores` 之后添加：

```python
    def _record_ranks(self, scored: List[ScoredStock], pred_results: Dict[str, Dict]) -> None:
        """Sort scored stocks by score and write rank back into pred_results.

        Rank is persisted via daily_snapshot for later analysis.
        Single-stock mode: rank stays 1, harmless.
        """
        scored_sorted = sorted(scored, key=lambda s: s.score, reverse=True)
        for rank, stock in enumerate(scored_sorted, start=1):
            pred_results[stock.ts_code]["rank"] = rank
```

- [ ] **Step 4: 在 `run_backtest()` 主循环中插入调用**

找到现有代码（约 303-319 行）：
```python
            pred_results = {}
            for ts_code, probs in pred_results_raw.items():
                close_price = close_prices.get(ts_code, 0)
                pred_results[ts_code] = compute_scores(probs, close_price, self._config.classification_horizons)
            if not pred_results:
                logger.debug(f"No predictions for {date}, skipping")
                date = _next_date(date)
                continue

            scored = [
                ScoredStock(
```

改为：

```python
            pred_results = {}
            for ts_code, probs in pred_results_raw.items():
                close_price = close_prices.get(ts_code, 0)
                pred_results[ts_code] = compute_scores(probs, close_price, self._config.classification_horizons)
            if not pred_results:
                logger.debug(f"No predictions for {date}, skipping")
                date = _next_date(date)
                continue

            # Smooth scores with EWMA to reduce ranking volatility
            self._smooth_scores(pred_results)

            scored = [
                ScoredStock(
```

然后在 `scored` 列表构建完成之后、单股票过滤之前（约 319-322 行），当前为：

```python
                for ts_code, r in pred_results.items()
            ]

            # Single-stock mode: filter to only the target stock
```

改为：

```python
                for ts_code, r in pred_results.items()
            ]

            # Record ranks after sorting by smoothed score
            self._record_ranks(scored, pred_results)

            # Single-stock mode: filter to only the target stock
```

- [ ] **Step 5: 运行单元测试验证**

```bash
cd d:\projects\trade-alpha\backend
pytest tests/trade_alpha/unit/ -v
```

Expected: 63 passed

- [ ] **Step 6: 提交**

```bash
git add backend/src/trade_alpha/execution/pipeline.py
git commit -m "feat: add score smoothing (EWMA span=3) and rank recording to execution pipeline"
```
