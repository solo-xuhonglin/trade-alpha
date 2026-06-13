# 清空股票信息 & stock_data_init 参数配置设计

## 概述

两个改动：
1. 前端股票列表页的"更新股票列表"改为"清空股票信息"，增加二次确认，清空 StockList 和 stock_daily 所有数据
2. stock_data_init 任务的参数（股票数量、数据年限）改为可通过前端配置页面设置，替代当前的环境变量固定值

## 改动清单

### 1. 前端：DataListView.vue — 按钮改造

- 按钮文本："更新股票列表" → "清空股票信息"
- 图标：`mdi-update` → `mdi-delete-sweep`
- 颜色：`color="error"`
- 加载状态：绑定 `loadingClear`
- 点击行为：弹出二次确认对话框 → 确认后调 API

**确认对话框：**

使用 `v-dialog`，包含：
- 标题："确认清空"
- 提示文案："此操作将清空所有股票信息和历史日线数据，不可恢复。确定要继续吗？"
- 两个按钮："取消" / "确认清空"（红色 error 颜色）

### 2. 后端：新 API — `DELETE /data/stocks/clear`

**data.py:**

```python
@router.delete("/stocks/clear")
async def clear_stocks_endpoint():
    """Clear all stock list and daily data. Use with caution."""
    db = await get_database()
    stock_result = await db.stock_list.delete_many({})
    daily_result = await db.stock_daily.delete_many({})
    return {
        "deleted_stocks": stock_result.deleted_count,
        "deleted_daily": daily_result.deleted_count,
    }
```

使用 raw MongoDB driver 的 `delete_many({})`，毫秒级完成，不清除索引。

### 3. 前端：data.ts — 新 API 方法

```typescript
clearStocks: () => api.delete('/data/stocks/clear'),
```

### 4. 后端：stock_data_init_job.py — 支持 cfg.params

`run_stock_data_init_job` 从 `cfg.params` 读取 `stock_count` 和 `data_years`：

- `stock_count` → 替代 `config.top_market_cap_stocks`
- `data_years` → 替代 `config.data_years`

params 中必须包含这两个值，`stock_data_init_job` 内的函数不再调用 `load_config()` 获取 `data_years` 和 `top_market_cap_stocks`，改为通过参数传入。同时为 `stock_data_init` 的默认配置设置默认 params（`{"stock_count": "1500", "data_years": "12"}`）。

修改函数签名和实现：

| 函数 | 改动 |
|------|------|
| `run_stock_data_init_job` | 从 cfg.params 提取 stock_count/data_years，传给下游函数；无 params 时抛出 ValueError |
| `get_pending_stocks` | 增加 `top_limit` 可选参数 |
| `get_data_period` | 增加 `data_years` 可选参数 |
| `check_active_stocks_sufficient` | 增加 `stock_count` 可选参数 |

### 5. 前端：ScheduledTaskConfigView.vue — stock_data_init 参数页

`showParamsTab` 增加 `stock_data_init`：

```typescript
const showParamsTab = computed(() =>
  ['auto_suggest', 'stock_data_init'].includes(editItem.value?.task_key)
)
```

参数标签页内，根据 `task_key` 动态渲染不同字段：

```
auto_suggest → 现有的 training_id, strategy_config_id, top_n, portfolio_id
stock_data_init → 两个数字输入框：
  - stock_count: "股票数量", 默认 1500, min=100, max=6000
  - data_years: "数据年限", 默认 12, min=1, max=20
```

### 6. 执行历史页面：ScheduledTaskLogView.vue — 更新筛选下拉

当前筛选选项写死了旧的 `data_sync`、`data_count`、`daily_update`，更新为新的 task_key：

```typescript
const taskKeyOptions = [
  { title: '股票列表同步', value: 'stock_list_sync' },
  { title: '股票数据初始化', value: 'stock_data_init' },
  { title: '每日数据更新', value: 'daily_data' },
  { title: '实盘建议', value: 'auto_suggest' },
]
```

## 操作流程

```
1. 用户点击 "清空股票信息" → 确认对话框 → 确认
   → 后端删除 StockList + stock_daily 所有文档
   → 前端刷新列表（显示空表）

2. 进入 任务配置 → 编辑 stock_data_init → 设置参数
   → stock_count=1500, data_years=12

3. 手动触发 stock_list_sync
   → 从 Tushare 拉取最新股票列表
   → 新股票 sync_status="pending"

4. 手动触发 stock_data_init
   → 按配置的 stock_count 和 data_years 处理 pending 股票
   → 全量下载日线 + 计算指标 → 标记 active
```

## 不涉及

- daily_data（17:00 增量更新）不受影响
- auto_suggest（18:00 实盘建议）不受影响
- stock_list_sync（01:00 列表同步）不受影响