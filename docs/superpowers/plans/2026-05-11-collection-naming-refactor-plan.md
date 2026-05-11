# 集合名称重命名实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 MongoDB 集合名称统一为两个单词，重命名 6 个实体类和集合名称，更新所有相关引用。

**Architecture:** 
- 重命名 DAO 层实体类（Portfolio→AccountConfig, Strategy→StrategyConfig, Prediction→PredictionResult, Training→TrainingResult, Signal→SignalResult, Backtest→BacktestResult）
- 更新集合名称为两个单词（account_configs, strategy_configs, prediction_results, training_results, signal_results, backtest_results）
- 更新所有 Service、API 路由和测试文件的导入和变量名
- 删除旧集合，运行测试重新生成数据

**Tech Stack:** Python, Beanie ODM, MongoDB, FastAPI, pytest

---

## 阶段 1: 数据库清理

### Task 1: 删除旧集合

**Files:**
- Modify: `backend/cleanup_db.py` - 添加删除旧集合的代码

- [ ] **Step 1: 更新清理脚本，删除旧集合**

```python
# 在 cleanup_db.py 中添加
async def cleanup():
    """Clean up test data from database."""
    await init_db()
    db = await get_database()
    
    print("Cleaning up test database...")
    
    # 删除旧集合
    old_collections = [
        "portfolios", "strategies", "predictions", 
        "trainings", "signals", "backtests"
    ]
    
    for coll_name in old_collections:
        try:
            await db.drop_collection(coll_name)
            print(f"Dropped collection: {coll_name}")
        except Exception as e:
            print(f"Warning: Could not drop {coll_name}: {e}")
    
    # 保留 stock_daily, stock_list, model_configs, backtest_trades
    print("\nDatabase cleanup complete!")
```

- [ ] **Step 2: 运行清理脚本**

Run: `cd backend && python cleanup_db.py`
Expected: 删除 portfolios, strategies, predictions, trainings, signals, backtests 集合

- [ ] **Step 3: 提交变更**

Run:
```bash
git add backend/cleanup_db.py
git commit -m "chore: add cleanup script for old collection names"
```

---

## 阶段 2: DAO 层修改

### Task 2: 重命名 Portfolio → AccountConfig

**Files:**
- Modify: `backend/src/trade_alpha/dao/portfolio.py` - 重命名类和集合名
- Modify: `backend/src/trade_alpha/dao/__init__.py` - 更新导入

- [ ] **Step 1: 更新 portfolio.py**

```python
# backend/src/trade_alpha/dao/portfolio.py
"""AccountConfig Document model."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document, PydanticObjectId


class AccountConfig(Document):
    """Account config document for MongoDB."""
    
    name: str
    initial_capital: float
    buy_fee_rate: float = Field(default=0.0003)
    sell_fee_rate: float = Field(default=0.0003)
    stamp_tax_rate: float = Field(default=0.001)
    min_fee: float = Field(default=5.0)
    cash: float = Field(default=0.0)
    position: int = Field(default=0)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Settings:
        collection = "account_configs"
        indexes = [
            "name",
        ]
    
    def __init__(self, **data):
        super().__init__(**data)
        if self.cash == 0.0:
            self.cash = self.initial_capital
```

- [ ] **Step 2: 更新 dao/__init__.py**

```python
# backend/src/trade_alpha/dao/__init__.py
"""DAO module with Beanie Document models."""

from trade_alpha.dao.mongodb import init_db, get_db, close_db
from trade_alpha.dao.portfolio import AccountConfig
from trade_alpha.dao.strategy import StrategyConfig
from trade_alpha.dao.model_config import ModelConfig
from trade_alpha.dao.training import TrainingResult
from trade_alpha.dao.backtest import BacktestResult
from trade_alpha.dao.backtest_trade import BacktestTrade
from trade_alpha.dao.prediction import PredictionResult
from trade_alpha.dao.signal import SignalResult
from trade_alpha.dao.stock_daily import StockDaily
from trade_alpha.dao.stock_list import StockList

__all__ = [
    "init_db",
    "get_db",
    "close_db",
    "AccountConfig",
    "StrategyConfig",
    "ModelConfig",
    "TrainingResult",
    "BacktestResult",
    "BacktestTrade",
    "PredictionResult",
    "SignalResult",
    "StockDaily",
    "StockList",
]
```

