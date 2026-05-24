# 单只股票LSTM回测性能优化设计

## 问题分析

单只股票回测模式存在严重性能问题：
- 加载200只股票列表，但只需要1只
- 每天查询200只股票的收盘价和日数据，但只需要1只
- 一年约250个交易日 × 多个数据库查询 = 巨大开销

**统计（1年回测）：**
| 操作 | 频率 | 每次对象数 | 总查询数 |
|------|------|-----------|---------|
| load_day_close | 每天 | 200只股票 | 250次 |
| load_day_data | 每天 | 200只股票 | 250次 |
| load_history_data | 每天 | 200只股票 | 250次 |
| **总计** | - | - | **750次数据库查询** |

## 优化方案

### 修改1：单只股票模式只处理单只股票

**位置：** [pipeline.py#L131-L149](file:///d:/projects/trade-alpha/backend/src/trade_alpha/execution/pipeline.py#L131-L149)

**原代码：**
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

**修改后：**
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

## 预期效果

- 数据库查询从200只股票降至1只股票
- 回测速度预计提升约200倍（理论上限）
- 实际提升受缓存和其他因素影响，预计能从半小时降至几分钟

## 下一步优化（可选）

如果上述优化后仍需改进，可以考虑：
- 预加载回测期间全部历史数据，避免每天查询
- 减少load_history_data调用频率
