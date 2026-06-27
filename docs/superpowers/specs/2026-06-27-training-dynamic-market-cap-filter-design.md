# 训练模块按年动态筛选市值 Top N 股票

## 背景

当前训练模块和回测模块在股票筛选上存在不一致：

| | 训练 | 回测 |
|:---|:---|:---|
| 股票来源 | API 入参 `start_rank`/`end_rank`，**一次性**从当前 `StockList` 取 | 每周从 `StockListHistory` 动态取历史市值 top N |
| 数据准备 | 训练前只对入参列表中的股票确保数据就绪 | 候选池新入的股票自动下载日线+计算指标 |
| 范围 | 固定 top 100（由 UI 传入） | 每周按历史市值变化 |

**问题：** 现在训练取的是**当前**市值 top 100 的股票列表，一整批传给训练模块。但：
- 5 年前 top 100 的股票和今天 top 100 的可能完全不同
- 某些今天 top 100 的股票 5 年前可能还没上市（没有历史数据）
- 某些 5 年前 top 100 的股票今天可能跌出了前 100（训练数据漏了）

## 设计

### 核心思路

按年查 `StockListHistory` 取该年最后一个交易日的历史市值 top N，作为该年的实际训练股票列表。每年训练前自动补全缺失股票的日线数据和指标。

### 数据流

```
API入参 (start_rank=1, end_rank=100)
    ↓ 仅作为初始参考范围
按年训练：
  2023年 → StockListHistory → 2023年最后交易日 top 100
    ↓ 对每只股票检查数据完整性
    ├── 已有 sync_status='active' → 直接使用
    └── 无数据 → 下载日线 + 计算指标 → 标记 active
    ↓
  只加载这 100 只股票的数据训练

  2024年 → StockListHistory → 2024年最后交易日 top 100
    ↓ (同上)
    ↓
  只加载这 100 只股票的数据训练
```

### 按年动态筛选

不再使用 API 传入的 `ts_codes` 列表，改为每年直接从 `StockListHistory` 取 top N：

```python
async def _get_top_n_for_year(year: int, top_n: int) -> List[str]:
    """Get top N ts_codes by market cap for a given year's last trading day."""
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

    # 确保市值数据存在（自动下载）
    resolved = await resolve_and_fetch_historical_date(resolved)

    # 查该年 top N
    records = await StockListHistory.find(
        StockListHistory.trade_date == resolved,
        StockListHistory.total_mv != None,
    ).sort(-StockListHistory.total_mv).limit(top_n).to_list()
    return [s.ts_code for s in records]
```

### 数据补全

对每年 top N 中尚未就绪的股票，复用 `active_stock_data` 下载日线并计算指标：

```python
async def _ensure_stocks_ready(ts_codes: List[str]) -> None:
    """Ensure all stocks have daily data and indicators calculated."""
    pending = []
    for code in ts_codes:
        stock = await StockList.find_one(StockList.ts_code == code)
        if not stock or stock.sync_status != "active":
            pending.append(code)

    if not pending:
        return

    logger.info(f"Preparing data for {len(pending)} stocks...")
    sem = asyncio.Semaphore(5)  # limit concurrency

    async def prepare_one(code: str) -> bool:
        async with sem:
            await asyncio.sleep(0.2)  # rate limit
            return await active_stock_data(code)

    results = await asyncio.gather(*[prepare_one(c) for c in pending])
    success = sum(1 for r in results if r)
    logger.info(f"Data preparation: {success}/{len(pending)} succeeded")
```

### 进度更新

```python
for year in years:
    await TaskService.update_progress(task_id, f"正在获取 {year} 年股票列表...")
    year_stocks = await _get_top_n_for_year(year, len(ts_codes))
    if not year_stocks:
        continue
    logger.info(f"{year}: top {len(year_stocks)} stocks")

    await TaskService.update_progress(task_id, f"正在准备 {year} 年股票数据...")
    await _ensure_stocks_ready(year_stocks)

    year_df = await _load_year_data(year, year_stocks, horizon)
    ...
```

### API 层不变

入参 `start_rank`/`end_rank` 保留，`end_rank` 的值作为每年取 top N 的 N 值。但训练不再使用 API 传入的具体 ts_codes 列表，改为每年动态查询。

## 涉及文件

| 文件 | 改动 |
|------|------|
| `models/training/helpers.py` | 新增 `_get_top_n_for_year()` 和 `_ensure_stocks_ready()` |
| `models/xgboost/classifier.py` | 年循环改为动态筛选 + 数据补全 + 进度 |
| `models/lstm/classifier.py` | 同上 |

## 不变的部分

- API 层入参（`start_rank`/`end_rank`）
- `_load_year_data` 本身
- 模型配置项
- 训练后的保存/评估流程
- `active_stock_data` 函数（直接复用）
