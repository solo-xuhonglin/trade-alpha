# 预测层实现计划

> **For agentic workers:** Use superpowers:executing-plans skill to implement this plan task-by-task.

**Goal:** 实现预测模块，支持多种模型预测，当前仅实现线性回归

**Architecture:** 采用计算与存储分离的设计。predictor 负责纯计算，service 负责编排数据流和存储

**Tech Stack:** scikit-learn (线性回归), numpy, pandas

---

## 依赖检查

需要确保 scikit-learn 已安装，检查 pyproject.toml

---

## Task 1: 依赖添加

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 检查并添加 scikit-learn 依赖**

```toml
# pyproject.toml 添加
dependencies = [
    ...
    "scikit-learn>=1.4.0",
]
```

- [ ] **Step 2: 安装依赖**

```bash
pip install scikit-learn
```

- [ ] **Step 3: 提交**

```bash
git add pyproject.toml
git commit -m "deps: add scikit-learn for prediction"
```

---

## Task 2: 创建 predict 模块结构

**Files:**
- Create: `src/trade_alpha/predict/__init__.py`
- Create: `src/trade_alpha/predict/base.py`
- Create: `src/trade_alpha/predict/linear.py`
- Create: `src/trade_alpha/predict/service.py`

- [ ] **Step 1: 创建 `__init__.py`**

```python
"""Stock prediction module."""

from trade_alpha.predict.base import BasePredictor
from trade_alpha.predict.linear import LinearPredictor
from trade_alpha.predict.service import predict

__all__ = ["BasePredictor", "LinearPredictor", "predict"]
```

- [ ] **Step 2: 创建 `base.py`**

```python
"""Base predictor interface."""

from abc import ABC, abstractmethod
import numpy as np


class BasePredictor(ABC):
    """Abstract base class for all predictors."""

    @abstractmethod
    def predict(self, features: np.ndarray, targets: list[str]) -> dict[str, float]:
        """Predict using trained model.

        Args:
            features: Feature matrix (n_samples, n_features)
            targets: List of target names (e.g., ["open", "close"])

        Returns:
            Dictionary mapping target names to predicted values
        """
        pass
```

- [ ] **Step 3: 创建 `linear.py`**

```python
"""Linear regression predictor."""

import numpy as np
from sklearn.linear_model import LinearRegression
from trade_alpha.predict.base import BasePredictor


class LinearPredictor(BasePredictor):
    """Linear regression predictor for multiple targets."""

    def __init__(self):
        self.models: dict[str, LinearRegression] = {}

    def fit(self, X: np.ndarray, y: np.ndarray, targets: list[str]) -> None:
        """Train the model.

        Args:
            X: Feature matrix (n_samples, n_features)
            y: Target matrix (n_samples, n_targets)
            targets: List of target names
        """
        self.models = {}
        for i, target in enumerate(targets):
            model = LinearRegression()
            model.fit(X, y[:, i])
            self.models[target] = model

    def predict(self, features: np.ndarray, targets: list[str]) -> dict[str, float]:
        """Predict using trained model.

        Args:
            features: Feature matrix (n_samples, n_features)
            targets: List of target names

        Returns:
            Dictionary mapping target names to predicted values
        """
        result = {}
        for target in targets:
            if target in self.models:
                result[target] = self.models[target].predict(features)[0]
        return result
```

- [ ] **Step 4: 创建 `service.py`**

