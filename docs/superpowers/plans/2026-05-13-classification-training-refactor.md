# 模型训练分类化重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将模型训练系统从回归模式重构为纯分类模式，支持三分类标签(-1/0/1)，集成标准化器。

**Architecture:** 新的分类架构：ModelConfig 配置分类参数 → TrainingResult 保存训练元数据 → XGBoostClassifier/LSTMClassifier 训练 → PredictionResult 持久化预测结果。

**Tech Stack:** Python, pandas, numpy, xgboost, torch, Beanie, FastAPI

---

## 依赖顺序图

```
Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7 → Task 8 → Task 9 → Task 10 → Task 11 → Task 12
                   ↑                              ↑
              Task 2.1                      Task 5.1
```

---

### Task 1: 重写数据模型（ModelConfig, TrainingResult, PredictionResult）

**Files:**
- Modify: `backend/src/trade_alpha/dao/model_config.py`
- Modify: `backend/src/trade_alpha/dao/training.py`
- Modify: `backend/src/trade_alpha/dao/prediction.py`

- [ ] **Step 1: 重写 model_config.py**

```python
"""ModelConfig Document model."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import Field
from beanie import Document


class ModelConfig(Document):
    """Model config document for MongoDB."""

    name: str
    model_type: str  # xgboost / lstm
    feature_fields: List[str] = Field(default_factory=list)
    classification_horizons: List[int] = Field(default_factory=lambda: [3, 5])
    classification_threshold: float = 0.02
    normalizer_fields: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Settings:
        name = "model_configs"
        indexes = ["name"]
```

- [ ] **Step 2: 重写 training.py**

```python
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
    feature_fields: List[str] = Field(default_factory=list)
    classification_horizons: List[int] = Field(default_factory=lambda: [3, 5])
    metrics: Dict[str, Any] = Field(default_factory=dict)
    model_path: Optional[str] = None
    created_at: Optional[datetime] = None

    class Settings:
        name = "training_results"
        indexes = ["name", "config_id"]
```

- [ ] **Step 3: 重写 prediction.py**

```python
"""PredictionResult Document model."""

from datetime import datetime
from typing import Optional, Dict, List
from pydantic import Field
from beanie import Document, PydanticObjectId


class PredictionResult(Document):
    """Prediction result document for MongoDB."""

    training_result_id: PydanticObjectId
    ts_code: str
    trade_date: str
    predictions: Dict[str, int] = Field(default_factory=dict)  # {label_3d: -1/0/1}
    probabilities: Dict[str, List[float]] = Field(default_factory=dict)  # {label_3d: [P(-1), P(0), P(1)]}
    created_at: Optional[datetime] = None

    class Settings:
        name = "prediction_results"
        indexes = ["training_result_id", "ts_code", "trade_date"]
```

- [ ] **Step 4: 运行 dao 测试验证**

```bash
cd backend && pytest tests/trade_alpha/unit/dao/ -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/trade_alpha/dao/model_config.py backend/src/trade_alpha/dao/training.py backend/src/trade_alpha/dao/prediction.py
git commit -m "refactor: update data models for classification (ModelConfig, TrainingResult, PredictionResult)"
```

---

### Task 2: 重写 BaseClassifier 基类

**Files:**
- Create: `backend/src/trade_alpha/predict/models/base.py`

- [ ] **Step 1: 编写 BaseClassifier**

```python
"""Base classifier interface."""

from abc import ABC, abstractmethod
from typing import List, Dict
import numpy as np


class BaseClassifier(ABC):
    """Abstract base class for all classifiers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Classifier name."""

    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray, target_names: List[str]) -> None:
        """Train the classifier.

        Args:
            X: Feature matrix (n_samples, n_features)
            y: Label matrix (n_samples, n_targets), values in {-1, 0, 1}
            target_names: List of target names
        """

    @abstractmethod
    def predict(self, features: np.ndarray, target_names: List[str]) -> Dict[str, int]:
        """Predict class labels.

        Args:
            features: Feature matrix (n_samples, n_features)
            target_names: List of target names

        Returns:
            Dictionary mapping target names to class labels (-1/0/1)
        """

    @abstractmethod
    def predict_proba(self, features: np.ndarray, target_names: List[str]) -> Dict[str, List[float]]:
        """Predict class probabilities.

        Args:
            features: Feature matrix (n_samples, n_features)
            target_names: List of target names

        Returns:
            Dictionary mapping target names to [P(-1), P(0), P(1)]
        """

    @abstractmethod
    def save(self, path: str) -> None:
        """Save model to file."""

    @abstractmethod
    def load(self, path: str) -> None:
        """Load model from file."""
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/trade_alpha/predict/models/base.py
git commit -m "feat: add BaseClassifier interface for classification models"
```

