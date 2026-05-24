# Predictor 分层重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标:** 将 Predictor 从单类 + if-else 重构为 BasePredictor + XGBoostPredictor + LSTMPredictor 分层结构，消除模型类型分支。

**架构:** BasePredictor 只定义 `async predict(ts_code, target_names, current_date)` 抽象方法，内部自己通过 data_loader 加载数据、提取特征、调用 classifier.predict_proba。分数计算抽取为独立函数 `compute_scores`，循环多股票上移到 Pipeline。

**Tech Stack:** Python, asyncio, NumPy, pandas

---

## 文件结构

| 文件 | 变更 |
|------|------|
| `models/predictor.py` | **新建** |
| `execution/predictor.py` | **删除** |
| `execution/pipeline.py` | import 改为从 `models.predictor` |
| `tests/trade_alpha/unit/models/test_predictor.py` | 新增 |

---

### Task 1: 新建 models/predictor.py

**Files:**
- Create: `backend/src/trade_alpha/models/predictor.py`
- Delete: `backend/src/trade_alpha/execution/predictor.py`
- Create: `backend/tests/trade_alpha/unit/models/test_predictor.py`

- [ ] **Step 1: 重写 predictor.py**

完整替换内容为 BasePredictor、XGBoostPredictor、LSTMPredictor、compute_scores、create_predictor：

```python
"""Predictor - model-specific prediction logic."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import numpy as np
from beanie import PydanticObjectId
from trade_alpha.models.training.trainer import get_training_by_id
from trade_alpha.models.training.config import get_config_by_id
from trade_alpha.logging import get_logger

logger = get_logger("execution.predictor")


def compute_scores(probs: Dict, close: float) -> Dict:
    """从概率字典计算交易分数。"""
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


class BasePredictor(ABC):
    def __init__(self, config, classifier, data_loader):
        self.config = config
        self.classifier = classifier
        self.data_loader = data_loader

    @abstractmethod
    async def predict(self, ts_code: str, target_names: List[str], current_date: str) -> Optional[Dict]:
        """内部构造 DataFrame，预测单只股票的概率字典。
        
        Returns {target_name: [p_down, p_flat, p_up]} or None.
        """


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


async def create_predictor(training_id: PydanticObjectId, data_loader=None):
    """创建对应模型类型的 Predictor 实例。"""
    training = await get_training_by_id(training_id)
    config = await get_config_by_id(training.config_id)

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

- [ ] **Step 2: 写测试文件**

创建 `test_predictor.py`:

```python
"""Tests for predictors and compute_scores."""
import pytest
import numpy as np
from trade_alpha.models.predictor import compute_scores


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
    from trade_alpha.models.predictor import XGBoostPredictor
    config = FakeConfig()
    config.model_type = "xgboost"
    pred = XGBoostPredictor(config, FakeClassifier(), FakeDataLoader())
    result = await pred.predict("000001.SZ", ["label_3d", "label_5d"], "20240110")
    assert result is not None
    assert "label_3d" in result
    assert len(result["label_3d"]) == 3


@pytest.mark.asyncio
async def test_lstm_predictor_predict():
    from trade_alpha.models.predictor import LSTMPredictor
    config = FakeConfig()
    config.lstm_sequence_length = 3
    pred = LSTMPredictor(config, FakeClassifier(), FakeDataLoader())
    result = await pred.predict("000001.SZ", ["label_3d", "label_5d"], "20240110")
    assert result is not None
    assert "label_3d" in result
    assert len(result["label_3d"]) == 3
```

- [ ] **Step 3: 运行测试验证新测试通过**

Run: `cd backend && python -m pytest tests/trade_alpha/unit/models/test_predictor.py -v`
Expected: compute_scores 测试通过，predictor 测试因缺少 data_loader 等依赖可能 FAIL

实际上应该全部通过，因为新文件只依赖已存在的模块。运行验证。

- [ ] **Step 4: 删除旧文件并提交**

```bash
git rm backend/src/trade_alpha/execution/predictor.py
git add backend/src/trade_alpha/models/predictor.py backend/tests/trade_alpha/unit/models/test_predictor.py
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
from trade_alpha.models.predictor import create_predictor, compute_scores

# 在 __init__ 中 (第61行附近)
# 旧: self.predictor = Predictor(training_id, normalizer=None, data_loader=self.data_loader)
# 改为:
self.predictor = await create_predictor(training_id, data_loader=self.data_loader)
```

注意：`__init__` 是同步的，但 `create_predictor` 是 async 的。需要把 predictor 创建移到第一个 async 方法（如 `run_backtest`）中，或改为延迟初始化。

**方案：添加 `_ensure_predictor` 辅助方法，延迟初始化**

修改第61行：
```python
self.predictor = None  # 延迟初始化
```

在 `run_backtest` 中（第126行任务进度更新后）和 `run_live` 中（第399行开始处）添加：
```python
if self.predictor is None:
    self.predictor = await create_predictor(self.training_id, data_loader=self.data_loader)
```

- [ ] **Step 2: 修改 run_backtest 中的预测调用（L284-291）**

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

- [ ] **Step 3: 修改 run_live 中的预测调用（L417）**

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

- [ ] **Step 4: 运行测试验证**

Run: `cd backend && python -m pytest tests/trade_alpha/unit/models/test_predictor.py tests/trade_alpha/unit/predict/ -v`
Expected: 全部 PASSED

Run: `cd backend && python -m pytest tests/ -v -x --timeout=60`
Expected: PASSED

- [ ] **Step 5: 提交**

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
