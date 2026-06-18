# ATR Dynamic Trailing Stop-Loss Design

## 1. Background

Current stop-loss uses a fixed percentage trailing from peak price, adjusted by
a `baseline_vol_multiplier` computed from std(20d returns)/std(60d returns) of
the daily-rebalanced index. Problems:

1. **No dynamic up-move** — stop price does not rise with the stock price beyond
   percentage trailing, failing to protect unrealized gains.
2. **Baseline vol std-based** — `np.std` on 19 daily returns jumps wildly each day
   (std=0.396, only 49.6% of days within 0.8~1.2 range).
3. **No per-stock volatility** — vol_multiplier is market-wide, ignores individual
   stock volatility. A high-beta stock gets same stop buffer as a low-beta stock.

## 2. Changes Summary

| Layer | Change |
|-------|--------|
| StockDaily model | Add `atr_14` field |
| Indicator service | Persist `atr_14` to DB (+ ALL_INDICATOR_FIELDS) |
| StrategyConfig | Add `atr_stop_multiplier`, `atr_trail_rate`; remove nothing (old params still exist for legacy data) |
| PositionEmbed | Add `atr_at_entry` |
| PendingBuy | Add `atr_at_entry` |
| PortfolioManager | `__init__` takes `atr_stop_multiplier`/`atr_trail_rate`; rewrite `is_stop_loss_triggered`; `_upsert_position` takes `atr_at_entry` |
| MarketRegimeAnalyzer | Replace `_compute_baseline_volatility` with EMA-ATR; remove `_cum_values_buffer` |
| Data loader | `load_day_data()` returns `atr_14` dict alongside close/high/low/open/vol |
| Pipeline | Pass `atr_14` values into `make_orders()` |
| BaseStrategy.daily_snapshot | Preserve `atr_at_entry` in PositionEmbed copy |
| Frontend types | Add `atr_stop_multiplier`, `atr_trail_rate` to Strategy interface |
| Frontend Config | UI form fields + compare fields + backtest detail echo |
| API schemas | Add `atr_stop_multiplier`, `atr_trail_rate` |

## 3. Database Schema Changes

### StockDaily — one new field

```python
atr_14: Optional[float] = None  # Average True Range(14) for volatility
```

### Indicator service — persist atr_14

In `indicators/service.py` `calculate_and_store_custom_indicators()`:

```python
# update_data dict — add:
"atr_14": row.get("atr_14"),
```

Also add `"atr_14"` to `ALL_INDICATOR_FIELDS` list.

### PositionEmbed — one new field

```python
class PositionEmbed(BaseModel):
    ...
    atr_at_entry: float = 0.0  # ATR(14) value at buy date
```

### PendingBuy — one new field (for ATR transfer through reservation)

```python
class PendingBuy(BaseModel):
    ...
    atr_at_entry: float = 0.0
```

### StrategyConfig — two new fields

```python
atr_stop_multiplier: float = 3.0   # 初始止损 = 入场价 - 乘数 × ATR
atr_trail_rate: float = 0.5        # 每涨 1×ATR 止损上移 比例 × ATR
```

### API schemas — two new optional fields

```python
atr_stop_multiplier: Optional[float] = None
atr_trail_rate: Optional[float] = None
```

## 4. Core Stop-Loss Logic Replacement

### PortfolioManager — constructor

```python
def __init__(
    self,
    ...,
    atr_stop_multiplier: float = 3.0,
    atr_trail_rate: float = 0.5,
):
    ...
    self._atr_stop_multiplier = atr_stop_multiplier
    self._atr_trail_rate = atr_trail_rate
```

### PortfolioManager — _upsert_position

```python
def _upsert_position(self, ts_code, stock_name, order_shares, matched_price,
                     matched_fee, atr_at_entry=0.0):
    if existing:
        self.positions[ts_code] = PositionEmbed(
            ..., atr_at_entry=existing.atr_at_entry,  # keep original ATR
        )
    else:
        self.positions[ts_code] = PositionEmbed(
            ..., atr_at_entry=atr_at_entry,
        )
```

### PortfolioManager — is_stop_loss_triggered (rewritten)

