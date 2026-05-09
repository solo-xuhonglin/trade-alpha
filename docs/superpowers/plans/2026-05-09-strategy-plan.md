# 交易策略模块实现计划

> **For agentic workers:** Use superpowers:executing-plans skill to implement this plan task-by-task.

**Goal:** 实现交易策略模块，根据预测价格生成交易信号

**Architecture:** 采用计算与存储分离的设计。strategy 负责纯决策逻辑，service 负责编排数据流和存储

**Tech Stack:** Python 标准库 (dataclass)

---

## Task 1: 创建 strategy 模块结构

**Files:**
- Create: `src/trade_alpha/strategy/__init__.py`
- Create: `src/trade_alpha/strategy/base.py`
- Create: `src/trade_alpha/strategy/price.py`
- Create: `src/trade_alpha/strategy/service.py`

- [ ] **Step 1: 创建 `__init__.py`**

```python
"""Trading strategy module."""

from trade_alpha.strategy.base import BaseStrategy, StrategyContext
from trade_alpha.strategy.price import PriceStrategy
from trade_alpha.strategy.service import generate_signal

__all__ = ["BaseStrategy", "StrategyContext", "PriceStrategy", "generate_signal"]
```

- [ ] **Step 2: 创建 `base.py`**

```python
"""Base strategy interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class StrategyContext:
    """Strategy context data."""
    ts_code: str
    trade_date: str
    current_price: float
    prediction: dict[str, float]
    indicators: dict[str, float]


class BaseStrategy(ABC):
    """Abstract base class for all strategies."""

    @abstractmethod
    def decide(self, context: StrategyContext) -> str:
        """Make trading decision.

        Args:
            context: Strategy context with current price, prediction, indicators

        Returns:
            Trading action: "buy", "sell", "hold"
        """
        pass
```

- [ ] **Step 3: 创建 `price.py`**

```python
"""Price-based strategy."""

from trade_alpha.strategy.base import BaseStrategy, StrategyContext


class PriceStrategy(BaseStrategy):
    """Simple strategy based on predicted price vs current price."""

    def decide(self, context: StrategyContext) -> str:
        """Make decision based on predicted close price.

        Buy if predicted close > current price, otherwise hold.
        """
        target_price = context.prediction.get("close")
        if target_price is None:
            return "hold"

        if target_price > context.current_price:
            return "buy"
        return "hold"
```

- [ ] **Step 4: 创建 `service.py`**

```python
"""Strategy service."""

from datetime import datetime
from trade_alpha.db.storage import Storage
from trade_alpha.strategy.base import StrategyContext
from trade_alpha.strategy.price import PriceStrategy


STRATEGIES = {
    "price": PriceStrategy,
}


def generate_signal(
    ts_code: str,
    strategy: str = "price"
) -> dict[str, any]:
    """Generate trading signal and store to database.

    Args:
        ts_code: Stock code
        strategy: Strategy name, default "price"

    Returns:
        Signal result dictionary
    """
    storage = Storage()
    records = storage.find_by_ts_code(ts_code)

    if not records:
        storage.close()
        return {}

    latest = records[-1]

    prediction = {}
    pred_records = list(storage._get_collection("predictions").find(
        {"ts_code": ts_code},
        {"_id": 0, "target_open": 1, "target_close": 1, "target_high": 1, "target_low": 1}
    ).sort("trade_date", -1).limit(1))
    if pred_records:
        pred = pred_records[0]
        prediction = {
            "open": pred.get("target_open"),
            "close": pred.get("target_close"),
            "high": pred.get("target_high"),
            "low": pred.get("target_low"),
        }

    indicator_cols = [col for col in latest.keys() if col.startswith(("ma_", "macd"))]
    indicators = {col: latest[col] for col in indicator_cols if latest.get(col) is not None}

    context = StrategyContext(
        ts_code=ts_code,
        trade_date=latest["trade_date"],
        current_price=float(latest["close"]),
        prediction=prediction,
        indicators=indicators,
    )

    strategy_cls = STRATEGIES.get(strategy)
    if strategy_cls is None:
        storage.close()
        return {}

    action = strategy_cls().decide(context)

    today = datetime.now().strftime("%Y%m%d")

    signal_record = {
        "ts_code": ts_code,
        "trade_date": today,
        "strategy": strategy,
        "action": action,
        "current_price": context.current_price,
        "target_price": prediction.get("close"),
        "reason": f"{strategy} strategy",
    }

    storage.insert_many([signal_record], collection="signals")
    storage.close()

    return {
        "action": action,
        "current_price": context.current_price,
        "target_price": prediction.get("close"),
        "reason": signal_record["reason"],
    }
```

