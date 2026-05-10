# 机器学习预测模块实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 XGBoost 和 LSTM 预测算法，实现模型持久化，统一使用 ID 作为资源标识。

**Architecture:** 扩展现有 predict 模块，新增 XGBoostPredictor 和 LSTMPredictor，添加模型管理服务实现持久化，调整策略 API 使用 ID。

**Tech Stack:** Python, XGBoost, PyTorch, MongoDB, FastAPI

---

## 文件结构

```
backend/
├── models/                        # 新建目录
│   ├── linear/
│   ├── xgboost/
│   └── lstm/
└── src/trade_alpha/
    ├── predict/
    │   ├── base.py               # 修改：添加 save/load
    │   ├── linear.py             # 修改：实现 save/load
    │   ├── xgboost.py            # 新建
    │   ├── lstm.py               # 新建
    │   ├── service.py            # 修改：支持模型选择
    │   └── model_service.py      # 新建
    ├── api/
    │   ├── routers/
    │   │   ├── models.py         # 新建
    │   │   └── strategy.py       # 修改：使用 ID
    │   └── schemas.py            # 修改：新增 schema
    └── strategy/
        └── service.py            # 修改：使用 ID
```

---

### Task 1: 更新 BasePredictor 添加持久化接口

**Files:**
- Modify: `backend/src/trade_alpha/predict/base.py`

- [ ] **Step 1: 更新 BasePredictor 基类**

```python
"""Base predictor interface."""

from abc import ABC, abstractmethod
import numpy as np


class BasePredictor(ABC):
    """Abstract base class for all predictors."""

    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray, targets: list[str]) -> None:
        """Train the model.

        Args:
            X: Feature matrix (n_samples, n_features)
            y: Target matrix (n_samples, n_targets)
            targets: List of target names
        """
        pass

    @abstractmethod
    def predict(self, features: np.ndarray, targets: list[str]) -> dict[str, float]:
        """Predict using trained model.

        Args:
            features: Feature matrix (n_samples, n_features)
            targets: List of target names

        Returns:
            Dictionary mapping target names to predicted values
        """
        pass

    @abstractmethod
    def save(self, path: str) -> None:
        """Save model to file.

        Args:
            path: File path to save model
        """
        pass

    @abstractmethod
    def load(self, path: str) -> None:
        """Load model from file.

        Args:
            path: File path to load model
        """
        pass
```

- [ ] **Step 2: 提交**

```bash
git add src/trade_alpha/predict/base.py
git commit -m "feat(predict): add save/load methods to BasePredictor"
```

---

### Task 2: 更新 LinearPredictor 实现持久化

**Files:**
- Modify: `backend/src/trade_alpha/predict/linear.py`

- [ ] **Step 1: 更新 LinearPredictor**

```python
"""Linear regression predictor."""

import pickle
import numpy as np
from sklearn.linear_model import LinearRegression
from trade_alpha.predict.base import BasePredictor


class LinearPredictor(BasePredictor):
    """Linear regression predictor for multiple targets."""

    def __init__(self):
        self.models: dict[str, LinearRegression] = {}

    def fit(self, X: np.ndarray, y: np.ndarray, targets: list[str]) -> None:
        """Train the model."""
        self.models = {}
        for i, target in enumerate(targets):
            model = LinearRegression()
            model.fit(X, y[:, i])
            self.models[target] = model

    def predict(self, features: np.ndarray, targets: list[str]) -> dict[str, float]:
        """Predict using trained model."""
        result = {}
        for target in targets:
            if target in self.models:
                result[target] = self.models[target].predict(features)[0]
        return result

    def save(self, path: str) -> None:
        """Save model to file."""
        with open(path, 'wb') as f:
            pickle.dump(self.models, f)

    def load(self, path: str) -> None:
        """Load model from file."""
        with open(path, 'rb') as f:
            self.models = pickle.load(f)
```

- [ ] **Step 2: 提交**

```bash
git add src/trade_alpha/predict/linear.py
git commit -m "feat(predict): implement save/load for LinearPredictor"
```

---

### Task 3: 实现 XGBoostPredictor

**Files:**
- Create: `backend/src/trade_alpha/predict/xgboost.py`

- [ ] **Step 1: 创建 XGBoostPredictor**

