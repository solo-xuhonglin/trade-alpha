# 数据同步定时任务设计

## 概述

实现一个APScheduler定时任务，每1分钟执行一次，自动同步市值前3000只股票的日线数据和计算技术指标。

## 状态定义

StockList 新增字段 `sync_status`：

| 状态值 | 说明 |
|--------|------|
| `pending` | 待处理（默认值） |
| `data_completed` | 数据下载完成，等待指标计算 |
| `indicator_completed` | 指标计算完成，同步完成 |

## 任务逻辑

### data_sync_job()

每分钟执行一次：

1. **更新股票列表**：检查 stock_list 是否为空，为空则从 Tushare 获取
2. **查询待处理股票**：按市值（total_mv）从大到小，取 sync_status = "pending" 的前1只股票
3. **如无待处理股票**：检查是否有 sync_status = "data_completed" 的股票需要计算指标
4. **处理数据获取**（sync_status = "pending"）：
   - 更新状态为 `data_completed`
   - 按5个时间段分批获取2010年后的数据
   - 每段时间获取完成后等待1秒
5. **处理指标计算**（sync_status = "data_completed"）：
   - 计算 MA 指标（5/10/20/60日均线）
   - 计算 MACD 指标
   - 更新状态为 `active`

### 数据分段

每只股票按以下时间段分批获取：

| 序号 | 开始日期 | 结束日期 |
|------|----------|----------|
| 1 | 2010-01-01 | 2014-12-31 |
| 2 | 2015-01-01 | 2019-12-31 |
| 3 | 2020-01-01 | 2024-12-31 |
| 4 | 2025-01-01 | 当前日期 |

### 并发控制

- 使用 1 个并发（asyncio.Semaphore）
- 每次 Tushare API 请求前等待 1 秒
- 单只股票处理失败后保持原状态，下次任务继续处理

### 错误处理

- Tushare 接口异常：记录日志，继续处理
- 单只股票失败：保持 sync_status 不变，下次任务重试
- 不使用重试机制，依赖定时任务自然重试

## 文件结构

```
backend/src/trade_alpha/
├── scheduler/
│   ├── __init__.py
│   ├── data_sync.py          # 定时任务主逻辑
│   └── jobs.py               # APScheduler 任务注册
```

## 实现要点

1. 使用 APScheduler 的 BackgroundScheduler
2. 异步执行，使用 asyncio + aiohttp 或同步调用 Tushare SDK
3. 查询股票时按 total_mv 降序排列（注意处理 NULL 值）
4. 市值前3000只的限制在查询时用 limit(3000)

## 启动方式

集成到 FastAPI lifespan 生命周期：

1. 在 `api/main.py` 的 lifespan 事件中初始化并启动 APScheduler
2. 服务启动时调度器开始运行，每分钟执行 `data_sync_job`
3. 服务关闭时调度器优雅停止

```python
# api/main.py lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时
    scheduler = DataSyncScheduler()
    scheduler.start()
    app.state.scheduler = scheduler

    yield

    # 关闭时
    scheduler.stop()
```

## 配置项

可通过环境变量或配置文件设置：
- `DATA_SYNC_INTERVAL`: 任务执行间隔（默认60秒）
- `SYNC_STOCK_LIMIT`: 每批次处理的股票数量（默认1）
- `API_REQUEST_DELAY`: API请求间隔（默认1秒）