- [ ] **Step 5: 提交**

```bash
git add src/trade_alpha/strategy/
git commit -m "feat: add strategy module with price strategy"
```

---

## Task 2: 更新数据库表结构文档

**Files:**
- Modify: `docs/database-schema.md`

- [ ] **Step 1: 添加 signals 集合文档**

在 `database-schema.md` 末尾添加：

```markdown
### signals

存储交易信号。

**索引**: `{ts_code: 1, trade_date: 1, strategy: 1}` 联合唯一索引

**字段**:

| 字段 | 类型 | 说明 |
|-----|------|------|
| `ts_code` | string | 股票代码 |
| `trade_date` | string | 决策日期 (YYYYMMDD) |
| `strategy` | string | 策略名称 (e.g., "price") |
| `action` | string | 交易动作 ("buy" / "sell" / "hold") |
| `current_price` | float | 当前价格 |
| `target_price` | float | 目标价格 |
| `reason` | string | 决策原因 |
```

- [ ] **Step 2: 提交**

```bash
git add docs/database-schema.md
git commit -m "docs: add signals collection schema"
```

---

## Task 3: 更新 system-design.md

**Files:**
- Modify: `docs/system-design.md`

- [ ] **Step 1: 更新技术架构图**

添加 Strategy 模块到架构图：

```markdown
                    ┌─────────────┐
                    │   Predict   │
                    │   Module    │
                    └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Strategy   │
                    │   Module    │
                    └─────────────┘
```

- [ ] **Step 2: 添加策略模块说明**

添加新章节：

```markdown
### 6. 策略模块 (strategy)

**base.py** - 策略基类：
- `StrategyContext`: 策略上下文数据
- `BaseStrategy`: 抽象基类，定义 decide 接口

**price.py** - 价格策略：
- `PriceStrategy`: 基于预测价格决策

**service.py** - 策略服务：
- `generate_signal()`: 生成交易信号并存储
```

- [ ] **Step 3: 更新项目结构**

```markdown
└── predict/
│   └── strategy/            # 策略模块
│       ├── base.py        # 策略基类
│       ├── price.py       # 价格策略
│       └── service.py     # 策略服务
```

- [ ] **Step 4: 更新已实现功能**

```markdown
- [x] 策略层：交易信号生成（价格策略）
```

- [ ] **Step 5: 提交**

```bash
git add docs/system-design.md
git commit -m "docs: add strategy module to system design"
```

---

## Task 4: 单元测试

**Files:**
- Create: `tests/trade_alpha/strategy/__init__.py`
- Create: `tests/trade_alpha/strategy/test_price.py`
- Create: `tests/trade_alpha/strategy/test_service.py`

- [ ] **Step 1: 创建 `__init__.py`**

```python
```

- [ ] **Step 2: 创建 `test_price.py`**

