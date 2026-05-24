# Predictor 分层重构设计

## 问题

当前 `Predictor` 类通过 `if model_type == "xgboost" / elif == "lstm"` 分支处理不同模型的数据加载和特征提取，共 3 处分支。新增模型类型时必须修改 Predictor 代码。

## 目标

Predictor 改为分层结构，与 Classifier 体系并列：

```
BasePredictor (抽象)
  ├── XGBoostPredictor  (封装 XGBoostClassifier)
  └── LSTMPredictor     (封装 LSTMClassifier)
```

每个实现类负责：
- 自己需要多少天历史数据（`required_history_days`）
- 如何从 DataFrame 提取特征（`prepare_features`）
- predict_proba 来自内部的 classifier

BasePredictor 负责：
- 持有 classifier 引用
- 统一计算分数（up_prob_3d、down_prob_5d、score、close）
- 业务方法：`predict_batch`、`predict_single`、`predict_batch_with_history`

## 当前代码链路

```
Pipeline → Predictor(training_id, data_loader)
  → _ensure_model_loaded: if xgboost/lstm (import 分支)
  → predict_batch_with_history: if xgboost/lstm (数据加载 + 特征提取分支)
  → _predict_single: if xgboost/lstm (标准化分支)
  → _predict_and_add / _predict_single: 分数计算 (重复)
```

## 新的设计

### BasePredictor

```python
class BasePredictor(ABC):
    def __init__(self, config, classifier, data_loader=None):
        self.config = config
        self.classifier = classifier
        self._data_loader = data_loader

    @property
    @abstractmethod
    def required_history_days(self) -> int: ...

    @abstractmethod
    def prepare_features(self, df: pd.DataFrame, ts_code: str) -> np.ndarray: ...

    @property
    @abstractmethod
    def target_names(self) -> List[str]: ...

    def predict(self, df, ts_code) -> dict:
        features = self.prepare_features(df, ts_code)
        probs = self.classifier.predict_proba(features, self.target_names)
        return self._compute_score(probs, df, ts_code)

    def predict_batch(self, df, ts_codes) -> dict:
        result = {}
        for ts_code in ts_codes:
            try:
                result[ts_code] = self.predict(df, ts_code)
            except Exception as e:
                logger.warning(f"Predict failed for {ts_code}: {e}")
        return result

    async def predict_batch_with_history(self, day_df, ts_codes, current_date) -> dict:
        result = {}
        if day_df.empty:
            return result
        df = await self._data_loader.load_history_data(
            current_date, ts_codes, self.required_history_days
        )
        if df.empty:
            return result
        for ts_code in ts_codes:
            try:
                pred = self.predict(df, ts_code)
                if pred is not None:
                    result[ts_code] = pred
            except Exception as e:
                logger.warning(f"Predict failed for {ts_code}: {e}")
        return result

    def _compute_score(self, probs, df, ts_code) -> dict:
        if not probs:
            return {}
        up_3d = probs.get("label_3d", [0,0,0])[2]
        up_5d = probs.get("label_5d", [0,0,0])[2]
        down_3d = probs.get("label_3d", [0,0,0])[0]
        down_5d = probs.get("label_5d", [0,0,0])[0]
        score = (up_3d - down_3d) * 0.4 + (up_5d - down_5d) * 0.6
        close = 0
        stock = df[df["ts_code"] == ts_code]
        if not stock.empty and "close" in stock.columns:
            close = float(stock.iloc[-1]["close"])
        return {
            "up_prob_3d": up_3d, "up_prob_5d": up_5d,
            "down_prob_3d": down_3d, "down_prob_5d": down_5d,
            "score": score, "close": close,
        }
```

### XGBoostPredictor

```python
class XGBoostPredictor(BasePredictor):
    @property
    def required_history_days(self) -> int:
        return 1

    @property
    def target_names(self) -> List[str]:
        return [f"label_{h}d" for h in self.config.classification_horizons]

    def prepare_features(self, df, ts_code) -> np.ndarray:
        from trade_alpha.models.xgboost.normalizer import normalize
        stock = df[df["ts_code"] == ts_code]
        norm = normalize(stock, self.config.feature_fields,
                         self.config.standardize_fields, self.config.winsorize_fields)
        features = norm[self.config.feature_fields].iloc[-1:].values
        if np.isnan(features).any():
            raise ValueError(f"NaN features for {ts_code}")
        return features
```

### LSTMPredictor

```python
class LSTMPredictor(BasePredictor):
    @property
    def required_history_days(self) -> int:
        return self.config.lstm_sequence_length + 10

    @property
    def target_names(self) -> List[str]:
        return [f"label_{h}d" for h in self.config.classification_horizons]

    def prepare_features(self, df, ts_code) -> np.ndarray:
        stock = df[df["ts_code"] == ts_code].sort_values("trade_date")
        if len(stock) < self.config.lstm_sequence_length:
            raise ValueError(f"Not enough history for {ts_code}")
        features = stock[self.config.feature_fields].values[-self.config.lstm_sequence_length:]
        if np.isnan(features).any():
            raise ValueError(f"NaN features for {ts_code}")
        return features
```

### Factory

```python
def create_predictor(training_id, data_loader=None) -> BasePredictor:
    training = get_training_by_id(training_id)
    config = get_config_by_id(training.config_id)

    if config.model_type == "xgboost":
        from trade_alpha.models.xgboost.classifier import XGBoostClassifier
        classifier = XGBoostClassifier(config)
    elif config.model_type == "lstm":
        from trade_alpha.models.lstm.classifier import LSTMClassifier
        classifier = LSTMClassifier(config)
    else:
        raise ValueError(f"Unknown model type: {config.model_type}")

    classifier.load(training.model_path)

    if config.model_type == "xgboost":
        return XGBoostPredictor(config, classifier, data_loader)
    elif config.model_type == "lstm":
        return LSTMPredictor(config, classifier, data_loader)
```

### Pipeline 修改

原来的 `self.predictor = Predictor(training_id, ...)` 改为：
```python
self.predictor = create_predictor(training_id, data_loader=self.data_loader)
```

## 文件结构

| 文件 | 内容 |
|------|------|
| `execution/predictor.py`（重写） | BasePredictor、XGBoostPredictor、LSTMPredictor、create_predictor |
| `execution/pipeline.py` | 改为调用 create_predictor |
| `models/base.py` | 不变 |

## 测试

- 测试 XGBoostPredictor：prepare_features 返回正确形状 + predict 返回分数
- 测试 LSTMPredictor：同上
