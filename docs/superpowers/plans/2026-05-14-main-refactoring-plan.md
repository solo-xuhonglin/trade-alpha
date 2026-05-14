# main.py Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor main.py into three independent methods: train_model(), run_portfolio_backtest(), and run_single_stock_backtest()

**Architecture:** Extract training logic, enhance portfolio backtest with new metrics, add single-stock backtest with baseline comparison

**Tech Stack:** Python 3.14, Beanie ODM, pandas, numpy

---

## Task 1: Enhance ExecutionResult Schema

**Files:**
- Modify: `backend/src/trade_alpha/dao/execution.py`
- Test: Run existing integration tests

- [ ] **Step 1: Add new fields to ExecutionResult**

Add the following fields to the `ExecutionResult` class:
```python
ts_code: Optional[str] = None
stock_name: Optional[str] = None
baseline_return: Optional[float] = None
excess_return: Optional[float] = None
baseline_max_drawdown: Optional[float] = None
sharpe_ratio: Optional[float] = None
volatility: Optional[float] = None
avg_hold_days: Optional[float] = None
```

- [ ] **Step 2: Run existing tests**

Run: `cd backend && pytest tests/trade_alpha/integration/ -v -k "execution" --tb=short`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/dao/execution.py
git commit -m "feat: add new fields to ExecutionResult for single-stock backtest"
```

---

## Task 2: Enhance ExecutionPortfolioDaily Schema

**Files:**
- Modify: `backend/src/trade_alpha/dao/execution_portfolio_daily.py`
- Test: Run existing integration tests

- [ ] **Step 1: Add baseline fields to ExecutionPortfolioDaily**

Add the following fields:
```python
baseline_value: float = 0.0
baseline_hold_days: int = 0
```

- [ ] **Step 2: Run existing tests**

Run: `cd backend && pytest tests/trade_alpha/integration/ -v --tb=short`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/dao/execution_portfolio_daily.py
git commit -m "feat: add baseline fields to ExecutionPortfolioDaily"
```

---

## Task 3: Add Metrics Calculation Methods

**Files:**
- Modify: `backend/src/trade_alpha/execution/position_manager.py`
- Test: Create unit test

- [ ] **Step 1: Add calculate_metrics static method**

Add a new static method to calculate metrics:
```python
@staticmethod
def calculate_metrics(
    daily_returns: List[float],
    initial_capital: float
) -> Dict[str, float]:
    """Calculate Sharpe ratio, volatility, and avg hold days."""
    # Calculate Sharpe ratio
    # Calculate volatility
    # Return dict with sharpe_ratio, volatility, avg_hold_days
```

- [ ] **Step 2: Add calculate_baseline_metrics method**

Add method to calculate baseline metrics:
```python
async def calculate_baseline_metrics(
    self,
    ts_code: str,
    start_date: str,
    end_date: str,
    daily_prices: List[float],
    initial_capital: float
) -> Dict[str, float]:
    """Calculate baseline return and max drawdown for buy-and-hold."""
    # Buy at first day's close, sell at last day's close
    # Track daily value for max drawdown calculation
```

- [ ] **Step 3: Create unit test**

Create `backend/tests/trade_alpha/execution/test_position_manager.py`:
```python
def test_calculate_metrics():
    from trade_alpha.execution.position_manager import PositionManager
    daily_returns = [0.01, -0.02, 0.03, 0.01, -0.01]
    result = PositionManager.calculate_metrics(daily_returns, 100000)
    assert "sharpe_ratio" in result
    assert "volatility" in result
```

Run: `cd backend && pytest tests/trade_alpha/execution/test_position_manager.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/execution/position_manager.py tests/
git commit -m "feat: add metrics calculation methods to PositionManager"
```

---

## Task 4: Refactor main.py - Extract train_model()

**Files:**
- Modify: `backend/main.py`
- Test: Run main.py with --mode=train

- [ ] **Step 1: Create train_model() function**

Extract the training logic into a separate function:
```python
async def train_model(
    ts_codes: List[str],
    train_start: str,
    train_end: str,
    model_config_id: PydanticObjectId,
    training_name: str = "prod_training"
) -> Tuple[Training, float]:
    """Train model and return training record with duration."""
    # Get or create training
    # Train if not exists
    # Return (training, duration)
```

- [ ] **Step 2: Test train_model()**

