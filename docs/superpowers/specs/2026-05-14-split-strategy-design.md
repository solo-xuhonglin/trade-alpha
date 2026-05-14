# Split Strategy Design

**Date**: 2026-05-14
**Author**: AI Assistant

## Overview

Split the monolithic PositionManager into two separate strategy classes to address the issues with single-stock backtesting.

## Problem

Current implementation uses the same ranking-based strategy for both portfolio and single-stock modes, which causes:
- Low trading frequency in single-stock mode (only 1 trade per backtest)
- Low capital utilization (max 30% per stock)
- No probability-based buy/sell decisions
- Ranking logic doesn't make sense for single-stock mode

## Design

### 1. File Structure

```
execution/
├── position_manager.py       # Base class with common functionality
├── portfolio_strategy.py     # PortfolioStrategy (ranking-based)
├── single_stock_strategy.py  # SingleStockStrategy (probability-based)
└── pipeline.py               # Uses mode + ts_codes to select strategy
```

### 2. Base Class (position_manager.py)

Retain common functionality:
- `settle_orders()`
- `daily_snapshot()`
- `calculate_metrics()`
- `calculate_max_drawdown()`
- `calculate_baseline_metrics()`
- `calculate_trade_metrics()`

Make `make_decisions()` an abstract method to be implemented by subclasses.

### 3. PortfolioStrategy (portfolio_strategy.py)

**Purpose**: Multi-stock portfolio strategy based on ranking

**Parameters**:
- `max_positions`: Number of stocks to hold (default: 10)
- `max_position_pct`: Max position size (default: 0.3)
- `ts_codes`: Stock universe to select from

**Buy Conditions**:
- Stock is in top N ranking
- Not already held
- Sufficient cash

**Sell Conditions**:
- Stock falls out of top N ranking
- Hold days >= max_hold_days (20)
- Stop loss triggered (10%)

### 4. SingleStockStrategy (single_stock_strategy.py)

**Purpose**: Single-stock strategy based on prediction probabilities

**Parameters**:
- `target_ts_code`: Single stock to trade
- `max_position_pct`: 0.95 (higher capital utilization)
- `max_hold_days`: 30 (more flexible)

**Buy Conditions**:
- `up_prob_3d > 0.6` or `up_prob_5d > 0.65`

**Sell Conditions**:
- `up_prob_3d < 0.4`
- Stop loss triggered (10%)
- Hold days >= max_hold_days (30)

### 5. Pipeline Integration (pipeline.py)

```python
class ExecutionPipeline:
    def __init__(
        self,
        account_config: AccountConfig,
        training_id: PydanticObjectId,
        model_config: ModelConfig,
        mode: str = "portfolio",  # "portfolio" or "single"
        ts_codes: List[str] = None,
        max_positions: int = 10,
    ):
        self.mode = mode
        self.ts_codes = ts_codes or []
        
        if mode == "single":
            assert len(ts_codes) == 1, "single mode requires exactly 1 ts_code"
            self.strategy = SingleStockStrategy(
                account_config=account_config,
                target_ts_code=ts_codes[0],
            )
        else:
            self.strategy = PortfolioStrategy(
                account_config=account_config,
                max_positions=max_positions,
                ts_codes=ts_codes,
            )
```

### 6. Usage Examples

#### Portfolio Mode
```python
pipeline = ExecutionPipeline(
    account_config=account_config,
    training_id=training_id,
    model_config=model_config,
    mode="portfolio",
    ts_codes=["600519.SH", "000858.SZ", "300750.SZ", "000001.SZ"],
    max_positions=3,
)
```

#### Single-Stock Mode
```python
pipeline = ExecutionPipeline(
    account_config=account_config,
    training_id=training_id,
    model_config=model_config,
    mode="single",
    ts_codes=["600519.SH"],
)
```

## Implementation Plan

1. Refactor PositionManager to extract common methods
2. Create PortfolioStrategy
3. Create SingleStockStrategy
4. Update ExecutionPipeline to use strategy classes
5. Update main.py to pass mode and ts_codes
6. Test both modes

## Success Criteria

- Single-stock backtests have more frequent trading (multiple trades)
- Higher capital utilization in single-stock mode
- Both portfolio and single-stock modes work correctly
- Backtest results are saved properly with all metrics
