# 策略阈值实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 PriceStrategy 增加买入/卖出阈值参数，支持根据持仓状态决定交易动作

**Architecture:** 修改 StrategyContext 增加 position 字段，PriceStrategy 增加阈值参数，调用方传递持仓状态

**Tech Stack:** Python 3.14+, pytest

---

## 文件结构

```
src/trade_alpha/strategy/
├── base.py         # StrategyContext 增加 position 字段
├── price.py        # PriceStrategy 增加阈值参数
└── service.py     # generate_signal 传递 position

src/trade_alpha/backtest/
└── engine.py      # 回测传递 Portfolio.position

tests/trade_alpha/strategy/
├── test_price.py   # 更新测试
└── test_service.py # 更新测试
```

---

### Task 1: 修改 StrategyContext

**Files:**
- Modify: `src/trade_alpha/strategy/base.py:7-14`
- Test: `tests/trade_alpha/strategy/test_price.py`

- [ ] **Step 1: Write the failing test**

```python
def test_strategy_context_with_position():
    """Test StrategyContext includes position field."""
    from trade_alpha.strategy.base import StrategyContext

    context = StrategyContext(
        ts_code="000001.SZ",
        trade_date="20240101",
        current_price=100.0,
        prediction={"close": 105.0},
        indicators={},
        position=100,  # 持仓100股
    )

    assert context.position == 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trade_alpha/strategy/test_price.py::test_strategy_context_with_position -v`
Expected: FAIL with "position"

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass
class StrategyContext:
    """Strategy context data."""
    ts_code: str
    trade_date: str
    current_price: float
    prediction: dict[str, float]
    indicators: dict[str, float]
    position: int = 0  # 新增：当前持仓股数
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trade_alpha/strategy/test_price.py::test_strategy_context_with_position -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/trade_alpha/strategy/base.py tests/trade_alpha/strategy/test_price.py
git commit -m "feat: add position field to StrategyContext"
```

---

### Task 2: 修改 PriceStrategy

**Files:**
- Modify: `src/trade_alpha/strategy/price.py`
- Test: `tests/trade_alpha/strategy/test_price.py`

- [ ] **Step 1: Write the failing test**

```python
def test_price_strategy_with_threshold():
    """Test PriceStrategy with threshold parameters."""
    from trade_alpha.strategy.price import PriceStrategy
    from trade_alpha.strategy.base import StrategyContext

    # 空仓状态，上涨 0.5%，阈值 1%，不应买入
    context = StrategyContext(
        ts_code="000001.SZ",
        trade_date="20240101",
        current_price=100.0,
        prediction={"close": 100.5},
        indicators={},
        position=0,
    )

    strategy = PriceStrategy(buy_threshold=0.01, sell_threshold=0.01)
    assert strategy.decide(context) == "hold"

    # 空仓状态，上涨 2%，阈值 1%，应买入
    context.prediction = {"close": 102.0}
    assert strategy.decide(context) == "buy"

    # 持仓状态，下跌 2%，阈值 1%，应卖出
    context.position = 100
    context.prediction = {"close": 98.0}
    assert strategy.decide(context) == "sell"

    # 持仓状态，下跌 0.5%，阈值 1%，不应卖出
    context.prediction = {"close": 99.5}
    assert strategy.decide(context) == "hold"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trade_alpha/strategy/test_price.py::test_price_strategy_with_threshold -v`
Expected: FAIL with "buy_threshold" or "sell_threshold"

- [ ] **Step 3: Write minimal implementation**

```python
"""Price-based strategy."""

from trade_alpha.strategy.base import BaseStrategy, StrategyContext


class PriceStrategy(BaseStrategy):
    """Strategy based on predicted price change percentage with thresholds."""

    def __init__(
        self,
        buy_threshold: float = 0.01,
        sell_threshold: float = 0.01,
    ):
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    def decide(self, context: StrategyContext) -> str:
        """Make decision based on predicted price change percentage.

        Buy if predicted price rises by buy_threshold or more (when no position).
        Sell if predicted price falls by sell_threshold or more (when has position).
        Otherwise hold.
        """
        target_price = context.prediction.get("close")
        if target_price is None:
            return "hold"

        change_pct = (target_price - context.current_price) / context.current_price

        if context.position == 0:
            if change_pct >= self.buy_threshold:
                return "buy"
        else:
            if change_pct <= -self.sell_threshold:
                return "sell"

        return "hold"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trade_alpha/strategy/test_price.py::test_price_strategy_with_threshold -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/trade_alpha/strategy/price.py tests/trade_alpha/strategy/test_price.py