---

### Task 3: 重写 XGBoostClassifier

**Files:**
- Create: `backend/src/trade_alpha/predict/models/xgboost.py`

- [ ] **Step 1: 编写 XGBoostClassifier**

```python
"""XGBoost classifier for multi-label classification."""

import pickle
import numpy as np
import xgboost as xgb
from typing import List, Dict
from trade_alpha.predict.models.base import BaseClassifier


class XGBoostClassifier(BaseClassifier):
    """XGBoost multi-label classifier for stock direction prediction."""

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
        self.models: Dict[str, xgb.XGBClassifier] = {}
        self._label_mapping: Dict[str, Dict[int, int]] = {}  # target -> {0: -1, 1: 0, 2: 1}

    @property
    def name(self) -> str:
        return "xgboost"

    def fit(self, X: np.ndarray, y: np.ndarray, target_names: List[str]) -> None:
        self.models = {}
        self._label_mapping = {}
        for i, target in enumerate(target_names):
            y_i = y[:, i].astype(int)
            unique_labels = sorted(set(y_i))
            label_map = {j: label for j, label in enumerate(unique_labels)}
            reverse_map = {label: j for j, label in label_map.items()}
            y_mapped = np.array([reverse_map[v] for v in y_i])

            model = xgb.XGBClassifier(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                learning_rate=self.learning_rate,
                min_child_weight=self.min_child_weight,
                subsample=self.subsample,
                colsample_bytree=self.colsample_bytree,
                use_label_encoder=False,
                eval_metric="mlogloss",
            )
            model.fit(X, y_mapped)
            self.models[target] = model
            self._label_mapping[target] = label_map

    def predict(self, features: np.ndarray, target_names: List[str]) -> Dict[str, int]:
        result = {}
        for target in target_names:
            if target not in self.models:
                continue
            label_map = self._label_mapping[target]
            pred_mapped = self.models[target].predict(features)[0]
            result[target] = label_map[pred_mapped]
        return result

    def predict_proba(self, features: np.ndarray, target_names: List[str]) -> Dict[str, List[float]]:
        result = {}
        for target in target_names:
            if target not in self.models:
                continue
            label_map = self._label_mapping[target]
            n_classes = len(label_map)
            proba_mapped = self.models[target].predict_proba(features)[0]
            proba = [0.0, 0.0, 0.0]
            for j, label in label_map.items():
                idx = label + 1  # -1 -> 0, 0 -> 1, 1 -> 2
                proba[idx] = proba_mapped[j]
            result[target] = proba
        return result

    def save(self, path: str) -> None:
        with open(path, "wb") as f:
            pickle.dump({"models": self.models, "label_mapping": self._label_mapping}, f)

    def load(self, path: str) -> None:
        with open(path, "rb") as f:
            data = pickle.load(f)
            self.models = data["models"]
            self._label_mapping = data["label_mapping"]
```

- [ ] **Step 2: 编写测试**

```python
"""Tests for XGBoostClassifier."""
import pytest
import numpy as np
from trade_alpha.predict.models.xgboost import XGBoostClassifier


def test_xgboost_classifier_fit_predict():
    X = np.random.randn(100, 5)
    y = np.random.choice([-1, 0, 1], size=(100, 2))
    clf = XGBoostClassifier(n_estimators=10)
    clf.fit(X, y, ["label_3d", "label_5d"])

    preds = clf.predict(X[:1], ["label_3d", "label_5d"])
    assert "label_3d" in preds
    assert preds["label_3d"] in [-1, 0, 1]

    probas = clf.predict_proba(X[:1], ["label_3d", "label_5d"])
    assert len(probas["label_3d"]) == 3
    assert abs(sum(probas["label_3d"]) - 1.0) < 0.01


def test_xgboost_classifier_save_load(tmp_path):
    X = np.random.randn(50, 5)
    y = np.random.choice([-1, 0, 1], size=(50, 1))
    clf = XGBoostClassifier(n_estimators=10)
    clf.fit(X, y, ["label_3d"])

    path = tmp_path / "model.pkl"
    clf.save(str(path))
    clf2 = XGBoostClassifier()
    clf2.load(str(path))

    preds = clf.predict(X[:1], ["label_3d"])
    preds2 = clf2.predict(X[:1], ["label_3d"])
    assert preds == preds2
```

