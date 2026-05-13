# 模型训练分类化重构设计方案

> **日期:** 2026-05-13
> **状态:** 待审查

## 1. 目标

将模型训练系统从回归模式重构为纯分类模式：
- 输出标签：看多(1)、中性(0)、看空(-1)
- 支持多周期分类（如同时预测3日、5日标签）
- 集成标准化器，支持灵活的特征字段配置
- 训练前检查股票数据状态

---

## 2. 数据模型变更

### 2.1 ModelConfig (`dao/model_config.py`)

**删除字段：** `params`, `window_size`, `targets`, `target_cols`, `normalizer`

**保留字段：** `name`, `model_type`, `created_at`, `updated_at`

**新增字段：**
```python
feature_fields: List[str] = Field(default_factory=list)    # 特征列，默认用所有相对值指标
classification_horizons: List[int] = Field(default_factory=lambda: [3, 5])  # 分类周期
classification_threshold: float = 0.02                      # 分类阈值 2%
normalizer_fields: Dict[str, Any] = Field(default_factory=dict)  # 标准化器参数
```

**model_type 约束：** 仅支持 `xgboost` 和 `lstm`

### 2.2 TrainingResult (`dao/training.py`)

**删除字段：** `feature_cols`

**保留字段：** `config_id`, `name`, `ts_codes`, `start_date`, `end_date`, `model_path`, `created_at`

**新增字段：**
```python
feature_fields: List[str] = Field(default_factory=list)
classification_horizons: List[int] = Field(default_factory=lambda: [3, 5])
metrics: Dict[str, Any] = Field(default_factory=dict)  # 分类指标：accuracy, precision, recall, f1, confusion_matrix
```

### 2.3 PredictionResult (`dao/prediction.py`)

**删除字段：** `model`, `target_open`, `target_close`, `target_high`, `target_low`

**保留字段：** `ts_code`, `trade_date`, `created_at`

**新增字段：**
```python
training_result_id: PydanticObjectId           # 关联的训练结果ID
predictions: Dict[str, int]                     # {label_3d: 1, label_5d: 0}
probabilities: Dict[str, List[float]]           # {label_3d: [0.1, 0.7, 0.2], ...}  [P(-1), P(0), P(1)]
```

### 2.4 StockList (`dao/stock_list.py`)

**无变更**，训练时使用 `sync_status == "active"` 判断数据是否就绪

---

## 3. API 变更

### 3.1 修改的路由

**`api/routers/trainings.py` 调整：**
```python
# TrainingCreate 调整：
class TrainingCreate(BaseModel):
    config_id: str
    name: str
    ts_codes: List[str]
    start_date: str
    end_date: str

# /trainings/{training_id}/predict 调整：
# 返回值改为 {predictions: dict, probabilities: dict}
```

**`api/routers/predict.py` 重构：**
```python
# 保留文件，但重构为分类模式
class PredictRequest(BaseModel):
    training_result_id: str      # 必填，关联训练结果
    ts_code: str                 # 必填，预测的股票

# GET /predict/{prediction_id}：获取预测结果
# POST /predict：执行预测并持久化
# DELETE /predict/{prediction_id}：删除预测结果
```

**`api/routers/model_configs.py` 调整：**
- `ModelCreateRequest` 改为新的字段定义（无 params, targets 等旧字段）

### 3.2 删除的 Schema

- **删除 `api/schemas.py` 中的 `PredictRequest`, `PredictResponse`**：合并到 routers 中
- **删除 `api/schemas.py` 中的 `ModelCreateRequest`, `ModelResponse`**：合并到 config_service

---

## 4. 预测器重构

### 4.1 删除的文件

- `predict/models/linear.py`：删除

### 4.2 新增 `predict/models/base.py`