- [ ] **Step 3: 提交变更**

Run:
```bash
git add backend/src/trade_alpha/dao/portfolio.py backend/src/trade_alpha/dao/__init__.py
git commit -m "refactor: rename Portfolio to AccountConfig, portfolios to account_configs"
```

---

### Task 3: 重命名 Strategy → StrategyConfig

**Files:**
- Modify: `backend/src/trade_alpha/dao/strategy.py` - 重命名类和集合名
- Modify: `backend/src/trade_alpha/dao/__init__.py` - 更新导入（已完成）

- [ ] **Step 1: 更新 strategy.py**

```python
# backend/src/trade_alpha/dao/strategy.py
"""StrategyConfig Document model."""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import Field
from beanie import Document


class StrategyConfig(Document):
    """Strategy config document for MongoDB."""
    
    name: str
    type: str = Field(default="price")
    config: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Settings:
        collection = "strategy_configs"
        indexes = [
            "name",
        ]
```

- [ ] **Step 2: 提交变更**

Run:
```bash
git add backend/src/trade_alpha/dao/strategy.py
git commit -m "refactor: rename Strategy to StrategyConfig, strategies to strategy_configs"
```

---

### Task 4: 重命名 Prediction → PredictionResult

**Files:**
- Modify: `backend/src/trade_alpha/dao/prediction.py` - 重命名类和集合名

- [ ] **Step 1: 更新 prediction.py**

```python
# backend/src/trade_alpha/dao/prediction.py
"""PredictionResult Document model."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document


class PredictionResult(Document):
    """Prediction result document for MongoDB."""
    
    ts_code: str
    trade_date: str
    model: str
    target_open: Optional[float] = None
    target_close: Optional[float] = None
    target_high: Optional[float] = None
    target_low: Optional[float] = None
    created_at: Optional[datetime] = None
    
    class Settings:
        collection = "prediction_results"
        indexes = [
            "ts_code",
            "trade_date",
        ]
```

- [ ] **Step 2: 提交变更**

Run:
```bash
git add backend/src/trade_alpha/dao/prediction.py
git commit -m "refactor: rename Prediction to PredictionResult, predictions to prediction_results"
```

---

### Task 5: 重命名 Training → TrainingResult

**Files:**
- Modify: `backend/src/trade_alpha/dao/training.py` - 重命名类和集合名

- [ ] **Step 1: 更新 training.py**

```python
# backend/src/trade_alpha/dao/training.py
"""TrainingResult Document model."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import Field
from beanie import Document, PydanticObjectId


class TrainingResult(Document):
    """Training result document for MongoDB."""
    
    config_id: PydanticObjectId
    name: str
    ts_codes: List[str] = Field(default_factory=list)
    start_date: str
    end_date: str
    feature_cols: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    model_path: Optional[str] = None
    created_at: Optional[datetime] = None
    
    class Settings:
        collection = "training_results"
        indexes = [
            "name",
            "config_id",
        ]
```

- [ ] **Step 2: 提交变更**

Run:
```bash
git add backend/src/trade_alpha/dao/training.py
git commit -m "refactor: rename Training to TrainingResult, trainings to training_results"
```

---

### Task 6: 重命名 Signal → SignalResult

**Files:**
- Modify: `backend/src/trade_alpha/dao/signal.py` - 重命名类和集合名

- [ ] **Step 1: 更新 signal.py**

```python
# backend/src/trade_alpha/dao/signal.py
"""SignalResult Document model."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document


class SignalResult(Document):
    """Signal result document for MongoDB."""
    
    ts_code: str
    trade_date: str
    strategy: str
    action: str
    current_price: float
    target_price: Optional[float] = None
    reason: str
    created_at: Optional[datetime] = None
    
    class Settings:
        collection = "signal_results"
        indexes = [
            "ts_code",
            "trade_date",
        ]
```

