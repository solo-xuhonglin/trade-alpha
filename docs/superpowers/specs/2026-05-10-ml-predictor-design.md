# 机器学习预测模块设计文档

## 概述

新增 XGBoost 和 LSTM 预测算法，实现模型持久化，统一使用 ID 作为资源标识。

## 架构设计

### 目录结构

```
backend/
├── models/                        # 模型文件存储目录
│   ├── linear/
│   ├── xgboost/
│   └── lstm/
└── src/trade_alpha/
    └── predict/
        ├── __init__.py
        ├── base.py               # BasePredictor 基类
        ├── linear.py             # LinearPredictor
        ├── xgboost.py            # XGBoostPredictor（新增）
        ├── lstm.py               # LSTMPredictor（新增）
        ├── service.py            # 预测服务
        └── model_service.py      # 模型管理服务（新增）
```

### 类设计

#### BasePredictor 更新

```python
class BasePredictor(ABC):
    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray, targets: list[str]) -> None: ...
    
    @abstractmethod
    def predict(self, features: np.ndarray, targets: list[str]) -> dict[str, float]: ...
    
    @abstractmethod
    def save(self, path: str) -> None: ...
    
    @abstractmethod
    def load(self, path: str) -> None: ...
```

#### XGBoostPredictor

```python
class XGBoostPredictor(BasePredictor):
    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 6,
        learning_rate: float = 0.1,
        min_child_weight: int = 1,
        subsample: float = 1.0,
        colsample_bytree: float = 1.0,
    ): ...
```

#### LSTMPredictor

```python
class LSTMPredictor(BasePredictor):
    def __init__(
        self,
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.1,
        epochs: int = 50,
        batch_size: int = 32,
        learning_rate: float = 0.001,
        sequence_length: int = 10,
    ): ...
```

## 数据库设计

### models 集合

```json
{
    "_id": ObjectId,
    "name": "my_xgboost_model",
    "model_type": "xgboost",
    "ts_code": "000001.SZ",
    "targets": ["open", "close", "high", "low"],
    "params": {
        "n_estimators": 200,
        "max_depth": 8
    },
    "feature_cols": ["open", "close", "ma_5", "macd"],
    "train_date_range": {
        "start": "20200101",
        "end": "20241231"
    },
    "metrics": {
        "mse": 0.05,
        "mae": 0.03
    },
    "model_path": "models/xgboost/<id>.pkl",
    "created_at": ISODate,
    "updated_at": ISODate
}
```

## API 设计

### 模型管理 API

| 方法 | 路径 | 说明 |
|-----|------|------|
| POST | /api/models | 创建/训练模型 |
| GET | /api/models | 列出模型 |
| GET | /api/models/{id} | 获取模型详情 |
| DELETE | /api/models/{id} | 删除模型 |
| POST | /api/models/{id}/predict | 使用模型预测 |

### 创建模型请求

```json
{
    "name": "my_xgboost_model",
    "model_type": "xgboost",
    "ts_code": "000001.SZ",
    "targets": ["open", "close"],
    "params": {
        "n_estimators": 200,
        "max_depth": 8
    },
    "start_date": "20200101",
    "end_date": "20241231"
}
```

### 策略 API 调整

| 方法 | 路径 | 说明 |
|-----|------|------|
| POST | /api/strategies | 创建策略 |
| GET | /api/strategies | 列出策略 |
| GET | /api/strategies/{id} | 获取策略详情 |
| PUT | /api/strategies/{id} | 更新策略 |
| DELETE | /api/strategies/{id} | 删除策略 |

## 依赖

```
# requirements.txt 新增
xgboost>=2.0.0
torch>=2.0.0
```

## 实现任务

1. 更新 BasePredictor 添加 save/load 方法
2. 实现 XGBoostPredictor
3. 实现 LSTMPredictor
4. 创建 models 存储目录
5. 实现 model_service.py 模型管理服务
6. 创建 models API 路由
7. 更新策略 API 使用 ID
8. 添加集成测试