- [ ] **Step 3: 运行测试**

```bash
cd backend && pytest tests/trade_alpha/unit/predict/test_xgboost.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/predict/models/xgboost.py tests/trade_alpha/unit/predict/test_xgboost.py
git commit -m "feat: implement XGBoostClassifier for multi-label stock classification"
```

---

### Task 4: 重写 LSTMClassifier

**Files:**
- Create: `backend/src/trade_alpha/predict/models/lstm.py`

- [ ] **Step 1: 编写 LSTMClassifier**

```python
"""LSTM classifier for multi-label classification."""

import os
import numpy as np
import torch
import torch.nn as nn
from typing import List, Dict
from trade_alpha.predict.models.base import BaseClassifier


class LSTMModel(nn.Module):
    """LSTM neural network for classification."""

    def __init__(self, input_size: int, hidden_size: int, num_layers: int, num_class: int = 3, dropout: float = 0.1):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size, hidden_size, num_layers,
            batch_first=True, dropout=dropout if num_layers > 1 else 0
        )
        self.fc = nn.Linear(hidden_size, num_class)

    def forward(self, x):
        out, _ = self.lstm(x)
        out = self.fc(out[:, -1, :])
        return torch.softmax(out, dim=1)


class LSTMClassifier(BaseClassifier):
    """LSTM multi-label classifier for stock direction prediction."""

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
        self.models: Dict[str, LSTMModel] = {}
        self.input_size: int = 0
        self._label_mapping: Dict[str, Dict[int, int]] = {}

    @property
    def name(self) -> str:
        return "lstm"

    def _create_sequences(self, X: np.ndarray) -> np.ndarray:
        sequences = []
        for i in range(len(X) - self.sequence_length):
            sequences.append(X[i:i + self.sequence_length])
        return np.array(sequences)

    def fit(self, X: np.ndarray, y: np.ndarray, target_names: List[str]) -> None:
        self.input_size = X.shape[1]
        self.models = {}
        self._label_mapping = {}

        X_seq = self._create_sequences(X)
        y_seq = y[self.sequence_length:]

        for i, target in enumerate(target_names):
            y_i = y_seq[:, i].astype(int)
            unique_labels = sorted(set(y_i))
            label_map = {j: label for j, label in enumerate(unique_labels)}
            reverse_map = {label: j for j, label in label_map.items()}
            y_mapped = np.array([reverse_map[v] for v in y_i])

            model = LSTMModel(
                input_size=self.input_size,
                hidden_size=self.hidden_size,
                num_layers=self.num_layers,
                num_class=len(label_map),
                dropout=self.dropout,
            )
            criterion = nn.CrossEntropyLoss()
            optimizer = torch.optim.Adam(model.parameters(), lr=self.learning_rate)

            X_tensor = torch.FloatTensor(X_seq)
            y_tensor = torch.LongTensor(y_mapped)

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
            self._label_mapping[target] = label_map

    def predict(self, features: np.ndarray, target_names: List[str]) -> Dict[str, int]:
        result = {}
        if len(features) < self.sequence_length:
            return result

        seq = features[-self.sequence_length:].reshape(1, self.sequence_length, -1)
        X_tensor = torch.FloatTensor(seq)

        for target in target_names:
            if target not in self.models:
                continue
            self.models[target].eval()
            with torch.no_grad():
                proba = self.models[target](X_tensor)[0]
                pred_idx = proba.argmax().item()
                result[target] = self._label_mapping[target][pred_idx]
        return result

    def predict_proba(self, features: np.ndarray, target_names: List[str]) -> Dict[str, List[float]]:
        result = {}
        if len(features) < self.sequence_length:
            return result

        seq = features[-self.sequence_length:].reshape(1, self.sequence_length, -1)
        X_tensor = torch.FloatTensor(seq)

        for target in target_names:
            if target not in self.models:
                continue
            self.models[target].eval()
            with torch.no_grad():
                proba_mapped = self.models[target](X_tensor)[0].numpy()
                label_map = self._label_mapping[target]
                proba = [0.0, 0.0, 0.0]
                for j, label in label_map.items():
                    idx = label + 1  # -1 -> 0, 0 -> 1, 1 -> 2
                    proba[idx] = proba_mapped[j]
                result[target] = proba
        return result

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        state = {
            "models": {k: v.state_dict() for k, v in self.models.items()},
            "label_mapping": self._label_mapping,
            "input_size": self.input_size,
            "hidden_size": self.hidden_size,
            "num_layers": self.num_layers,
            "sequence_length": self.sequence_length,
        }
        torch.save(state, path)

    def load(self, path: str) -> None:
        state = torch.load(path)
        self.input_size = state["input_size"]
        self.hidden_size = state["hidden_size"]
        self.num_layers = state["num_layers"]
        self.sequence_length = state["sequence_length"]
        self._label_mapping = state["label_mapping"]
        self.models = {}
        for target, model_state in state["models"].items():
            model = LSTMModel(
                input_size=self.input_size,
                hidden_size=self.hidden_size,
                num_layers=self.num_layers,
                num_class=len(self._label_mapping[target]),
            )
            model.load_state_dict(model_state)
            self.models[target] = model
```

