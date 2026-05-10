# 模型模块拆分实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将模型模块拆分为模型配置和模型训练两部分，支持一个配置多次训练，回测依赖训练结果。

**Architecture:** 创建 model_configs 和 trainings 两个集合，模型配置定义类型和参数，训练结果记录每次训练的详细信息。训练采用样本混合策略，支持多股票、多目标预测。

**Tech Stack:** Python, MongoDB, FastAPI, scikit-learn, XGBoost, PyTorch

---

## 文件结构

```
backend/src/trade_alpha/predict/
├── __init__.py              # 更新导出
├── base.py                  # 保持不变
├── linear.py                # 保持不变
├── xgboost.py               # 保持不变
├── lstm.py                  # 保持不变
├── config_service.py        # 新增：模型配置服务
├── training_service.py      # 新增：训练服务
└── model_service.py         # 删除（迁移到新服务）

backend/src/trade_alpha/api/routers/
├── model_configs.py         # 新增：模型配置 API
├── trainings.py             # 新增：训练 API
└── models.py                # 删除

backend/tests/trade_alpha/integration/
├── test_43_model_config_service.py  # 新增
├── test_51_training_service.py      # 新增
├── test_42_model_service.py         # 删除
└── test_50_backtest.py              # 修改：使用 training_id
```

---

### Task 1: 创建模型配置服务

**Files:**
- Create: `backend/src/trade_alpha/predict/config_service.py`

- [ ] **Step 1: 创建 config_service.py**

```python
"""Model configuration service."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from bson import ObjectId
from trade_alpha.dao import MongoDB


COLLECTION = "model_configs"


def create_config(
    name: str,
    model_type: str,
    params: Dict[str, Any],
    targets: List[str],
) -> str:
    """Create model configuration.

    Args:
        name: Configuration name (unique)
        model_type: Model type (linear/xgboost/lstm)
        params: Model parameters
        targets: Target columns to predict

    Returns:
        Configuration ID
    """
    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)

    existing = collection.find_one({"name": name})
    if existing:
        dao.close()
        raise ValueError(f"Config already exists: {name}")

    valid_types = ["linear", "xgboost", "lstm"]
    if model_type not in valid_types:
        dao.close()
        raise ValueError(f"Invalid model_type: {model_type}")

    config = {
        "name": name,
        "model_type": model_type,
        "params": params,
        "targets": targets,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    result = collection.insert_one(config)
    dao.close()
    return str(result.inserted_id)


def get_config_by_id(config_id: str) -> Optional[Dict]:
    """Get configuration by ID."""
    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)
    result = collection.find_one({"_id": ObjectId(config_id)})
    dao.close()
    return result


def get_config_by_name(name: str) -> Optional[Dict]:
    """Get configuration by name."""
    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)
    result = collection.find_one({"name": name})
    dao.close()
    return result


def list_configs(model_type: str = None) -> List[Dict]:
    """List configurations with optional filter."""
    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)

    query = {}
    if model_type:
        query["model_type"] = model_type

    results = list(collection.find(query))
    dao.close()
    return results


def update_config(config_id: str, **kwargs) -> bool:
    """Update configuration."""
    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)

    if "name" in kwargs:
        existing = collection.find_one({"name": kwargs["name"], "_id": {"$ne": ObjectId(config_id)}})
        if existing:
            dao.close()
            raise ValueError(f"Config name already exists: {kwargs['name']}")

    kwargs["updated_at"] = datetime.utcnow()
    result = collection.update_one(
        {"_id": ObjectId(config_id)},
        {"$set": kwargs}
    )
    dao.close()
    return result.modified_count > 0


def delete_config(config_id: str) -> bool:
    """Delete configuration and cascade delete trainings."""
    from trade_alpha.predict.training_service import delete_trainings_by_config

    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)

    config = collection.find_one({"_id": ObjectId(config_id)})
    if not config:
        dao.close()
        return False

    delete_trainings_by_config(config_id)

    result = collection.delete_one({"_id": ObjectId(config_id)})
    dao.close()
    return result.deleted_count > 0
```

