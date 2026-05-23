# 模型架构简化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 移除适配器层，每个模型类型自闭环。XGBoost 和 LSTM 各自独立模块，`train()` 内部完成数据加载→标准化→训练，不对外暴露 X, y。

**Architecture:** 两个模型类继承简约基类 `BaseClassifier`。`train(config, ts_codes, start_date, end_date, task_id)` 内部从 MongoDB 加载数据、标准化、训练、返回指标。训练分流器只负责创建实例和保存元数据。

**Tech Stack:** Python, NumPy, Pandas, XGBoost, PyTorch, Beanie/MongoDB

---

## 文件变更总览

### 新建文件 (6)
| 文件 | 说明 |
|------|------|
| `models/base.py` | BaseClassifier 简约基类（train 接收高层配置） |
| `models/xgboost/__init__.py` | XGBoost 模块 |
| `models/xgboost/normalizer.py` | 截面标准化函数（从 normalizers/ 迁移） |
| `models/xgboost/classifier.py` | XGBoostClassifier 自闭环（train 内部加载 DB 数据） |
| `models/lstm/__init__.py` | LSTM 模块 |
| `models/lstm/normalizer.py` | LSTM 序列内标准化函数（新） |
| `models/lstm/classifier.py` | LSTMClassifier 自闭环（train 内部构建序列+标准化） |

### 删除目录 (3)
| 目录 | 说明 |
|------|------|
| `models/adapters/` | 适配器层整体移除 |
| `models/classifiers/` | 拆到 xgboost/ 和 lstm/ |
| `models/normalizers/` | 拆到 xgboost/ 和 lstm/ |

### 修改文件 (5)
| 文件 | 说明 |
|------|------|
| `models/__init__.py` | 移除 adapter 导出，添加 CLASSIFIERS 导出 |
| `models/training/trainer.py` | 变薄，只做编排调度 |
| `execution/predictor.py` | 按模型类型分流 |
| `execution/pipeline.py` | 移除 dead import |
| 测试文件 | 更新 import 路径 |

---

## Task 1: 创建基类和新模块结构

**Files:**
- Create: `backend/src/trade_alpha/models/base.py`
- Create: `backend/src/trade_alpha/models/xgboost/__init__.py`
- Create: `backend/src/trade_alpha/models/lstm/__init__.py`

- [ ] **Step 1: 创建 models/base.py**

```python
"""Base classifier interface."""

from abc import ABC, abstractmethod
from typing import Dict


class BaseClassifier(ABC):
    def __init__(self, config):
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def train(self, ts_codes, start_date, end_date, task_id=None) -> Dict:
        """自闭环训练：加载数据 → 标准化 → 训练 → 返回指标。"""

    @abstractmethod
    def predict(self, features, target_names) -> Dict: ...

    @abstractmethod
    def predict_proba(self, features, target_names) -> Dict: ...

    @abstractmethod
    def save(self, path: str) -> None: ...

    @abstractmethod
    def load(self, path: str) -> None: ...
```

- [ ] **Step 2: 创建模块 __init__.py**

`models/xgboost/__init__.py`:
```python
"""XGBoost model module."""
```

`models/lstm/__init__.py`:
```python
"""LSTM model module."""
```

- [ ] **Step 3: 更新 models/__init__.py**

```python
"""Models module."""
from trade_alpha.models.base import BaseClassifier
from trade_alpha.models.xgboost.classifier import XGBoostClassifier
from trade_alpha.models.lstm.classifier import LSTMClassifier

CLASSIFIERS = {
    "xgboost": XGBoostClassifier,
    "lstm": LSTMClassifier,
}

from trade_alpha.models.training.trainer import (
    create_training,
    get_training_by_id,
    get_training_by_name,
    list_trainings,
    delete_training,
    delete_training_by_name,
    predict_with_training,
    get_prediction_by_id,
    delete_prediction,
)
from trade_alpha.models.training.config import (
    create_config,
    get_config_by_id,
    get_config_by_name,
    list_configs,
    update_config,
    delete_config,
)

__all__ = [
    "BaseClassifier",
    "XGBoostClassifier",
    "LSTMClassifier",
    "CLASSIFIERS",
    "create_training",
    "get_training_by_id",
    ...
]
```

- [ ] **Step 4: 提交**