- [ ] **Step 2: 编写测试**

```python
"""Tests for LSTMClassifier."""
import pytest
import numpy as np
from trade_alpha.predict.models.lstm import LSTMClassifier


def test_lstm_classifier_fit_predict():
    X = np.random.randn(50, 5).astype(np.float32)
    y = np.random.choice([-1, 0, 1], size=(50, 2)).astype(int)
    clf = LSTMClassifier(epochs=5, sequence_length=5)
    clf.fit(X, y, ["label_3d", "label_5d"])

    preds = clf.predict(X[-5:], ["label_3d", "label_5d"])
    assert "label_3d" in preds
    assert preds["label_3d"] in [-1, 0, 1]


def test_lstm_classifier_save_load(tmp_path):
    X = np.random.randn(30, 5).astype(np.float32)
    y = np.random.choice([-1, 0, 1], size=(30, 1)).astype(int)
    clf = LSTMClassifier(epochs=5, sequence_length=5)
    clf.fit(X, y, ["label_3d"])

    path = tmp_path / "model.pt"
    clf.save(str(path))
    clf2 = LSTMClassifier()
    clf2.load(str(path))

    preds = clf.predict(X[-5:], ["label_3d"])
    preds2 = clf2.predict(X[-5:], ["label_3d"])
    assert preds == preds2
```

- [ ] **Step 3: 运行测试**

```bash
cd backend && pytest tests/trade_alpha/unit/predict/test_lstm.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/predict/models/lstm.py tests/trade_alpha/unit/predict/test_lstm.py
git commit -m "feat: implement LSTMClassifier for multi-label stock classification"
```

---

### Task 5: 重写 training_service.py

**Files:**
- Create: `backend/src/trade_alpha/predict/training_service.py`

- [ ] **Step 1: 编写完整的 training_service.py**

