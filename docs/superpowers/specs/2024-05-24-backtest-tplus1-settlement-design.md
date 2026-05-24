# Backtest T+1 Order Settlement Design

## Problem

Currently, backtest orders are generated and settled on the same day using the day's close price. This is unrealistic because:

1. In real trading, orders placed on day T are executed on day T+1
2. Orders are filled based on the next day's open/high/low prices, not the current day's close
3. Orders may not be filled at all if the price doesn't reach the limit order price

## Solution

Change the backtest order flow from T+0 settlement to T+1 settlement:

- Orders generated on day T are settled on day T+1 using T+1's OHLC data
- A limit-order matching model determines fill price and whether the order fills at all
- Unfilled orders are recorded as cancelled

## Daily Loop (using backtest date = T)

For each trading day T in the backtest date range:

```
Step 1: Load day T data (open_T, high_T, low_T, close_T)

Step 2: Settle T-1 pending orders with day T's OHLC
  for each order in self.pending_orders:
    matched_price = match_order(order, open_T, high_T, low_T)
    if matched_price:
      → record ExecutionTrade (trade_date = T, price = matched_price, status="filled")
      → update positions / cash
    else:
      → record ExecutionTrade (trade_date = T, status="cancelled", no cash impact)
  self.pending_orders.clear()

Step 3: Make predictions (predict T+1 returns)
  → scored_stocks

Step 4: Generate new orders
  pending_orders = make_decisions(scored_stocks, positions, cash, date=T)
  for order in pending_orders:
    order.trade_date = T
    order.settle_date = next_trade_date(T)  // T+1

Step 5: Daily snapshot
  → snapshot(T, positions, cash, close_prices)
```

## Limit Order Matching

### Match function

```python
def match_order(order: PendingOrder, open_px: float, high_px: float, low_px: float) -> Optional[float]:
    """
    Match a pending order against next day's OHLC.
    Returns matched price or None if not filled.
    """
    if order.order_shares > 0:  # Buy order
        # Buy: bid price >= open → filled at open
        if order.order_price >= open_px:
            return open_px
        # Buy: bid price < open → check if price ever reached bid during the day
        if high_px >= order.order_price:
            return order.order_price
        return None
    else:  # Sell order
        # Sell: ask price <= open → filled at open
        if order.order_price <= open_px:
            return open_px
        # Sell: ask price > open → check if price ever dropped to ask during the day
        if low_px <= order.order_price:
            return order.order_price
        return None
```

### Fee calculation (unchanged from current)

Same as current `settle_orders` logic:
- Buy: `fee = max(price * shares * buy_fee_rate, min_fee)`
- Sell: `fee = max(price * shares * sell_fee_rate, min_fee)` + stamp tax

### Unfilled orders

Each order (whether filled or not) produces exactly one `ExecutionTrade` record:
- Filled: `status="filled"`, has actual price/shares/fee/cash_after
- Unfilled: `status="cancelled"`, price/shares/fee/cash_after all set to 0, no cash impact

No separate pending order table is needed. The `ExecutionTrade` table serves as both the order log and the trade log.

## Pipeline State Changes

Add to `ExecutionPipeline.__init__`:

```python
self.pending_orders: List[PendingOrder] = []  # Orders from T-1 waiting to settle on T
```

## Changes by File

### `backend/src/trade_alpha/dao/execution_trade.py`

Add `status` field to `ExecutionTrade`:
```python
status: str = Field(default="filled")  # "filled" or "cancelled"
```

### `backend/src/trade_alpha/schemas.py`

No changes needed. `PendingOrder` already has `order_price` field.

### `backend/src/trade_alpha/strategy/base.py`

**Modify `settle_orders`:**
- Accept OHLC data (open_prices, high_prices, low_prices) instead of just close_prices
- Implement match_order logic for each pending order
- Return filled trades, unfilled orders, and net cash change

New method signature:
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

Returns:
- `filled_trades`: List[ExecutionTrade] - successfully filled trades
- `unfilled_orders`: List[PendingOrder] - orders that did NOT fill
- `net_cash_change`: float - cash impact of filled trades

### `backend/src/trade_alpha/execution/pipeline.py`

**Modify `run_backtest`:**
- Add `self.pending_orders: List[PendingOrder] = []` in init (already initialized in `__init__`)
- Change daily loop:

```python
# Before: T+0 settlement
pending_orders = await self.strategy.make_decisions(...)
trades, net_cash = await self.strategy.settle_orders(pending_orders, date, close_prices, backtest_id)

# After: T+1 settlement
# Step 1: Settle T-1 orders
if self.pending_orders:
    filled_trades, unfilled, net_cash = await self.strategy.settle_orders(
        self.pending_orders, date, open_prices, high_prices, low_prices, backtest_id
    )
    self.cash += net_cash
    # Process filled trades (update positions)
    ...
    # Record all orders to ExecutionTrade (filled + cancelled)
    all_trades = filled_trades + [
        ExecutionTrade(
            backtest_id=backtest_id,
            ts_code=order.ts_code,
            trade_date=date,
            action="buy" if order.order_shares > 0 else "sell",
            price=0,
            shares=0,
            fee=0,
            cash_after=0,
            reason="cancelled",
            entry_score=order.score,
            up_prob_3d=order.up_prob_3d,
            up_prob_5d=order.up_prob_5d,
        )
        for order in unfilled
    ]
    await ExecutionTrade.insert_many(all_trades)
    self.pending_orders.clear()

# Step 2: Generate new orders for T+1
pending_orders = await self.strategy.make_decisions(...)
for order in pending_orders:
    order.trade_date = date
    order.settle_date = _next_date(date)
self.pending_orders = pending_orders
```

### DataLoader changes

Currently `load_day_data` returns a DataFrame already containing open/high/low/close columns. We just need to extract them:

```python
open_prices = dict(zip(day_df["ts_code"], day_df["open"]))
high_prices = dict(zip(day_df["ts_code"], day_df["high"]))
low_prices = dict(zip(day_df["ts_code"], day_df["low"]))
close_prices = dict(zip(day_df["ts_code"], day_df["close"]))
```

## Edge Cases

1. **First day of backtest**: No pending orders to settle. Skip settlement step.
2. **Stock suspension on settlement day**: No OHLC data available → order cannot be filled → recorded as cancelled.
3. **Order with zero shares**: Skip (shouldn't happen in practice).
4. **Cash insufficient**: The `make_decisions` strategy should handle position/cash limits. The settlement step doesn't need to check cash availability because the order was already validated when generated (using T-1's cash/position state).
5. **Multiple orders for same stock**: Each order is matched independently. Only the first sell order for a stock can fill (position is removed after first fill).

## Testing

1. **Unit tests for match_order**:
   - Buy: bid >= open → filled at open
   - Buy: bid < open, high >= bid → filled at bid
   - Buy: bid < open, high < bid → not filled
   - Sell: ask <= open → filled at open
   - Sell: ask > open, low <= ask → filled at ask
   - Sell: ask > open, low > ask → not filled

2. **Integration tests**:
   - Full backtest with T+1 settlement → verify trade dates are T+1
   - Verify unfilled orders are recorded as cancelled
   - Verify cash and position tracking is correct across multiple days