```python
"""Prediction service."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from trade_alpha.db.storage import Storage
from trade_alpha.predict.linear import LinearPredictor


def predict(
    ts_code: str,
    targets: list[str] | None = None,
    model: str = "linear",
    start_date: str | None = None,
    end_date: str | None = None
) -> dict[str, float]:
    """Predict stock prices and store results.

    Args:
        ts_code: Stock code
        targets: List of prediction targets, default ["open", "close", "high", "low"]
        model: Model name, default "linear"
        start_date: Training data start date (YYYYMMDD)
        end_date: Training data end date (YYYYMMDD)

    Returns:
        Prediction results dictionary
    """
    if targets is None:
        targets = ["open", "close", "high", "low"]

    storage = Storage()
    records = storage.find_by_ts_code(ts_code)

    if not records:
        storage.close()
        return {}

    df = pd.DataFrame(records)

    if start_date:
        df = df[df["trade_date"] >= start_date]
    if end_date:
        df = df[df["trade_date"] <= end_date]

    if len(df) < 10:
        storage.close()
        return {}

    features_cols = ["open", "high", "low", "close", "vol"]
    indicator_cols = [col for col in df.columns if col.startswith(("ma_", "macd"))]

    all_feature_cols = features_cols + indicator_cols
    all_feature_cols = [col for col in all_feature_cols if col in df.columns]

    df = df.dropna(subset=all_feature_cols + targets)

    if len(df) < 10:
        storage.close()
        return {}

    X = df[all_feature_cols].values[:-1]
    y = df[targets].values[1:]

    predictor = LinearPredictor()
    predictor.fit(X, y, targets)

    last_features = df[all_feature_cols].iloc[-1:].values
    predictions = predictor.predict(last_features, targets)

    last_date = df["trade_date"].iloc[-1]
    next_date = (datetime.strptime(last_date, "%Y%m%d") + timedelta(days=1)).strftime("%Y%m%d")

    result_record = {
        "ts_code": ts_code,
        "trade_date": next_date,
        "model": model,
    }
    for target in targets:
        result_record[f"target_{target}"] = predictions.get(target)

    storage.insert_many([result_record], collection="predictions")
    storage.close()

    return predictions
```

- [ ] **Step 5: 提交**

```bash
git add src/trade_alpha/predict/
git commit -m "feat: add predict module with linear regression"
```

---

## Task 3: 数据库表结构更新

**Files:**
- Modify: `docs/database-schema.md`

- [ ] **Step 1: 添加 predictions 集合文档**

在 `database-schema.md` 中添加：

```markdown
### predictions

存储预测结果。

**索引**: `{ts_code: 1, trade_date: 1, model: 1}` 联合唯一索引

**字段**:

| 字段 | 类型 | 说明 |
|-----|------|------|
| `ts_code` | string | 股票代码 |
| `trade_date` | string | 预测日期 (YYYYMMDD) |
| `model` | string | 模型名称 (e.g., "linear") |
| `target_open` | float | 预测开盘价 |
| `target_close` | float | 预测收盘价 |
| `target_high` | float | 预测最高价 |
| `target_low` | float | 预测最低价 |
```

- [ ] **Step 2: 提交**

```bash
git add docs/database-schema.md
git commit -m "docs: add predictions collection schema"
```

---

## Task 4: 更新 system-design.md

**Files:**
- Modify: `docs/system-design.md`

- [ ] **Step 1: 添加预测模块说明**

在 "已实现功能" 部分添加：
```markdown
- [x] 预测层：价格预测（线性回归）
```

- [ ] **Step 2: 添加预测模块文档**

添加新章节：

```markdown
### 5. 预测模块 (predict)

**base.py** - 预测基类：
- `BasePredictor`: 抽象基类，定义 predict 接口

**linear.py** - 线性回归预测器：
- `LinearPredictor`: 使用 scikit-learn 线性回归

**service.py** - 预测服务：
- `predict()`: 预测并存储结果
```

- [ ] **Step 3: 更新项目结构**

```markdown
└── indicators/
│   └── predict/            # 预测模块
│       ├── base.py        # 预测基类
│       ├── linear.py      # 线性回归
│       └── service.py     # 预测服务
```

- [ ] **Step 4: 提交**

```bash
git add docs/system-design.md
git commit -m "docs: add predict module to system design"
```

---

## Task 5: 单元测试

**Files:**
- Create: `tests/trade_alpha/predict/__init__.py`
- Create: `tests/trade_alpha/predict/test_linear.py`
- Create: `tests/trade_alpha/predict/test_service.py`

- [ ] **Step 1: 创建测试目录 `__init__.py`**