```python
"""XGBoost predictor."""

import pickle
import numpy as np
import xgboost as xgb
from trade_alpha.predict.base import BasePredictor


class XGBoostPredictor(BasePredictor):
    """XGBoost predictor for multiple targets."""

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 6,
        learning_rate: float = 0.1,
        min_child_weight: int = 1,
        subsample: float = 1.0,
        colsample_bytree: float = 1.0,
    ):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.min_child_weight = min_child_weight
        self.subsample = subsample
        self.colsample_bytree = colsample_bytree
        self.models: dict[str, xgb.XGBRegressor] = {}

    def fit(self, X: np.ndarray, y: np.ndarray, targets: list[str]) -> None:
        """Train the model."""
        self.models = {}
        for i, target in enumerate(targets):
            model = xgb.XGBRegressor(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                learning_rate=self.learning_rate,
                min_child_weight=self.min_child_weight,
                subsample=self.subsample,
                colsample_bytree=self.colsample_bytree,
            )
            model.fit(X, y[:, i])
            self.models[target] = model

    def predict(self, features: np.ndarray, targets: list[str]) -> dict[str, float]:
        """Predict using trained model."""
        result = {}
        for target in targets:
            if target in self.models:
                result[target] = self.models[target].predict(features)[0]
        return result

    def save(self, path: str) -> None:
        """Save model to file."""
        with open(path, 'wb') as f:
            pickle.dump(self.models, f)

    def load(self, path: str) -> None:
        """Load model from file."""
        with open(path, 'rb') as f:
            self.models = pickle.load(f)

    def get_feature_importance(self, target: str) -> dict[str, float]:
        """Get feature importance for a target."""
        if target not in self.models:
            return {}
        model = self.models[target]
        return dict(zip(
            model.feature_names_in_,
            model.feature_importances_
        ))
```

- [ ] **Step 2: 提交**

```bash
git add src/trade_alpha/predict/xgboost.py
git commit -m "feat(predict): add XGBoostPredictor"
```

---

### Task 4: 实现 LSTMPredictor

**Files:**
- Create: `backend/src/trade_alpha/predict/lstm.py`

- [ ] **Step 1: 创建 LSTMPredictor**

```python
"""LSTM predictor."""

import os
import numpy as np
import torch
import torch.nn as nn
from trade_alpha.predict.base import BasePredictor


class LSTMModel(nn.Module):
    """LSTM neural network model."""

    def __init__(self, input_size: int, hidden_size: int, num_layers: int, output_size: int, dropout: float = 0.1):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=dropout if num_layers > 1 else 0)
        self.fc = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size)
        out, _ = self.lstm(x, (h0, c0))
        out = self.fc(out[:, -1, :])
        return out


class LSTMPredictor(BasePredictor):
    """LSTM predictor for multiple targets."""

    def __init__(
        self,
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.1,
        epochs: int = 50,
        batch_size: int = 32,
        learning_rate: float = 0.001,
        sequence_length: int = 10,
    ):
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.dropout = dropout
        self.epochs = epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.sequence_length = sequence_length
        self.models: dict[str, LSTMModel] = {}
        self.input_size: int = 0
        self.scalers: dict[str, dict] = {}

    def _create_sequences(self, X: np.ndarray) -> np.ndarray:
        """Create sequences for LSTM input."""
        sequences = []
        for i in range(len(X) - self.sequence_length):
            sequences.append(X[i:i + self.sequence_length])
        return np.array(sequences)

    def fit(self, X: np.ndarray, y: np.ndarray, targets: list[str]) -> None:
        """Train the model."""
        self.input_size = X.shape[1]
        self.models = {}

        X_seq = self._create_sequences(X)
        y_seq = y[self.sequence_length:]

        for i, target in enumerate(targets):
            model = LSTMModel(
                input_size=self.input_size,
                hidden_size=self.hidden_size,
                num_layers=self.num_layers,
                output_size=1,
                dropout=self.dropout,
            )
            criterion = nn.MSELoss()
            optimizer = torch.optim.Adam(model.parameters(), lr=self.learning_rate)

            X_tensor = torch.FloatTensor(X_seq)
            y_tensor = torch.FloatTensor(y_seq[:, i]).unsqueeze(1)

            dataset = torch.utils.data.TensorDataset(X_tensor, y_tensor)
            loader = torch.utils.data.DataLoader(dataset, batch_size=self.batch_size, shuffle=True)

            model.train()
            for _ in range(self.epochs):
                for batch_X, batch_y in loader:
                    optimizer.zero_grad()
                    outputs = model(batch_X)
                    loss = criterion(outputs, batch_y)
                    loss.backward()
                    optimizer.step()

            self.models[target] = model

    def predict(self, features: np.ndarray, targets: list[str]) -> dict[str, float]:
        """Predict using trained model."""
        result = {}
        if len(features) < self.sequence_length:
            return result

        seq = features[-self.sequence_length:].reshape(1, self.sequence_length, -1)
        X_tensor = torch.FloatTensor(seq)

        for target in targets:
            if target in self.models:
                self.models[target].eval()
                with torch.no_grad():
                    pred = self.models[target](X_tensor)
                    result[target] = pred.item()
        return result

    def save(self, path: str) -> None:
        """Save model to file."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        state = {
            'models': {k: v.state_dict() for k, v in self.models.items()},
            'input_size': self.input_size,
            'hidden_size': self.hidden_size,
            'num_layers': self.num_layers,
            'sequence_length': self.sequence_length,
        }
        torch.save(state, path)

    def load(self, path: str) -> None:
        """Load model from file."""
        state = torch.load(path)
        self.input_size = state['input_size']
        self.hidden_size = state['hidden_size']
        self.num_layers = state['num_layers']
        self.sequence_length = state['sequence_length']
        self.models = {}
        for target, model_state in state['models'].items():
            model = LSTMModel(
                input_size=self.input_size,
                hidden_size=self.hidden_size,
                num_layers=self.num_layers,
                output_size=1,
            )
            model.load_state_dict(model_state)
            self.models[target] = model
```