- [ ] **Step 2: 提交变更**

Run:
```bash
git add backend/src/trade_alpha/dao/signal.py
git commit -m "refactor: rename Signal to SignalResult, signals to signal_results"
```

---

### Task 7: 重命名 Backtest → BacktestResult

**Files:**
- Modify: `backend/src/trade_alpha/dao/backtest.py` - 重命名类和集合名

- [ ] **Step 1: 更新 backtest.py**

```python
# backend/src/trade_alpha/dao/backtest.py
"""BacktestResult Document model."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document, PydanticObjectId


class BacktestResult(Document):
    """Backtest result document for MongoDB."""
    
    portfolio_id: Optional[PydanticObjectId] = None
    strategy_id: Optional[PydanticObjectId] = None
    training_id: Optional[PydanticObjectId] = None
    ts_code: str
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float
    total_return: float
    annual_return: float
    benchmark_return: float = Field(default=0.0)
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    total_trades: int
    total_fees: float
    created_at: Optional[datetime] = None
    
    class Settings:
        collection = "backtest_results"
        indexes = [
            "ts_code",
            "portfolio_id",
            "strategy_id",
        ]
```

- [ ] **Step 2: 提交变更**

Run:
```bash
git add backend/src/trade_alpha/dao/backtest.py
git commit -m "refactor: rename Backtest to BacktestResult, backtests to backtest_results"
```

---

## 阶段 3: Service 层修改

### Task 8: 更新 portfolio/service.py

**Files:**
- Modify: `backend/src/trade_alpha/portfolio/service.py` - 更新导入和变量名

- [ ] **Step 1: 更新 portfolio/service.py**

```python
# backend/src/trade_alpha/portfolio/service.py
# 更新所有 Portfolio → AccountConfig 的引用
# 更新所有 from trade_alpha.dao import Portfolio → from trade_alpha.dao import AccountConfig
```

关键修改点：
- 类名：`Portfolio` → `AccountConfig`
- 导入：`from trade_alpha.dao import Portfolio` → `from trade_alpha.dao import AccountConfig`
- 所有变量名：`portfolio` → `account_config`（如适用）

- [ ] **Step 2: 提交变更**

Run:
```bash
git add backend/src/trade_alpha/portfolio/service.py
git commit -m "refactor: update portfolio service to use AccountConfig"
```

---

### Task 9: 更新 strategy/service.py

**Files:**
- Modify: `backend/src/trade_alpha/strategy/service.py` - 更新导入和变量名

- [ ] **Step 1: 更新 strategy/service.py**

```python
# backend/src/trade_alpha/strategy/service.py
# 更新所有 Strategy → StrategyConfig 的引用
```

关键修改点：
- 类名：`Strategy` → `StrategyConfig`
- 导入：`from trade_alpha.dao import Strategy` → `from trade_alpha.dao import StrategyConfig`

- [ ] **Step 2: 提交变更**

Run:
```bash
git add backend/src/trade_alpha/strategy/service.py
git commit -m "refactor: update strategy service to use StrategyConfig"
```

---

### Task 10: 更新 predict/service.py

**Files:**
- Modify: `backend/src/trade_alpha/predict/service.py` - 更新导入和变量名

- [ ] **Step 1: 更新 predict/service.py**

```python
# backend/src/trade_alpha/predict/service.py
# 更新所有 Prediction → PredictionResult 的引用
```

关键修改点：
- 类名：`Prediction` → `PredictionResult`
- 导入：`from trade_alpha.dao import Prediction` → `from trade_alpha.dao import PredictionResult`

- [ ] **Step 2: 提交变更**

Run:
```bash
git add backend/src/trade_alpha/predict/service.py
git commit -m "refactor: update predict service to use PredictionResult"
```

---

### Task 11: 更新 predict/training_service.py

**Files:**
- Modify: `backend/src/trade_alpha/predict/training_service.py` - 更新导入和变量名