```python
"""Training service for classification models."""

import os
from datetime import datetime, timezone
from typing import Optional, List, Dict
from beanie import PydanticObjectId
import pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

from trade_alpha.dao import StockDaily, StockList, TrainingResult, PredictionResult
from trade_alpha.predict.config_service import get_config_by_id
from trade_alpha.predict.models.xgboost import XGBoostClassifier
from trade_alpha.predict.models.lstm import LSTMClassifier
from trade_alpha.predict.normalizers.cross_sectional import CrossSectionalNormalizer
from trade_alpha.logging import get_logger

logger = get_logger("training_service")

CLASSIFIERS = {
    "xgboost": XGBoostClassifier,
    "lstm": LSTMClassifier,
}

RELATIVE_INDICATOR_PREFIXES = [
    "ma_", "macd", "pct_chg", "bias_",
    "close_pct_rank_", "vol_ratio_",
    "kdj_", "boll_"
]

MODELS_DIR = "models"


def _ensure_model_dir(config_id: str) -> None:
    os.makedirs(os.path.join(MODELS_DIR, config_id), exist_ok=True)


def _get_default_feature_fields(columns: List[str]) -> List[str]:
    features = []
    for col in columns:
        for prefix in RELATIVE_INDICATOR_PREFIXES:
            if col.startswith(prefix) or col == prefix.rstrip("_"):
                features.append(col)
                break
    return sorted(set(features))


def _create_classification_labels(df: pd.DataFrame, horizons: List[int], threshold: float) -> pd.DataFrame:
    for horizon in horizons:
        future_pct = (df["close"].shift(-horizon) - df["close"]) / df["close"]
        labels = future_pct.apply(
            lambda x: 1 if x > threshold else (-1 if x < -threshold else 0)
        )
        df[f"label_{horizon}d"] = labels
    return df.iloc[:-max(horizons)]


async def create_training(
    config_id: PydanticObjectId,
    name: str,
    ts_codes: List[str],
    start_date: str,
    end_date: str,
) -> TrainingResult:
    """Create training with classification labels."""
    config = await get_config_by_id(config_id)
    if not config:
        raise ValueError(f"Config not found: {config_id}")

    if config.model_type not in CLASSIFIERS:
        raise ValueError(f"Unsupported model type: {config.model_type}")

    all_dfs = []
    skipped = []
    for ts_code in ts_codes:
        stock = await StockList.find_one(StockList.ts_code == ts_code)
        if not stock or stock.sync_status != "active":
            skipped.append(ts_code)
            logger.warning(f"跳过 {ts_code}（sync_status != active，数据未就绪）")
            continue

        records = await StockDaily.find(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date >= start_date,
            StockDaily.trade_date <= end_date,
        ).sort(StockDaily.trade_date).to_list()

        if not records:
            skipped.append(ts_code)
            logger.warning(f"跳过 {ts_code}（无数据）")
            continue

        df = pd.DataFrame([r.model_dump() for r in records])
        df["ts_code"] = ts_code
        all_dfs.append(df)

    if not all_dfs:
        raise ValueError("无可用数据，所有股票均跳过")

    combined = pd.concat(all_dfs, ignore_index=True)
    combined = combined.sort_values(["trade_date", "ts_code"])

    combined = _create_classification_labels(
        combined,
        config.classification_horizons,
        config.classification_threshold
    )

    if config.feature_fields:
        feature_fields = config.feature_fields
    else:
        feature_fields = _get_default_feature_fields(combined.columns.tolist())

    target_names = [f"label_{h}d" for h in config.classification_horizons]

    if config.normalizer_fields:
        normalizer = CrossSectionalNormalizer(
            standardize_fields=feature_fields,
            **config.normalizer_fields
        )
    else:
        normalizer = CrossSectionalNormalizer(standardize_fields=feature_fields)

    combined_normalized = normalizer.normalize(combined[feature_fields + ["trade_date", "ts_code"]])
    combined_normalized["trade_date"] = combined["trade_date"].values
    combined_normalized["ts_code"] = combined["ts_code"].values

    drop_cols = ["trade_date", "ts_code"] + [c for c in combined.columns if c not in feature_fields + ["trade_date", "ts_code"] + target_names]
    for c in drop_cols:
        if c in combined_normalized.columns:
            combined_normalized = combined_normalized.drop(columns=[c])

    combined_normalized = combined_normalized.dropna(subset=feature_fields + target_names)

    if len(combined_normalized) < 20:
        raise ValueError(f"数据不足（{len(combined_normalized)} < 20）")

    X = combined_normalized[feature_fields].values
    y = combined_normalized[target_names].values

    classifier = CLASSIFIERS[config.model_type]()
    classifier.fit(X, y, target_names)

    y_pred = classifier.predict(X, target_names)
    y_true = {t: combined_normalized[t].values for t in target_names}

    metrics = {}
    for t in target_names:
        metrics[f"{t}_accuracy"] = accuracy_score(y_true[t], [y_pred[t] for _ in range(len(y_pred[t]))])
        metrics[f"{t}_precision"] = precision_score(y_true[t], [y_pred[t] for _ in range(len(y_pred[t]))], average="macro", zero_division=0)
        metrics[f"{t}_recall"] = recall_score(y_true[t], [y_pred[t] for _ in range(len(y_pred[t]))], average="macro", zero_division=0)
        metrics[f"{t}_f1"] = f1_score(y_true[t], [y_pred[t] for _ in range(len(y_pred[t]))], average="macro", zero_division=0)
    metrics["sample_count"] = len(combined_normalized)

    training = TrainingResult(
        config_id=config_id,
        name=name,
        ts_codes=[c for c in ts_codes if c not in skipped],
        start_date=start_date,
        end_date=end_date,
        feature_fields=feature_fields,
        classification_horizons=config.classification_horizons,
        metrics=metrics,
        created_at=datetime.now(timezone.utc),
    )
    await training.insert()

    _ensure_model_dir(str(config_id))
    model_path = os.path.join(MODELS_DIR, str(config_id), f"{training.id}.pkl")
    classifier.save(model_path)

    training.model_path = model_path
    await training.save()

    logger.info(f"训练完成 '{name}' id={training.id} samples={metrics['sample_count']}")
    return training


async def get_training_by_id(training_id: PydanticObjectId) -> Optional[TrainingResult]:
    return await TrainingResult.get(training_id)


async def list_trainings(config_id: PydanticObjectId = None) -> List[TrainingResult]:
    if config_id:
        return await TrainingResult.find(TrainingResult.config_id == config_id).to_list()
    return await TrainingResult.find_all().to_list()


async def delete_training(training_id: PydanticObjectId) -> bool:
    training = await TrainingResult.get(training_id)
    if not training:
        return False
    if training.model_path and os.path.exists(training.model_path):
        os.remove(training.model_path)
    await PredictionResult.find(PredictionResult.training_result_id == training_id).delete()
    await training.delete()
    return True


async def predict_with_training(training_id: PydanticObjectId, ts_code: str) -> Dict:
    from trade_alpha.predict.config_service import get_config_by_id

    training = await get_training_by_id(training_id)
    if not training:
        raise ValueError(f"Training not found: {training_id}")

    config = await get_config_by_id(training.config_id)
    if not config:
        raise ValueError(f"Config not found: {training.config_id}")

    records = await StockDaily.find(
        StockDaily.ts_code == ts_code
    ).sort(-StockDaily.trade_date).to_list()

    if not records:
        raise ValueError(f"No data for {ts_code}")

    df = pd.DataFrame([r.model_dump() for r in records])
    df = df.sort_values("trade_date")

    if config.normalizer_fields:
        normalizer = CrossSectionalNormalizer(
            standardize_fields=training.feature_fields,
            **config.normalizer_fields
        )
    else:
        normalizer = CrossSectionalNormalizer(standardize_fields=training.feature_fields)

    df_norm = normalizer.normalize(df[training.feature_fields + ["trade_date", "ts_code"]])
    for c in df.columns:
        if c not in training.feature_fields and c not in ["trade_date", "ts_code"]:
            if c in df_norm.columns:
                df_norm = df_norm.drop(columns=[c])

    df_norm = df_norm.dropna(subset=training.feature_fields)
    if len(df_norm) == 0:
        raise ValueError("No valid data after normalization")

    classifier = CLASSIFIERS[config.model_type]()
    classifier.load(training.model_path)

    target_names = [f"label_{h}d" for h in training.classification_horizons]
    features = df_norm[training.feature_fields].iloc[-1:].values

    predictions = classifier.predict(features, target_names)
    probabilities = classifier.predict_proba(features, target_names)

    last_date = df["trade_date"].iloc[-1]

    prediction = PredictionResult(
        training_result_id=training_id,
        ts_code=ts_code,
        trade_date=last_date,
        predictions=predictions,
        probabilities=probabilities,
        created_at=datetime.now(timezone.utc),
    )
    await prediction.insert()

    return {"predictions": predictions, "probabilities": probabilities}


async def get_prediction_by_id(prediction_id: PydanticObjectId) -> Optional[PredictionResult]:
    return await PredictionResult.get(prediction_id)


async def delete_prediction(prediction_id: PydanticObjectId) -> bool:
    prediction = await PredictionResult.get(prediction_id)
    if not prediction:
        return False
    await prediction.delete()
    return True
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/trade_alpha/predict/training_service.py
git commit -m "refactor: rewrite training_service for classification (labels -1/0/1, XGBoost/LSTM classifiers)"
```

