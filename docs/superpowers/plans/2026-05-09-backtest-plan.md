# 回测模块实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现回测模块和账户管理模块，支持策略验证、风险评估和交易记录持久化

**Architecture:** 采用计算与存储分离的设计模式，portfolio 模块负责账户管理，backtest 模块负责回测引擎和指标计算

**Tech Stack:** Python 3.14+, MongoDB, pytest, pytest-order

---

## 文件结构

```
src/trade_alpha/
├── portfolio/           # 账户管理模块
│   ├── __init__.py      # 模块导出
│   └── portfolio.py     # 账户资金管理类
├── backtest/            # 回测模块
│   ├── __init__.py      # 模块导出
│   ├── engine.py        # 回测引擎
│   ├── metrics.py       # 指标计算
│   └── service.py       # 服务层（持久化）
tests/trade_alpha/
├── portfolio/
│   └── test_portfolio.py
└── backtest/
    ├── test_engine.py
    ├── test_metrics.py
    └── test_backtest_integration.py
```

---

### Task 1: 创建 portfolio 模块

**Files:**
- Create: `src/trade_alpha/portfolio/__init__.py`
- Create: `src/trade_alpha/portfolio/portfolio.py`
- Create: `tests/trade_alpha/portfolio/test_portfolio.py`

- [ ] **Step 1: Write the failing test**

```python
"""Unit tests for portfolio module."""

import pytest
from trade_alpha.portfolio import Portfolio, Trade


class TestPortfolio:
    """Test cases for Portfolio class."""

    def test_initial_balance(self):
        """Test initial portfolio balance."""
        portfolio = Portfolio(100000)
        assert portfolio.cash == 100000
        assert portfolio.position == 0

    def test_buy(self):
        """Test buying shares."""
        portfolio = Portfolio(100000)
        trade = portfolio.buy("20240102", 100.0, 100)
        assert trade.action == "buy"
        assert trade.shares == 100
        assert trade.price == 100.0
        assert portfolio.position == 100
        assert portfolio.cash < 100000

    def test_sell(self):
        """Test selling shares."""
        portfolio = Portfolio(100000)
        portfolio.buy("20240102", 100.0, 100)
        trade = portfolio.sell("20240103", 105.0, 100)
        assert trade.action == "sell"
        assert portfolio.position == 0
        assert portfolio.cash > 90000

    def test_fee_calculation(self):
        """Test fee calculation with minimum fee."""
        portfolio = Portfolio(100000)
        # Small trade should apply minimum fee of 5 yuan
        trade = portfolio.buy("20240102", 100.0, 10)  # 1000 yuan
        assert trade.fee == 5.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trade_alpha/portfolio/test_portfolio.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'trade_alpha.portfolio'"

- [ ] **Step 3: Write minimal implementation**

**src/trade_alpha/portfolio/portfolio.py:**

```python
"""Portfolio management module."""

from dataclasses import dataclass


@dataclass
class Trade:
    """Trade record."""
    date: str
    action: str
    price: float
    shares: int
    fee: float
    cash_after: float
    position_after: int


class Portfolio:
    """Account portfolio management."""

    def __init__(
        self,
        initial_capital: float,
        buy_fee_rate: float = 0.0003,
        sell_fee_rate: float = 0.0003,
        stamp_tax_rate: float = 0.001,
        min_fee: float = 5.0,
    ):
        self.cash = initial_capital
        self.position = 0
        self.buy_fee_rate = buy_fee_rate
        self.sell_fee_rate = sell_fee_rate
        self.stamp_tax_rate = stamp_tax_rate
        self.min_fee = min_fee
        self.trades: list[Trade] = []

    def _calculate_buy_fee(self, price: float, shares: int) -> float:
        """Calculate buy fee."""
        amount = price * shares
        fee = amount * self.buy_fee_rate
        return max(fee, self.min_fee)

    def _calculate_sell_fee(self, price: float, shares: int) -> float:
        """Calculate sell fee including stamp tax."""
        amount = price * shares
        fee = amount * self.sell_fee_rate + amount * self.stamp_tax_rate
        return max(fee, self.min_fee)

    def buy(self, date: str, price: float, shares: int) -> Trade:
        """Buy shares."""
        fee = self._calculate_buy_fee(price, shares)
        total_cost = price * shares + fee
        
        if total_cost > self.cash:
            raise ValueError("Insufficient cash")
        
        self.cash -= total_cost
        self.position += shares
        
        trade = Trade(
            date=date,
            action="buy",
            price=price,
            shares=shares,
            fee=fee,
            cash_after=self.cash,
            position_after=self.position,
        )
        self.trades.append(trade)
        return trade

    def sell(self, date: str, price: float, shares: int) -> Trade:
        """Sell shares."""
        if shares > self.position:
            raise ValueError("Insufficient position")
        
        fee = self._calculate_sell_fee(price, shares)
        total_revenue = price * shares - fee
        
        self.cash += total_revenue
        self.position -= shares
        
        trade = Trade(
            date=date,
            action="sell",
            price=price,
            shares=shares,
            fee=fee,
            cash_after=self.cash,
            position_after=self.position,
        )
        self.trades.append(trade)
        return trade
