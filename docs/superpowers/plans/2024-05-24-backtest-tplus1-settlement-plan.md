# 回测 T+1 结算实施计划

> **给执行者的说明：** 请使用 subagent-driven-development（推荐）或 executing-plans 技能按任务逐步实施。步骤使用复选框（`- [ ]`）跟踪。

**目标：** 将回测委托单结算从 T+0（当日收盘价）改为 T+1（次日 OHLC 撮合）

**架构：** 修改 `PositionManager.settle_orders` 使其接受 OHLC 数据并实现限价单撮合。在 `ExecutionPipeline` 中添加 `pending_orders` 队列。每日循环先结算 T-1 的委托单，再生成新的 T+1 委托单。每个委托单产生一条 `ExecutionTrade` 记录，`status="filled"`（成交）或 `status="cancelled"`（未成交）。

**技术栈：** Python 3.14+, Beanie ODM, MongoDB, asyncio

---

### Task 1: 给 ExecutionTrade 模型添加 status 字段

**涉及文件：**
- 修改：`backend/src/trade_alpha/dao/execution_trade.py`

- [ ] **Step 1: 添加 status 字段**

```python
# backend/src/trade_alpha/dao/execution_trade.py
# 在 mode 字段后面添加（约第25行）
status: str = Field(default="filled")  # "filled" or "cancelled"
```

- [ ] **Step 2: 验证导入正常**

```bash
cd d:/projects/trade-alpha/backend && python -c "from trade_alpha.dao.execution_trade import ExecutionTrade; print('OK')"
```
预期输出：`OK`

- [ ] **Step 3: 提交**

```bash
cd d:/projects/trade-alpha
git add backend/src/trade_alpha/dao/execution_trade.py
git commit -m "feat: add status field to ExecutionTrade model"
```

---

### Task 2: 修改 PositionManager.settle_orders

**涉及文件：**
- 修改：`backend/src/trade_alpha/strategy/base.py:48-88`

当前 `settle_orders` 签名：
```python
async def settle_orders(
    self,
    orders: List[PendingOrder],
    date: str,
    close_prices: Dict[str, float],
    backtest_id: Optional[PydanticObjectId] = None,
) -> Tuple[List[ExecutionTrade], float]:
```

新签名：
```python
async def settle_orders(
    self,
    orders: List[PendingOrder],
    date: str,
    open_prices: Dict[str, float],
    high_prices: Dict[str, float],
    low_prices: Dict[str, float],
    backtest_id: Optional[PydanticObjectId] = None,
) -> Tuple[List[ExecutionTrade], List[PendingOrder], float]:
```

参数说明：
- `open_prices`/`high_prices`/`low_prices`：结算日 `{ts_code: price}` 字典
- 返回 `(filled_trades, unfilled_orders, net_cash_change)`

实现要点：
- 对每个委托单调用 `match_order(order, open, high, low)` 确定成交价
- 成交：创建 `ExecutionTrade(status="filled")`，按之前逻辑计算费用
- 未成交：加入 unfilled_orders 列表返回

- [ ] **Step 1: 给 PositionManager 添加 match_order 静态方法**

```python
@staticmethod
def match_order(order: PendingOrder, open_px: float, high_px: float, low_px: float) -> Optional[float]:
    """Match a pending order against next day's OHLC. Returns matched price or None."""
    if order.order_shares > 0:  # Buy
        if order.order_price >= open_px:
            return open_px
        if high_px >= order.order_price:
            return order.order_price
        return None
    else:  # Sell
        if order.order_price <= open_px:
            return open_px
        if low_px <= order.order_price:
            return order.order_price
        return None
```

- [ ] **Step 2: 重写 settle_orders 方法**

删除原 `settle_orders` 方法（第48-88行），替换为：

