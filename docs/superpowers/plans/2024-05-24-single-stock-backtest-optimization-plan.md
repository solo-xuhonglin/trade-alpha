# 单只股票LSTM回测性能优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化单只股票LSTM回测速度，从半小时降至几分钟

**Architecture:** 修改单只股票模式只加载1只股票的数据，而不是200只

**Tech Stack:** Python, Beanie (MongoDB)

---

## File Structure

- `backend/src/trade_alpha/execution/pipeline.py`: Modify - 单只股票模式优化

---

## Task 1: 优化单只股票模式的股票列表加载

**Files:**
- Modify: `backend/src/trade_alpha/execution/pipeline.py:131-149`

- [ ] **Step 1: 读取当前代码**

```python
limit = 200 if self.single_stock_ts_code else 3000

from beanie.odm.operators.find.comparison import NotIn

await TaskService.update_progress(task_id, 20, "正在加载股票列表...")
all_stocks = await StockList.find(
    StockList.sync_status == "active",
    NotIn(StockList.ts_code, TEST_EXCLUDED_TS_CODES)
).sort(-StockList.total_mv).limit(limit).to_list()

# Ensure target stock is included in single-stock mode
if self.single_stock_ts_code:
    target_stock = await StockList.find_one(StockList.ts_code == self.single_stock_ts_code)
    if target_stock and target_stock not in all_stocks:
        all_stocks.append(target_stock)

universe = {s.ts_code: s.name for s in all_stocks}
ts_codes = list(universe.keys())
```

- [ ] **Step 2: 修改为单只股票模式只加载目标股票**

```python
if self.single_stock_ts_code:
    limit = 1
    await TaskService.update_progress(task_id, 20, "正在加载股票列表...")
    target_stock = await StockList.find_one(StockList.ts_code == self.single_stock_ts_code)
    if not target_stock:
        raise ValueError(f"Target stock {self.single_stock_ts_code} not found")
    all_stocks = [target_stock]
else:
    limit = 3000
    from beanie.odm.operators.find.comparison import NotIn
    await TaskService.update_progress(task_id, 20, "正在加载股票列表...")
    all_stocks = await StockList.find(
        StockList.sync_status == "active",
        NotIn(StockList.ts_code, TEST_EXCLUDED_TS_CODES)
    ).sort(-StockList.total_mv).limit(limit).to_list()

universe = {s.ts_code: s.name for s in all_stocks}
ts_codes = list(universe.keys())
```

- [ ] **Step 3: 验证语法**

```bash
cd d:/projects/trade-alpha/backend
python -c "from trade_alpha.execution.pipeline import ExecutionPipeline; print('Import OK')"
```

- [ ] **Step 4: 提交**

```bash
git add backend/src/trade_alpha/execution/pipeline.py
git commit -m "perf: optimize single stock backtest by loading only 1 stock"
```

---

## Task 2: 运行测试验证

**Files:**
- Test: 现有相关测试

- [ ] **Step 1: 运行LSTM相关测试**

```bash
cd backend
python -m pytest tests/trade_alpha/unit/predict/test_lstm.py -v
```

- [ ] **Step 2: 验证测试通过**

Expected: All tests pass

- [ ] **Step 3: 提交（如果无变更，提交空提交）**

```bash
git commit --allow-empty -m "test: verify single stock backtest optimization"
```

---

## Self-Review

### 1. Spec Coverage

✅ 单只股票模式只加载1只股票 - Task 1

### 2. Placeholder Scan

✅ No TBD/TODO
✅ Complete code blocks
✅ Exact file paths

### 3. Type Consistency

✅ No type changes needed