- [ ] **Step 2: 提交**

```bash
git add src/trade_alpha/predict/lstm.py
git commit -m "feat(predict): add LSTMPredictor"
```

---

### Task 5: 创建模型管理服务

**Files:**
- Create: `backend/src/trade_alpha/predict/model_service.py`

- [ ] **Step 1: 创建 model_service.py**

```python
"""Model management service."""

import os
from datetime import datetime
from typing import Optional, Dict, Any
from bson import ObjectId
from trade_alpha.dao import MongoDB
from trade_alpha.predict.linear import LinearPredictor
from trade_alpha.predict.xgboost import XGBoostPredictor
from trade_alpha.predict.lstm import LSTMPredictor

MODELS_DIR = "models"

PREDICTORS = {
    "linear": LinearPredictor,
    "xgboost": XGBoostPredictor,
    "lstm": LSTMPredictor,
}


def _ensure_model_dirs():
    """Ensure model directories exist."""
    for model_type in PREDICTORS.keys():
        os.makedirs(os.path.join(MODELS_DIR, model_type), exist_ok=True)


def create_model(
    name: str,
    model_type: str,
    ts_code: str,
    targets: list[str],
    params: Dict[str, Any],
    start_date: str,
    end_date: str,
) -> str:
    """Train and save model, return model ID."""
    import pandas as pd
    import numpy as np
    from sklearn.metrics import mean_squared_error, mean_absolute_error

    _ensure_model_dirs()

    if model_type not in PREDICTORS:
        raise ValueError(f"Unknown model type: {model_type}")

    dao = MongoDB()
    records = dao.find_by_ts_code(ts_code)

    if not records:
        dao.close()
        raise ValueError(f"No data found for {ts_code}")

    df = pd.DataFrame(records)
    df = df[(df["trade_date"] >= start_date) & (df["trade_date"] <= end_date)]

    if len(df) < 20:
        dao.close()
        raise ValueError("Insufficient data for training")

    features_cols = ["open", "high", "low", "close", "vol"]
    indicator_cols = [col for col in df.columns if col.startswith(("ma_", "macd"))]
    all_feature_cols = [col for col in features_cols + indicator_cols if col in df.columns]

    df = df.dropna(subset=all_feature_cols + targets)
    df = df.sort_values("trade_date")

    X = df[all_feature_cols].values[:-1]
    y = df[targets].values[1:]

    predictor = PREDICTORS[model_type](**params)
    predictor.fit(X, y, targets)

    predictions = predictor.predict(df[all_feature_cols].iloc[-1:].values, targets)
    actuals = df[targets].iloc[-1].to_dict()

    mse = mean_squared_error(
        [actuals.get(t, 0) for t in targets],
        [predictions.get(t, 0) for t in targets]
    )
    mae = mean_absolute_error(
        [actuals.get(t, 0) for t in targets],
        [predictions.get(t, 0) for t in targets]
    )

    collection = dao._get_collection("models")
    model_doc = {
        "name": name,
        "model_type": model_type,
        "ts_code": ts_code,
        "targets": targets,
        "params": params,
        "feature_cols": all_feature_cols,
        "train_date_range": {"start": start_date, "end": end_date},
        "metrics": {"mse": float(mse), "mae": float(mae)},
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    result = collection.insert_one(model_doc)
    model_id = str(result.inserted_id)

    model_path = os.path.join(MODELS_DIR, model_type, f"{model_id}.pkl")
    predictor.save(model_path)

    collection.update_one(
        {"_id": ObjectId(model_id)},
        {"$set": {"model_path": model_path}}
    )

    dao.close()
    return model_id


def get_model_by_id(model_id: str) -> Optional[Dict]:
    """Get model by ID."""
    dao = MongoDB()
    collection = dao._get_collection("models")
    result = collection.find_one({"_id": ObjectId(model_id)})
    dao.close()
    return result


def list_models(model_type: str = None, ts_code: str = None) -> list[Dict]:
    """List models with optional filters."""
    dao = MongoDB()
    collection = dao._get_collection("models")

    query = {}
    if model_type:
        query["model_type"] = model_type
    if ts_code:
        query["ts_code"] = ts_code

    results = list(collection.find(query))
    dao.close()
    return results


def delete_model(model_id: str) -> bool:
    """Delete model and its file."""
    dao = MongoDB()
    collection = dao._get_collection("models")

    model = collection.find_one({"_id": ObjectId(model_id)})
    if not model:
        dao.close()
        return False

    if model.get("model_path") and os.path.exists(model["model_path"]):
        os.remove(model["model_path"])

    result = collection.delete_one({"_id": ObjectId(model_id)})
    dao.close()
    return result.deleted_count > 0


def predict_with_model(model_id: str, ts_code: str = None) -> Dict[str, float]:
    """Predict using saved model."""
    import pandas as pd

    model = get_model_by_id(model_id)
    if not model:
        raise ValueError(f"Model not found: {model_id}")

    ts_code = ts_code or model["ts_code"]

    dao = MongoDB()
    records = dao.find_by_ts_code(ts_code)
    dao.close()

    if not records:
        raise ValueError(f"No data found for {ts_code}")

    df = pd.DataFrame(records)
    df = df.sort_values("trade_date")

    all_feature_cols = model["feature_cols"]
    df = df.dropna(subset=all_feature_cols)

    predictor = PREDICTORS[model["model_type"]]()
    predictor.load(model["model_path"])

    last_features = df[all_feature_cols].iloc[-1:].values
    predictions = predictor.predict(last_features, model["targets"])

    return predictions
```