```python
async def settle_orders(
    self,
    orders: List[PendingOrder],
    date: str,
    open_prices: Dict[str, float],
    high_prices: Dict[str, float],
    low_prices: Dict[str, float],
    backtest_id: Optional[PydanticObjectId] = None,
) -> Tuple[List[ExecutionTrade], List[PendingOrder], float]:
    """Settle pending orders using T+1 OHLC matching."""
    filled_trades: List[ExecutionTrade] = []
    unfilled_orders: List[PendingOrder] = []
    net_cash_change = 0.0

    for order in orders:
        open_px = open_prices.get(order.ts_code)
        high_px = high_prices.get(order.ts_code)
        low_px = low_prices.get(order.ts_code)
        if open_px is None or high_px is None or low_px is None:
            unfilled_orders.append(order)
            continue

        matched_price = self.match_order(order, open_px, high_px, low_px)
        if matched_price is None:
            unfilled_orders.append(order)
            continue

        shares = abs(order.order_shares)
        action = "buy" if order.order_shares > 0 else "sell"

        if action == "buy":
            fee = max(matched_price * shares * self.account_config.buy_fee_rate, self.account_config.min_fee)
            cash_after = -matched_price * shares - fee
        else:
            fee = max(matched_price * shares * self.account_config.sell_fee_rate, self.account_config.min_fee)
            stamp_tax = matched_price * shares * self.account_config.stamp_tax_rate
            cash_after = matched_price * shares - fee - stamp_tax

        net_cash_change += cash_after
        filled_trades.append(ExecutionTrade(
            backtest_id=backtest_id,
            ts_code=order.ts_code,
            trade_date=date,
            action=action,
            price=matched_price,
            shares=shares if action == "buy" else -shares,
            fee=fee,
            cash_after=cash_after,
            status="filled",
            reason=f"rank_{action}",
            entry_score=order.score,
            up_prob_3d=order.up_prob_3d,
            up_prob_5d=order.up_prob_5d,
        ))

    return filled_trades, unfilled_orders, net_cash_change
```

- [ ] **Step 3: 运行单元测试确认没有破坏现有功能**

```bash
cd d:/projects/trade-alpha/backend && python -m pytest tests/trade_alpha/unit/ -v --timeout=30 2>&1 | tail -5
```
预期：所有测试通过（如果测试引用了旧的 settle_orders 签名，可能会有失败）

- [ ] **Step 4: 提交**

```bash
cd d:/projects/trade-alpha
git add backend/src/trade_alpha/strategy/base.py
git commit -m "feat: update settle_orders with OHLC matching for T+1 settlement"
```

---

### Task 3: 更新 pipeline run_backtest 实现 T+1 结算

**涉及文件：**
- 修改：`backend/src/trade_alpha/execution/pipeline.py`

修改内容：
1. 在 `__init__` 中添加 `self.pending_orders: List[PendingOrder] = []`（第83行后面）
2. 修改每日循环（第210-313行）实现 T+1 结算流程

- [ ] **Step 1: 在 __init__ 中添加 pending_orders**

在第83行 `self.prev_total_value: Optional[float] = None` 后面添加：
```python
self.pending_orders: List[PendingOrder] = []
```

- [ ] **Step 2: 替换每日循环的结算逻辑**

原结算逻辑（约第210-280行）：
```python
day_df = await self.data_loader.load_day_data(date, ts_codes)
# ...跳过检查...
close_prices = dict(zip(day_df["ts_code"], day_df["close"]))
# ...
pred_results = await self.predictor.predict_batch_with_history(day_df, ts_codes, date)
# ...scored stocks...
pending_orders = await self.strategy.make_decisions(...)
if pending_orders:
    trades, net_cash = await self.strategy.settle_orders(
        orders=pending_orders,
        date=date,
        close_prices=close_prices,
        backtest_id=backtest_id,
    )
    self.cash += net_cash
    total_trades += len(trades)
    for t in trades:
        total_fees += t.fee
        if t.action == "sell":
            total_fees += abs(t.shares) * t.price * self.account_config.stamp_tax_rate
    
    await ExecutionTrade.insert_many(trades)

    for t in trades:
        if t.action == "sell":
            self.positions.pop(t.ts_code, None)
        elif t.action == "buy":
            self.positions[t.ts_code] = PositionEmbed(...)
```

替换为 T+1 流程：

