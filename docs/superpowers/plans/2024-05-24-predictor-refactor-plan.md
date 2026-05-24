# Predictor 分层重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标:** 将 Predictor 从单类 + if-else 重构为 BasePredictor + XGBoostPredictor + LSTMPredictor 分层结构，消除模型类型分支。

**架构:** BasePredictor 只定义 `async predict(ts_code, target_names, current_date)` 抽象方法，内部自己通过 data_loader 加载数据、提取特征、调用 classifier.predict_proba。分数计算抽取为独立函数 `compute_scores`，循环多股票上移到 Pipeline。

**Tech Stack:** Python, asyncio, NumPy, pandas

---

## 文件结构

| 文件 | 变更 |
|------|------|
| `models/base.py` | **追加** BasePredictor + compute_scores |
| `models/factory.py` | **新建** create_predictor |
| `models/lstm/predictor.py` | **新建** LSTMPredictor |
| `models/xgboost/predictor.py` | **新建** XGBoostPredictor |
| `execution/predictor.py` | **删除** |
| `execution/pipeline.py` | 修改 import |
| `tests/trade_alpha/unit/models/test_predictor.py` | 新增 |

---

### Task 1: 追加 BasePredictor + compute_scores 到 models/base.py

**Files:**
- Modify: `backend/src/trade_alpha/models/base.py`
- Create: `backend/src/trade_alpha/models/xgboost/predictor.py`
- Create: `backend/src/trade_alpha/models/lstm/predictor.py`
- Create: `backend/src/trade_alpha/models/factory.py`
- Delete: `backend/src/trade_alpha/execution/predictor.py`
- Create: `backend/tests/trade_alpha/unit/models/test_predictor.py`

- [ ] **Step 1: 在 models/base.py 末尾追加 BasePredictor 和 compute_scores**

追加到现有文件末尾：

```python
# ============================================================
# Predictor
# ============================================================


class BasePredictor(ABC):
    def __init__(self, config, classifier, data_loader):
        self.config = config
        self.classifier = classifier
        self.data_loader = data_loader

    @abstractmethod
    async def predict(self, ts_code: str, target_names: List[str], current_date: str) -> Optional[Dict]:
        pass


def compute_scores(probs: Dict, close: float) -> Dict:
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

需要补充 import：在文件顶部 `from typing import Dict` 改为 `from typing import Dict, List, Optional`。

- [ ] **Step 2: 新建 models/xgboost/predictor.py**

```python
"""XGBoostPredictor - loads day data and predicts."""
import numpy as np
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

- [ ] **Step 3: 新建 models/lstm/predictor.py**

```python
"""LSTMPredictor - loads history data and predicts."""
import numpy as np
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

- [ ] **Step 4: 新建 models/factory.py**

```python
"""Factory for creating Predictor instances."""
from trade_alpha.models.training.trainer import get_training_by_id
from trade_alpha.models.training.config import get_config_by_id


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

- [ ] **Step 5: 新建测试文件**

创建 `tests/trade_alpha/unit/models/test_predictor.py`:

```python
"""Tests for predictors and compute_scores."""
import pytest
import numpy as np
from trade_alpha.models.base import compute_scores


class FakeClassifier:
    def predict_proba(self, features, target_names):
        return {t: [0.2, 0.3, 0.5] for t in target_names}


class FakeDataLoader:
    async def load_day_data(self, date, ts_codes):
        import pandas as pd
        return pd.DataFrame({"ts_code": ts_codes, "close": [15.0]})

    async def load_history_data(self, end_date, ts_codes, days):
        import pandas as pd
        dates = [f"2024-01-{i+1:02d}" for i in range(days)]
        return pd.DataFrame({
            "ts_code": ts_codes * days,
            "trade_date": dates * len(ts_codes),
            "close": list(range(10, 10 + days)) * len(ts_codes),
            "ma_5": [11.0] * days * len(ts_codes),
        })


class FakeConfig:
    model_type = "lstm"
    feature_fields = ["close", "ma_5"]
    standardize_fields = ["close", "ma_5"]
    winsorize_fields = []
    lstm_sequence_length = 5
    classification_horizons = [3, 5]


def test_compute_scores():
    probs = {"label_3d": [0.1, 0.2, 0.7], "label_5d": [0.2, 0.3, 0.5]}
    result = compute_scores(probs, 15.0)
    assert abs(result["up_prob_3d"] - 0.7) < 1e-6
    assert abs(result["up_prob_5d"] - 0.5) < 1e-6
    assert abs(result["down_prob_3d"] - 0.1) < 1e-6
    assert abs(result["down_prob_5d"] - 0.2) < 1e-6
    expected_score = (0.7 - 0.1) * 0.4 + (0.5 - 0.2) * 0.6
    assert abs(result["score"] - expected_score) < 1e-6
    assert result["close"] == 15.0


def test_compute_scores_empty():
    result = compute_scores({}, 0.0)
    assert result["score"] == 0.0
    assert result["close"] == 0.0


@pytest.mark.asyncio
async def test_xgboost_predictor_predict():
    from trade_alpha.models.xgboost.predictor import XGBoostPredictor
    config = FakeConfig()
    config.model_type = "xgboost"
    pred = XGBoostPredictor(config, FakeClassifier(), FakeDataLoader())
    result = await pred.predict("000001.SZ", ["label_3d", "label_5d"], "20240110")
    assert result is not None
    assert "label_3d" in result
    assert len(result["label_3d"]) == 3


@pytest.mark.asyncio
async def test_lstm_predictor_predict():
    from trade_alpha.models.lstm.predictor import LSTMPredictor
    config = FakeConfig()
    config.lstm_sequence_length = 3
    pred = LSTMPredictor(config, FakeClassifier(), FakeDataLoader())
    result = await pred.predict("000001.SZ", ["label_3d", "label_5d"], "20240110")
    assert result is not None
    assert "label_3d" in result
    assert len(result["label_3d"]) == 3
```

