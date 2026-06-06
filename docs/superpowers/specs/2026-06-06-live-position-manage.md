# 仓位管理页面 — 设计文档

## 1. 概述

在实盘模块中增加"仓位管理"页面，作为实盘菜单的第一个子菜单。用户可手动编辑持有的股票和现金，系统按费率自动计算手续费并同步更新现金。当前版本不参与自动交易。

## 2. 数据模型

### 2.1 LivePortfolio（主文档）

集合名：`live_portfolio`，全局只有 1 条记录。

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `total_cash` | float | 0.0 | 当前可用现金 |
| `buy_fee_rate` | float | 0.0003 | 买入费率（万分之三） |
| `sell_fee_rate` | float | 0.0003 | 卖出费率（万分之三） |
| `stamp_tax_rate` | float | 0.001 | 印花税率（千分之一） |
| `min_fee` | float | 5.0 | 最低佣金（元） |
| `positions` | List[LivePositionEmbed] | [] | 持仓列表（嵌入） |
| `created_at` | datetime | now | 创建时间 |
| `updated_at` | datetime | now | 更新时间 |

### 2.2 LivePositionEmbed（嵌入子文档）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | str | 唯一标识（uuid 或时间戳） |
| `ts_code` | str | 股票代码 |
| `stock_name` | str | 股票名称 |
| `shares` | int | 持有股数 |
| `cost_price` | float | 加权平均买入成本价 |
| `total_cost` | float | 总成本 = shares × cost_price |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

## 3. 后端 API

前缀：`/api/live-portfolio`

### 3.1 获取组合

```
GET /
Response: { total_cash, buy_fee_rate, sell_fee_rate, stamp_tax_rate, min_fee, positions: [...], created_at, updated_at }
```

首次调用自动初始化（现金 0，默认费率）。

### 3.2 初始化

```
POST /init
Body: { initial_cash: float }
Response: LivePortfolio
```

仅当 portfolio 不存在时有效。

### 3.3 更新现金

```
PUT /cash
Body: { total_cash: float }
Response: LivePortfolio
```

### 3.4 更新费率

```
PUT /settings
Body: { buy_fee_rate?: float, sell_fee_rate?: float, stamp_tax_rate?: float, min_fee?: float }
Response: LivePortfolio
```

### 3.5 新增持仓

```
POST /positions
Body: { ts_code: str, stock_name: str, shares: int, price: float }
Response: LivePortfolio
```

逻辑：
1. 计算买入手续费：`fee = max(shares × price × buy_fee_rate, min_fee)`
2. 检查现金是否充足：`total_cash >= shares × price + fee`
3. 若已有同 `ts_code` 的持仓：
   - 加权平均成本：`new_cost = (old_cost × old_shares + price × new_shares) / (old_shares + new_shares)`
   - 合并股数
4. 若没有则新建持仓
5. 扣除现金：`total_cash -= shares × price + fee`

### 3.6 修改持仓

```
PUT /positions/{id}
Body: { shares?: int, cost_price?: float }
Response: LivePortfolio
```

逻辑：
1. 计算新旧总成本差额：`delta = new_total_cost - old_total_cost`
2. 更新现金：`total_cash -= delta`（若差额为负则增加现金）
3. 更新持仓的股数/成本价

### 3.7 删除持仓

```
DELETE /positions/{id}
Response: LivePortfolio
```

逻辑：
1. 按成本价加回现金：`total_cash += position.total_cost`
2. 移除持仓

### 3.8 搜索股票

```
GET /stocks/search?q={keyword}
Response: [{ ts_code, name, industry, market }]
```

从 `StockList` 集合中模糊匹配 `ts_code` 或 `name`，返回前 20 条。支持中文。

## 4. 前端页面

### 4.1 路由与菜单

```
路由：/live-suggestion/positions
菜单：实盘 → 仓位管理（第一个子菜单）
```

菜单顺序调整：
```
仓位管理  >  实盘管理  >  每日排名  >  实盘记录
```

### 4.2 页面布局

#### 概览卡（顶部）

```
┌──────────────────────────────────────────────────────────┐
│  💰 总现金: ¥100,000    📊 总市值(成本): ¥50,000        │
│  🏦 总资产: ¥150,000    📋 持仓数: 3       [账户设置]   │
└──────────────────────────────────────────────────────────┘
```

- 点击总现金金额可编辑（行内编辑或弹窗）
- 账户设置打开费率配置弹窗

#### 持仓表格

```
┌─ [新增持仓] ────────────────────────────────────────────┐
│ 股票名称 │ 代码  │ 股数  │ 成本价  │ 总成本  │ 操作    │
│─────────┼──────┼──────┼────────┼────────┼─────────│
│ 贵州茅台 │600519│  100 │ 1800.00│180000.0│ ✏️  🗑  │
│ 腾讯控股 │00700 │  500 │ 380.00 │190000.0│ ✏️  🗑  │
└─────────────────────────────────────────────────────────┘
```

- 操作列：编辑（铅笔图标）、删除（垃圾桶图标）
- 删除前确认弹窗

#### 新增/编辑持仓弹窗

```
┌─ 新增持仓 ─────────────────────────────────────┐
│  股票: [搜索框 v-autocomplete]                  │
│  股数: [_________]  买入单价: [_________]       │
│  小计: ¥180,000                                 │
│  买入手续费: ¥5.00                              │
│  现金变化: -¥180,005                            │
│  [取消]  [确认]                                 │
└─────────────────────────────────────────────────┘
```

编辑模式下：
```
┌─ 编辑持仓 (贵州茅台) ───────────────────────────┐
│  股票代码: 600519（只读）                          │
│  股票名称: 贵州茅台（只读）                        │
│  股数: [200]  成本价: [1750.00]                   │
│  原总成本: ¥180,000 → 新总成本: ¥350,000          │
│  现金变化: -¥170,000                              │
│  [取消]  [保存]                                   │
└──────────────────────────────────────────────────┘
```

#### 账户设置弹窗

```
┌─ 账户设置 ───────────────────────────────────────┐
│  买入费率: [0.0003]   万分之三                    │
│  卖出费率: [0.0003]   万分之三                    │
│  印花税率: [0.001]    千分之一                    │
│  最低佣金: [5.00]     元                         │
│  [恢复默认]              [取消]  [保存]           │
└──────────────────────────────────────────────────┘
```

- 恢复默认按钮一键重置为系统默认值

## 5. 文件变更清单

### 后端
| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/src/trade_alpha/dao/live_portfolio.py` | DAO 模型 |
| 新增 | `backend/src/trade_alpha/api/routers/live_portfolio.py` | API 路由 |
| 修改 | `backend/src/trade_alpha/api/routers/__init__.py` | 注册 router |
| 修改 | `backend/src/trade_alpha/dao/__init__.py` | 导出新模型 |

### 前端
| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `frontend/src/api/livePortfolio.ts` | API 接口 |
| 新增 | `frontend/src/views/LivePositionManageView.vue` | 页面组件 |
| 修改 | `frontend/src/router/index.ts` | 新增路由 |
| 修改 | `frontend/src/components/AppLayout.vue` | 新增菜单项 |

## 6. 约束与限制

- 现金不允许为负数（新增/修改持仓时校验）
- 删除持仓时为"完全删除"，不支持部分卖出（未来迭代可加）
- 费率修改不影响已有持仓的成本计算，仅影响后续交易
- 搜索股票从已有的 `StockList` 集合查询，依赖股票列表已同步
- 手动"修改持仓"的现金变化按总成本差额计算，不含手续费（视为调整既有持仓的成本）