- [ ] **Step 2: 提交**

```bash
git add src/trade_alpha/predict/model_service.py
git commit -m "feat(predict): add model management service"
```

---

### Task 6: 更新 predict __init__.py

**Files:**
- Modify: `backend/src/trade_alpha/predict/__init__.py`

- [ ] **Step 1: 更新 __init__.py**

```python
"""Predict module."""

from trade_alpha.predict.base import BasePredictor
from trade_alpha.predict.linear import LinearPredictor
from trade_alpha.predict.xgboost import XGBoostPredictor
from trade_alpha.predict.lstm import LSTMPredictor

PREDICTORS = {
    "linear": LinearPredictor,
    "xgboost": XGBoostPredictor,
    "lstm": LSTMPredictor,
}

__all__ = ["BasePredictor", "LinearPredictor", "XGBoostPredictor", "LSTMPredictor", "PREDICTORS"]
```

- [ ] **Step 2: 提交**

```bash
git add src/trade_alpha/predict/__init__.py
git commit -m "feat(predict): export XGBoostPredictor and LSTMPredictor"
```

---

### Task 7: 新增 API Schema

**Files:**
- Modify: `backend/src/trade_alpha/api/schemas.py`

- [ ] **Step 1: 新增模型相关 Schema**

在文件末尾添加：

