# 仓位管理重构 & 实盘建议卖出集成

## 概述

对仓位管理功能进行重构，移除所有资金相关字段和逻辑，仅保留股票持仓管理；同时在实盘建议流程中，加载实际持仓并通过策略判断卖出信号。

## 涉及模块

- `backend/src/trade_alpha/dao/live_portfolio.py` — 数据模型
- `backend/src/trade_alpha/api/routers/live_portfolio.py` — API 端点
- `frontend/src/api/livePortfolio.ts` — 前端 API 层
- `frontend/src/views/LivePositionManageView.vue` — 前端页面
- `backend/src/trade_alpha/execution/pipeline.py` — 流水线
- `backend/src/trade_alpha/strategy/multi_stock_strategy.py` — 策略
- `backend/src/trade_alpha/dao/live_order_suggestion.py` — 建议数据模型（无变化）
- `backend/src/trade_alpha/api/routers/live_suggestion.py` — 建议 API（无变化）

## 1. 仓位管理重构

### 1.1 数据模型

`LivePortfolio` Document 去掉所有资金和费率字段，只保留持仓列表：

```python
# Before
class LivePortfolio(Document):
    total_cash: float = 0.0
    buy_fee_rate: float = 0.0003
    sell_fee_rate: float = 0.0003
    stamp_tax_rate: float = 0.001
    min_fee: float = 5.0
    positions: List[LivePositionEmbed] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

# After
class LivePortfolio(Document):
    positions: List[LivePositionEmbed] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
```

`LivePositionEmbed` 保持不变：
```python
class LivePositionEmbed(BaseModel):
    id: str
    ts_code: str
    stock_name: str
    shares: int
    cost_price: float
    total_cost: float
    created_at: datetime
    updated_at: datetime
```

### 1.2 API 端点

移除的资金相关端点：
- `POST /init` — 初始化组合
- `PUT /cash` — 更新现金
- `PUT /settings` — 更新费率

保留的持仓管理端点（不再调现金）：

| 端点 | 变化 |
|------|------|
| `GET /` | 返回纯持仓组合 |
| `POST /positions` | 不再检查/扣除现金，不再计算手续费 |
| `PUT /positions/{id}` | 不再调现金 |
| `DELETE /positions/{id}` | 不再退现金到现金 |
| `GET /stocks/search` | 不变 |

### 1.3 前端页面

移除的 UI 元素：
- 顶部资金摘要卡片（总现金、总市值、总资产）
- 账户设置按钮和弹窗（买入费率、卖出费率、印花税率、最低佣金）
- 修改现金弹窗

保留的 UI 元素：
- 持仓列表（股票名称、代码、股数、成本价、总成本、操作）
- 新增持仓弹窗（搜索股票、股数、买入单价）
- 编辑持仓弹窗（股数、成本价）
- 删除确认弹窗

## 2. 实盘建议卖出集成

### 2.1 核心思路

在 `run_live_suggestion` 中对每个目标日期，从 `LivePortfolio` 加载实际持仓注入策略，策略通过新增 `suggestion_mode` 参数跳过 `reserve_funds` 买入股数计算。

### 2.2 策略层

`MultiStockStrategy.make_decisions` 新增参数：

```python
async def make_decisions(
    self,
    scored_stocks: List[ScoredStock],
    portfolio: PortfolioManager,
    trade_date: str,
    close_prices: Optional[Dict[str, float]] = None,
    suggestion_mode: bool = False,  # NEW
) -> List[PendingOrder]:
```

在 `suggestion_mode=True` 时的行为：

**卖出逻辑不变：**
- `_check_sell` 照常判断，使用相同的策略参数（sell_threshold, hold_days, max_hold_days, stop_loss_pct, sell_rank_n, hold_score_threshold）
- 生成 `PendingOrder` 时 `order_shares = -pos.shares`（表示清仓），`reason` 沿用现有卖出的原因字符串

**买入逻辑修改：**
- 跳过 `portfolio.reserve_funds()`
- 直接取 `top_stocks` 中排在前 `max_positions` 的、未被排除的、未在卖出列表中的
- 生成 `PendingOrder`，`order_shares = 0`，`reason = "buy_suggestion"`
- 买入阈值 `buy_threshold` 仍然生效（低于阈值的不建议买入）

### 2.3 流水线层

`ExecutionPipeline.run_live_suggestion` 修改：

```python
# 每个 target_date 时：
# 1. 加载实际持仓
portfolio_doc = await LivePortfolio.find_one()
real_positions = {}
if portfolio_doc:
    for pos in portfolio_doc.positions:
        real_positions[pos.ts_code] = PositionEmbed(
            ts_code=pos.ts_code,
            stock_name=pos.stock_name,
            buy_date="",
            buy_price=pos.cost_price,
            shares=pos.shares,
            fee=0.0,
            entry_score=0,
            entry_3d_prob=0, entry_5d_prob=0,
            entry_10d_prob=0, entry_20d_prob=0,
            hold_days=0,  # 每个 target date hold_days 重新开始
        )

# 2. 重置 portfolio 并注入实际持仓
self.portfolio.reset()
self.portfolio.positions = real_positions
self.portfolio._cash_available = 0  # 无现金

# 3. 调用策略（suggestion_mode=True）
pending_orders = await self.strategy.make_decisions(
    scored_stocks=scored,
    portfolio=self.portfolio,
    trade_date=date,
    close_prices=close_prices,
    suggestion_mode=True,
)
```

注意：`hold_days` 在每个 target date 重新从 0 开始，这意味着 `min_hold_days` 和 `max_hold_days` 在建议模式下可能意义不大（参考阅读即可）。卖出判断主要依赖 `sell_threshold`、`stop_loss_pct` 和 `hold_score_threshold`。

### 2.4 建议结果保存

`LiveOrderSuggestion` 的 `reason` 字段区分买卖：
- `reason` 以 `"buy_suggestion"` → 买入建议
- `reason` 以现有 `SELL_REASON_*` 开头 → 卖出建议（`score_below`, `max_hold_days`, `stop_loss`, `hold_score_low`）

### 2.5 前端展示

「每日建议」页面详情弹窗增加「类型」列，标识买入/卖出建议。

## 3. 测试

### 后端集成测试
- 重建 `test_46_live_portfolio.py` 验证纯持仓 CRUD（去掉现金相关断言）
- `test_65_live_suggestion.py` 中验证 `suggestion_mode=True` 时生成正确的买入/卖出建议

### 前端 E2E
- 更新 `test_position_manage_page.py` 去掉现金相关断言
- 可选：新增卖出建议展示的验证

## 4. 影响范围

| 文件 | 改动量 |
|------|--------|
| `live_portfolio.py` (dao) | ~15 行（去字段） |
| `live_portfolio.py` (api) | ~40 行（去端点、简化逻辑） |
| `livePortfolio.ts` | ~20 行（去 API 调用） |
| `LivePositionManageView.vue` | ~150 行（去资金 UI） |
| `multi_stock_strategy.py` | ~15 行（加 suggestion_mode） |
| `pipeline.py` | ~30 行（加载持仓、传参数） |
| 文档 | 更新 database-schema + api 文档 |

## 5. 未涉及

- `LiveOrderSuggestion` 数据模型不变
- `LiveDailyStockScore` 数据模型不变
- 建议 API 端点和前端「每日建议」页面不重构，仅增加类型展示
- 定时任务/调度器不涉及