---

### Task 6: 更新 config_service.py

**Files:**
- Modify: `backend/src/trade_alpha/predict/config_service.py`

- [ ] **Step 1: 更新 config_service.py**

```python
"""Model configuration service."""

from datetime import datetime, timezone
from typing import Optional, List
from beanie import PydanticObjectId
from trade_alpha.dao import ModelConfig, TrainingResult
from trade_alpha.logging import get_logger

logger = get_logger("config_service")


async def create_config(
    name: str,
    model_type: str,
    feature_fields: Optional[List[str]] = None,
    classification_horizons: Optional[List[int]] = None,
    classification_threshold: float = 0.02,
    normalizer_fields: Optional[dict] = None,
) -> ModelConfig:
    """Create model configuration."""
    if not name:
        raise ValueError("name is required")
    if model_type not in ("xgboost", "lstm"):
        raise ValueError(f"model_type must be xgboost or lstm, got: {model_type}")

    existing = await ModelConfig.find_one(ModelConfig.name == name)
    if existing:
        raise ValueError(f"Config already exists: {name}")

    config = ModelConfig(
        name=name,
        model_type=model_type,
        feature_fields=feature_fields or [],
        classification_horizons=classification_horizons or [3, 5],
        classification_threshold=classification_threshold,
        normalizer_fields=normalizer_fields or {},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await config.insert()
    logger.info(f"Config created: id={config.id} name={name} model_type={model_type}")
    return config


async def get_config_by_id(config_id: PydanticObjectId) -> Optional[ModelConfig]:
    return await ModelConfig.get(config_id)


async def get_config_by_name(name: str) -> Optional[ModelConfig]:
    return await ModelConfig.find_one(ModelConfig.name == name)


async def list_configs(model_type: str = None) -> List[ModelConfig]:
    if model_type:
        return await ModelConfig.find(ModelConfig.model_type == model_type).to_list()
    return await ModelConfig.find_all().to_list()


async def update_config(config_id: PydanticObjectId, **kwargs) -> Optional[ModelConfig]:
    config = await ModelConfig.get(config_id)
    if not config:
        return None
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    config.updated_at = datetime.now(timezone.utc)
    await config.save()
    return config


async def delete_config(config_id: PydanticObjectId) -> bool:
    config = await ModelConfig.get(config_id)
    if not config:
        return False
    await TrainingResult.find(TrainingResult.config_id == config_id).delete()
    await config.delete()
    return True
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/trade_alpha/predict/config_service.py
git commit -m "refactor: update config_service for classification config fields"
```