Run: `cd backend && python main.py --mode=train`
Expected: Train model and print results

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "refactor: extract train_model() from main.py"
```

---

## Task 5: Refactor main.py - Extract run_portfolio_backtest()

**Files:**
- Modify: `backend/main.py`
- Test: Run main.py with --mode=portfolio

- [ ] **Step 1: Create run_portfolio_backtest() function**

Extract portfolio backtest logic:
```python
async def run_portfolio_backtest(
    training_id: PydanticObjectId,
    account_config_id: PydanticObjectId,
    model_config_id: PydanticObjectId,
    start_date: str,
    end_date: str,
    ts_codes: List[str],
    max_positions: int = 10
) -> ExecutionResult:
    """Run portfolio backtest and return results."""
    # Load configs
    # Run pipeline
    # Calculate and add new metrics
    # Save and return result
```

- [ ] **Step 2: Add metrics calculation to pipeline**

Update `pipeline.run_backtest()` to calculate:
- sharpe_ratio
- volatility
- avg_hold_days

- [ ] **Step 3: Test run_portfolio_backtest()**

Run: `cd backend && python main.py --mode=portfolio --training-id=<id>`
Expected: Run backtest and print results

- [ ] **Step 4: Commit**

```bash
git add backend/main.py backend/src/trade_alpha/execution/pipeline.py
git commit -m "feat: extract run_portfolio_backtest() with metrics"
```

---

## Task 6: Implement run_single_stock_backtest()

**Files:**
- Modify: `backend/main.py`
- Create: `backend/src/trade_alpha/execution/single_stock_pipeline.py` (optional, can be in pipeline.py)
- Test: Run main.py with --mode=single

- [ ] **Step 1: Create run_single_stock_backtest() function**

```python
async def run_single_stock_backtest(
    ts_code: str,
    training_id: PydanticObjectId,
    account_config_id: PydanticObjectId,
    model_config_id: PydanticObjectId,
    start_date: str,
    end_date: str,
    all_ts_codes: List[str]
) -> ExecutionResult:
    """Run single-stock backtest with baseline comparison."""
    # Load all stocks data for cross-sectional normalization
    # Run strategy backtest (max_positions=1)
    # Calculate baseline (buy-and-hold)
    # Calculate all metrics
    # Save and return result
```

- [ ] **Step 2: Add baseline calculation logic**

Implement baseline calculation:
1. Load daily close prices for the stock
2. Calculate baseline return = (end_price - start_price) / start_price
3. Calculate baseline max drawdown during period

- [ ] **Step 3: Add CLI arguments**

Add argparse for:
- `--mode`: train, portfolio, single, single-batch, full
- `--ts-code`: Stock code for single mode
- `--training-id`: Existing training ID

- [ ] **Step 4: Test run_single_stock_backtest()**

Run: `cd backend && python main.py --mode=single --ts-code=600519.SH --training-id=<id>`
Expected: Run backtest and print strategy vs baseline comparison

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/src/trade_alpha/execution/pipeline.py
git commit -m "feat: implement run_single_stock_backtest() with baseline"
```

---

## Task 7: Add Batch Single-Stock Mode

**Files:**
- Modify: `backend/main.py`
- Test: Run main.py with --mode=single-batch

- [ ] **Step 1: Add batch mode to main()**

```python
if mode == "single-batch":
    training_id = args.training_id
    # Loop through all stocks
    # Call run_single_stock_backtest() for each
    # Print summary table
```

- [ ] **Step 2: Add result query script**

Create `backend/scripts/query_single_stock_results.py`:
```python
async def query_results(training_id: str):
    """Query and display single-stock backtest results."""
    results = await ExecutionResult.find(
        ExecutionResult.training_id == training_id,
        ExecutionResult.ts_code != None
    ).to_list()
    # Print table with strategy vs baseline
```

- [ ] **Step 3: Test batch mode**

Run: `cd backend && python main.py --mode=single-batch --training-id=<id>`
Expected: Run backtest for all stocks and print summary

- [ ] **Step 4: Commit**

```bash
git add backend/main.py backend/scripts/query_single_stock_results.py
git commit -m "feat: add batch single-stock backtest mode"
```

---

## Task 8: Update Documentation

**Files:**
- Modify: `docs/system-design.md` (if exists)
- Modify: `README.md` (if exists)

- [ ] **Step 1: Document new CLI usage**

Add documentation for:
- New command-line arguments
- Example usage for each mode
- Output format description

- [ ] **Step 2: Commit**

```bash
git add docs/ README.md
git commit -m "docs: update CLI documentation for main.py refactoring"
```

---

## Verification

**Integration Test:**

Run full workflow:
```bash
cd backend && python main.py --mode=full
```

Expected output:
- Training completed
- Portfolio backtest completed with all metrics
- Single-stock backtest with baseline comparison
- All results saved to database

**Query Results:**
```bash
cd backend && python scripts/query_single_stock_results.py --training-id=<id>
```

Expected: Table with all stocks, strategy return, baseline return, excess return