```python
day_df = await self.data_loader.load_day_data(date, ts_codes)
if day_df.empty:
    logger.debug(f"No day data for {date}, skipping")
    date = _next_date(date)
    continue

open_prices = dict(zip(day_df["ts_code"], day_df["open"]))
high_prices = dict(zip(day_df["ts_code"], day_df["high"]))
low_prices = dict(zip(day_df["ts_code"], day_df["low"]))
close_prices = dict(zip(day_df["ts_code"], day_df["close"]))
if not close_prices:
    date = _next_date(date)
    continue

# Step 1: Settle T-1 pending orders with T's OHLC
if self.pending_orders:
    filled_trades, unfilled_orders, net_cash = await self.strategy.settle_orders(
        orders=self.pending_orders,
        date=date,
        open_prices=open_prices,
        high_prices=high_prices,
        low_prices=low_prices,
        backtest_id=backtest_id,
    )
    self.cash += net_cash
    total_trades += len(filled_trades)

    # Record all orders (filled + cancelled) as ExecutionTrade
    all_trades = filled_trades + [
        ExecutionTrade(
            backtest_id=backtest_id,
            ts_code=order.ts_code,
            trade_date=date,
            action="buy" if order.order_shares > 0 else "sell",
            price=0.0,
            shares=0,
            fee=0.0,
            cash_after=0.0,
            status="cancelled",
            reason="cancelled",
            entry_score=order.score,
            up_prob_3d=order.up_prob_3d,
            up_prob_5d=order.up_prob_5d,
        )
        for order in unfilled_orders
    ]
    await ExecutionTrade.insert_many(all_trades)

    for t in filled_trades:
        total_fees += t.fee
        if t.action == "sell":
            total_fees += abs(t.shares) * t.price * self.account_config.stamp_tax_rate

    for t in filled_trades:
        if t.action == "sell":
            self.positions.pop(t.ts_code, None)
        elif t.action == "buy":
            self.positions[t.ts_code] = PositionEmbed(
                ts_code=t.ts_code,
                stock_name=universe.get(t.ts_code, ""),
                buy_date=date,
                buy_price=t.price,
                shares=t.shares,
                fee=t.fee,
                entry_score=t.entry_score or 0,
                entry_3d_prob=t.up_prob_3d or 0,
                entry_5d_prob=t.up_prob_5d or 0,
                hold_days=0,
            )

    self.pending_orders.clear()

# Step 2: Predict T+1 signals
pred_results = await self.predictor.predict_batch_with_history(
    day_df, ts_codes, date
)
if not pred_results:
    logger.debug(f"No predictions for {date}, skipping")
    date = _next_date(date)
    continue

scored = [
    ScoredStock(
        ts_code=ts_code,
        stock_name=universe.get(ts_code, ""),
        close=r["close"],
        up_prob_3d=r["up_prob_3d"],
        up_prob_5d=r["up_prob_5d"],
        score=r["score"],
    )
    for ts_code, r in pred_results.items()
]

if self.single_stock_ts_code:
    scored = [s for s in scored if s.ts_code == self.single_stock_ts_code]

# Step 3: Generate new pending orders for T+1
pending_orders = await self.strategy.make_decisions(
    scored_stocks=scored,
    current_positions=self.positions,
    cash=self.cash,
    trade_date=date,
    close_prices=close_prices,
)

for order in pending_orders:
    order.trade_date = date
    order.settle_date = _next_date(date)

self.pending_orders = pending_orders
```

每日快照部分（当前第299-313行）保持不变。

- [ ] **Step 3: 提交**

```bash
cd d:/projects/trade-alpha
git add backend/src/trade_alpha/execution/pipeline.py
git commit -m "feat: implement T+1 settlement in backtest pipeline"
```

---

### Task 4: 编写 match_order 的单元测试

**涉及文件：**
- 创建：`backend/tests/trade_alpha/unit/strategy/test_order_matching.py`

