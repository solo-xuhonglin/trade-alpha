# MA与MACD策略实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 MAStrategy 和 MACDStrategy 两个基于技术指标的交易策略

**Architecture:** 两个策略类独立实现，继承 BaseStrategy，通过 context.indicators 获取指标数据，根据 context.position 判断持仓状态

**Tech Stack:** Python, pandas, pytest

---

## 文件结构

```
src/trade_alpha/strategy/
├── base.py          # BaseStrategy, StrategyContext (已有)
├── price.py         # PriceStrategy (已有)
├── ma.py            # MAStrategy (新增)
└── macd.py          # MACDStrategy (新增)

tests/trade_alpha/strategy/
├── test_price.py    # PriceStrategy tests (已有)
├── test_ma.py       # MAStrategy tests (新增)
└── test_macd.py     # MACDStrategy tests (新增)
```

---

## Task 1: 实现 MAStrategy

**Files:**
- Create: `src/trade_alpha/strategy/ma.py`
- Test: `tests/trade_alpha/strategy/test_ma.py`

- [ ] **Step 1: 创建 MAStrategy 实现**

```python
"""Moving average based strategy."""

from trade_alpha.strategy.base import BaseStrategy, StrategyContext


class MAStrategy(BaseStrategy):
    """Strategy based on price vs MA crossover with threshold."""

    def __init__(
        self,
        ma_period: int = 20,
        threshold: float = 0.01,
    ):
        self.ma_period = ma_period
        self.threshold = threshold

    def decide(self, context: StrategyContext) -> str:
        ma_key = f"ma_{self.ma_period}"
        ma_value = context.indicators.get(ma_key)
        if ma_value is None:
            return "hold"

        diff_pct = (context.current_price - ma_value) / ma_value

        if context.position == 0:
            if diff_pct >= self.threshold:
                return "buy"
        else:
            if diff_pct <= -self.threshold:
                return "sell"
        return "hold"
```

- [ ] **Step 2: 编写测试用例**

```python
import pytest
from trade_alpha.strategy.ma import MAStrategy
from trade_alpha.strategy.base import StrategyContext


class TestMAStrategy:
    def test_buy_when_price_above_ma_with_threshold(self):
        strategy = MAStrategy(ma_period=20, threshold=0.01)
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=110.0,
            prediction={},
            indicators={"ma_20": 100.0},
            position=0,
        )
        assert strategy.decide(context) == "buy"

    def test_hold_when_price_above_ma_below_threshold(self):
        strategy = MAStrategy(ma_period=20, threshold=0.05)
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=103.0,
            prediction={},
            indicators={"ma_20": 100.0},
            position=0,
        )
        assert strategy.decide(context) == "hold"

    def test_sell_when_price_below_ma_with_threshold(self):
        strategy = MAStrategy(ma_period=20, threshold=0.01)
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=90.0,
            prediction={},
            indicators={"ma_20": 100.0},
            position=100,
        )
        assert strategy.decide(context) == "sell"

    def test_hold_when_no_ma_indicator(self):
        strategy = MAStrategy(ma_period=20, threshold=0.01)
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=110.0,
            prediction={},
            indicators={},
            position=0,
        )
        assert strategy.decide(context) == "hold"

    def test_default_threshold(self):
        strategy = MAStrategy(ma_period=20)
        assert strategy.threshold == 0.01
        assert strategy.ma_period == 20
```

- [ ] **Step 3: 运行测试验证**

Run: `pytest tests/trade_alpha/strategy/test_ma.py -v`
Expected: 5 passed

---

## Task 2: 实现 MACDStrategy

**Files:**
- Create: `src/trade_alpha/strategy/macd.py`
- Test: `tests/trade_alpha/strategy/test_macd.py`

- [ ] **Step 1: 创建 MACDStrategy 实现**

```python
"""MACD based strategy."""

from trade_alpha.strategy.base import BaseStrategy, StrategyContext


class MACDStrategy(BaseStrategy):
    """Strategy based on MACD vs signal line crossover with threshold."""

    def __init__(
        self,
        threshold: float = 0.5,
    ):
        self.threshold = threshold

    def decide(self, context: StrategyContext) -> str:
        macd = context.indicators.get("macd")
        signal = context.indicators.get("macd_signal")
        if macd is None or signal is None:
            return "hold"

        diff = macd - signal

        if context.position == 0:
            if diff >= self.threshold:
                return "buy"
        else:
            if diff <= -self.threshold:
                return "sell"
        return "hold"
```

- [ ] **Step 2: 编写测试用例**

```python
import pytest
from trade_alpha.strategy.macd import MACDStrategy
from trade_alpha.strategy.base import StrategyContext


class TestMACDStrategy:
    def test_buy_when_macd_above_signal_with_threshold(self):
        strategy = MACDStrategy(threshold=0.5)
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=100.0,
            prediction={},
            indicators={"macd": 2.0, "macd_signal": 1.0},
            position=0,
        )
        assert strategy.decide(context) == "buy"

    def test_hold_when_macd_above_signal_below_threshold(self):
        strategy = MACDStrategy(threshold=5.0)
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=100.0,
            prediction={},
            indicators={"macd": 2.0, "macd_signal": 1.0},
            position=0,
        )
        assert strategy.decide(context) == "hold"

    def test_sell_when_macd_below_signal_with_threshold(self):
        strategy = MACDStrategy(threshold=0.5)
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=100.0,
            prediction={},
            indicators={"macd": -2.0, "macd_signal": 1.0},
            position=100,
        )
        assert strategy.decide(context) == "sell"

    def test_hold_when_no_macd_indicator(self):
        strategy = MACDStrategy(threshold=0.5)
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=100.0,
            prediction={},
            indicators={},
            position=0,
        )
        assert strategy.decide(context) == "hold"

    def test_default_threshold(self):
        strategy = MACDStrategy()
        assert strategy.threshold == 0.5
```

- [ ] **Step 3: 运行测试验证**

Run: `pytest tests/trade_alpha/strategy/test_macd.py -v`
Expected: 5 passed

---

## Task 3: 运行完整测试套件

- [ ] **Step 1: 运行所有策略相关测试**

Run: `pytest tests/trade_alpha/strategy/ -v`
Expected: test_price.py (6) + test_ma.py (5) + test_macd.py (5) = 16 passed

- [ ] **Step 2: 运行完整测试套件确保无回归**

Run: `pytest tests/ -v`
Expected: 所有测试通过

---

## Task 4: 提交代码

- [ ] **Step 1: 提交变更**

```bash
git add src/trade_alpha/strategy/ma.py src/trade_alpha/strategy/macd.py
git add tests/trade_alpha/strategy/test_ma.py tests/trade_alpha/strategy/test_macd.py
git commit -m "feat: add MAStrategy and MACDStrategy"
```
