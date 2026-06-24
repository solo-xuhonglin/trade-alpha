# 选股管道串行重构 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or executing-plans to implement this plan task-by-task.

**Goal:** 候选池构建从并行合并改为串行管道。3 个 Step 统一接口 `(date, universe) → List[str]`，内部状态不暴露。

**范围:** 仅改 `candidate_list_provider.py`。

---

### Task 1: 新增 3 个 Step 方法

在 `_get_candidates` 之前新增：

```python
    async def _step_market_cap(
        self, date: str, universe: List[str],
    ) -> List[str]:
        """Select top_n stocks by market cap."""
        return universe[:self._top_n]


    async def _step_momentum(
        self, date: str, universe: List[str],
    ) -> List[str]:
        """Select momentum_n stocks by weighted composite score from universe."""
        if self._momentum_n <= 0 or not universe:
            return []
        # ... 复用 _get_momentum_stocks 的主体计算逻辑 ...
        # 使用 self._prev_composite 替代参数传入
        # 最后更新 self._prev_composite = cur_composite
        # 返回: [ts_code, ...] 仅选中列表


    async def _step_ma_trend(
        self, date: str, universe: List[str],
    ) -> List[str]:
        """Filter out stocks where MA5/MA60 < threshold."""
        if not self._use_ma_trend_filter or not universe:
            return universe
        records = await StockDaily.find(
            StockDaily.trade_date == date,
            In(StockDaily.ts_code, universe),
            StockDaily.ma_5 != None,
            StockDaily.ma_60 != None,
        ).to_list()
        valid = set()
        for r in records:
            if r.ma_5 and r.ma_60 and r.ma_60 > 0:
                if r.ma_5 / r.ma_60 >= self._ma_trend_ratio_threshold:
                    valid.add(r.ts_code)
            else:
                valid.add(r.ts_code)
        return [ts for ts in universe if ts in valid]
```

---

### Task 2: 重写 `_get_candidates` 为串行管道

删除原有 `mv_group`、`momentum_universe`、`_get_momentum_stocks` 调用，替换为：

```python
            universe_codes = [r.ts_code for r in universe_records]

            # ── Serial pipeline ──
            # Step 1: market cap selection
            selected_mc = await self._step_market_cap(resolved, universe_codes)
            # Step 2: momentum from stocks not selected by market cap
            remaining = [c for c in universe_codes if c not in selected_mc]
            selected_mt = await self._step_momentum(resolved, remaining)
            # Step 3: filter downtrend from combined selections
            current_base = await self._step_ma_trend(resolved, selected_mc + selected_mt)

            final = list(dict.fromkeys(current_base + prev_base))
            result[resolved] = final
            # ── End pipeline ──

            for ts in selected_mc:
                self._stock_groups[ts] = "base"
            for ts in selected_mt:
                self._stock_groups[ts] = "momentum"
            prev_base = current_base
```

在 `__init__` 中新增 `self._prev_composite: Optional[Dict[str, float]] = None`。

### Task 3: 删除旧方法 + 验证

删除 `_get_momentum_stocks`（逻辑已迁移到 `_step_momentum`）。

运行：
```bash
pytest tests/trade_alpha/integration/test_30_candidate_lifecycle.py -v --tb=short
```
预期通过。
