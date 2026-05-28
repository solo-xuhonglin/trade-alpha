# 回测功能增强设计文档

## 概述

增强回测功能，增加：
1. 每笔卖出交易的盈亏追踪（pnl_amount / pnl_pct）
2. 按股票的盈亏详情统计（PNL Details API）
3. 胜率改为卖出交易胜率
4. 基线基准从每日再平衡改为期初等权买入持有
5. 前端盈亏分析面板（饼状图 + 详情表格）

## 涉及模块

| 模块 | 改动内容 |
|------|---------|
| `dao/execution_trade.py` | 新增 pnl_amount、pnl_pct 字段 |
| `dao/execution.py` | 新增 trade_win_rate 字段 |
| `execution/pipeline.py` | 基线改为期初等权买入持有；sell 时计算 PnL 写入 trade |
| `strategy/base.py` | PositionManager.settle_orders 返回 PnL 数据 |
| `api/routers/backtest_records.py` | 新增 PNL Details API |
| `frontend` | 新增盈亏分析面板（饼图 + 表格） |

## 后端变更

### 1. ExecutionTrade 模型

新增两个字段：

```python
pnl_amount: Optional[float] = None  # 卖出时实现的盈亏金额（正=盈利，负=亏损）
pnl_pct: Optional[float] = None     # 盈亏百分比 = pnl_amount / cost_basis
```

买入交易这两个字段始终为 None。

### 2. ExecutionResult 模型

新增一个字段：

```python
trade_win_rate: Optional[float] = None  # 卖出交易胜率（盈利卖出次数 / 总卖出次数）
```

在 `_finalize_result` 中从已落盘的 ExecutionTrade 汇总填入，避免每次前端查询实时计算。

### 3. 卖出盈亏计算（pipeline.py _settle_orders）

在卖出交易创建时计算 PnL：

```python
# cost_basis: 持仓买入成本（含买入手续费分摊）
# revenue: 卖出收入（减卖出费用和印花税）
cost_basis = buy_price * abs(shares) + fee * (abs(shares) / total_shares)
sell_revenue = matched_price * abs(shares) - sell_fee - stamp_tax
pnl_amount = round(sell_revenue - cost_basis, 2)
pnl_pct = round(pnl_amount / cost_basis, 4)
```

- `buy_price` 来自 `self.positions[ts_code].buy_price`
- `total_shares` 来自 `self.positions[ts_code].shares`
- 买入手续费按卖出股数比例分摊

**注意**：目前的策略模型是每次买入累计持仓（多次买入同只股票会更新 position 的 shares 和 buy_price），卖出时按 FIFO 平均成本。当前 PositionEmbed 的 buy_price 是最后一次买入的价格，为了准确需要改为加权平均成本。

但为了最小化改动，可以用 `PositionEmbed.buy_price` 作为近似（简化处理），因为目前的策略很少对同一股票做多次买入。

### 4. 基线改为期初等权买入持有

**`_init_baseline`** 新增数据结构：

```python
self._baseline_shares: Dict[str, float] = {}
self._baseline_initialized = False
```

**`_track_baseline`** 逻辑变更：

- 第一个有数据的交易日：
  - 对每只股票：`shares = (initial_capital / len(ts_codes)) / close_price`
  - `_baseline_daily_values[0] = initial_capital`

- 后续每日：
  - `portfolio_value = sum(shares[i] * close[i])`
  - 追加到 `_baseline_daily_values`
  - 忽略 close 缺失的股票（不贡献价值）

- 指标计算复用现有逻辑（daily returns → calculate_metrics）

### 5. PNL Details API

新增 `GET /backtests/{result_id}/pnl-details`

从 ExecutionTrade 聚合卖出交易数据，按 ts_code 分组：

```python
# 聚合逻辑
pipeline = [
    {"$match": {"backtest_id": result_id, "action": "sell", "status": "filled"}},
    {"$group": {
        "_id": "$ts_code",
        "total_pnl_amount": {"$sum": "$pnl_amount"},
        "profit_trades": {"$sum": {"$cond": [{"$gt": ["$pnl_amount", 0]}, 1, 0]}},
        "loss_trades": {"$sum": {"$cond": [{"$lt": ["$pnl_amount", 0]}, 1, 0]}},
        "total_sells": {"$sum": 1},
        "total_profit_amount": {"$sum": {"$cond": [{"$gt": ["$pnl_amount", 0]}, "$pnl_amount", 0]}},
        "total_loss_amount": {"$sum": {"$cond": [{"$lt": ["$pnl_amount", 0]}, "$pnl_amount", 0]}},
    }}
]
```

返回格式：

```json
{
  "items": [
    {
      "ts_code": "000001.SZ",
      "stock_name": "平安银行",
      "total_pnl_amount": 1500.0,
      "profit_count": 3,
      "loss_count": 2,
      "trade_win_rate": 0.6,
      "total_profit_amount": 2500.0,
      "total_loss_amount": -1000.0
    }
  ],
  "summary": {
    "total_sell_trades": 80,
    "total_pnl_amount": 5000.0,
    "total_profit_trades": 50,
    "total_loss_trades": 30,
    "total_profit_amount": 12000.0,
    "total_loss_amount": -7000.0,
    "overall_win_rate": 0.625
  }
}
```

### 6. `_finalize_result` 更新

在现有汇总逻辑中增加：

```python
# 计算 trade_win_rate
sell_trades = await ExecutionTrade.find(
    ExecutionTrade.backtest_id == result.id,
    ExecutionTrade.action == "sell",
    ExecutionTrade.status == "filled",
).to_list()
if sell_trades:
    profit_sells = sum(1 for t in sell_trades if t.pnl_amount and t.pnl_amount > 0)
    result.trade_win_rate = round(profit_sells / len(sell_trades), 4)
```

## 前端变更

### 1. API 层

`frontend/src/api/backtestRecord.ts` 新增 `getPnlDetails(resultId)` 方法。

### 2. 盈亏分析面板

在 `BacktestRecordsView.vue` 的指标弹窗（`resultDialog`）中新增**盈亏分析**部分，含：

| 模块 | 说明 |
|------|------|
| **汇总卡片** | 总盈亏金额（绿/红）、盈利次数、亏损次数、胜率 |
| **金额饼图** | 每只股票一个扇区，盈利绿色，亏损红色，大小= \|pnl_amount\| |
| **次数饼图** | 每只股票一个扇区，大小= 总卖出次数 |
| **详情表格** | 股票名称、总盈亏、盈利次数、亏损次数、胜率 |

饼图使用 VChart 或 ECharts，颜色映射：
- 盈利（pnl > 0）：绿色系 `#4caf50`
- 亏损（pnl < 0）：红色系 `#f44336`

## 测试计划

| 测试项 | 说明 |
|-------|------|
| 基线验证 | 期初买入持有 vs 原每日再平衡，对比差异 |
| PnL 准确性 | 手动计算验证多笔买卖的 PnL |
| API 聚合 | 按股票分组汇聚正确性 |
| 边界情况 | 无卖出交易、股票数据缺失、零值处理 |

## 不涉及

- 不做历史回测数据的迁移（旧数据的 ExecutionTrade 无 pnl 字段，新回测才有）
- 不改动回测任务的触发方式
- 不改动现有的日度胜率（day-level win_rate）字段