- [ ] **Step 1: 更新 predict/training_service.py**

```python
# backend/src/trade_alpha/predict/training_service.py
# 更新所有 Training → TrainingResult 的引用
```

关键修改点：
- 类名：`Training` → `TrainingResult`
- 导入：`from trade_alpha.dao import Training` → `from trade_alpha.dao import TrainingResult`

- [ ] **Step 2: 提交变更**

Run:
```bash
git add backend/src/trade_alpha/predict/training_service.py
git commit -m "refactor: update training service to use TrainingResult"
```

---

### Task 12: 更新 backtest/service.py

**Files:**
- Modify: `backend/src/trade_alpha/backtest/service.py` - 更新导入和变量名

- [ ] **Step 1: 更新 backtest/service.py**

```python
# backend/src/trade_alpha/backtest/service.py
# 更新所有 Backtest → BacktestResult 的引用
# 更新所有 Signal → SignalResult 的引用
```

关键修改点：
- 类名：`Backtest` → `BacktestResult`
- 类名：`Signal` → `SignalResult`
- 导入：`from trade_alpha.dao import Backtest, Signal` → `from trade_alpha.dao import BacktestResult, SignalResult`

- [ ] **Step 2: 提交变更**

Run:
```bash
git add backend/src/trade_alpha/backtest/service.py
git commit -m "refactor: update backtest service to use BacktestResult and SignalResult"
```

---

## 阶段 4: API 路由层修改

