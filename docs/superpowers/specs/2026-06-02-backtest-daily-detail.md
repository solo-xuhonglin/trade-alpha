# 回测每日详情弹窗

## 概述

在现有回测记录弹窗中替换掉「交易」按钮，改为每日详情弹窗，按天展示回测过程的详细数据，包括每日成交记录（含卖出理由）和每日持仓明细（含收益及基线对比），帮助用户深入分析策略的日常表现。原有「交易」功能与独立交易记录页面功能重复，故替换。

## 功能需求

### 1. 卖出理由标注

在 `MultiStockStrategy` 的 `make_decisions` 中，为每条卖出 `PendingOrder` 标注具体理由，理由字段通过结算流程传递到 `ExecutionTrade.reason`，最终在前端交易记录中展示。

#### 卖出理由列表

| 理由标识 | 中文显示 | 触发条件 |
|---------|---------|---------|
| `stop_loss` | 止损卖出 | 持仓亏损达到 `stop_loss_pct` 阈值 |
| `score_below_sell` | 评分低于卖出阈值 | `current_score < sell_threshold` |
| `max_hold_days` | 达到最大持仓天数 | `hold_days >= max_hold_days` |
| `hold_score_low` | 排名靠后评分低 | 不在 `sell_rank_n` 内且 `score < hold_score_threshold` |
| `full_position_forced_sell` | 满仓强制卖出 | 满仓容忍卖出逻辑触发（已有） |

#### 卖出理由常量

定义在 `backend/src/trade_alpha/constants.py`：

```python
# Sell reason constants
SELL_REASON_STOP_LOSS: str = "stop_loss"
SELL_REASON_SCORE_BELOW: str = "score_below_sell"
SELL_REASON_MAX_HOLD_DAYS: str = "max_hold_days"
SELL_REASON_HOLD_SCORE_LOW: str = "hold_score_low"
SELL_REASON_FULL_POSITION: str = "full_position_forced_sell"
```

#### 实现方式

修改 `_check_sell` 方法签名从 `-> bool` 改为 `-> Tuple[bool, str]`，返回 `(是否卖出, 理由常量)`。卖出逻辑的顺序即为理由判定顺序——第一个匹配的条件即为理由。`pipeline.py` 中满仓强制卖出也用常量替代硬编码字符串。

### 2. 后端 API：每日详情

**接口**：`GET /api/backtests/{result_id}/daily-details`

返回回测期间每个交易日的快照详情，包含当日的所有成交记录和持仓明细。

#### 响应结构

```json
{
  "items": [
    {
      "date": "2026-01-15",
      "cash": 50000.0,
      "total_market_value": 55000.0,
      "total_value": 105000.0,
      "baseline_value": 102000.0,
      "day_return": 0.012,
      "cml_return": 0.10,
      "baseline_cml_return": 0.08,
      "positions": [
        {
          "ts_code": "000651.SZ",
          "stock_name": "格力电器",
          "buy_date": "2026-01-10",
          "buy_price": 38.5,
          "current_price": 39.2,
          "shares": 500,
          "fee": 19.25,
          "cost_basis": 19250.0,
          "market_value": 19600.0,
          "unrealized_pnl": 350.0,
          "unrealized_pnl_pct": 0.018,
          "hold_days": 5,
          "entry_score": 0.35
        }
      ],
      "trades": [
        {
          "ts_code": "000651.SZ",
          "stock_name": "格力电器",
          "action": "sell",
          "filled_price": 39.2,
          "shares": -500,
          "fee": 19.6,
          "reason": "max_hold_days",
          "pnl_amount": 350.0,
          "pnl_pct": 0.018
        }
      ]
    }
  ]
}
```

其中 `cml_return` 为累计收益率，`baseline_cml_return` 为基准累计收益率，用于在前端直观对比策略与基准的累计表现。

#### 数据来源

- 日期维度：`ExecutionDailySnapshot.find(backtest_id == obj_id).sort(date)`，每个 snapshot 对应一天
- 持仓数据：直接从 snapshot 的 `positions` 字段读取，`unrealized_pnl` = `market_value - cost_basis`
- 成交数据：`ExecutionTrade.find(backtest_id == obj_id, trade_date == snap.date)`，按日期关联
- 累计收益率：从第一个 snapshot 的 `total_value` 开始逐日计算 `(当前 total_value / 首个 total_value) - 1`
- 基线累计收益率：同样方式基于 `baseline_value`

### 3. 前端弹窗：每日详情

#### 入口

替换回测记录列表 `BacktestRecordsView.vue` 中现有的「交易」按钮：

