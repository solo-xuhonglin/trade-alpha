# Predictor 分层重构设计

## 当前分析

### Predictor 当前职责

[current Predictor](file:///d:/projects/trade-alpha/backend/src/trade_alpha/execution/predictor.py) 混合了以下职责：

| 职责 | 方法 | 需要的数据 |
|------|------|-----------|
| 加载 classifier 模型 | `_ensure_model_loaded` | training_id → DB |
| 加载历史数据 | `predict_batch_with_history` | data_loader |
| 提取特征（依赖模型类型） | `predict_batch_with_history` + `_predict_single` | DataFrame |
| 调用 predict_proba | `_predict_and_add` + `_predict_single` | features |
| 计算分数（up_prob/down_prob/score/close） | `_predict_and_add` + `_predict_single` | probabilities |
| 循环多只股票 | `predict_batch_with_history` + `predict_batch` | ts_codes |

其中 **模型类型分支** 出现在 3 处：

1. `_ensure_model_loaded`（第28-35行）：导入哪个 classifier
2. `predict_batch_with_history`（第48-76行）：XGB 用 load_day_data + cross-section normalize；LSTM 用 load_history_data + 截取后 seq_len 行
3. `_predict_single`（第116-123行）：XGB 调用 normalize 再取最后一行；LSTM 直接截取后 seq_len 行

### 调用方

[Pipeline](file:///d:/projects/trade-alpha/backend/src/trade_alpha/execution/pipeline.py) 对 Predictor 只有两种调用：

| 调用点 | 方法 | 入参 | 返回 |
|--------|------|------|------|
| 回测（L285-286） | `predict_batch_with_history(day_df, ts_codes, date)` | 当日数据 + 股票列表 + 日期 | `{ts_code: {up_prob_3d, up_prob_5d, down_prob_3d, down_prob_5d, score, close}}` |
| 实盘（L417） | `predict_batch(day_df, ts_codes)` | 当日数据 + 股票列表 | 同上 |

## 目标

BasePredictor 只负责**预测本身**：从 DataFrame 提取特征 → 调用 predict_proba → 返回原始概率。

按模型类型分层：

```
BasePredictor (抽象)
  ├── XGBoostPredictor
  └── LSTMPredictor
```

其他职责（数据加载、分数计算、循环多股票）上移到调用方（Pipeline）或抽取为独立函数。

## 新设计

### 文件结构

```
models/
  base.py              ← 新增 BasePredictor + compute_scores
  factory.py           ← 新增 create_predictor 工厂
  lstm/
    predictor.py       ← 新增 LSTMPredictor
  xgboost/
    predictor.py       ← 新增 XGBoostPredictor
execution/
  predictor.py         ← 删除
  pipeline.py          ← 修改 import
```

### BasePredictor (models/base.py)

```python
class BasePredictor(ABC):
    def __init__(self, config, classifier, data_loader):
        self.config = config
        self.classifier = classifier
        self.data_loader = data_loader

    @abstractmethod
    async def predict(self, ts_code: str, target_names: List[str], current_date: str) -> Optional[Dict]:
        """内部构造 DataFrame，预测单只股票的 label_xxd 概率。
        
        Returns: {target_name: [p_down, p_flat, p_up]} 或 None
        """


def compute_scores(probs: Dict, close: float) -> Dict:
    """计算分数（与模型类型无关）。"""
    up_3d = probs.get("label_3d", [0, 0, 0])[2]
    up_5d = probs.get("label_5d", [0, 0, 0])[2]
    down_3d = probs.get("label_3d", [0, 0, 0])[0]
    down_5d = probs.get("label_5d", [0, 0, 0])[0]
    score = (up_3d - down_3d) * 0.4 + (up_5d - down_5d) * 0.6
    return {
        "up_prob_3d": up_3d, "up_prob_5d": up_5d,
        "down_prob_3d": down_3d, "down_prob_5d": down_5d,
        "score": score, "close": close,
    }
```

### XGBoostPredictor (models/xgboost/predictor.py)

```python
from trade_alpha.models.base import BasePredictor

class XGBoostPredictor(BasePredictor):
    async def predict(self, ts_code, target_names, current_date):
        from trade_alpha.models.xgboost.normalizer import normalize
        df = await self.data_loader.load_day_data(current_date, [ts_code])
        if df.empty:
            return None
        stock = df[df["ts_code"] == ts_code]
        if stock.empty:
            return None
        norm = normalize(stock, self.config.feature_fields,
                         self.config.standardize_fields, self.config.winsorize_fields)
        features = norm[self.config.feature_fields].iloc[-1:].values
        if np.isnan(features).any():
            return None
        return self.classifier.predict_proba(features, target_names)
```

### LSTMPredictor (models/lstm/predictor.py)

```python
from trade_alpha.models.base import BasePredictor

class LSTMPredictor(BasePredictor):
    async def predict(self, ts_code, target_names, current_date):
        seq_len = self.config.lstm_sequence_length
        df = await self.data_loader.load_history_data(current_date, [ts_code], seq_len + 10)
        if df.empty:
            return None
        stock = df[df["ts_code"] == ts_code].sort_values("trade_date")
        if len(stock) < seq_len:
            return None
        features = stock[self.config.feature_fields].values[-seq_len:]
        if np.isnan(features).any():
            return None
        return self.classifier.predict_proba(features, target_names)
```

### create_predictor 工厂 (models/factory.py)

```python
async def create_predictor(training_id, data_loader=None):
    training = await get_training_by_id(training_id)
    config = await get_config_by_id(training.config_id)

    if config.model_type == "xgboost":
        from trade_alpha.models.xgboost.classifier import XGBoostClassifier
        from trade_alpha.models.xgboost.predictor import XGBoostPredictor
        classifier = XGBoostClassifier(config)
        predictor_class = XGBoostPredictor
    elif config.model_type == "lstm":
        from trade_alpha.models.lstm.classifier import LSTMClassifier
        from trade_alpha.models.lstm.predictor import LSTMPredictor
        classifier = LSTMClassifier(config)
        predictor_class = LSTMPredictor
    else:
        raise ValueError(f"Unknown model type: {config.model_type}")

    classifier.load(training.model_path)
    return predictor_class(config, classifier, data_loader)
```

### Pipeline 调用示例

```python
from trade_alpha.models.factory import create_predictor
from trade_alpha.models.base import compute_scores

# 在 Pipeline.__init__ 中
self.predictor = None  # 延迟初始化

# 在 run_backtest / run_live 中
if self.predictor is None:
    self.predictor = await create_predictor(training_id, data_loader=self.data_loader)

# 预测
pred_result = {}
for ts_code in ts_codes:
    probs = await self.predictor.predict(ts_code, target_names, date)
    if probs is None:
        continue
    pred_result[ts_code] = compute_scores(probs, close_prices.get(ts_code, 0))
```

## 文件变更

| 文件 | 变更 |
|------|------|
| `models/base.py` | **追加** BasePredictor + compute_scores |
| `models/factory.py` | **新建** create_predictor |
| `models/lstm/predictor.py` | **新建** LSTMPredictor |
| `models/xgboost/predictor.py` | **新建** XGBoostPredictor |
| `execution/predictor.py` | **删除** |
| `execution/pipeline.py` | 修改 import |

## 测试

- 测试 XGBoostPredictor.predict 返回正确的概率字典
- 测试 LSTMPredictor.predict 返回正确的概率字典
- 测试 compute_scores 返回正确的分数格式
- 数据不足时返回 None