---

### Task 7: 重写 API 路由

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/trainings.py`
- Modify: `backend/src/trade_alpha/api/routers/predict.py`
- Modify: `backend/src/trade_alpha/api/routers/model_configs.py`
- Modify: `backend/src/trade_alpha/api/schemas.py`
- Modify: `backend/src/trade_alpha/api/main.py`

- [ ] **Step 1: 重写 trainings.py**

```python
"""Training API router."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from beanie import PydanticObjectId
from trade_alpha.predict import training_service

router = APIRouter(prefix="/trainings", tags=["trainings"])


class TrainingCreate(BaseModel):
    config_id: str
    name: str
    ts_codes: List[str]
    start_date: str
    end_date: str


@router.post("")
async def create_training(body: TrainingCreate):
    try:
        config_id = PydanticObjectId(body.config_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid config ID format")
    try:
        return await training_service.create_training(
            config_id=config_id,
            name=body.name,
            ts_codes=body.ts_codes,
            start_date=body.start_date,
            end_date=body.end_date,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
async def list_trainings(config_id: str = Query(None)):
    if config_id:
        try:
            c_id = PydanticObjectId(config_id)
            return await training_service.list_trainings(config_id=c_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid config ID format")
    return await training_service.list_trainings()


@router.get("/{training_id}")
async def get_training(training_id: str):
    try:
        obj_id = PydanticObjectId(training_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid training ID")
    training = await training_service.get_training_by_id(obj_id)
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")
    return training


@router.delete("/{training_id}")
async def delete_training(training_id: str):
    try:
        obj_id = PydanticObjectId(training_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid training ID")
    deleted = await training_service.delete_training(obj_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Training not found")
    return {"deleted": True}


class PredictRequest(BaseModel):
    ts_code: str


@router.post("/{training_id}/predict")
async def predict(training_id: str, body: PredictRequest):
    try:
        obj_id = PydanticObjectId(training_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid training ID")
    try:
        result = await training_service.predict_with_training(obj_id, body.ts_code)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 2: 重写 predict.py**

```python
"""Predict API router."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from beanie import PydanticObjectId
from trade_alpha.predict import training_service

router = APIRouter(prefix="/predict", tags=["predict"])


