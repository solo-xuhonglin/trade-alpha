# 每日数据增量更新设计

## 概述

新增一个定时任务，每日收盘后（18:00）自动补齐 active 股票的最新日线数据，并检测是否发生过除权除息，发现后标记 pending 等待全量重拉。

## 背景

现有 `data_sync.py` 是一次性初始化全量同步（pending→active），达到目标后就不再执行。没有每日增量更新机制。

Tushare 的 `pro_bar(adj="qfq")` 返回前复权数据。发生除权除息时，所有历史前复权价格会被重新计算。通过"多查一天"的方式检测：对比同一交易日的新旧 close 价格，不一致说明发生了前复权调整。

## 状态流转

```
                daily_update (检测到除权)
  active ───────────────────────────────→ pending
    ↑                                        │
    │                                        │ data_sync (全量重拉+指标重算)
    │                                        ↓
    └─────────────────────────────────────── active
```

- `daily_update`（新增）：只处理 active 股票，增量更新 + 除权检测
- `data_sync`（不变）：处理 pending→active 的全量拉取

## 执行流程

### 入口：每日 18:00 触发

```
1. 获取最新交易日
   从 trade_calendar 查最新 is_open=1 且 ≤ today 的日期

2. 获取所有 active 股票（含 StockList.latest_date）
   sync_status="active", 排除测试股票

3. 顺序处理每只股票（限速 0.3s/只 = 200次/分钟）:
   a. 确定缺失范围
      missing_trade_dates = 日历中 latest_date 之后的所有交易日
      if 无缺失 → skip

   b. 一次 API 调用完成：fetch + 检测 + 写入
      
      df = fetch_stock_data(ts_code, latest_date, latest_trade_date)
      if df empty → continue
      
      对比 latest_date 的 close:
        new_close = df[df.trade_date==latest_date].close
        old_close = StockDaily 中 latest_date 的 close
        if not math.isclose(new_close, old_close):
            标记 sync_status="pending"
            logger.warning("...ex-rights detected")
            continue  # 等 data_sync 全量重拉
      
      写入新数据：
        new_records = df[df.trade_date > latest_date]
        if new_records 非空 → 批量写入 StockDaily
      
   c. 计算指标（仅新日期）
      if new_records 非空:
          calculate_all_indicators(ts_code, min_date, max_date)
          update_single_stock_data_count(ts_code)

4. 日志摘要：总处理数 / 新增数 / 除权数 / 失败数
```

### 关键设计点

**一次 API 调用完成检测+写入**
- `fetch_and_store_stock_daily` 会跳过已存在的日期，无法获取新拉的 close 做比对
- 改用 `fetch_stock_data`（同步函数，只返回 DataFrame 不做写入）+ 手动写入
- 这样一次 API 调用同时完成：数据获取、一致性检测、新数据写入

**close 对比精度**
- 使用 `math.isclose`，默认 rel_tol=1e-9

**限速 200次/分钟**
- 顺序处理，每只股票间隔 0.3s
- 无需并发，因为主要瓶颈是 API 调用，后续指标计算是本地操作

## 文件变更

### 新增 `backend/src/trade_alpha/scheduler/daily_update.py`

| 函数 | 职责 |
|------|------|
| `run_daily_update()` | 入口函数 |
| `_get_active_stocks()` | 获取所有 active 股票 |
| `_check_and_update_single_stock()` | 单只股票：fetch→检测→写入→指标 |
| `create_daily_update_scheduler()` | 创建 APScheduler job |

### 修改文件

| 文件 | 修改内容 |
|------|---------|
| `scheduler/data_sync.py` | 在 `create_scheduler()` 中新增 daily_update job |
| `data/fetcher.py` | 无修改（复用 `fetch_stock_data`）|
| `data/service.py` | 复用 `fetch_and_store_stock_daily` 中的写入逻辑，或直接操作 StockDaily |
| `indicators/service.py` | 已有 start_date/end_date 参数，可直接用 |

## 错误处理

- 单只股票异常（API / 数据库 / 指标计算）不影响其他，记录 error 后 continue
- Tushare API 异常：捕获后跳过该股票，记录日志

## 日志

关键节点日志使用英文：
- "Daily update job started" (info)
- "Processing {ts_code}: {n} missing trade days" (info)
- "{ts_code}: ex-rights detected (close {old}->{new}), marking pending" (warning)
- "{ts_code}: inserted {n} new records" (info)
- "Daily update job completed: {processed} processed, {ex_rights} pending, {failed} failed" (info)