- [ ] **Step 2: 提交**

```bash
git add backend/src/trade_alpha/predict/config_service.py
git commit -m "feat(predict): add model config service"
```

---

### Task 2: 创建训练服务

**Files:**
- Create: `backend/src/trade_alpha/predict/training_service.py`

- [ ] **Step 1: 创建 training_service.py**

```python
"""Training service."""

import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from bson import ObjectId
from trade_alpha.dao import MongoDB, StockDailyDAO
from trade_alpha.predict.linear import LinearPredictor
from trade_alpha.predict.xgboost import XGBoostPredictor
from trade_alpha.predict.lstm import LSTMPredictor


MODELS_DIR = "models"
COLLECTION = "trainings"

PREDICTORS = {
    "linear": LinearPredictor,
    "xgboost": XGBoostPredictor,
    "lstm": LSTMPredictor,
}


def _ensure_model_dir(config_id: str):
    """Ensure model directory exists for config."""
    os.makedirs(os.path.join(MODELS_DIR, config_id), exist_ok=True)


def create_training(
    config_id: str,
    name: str,
    ts_codes: List[str],
    start_date: str,
    end_date: str,
) -> str:
    """Create training with sample mixing strategy.

    Args:
        config_id: Model configuration ID
        name: Training name
        ts_codes: List of stock codes
        start_date: Start date (YYYYMMDD)
        end_date: End date (YYYYMMDD)

    Returns:
        Training ID
    """
    import pandas as pd
    import numpy as np
    from sklearn.metrics import mean_squared_error, mean_absolute_error

    from trade_alpha.predict.config_service import get_config_by_id

    config = get_config_by_id(config_id)
    if not config:
        raise ValueError(f"Config not found: {config_id}")

    model_type = config["model_type"]
    params = config.get("params", {})
    targets = config["targets"]

    dao = StockDailyDAO()
    all_dfs = []

    for ts_code in ts_codes:
        records = dao.find_by_ts_code(ts_code)
        if not records:
            continue
        df = pd.DataFrame(records)
        df = df[(df["trade_date"] >= start_date) & (df["trade_date"] <= end_date)]
        df["ts_code"] = ts_code
        all_dfs.append(df)

    if not all_dfs:
        dao.db.close()
        raise ValueError("No data found for specified stocks and date range")

    combined_df = pd.concat(all_dfs, ignore_index=True)

    feature_cols = ["open", "high", "low", "close", "vol"]
    indicator_cols = [col for col in combined_df.columns if col.startswith(("ma_", "macd"))]
    all_feature_cols = [col for col in feature_cols + indicator_cols if col in combined_df.columns]

    combined_df = combined_df.dropna(subset=all_feature_cols + targets)
    combined_df = combined_df.sort_values(["trade_date", "ts_code"])

    if len(combined_df) < 20:
        dao.db.close()
        raise ValueError("Insufficient data for training (minimum 20 samples)")

    X = combined_df[all_feature_cols].values[:-1]
    y = combined_df[targets].values[1:]

    predictor = PREDICTORS[model_type](**params)
    predictor.fit(X, y, targets)

    last_features = combined_df[all_feature_cols].iloc[-1:].values
    predictions = predictor.predict(last_features, targets)
    actuals = combined_df[targets].iloc[-1].to_dict()

    metrics = {}
    for target in targets:
        actual_val = actuals.get(target, 0)
        pred_val = predictions.get(target, 0)
        metrics[f"{target}_mse"] = float((actual_val - pred_val) ** 2)
        metrics[f"{target}_mae"] = float(abs(actual_val - pred_val))
    metrics["sample_count"] = len(combined_df)

    storage = MongoDB()
    collection = storage._get_collection(COLLECTION)

    training = {
        "config_id": ObjectId(config_id),
        "name": name,
        "ts_codes": ts_codes,
        "start_date": start_date,
        "end_date": end_date,
        "feature_cols": all_feature_cols,
        "metrics": metrics,
        "created_at": datetime.utcnow(),
    }

    result = collection.insert_one(training)
    training_id = str(result.inserted_id)

    _ensure_model_dir(config_id)
    model_path = os.path.join(MODELS_DIR, config_id, f"{training_id}.pkl")
    predictor.save(model_path)

    collection.update_one(
        {"_id": ObjectId(training_id)},
        {"$set": {"model_path": model_path}}
    )

    storage.close()
    dao.db.close()
    return training_id


def get_training_by_id(training_id: str) -> Optional[Dict]:
    """Get training by ID."""
    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)
    result = collection.find_one({"_id": ObjectId(training_id)})
    dao.close()
    return result


def list_trainings(config_id: str = None) -> List[Dict]:
    """List trainings with optional filter."""
    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)

    query = {}
    if config_id:
        query["config_id"] = ObjectId(config_id)

    results = list(collection.find(query))
    dao.close()
    return results


def delete_training(training_id: str) -> bool:
    """Delete training and model file."""
    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)

    training = collection.find_one({"_id": ObjectId(training_id)})
    if not training:
        dao.close()
        return False

    if training.get("model_path") and os.path.exists(training["model_path"]):
        os.remove(training["model_path"])

    result = collection.delete_one({"_id": ObjectId(training_id)})
    dao.close()
    return result.deleted_count > 0


def delete_trainings_by_config(config_id: str) -> int:
    """Delete all trainings for a config."""
    trainings = list_trainings(config_id)
    count = 0
    for t in trainings:
        if delete_training(str(t["_id"])):
            count += 1
    return count


def predict_with_training(training_id: str, ts_code: str = None) -> Dict[str, float]:
    """Predict using trained model.

    Args:
        training_id: Training ID
        ts_code: Stock code (optional, uses first from training)

    Returns:
        Predictions dict
    """
    import pandas as pd

    from trade_alpha.predict.config_service import get_config_by_id

    training = get_training_by_id(training_id)
    if not training:
        raise ValueError(f"Training not found: {training_id}")

    config = get_config_by_id(str(training["config_id"]))
    if not config:
        raise ValueError(f"Config not found: {training['config_id']}")

    ts_code = ts_code or training["ts_codes"][0]

    dao = StockDailyDAO()
    records = dao.find_by_ts_code(ts_code)
    dao.db.close()

    if not records:
        raise ValueError(f"No data found for {ts_code}")

    df = pd.DataFrame(records)
    df = df.sort_values("trade_date")

    feature_cols = training["feature_cols"]
    df = df.dropna(subset=feature_cols)

    predictor = PREDICTORS[config["model_type"]]()
    predictor.load(training["model_path"])

    last_features = df[feature_cols].iloc[-1:].values
    predictions = predictor.predict(last_features, config["targets"])

    return predictions
```