```python
class BaseClassifier(ABC):
    """分类器基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """分类器名称"""

    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray, target_names: List[str]) -> None:
        """训练分类模型"""

    @abstractmethod
    def predict(self, features: np.ndarray, target_names: List[str]) -> Dict[str, int]:
        """预测类别标签 {target: -1/0/1}"""

    @abstractmethod
    def predict_proba(self, features: np.ndarray, target_names: List[str]) -> Dict[str, List[float]]:
        """预测各类别概率 {target: [P(-1), P(0), P(1)]}"""

    @abstractmethod
    def save(self, path: str) -> None:
        """保存模型"""

    @abstractmethod
    def load(self, path: str) -> None:
        """加载模型"""
```

### 4.3 重构 `predict/models/xgboost.py` → `XGBoostClassifier`

```python
class XGBoostClassifier(BaseClassifier):
    """XGBoost 多标签分类器"""

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 6,
        learning_rate: float = 0.1,
        num_class: int = 3,  # -1, 0, 1 三类
    ):
        self.models: Dict[str, xgb.XGBClassifier] = {}

    def fit(self, X, y, target_names) -> None:
        # 将 y 中的 -1 映射为 0（XGBoost 需要从 0 开始）
        # 训练 XGBClassifier
        pass

    def predict(self, features, target_names) -> Dict[str, int]:
        # 返回 {target: -1/0/1}
        pass

    def predict_proba(self, features, target_names) -> Dict[str, List[float]]:
        # 返回 {target: [P(0映射-1), P(1映射0), P(2映射1)]}
        # 需要 reorder 概率顺序
        pass

    def save(self, path) -> None: pickle.dump(...)
    def load(self, path) -> None: pickle.load(...)
```

### 4.4 重构 `predict/models/lstm.py` → `LSTMClassifier`

```python
class LSTMClassifier(BaseClassifier):
    """LSTM 多标签分类器"""

    def __init__(
        self,
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.1,
        epochs: int = 50,
        batch_size: int = 32,
        learning_rate: float = 0.001,
        sequence_length: int = 10,
        num_class: int = 3,
    ):
        self.models: Dict[str, LSTMModel] = {}

    # 输出层改为 num_class，用 CrossEntropyLoss
    # predict 返回 argmax(softmax) 映射到 -1/0/1
    # predict_proba 返回 softmax 概率（重新排序为 [P(-1), P(0), P(1)])
```

---

## 5. 训练逻辑重构

### 5.1 分类标签构造

```python
def create_classification_labels(df: pd.DataFrame, horizons: List[int], threshold: float) -> pd.DataFrame:
    """为每个 horizon 构造分类标签列 label_{horizon}d"""
    for horizon in horizons:
        future_pct = (df["close"].shift(-horizon) - df["close"]) / df["close"]
        labels = future_pct.apply(
            lambda x: 1 if x > threshold else (-1 if x < -threshold else 0)
        )
        df[f"label_{horizon}d"] = labels
    # 删除最后 max(horizons) 行（无未来数据）
    return df.iloc[:-max(horizons)]
```

### 5.2 默认特征字段

```python
RELATIVE_INDICATOR_PREFIXES = [
    "ma_", "macd", "pct_chg", "bias_",
    "close_pct_rank_", "vol_ratio_",
    "kdj_", "boll_"
]

def get_default_feature_fields(df_columns: List[str]) -> List[str]:
    """从数据列中筛选所有相对值指标列"""
    features = []
    for col in df_columns:
        for prefix in RELATIVE_INDICATOR_PREFIXES:
            if col.startswith(prefix) or col == prefix.rstrip("_"):
                features.append(col)
                break
    return sorted(set(features))
```

### 5.3 训练流程（`training_service.py`）

