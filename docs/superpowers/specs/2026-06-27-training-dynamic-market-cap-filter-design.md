# 训练模块按年动态筛选市值 Top N 股票

## 背景

当前训练模块和回测模块在股票筛选上存在不一致：

| | 训练 | 回测 |
|:---|:---|:---|
| 数据源 | `StockList`（当前市值） | `StockListHistory`（历史市值快照） |
| 范围 | top 3000 只（一次性固定） | top 300 → 筛选到 ~150（每周动态） |
| 市值时效性 | 训练时的市值，过时 | 对应交易日的市值 |

**问题：** 模型从 3000 只股票学习，但实际回测只用到 ~150 只。大量训练样本来自不会出现在回测的股票，模型注意力被分散。同时一个 2020 年市值 top 100 但 2025 年跌出前 100 的股票，数据仍然出现在 2025 年的训练中。

## 设计

### 核心思路

在每一年训练前，查 `StockListHistory` 获取该年最后一个交易日的 top N 市值股票，取与原始 `ts_codes` 的交集作为该年训练样本。

### 数据流

```
API入参 (start_rank=1, end_rank=100)
    ↓
原始 ts_codes = [A, B, C, D, E, F]  (当前市值 top 100)
    ↓
按年训练：
  2023年 → StockListHistory → 2023年最后交易日 top 100 → 交集 [A,B,C,D,E] → 训练
  2024年 → StockListHistory → 2024年最后交易日 top 100 → 交集 [A,B,C,D,F] → 训练
```

### 数据容错

如果 `StockListHistory` 中某年的市值数据不存在，自动从 Tushare 下载（复用回测的 `resolve_and_fetch_historical_date` 机制）。

### 进度更新

在按年过滤步骤加入 `TaskService.update_progress()`，保证训练任务的可观测性。

## 涉及文件

| 文件 | 改动 |
|------|------|
| `models/training/helpers.py` | 新增 `_get_top_n_for_year()` 辅助函数 |
| `models/xgboost/classifier.py` | 年循环内加动态过滤 + 进度更新 |
| `models/lstm/classifier.py` | 同上 |

## 关键函数

```python
async def _get_top_n_for_year(year: int, top_n: int) -> List[str]:
    """Get top N ts_codes by market cap for a given year's last trading day.

    Auto-fetches from Tushare if market cap data doesn't exist for that date.
    """
    # 从年末往前找最后一个交易日
    for i in range(31):
        check = (datetime(year, 12, 31) - timedelta(days=i)).strftime("%Y%m%d")
        day = await TradeCalendar.find_one(
            TradeCalendar.cal_date == check,
            TradeCalendar.is_open == 1,
        )
        if day:
            resolved = day.cal_date
            break
    else:
        return []

    # 确保市值数据存在（有则直接返回，无则自动下载）
    resolved = await resolve_and_fetch_historical_date(resolved)

    # 查该交易日 top N
    records = await StockListHistory.find(
        StockListHistory.trade_date == resolved,
        StockListHistory.total_mv != None,
    ).sort(-StockListHistory.total_mv).limit(top_n).to_list()
    return [s.ts_code for s in records]
```

```python
# XGBoost classifier - train() 方法中的年循环
for year in years:
    await TaskService.update_progress(task_id, f"正在获取 {year} 年股票列表...")
    year_top = await _get_top_n_for_year(year, len(ts_codes))
    if not year_top:
        continue
    filtered = [c for c in ts_codes if c in year_top]
    if not filtered:
        continue
    logger.info(f"{year}: keeping {len(filtered)}/{len(ts_codes)} stocks")
    year_df = await _load_year_data(year, filtered, horizon)
    ...
```

## 不变的部分

- API 层入参（`start_rank`/`end_rank`）
- `_load_year_data` 函数本身
- 模型配置项
- 训练后的保存/评估流程