- [ ] **Step 2: 提交**

```bash
git add backend/src/trade_alpha/predict/training_service.py
git commit -m "feat(predict): add training service with sample mixing"
```

---

### Task 3: 更新 predict 模块导出

**Files:**
- Modify: `backend/src/trade_alpha/predict/__init__.py`

- [ ] **Step 1: 更新 __init__.py**

```python
"""Predict module."""

from trade_alpha.predict.base import BasePredictor
from trade_alpha.predict.linear import LinearPredictor
from trade_alpha.predict.xgboost import XGBoostPredictor
from trade_alpha.predict.lstm import LSTMPredictor
from trade_alpha.predict import config_service
from trade_alpha.predict import training_service

__all__ = [
    "BasePredictor",
    "LinearPredictor",
    "XGBoostPredictor",
    "LSTMPredictor",
    "config_service",
    "training_service",
]
```

- [ ] **Step 2: 提交**

```bash
git add backend/src/trade_alpha/predict/__init__.py
git commit -m "refactor(predict): update exports for config and training services"
```

---

### Task 4: 创建模型配置 API

**Files:**
- Create: `backend/src/trade_alpha/api/routers/model_configs.py`

- [ ] **Step 1: 创建 model_configs.py**

```python
"""Model configuration API router."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from trade_alpha.predict import config_service

router = APIRouter(prefix="/model-configs", tags=["model-configs"])


class ConfigCreate(BaseModel):
    name: str
    model_type: str
    params: Dict[str, Any] = {}
    targets: List[str]


class ConfigUpdate(BaseModel):
    name: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    targets: Optional[List[str]] = None


class ConfigResponse(BaseModel):
    id: str
    name: str
    model_type: str
    params: Dict[str, Any]
    targets: List[str]


@router.post("", response_model=ConfigResponse)
def create_config(body: ConfigCreate):
    """Create model configuration."""
    try:
        config_id = config_service.create_config(
            name=body.name,
            model_type=body.model_type,
            params=body.params,
            targets=body.targets,
        )
        config = config_service.get_config_by_id(config_id)
        return ConfigResponse(
            id=str(config["_id"]),
            name=config["name"],
            model_type=config["model_type"],
            params=config["params"],
            targets=config["targets"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[ConfigResponse])
def list_configs(model_type: str = None):
    """List model configurations."""
    configs = config_service.list_configs(model_type=model_type)
    return [
        ConfigResponse(
            id=str(c["_id"]),
            name=c["name"],
            model_type=c["model_type"],
            params=c["params"],
            targets=c["targets"],
        )
        for c in configs
    ]


@router.get("/{config_id}", response_model=ConfigResponse)
def get_config(config_id: str):
    """Get model configuration by ID."""
    config = config_service.get_config_by_id(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    return ConfigResponse(
        id=str(config["_id"]),
        name=config["name"],
        model_type=config["model_type"],
        params=config["params"],
        targets=config["targets"],
    )


@router.put("/{config_id}", response_model=ConfigResponse)
def update_config(config_id: str, body: ConfigUpdate):
    """Update model configuration."""
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        config_service.update_config(config_id, **update_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    config = config_service.get_config_by_id(config_id)
    return ConfigResponse(
        id=str(config["_id"]),
        name=config["name"],
        model_type=config["model_type"],
        params=config["params"],
        targets=config["targets"],
    )


@router.delete("/{config_id}")
def delete_config(config_id: str):
    """Delete model configuration and cascade delete trainings."""
    deleted = config_service.delete_config(config_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Config not found")
    return {"deleted": True}
```

