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

### BasePredictor

只有一个抽象方法，入参只有 ts_code 和 date，内部自己加载数据：

```python
class BasePredictor(ABC):
    def __init__(self, config, classifier, data_loader):
        self.config = config
        self.classifier = classifier
        self.data_loader = data_loader

    @abstractmethod
    async def predict(self, ts_code: str, target_names: List[str], current_date: str) -> Optional[Dict]:
        """内部构造 DataFrame，预测单只股票的 label_xxd 概率。
        
        Args:
            ts_code: 目标股票代码
            target_names: 预测目标名列表，如 ["label_3d", "label_5d"]
            current_date: 当前交易日，格式 YYYYMMDD
            
        Returns:
            {target_name: [p_down, p_flat, p_up]} 或 None（数据不足时）
        """
```

### XGBoostPredictor

```python
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

### LSTMPredictor

```python
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

### 移除部分

从 Predictor 移除的职责：

| 职责 | 去哪了 | 原因 |
|------|--------|------|
| 数据加载 | 各 Predictor 实现类内部调用 data_loader | 每种模型需要的数据量和方式不同 |
| 分数计算 | 抽取为独立函数 `compute_scores(probs, close)` | 与模型类型无关，所有模型统一 |
| 循环多只股票 | Pipeline 自己 for 循环 | 简单循环不需要封装 |
| 模型加载 + 工厂 | 放在 create_predictor 工厂函数 | 统一一处决定 |

### Pipeline 调用示例

```python
# 在 Pipeline.__init__ 中
self.predictor = None  # 延迟初始化

# 在 run_backtest / run_live 中
if self.predictor is None:
    from trade_alpha.models.predictor import create_predictor
    self.predictor = await create_predictor(training_id, data_loader=self.data_loader)

# 预测
from trade_alpha.models.predictor import compute_scores
pred_result = {}
for ts_code in ts_codes:
    probs = await self.predictor.predict(ts_code, target_names, date)
    if probs is None:
        continue
    pred_result[ts_code] = compute_scores(probs, close_prices.get(ts_code, 0))
```

### compute_scores

```python
def compute_scores(probs: Dict, close: float) -> Dict:
    up_3d = probs.get("label_3d", [0,0,0])[2]
    up_5d = probs.get("label_5d", [0,0,0])[2]
    down_3d = probs.get("label_3d", [0,0,0])[0]
    down_5d = probs.get("label_5d", [0,0,0])[0]
    score = (up_3d - down_3d) * 0.4 + (up_5d - down_5d) * 0.6
    return {
        "up_prob_3d": up_3d, "up_prob_5d": up_5d,
        "down_prob_3d": down_3d, "down_prob_5d": down_5d,
        "score": score, "close": close,
    }
```

## 文件变更

| 文件 | 变更 |
|------|------|
| `models/predictor.py` | **新建**：BasePredictor、XGBoostPredictor、LSTMPredictor、create_predictor 工厂、compute_scores 函数 |
| `execution/predictor.py` | **删除** |
| `execution/pipeline.py` | import 改为 `from trade_alpha.models.predictor import ...` |

## 测试

- 测试 XGBoostPredictor.predict 返回正确的概率字典
- 测试 LSTMPredictor.predict 返回正确的概率字典
- 测试 compute_scores 返回正确的分数格式
- 数据不足时返回 None