```python
"""Tests for price strategy."""

import pytest
from trade_alpha.strategy.base import StrategyContext
from trade_alpha.strategy.price import PriceStrategy


class TestPriceStrategy:
    def test_buy_when_price_rises(self):
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=100.0,
            prediction={"close": 110.0},
            indicators={},
        )

        strategy = PriceStrategy()
        result = strategy.decide(context)

        assert result == "buy"

    def test_hold_when_price_falls(self):
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=100.0,
            prediction={"close": 90.0},
            indicators={},
        )

        strategy = PriceStrategy()
        result = strategy.decide(context)

        assert result == "hold"

    def test_hold_when_no_prediction(self):
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=100.0,
            prediction={},
            indicators={},
        )

        strategy = PriceStrategy()
        result = strategy.decide(context)

        assert result == "hold"
```

- [ ] **Step 3: 创建 `test_service.py`**

```python
"""Tests for strategy service."""

import pytest
from unittest.mock import MagicMock, patch
from trade_alpha.strategy.service import generate_signal


class TestStrategyService:
    @patch("trade_alpha.strategy.service.Storage")
    def test_generate_signal_no_data(self, mock_storage_class):
        mock_storage = MagicMock()
        mock_storage.find_by_ts_code.return_value = []
        mock_storage_class.return_value = mock_storage

        result = generate_signal("000001.SZ")

        assert result == {}
        mock_storage.close.assert_called_once()

    @patch("trade_alpha.strategy.service.Storage")
    def test_generate_signal_success(self, mock_storage_class):
        mock_storage = MagicMock()
        mock_storage.find_by_ts_code.return_value = [
            {"trade_date": "20240101", "close": 100.0},
        ]
        mock_storage._get_collection.return_value.find.return_value.sort.return_value.limit.return_value = [
            {"target_close": 110.0}
        ]
        mock_storage_class.return_value = mock_storage

        result = generate_signal("000001.SZ")

        assert "action" in result
        assert result["action"] == "buy"
        mock_storage.insert_many.assert_called_once()
        mock_storage.close.assert_called_once()
```

- [ ] **Step 4: 运行测试**

```bash
pytest tests/trade_alpha/strategy/ -v
```

- [ ] **Step 5: 提交**

```bash
git add tests/trade_alpha/strategy/
git commit -m "test: add strategy module tests"
```

---

## Task 5: 集成测试

**Files:**
- Create: `tests/trade_alpha/strategy/test_strategy_integration.py`

- [ ] **Step 1: 创建集成测试**

```python
"""Integration tests for strategy module."""

import pytest
from trade_alpha.data import fetch_and_store
from trade_alpha.indicators import calculate_and_store_ma
from trade_alpha.predict import predict
from trade_alpha.strategy import generate_signal
from trade_alpha.db.storage import Storage


@pytest.mark.integration
class TestStrategyIntegration:
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.storage = Storage()
        self.ts_code = "002594.SZ"

        yield

        self.storage.close()

    def cleanup_signals(self):
        coll = self.storage._get_collection("signals")
        coll.delete_many({"ts_code": self.ts_code})

    def test_generate_signal_real_data(self):
        """Test: fetch -> indicators -> predict -> signal"""
        self.cleanup_signals()

        self.storage._get_collection("daily").delete_many({"ts_code": self.ts_code})
        fetch_and_store(self.ts_code, "20240101", "20240131")

        calculate_and_store_ma(self.ts_code, periods=[5, 10])

        predict(self.ts_code, targets=["close"])

        signal = generate_signal(self.ts_code, strategy="price")

        assert "action" in signal
        assert signal["action"] in ["buy", "sell", "hold"]
        assert signal["current_price"] > 0
```

- [ ] **Step 2: 运行集成测试**

```bash
pytest tests/trade_alpha/strategy/test_strategy_integration.py -v -m integration
```

- [ ] **Step 3: 提交**

```bash
git add tests/trade_alpha/strategy/test_strategy_integration.py
git commit -m "test: add strategy integration test"
```

---

## 总结

完成以上任务后，策略模块将具备：
1. 策略基类和上下文
2. 价格策略实现
3. 交易信号生成和存储
4. 完整的单元测试和集成测试
