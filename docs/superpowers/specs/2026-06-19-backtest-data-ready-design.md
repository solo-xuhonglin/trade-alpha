# 回测数据自动准备设计文档

## 问题

候选池扩大后（周度双选股 + 滚动保留，约 200~300 只），部分股票可能尚未被数据初始化流程处理（`sync_status != "active"`），缺少日线数据和技术指标，导致回测时评分排名失败。

## 方案：提取共享数据准备函数 + BacktestRunner 集成

### 核心思路

1. 从 `stock_data_init_job.py` 中提取 `ensure_stock_data_ready()` 共享函数到 `data/service.py`
2. BacktestRunner 在生成候选池后、初始化 Pipeline 前，检查所有候选股票的 `sync_status`，对非 active 的股票调用共享函数补齐数据
3. 数据准备阶段在进度条中体现，显示当前正在处理的股票代码

### 共享函数

```python
# data/service.py 新增

async def active_stock_data(ts_code: str) -> bool:
    """Ensure a stock has daily data and indicators calculated.

    If the stock already has sync_status='active', returns True immediately.
    Otherwise performs the full init flow: fetch daily data from Tushare,
    calculate all indicators, mark sync_status='active', update data_count.
    """
```

逻辑与 `stock_data_init_job.py:process_single_stock()` 完全一致，使用配置的 `data_years` 确定下载范围（比回测区间更长）。`process_single_stock()` 重构后直接委托给这个共享函数。

### BacktestRunner 集成

```
BacktestRunner.execute()
  │
  ├─ 1. 计算候选池 (0%~10%)
  │      CandidateListProvider + 统计 union_ts_codes
  │
  ├─ 2. 数据准备 (10%~20%)
  │      检查 union_ts_codes 的 sync_status
  │      对有 pending 的股票逐个执行 ensure_stock_data_ready()
  │      每个股票更新进度: "正在准备数据 000001.SZ (3/15)"
  │
  ├─ 3. 预热 + 回测 (20%~100%)
  │      BacktestPipeline run_backtest()
  │
```

### 进度分档

| 进度 | 阶段 | 操作 |
|------|------|------|
| 0% ~ 10% | 候选池计算 | provider.get_weekly_candidates() |
| 10% ~ 20% | 数据就绪 | 逐个处理 pending 股票 |
| 20% ~ 40% | 预热 | Pipeline warmup |
| 40% ~ 90% | 回测主循环 | Pipeline daily loop |
| 90% ~ 100% | 收尾 | Pipeline finalize |

### 影响范围

| 文件 | 改动 | 说明 |
|------|------|------|
| `backend/src/trade_alpha/data/service.py` | **新增** `ensure_stock_data_ready()` ~20 行 | 共享函数，无日期参数 |
| `backend/src/trade_alpha/scheduler/stock_data_init_job.py` | 重构 `process_single_stock()` ~5 行 | 委托给共享函数 |
| `backend/src/trade_alpha/task/backtest_runner.py` | 新增数据检查+准备逻辑 ~30 行 | 第 2 阶段数据就绪 |

**不涉及**：BacktestPipeline、CandidateListProvider、API、前端、DAO 层全部不变。