- [ ] **Step 2: 提交**

```bash
git add backend/src/trade_alpha/api/routers/model_configs.py
git commit -m "feat(api): add model config API endpoints"
```

---

### Task 5: 创建训练 API

**Files:**
- Create: `backend/src/trade_alpha/api/routers/trainings.py`

- [ ] **Step 1: 创建 trainings.py**

```python
"""Training API router."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from trade_alpha.predict import training_service

router = APIRouter(prefix="/trainings", tags=["trainings"])


class TrainingCreate(BaseModel):
    config_id: str
    name: str
    ts_codes: List[str]
    start_date: str
    end_date: str


class PredictRequest(BaseModel):
    ts_code: Optional[str] = None


class TrainingResponse(BaseModel):
    id: str
    config_id: str
    name: str
    ts_codes: List[str]
    start_date: str
    end_date: str
    metrics: Dict[str, Any]


@router.post("", response_model=TrainingResponse)
def create_training(body: TrainingCreate):
    """Create training."""
    try:
        training_id = training_service.create_training(
            config_id=body.config_id,
            name=body.name,
            ts_codes=body.ts_codes,
            start_date=body.start_date,
            end_date=body.end_date,
        )
        training = training_service.get_training_by_id(training_id)
        return TrainingResponse(
            id=str(training["_id"]),
            config_id=str(training["config_id"]),
            name=training["name"],
            ts_codes=training["ts_codes"],
            start_date=training["start_date"],
            end_date=training["end_date"],
            metrics=training["metrics"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[TrainingResponse])
def list_trainings(config_id: str = None):
    """List trainings."""
    trainings = training_service.list_trainings(config_id=config_id)
    return [
        TrainingResponse(
            id=str(t["_id"]),
            config_id=str(t["config_id"]),
            name=t["name"],
            ts_codes=t["ts_codes"],
            start_date=t["start_date"],
            end_date=t["end_date"],
            metrics=t["metrics"],
        )
        for t in trainings
    ]


@router.get("/{training_id}", response_model=TrainingResponse)
def get_training(training_id: str):
    """Get training by ID."""
    training = training_service.get_training_by_id(training_id)
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")
    return TrainingResponse(
        id=str(training["_id"]),
        config_id=str(training["config_id"]),
        name=training["name"],
        ts_codes=training["ts_codes"],
        start_date=training["start_date"],
        end_date=training["end_date"],
        metrics=training["metrics"],
    )


@router.delete("/{training_id}")
def delete_training(training_id: str):
    """Delete training."""
    deleted = training_service.delete_training(training_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Training not found")
    return {"deleted": True}


@router.post("/{training_id}/predict")
def predict(training_id: str, body: PredictRequest = None):
    """Predict using trained model."""
    try:
        ts_code = body.ts_code if body else None
        predictions = training_service.predict_with_training(training_id, ts_code)
        return {"predictions": predictions}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 2: 提交**

```bash
git add backend/src/trade_alpha/api/routers/trainings.py
git commit -m "feat(api): add training API endpoints"
```

---

### Task 6: 更新主应用路由

**Files:**
- Modify: `backend/src/trade_alpha/api/main.py`

- [ ] **Step 1: 添加新路由**

在现有路由后添加：

```python
from trade_alpha.api.routers import model_configs, trainings