```bash
git add backend/src/trade_alpha/models/base.py
git add backend/src/trade_alpha/models/xgboost/__init__.py
git add backend/src/trade_alpha/models/lstm/__init__.py
git add backend/src/trade_alpha/models/__init__.py
git commit -m "refactor: add BaseClassifier and new model module structure"
```

---

## Task 2: 创建 XGBoost 模块

**Files:**
- Create: `backend/src/trade_alpha/models/xgboost/normalizer.py`
- Create: `backend/src/trade_alpha/models/xgboost/classifier.py`

- [ ] **Step 1: 创建 xgboost/normalizer.py**

从 `models/normalizers/cross_sectional.py` 迁移，去掉类定义，改为独立函数：

```python
"""Cross-sectional normalizer for XGBoost."""

import pandas as pd
import numpy as np
from typing import List, Optional


def normalize(
    df: pd.DataFrame,
    feature_fields: List[str],
    standardize_fields: List[str],
    winsorize_fields: Optional[List[str]] = None,
    winsorize_lower: float = 0.05,
    winsorize_upper: float = 0.95,
) -> pd.DataFrame:
    """按 trade_date 分组做 Z-score 标准化。"""
    if df.empty:
        return pd.DataFrame(columns=feature_fields)

    winsorize_fields = winsorize_fields or []
    result_parts = []

    for _, group in df.groupby("trade_date"):
        group = group.copy()
        for field in winsorize_fields:
            if field not in group.columns:
                continue
            lower = group[field].quantile(winsorize_lower)
            upper = group[field].quantile(winsorize_upper)
            group[field] = group[field].clip(lower=lower, upper=upper)
        for field in standardize_fields:
            if field not in group.columns:
                continue
            vals = group[field]
            mean, std = vals.mean(), vals.std()
            group[field] = (vals - mean) / std if std > 0 else vals - mean
        result_parts.append(group)

    result_df = pd.concat(result_parts, ignore_index=True)
    available = [f for f in feature_fields if f in result_df.columns]
    return result_df[available]
```

- [ ] **Step 2: 创建 xgboost/classifier.py**

从 `models/classifiers/xgboost.py` 迁移，核心变更：
- `train()` 改为 `async def train(self, config, ts_codes, start_date, end_date, task_id=None)`
- `train()` 内部从 MongoDB 加载数据，计算标签，标准化，训练
- 内部调用 `_load_year_data` 等辅助函数