- [ ] **Step 6: 运行新测试**

Run: `cd backend && python -m pytest tests/trade_alpha/unit/models/test_predictor.py -v`
Expected: PASSED

- [ ] **Step 7: 删除旧文件并提交**

```bash
git rm backend/src/trade_alpha/execution/predictor.py
git add backend/src/trade_alpha/models/base.py
git add backend/src/trade_alpha/models/factory.py
git add backend/src/trade_alpha/models/lstm/predictor.py
git add backend/src/trade_alpha/models/xgboost/predictor.py
git add backend/tests/trade_alpha/unit/models/test_predictor.py
git commit -m "refactor: split Predictor into BasePredictor + XGBoostPredictor + LSTMPredictor"
```

---

### Task 2: 修改 pipeline.py

**Files:**
- Modify: `backend/src/trade_alpha/execution/pipeline.py`

- [ ] **Step 1: 修改 import 和 __init__**

```python
# 移除旧的 import
# from trade_alpha.execution.predictor import Predictor
# 改为
from trade_alpha.models.factory import create_predictor
from trade_alpha.models.base import compute_scores

# 在 __init__ 中 (第61行附近)
# 旧: self.predictor = Predictor(training_id, normalizer=None, data_loader=self.data_loader)
# 改为:
self.predictor = None  # 延迟初始化
```

- [ ] **Step 2: 在 run_backtest 和 run_live 中添加延迟初始化**

在 `run_backtest` 中（第126行任务进度更新后）和 `run_live` 中（第399行开始处）添加：
```python
if self.predictor is None:
    self.predictor = await create_predictor(self.training_id, data_loader=self.data_loader)
```

- [ ] **Step 3: 修改 run_backtest 中的预测调用（L284-291）**

旧代码：
```python
pred_results = await self.predictor.predict_batch_with_history(
    day_df, ts_codes, date
)
```

改为：
```python
target_names = [f"label_{h}d" for h in self._config.classification_horizons]
pred_results = {}
for ts_code in ts_codes:
    probs = await self.predictor.predict(ts_code, target_names, date)
    if probs is None:
        continue
    close_price = close_prices.get(ts_code, 0)
    pred_results[ts_code] = compute_scores(probs, close_price)
```

- [ ] **Step 4: 修改 run_live 中的预测调用（L417）**

旧代码：
```python
pred_results = await self.predictor.predict_batch(day_df, ts_codes)
```

改为：
```python
target_names = [f"label_{h}d" for h in self._config.classification_horizons]
pred_results = {}
for ts_code in ts_codes:
    probs = await self.predictor.predict(ts_code, target_names, date)
    if probs is None:
        continue
    close_price = close_prices.get(ts_code, 0)
    pred_results[ts_code] = compute_scores(probs, close_price)
```

- [ ] **Step 5: 运行测试验证**

Run: `cd backend && python -m pytest tests/trade_alpha/unit/models/test_predictor.py tests/trade_alpha/unit/predict/ -v`
Expected: 全部 PASSED

Run: `cd backend && python -m pytest tests/ -v -x --timeout=120`
Expected: PASSED

- [ ] **Step 6: 提交**

```bash
git add backend/src/trade_alpha/execution/pipeline.py
git commit -m "refactor: update Pipeline to use new Predictor interface"
```

---

### Task 3: 全量测试 + 推送

**Files:**
- Test: 全部单元测试

- [ ] **Step 1: 运行所有单元测试**

Run: `cd backend && python -m pytest tests/ -v --timeout=120`
Expected: PASSED

- [ ] **Step 2: 推送**

```bash
git push
```
