# main.py Refactoring Design

## Overview

Refactor `main.py` into three independent methods: model training, portfolio backtest, and single-stock backtest. The single-stock backtest will compare strategy returns with a buy-and-hold baseline.

## Architecture

```
main.py
├── train_model()                    # Train model (extracted from main)
├── run_portfolio_backtest()          # Portfolio backtest (enhanced)
└── run_single_stock_backtest()       # Single-stock backtest (new)
```

## Changes

### 1. ExecutionResult Schema Enhancement

Add new fields to `ExecutionResult`:

| Field | Type | Description |
|-------|------|-------------|
| ts_code | Optional[str] | Stock code (single-stock mode) |
| stock_name | Optional[str] | Stock name (single-stock mode) |
| baseline_return | Optional[float] | Baseline return (buy-and-hold) |
| excess_return | Optional[float] | Strategy - baseline return |
| baseline_max_drawdown | Optional[float] | Baseline max drawdown |
| sharpe_ratio | Optional[float] | Sharpe ratio |
| volatility | Optional[float] | Volatility |
| avg_hold_days | Optional[float] | Average hold days |

### 2. ExecutionPortfolioDaily Enhancement

Add fields to support baseline calculation:

| Field | Type | Description |
|-------|------|-------------|
| baseline_value | float | Baseline portfolio value (for single-stock mode) |
| baseline_hold_days | int | Days since baseline buy (for single-stock mode) |

### 3. Command-line Interface

```bash
# Full workflow: train + portfolio backtest
python main.py --mode=full

# Train only
python main.py --mode=train

# Portfolio backtest only
python main.py --mode=portfolio --training-id=<id>

# Single-stock backtest
python main.py --mode=single --ts-code=600519.SH --training-id=<id>

# Batch single-stock backtest (all stocks)
python main.py --mode=single-batch --training-id=<id>
```

## Single-Stock Backtest Logic

### Strategy Part
1. Load all stocks' historical data for cross-sectional normalization
2. Each day: predict target stock using model
3. Decision: buy/sell based on score threshold
4. Calculate: strategy return, max drawdown, Sharpe ratio, volatility, avg hold days

### Baseline Part
1. Buy on first day at close price
2. Track daily market value throughout backtest period
3. Calculate: baseline return, baseline max drawdown

## Metrics Calculation

### Sharpe Ratio
```
Sharpe = (Mean Return - Risk-free Rate) / Std(Returns)
Risk-free Rate = 0.03 (3% annual)
```

### Volatility
```
Volatility = Std(Daily Returns) * sqrt(252)
```

### Average Hold Days
```
Avg Hold Days = Sum(Hold Days for all trades) / Number of Trades
```

## Data Flow

```
Single-Stock Backtest:
1. Load training data → Build feature DataFrame
2. Load backtest data → Build prediction DataFrame
3. For each day:
   - Cross-sectional normalize all stocks
   - Predict target stock
   - Execute strategy decisions
   - Calculate baseline (buy-and-hold)
4. Save results to ExecutionResult
```

## Files to Modify

1. `backend/src/trade_alpha/dao/execution.py` - Add new fields
2. `backend/src/trade_alpha/dao/execution_portfolio_daily.py` - Add baseline fields
3. `backend/main.py` - Refactor into three methods + CLI
4. `backend/src/trade_alpha/execution/position_manager.py` - Add baseline calculation method
5. `backend/src/trade_alpha/execution/pipeline.py` - Add single-stock backtest support

## Backward Compatibility

- Portfolio backtest mode: new fields are None
- Single-stock mode: all fields populated
- Existing execution results remain unchanged