### Task 13: 更新 API 路由导入

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/portfolio.py` - 更新导入
- Modify: `backend/src/trade_alpha/api/routers/strategy.py` - 更新导入
- Modify: `backend/src/trade_alpha/api/routers/predict.py` - 更新导入
- Modify: `backend/src/trade_alpha/api/routers/backtest.py` - 更新导入

- [ ] **Step 1: 更新 portfolio.py**

```python
# backend/src/trade_alpha/api/routers/portfolio.py
# 更新 from trade_alpha.dao import Portfolio → from trade_alpha.dao import AccountConfig
```

- [ ] **Step 2: 更新 strategy.py**

```python
# backend/src/trade_alpha/api/routers/strategy.py
# 更新 from trade_alpha.dao import Strategy → from trade_alpha.dao import StrategyConfig
```

- [ ] **Step 3: 更新 predict.py**

```python
# backend/src/trade_alpha/api/routers/predict.py
# 更新 from trade_alpha.dao import Prediction → from trade_alpha.dao import PredictionResult
```

- [ ] **Step 4: 更新 backtest.py**

```python
# backend/src/trade_alpha/api/routers/backtest.py
# 更新 from trade_alpha.dao import Backtest → from trade_alpha.dao import BacktestResult
# 更新 from trade_alpha.dao import Signal → from trade_alpha.dao import SignalResult
```

- [ ] **Step 5: 提交所有 API 路由变更**

Run:
```bash
git add backend/src/trade_alpha/api/routers/portfolio.py backend/src/trade_alpha/api/routers/strategy.py backend/src/trade_alpha/api/routers/predict.py backend/src/trade_alpha/api/routers/backtest.py
git commit -m "refactor: update API routers to use new DAO class names"
```

---

## 阶段 5: 测试层修改

### Task 14: 更新集成测试

**Files:**
- Modify: `backend/tests/trade_alpha/integration/*.py` - 所有集成测试文件

- [ ] **Step 1: 批量更新导入语句**

使用 grep 查找并替换：
```bash
# 在 tests/trade_alpha/integration/ 目录下
# Portfolio → AccountConfig
# Strategy → StrategyConfig
# Prediction → PredictionResult
# Training → TrainingResult
# Signal → SignalResult
# Backtest → BacktestResult
```

需要更新的文件：
- `test_41_portfolio_service.py` - Portfolio → AccountConfig
- `test_43_strategy_service.py` - Strategy → StrategyConfig
- `test_43_model_config_service.py` - Training → TrainingResult
- `test_51_training_service.py` - Training → TrainingResult
- `test_60_backtest.py` - Backtest → BacktestResult, Signal → SignalResult

- [ ] **Step 2: 提交测试变更**

Run:
```bash
git add backend/tests/trade_alpha/integration/
git commit -m "refactor: update integration tests to use new DAO class names"
```

---

## 阶段 6: 文档更新

### Task 15: 更新文档

**Files:**
- Modify: `docs/system-design.md` - 更新 DAO 模块说明
- Modify: `docs/database-schema.md` - 更新集合名称

- [ ] **Step 1: 更新 system-design.md**

```markdown
### 3. DAO 模块 (dao)

使用 Beanie ODM 异步数据访问层：

- `mongodb.py`: MongoDB 连接管理和 Beanie 初始化
- `stock_daily.py`: 股票日线数据 Document
- `stock_list.py`: 股票列表 Document
- `portfolio.py`: 账户 Document
- `strategy.py`: 策略 Document
- `model_config.py`: 模型配置 Document
- `training.py`: 训练记录 Document
- `backtest.py`: 回测记录 Document
- `backtest_trade.py`: 回测交易 Document
- `prediction.py`: 预测结果 Document
- `signal.py`: 交易信号 Document
```

改为：

```markdown
### 3. DAO 模块 (dao)

使用 Beanie ODM 异步数据访问层：

- `mongodb.py`: MongoDB 连接管理和 Beanie 初始化
- `stock_daily.py`: 股票日线数据 Document
- `stock_list.py`: 股票列表 Document
- `account_config.py`: 账户配置 Document
- `strategy_config.py`: 策略配置 Document
- `model_config.py`: 模型配置 Document
- `training_result.py`: 训练结果 Document
- `backtest_result.py`: 回测结果 Document
- `backtest_trade.py`: 回测交易 Document
- `prediction_result.py`: 预测结果 Document
- `signal_result.py`: 交易信号 Document
```

- [ ] **Step 2: 更新 database-schema.md**

更新所有集合名称：
- portfolios → account_configs
- strategies → strategy_configs
- predictions → prediction_results
- trainings → training_results
- signals → signal_results
- backtests → backtest_results

- [ ] **Step 3: 提交文档变更**

Run:
```bash
git add docs/system-design.md docs/database-schema.md
git commit -m "docs: update docs for collection naming changes"
```

---

## 阶段 7: 验证测试

### Task 16: 运行集成测试

- [ ] **Step 1: 运行集成测试**

Run: `cd backend && python -m pytest tests/trade_alpha/integration/ -v`
Expected: 所有 48 个测试通过

- [ ] **Step 2: 如果测试失败，调试并修复**

根据错误信息修复问题，可能需要检查：
- 导入语句是否正确
- 类名是否一致
- 变量名是否更新

- [ ] **Step 3: 提交测试修复**

Run:
```bash
git add backend/tests/
git commit -m "fix: resolve test issues from collection naming changes"
```

---

### Task 17: 运行 E2E 测试

- [ ] **Step 1: 启动后端服务**

Run: `cd backend && uvicorn trade_alpha.api.main:app --reload --port 8000`

- [ ] **Step 2: 启动前端服务**

Run: `cd frontend && npm run dev`

- [ ] **Step 3: 运行 E2E 测试**

Run: `cd frontend/e2e && python -m pytest tests/ -v --base-url=http://localhost:3000`
Expected: 所有 27 个测试通过

- [ ] **Step 4: 提交 E2E 测试修复（如有）**

---

### Task 18: 最终提交

- [ ] **Step 1: 推送所有变更**

Run:
```bash
git push
```

- [ ] **Step 2: 最终验证**

确认：
- 所有集合名称已更新
- 所有测试通过
- 文档已更新

---

## 预期结果

✅ 所有集合名称统一为两个单词：
- account_configs
- strategy_configs
- prediction_results
- training_results
- signal_results
- backtest_results

✅ 类名与集合名保持一致

✅ 所有 48 个集成测试通过

✅ 所有 27 个 E2E 测试通过

✅ 文档更新完成