app.include_router(model_configs.router)
app.include_router(trainings.router)
```

- [ ] **Step 2: 删除旧路由**

移除：
```python
from trade_alpha.api.routers import models
app.include_router(models.router)
```

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/api/main.py
git commit -m "refactor(api): update routes for model configs and trainings"
```

---

### Task 7: 删除旧文件

**Files:**
- Delete: `backend/src/trade_alpha/predict/model_service.py`
- Delete: `backend/src/trade_alpha/api/routers/models.py`

- [ ] **Step 1: 删除文件**

```bash
rm backend/src/trade_alpha/predict/model_service.py
rm backend/src/trade_alpha/api/routers/models.py
```

- [ ] **Step 2: 提交**

```bash
git add -A
git commit -m "refactor: remove old model service and API"
```

---

### Task 8: 创建模型配置集成测试

**Files:**
- Create: `backend/tests/trade_alpha/integration/test_43_model_config_service.py`

- [ ] **Step 1: 创建测试文件**

```python
"""Integration tests for model config service."""

import pytest
from trade_alpha.predict import config_service


@pytest.mark.integration
@pytest.mark.order(43)
class TestModelConfigService:
    """Integration tests for model config service."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        self.default_config_name = "test_model_config"

        yield

        configs = config_service.list_configs()
        for c in configs:
            if c["name"] != self.default_config_name:
                config_service.delete_config(str(c["_id"]))

    def test_create_config(self):
        """Test creating config."""
        config_id = config_service.create_config(
            name="test_create_temp",
            model_type="xgboost",
            params={"n_estimators": 50},
            targets=["close"],
        )

        assert config_id is not None

        config = config_service.get_config_by_id(config_id)
        assert config is not None
        assert config["model_type"] == "xgboost"

    def test_create_duplicate_config(self):
        """Test creating duplicate config fails."""
        config_service.create_config(
            name="test_dup_temp",
            model_type="linear",
            params={},
            targets=["close"],
        )

        with pytest.raises(ValueError, match="already exists"):
            config_service.create_config(
                name="test_dup_temp",
                model_type="linear",
                params={},
                targets=["close"],
            )

    def test_list_configs(self):
        """Test listing configs."""
        config_service.create_config(
            name="test_list_temp",
            model_type="linear",
            params={},
            targets=["close"],
        )

        configs = config_service.list_configs()
        assert len(configs) > 0

    def test_update_config(self):
        """Test updating config."""
        config_id = config_service.create_config(
            name="test_update_temp",
            model_type="linear",
            params={},
            targets=["close"],
        )

        config_service.update_config(config_id, params={"n_estimators": 100})

        config = config_service.get_config_by_id(config_id)
        assert config["params"]["n_estimators"] == 100

    def test_delete_config(self):
        """Test deleting config."""
        config_id = config_service.create_config(
            name="test_delete_temp",
            model_type="linear",
            params={},
            targets=["close"],
        )

        deleted = config_service.delete_config(config_id)
        assert deleted is True

        config = config_service.get_config_by_id(config_id)
        assert config is None

    def test_ensure_default_config(self):
        """Ensure default config exists for Layer 5 tests."""
        existing = config_service.get_config_by_name(self.default_config_name)
        if existing:
            return

        config_service.create_config(
            name=self.default_config_name,
            model_type="linear",
            params={},
            targets=["close"],
        )
```

