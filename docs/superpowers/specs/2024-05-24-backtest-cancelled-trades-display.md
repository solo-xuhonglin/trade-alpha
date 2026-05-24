# 回测交易记录显示未成交委托单

## 问题

T+1 结算改造后，未成交的委托单也会记录到 `ExecutionTrade` 表（`status="cancelled"`）。但前端交易记录弹窗和交易记录页面没有区分已成交和未成交，未成交的行显示 price=0、shares=0 等无意义的值。

## 解决方案

### 后端改动

两个 API 响应增加 `status`、`ts_code`、`reason` 字段：

1. **`GET /backtests/{result_id}/trades`**（回测记录弹窗）
2. **`GET /backtests/trades`**（交易记录页面）

```python
# 在 items 的 dict 中增加
{
    "status": trade.status,        # "filled" or "cancelled"
    "ts_code": trade.ts_code,      # 股票代码
    "reason": trade.reason,        # 成交原因或 "cancelled"
}
```

### 前端改动

#### 1. TypeScript 接口

两个文件的 `Trade` 接口增加 `status` 字段：
- `frontend/src/api/backtestRecord.ts`（回测记录弹窗）
- `frontend/src/api/trade.ts`（交易记录页面）

```typescript
export interface Trade {
  // ... 现有字段
  status: string       // "filled" or "cancelled"
  ts_code?: string     // 股票代码（回测弹窗新增）
  reason?: string      // 原因
}
```

#### 2. 回测记录弹窗（BacktestRecordsView.vue）

`viewTrades` 弹窗的表头新增列：

| 列标题 | key | 说明 |
|--------|-----|------|
| 股票代码 | ts_code | 新增 |
| 日期 | trade_date | 已有 |
| 操作 | action | 已有 |
| 状态 | status | 新增，"成交"/"未成交" |
| 价格 | price | 已有，未成交显示 `-` |
| 数量 | shares | 已有，未成交显示 `-` |
| 手续费 | fee | 已有，未成交显示 `-` |
| 现金 | cash_after | 已有 |

状态列样式：
- `filled`：绿色 tag "成交"
- `cancelled`：灰色 tag "未成交"，整行文字变灰/斜体

价格/数量列：`status === "cancelled"` 时显示 `-`

#### 3. 交易记录页面（TradesView.vue）

表头新增：
| 列标题 | key |
|--------|-----|
| 股票代码 | ts_code |
| 状态 | status |

新增状态过滤：
- 在过滤器栏增加一个 `v-select`，选项为：全部 / 已成交 / 未成交
- 后端过滤或前端过滤均可（前端过滤更简单）

样式同弹窗。

## 实现步骤

1. 后端 API 增加 `status`、`ts_code`、`reason` 字段
2. 前端 TypeScript 接口增加 `status` 字段
3. 修改回测记录弹窗的交易列表
4. 修改交易记录页面的表格和过滤器