```python
class ModelCreateRequest(BaseModel):
    name: str
    model_type: str
    ts_code: str
    targets: list[str] = ["open", "close", "high", "low"]
    params: dict[str, Any] = {}
    start_date: str
    end_date: str


class ModelResponse(BaseModel):
    id: str
    name: str
    model_type: str
    ts_code: str
    targets: list[str]
    params: dict[str, Any]
    feature_cols: list[str]
    train_date_range: dict[str, str]
    metrics: dict[str, float]
    created_at: datetime
    updated_at: datetime


class PredictWithModelRequest(BaseModel):
    ts_code: Optional[str] = None
```

- [ ] **Step 2: 提交**

```bash
git add src/trade_alpha/api/schemas.py
git commit -m "feat(api): add model schemas"
```

---

### Task 8: 创建模型 API 路由

**Files:**
- Create: `backend/src/trade_alpha/api/routers/models.py`

- [ ] **Step 1: 创建 models.py**

```python
"""Model management API endpoints."""

from fastapi import APIRouter, HTTPException
from trade_alpha.api.schemas import ModelCreateRequest, ModelResponse, PredictWithModelRequest
from trade_alpha.predict import model_service

router = APIRouter(prefix="/models", tags=["models"])


@router.post("", response_model=dict)
def create_model(request: ModelCreateRequest):
    """Create and train a new model."""
    try:
        model_id = model_service.create_model(
            name=request.name,
            model_type=request.model_type,
            ts_code=request.ts_code,
            targets=request.targets,
            params=request.params,
            start_date=request.start_date,
            end_date=request.end_date,
        )
        return {"id": model_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[dict])
def list_models(model_type: str = None, ts_code: str = None):
    """List all models."""
    models = model_service.list_models(model_type=model_type, ts_code=ts_code)
    return [
        {
            "id": str(m["_id"]),
            "name": m["name"],
            "model_type": m["model_type"],
            "ts_code": m["ts_code"],
            "targets": m["targets"],
            "metrics": m["metrics"],
            "created_at": m["created_at"],
        }
        for m in models
    ]


@router.get("/{model_id}", response_model=ModelResponse)
def get_model(model_id: str):
    """Get model details."""
    model = model_service.get_model_by_id(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return ModelResponse(
        id=str(model["_id"]),
        name=model["name"],
        model_type=model["model_type"],
        ts_code=model["ts_code"],
        targets=model["targets"],
        params=model["params"],
        feature_cols=model["feature_cols"],
        train_date_range=model["train_date_range"],
        metrics=model["metrics"],
        created_at=model["created_at"],
        updated_at=model["updated_at"],
    )


@router.delete("/{model_id}")
def delete_model(model_id: str):
    """Delete a model."""
    deleted = model_service.delete_model(model_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"deleted": True}


@router.post("/{model_id}/predict")
def predict_with_model(model_id: str, request: PredictWithModelRequest = None):
    """Predict using a saved model."""
    try:
        ts_code = request.ts_code if request else None
        predictions = model_service.predict_with_model(model_id, ts_code)
        return {"model_id": model_id, "predictions": predictions}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 2: 提交**

```bash
git add src/trade_alpha/api/routers/models.py
git commit -m "feat(api): add models router"
```

---

### Task 9: 注册模型路由

**Files:**
- Modify: `backend/src/trade_alpha/api/main.py`

- [ ] **Step 1: 添加模型路由**

在 `app.include_router(predict_router)` 后添加：

```python
from trade_alpha.api.routers.models import router as models_router
app.include_router(models_router, prefix="/api")
```

- [ ] **Step 2: 提交**

```bash
git add src/trade_alpha/api/main.py
git commit -m "feat(api): register models router"
```

---

### Task 10: 更新策略服务使用 ID

**Files:**
- Modify: `backend/src/trade_alpha/strategy/service.py`

- [ ] **Step 1: 移除 get_strategy(name) 方法，保留 get_strategy_by_id**

删除 `get_strategy(name: str)` 方法，保留 `get_strategy_by_id`。

- [ ] **Step 2: 提交**

```bash
git add src/trade_alpha/strategy/service.py
git commit -m "refactor(strategy): remove get_strategy by name, use ID only"
```

---

### Task 11: 更新策略 API 使用 ID

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/strategy.py`

- [ ] **Step 1: 更新 API 路由使用 ID**

将 `GET /strategies/{name}` 改为 `GET /strategies/{id}`，其他同理。