```python
async def create_training(config_id, name, ts_codes, start_date, end_date):
    # 1. 获取配置
    config = await get_config_by_id(config_id)

    # 2. 加载所有股票数据，跳过 non-active 的
    all_dfs = []
    for ts_code in ts_codes:
        stock = await StockList.find_one(StockList.ts_code == ts_code)
        if not stock or stock.sync_status != "active":
            logger.warning(f"跳过 {ts_code}（数据未就绪）")
            continue
        records = await StockDaily.find(...).sort(...)
        if len(records) < 100:
            continue
        df = pd.DataFrame([r.model_dump() for r in records])
        df["ts_code"] = ts_code
        all_dfs.append(df)

    if not all_dfs:
        raise ValueError("无可用数据")

    # 3. 合并数据
    combined = pd.concat(all_dfs, ignore_index=True)
    combined = combined.sort_values(["trade_date", "ts_code"])

    # 4. 构造分类标签
    combined = create_classification_labels(
        combined,
        config.classification_horizons,
        config.classification_threshold
    )

    # 5. 确定特征列
    if config.feature_fields:
        feature_fields = config.feature_fields
    else:
        feature_fields = get_default_feature_fields(combined.columns)

    # 6. 标准化
    normalizer = CrossSectionalNormalizer(
        standardize_fields=feature_fields,
        **config.normalizer_fields
    )
    combined = normalizer.normalize(combined)

    # 7. 构造 X, y
    target_names = [f"label_{h}d" for h in config.classification_horizons]
    combined = combined.dropna(subset=feature_fields + target_names)

    X = combined[feature_fields].values
    y = combined[target_names].values

    # 8. 训练
    predictor = CLASSIFIERS[config.model_type]()
    predictor.fit(X, y, target_names)

    # 9. 保存
    # ...
```

### 5.4 预测逻辑（`predict_with_training`）

```python
async def predict_with_training(training_id, ts_code=None):
    # 1. 加载训练结果和配置
    # 2. 加载最新数据
    # 3. 标准化
    # 4. 加载模型
    # 5. predict + predict_proba
    # 6. 保存 PredictionResult
    # 7. 返回
```

---

## 6. 文件变更清单

| 操作 | 文件路径 |
|------|----------|
| 重写 | `dao/model_config.py` |
| 重写 | `dao/prediction.py` |
| 重写 | `dao/training.py` |
| 删除 | `dao/prediction.py`（→ 重建PredictionResult） |
| 删除 | `predict/models/linear.py` |
| 删除 | `predict/service.py`（所有函数已由 training_service.py 替代：predict() 改为先训练再预测架构；get_prediction_by_ts_code/delete_predictions_by_ts_code 移至 training_service.py） |
| 重写 | `predict/models/base.py` → BaseClassifier |
| 重写 | `predict/models/xgboost.py` → XGBoostClassifier |
| 重写 | `predict/models/lstm.py` → LSTMClassifier |
| 删除 | `predict/service.py`（全部删除） |
| 重写 | `predict/training_service.py` |
| 重写 | `predict/config_service.py`（字段验证更新） |
| 重构 | `api/routers/predict.py`（改为分类模式） |
| 修改 | `api/routers/trainings.py`（调整 schema） |
| 修改 | `api/routers/model_configs.py`（调整 schema） |
| 修改 | `api/schemas.py`（删除 PredictRequest, PredictResponse, ModelCreateRequest, ModelResponse） |
| 修改 | `api/main.py`（移除 predict.router） |
| 修改 | `dao/__init__.py`（移除 PredictionResult 导出，如需保留则保留） |

---

## 7. 测试更新

需要更新的测试：
- `tests/trade_alpha/unit/predict/test_service.py`：删除
- `tests/trade_alpha/unit/predict/test_linear.py`：删除
- `tests/trade_alpha/unit/predict/normalizers/test_cross_sectional.py`：可能需调整
- `tests/trade_alpha/integration/test_predict_integration.py`：重写为分类测试
- `tests/trade_alpha/integration/test_51_training_service.py`：重写为分类测试
- `tests/trade_alpha/unit/predict/test_xgboost.py`：新增
- `tests/trade_alpha/unit/predict/test_lstm.py`：新增

---

## 8. 自审查清单

- [x] 所有字段命名统一（fields）
- [x] 删除了所有回归相关代码
- [x] 保留了 PredictionResult 持久化
- [x] TrainingResult 包含 training_result_id 关联
- [x] 删除了 linear.py
- [x] 只保留 xgboost 和 lstm
- [x] 默认特征为相对值指标
- [x] 训练前检查 sync_status == "active"
- [x] 预测接口保留并重构为分类模式
- [x] 三分类标签：-1/0/1
- [x] 默认 horizon: [3, 5]
