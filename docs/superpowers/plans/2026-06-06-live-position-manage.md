# 仓位管理页面 — 实施计划

## 概述

在实盘模块新增"仓位管理"子页面，作为菜单第一项。支持手动管理持仓和现金，费率设置，按成本价自动同步现金。

## 执行步骤

### 第一步：后端 DAO

新建 `backend/src/trade_alpha/dao/live_portfolio.py`：

- `LivePositionEmbed(BaseModel)` — 嵌入子文档
  - `id: str` (内部用 str(uuid) 或递增)
  - `ts_code: str`
  - `stock_name: str`
  - `shares: int`
  - `cost_price: float` — 加权平均成本
  - `total_cost: float` — shares × cost_price
  - `created_at: datetime`
  - `updated_at: datetime`

- `LivePortfolio(Document)` — 主文档，集合名 `live_portfolio`
  - `total_cash: float` = 0.0
  - `buy_fee_rate: float` = 0.0003
  - `sell_fee_rate: float` = 0.0003
  - `stamp_tax_rate: float` = 0.001
  - `min_fee: float` = 5.0
  - `positions: List[LivePositionEmbed]` = []
  - `created_at: datetime`
  - `updated_at: datetime`
  - 索引：无特殊要求，全局仅 1 条记录

DAO 层方法（初始化、增删改持仓、更新现金、更新费率、获取组合），所有错误向上抛。

### 第二步：后端 API

新建 `backend/src/trade_alpha/api/routers/live_portfolio.py`，前缀 `/live-portfolio`：

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/` | 获取 portfolio（现金 + 持仓 + 费率） |
| POST | `/init` | 初始化 portfolio（指定初始现金） |
| PUT | `/cash` | 更新现金（请求体 `{total_cash}`） |
| PUT | `/settings` | 更新费率（请求体 `{buy_fee_rate, sell_fee_rate, stamp_tax_rate, min_fee}`） |
| POST | `/positions` | 新增持仓（请求体 `{ts_code, stock_name, shares, price}`），自动计算加权平均和现金变动 |
| PUT | `/positions/{id}` | 修改持仓（请求体 `{shares?, cost_price?}`），同步现金 |
| DELETE | `/positions/{id}` | 删除持仓，按 total_cost 加回现金 |
| GET | `/stocks/search?q=` | 搜索股票，从 StockList 集合模糊匹配 ts_code 或 name |

关键逻辑：
- **新增持仓**：若已有同股票 -> 加权平均成本；否则新建。现金减少 `shares × price + max(shares × price × buy_fee_rate, min_fee)`
- **删除持仓**：现金增加 `position.total_cost`（按成本价，不含卖出费用）
- **修改持仓**：新旧总成本差额同步现金

在 `backend/src/trade_alpha/api/routers/__init__.py` 中注册 router。

### 第三步：前端 API 模块

新建 `frontend/src/api/livePortfolio.ts`，包含：

- `getPortfolio()` — GET `/live-portfolio/`
- `initPortfolio(cash)` — POST `/live-portfolio/init`
- `updateCash(total_cash)` — PUT `/live-portfolio/cash`
- `updateSettings(settings)` — PUT `/live-portfolio/settings`
- `addPosition(data)` — POST `/live-portfolio/positions`
- `updatePosition(id, data)` — PUT `/live-portfolio/positions/{id}`
- `deletePosition(id)` — DELETE `/live-portfolio/positions/{id}`
- `searchStocks(q)` — GET `/live-portfolio/stocks/search?q=`

### 第四步：前端页面

新建 `frontend/src/views/LivePositionManageView.vue`：

- **概览卡**（顶部）：
  - 左：总现金、总市值（成本）、总资产、持仓数
  - 右："账户设置"按钮（打开费率编辑弹窗）
  - 点击现金可编辑（行内或弹窗）

- **持仓表格**：
  - 列：股票名称、代码、股数、成本价、总成本、市值（按成本价 = 总成本）、操作
  - 操作列：编辑（修改股数/成本价）、删除
  - 顶部"新增持仓"按钮

- **新增/编辑弹窗**：
  - 股票搜索框（v-autocomplete，实时从后端搜索 StockList）
  - 股数输入
  - 单价输入
  - 自动显示：小计、买入手续费、现金变化
  - 编辑模式：可修改股数和成本价

- **账户设置弹窗**：
  - 买入费率、卖出费率、印花税率、最低佣金
  - 保存后更新

### 第五步：路由 & 菜单

- `frontend/src/router/index.ts`：在 `/live-suggestion` 下新增 `positions` 路由（redirect 改为 `/live-suggestion/positions`）
- `frontend/src/components/AppLayout.vue`：`liveSuggestionItems` 第一位插入仓位管理

### 第六步：验证

- 后端 ruff lint
- 前端 `vue-tsc --noEmit` + `npm run build`
- 启动前后端，手动验证 CRUD 流程