```python
"""XGBoost classifier - fully self-contained."""

import os
import pickle
import numpy as np
from typing import List, Dict
from trade_alpha.models.base import BaseClassifier


class XGBoostClassifier(BaseClassifier):
    def __init__(self, config):
        super().__init__(config)
        self.models: Dict[str, object] = {}
        self._label_mapping: Dict[str, Dict[int, int]] = {}

    @property
    def name(self) -> str:
        return "xgboost"

    async def train(self, ts_codes, start_date, end_date, task_id=None):
        """自闭环训练：加载数据 → 截面标准化 → 训练XGBoost。"""
        from trade_alpha.models.xgboost.normalizer import normalize as xgb_normalize
        from trade_alpha.task.service import TaskService
        from trade_alpha.models.training.trainer import _create_classification_labels, _load_year_data

        await TaskService.update_progress(task_id, 20, "正在加载数据...")

        config = self.config
        target_names = [f"label_{h}d" for h in config.classification_horizons]
        horizon = max(config.classification_horizons)
        years = sorted(set(y for y, _ in _get_year_months(start_date, end_date)))

        all_X, all_y, all_norm_dfs = [], [], []

        for year_idx, year in enumerate(years):
            year_df = await _load_year_data(year, ts_codes, horizon)
            if year_df is None:
                continue
            year_df = _create_classification_labels(
                year_df, config.classification_horizons, config.classification_threshold
            )
            year_norm = xgb_normalize(
                year_df, config.feature_fields,
                config.standardize_fields, config.winsorize_fields,
            )
            year_norm = year_norm.dropna(subset=config.feature_fields)
            year_labels = year_df.loc[year_norm.index, target_names]
            if not year_norm.empty:
                all_X.append(year_norm[config.feature_fields].values)
                all_y.append(year_labels.values)
                all_norm_dfs.append(year_norm[config.feature_fields])
            await TaskService.update_progress(
                task_id, 20 + (year_idx + 1) / len(years) * 30,
                f"正在处理 {year} 年数据..."
            )

        if not all_X:
            raise ValueError("No available data")

        X = np.vstack(all_X)
        y = np.vstack(all_y)
        self.models = {}
        self._label_mapping = {}

        await TaskService.update_progress(task_id, 60, "正在训练模型...")

        for target_idx, target in enumerate(target_names):
            y_i = y[:, target_idx]
            valid = ~np.isnan(y_i)
            X_valid, y_valid = X[valid], y_i[valid].astype(int)

            unique_labels = sorted(set(y_valid))
            label_map = {j: label for j, label in enumerate(unique_labels)}
            reverse_map = {label: j for j, label in label_map.items()}
            y_mapped = np.array([reverse_map[v] for v in y_valid])

            import xgboost as xgb
            model = xgb.XGBClassifier(
                n_estimators=config.xgb_n_estimators,
                max_depth=config.xgb_max_depth,
                learning_rate=config.xgb_learning_rate,
                min_child_weight=config.xgb_min_child_weight,
                subsample=config.xgb_subsample,
                colsample_bytree=config.xgb_colsample_bytree,
                eval_metric="mlogloss", use_label_encoder=False, verbosity=0,
            )
            model.fit(X_valid, y_mapped)
            self.models[target] = model
            self._label_mapping[target] = label_map

        await TaskService.update_progress(task_id, 80, "正在评估模型...")
        metrics = await _evaluate_classifier(self, X, y, config.feature_fields, target_names)
        metrics["sample_count"] = len(X)

        return metrics

    def predict(self, features, target_names):
        result = {}
        features = np.array(features, dtype=np.float64)
        for target in target_names:
            if target not in self.models:
                continue
            pred_idx = self.models[target].predict(features)[0]
            result[target] = self._label_mapping[target][pred_idx]
        return result

    def predict_proba(self, features, target_names):
        result = {}
        features = np.array(features, dtype=np.float64)
        for target in target_names:
            if target not in self.models:
                continue
            proba_mapped = self.models[target].predict_proba(features)[0]
            label_map = self._label_mapping[target]
            proba = [0.0, 0.0, 0.0]
            for j, label in label_map.items():
                proba[label + 1] = proba_mapped[j]
            result[target] = proba
        return result

    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({"models": self.models, "label_mapping": self._label_mapping}, f)

    def load(self, path: str):
        with open(path, "rb") as f:
            state = pickle.load(f)
        self.models = state["models"]
        self._label_mapping = state["label_mapping"]
```

注意：`_create_classification_labels`、`_load_year_data`、`_evaluate_classifier`、`_get_year_months` 这些辅助函数需要从旧 `trainer.py` 移到共享位置（如 `models/training/helpers.py` 或者保留在 trainer.py 中作为模块级函数）。

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/models/xgboost/
git commit -m "refactor: create self-contained XGBoost module"
```

---

## Task 3: 创建 LSTM 模块（核心修复）

**Files:**
- Create: `backend/src/trade_alpha/models/lstm/normalizer.py`
- Create: `backend/src/trade_alpha/models/lstm/classifier.py`

- [ ] **Step 1: 创建 lstm/normalizer.py**

```python
"""LSTM sequence normalizer."""

import pandas as pd
import numpy as np
from typing import List, Tuple


def create_sequences(
    df: pd.DataFrame,
    feature_fields: List[str],
    target_names: List[str],
    sequence_length: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """构造重叠序列 → 序列内标准化。

    对每只股票：排序 → 构造重叠序列 → 该序列自身 Z-score → 返回 3D。
    """
    X_list, y_list = [], []

    for _, group in df.groupby("ts_code"):
        group = group.sort_values("trade_date")
        values = group[feature_fields].values
        labels = group[target_names].values
        if len(values) < sequence_length + 1:
            continue

        for i in range(len(values) - sequence_length):
            seq = values[i:i + sequence_length].copy()
            label = labels[i + sequence_length - 1]
            if np.isnan(seq).any() or np.isnan(label).any():
                continue

            seq_mean = seq.mean(axis=0)
            seq_std = seq.std(axis=0)
            seq_std[seq_std == 0] = 1.0
            seq = (seq - seq_mean) / seq_std
            X_list.append(seq)
            y_list.append(label)

    if not X_list:
        return np.empty((0, sequence_length, len(feature_fields))), \
               np.empty((0, len(target_names)))
    return np.array(X_list), np.array(y_list)
```

- [ ] **Step 2: 创建 lstm/classifier.py**

```python
"""LSTM classifier - fully self-contained."""

import os
import numpy as np
import torch
import torch.nn as nn
from typing import Dict, List
from trade_alpha.models.base import BaseClassifier


class LSTMModel(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, num_class=3, dropout=0.1):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True,
                            dropout=dropout if num_layers > 1 else 0)
        self.fc = nn.Linear(hidden_size, num_class)

    def forward(self, x):
        out, _ = self.lstm(x)
        return torch.softmax(self.fc(out[:, -1, :]), dim=1)