- [ ] **Step 2: 提交**

```bash
git add src/trade_alpha/api/routers/strategy.py
git commit -m "refactor(api): strategy routes use ID instead of name"
```

---

### Task 12: 创建模型存储目录

**Files:**
- Create: `backend/models/.gitkeep`

- [ ] **Step 1: 创建目录结构**

```bash
mkdir -p models/linear models/xgboost models/lstm
touch models/.gitkeep models/linear/.gitkeep models/xgboost/.gitkeep models/lstm/.gitkeep
```

- [ ] **Step 2: 更新 .gitignore**

```
# 模型文件（保留目录结构）
models/**/*.pkl
models/**/*.pt
models/**/*.pth
!models/**/.gitkeep
```

- [ ] **Step 3: 提交**

```bash
git add models/ .gitignore
git commit -m "chore: create models directory structure"
```

---

### Task 13: 更新依赖

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: 添加依赖**

```
xgboost>=2.0.0
torch>=2.0.0
```

- [ ] **Step 2: 提交**

```bash
git add requirements.txt
git commit -m "chore: add xgboost and torch dependencies"
```

---

### Task 14: 添加集成测试

**Files:**
- Create: `backend/tests/trade_alpha/integration/test_40_model_service.py`

- [ ] **Step 1: 创建集成测试**

```python
"""Integration tests for model service."""

import pytest
from trade_alpha.predict import model_service


@pytest.mark.integration
@pytest.mark.order(40)
class TestModelService:
    """Integration tests for model service."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        self.ts_code = "002594.SZ"
        self.start_date = "20230101"
        self.end_date = "20231231"

        yield

        dao = model_service.MongoDB()
        collection = dao._get_collection("models")
        for m in collection.find({"ts_code": self.ts_code}):
            model_service.delete_model(str(m["_id"]))
        dao.close()

    def test_create_linear_model(self):
        """Test creating linear model."""
        model_id = model_service.create_model(
            name="test_linear",
            model_type="linear",
            ts_code=self.ts_code,
            targets=["close"],
            params={},
            start_date=self.start_date,
            end_date=self.end_date,
        )

        assert model_id is not None

        model = model_service.get_model_by_id(model_id)
        assert model is not None
        assert model["model_type"] == "linear"

    def test_create_xgboost_model(self):
        """Test creating XGBoost model."""
        model_id = model_service.create_model(
            name="test_xgboost",
            model_type="xgboost",
            ts_code=self.ts_code,
            targets=["close"],
            params={"n_estimators": 50, "max_depth": 4},
            start_date=self.start_date,
            end_date=self.end_date,
        )

        assert model_id is not None

        predictions = model_service.predict_with_model(model_id)
        assert "close" in predictions

    def test_list_models(self):
        """Test listing models."""
        model_service.create_model(
            name="test_list",
            model_type="linear",
            ts_code=self.ts_code,
            targets=["close"],
            params={},
            start_date=self.start_date,
            end_date=self.end_date,
        )

        models = model_service.list_models(ts_code=self.ts_code)
        assert len(models) > 0

    def test_delete_model(self):
        """Test deleting model."""
        model_id = model_service.create_model(
            name="test_delete",
            model_type="linear",
            ts_code=self.ts_code,
            targets=["close"],
            params={},
            start_date=self.start_date,
            end_date=self.end_date,
        )

        deleted = model_service.delete_model(model_id)
        assert deleted is True

        model = model_service.get_model_by_id(model_id)
        assert model is None
```

- [ ] **Step 2: 提交**

```bash
git add tests/trade_alpha/integration/test_40_model_service.py
git commit -m "test: add model service integration tests"
```

---

### Task 15: 更新集成测试文档

**Files:**
- Modify: `backend/docs/integration-tests.md`

- [ ] **Step 1: 更新文档**

在测试顺序表中添加：

```
| 40 | test_40_model_service.py | TestModelService | 验证模型管理服务 |
```

- [ ] **Step 2: 提交**

```bash
git add docs/integration-tests.md
git commit -m "docs: update integration tests documentation"
```

---

### Task 16: 最终提交

- [ ] **Step 1: 运行所有集成测试**

```bash
cd backend
$env:PYTHONPATH='src'
pytest tests/trade_alpha/integration/ -v
```

- [ ] **Step 2: 推送代码**

```bash
git push
```