```python
"""Tests for T+1 order matching logic."""
from typing import Optional
from trade_alpha.schemas import PendingOrder


class FakePositionManager:
    """Minimal stand-in for PositionManager.match_order."""

    @staticmethod
    def match_order(order: PendingOrder, open_px: float, high_px: float, low_px: float) -> Optional[float]:
        if order.order_shares > 0:  # Buy
            if order.order_price >= open_px:
                return open_px
            if high_px >= order.order_price:
                return order.order_price
            return None
        else:  # Sell
            if order.order_price <= open_px:
                return open_px
            if low_px <= order.order_price:
                return order.order_price
            return None


def test_buy_bid_above_open_fills_at_open():
    """Buy: bid price >= open -> filled at open."""
    order = PendingOrder(ts_code="000001.SZ", stock_name="Test", order_price=10.5, order_shares=100,
                          score=0.8, up_prob_3d=0.6, up_prob_5d=0.55, trade_date="20250102", settle_date="20250103")
    result = FakePositionManager.match_order(order, open_px=10.2, high_px=10.8, low_px=10.1)
    assert result == 10.2


def test_buy_bid_below_open_high_reaches_bid():
    """Buy: bid < open, high >= bid -> filled at bid."""
    order = PendingOrder(ts_code="000001.SZ", stock_name="Test", order_price=10.0, order_shares=100,
                          score=0.8, up_prob_3d=0.6, up_prob_5d=0.55, trade_date="20250102", settle_date="20250103")
    result = FakePositionManager.match_order(order, open_px=10.5, high_px=10.3, low_px=9.8)
    assert result == 10.0


def test_buy_bid_below_open_high_never_reaches():
    """Buy: bid < open, high < bid -> not filled."""
    order = PendingOrder(ts_code="000001.SZ", stock_name="Test", order_price=10.0, order_shares=100,
                          score=0.8, up_prob_3d=0.6, up_prob_5d=0.55, trade_date="20250102", settle_date="20250103")
    result = FakePositionManager.match_order(order, open_px=10.5, high_px=10.8, low_px=10.2)
    assert result is None


def test_sell_ask_below_open_fills_at_open():
    """Sell: ask <= open -> filled at open."""
    order = PendingOrder(ts_code="000001.SZ", stock_name="Test", order_price=10.0, order_shares=-100,
                          score=0.8, up_prob_3d=0.6, up_prob_5d=0.55, trade_date="20250102", settle_date="20250103")
    result = FakePositionManager.match_order(order, open_px=10.2, high_px=10.5, low_px=9.9)
    assert result == 10.2


def test_sell_ask_above_open_low_reaches_ask():
    """Sell: ask > open, low <= ask -> filled at ask."""
    order = PendingOrder(ts_code="000001.SZ", stock_name="Test", order_price=10.5, order_shares=-100,
                          score=0.8, up_prob_3d=0.6, up_prob_5d=0.55, trade_date="20250102", settle_date="20250103")
    result = FakePositionManager.match_order(order, open_px=10.2, high_px=10.8, low_px=10.3)
    assert result == 10.5


def test_sell_ask_above_open_low_never_reaches():
    """Sell: ask > open, low > ask -> not filled."""
    order = PendingOrder(ts_code="000001.SZ", stock_name="Test", order_price=11.0, order_shares=-100,
                          score=0.8, up_prob_3d=0.6, up_prob_5d=0.55, trade_date="20250102", settle_date="20250103")
    result = FakePositionManager.match_order(order, open_px=10.5, high_px=10.8, low_px=10.6)
    assert result is None
```

- [ ] **Step 1: 创建测试文件，包含全部6个测试用例**

- [ ] **Step 2: 运行测试确认通过**

```bash
cd d:/projects/trade-alpha/backend && python -m pytest tests/trade_alpha/unit/strategy/test_order_matching.py -v
```
预期：6 个测试全部通过

- [ ] **Step 3: 提交**

```bash
cd d:/projects/trade-alpha
git add backend/tests/trade_alpha/unit/strategy/test_order_matching.py
git commit -m "test: add unit tests for T+1 order matching"
```

---

### Task 5: 运行集成测试

- [ ] **Step 1: 运行所有集成测试**

```bash
cd d:/projects/trade-alpha/backend && python -m pytest tests/trade_alpha/integration/ -v --timeout=600 2>&1 | tail -20
```
预期：所有回测相关测试通过

- [ ] **Step 2: 修复失败项（如有）**

如果测试失败，分析原因并修复代码。

- [ ] **Step 3: 提交修复**

---

### Task 6: 更新文档并推送

- [ ] **Step 1: 如果实现与 spec 有偏差，同步更新设计文档**

- [ ] **Step 2: 推送所有提交**

```bash
cd d:/projects/trade-alpha
git push
```