class LSTMClassifier(BaseClassifier):
    def __init__(self, config):
        super().__init__(config)
        self.sequence_length = config.lstm_sequence_length
        self.models: Dict[str, LSTMModel] = {}
        self.input_size = 0
        self._label_mapping: Dict[str, Dict[int, int]] = {}

    @property
    def name(self) -> str:
        return "lstm"

    async def train(self, ts_codes, start_date, end_date, task_id=None):
        """自闭环训练：加载数据 → 构造序列 → 序列内标准化 → 训练LSTM。"""
        from trade_alpha.models.lstm.normalizer import create_sequences
        from trade_alpha.task.service import TaskService
        from trade_alpha.models.training.trainer import _create_classification_labels, _load_year_data

        await TaskService.update_progress(task_id, 20, "正在加载数据...")

        config = self.config
        target_names = [f"label_{h}d" for h in config.classification_horizons]
        horizon = max(config.classification_horizons)
        seq_len = self.sequence_length
        extra_days = seq_len + 10
        years = sorted(set(y for y, _ in _get_year_months(start_date, end_date)))

        all_dfs = []
        for year_idx, year in enumerate(years):
            year_df = await _load_year_data(year, ts_codes, horizon, extra_days)
            if year_df is None:
                continue
            year_df = _create_classification_labels(
                year_df, config.classification_horizons, config.classification_threshold
            )
            all_dfs.append(year_df)
            await TaskService.update_progress(
                task_id, 20 + (year_idx + 1) / len(years) * 30,
                f"正在处理 {year} 年数据..."
            )

        if not all_dfs:
            raise ValueError("No available data")

        combined_df = pd.concat(all_dfs, ignore_index=True)
        X_3d, y_2d = create_sequences(combined_df, config.feature_fields, target_names, seq_len)

        if len(X_3d) == 0:
            raise ValueError("No sequences created from available data")

        await TaskService.update_progress(task_id, 55, "正在创建模型...")

        self.input_size = X_3d.shape[2]
        self.models = {}
        self._label_mapping = {}
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        X_3d = np.nan_to_num(np.array(X_3d, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
        y_2d = np.array(y_2d, dtype=np.float64)
        valid_mask = ~np.isnan(y_2d).any(axis=1)
        X_3d, y_2d = X_3d[valid_mask], y_2d[valid_mask]

        await TaskService.update_progress(task_id, 60, "正在训练模型...")

        all_epoch_losses = []
        for target_idx, target in enumerate(target_names):
            y_i = y_2d[:, target_idx].astype(int)
            unique_labels = sorted(set(y_i))
            label_map = {j: label for j, label in enumerate(unique_labels)}
            reverse_map = {label: j for j, label in label_map.items()}
            y_mapped = np.array([reverse_map[v] for v in y_i])

            model = LSTMModel(self.input_size, config.lstm_hidden_size, config.lstm_num_layers,
                              len(label_map), config.lstm_dropout).to(device)
            criterion = nn.CrossEntropyLoss()
            optimizer = torch.optim.Adam(model.parameters(), lr=config.lstm_learning_rate)

            X_tensor = torch.FloatTensor(X_3d).to(device)
            y_tensor = torch.LongTensor(y_mapped).to(device)
            loader = torch.utils.data.DataLoader(
                torch.utils.data.TensorDataset(X_tensor, y_tensor),
                batch_size=config.lstm_batch_size, shuffle=True,
            )

            model.train()
            epoch_loss = 0.0
            num_batches = 0
            for _ in range(config.lstm_epochs):
                for batch_X, batch_y in loader:
                    optimizer.zero_grad()
                    criterion(model(batch_X), batch_y).backward()
                    optimizer.step()
                    # track only last epoch
            for batch_X, batch_y in loader:
                with torch.no_grad():
                    epoch_loss += criterion(model(batch_X), batch_y).item()
                    num_batches += 1

            all_epoch_losses.append(epoch_loss / max(num_batches, 1))
            self.models[target] = model.cpu()
            self._label_mapping[target] = label_map

        await TaskService.update_progress(task_id, 80, "正在评估模型...")
        metrics = {"final_train_loss": all_epoch_losses[-1],
                   "loss_per_epoch": all_epoch_losses,
                   "sample_count": len(X_3d)}
        return metrics

    def predict(self, features, target_names):
        seq = np.array(features, dtype=np.float64)
        if len(seq) < self.sequence_length:
            return {}
        seq = seq[-self.sequence_length:]
        seq_mean, seq_std = seq.mean(axis=0), seq.std(axis=0)
        seq_std[seq_std == 0] = 1.0
        seq = np.nan_to_num((seq - seq_mean) / seq_std, nan=0.0)
        X_tensor = torch.FloatTensor(seq).unsqueeze(0)
        result = {}
        for target in target_names:
            if target not in self.models:
                continue
            self.models[target].eval()
            with torch.no_grad():
                pred_idx = self.models[target](X_tensor)[0].argmax().item()
                result[target] = self._label_mapping[target][pred_idx]
        return result

    def predict_proba(self, features, target_names):
        seq = np.array(features, dtype=np.float64)
        if len(seq) < self.sequence_length:
            return {t: [0.0, 0.0, 0.0] for t in target_names}
        seq = seq[-self.sequence_length:]
        seq_mean, seq_std = seq.mean(axis=0), seq.std(axis=0)
        seq_std[seq_std == 0] = 1.0
        seq = np.nan_to_num((seq - seq_mean) / seq_std, nan=0.0)
        X_tensor = torch.FloatTensor(seq).unsqueeze(0)
        result = {}
        for target in target_names:
            if target not in self.models:
                continue
            self.models[target].eval()
            with torch.no_grad():
                proba_mapped = self.models[target](X_tensor)[0].numpy()
                label_map = self._label_mapping[target]
                proba = [0.0, 0.0, 0.0]
                for j, label in label_map.items():
                    proba[label + 1] = proba_mapped[j]
                result[target] = proba
        return result

    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        torch.save({
            "models": {k: v.state_dict() for k, v in self.models.items()},
            "label_mapping": self._label_mapping,
            "input_size": self.input_size,
            "sequence_length": self.sequence_length,
        }, path)

    def load(self, path: str):
        state = torch.load(path, weights_only=False)
        self.input_size = state["input_size"]
        self.sequence_length = state["sequence_length"]
        self._label_mapping = state["label_mapping"]
        self.models = {}
        for target, model_state in state["models"].items():
            model = LSTMModel(self.input_size, self.config.lstm_hidden_size,
                              self.config.lstm_num_layers,
                              len(self._label_mapping[target]))
            model.load_state_dict(model_state)
            self.models[target] = model
```

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/models/lstm/
git commit -m "refactor: create self-contained LSTM module with fixed data flow"
```

---

## Task 4: 重构 trainer.py（变薄）

**Files:**
- Modify: `backend/src/trade_alpha/models/training/trainer.py`

trainer.py 变薄：只做编排调度，不介入数据加载和标准化。辅助函数保留为模块级函数供模型内部调用。

- [ ] **Step 1: 精简 trainer.py**

```python
"""模型训练编排 - 只做调度，数据工作在模型内部。"""

import os
from datetime import datetime, timezone
from typing import Optional, Dict
from beanie import PydanticObjectId
from trade_alpha.dao import TrainingResult, PredictionResult
from trade_alpha.logging import get_logger

logger = get_logger("models.training.trainer")
MODELS_DIR = "models"

# ===== 辅助函数（供模型内部调用） =====

from trade_alpha.utils.date_utils import get_year_months as _get_year_months
from trade_alpha.models.training.helpers import (
    _create_classification_labels,
    _load_year_data,
    _evaluate_classifier,
)

# ===== 训练编排 =====

async def create_training(config_id, name, ts_codes, start_date, end_date, task_id=None):
    from trade_alpha.models.training.config import get_config_by_id

    existing = await get_training_by_name(name)
    if existing:
        raise ValueError(f"Training already exists: {name}")

    config = await get_config_by_id(config_id)
    if not config:
        raise ValueError(f"Config not found: {config_id}")

    if config.model_type == "xgboost":
        from trade_alpha.models.xgboost.classifier import XGBoostClassifier
        classifier = XGBoostClassifier(config)
    elif config.model_type == "lstm":
        from trade_alpha.models.lstm.classifier import LSTMClassifier
        classifier = LSTMClassifier(config)
    else:
        raise ValueError(f"Unknown model type: {config.model_type}")

    metrics = await classifier.train(ts_codes, start_date, end_date, task_id)

    training = TrainingResult(
        config_id=config_id, name=name,
        ts_codes=ts_codes, start_date=start_date, end_date=end_date,
        feature_fields=config.feature_fields,
        classification_horizons=config.classification_horizons,
        model_metrics=metrics,
        created_at=datetime.now(timezone.utc),
    )
    await training.insert()

    os.makedirs(os.path.join(MODELS_DIR, str(config_id)), exist_ok=True)
    model_path = os.path.join(MODELS_DIR, str(config_id), f"{training.id}.pkl")
    classifier.save(model_path)
    training.model_path = model_path
    await training.save()

    logger.info(f"Training completed: name={name} id={training.id}")
    return training


async def get_training_by_id(training_id): ...
async def get_training_by_name(name): ...
async def list_trainings(config_id=None): ...
async def delete_training(training_id): ...
async def delete_training_by_name(name): ...
async def predict_with_training(training_id, ts_code): ...  # 见 Task 5
async def get_prediction_by_id(prediction_id): ...
async def delete_prediction(prediction_id): ...
```

注意：`_create_classification_labels`、`_load_year_data`、`_evaluate_classifier` 等辅助函数需要抽取到 `models/training/helpers.py` 中供 XGBoost 和 LSTM 模型的 `train()` 复用。

- [ ] **Step 2: 创建 helpers.py**

从旧 trainer.py 中抽取 `_create_classification_labels`、`_load_year_data`、`_evaluate_classifier` 到 `backend/src/trade_alpha/models/training/helpers.py`

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/models/training/trainer.py
git add backend/src/trade_alpha/models/training/helpers.py
git commit -m "refactor: thin trainer, move helpers to shared module"
```

---

## Task 5: 重构 predictor.py

**Files:**
- Modify: `backend/src/trade_alpha/execution/predictor.py`

- [ ] **Step 1: 移除适配器引用，按 model_type 分流**

```python
"""简化后的预测器 - 移除适配器，按模型类型分流。"""

from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from beanie import PydanticObjectId
from trade_alpha.models.training.trainer import get_training_by_id
from trade_alpha.models.training.config import get_config_by_id
from trade_alpha.logging import get_logger

logger = get_logger("execution.predictor")


class Predictor:
    def __init__(self, training_id, normalizer=None, data_loader=None):
        self.training_id = training_id
        self._training = None
        self._config = None
        self._classifier = None
        self._data_loader = data_loader

    async def _ensure_model_loaded(self):
        if self._classifier is not None:
            return
        self._training = await get_training_by_id(self.training_id)
        self._config = await get_config_by_id(self._training.config_id)
        from trade_alpha.models import CLASSIFIERS
        self._classifier = CLASSIFIERS[self._config.model_type]()
        self._classifier.load(self._training.model_path)

    async def predict_batch_with_history(self, day_df, ts_codes, current_date):
        await self._ensure_model_loaded()
        result = {}
        if day_df.empty:
            return result

        target_names = [f"label_{h}d" for h in self._training.classification_horizons]

        if self._config.model_type == "xgboost":
            from trade_alpha.models.xgboost.normalizer import normalize as xgb_normalize
            df = await self._data_loader.load_day_data(current_date, ts_codes)
            if df.empty:
                return result
            norm = xgb_normalize(df, self._config.feature_fields,
                                 self._config.standardize_fields, self._config.winsorize_fields)
            for ts_code in ts_codes:
                row = norm[norm["ts_code"] == ts_code]
                if row.empty:
                    continue
                features = row[self._config.feature_fields].values[0].reshape(1, -1)
                if np.isnan(features).any():
                    continue
                self._predict_and_add(result, ts_code, day_df, features, target_names)

        elif self._config.model_type == "lstm":
            seq_len = self._config.lstm_sequence_length
            df = await self._data_loader.load_history_data(current_date, ts_codes, seq_len + 10)
            if df.empty:
                return result
            for ts_code in ts_codes:
                stock = df[df["ts_code"] == ts_code].sort_values("trade_date")
                if len(stock) < seq_len:
                    continue
                features = stock[self._config.feature_fields].values[-seq_len:]
                if np.isnan(features).any():
                    continue
                self._predict_and_add(result, ts_code, day_df, features, target_names)

        return result

    def _predict_and_add(self, result, ts_code, day_df, features, target_names):
        predictions = self._classifier.predict(features, target_names)
        probabilities = self._classifier.predict_proba(features, target_names)
        if not predictions:
            return
        up_prob_3d = probabilities.get("label_3d", [0,0,0])[2] if isinstance(probabilities.get("label_3d"), list) and len(probabilities["label_3d"])==3 else 0
        up_prob_5d = probabilities.get("label_5d", [0,0,0])[2] if isinstance(probabilities.get("label_5d"), list) and len(probabilities["label_5d"])==3 else 0
        down_prob_3d = probabilities.get("label_3d", [0,0,0])[0] if isinstance(probabilities.get("label_3d"), list) and len(probabilities["label_3d"])==3 else 0
        down_prob_5d = probabilities.get("label_5d", [0,0,0])[0] if isinstance(probabilities.get("label_5d"), list) and len(probabilities["label_5d"])==3 else 0
        score = (up_prob_3d - down_prob_3d) * 0.4 + (up_prob_5d - down_prob_5d) * 0.6
        day_row = day_df[day_df["ts_code"] == ts_code]
        result[ts_code] = {
            "up_prob_3d": up_prob_3d, "up_prob_5d": up_prob_5d,
            "down_prob_3d": down_prob_3d, "down_prob_5d": down_prob_5d,
            "score": score, "close": float(day_row.iloc[0]["close"]) if not day_row.empty else 0,
        }

    async def predict_batch(self, df, ts_codes): ...  # 同上分流
    async def predict_single(self, df, ts_code): ...
```

- [ ] **Step 2: 移除 execution/pipeline.py 中的 dead import**

删除 `from trade_alpha.models.normalizers import CrossSectionalNormalizer`

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/execution/predictor.py
git add backend/src/trade_alpha/execution/pipeline.py
git commit -m "refactor: remove adapter usage from predictor, model-type branching"
```

---

## Task 6: 删除旧目录

**Files:**
- Delete: `backend/src/trade_alpha/models/adapters/`
- Delete: `backend/src/trade_alpha/models/classifiers/`
- Delete: `backend/src/trade_alpha/models/normalizers/`

- [ ] **Step 1: 删除目录**

```bash
Remove-Item -Recurse -Force backend/src/trade_alpha/models/adapters
Remove-Item -Recurse -Force backend/src/trade_alpha/models/classifiers
Remove-Item -Recurse -Force backend/src/trade_alpha/models/normalizers
```

- [ ] **Step 2: 验证 import**

```bash
cd backend
python -c "from trade_alpha.models import CLASSIFIERS; print('OK'); c = CLASSIFIERS['xgboost'](); print('XGBoost OK')"
```

- [ ] **Step 3: 提交**

```bash
git add -A
git commit -m "refactor: remove legacy adapters, classifiers, normalizers directories"
```

---

## Task 7: 更新测试

**Files:**
- Modify: 测试文件中的 import 路径

- [ ] **Step 1: 更新测试 import**

更新 `test_cross_sectional.py`、`test_sliding_window.py`、`test_xgboost.py`、`test_lstm.py` 中的 import 路径。

- [ ] **Step 2: 运行测试**

```bash
cd backend
pytest tests/trade_alpha/unit/predict/ -v
pytest tests/trade_alpha/integration/test_35_task_service.py -v
pytest tests/trade_alpha/integration/test_60_task_subprocess.py -v
```

- [ ] **Step 3: 提交**

```bash
git add backend/tests/
git commit -m "test: update imports for new model architecture"
```