@router.get("/{prediction_id}")
async def get_prediction(prediction_id: str):
    try:
        obj_id = PydanticObjectId(prediction_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid prediction ID")
    prediction = await training_service.get_prediction_by_id(obj_id)
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return prediction


@router.delete("/{prediction_id}")
async def delete_prediction(prediction_id: str):
    try:
        obj_id = PydanticObjectId(prediction_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid prediction ID")
    deleted = await training_service.delete_prediction(obj_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return {"deleted": True}
```

- [ ] **Step 3: 更新 model_configs.py（查看现有代码后调整）**

（略，根据现有代码调整 ModelCreateRequest schema）

- [ ] **Step 4: 更新 schemas.py**

删除：`PredictRequest`, `PredictResponse`, `ModelCreateRequest`, `ModelResponse`（合并到 routers）

- [ ] **Step 5: Commit**

```bash
git add backend/src/trade_alpha/api/routers/trainings.py backend/src/trade_alpha/api/routers/predict.py backend/src/trade_alpha/api/routers/model_configs.py backend/src/trade_alpha/api/schemas.py
git commit -m "refactor: update API routers for classification training and prediction"
```

---

### Task 8: 删除旧文件

**Files:**
- Delete: `backend/src/trade_alpha/predict/models/linear.py`
- Delete: `backend/src/trade_alpha/predict/service.py`
- Delete: `tests/trade_alpha/unit/predict/test_linear.py`
- Delete: `tests/trade_alpha/unit/predict/test_service.py`

- [ ] **Step 1: 删除并 commit**

```bash
git rm backend/src/trade_alpha/predict/models/linear.py backend/src/trade_alpha/predict/service.py tests/trade_alpha/unit/predict/test_linear.py tests/trade_alpha/unit/predict/test_service.py
git commit -m "refactor: remove regression-only files (linear.py, service.py, tests)"
```

---

### Task 9: 更新 dao/__init__.py 和 predict/__init__.py

**Files:**
- Modify: `backend/src/trade_alpha/dao/__init__.py`
- Modify: `backend/src/trade_alpha/predict/__init__.py`
- Modify: `backend/src/trade_alpha/predict/models/__init__.py`

- [ ] **Step 1: 更新导出**

- `dao/__init__.py`: 确保 PredictionResult, TrainingResult, ModelConfig 导出
- `predict/__init__.py`: 更新导出，移除 service.py 相关
- `predict/models/__init__.py`: 更新为 XGBoostClassifier, LSTMClassifier, BaseClassifier

- [ ] **Step 2: Commit**

```bash
git add backend/src/trade_alpha/dao/__init__.py backend/src/trade_alpha/predict/__init__.py backend/src/trade_alpha/predict/models/__init__.py
git commit -m "refactor: update module exports for classification architecture"
```

---

### Task 10: 更新集成测试

**Files:**
- Modify: `tests/trade_alpha/integration/test_51_training_service.py`
- Modify: `tests/trade_alpha/integration/test_predict_integration.py`

- [ ] **Step 1: 重写集成测试**

（基于 spec 中的测试更新说明，编写分类训练和预测的集成测试）

- [ ] **Step 2: 运行集成测试**

```bash
cd backend && pytest tests/trade_alpha/integration/ -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/trade_alpha/integration/test_51_training_service.py tests/trade_alpha/integration/test_predict_integration.py
git commit -m "test: update integration tests for classification training"
```

---

### Task 11: 运行全量测试验证

- [ ] **Step 1: 运行所有单元测试**

```bash
cd backend && pytest tests/trade_alpha/unit/ -v
```

- [ ] **Step 2: 运行所有集成测试**

```bash
cd backend && pytest tests/trade_alpha/integration/ -v
```

- [ ] **Step 3: 如有失败，修复并重新运行**

---

### Task 12: 文档同步

**Files:**
- Modify: `docs/system-design.md`
- Modify: `docs/database-schema.md`
- Modify: `docs/api.md`

- [ ] **Step 1: 同步文档**

- `system-design.md`: 更新 predict 模块描述
- `database-schema.md`: 更新 ModelConfig, TrainingResult, PredictionResult 表结构
- `api.md`: 更新训练和预测接口描述

- [ ] **Step 2: Commit**

```bash
git add docs/
git commit -m "docs: sync documentation for classification training architecture"
```

---

## Self-Review Check

1. **Spec coverage:** 所有 spec 中的需求都有对应任务：
   - ✅ 数据模型变更 → Task 1
   - ✅ BaseClassifier 接口 → Task 2
   - ✅ XGBoostClassifier → Task 3
   - ✅ LSTMClassifier → Task 4
   - ✅ training_service 重写 → Task 5
   - ✅ config_service 更新 → Task 6
   - ✅ API 路由更新 → Task 7
   - ✅ 删除旧文件 → Task 8
   - ✅ 导出更新 → Task 9
   - ✅ 集成测试 → Task 10
   - ✅ 全量测试 → Task 11
   - ✅ 文档同步 → Task 12

2. **Placeholder scan:** 无 TBD/TODO，所有步骤有具体代码

3. **Type consistency:** 类型注解一致，方法签名匹配