```python
def is_stop_loss_triggered(
    self,
    ts_code: str,
    close_prices: Dict[str, float],
    stop_loss_pct: float,
    vol_multiplier: float = 1.0,
) -> bool:
    position = self.positions.get(ts_code)
    if position is None:
        return False
    current_price = close_prices.get(ts_code)
    if current_price is None:
        return False

    atr = position.atr_at_entry

    # ATR-based stop: 入场价 - 乘数 × ATR × vol_mult
    if atr > 0:
        stop_distance = self._atr_stop_multiplier * atr * vol_multiplier
        stop_price = position.buy_price - stop_distance

        # Dynamic up-move: for each 1×ATR gained, move stop up by trail_rate × ATR × vol_mult
        gain = max(position.peak_price - position.buy_price, 0)
        atr_units = gain / atr
        trail_raise = atr_units * self._atr_trail_rate * atr * vol_multiplier
        stop_price = stop_price + trail_raise
    else:
        # Fallback: pure percentage stop (no ATR data)
        stop_price = position.buy_price * (1 + stop_loss_pct)

    # Hard floor: never exceed base percentage stop from cost
    min_stop = position.buy_price * (1 + stop_loss_pct)
    stop_price = max(stop_price, min_stop)

    return current_price < stop_price
```

### PortfolioManager — reserve_funds

Add `atr` parameter to receive ATR at entry time, store it in PendingBuy:

```python
def reserve_funds(self, ts_code, price, close_prices, max_position_scalar=1.0, atr=0.0):
    ...
    self._pending_buys[ts_code] = PendingBuy(
        ..., atr_at_entry=atr,
    )
```

### PortfolioManager — settle_buy

Extract `atr_at_entry` from pending buy and pass to `_upsert_position`:

```python
def settle_buy(self, ts_code, stock_name, order_shares, order_price, matched_price):
    pending = self._pending_buys.pop(ts_code, None)
    ...
    self._upsert_position(
        ts_code, stock_name, order_shares, matched_price, matched_fee,
        atr_at_entry=pending.atr_at_entry if pending else 0.0,
    )
```

## 5. Baseline Volatility: EMA-ATR Replacement

### MarketRegimeAnalyzer — remove _cum_values_buffer

In `__init__`, remove:
```python
self._cum_values_buffer: List[float] = []  # for baseline vol computation  ← DELETE
```

### MarketRegimeAnalyzer — rewrite _compute_baseline_volatility

```python
def _compute_baseline_volatility(
    self, daily_rebalanced_values: Optional[List[float]] = None
) -> None:
    if not daily_rebalanced_values or len(daily_rebalanced_values) < 2:
        return

    abs_returns = []
    prev = daily_rebalanced_values[0]
    for v in daily_rebalanced_values[1:]:
        r = abs((v - prev) / prev)
        abs_returns.append(r)
        prev = v

    if len(abs_returns) < 2:
        return

    short_ema = abs_returns[0]
    long_ema = abs_returns[0]
    for v in abs_returns[1:]:
        short_ema = 0.15 * v + 0.85 * short_ema
        long_ema = 0.05 * v + 0.95 * long_ema

    multiplier = short_ema / long_ema if long_ema > 0 else 1.0
    self._last_result.baseline_vol_multiplier = max(0.5, min(3.0, multiplier))
```

No more `vol_window` / `vol_window_mult` / `_cum_values_buffer` dependencies.

## 6. Data Flow — ATR from Daily Data to Position

```
_load_day_data(date, ts_codes)
  → StockDaily query returns DataFrame with atr_14 column
  → return dict includes "atr_14": {ts_code: value}

Pipeline make_orders():
  close_prices = day_data["close"]
  atr_values = day_data["atr_14"]
  await self.strategy.make_orders(..., close_prices=close_prices, atr_values=atr_values)

MultiStockStrategy.make_orders():
  When calling portfolio.reserve_funds(ts_code, price, close_prices, atr=atr_values.get(ts_code, 0))

PortfolioManager.reserve_funds(... atr=0.0):
  PendingBuy.ts_code = ts_code, atr_at_entry = atr

PortfolioManager.settle_buy():
  pending.atr_at_entry → _upsert_position(..., atr_at_entry=...)

BaseStrategy.daily_snapshot():
  PositionEmbed(..., atr_at_entry=pos.atr_at_entry)  # preserve in daily copy
```

### Pipeline initialization — pass config to Portfolio

```python
self.portfolio = PortfolioManager(
    ...,
    atr_stop_multiplier=getattr(strategy_config, 'atr_stop_multiplier', 3.0),
    atr_trail_rate=getattr(strategy_config, 'atr_trail_rate', 0.5),
)
```

## 7. Frontend Changes

### Strategy type (api/strategyConfig.ts)

```
atr_stop_multiplier?: number
atr_trail_rate?: number
```

### Config view — form defaults + load + save

```typescript
// form defaults
atr_stop_multiplier: 3.0,
atr_trail_rate: 0.5,

// openDialog — load from item
atr_stop_multiplier: item.atr_stop_multiplier ?? 3.0,
atr_trail_rate: item.atr_trail_rate ?? 0.5,

// saveStrategy — include in payload
atr_stop_multiplier: form.value.atr_stop_multiplier,
atr_trail_rate: form.value.atr_trail_rate,
```