- [ ] **Step 2: 提交**

```bash
git add backend/tests/trade_alpha/integration/test_43_model_config_service.py
git commit -m "test: add integration tests for model config service"
```

---

### Task 9: 创建训练服务集成测试

**Files:**
- Create: `backend/tests/trade_alpha/integration/test_51_training_service.py`

- [ ] **Step 1: 创建测试文件**

```python
"""Integration tests for training service."""

import pytest
from trade_alpha.predict import config_service, training_service
from trade_alpha.data import fetch_and_store_stock_daily


@pytest.mark.integration
@pytest.mark.order(51)
class TestTrainingService:
    """Integration tests for training service."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        self.ts_code = "002594.SZ"
        self.backup_ts_code = "601398.SH"
        self.start_date = "20230101"
        self.end_date = "20231231"
        self.default_config_name = "test_model_config"
        self.default_training_name = "test_training"

        fetch_and_store_stock_daily(self.ts_code, self.start_date, self.end_date)
        fetch_and_store_stock_daily(self.backup_ts_code, self.start_date, self.end_date)

        config = config_service.get_config_by_name(self.default_config_name)
        if config:
            self.config_id = str(config["_id"])
        else:
            self.config_id = config_service.create_config(
                name=self.default_config_name,
                model_type="linear",
                params={},
                targets=["close"],
            )

        yield

        trainings = training_service.list_trainings(config_id=self.config_id)
        for t in trainings:
            if t["name"] != self.default_training_name:
                training_service.delete_training(str(t["_id"]))

    def test_create_training_single_stock(self):
        """Test creating training with single stock."""
        training_id = training_service.create_training(
            config_id=self.config_id,
            name="test_single_temp",
            ts_codes=[self.ts_code],
            start_date=self.start_date,
            end_date=self.end_date,
        )

        assert training_id is not None

        training = training_service.get_training_by_id(training_id)
        assert training is not None
        assert self.ts_code in training["ts_codes"]

    def test_create_training_multi_stocks(self):
        """Test creating training with multiple stocks."""
        training_id = training_service.create_training(
            config_id=self.config_id,
            name="test_multi_temp",
            ts_codes=[self.ts_code, self.backup_ts_code],
            start_date=self.start_date,
            end_date=self.end_date,
        )

        assert training_id is not None

        training = training_service.get_training_by_id(training_id)
        assert len(training["ts_codes"]) == 2

    def test_list_trainings(self):
        """Test listing trainings."""
        training_service.create_training(
            config_id=self.config_id,
            name="test_list_temp",
            ts_codes=[self.ts_code],
            start_date=self.start_date,
            end_date=self.end_date,
        )

        trainings = training_service.list_trainings()
        assert len(trainings) > 0

    def test_list_trainings_by_config(self):
        """Test listing trainings by config."""
        training_service.create_training(
            config_id=self.config_id,
            name="test_filter_temp",
            ts_codes=[self.ts_code],
            start_date=self.start_date,
            end_date=self.end_date,
        )

        trainings = training_service.list_trainings(config_id=self.config_id)
        assert all(str(t["config_id"]) == self.config_id for t in trainings)

    def test_delete_training(self):
        """Test deleting training."""
        training_id = training_service.create_training(
            config_id=self.config_id,
            name="test_delete_temp",
            ts_codes=[self.ts_code],
            start_date=self.start_date,
            end_date=self.end_date,
        )

        deleted = training_service.delete_training(training_id)
        assert deleted is True

        training = training_service.get_training_by_id(training_id)
        assert training is None

    def test_predict(self):
        """Test prediction with trained model."""
        training_id = training_service.create_training(
            config_id=self.config_id,
            name="test_predict_temp",
            ts_codes=[self.ts_code],
            start_date=self.start_date,
            end_date=self.end_date,
        )

        predictions = training_service.predict_with_training(training_id)
        assert "close" in predictions

    def test_ensure_default_training(self):
        """Ensure default training exists for Layer 6 tests."""
        trainings = training_service.list_trainings(config_id=self.config_id)
        for t in trainings:
            if t["name"] == self.default_training_name:
                return

        training_service.create_training(
            config_id=self.config_id,
            name=self.default_training_name,
            ts_codes=[self.ts_code],
            start_date=self.start_date,
            end_date=self.end_date,
        )
```