- 移除 `tradesDialog` 及其关联的 `viewTrades`/`loadTrades` 方法
- 将「交易」按钮改为「每日」按钮，打开新的 `dailyDetailDialog`
- 「每日」按钮颜色使用 `teal`，图标 `mdi-calendar-text`

#### 弹窗布局：折叠卡片式

**弹窗标题**：回测名称 + "每日详情"

**卡片标题行**（始终可见，一行展示关键摘要）：

| 字段 | 说明 |
|------|------|
| 日期 | 交易日 |
| 现金 | 当日收盘现金余额 |
| 持仓市值 | 当日持仓总市值 |
| 总资产 | 现金+持仓市值 |
| 累计收益 | 策略累计收益率（带颜色标识） |
| 基准累计 | 基线累计收益率 |
| 仓位 | 持仓股数 |
| 操作 | 展开/折叠按钮 |

**展开内容**（点击展开后显示）：

1. **上半部分 — 当日成交**
   - 表格展示当日所有成交记录
   - 列：股票名称、操作（买入/卖出）、成交价、数量、手续费、理由（新列）
   - 理由列使用不同颜色 chip 展示，例如止损为红色、满仓强制为橙色等

2. **下半部分 — 当日持仓**
   - 表格展示当日收盘后的持仓明细
   - 列：股票名称、买入日期、成本价、现价、持股数、市值、浮盈亏、收益率、持有天数、入场评分
   - 收益率和浮盈亏用颜色标识（红跌绿涨）

#### 状态管理

- `loading: boolean` — 加载中
- `dailyDetails: DailyDetail[]` — 每日详情列表
- `dailyDetailDialog: boolean` — 弹窗显示状态
- `expandedDates: Set<string>` — 当前展开的日期集合

## 数据结构

### 前端类型定义

```typescript
export interface DailyPosition {
  ts_code: string
  stock_name: string
  buy_date: string
  buy_price: number
  current_price: number
  shares: number
  fee: number
  cost_basis: number
  market_value: number
  unrealized_pnl: number
  unrealized_pnl_pct: number
  hold_days: number
  entry_score: number
}

export interface DailyTrade {
  ts_code: string
  stock_name: string
  action: string
  filled_price: number
  shares: number
  fee: number
  reason: string
  pnl_amount?: number
  pnl_pct?: number
}

export interface DailyDetail {
  date: string
  cash: number
  total_market_value: number
  total_value: number
  baseline_value: number
  day_return: number
  cml_return: number
  baseline_cml_return: number
  positions: DailyPosition[]
  trades: DailyTrade[]
}

export interface DailyDetailResponse {
  items: DailyDetail[]
}
```

### 后端返回结构

使用 Pydantic 模型定义响应：

```python
class DailyPositionOut(BaseModel):
    ts_code: str
    stock_name: str
    buy_date: str
    buy_price: float
    current_price: float
    shares: int
    fee: float
    cost_basis: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    hold_days: int
    entry_score: float

class DailyTradeOut(BaseModel):
    ts_code: str
    stock_name: str
    action: str
    filled_price: float
    shares: int
    fee: float
    reason: Optional[str]
    pnl_amount: Optional[float]
    pnl_pct: Optional[float]

class DailyDetailOut(BaseModel):
    date: str
    cash: float
    total_market_value: float
    total_value: float
    baseline_value: float
    day_return: float
    cml_return: float
    baseline_cml_return: float
    positions: List[DailyPositionOut]
    trades: List[DailyTradeOut]

class DailyDetailResponse(BaseModel):
    items: List[DailyDetailOut]
```

## 影响范围

### 后端文件

| 文件 | 改动 |
|------|------|
| `constants.py` | 新增 `SELL_REASON_*` 常量 |
| `strategy/multi_stock_strategy.py` | `_check_sell` 返回值改为 `Tuple[bool, str]`；`make_decisions` 中为卖出 `PendingOrder` 设置 `reason`（引用常量） |
| `execution/pipeline.py` | 满仓强制卖出的 `reason` 字段改用常量 |
| `api/routers/backtest_records.py` | 新增 `GET /{result_id}/daily-details` 端点 |

### 前端文件

| 文件 | 改动 |
|------|------|
| `views/BacktestRecordsView.vue` | 移除 `tradesDialog` 及相关逻辑；新增 `dailyDetailDialog` 弹窗和展开卡片布局；「交易」按钮改为「每日」 |
| `api/backtestRecord.ts` | 新增 `getDailyDetails` API 调用 |

## 未涉及范围

- 不修改 `PendingOrder` 或 `ExecutionTrade` 的数据模型（`reason` 字段已存在）
- 不修改现有的回测概览、盈亏分析、交易优化页面
- 不修改实盘建议模块的代码