### Config view — UI fields (basic group, near stop_loss_pct)

```html
<v-col cols="12" md="4">
  <v-text-field v-model.number="form.atr_stop_multiplier" type="number" step="0.5" min="1" max="10"
    label="ATR止损乘数" hint="止损=入场价 - 乘数×ATR（默认3.0）" persistent-hint />
</v-col>
<v-col cols="12" md="4">
  <v-text-field v-model.number="form.atr_trail_rate" type="number" step="0.1" min="0" max="1"
    label="ATR上移比例" hint="每涨1倍ATR止损上移此比例×ATR（默认0.5）" persistent-hint />
</v-col>
```

### Config view — compareFields

```typescript
{ key: 'atr_stop_multiplier', label: 'ATR止损乘数', group: '基本配置', type: 'number' },
{ key: 'atr_trail_rate', label: 'ATR上移比例', group: '基本配置', type: 'number' },
```

### BacktestRecordsView — detail echo

```html
<v-col cols="6"><span class="text-body-2 text-medium-emphasis">ATR止损乘数：</span>{{ backtestStrategyConfig?.atr_stop_multiplier ?? '3.0' }}</v-col>
<v-col cols="6"><span class="text-body-2 text-medium-emphasis">ATR上移比例：</span>{{ backtestStrategyConfig?.atr_trail_rate ?? '0.5' }}</v-col>
```

### BacktestRecordsView — compareFields

Same additions as StrategyConfigView.

## 8. Files Modified

| File | Change |
|------|--------|
| `backend/src/trade_alpha/dao/stock_daily.py` | Add `atr_14` field |
| `backend/src/trade_alpha/dao/position.py` | Add `atr_at_entry` to `PositionEmbed` |
| `backend/src/trade_alpha/schemas.py` | Add `atr_at_entry` to `PendingBuy` |
| `backend/src/trade_alpha/dao/strategy_config.py` | Add `atr_stop_multiplier`, `atr_trail_rate` |
| `backend/src/trade_alpha/api/schemas.py` | Add `atr_stop_multiplier`, `atr_trail_rate` |
| `backend/src/trade_alpha/indicators/service.py` | Persist `atr_14` + add to ALL_INDICATOR_FIELDS |
| `backend/src/trade_alpha/execution/portfolio.py` | Rewrite stop-loss, `_upsert_position`, `reserve_funds` |
| `backend/src/trade_alpha/execution/market_regime.py` | Replace `_compute_baseline_volatility`, remove `_cum_values_buffer` |
| `backend/src/trade_alpha/execution/backtest_pipeline.py` | Return `atr_14` from `_load_day_data`, pass to `make_orders` |
| `backend/src/trade_alpha/execution/suggestion_pipeline.py` | Same changes as backtest_pipeline |
| `backend/src/trade_alpha/strategy/base.py` | Preserve `atr_at_entry` in `daily_snapshot` |
| `backend/src/trade_alpha/strategy/multi_stock_strategy.py` | Pass `atr_values` through `make_orders` |
| `backend/src/trade_alpha/execution/backtest_service.py` | Serialize `atr_at_entry` in position details |
| `frontend/src/api/strategyConfig.ts` | Add `atr_stop_multiplier`, `atr_trail_rate` |
| `frontend/src/views/StrategyConfigView.vue` | Form fields + defaults + save + compare |
| `frontend/src/views/BacktestRecordsView.vue` | Detail echo + compare fields |

## 9. Testing

### Unit test for is_stop_loss_triggered

Test cases:
- ATR > 0, price well above stop → False
- ATR > 0, price below initial stop → True
- ATR > 0, price rose 2×ATR, stop moved up correctly → verify stop price
- ATR = 0 (no data) → fallback to percentage stop
- min_stop clamped correctly (atr stop more aggressive than percentage floor)
- vol_multiplier widens/shrinks stop distance

### Integration test: verify atr_14 in stock_daily

Run indicator calculation, verify that `atr_14` field is populated for
a known stock.

### Integration test: verify atr_at_entry in snapshots

Run backtest, check that daily snapshots contain positions with `atr_at_entry`.

## 10. Edge Cases

| Case | Handling |
|------|----------|
| atr_at_entry = 0 (no ATR data for stock) | Fallback to pure percentage stop |
| vol_multiplier = 0.5 (calm market) | Stop distance halved, trail raise halved |
| vol_multiplier = 2.0 (volatile market) | Stop distance doubled, trail raise doubled |
| Multiple fills on same position | Keep original atr_at_entry (from first buy) |
| Peak price updated but ATR still 0 | Stop still works via percentage fallback |
| atr_stop_multiplier = 0 | stop_price = buy_price (instant stop at entry — edge configuration) |