- [ ] **Step 2: 提交**

```bash
git add backend/tests/trade_alpha/integration/test_51_training_service.py
git commit -m "test: add integration tests for training service"
```

---

### Task 10: 删除旧测试文件

**Files:**
- Delete: `backend/tests/trade_alpha/integration/test_42_model_service.py`

- [ ] **Step 1: 删除文件**

```bash
rm backend/tests/trade_alpha/integration/test_42_model_service.py
```

- [ ] **Step 2: 提交**

```bash
git add -A
git commit -m "test: remove old model service tests"
```

---

### Task 11: 更新集成测试文档

**Files:**
- Modify: `docs/integration-tests.md`

- [ ] **Step 1: 更新测试顺序表**

添加 Layer 5 和 Layer 6：

```markdown
| Layer 4 | 43 | test_43_model_config_service.py | TestModelConfigService | 验证模型配置服务 |
| Layer 5 | 51 | test_51_training_service.py | TestTrainingService | 验证训练服务 |
| Layer 6 | 60 | test_60_backtest.py | TestBacktest | 验证回测服务 |
```

- [ ] **Step 2: 更新依赖关系图**

添加 Training 层。

- [ ] **Step 3: 提交**

```bash
git add docs/integration-tests.md
git commit -m "docs: update integration tests for training layer"
```

---

### Task 12: 运行测试验证

- [ ] **Step 1: 运行集成测试**

```bash
cd backend
$env:PYTHONPATH='src'
pytest tests/trade_alpha/integration/ -v
```

Expected: All tests pass

- [ ] **Step 2: 提交最终变更**

```bash
git push
```

---

## 自检清单

- [ ] Spec coverage: 每个需求都有对应任务
- [ ] Placeholder scan: 无 TBD/TODO
- [ ] Type consistency: 类型和方法签名一致
