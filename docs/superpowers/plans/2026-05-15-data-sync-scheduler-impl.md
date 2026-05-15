# 数据同步定时任务优化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan.

**Goal:** 简化定时任务逻辑，每分钟批量处理最多 300 只股票的同步

**Architecture:** 修改 `scheduler/data_sync.py`，移除中间状态，实现批量循环处理

**Tech Stack:** Python, APScheduler, Beanie (MongoDB)

---

## 文件结构

- **修改**: `backend/src/trade_alpha/scheduler/data_sync.py`

---

## 实施任务

### Task 1: 修改 get_pending_stocks 函数

**Files:**
- Modify: `backend/src/trade_alpha/scheduler/data_sync.py`

- [ ] **Step 1: 修改函数 limit 参数**

将 `limit=1` 改为 `limit=300`：

```python
async def get_pending_stocks(limit: int = 300) -> List[StockList]:
    """Get pending stocks sorted by market value descending."""
    return await StockList.find(
        StockList.sync_status == "pending",
        NotIn(StockList.ts_code, TEST_EXCLUDED_TS_CODES)
    ).sort(-StockList.total_mv).limit(limit).to_list()
```

### Task 2: 新增单只股票完整处理函数

**Files:**
- Modify: `backend/src/trade_alpha/scheduler/data_sync.py`

- [ ] **Step 1: 新增 process_single_stock 函数**

```python
async def process_single_stock(stock: StockList) -> bool:
    """Process single stock: fetch data, calculate indicators, update status.
    
    Args:
        stock: Stock object
        
    Returns:
        Whether succeeded
    """
    try:
        # 拉取 20 年数据
        for start_date, end_date in DATA_PERIODS:
            count = await fetch_and_store_stock_daily(stock.ts_code, start_date, end_date)
            logger.info(f"Fetched {count} records for {stock.ts_code} ({start_date}-{end_date})")
            await asyncio.sleep(API_REQUEST_DELAY)
        
        # 计算指标
        await calculate_all_indicators(stock.ts_code)
        logger.info(f"Completed indicators for {stock.ts_code}")
        
        # 更新状态为 active
        stock.sync_status = "active"
        await stock.save()
        return True
    except Exception as e:
        logger.error(f"Failed to process {stock.ts_code}: {e}")
        return False
```

### Task 3: 重写 run_data_sync_job 函数

**Files:**
- Modify: `backend/src/trade_alpha/scheduler/data_sync.py`

- [ ] **Step 1: 修改 run_data_sync_job 函数**

```python
async def run_data_sync_job():
    """Execute one data sync job.
    
    Process up to 300 stocks per run:
    1. Get pending stocks (up to 300)
    2. Process each stock sequentially:
       a. Fetch 20 years of data
       b. Calculate indicators
       c. Update status to active
       d. Wait 0.2 seconds
    3. Stop on first failure
    """
    logger.info("Starting data sync job")

    await ensure_stock_list()

    pending_stocks = await get_pending_stocks(limit=300)
    if not pending_stocks:
        logger.info("No stocks to process")
        return
    
    logger.info(f"Found {len(pending_stocks)} stocks to process")
    
    for stock in pending_stocks:
        logger.info(f"Processing {stock.ts_code} ({pending_stocks.index(stock) + 1}/{len(pending_stocks)})")
        success = await process_single_stock(stock)
        
        if not success:
            logger.error(f"Stopping job due to failure on {stock.ts_code}")
            return
    
    logger.info("Data sync job completed")
```

### Task 4: 清理无用代码

**Files:**
- Modify: `backend/src/trade_alpha/scheduler/data_sync.py`

- [ ] **Step 1: 删除以下函数**

- `get_data_completed_stocks()`
- `fetch_stock_data_with_periods()`
- `calculate_stock_indicators()`

### Task 5: 测试验证

- [ ] **Step 1: 运行检查脚本确认服务正常**

```bash
cd backend && python scripts/check_server.py
```

- [ ] **Step 2: 检查同步状态**

```bash
cd backend && python scripts/check_stock_sync_status.py
```

---

## 预期结果

- `get_pending_stocks()` 获取最多 300 只股票
- 循环处理每只股票，完成后更新为 `active`
- 失败时立即停止
- 数据库中不再有 `data_completed` 状态的股票（除非处理失败）
