# PortfolioManager 重构设计

## 背景

`execution/pipeline.py`（641 行）承担了过多职责：回测编排、评分筛选、资金管理、持仓更新、费用计算、快照生成、指标计算等。多处直接操作 `self.cash` 和 `self.positions` 散落在不同方法中，逻辑耦合度高，修改风险大。

本次重构将**资金、持仓、费用计算**相关的职责抽取到独立的 `PortfolioManager` 类中，pipeline 只保留编排职责。

## 范围

**严格界定**：只抽取资金、持仓、费用计算。

### 移入 PortfolioManager

| 职责 | 说明 |
|------|------|
| 现金余额跟踪 | `cash` 状态持有与更新 |
| 持仓跟踪 | `positions` 状态持有与 CRUD |
| 费用计算 | 买入/卖出手续费、印花税 |
| 资金运算 | 总资产、持仓市值、单股上限、剩余容量 |

### 留在 Pipeline

| 职责 | 说明 |
|------|------|
| 回测编排 | `_run_daily_loop` 循环控制 |
| 评分/排名/筛选 | `_predict`、`_smooth_scores`、`_apply_momentum_boost`、`_filter_explosions` |
| 订单 OHLC 撮合 | 已在 `PositionManager.settle_orders` 中 |
| 成交记录数据库写入 | `ExecutionTrade` 插入 |
| 快照数据库写入 | `ExecutionDailySnapshot` 插入 |
| PnL 计算 | 持仓卖出时的盈亏计算 |
| 基线跟踪 | `_track_baseline`、`_init_baseline` |
| 指标计算 | `_calc_max_drawdown`、`_calc_win_rate` |
| 实盘 | `run_live` 逻辑 |

## 文件位置

```
backend/src/trade_alpha/execution/
├── __init__.py
├── data_loader.py
├── pipeline.py          # 精简编排职责
├── portfolio.py          ← 新增
├── schemas.py
└── service.py
```

## PortfolioManager API

```python
class PortfolioManager:
    def __init__(
        self,
        account_config: AccountConfig,
        initial_capital: float = 100000.0,
        max_position_pct: float = 0.3,
    ):
        self.account_config = account_config
        self.cash = initial_capital
        self.positions: Dict[str, PositionEmbed] = {}
        self.max_position_pct = max_position_pct
```

### 持仓管理

```python
def add_or_merge_position(
    self,
    ts_code: str,
    stock_name: str,
    shares: int,
    price: float,
    fee: float,
    entry_score: float = 0,
    entry_3d_prob: float = 0,
    entry_5d_prob: float = 0,
) -> None:
    """新增或合并加仓。

    已持有 → 累加股数、加权均价、累加费用、保留原买入日期和评分。
    新持有 → 创建新 PositionEmbed。
    """

def remove_position(self, ts_code: str) -> None:
    """卖出后移除持仓。"""
```

### 资金与费用

```python
def update_cash(self, amount: float) -> None:
    """更新现金余额。正数=收入，负数=支出。"""

def calc_buy_fee(self, cost: float) -> float:
    """max(cost * buy_fee_rate, min_fee)"""

def calc_sell_fee(self, cost: float) -> float:
    """max(cost * sell_fee_rate, min_fee)"""

def calc_stamp_tax(self, cost: float) -> float:
    """cost * stamp_tax_rate"""
```

### 资金运算

```python
def get_total_value(self, close_prices: Dict[str, float]) -> float:
    """总资产 = cash + 持仓市值"""

def get_market_value(self, close_prices: Dict[str, float]) -> float:
    """持仓市值 = sum(shares * price)"""

def get_position_value(self, ts_code: str, close_price: float) -> float:
    """单股持仓市值 = shares * close_price"""

def get_max_allowed_per_stock(self) -> float:
    """单股上限 = total_value * max_position_pct"""

def get_remaining_capacity(self, ts_code: str, close_price: float) -> float:
    """剩余容量 = max_allowed - pos_value"""
```

## Pipeline 改造点

### 初始化

```python
# 改前
self.cash = initial_capital
self.positions: Dict[str, PositionEmbed] = {}

# 改后
self.portfolio = PortfolioManager(
    account_config=self.account_config,
    initial_capital=initial_capital,
    max_position_pct=getattr(self.strategy_config, 'max_position_pct', 0.3),
)
```

### `_settle_orders` 中的持仓和资金操作

```python
# 改前
for t in filled_trades:
    if t.action == "sell":
        self.positions.pop(t.ts_code, None)
    elif t.action == "buy":
        existing = self.positions.get(t.ts_code)
        if existing:
            total_shares = existing.shares + t.shares
            ...
        else:
            self.positions[t.ts_code] = PositionEmbed(...)
self.cash += net_cash_change

# 改后
for t in filled_trades:
    if t.action == "sell":
        self.portfolio.remove_position(t.ts_code)
    elif t.action == "buy":
        self.portfolio.add_or_merge_position(
            ts_code=t.ts_code,
            stock_name=name_map.get(t.ts_code, ""),
            shares=t.shares,
            price=t.filled_price,
            fee=t.fee,
            entry_score=t.entry_score or 0,
            entry_3d_prob=t.up_prob_3d or 0,
            entry_5d_prob=t.up_prob_5d or 0,
        )
self.portfolio.update_cash(net_cash_change)
```

### 费用计算

```python
# pipeline 中 fee 相关的 4 处改为 portfolio.calc_*_fee()
# 例如 pipeline._make_orders 中的
buy_order.order_price * buy_order.order_shares * self.account_config.buy_fee_rate
# 改为
self.portfolio.calc_buy_fee(total_cost)
```

### `_save_snapshot` 中的资金运算

```python
# 改前
total_market_value = sum(...)
total_value = self.cash + total_market_value

# 改后
total_market_value = self.portfolio.get_market_value(close_prices)
total_value = self.portfolio.get_total_value(close_prices)
```

### 策略接口传参

```python
# 改前
pending_orders = await self.strategy.make_decisions(
    scored_stocks=scored,
    current_positions=self.positions,
    cash=self.cash,
    ...
)

# 改后（接口不变）
pending_orders = await self.strategy.make_decisions(
    scored_stocks=scored,
    current_positions=self.portfolio.positions,
    cash=self.portfolio.cash,
    ...
)
```

## 测试

- 不需要新增集成测试，现有的 87 个集成测试全部通过即表明重构正确
- 重构完成后运行全量集成测试验证
- 运行前端 E2E 测试验证接口兼容性