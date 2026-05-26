# 股票名称缓存 + 接口展示优化

## 问题

回测历史、交易记录等接口只返回股票代码（`ts_code`），前端展示时用户只能看到 "002594.SZ" 这样的代码，无法直观识别股票名称。

## 设计

### 1. 股票名称缓存

创建 [dao/stock_name_cache.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/dao/stock_name_cache.py)，提供进程级内存缓存：

```python
_cache: dict[str, str] = {}

async def get_stock_name(ts_code: str) -> str
async def get_stock_names(ts_codes: list[str]) -> dict[str, str]
```

- 首次查询时从 MongoDB `StockList` 加载，后续直接返回
- 不设过期，股票名称基本不变
- 批量查询一次性加载缺失项

### 2. API 数据模型变更

`ExecutionTrade` 本身无 `stock_name` 字段，所有 API 在返回时通过缓存动态填充。

#### `POST /backtests/run` — 触发回测

无变更。stock_name 在 pipeline.run_backtest 中已处理（单股票模式写 `result.stock_name`）。

#### `GET /backtests` — 回测结果列表

新增字段：
- 如果 `result.ts_code` 存在（单股票模式）+ `result.stock_name` 存在，直接用
- 否则 `stock_name` 为 None

#### `GET /backtests/{id}/trades` — 回测详情交易

每条 trade 新增 `stock_name`，通过缓存获取。

#### `GET /backtests/trades` — 全局交易记录

每条 trade 新增 `stock_name`，通过缓存获取。

#### `GET /backtests/trades/options` — 筛选条件

`ts_codes` 从 `string[]` 改为 `{code: string, name: string}[]`，返回代码 + 名称。

### 3. 前端展示

**原则**：接口同时返回 `ts_code` + `stock_name`，前端只显示 `stock_name`。

#### BacktestRecordsView.vue

- 回测列表表头 `股票代码` → `股票`
  - 单股票模式显示 `stock_name`
  - 多股票模式显示 `-`
- 交易弹窗表头 `股票代码` → `股票`，显示 `stock_name`

#### TradesView.vue

- 表格表头 `股票代码` → `股票`，列内容改为 `stock_name`
- 筛选下拉：
  - `v-select` 的 `items` 变更为 `{code, name}` 结构
  - 显示 `name`，内部 `value` 仍用 `code`
  - 选项标签展示 `name (code)`

### 不移改的

- `GET /backtests/{id}/prediction-stocks` — 已有 `ts_code + stock_name` ✅
- `GET /backtests/{id}/predictions/{ts_code}` — 已有 `stock_name` ✅