```python
```

- [ ] **Step 2: 创建 `test_linear.py`**

```python
"""Tests for linear predictor."""

import numpy as np
import pytest
from trade_alpha.predict.linear import LinearPredictor


class TestLinearPredictor:
    def test_fit_and_predict(self):
        X = np.array([[1, 2], [2, 3], [3, 4], [4, 5], [5, 6]])
        y = np.array([[2, 3], [3, 4], [4, 5], [5, 6], [6, 7]])
        targets = ["target_a", "target_b"]

        predictor = LinearPredictor()
        predictor.fit(X, y, targets)

        result = predictor.predict([[5, 6]], targets)

        assert "target_a" in result
        assert "target_b" in result
        assert isinstance(result["target_a"], float)
        assert isinstance(result["target_b"], float)

    def test_predict_single_target(self):
        X = np.array([[1], [2], [3], [4]])
        y = np.array([[2], [3], [4], [5]])
        targets = ["output"]

        predictor = LinearPredictor()
        predictor.fit(X, y, targets)

        result = predictor.predict([[5]], targets)

        assert "output" in result
        assert result["output"] > 5
```

- [ ] **Step 3: 创建 `test_service.py`**

```python
"""Tests for prediction service."""

import pytest
from unittest.mock import MagicMock, patch
from trade_alpha.predict.service import predict


class TestPredictService:
    @patch("trade_alpha.predict.service.Storage")
    def test_predict_with_no_data(self, mock_storage_class):
        mock_storage = MagicMock()
        mock_storage.find_by_ts_code.return_value = []
        mock_storage_class.return_value = mock_storage

        result = predict("000001.SZ")

        assert result == {}
        mock_storage.close.assert_called_once()

    @patch("trade_alpha.predict.service.Storage")
    def test_predict_success(self, mock_storage_class):
        mock_storage = MagicMock()
        mock_storage.find_by_ts_code.return_value = [
            {"trade_date": "20240101", "open": 10, "high": 11, "low": 9, "close": 10.5, "vol": 100, "ma_5": 10.2},
            {"trade_date": "20240102", "open": 10.5, "high": 11.5, "low": 10, "close": 11, "vol": 110, "ma_5": 10.4},
            {"trade_date": "20240103", "open": 11, "high": 12, "low": 10.5, "close": 11.5, "vol": 120, "ma_5": 10.8},
        ]
        mock_storage_class.return_value = mock_storage

        result = predict("000001.SZ", targets=["open", "close"])

        assert "open" in result
        assert "close" in result
        mock_storage.insert_many.assert_called_once()
        mock_storage.close.assert_called_once()
```

- [ ] **Step 4: 运行测试**

```bash
pytest tests/trade_alpha/predict/ -v
```

- [ ] **Step 5: 提交**

```bash
git add tests/trade_alpha/predict/
git commit -m "test: add predict module tests"
```

---

## Task 6: 集成测试

**Files:**
- Create: `tests/trade_alpha/predict/test_predict_integration.py`

- [ ] **Step 1: 创建集成测试**

```python
"""Integration tests for prediction module."""

import pytest
from trade_alpha.predict import predict


@pytest.mark.integration
class TestPredictIntegration:
    def test_predict_real_data(self):
        result = predict(
            ts_code="000001.SZ",
            targets=["open", "close"],
            model="linear",
            start_date="20230101",
            end_date="20231231"
        )

        assert "open" in result
        assert "close" in result
        assert result["open"] > 0
        assert result["close"] > 0
```

- [ ] **Step 2: 运行集成测试**

```bash
pytest tests/trade_alpha/predict/test_predict_integration.py -v -m integration
```

- [ ] **Step 3: 提交**

```bash
git add tests/trade_alpha/predict/test_predict_integration.py
git commit -m "test: add predict integration test"
```

---

## 总结

完成以上任务后，预测模块将具备：
1. 线性回归预测器
2. 统一接口支持扩展
3. 预测结果存储到 MongoDB
4. 完整的单元测试