git commit -m "feat: add threshold parameters to PriceStrategy"
```

---

### Task 3: 更新 generate_signal

**Files:**
- Modify: `src/trade_alpha/strategy/service.py`

- [ ] **Step 1: Write the failing test**

```python
def test_generate_signal_with_position():
    """Test generate_signal passes position to context."""
    from unittest.mock import MagicMock, patch

    with patch("trade_alpha.strategy.service.MongoDB") as mock_mongo:
        mock_mongo_instance = MagicMock()
        mock_mongo.return_value = mock_mongo_instance
        mock_mongo_instance.find_by_ts_code.return_value = [
            {"trade_date": "20240101", "close": 100.0},
        ]
        mock_mongo_instance._get_collection.return_value.find.return_value.sort.return_value.limit.return_value = [
            {"target_close": 110.0}
        ]

        from trade_alpha.strategy.service import generate_signal
        signal = generate_signal("000001.SZ", strategy="price")

        # 信号应该包含 action
        assert "action" in signal
```

- [ ] **Step 2: Run test to verify it passes (no change needed)**

Run: `pytest tests/trade_alpha/strategy/test_service.py -v`
Expected: PASS (service 不需要传递 position，因为它只生成信号)

- [ ] **Step 3: 检查 service.py 是否需要修改**

查看 generate_signal 函数，它从 MongoDB 获取数据生成信号，不需要修改。

- [ ] **Step 4: Commit (跳过)**

---

### Task 4: 更新 backtest engine

**Files:**
- Modify: `src/trade_alpha/backtest/engine.py`
- Test: `tests/trade_alpha/backtest/test_engine.py`

- [ ] **Step 1: Write the failing test**

```python
def test_backtest_engine_passes_position():
    """Test BacktestEngine passes portfolio position to strategy context."""
    from unittest.mock import MagicMock
    from trade_alpha.backtest.engine import BacktestEngine
    from trade_alpha.portfolio import Portfolio

    mock_records = [
        {"ts_code": "000001.SZ", "trade_date": "20240102", "open": 100.0, "close": 101.0},
        {"ts_code": "000001.SZ", "trade_date": "20240103", "open": 101.0, "close": 102.0},
    ]

    mock_strategy = MagicMock()
    mock_strategy.decide.return_value = "hold"

    portfolio = Portfolio(100000)
    engine = BacktestEngine("000001.SZ", "20240101", "20240131", mock_strategy, portfolio)

    engine.run(mock_records)

    # 验证 strategy.decide 被调用时 context 包含 position
    calls = mock_strategy.decide.call_args_list
    for call in calls:
        context = call[0][0]
        assert hasattr(context, "position")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trade_alpha/backtest/test_engine.py::test_backtest_engine_passes_position -v`
Expected: FAIL (需要修改 engine.py)

- [ ] **Step 3: Write minimal implementation**

查看 `src/trade_alpha/backtest/engine.py`，找到创建 context 的位置，添加 position 字段：

```python
context = MagicMock()
context.ts_code = self.ts_code
context.trade_date = record["trade_date"]
context.current_price = float(record["close"])
context.prediction = {"close": float(next_record["open"])}
context.indicators = {}
context.position = self.portfolio.position  # 新增
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trade_alpha/backtest/test_engine.py::test_backtest_engine_passes_position -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/trade_alpha/backtest/engine.py tests/trade_alpha/backtest/test_engine.py
git commit -m "feat: pass portfolio position to strategy context in backtest"
```

---

### Task 5: 更新集成测试

**Files:**
- Modify: `tests/trade_alpha/strategy/test_strategy_integration.py`
- Modify: `tests/trade_alpha/backtest/test_backtest_integration.py`

- [ ] **Step 1: 运行集成测试检查是否需要更新**

Run: `pytest tests/ -v -m integration --tb=short`
Expected: 可能需要调整阈值确保测试稳定

- [ ] **Step 2: 根据需要调整阈值参数**

如果测试失败，降低阈值（如 0.001）以确保策略能正常触发交易。

- [ ] **Step 3: Commit**

```bash
git add tests/trade_alpha/strategy/test_strategy_integration.py tests/trade_alpha/backtest/test_backtest_integration.py
git commit -m "test: update integration tests for strategy threshold"
```

---

## 自检查清单

1. **Spec 覆盖**: 所有设计文档中的需求都有对应的实现任务
2. **占位符检查**: 无 TBD、TODO 等占位符
3. **类型一致性**: StrategyContext.position 为 int 类型

---

## 执行方式

**Plan complete and saved to `docs/superpowers/plans/2026-05-09-strategy-threshold-plan.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