```

**src/trade_alpha/portfolio/__init__.py:**

```python
"""Portfolio module."""

from trade_alpha.portfolio.portfolio import Portfolio, Trade

__all__ = ["Portfolio", "Trade"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trade_alpha/portfolio/test_portfolio.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/trade_alpha/portfolio/ tests/trade_alpha/portfolio/
git commit -m "feat: add portfolio module"
```

---

### Task 2: 创建 backtest 模块 - engine.py

**Files:**
- Create: `src/trade_alpha/backtest/__init__.py`
- Create: `src/trade_alpha/backtest/engine.py`
- Create: `tests/trade_alpha/backtest/test_engine.py`

- [ ] **Step 1: Write the failing test**

```python
"""Unit tests for backtest engine."""

import pytest
from unittest.mock import MagicMock
from trade_alpha.backtest.engine import BacktestEngine
from trade_alpha.portfolio import Portfolio
from trade_alpha.strategy.price import PriceStrategy


class TestBacktestEngine:
    """Test cases for BacktestEngine."""

    def test_run_backtest(self):
        """Test running backtest with mock data."""
        mock_records = [
            {"ts_code": "000001.SZ", "trade_date": "20240102", "open": 100.0, "close": 101.0},
            {"ts_code": "000001.SZ", "trade_date": "20240103", "open": 101.0, "close": 102.0},
            {"ts_code": "000001.SZ", "trade_date": "20240104", "open": 102.0, "close": 100.0},
        ]
        
        strategy = MagicMock()
        strategy.decide.return_value = "buy"
        
        portfolio = Portfolio(100000)
        engine = BacktestEngine("000001.SZ", "20240101", "20240131", strategy, portfolio)
        
        result = engine.run(mock_records)
        
        assert result.initial_capital == 100000
        assert result.total_trades >= 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trade_alpha/backtest/test_engine.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'trade_alpha.backtest'"

- [ ] **Step 3: Write minimal implementation**

**src/trade_alpha/backtest/engine.py:**

```python
"""Backtest engine module."""

from dataclasses import dataclass
from typing import List, Dict
from trade_alpha.portfolio import Portfolio, Trade


@dataclass
class BacktestResult:
    """Backtest result container."""
    backtest_id: str = ""
    portfolio_id: str = ""
    ts_code: str = ""
    start_date: str = ""
    end_date: str = ""
    strategy: str = ""
    initial_capital: float = 0.0
    final_value: float = 0.0
    total_return: float = 0.0
    annual_return: float = 0.0
    benchmark_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    total_fees: float = 0.0


class BacktestEngine:
    """Backtest engine for running trading strategies on historical data."""

    def __init__(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
        strategy,
        portfolio: Portfolio,
    ):
        self.ts_code = ts_code
        self.start_date = start_date
        self.end_date = end_date
        self.strategy = strategy
        self.portfolio = portfolio
        self.daily_values = []

    def run(self, records: List[Dict]) -> BacktestResult:
        """Run backtest on historical data."""
        if not records:
            return BacktestResult(
                ts_code=self.ts_code,
                start_date=self.start_date,
                end_date=self.end_date,
                initial_capital=self.portfolio.cash,
                final_value=self.portfolio.cash,
            )

        initial_capital = self.portfolio.cash
        
        for i, record in enumerate(records[:-1]):
            next_record = records[i + 1]
            
            context = MagicMock()
            context.ts_code = self.ts_code
            context.trade_date = record["trade_date"]
            context.current_price = float(record["close"])
            context.prediction = {"close": float(next_record["open"])}
            context.indicators = {}
            
            action = self.strategy.decide(context)
            
            if action == "buy" and self.portfolio.cash > 0:
                price = float(next_record["open"])
                max_shares = int(self.portfolio.cash / price)
                if max_shares > 0:
                    self.portfolio.buy(next_record["trade_date"], price, max_shares)
            
            elif action == "sell" and self.portfolio.position > 0:
                price = float(next_record["open"])
                self.portfolio.sell(next_record["trade_date"], price, self.portfolio.position)

            daily_value = self.portfolio.cash + self.portfolio.position * float(record["close"])
            self.daily_values.append((record["trade_date"], daily_value))

        final_value = self.portfolio.cash + self.portfolio.position * float(records[-1]["close"])
        self.daily_values.append((records[-1]["trade_date"], final_value))
        
        total_return = (final_value - initial_capital) / initial_capital if initial_capital > 0 else 0
        
        return BacktestResult(
            ts_code=self.ts_code,
            start_date=self.start_date,
            end_date=self.end_date,
            strategy=str(self.strategy.__class__.__name__),
            initial_capital=initial_capital,
            final_value=final_value,
            total_return=total_return,
            total_trades=len(self.portfolio.trades),
            total_fees=sum(t.fee for t in self.portfolio.trades),
        )
```

**src/trade_alpha/backtest/__init__.py:**

```python
"""Backtest module."""

from trade_alpha.backtest.engine import BacktestEngine, BacktestResult

__all__ = ["BacktestEngine", "BacktestResult"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trade_alpha/backtest/test_engine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/trade_alpha/backtest/ tests/trade_alpha/backtest/
git commit -m "feat: add backtest engine"
```

---

### Task 3: 创建 metrics.py 指标计算模块

**Files:**
- Create: `src/trade_alpha/backtest/metrics.py`
- Modify: `tests/trade_alpha/backtest/test_engine.py`

- [ ] **Step 1: Write the failing test**

```python
"""Unit tests for metrics module."""

import pytest
from trade_alpha.backtest.metrics import calculate_metrics
from trade_alpha.portfolio import Trade


class TestMetrics:
    """Test cases for metrics calculation."""

    def test_total_return(self):
        """Test total return calculation."""
        trades = []
        daily_values = [
            ("20240102", 100000),
            ("20240103", 101000),
            ("20240104", 102000),
        ]
        result = calculate_metrics(trades, daily_values, 100000, 0.05)
        
        assert result.total_return == pytest.approx(0.02)

    def test_max_drawdown(self):
        """Test max drawdown calculation."""
        trades = []
        daily_values = [
            ("20240102", 100000),
            ("20240103", 105000),
            ("20240104", 102000),
            ("20240105", 98000),
        ]
        result = calculate_metrics(trades, daily_values, 100000, 0.05)
        
        assert result.max_drawdown == pytest.approx(0.0667, abs=0.01)

    def test_win_rate(self):
        """Test win rate calculation."""
        trades = [
            Trade("20240102", "buy", 100.0, 100, 5.0, 90000, 100),
            Trade("20240103", "sell", 105.0, 100, 15.5, 104984.5, 0),  # profitable
            Trade("20240104", "buy", 105.0, 100, 5.0, 94984.5, 100),
            Trade("20240105", "sell", 103.0, 100, 15.3, 103969.2, 0),  # losing
        ]
        daily_values = [("20240102", 100000)] * 4
        result = calculate_metrics(trades, daily_values, 100000, 0.05)
        
        assert result.win_rate == 0.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trade_alpha/backtest/test_metrics.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'trade_alpha.backtest.metrics'"

- [ ] **Step 3: Write minimal implementation**

**src/trade_alpha/backtest/metrics.py:**

```python
"""Metrics calculation module."""

from dataclasses import dataclass
from typing import List, Tuple
from trade_alpha.portfolio import Trade


@dataclass
class Metrics:
    """Backtest metrics container."""
    total_return: float = 0.0
    annual_return: float = 0.0
    benchmark_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    avg_holding_days: float = 0.0
    total_fees: float = 0.0


def calculate_metrics(
    trades: List[Trade],
    daily_values: List[Tuple[str, float]],
    initial_capital: float,
    benchmark_return: float,
) -> Metrics:
    """Calculate backtest metrics."""
    if not daily_values:
        return Metrics(benchmark_return=benchmark_return)
    
    dates = [v[0] for v in daily_values]
    values = [v[1] for v in daily_values]
    
    total_return = (values[-1] - initial_capital) / initial_capital if initial_capital > 0 else 0.0
    
    days = (len(dates) - 1)
    annual_return = (1 + total_return) ** (365 / days) - 1 if days > 0 else 0.0
    
    max_drawdown = calculate_max_drawdown(values)
    
    returns = [(values[i] - values[i-1]) / values[i-1] for i in range(1, len(values))]
    sharpe_ratio = calculate_sharpe_ratio(returns)
    
    win_rate, profit_factor, avg_holding_days = calculate_trade_metrics(trades, dates)
    
    total_fees = sum(t.fee for t in trades)
    
    return Metrics(
        total_return=total_return,
        annual_return=annual_return,
        benchmark_return=benchmark_return,
        max_drawdown=max_drawdown,
        sharpe_ratio=sharpe_ratio,
        win_rate=win_rate,
        profit_factor=profit_factor,
        total_trades=len(trades),
        avg_holding_days=avg_holding_days,
        total_fees=total_fees,
    )


def calculate_max_drawdown(values: List[float]) -> float:
    """Calculate maximum drawdown."""
    if not values:
        return 0.0
    
    max_so_far = values[0]
    max_drawdown = 0.0
    
    for value in values[1:]:
        max_so_far = max(max_so_far, value)
        drawdown = (max_so_far - value) / max_so_far if max_so_far > 0 else 0.0
        max_drawdown = max(max_drawdown, drawdown)
    
    return max_drawdown


def calculate_sharpe_ratio(returns: List[float]) -> float:
    """Calculate Sharpe ratio (assuming 0 risk-free rate)."""
    if not returns:
        return 0.0
    
    import numpy as np
    mean_return = np.mean(returns)
    std_return = np.std(returns)
    
    if std_return == 0:
        return 0.0
    
    return mean_return / std_return * np.sqrt(252)


def calculate_trade_metrics(trades: List[Trade], dates: List[str]) -> Tuple[float, float, float]:
    """Calculate trade-related metrics."""
    if not trades:
        return 0.0, 0.0, 0.0
    
    buy_trades = [t for t in trades if t.action == "buy"]
    sell_trades = [t for t in trades if t.action == "sell"]
    
    winning_trades = 0
    total_profit = 0.0
    total_loss = 0.0
    holding_days = 0.0
    
    for i, buy in enumerate(buy_trades):
        if i < len(sell_trades):
            sell = sell_trades[i]
            profit = (sell.price - buy.price) * buy.shares - buy.fee - sell.fee
            if profit > 0:
                winning_trades += 1
                total_profit += profit
            else:
                total_loss += abs(profit)
    
    win_rate = winning_trades / len(buy_trades) if buy_trades else 0.0
    profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
    
    return win_rate, profit_factor, holding_days / len(buy_trades) if buy_trades else 0.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trade_alpha/backtest/test_metrics.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/trade_alpha/backtest/metrics.py tests/trade_alpha/backtest/test_metrics.py
git commit -m "feat: add metrics calculation"
```

---

### Task 4: 创建 service.py 服务层（持久化）

**Files:**
- Create: `src/trade_alpha/backtest/service.py`

- [ ] **Step 1: Write the failing test**

```python
"""Unit tests for backtest service."""

import pytest
from unittest.mock import MagicMock, patch
from trade_alpha.backtest.service import (
    create_portfolio,
    get_portfolio,
    save_backtest,
    save_trades,
)


class TestBacktestService:
    """Test cases for backtest service."""

    @patch("trade_alpha.backtest.service.MongoDB")
    def test_create_portfolio(self, mock_mongo):
        """Test creating portfolio."""
        mock_collection = MagicMock()
        mock_mongo.return_value._get_collection.return_value = mock_collection
        mock_collection.insert_one.return_value.inserted_id = "test_id"
        
        portfolio_id = create_portfolio("test_portfolio", 100000)
        
        assert portfolio_id == "test_id"
        mock_collection.insert_one.assert_called_once()

    @patch("trade_alpha.backtest.service.MongoDB")
    def test_get_portfolio(self, mock_mongo):
        """Test getting portfolio."""
        mock_collection = MagicMock()
        mock_mongo.return_value._get_collection.return_value = mock_collection
        mock_collection.find_one.return_value = {
            "_id": "test_id",
            "name": "test_portfolio",
            "initial_capital": 100000,
            "buy_fee_rate": 0.0003,
            "sell_fee_rate": 0.0003,
            "stamp_tax_rate": 0.001,
            "min_fee": 5.0,
        }
        
        portfolio = get_portfolio("test_portfolio")
        
        assert portfolio is not None
        assert portfolio["name"] == "test_portfolio"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trade_alpha/backtest/test_service.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'trade_alpha.backtest.service'"

- [ ] **Step 3: Write minimal implementation**

**src/trade_alpha/backtest/service.py:**

```python
"""Backtest service module for persistence."""

from typing import Optional, Dict, List
from trade_alpha.dao import MongoDB
from trade_alpha.portfolio import Portfolio, Trade
from trade_alpha.backtest.engine import BacktestResult


def create_portfolio(
    name: str,
    initial_capital: float,
    buy_fee_rate: float = 0.0003,
    sell_fee_rate: float = 0.0003,
    stamp_tax_rate: float = 0.001,
    min_fee: float = 5.0,
) -> str:
    """Create a new portfolio."""
    dao = MongoDB()
    collection = dao._get_collection("portfolios")
    
    portfolio_doc = {
        "name": name,
        "initial_capital": initial_capital,
        "buy_fee_rate": buy_fee_rate,
        "sell_fee_rate": sell_fee_rate,
        "stamp_tax_rate": stamp_tax_rate,
        "min_fee": min_fee,
        "cash": initial_capital,
        "position": 0,
    }
    
    result = collection.insert_one(portfolio_doc)
    dao.close()
    return str(result.inserted_id)


def get_portfolio(name: str) -> Optional[Dict]:
    """Get portfolio by name."""
    dao = MongoDB()
    collection = dao._get_collection("portfolios")
    result = collection.find_one({"name": name})
    dao.close()
    return result


def get_portfolio_by_id(portfolio_id: str) -> Optional[Dict]:
    """Get portfolio by ID."""
    from bson import ObjectId
    dao = MongoDB()
    collection = dao._get_collection("portfolios")
    result = collection.find_one({"_id": ObjectId(portfolio_id)})
    dao.close()
    return result


def portfolio_to_obj(portfolio_doc: Dict) -> Portfolio:
    """Convert portfolio document to Portfolio object."""
    return Portfolio(
        initial_capital=portfolio_doc["initial_capital"],
        buy_fee_rate=portfolio_doc["buy_fee_rate"],
        sell_fee_rate=portfolio_doc["sell_fee_rate"],
        stamp_tax_rate=portfolio_doc["stamp_tax_rate"],
        min_fee=portfolio_doc["min_fee"],
    )


def save_backtest(result: BacktestResult) -> str:
    """Save backtest result."""
    from bson import ObjectId
    
    dao = MongoDB()
    collection = dao._get_collection("backtests")
    
    backtest_doc = {
        "portfolio_id": ObjectId(result.portfolio_id) if result.portfolio_id else None,
        "ts_code": result.ts_code,
        "start_date": result.start_date,
        "end_date": result.end_date,
        "strategy": result.strategy,
        "initial_capital": result.initial_capital,
        "final_value": result.final_value,
        "total_return": result.total_return,
        "annual_return": result.annual_return,
        "benchmark_return": result.benchmark_return,
        "max_drawdown": result.max_drawdown,
        "sharpe_ratio": result.sharpe_ratio,
        "win_rate": result.win_rate,
        "total_trades": result.total_trades,
        "total_fees": result.total_fees,
    }
    
    result_obj = collection.insert_one(backtest_doc)
    backtest_id = str(result_obj.inserted_id)
    result.backtest_id = backtest_id
    dao.close()
    return backtest_id


def save_trades(backtest_id: str, portfolio_id: str, trades: List[Trade]) -> None:
    """Save trade records."""
    from bson import ObjectId
    
    dao = MongoDB()
    collection = dao._get_collection("backtest_trades")
    
    trade_docs = []
    for trade in trades:
        trade_doc = {
            "backtest_id": ObjectId(backtest_id),
            "portfolio_id": ObjectId(portfolio_id) if portfolio_id else None,
            "ts_code": "",
            "trade_date": trade.date,
            "action": trade.action,
            "price": trade.price,
            "shares": trade.shares,
            "fee": trade.fee,
            "cash_after": trade.cash_after,
            "position_after": trade.position_after,
        }
        trade_docs.append(trade_doc)
    
    if trade_docs:
        collection.insert_many(trade_docs)
    
    dao.close()


def run_backtest(
    ts_code: str,
    start_date: str,
    end_date: str,
    strategy: str = "price",
    portfolio_name: str = "default",
    initial_capital: float = 100000,
) -> BacktestResult:
    """Run backtest with the given parameters."""
    from trade_alpha.backtest.engine import BacktestEngine
    from trade_alpha.strategy import STRATEGIES
    
    dao = MongoDB()
    
    portfolio_doc = get_portfolio(portfolio_name)
    if not portfolio_doc:
        portfolio_id = create_portfolio(portfolio_name, initial_capital)
        portfolio_doc = get_portfolio(portfolio_name)
    else:
        portfolio_id = str(portfolio_doc["_id"])
    
    portfolio = portfolio_to_obj(portfolio_doc)
    
    records = dao.find_by_ts_code(ts_code)
    filtered_records = [
        r for r in records 
        if start_date <= r["trade_date"] <= end_date
    ]
    dao.close()
    
    if not filtered_records:
        return BacktestResult(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            strategy=strategy,
            initial_capital=initial_capital,
            final_value=initial_capital,
        )
    
    strategy_cls = STRATEGIES.get(strategy)
    if strategy_cls is None:
        raise ValueError(f"Unknown strategy: {strategy}")
    
    strategy_obj = strategy_cls()
    engine = BacktestEngine(ts_code, start_date, end_date, strategy_obj, portfolio)
    
    result = engine.run(filtered_records)
    result.portfolio_id = portfolio_id
    result.strategy = strategy
    
    backtest_id = save_backtest(result)
    save_trades(backtest_id, portfolio_id, portfolio.trades)
    
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trade_alpha/backtest/test_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/trade_alpha/backtest/service.py tests/trade_alpha/backtest/test_service.py
git commit -m "feat: add backtest service with persistence"
```

---

### Task 5: 创建集成测试

**Files:**
- Create: `tests/trade_alpha/backtest/test_backtest_integration.py`

- [ ] **Step 1: Write the failing test**

```python
"""Integration tests for backtest module."""

import pytest
from trade_alpha.backtest import run_backtest


class TestBacktestIntegration:
    """Integration tests for backtest module."""

    @pytest.mark.order(6)
    @pytest.mark.integration
    def test_run_backtest(self):
        """Test running backtest with real data."""
        result = run_backtest(
            ts_code="002594.SZ",
            start_date="20240101",
            end_date="20240131",
            strategy="price",
            portfolio_name="test_backtest",
            initial_capital=100000,
        )
        
        assert result.backtest_id is not None
        assert result.portfolio_id is not None
        assert result.ts_code == "002594.SZ"
        assert result.initial_capital == 100000
        assert result.final_value > 0
        assert isinstance(result.total_return, float)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/trade_alpha/backtest/test_backtest_integration.py -v`
Expected: FAIL with "ModuleNotFoundError" or test will run after previous tasks

- [ ] **Step 3: No implementation needed (uses existing code)**

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/trade_alpha/backtest/test_backtest_integration.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/trade_alpha/backtest/test_backtest_integration.py
git commit -m "test: add backtest integration tests"
```

---

### Task 6: 更新文档

**Files:**
- Update: `docs/system-design.md`
- Update: `docs/database-schema.md`
- Update: `README.md`

- [ ] **Step 1: Update system-design.md**

Add portfolio and backtest modules to the documentation.

- [ ] **Step 2: Update database-schema.md**

Add portfolios, backtests, backtest_trades collections.

- [ ] **Step 3: Update README.md**

Add backtest usage example.

- [ ] **Step 4: Commit**

```bash
git add docs/ README.md
git commit -m "docs: update documentation for portfolio and backtest modules"
```

---

## 自检查清单

1. **Spec 覆盖**: 所有设计文档中的需求都有对应的实现任务
2. **占位符检查**: 无 TBD、TODO 等占位符
3. **类型一致性**: 所有类型、方法签名和属性名称保持一致

---

## 执行方式

**Plan complete and saved to `docs/superpowers/plans/2026-05-09-backtest-plan.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?"**
