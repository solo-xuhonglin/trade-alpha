# LSTM 滚动窗口标准化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标:** 将 LSTM 从 per-window Z-score 标准化改为滚动窗口标准化（250天 lookback），保留趋势方向信息，同时添加 close/vol 特征。

**架构:** 重写 `normalizer.py:create_sequences` 返回 norm_params，`classifier.py` 保存并在 predict 时使用，`predictor.py` 传递 ts_code。

**Tech Stack:** Python, NumPy, PyTorch

---

### Task 1: 重写 normalizer.py

**Files:**
- Modify: `backend/src/trade_alpha/models/lstm/normalizer.py` (全量重写)
- Test: `backend/tests/trade_alpha/unit/predict/test_lstm.py`

- [ ] **Step 1: 重写 create_sequences**

替换整个文件内容：

```python
"""LSTM sequence normalizer with rolling window Z-score normalization."""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any

LOOKBACK_DAYS = 250


def create_sequences(
    df: pd.DataFrame,
    feature_fields: List[str],
    target_names: List[str],
    sequence_length: int,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Dict[str, np.ndarray]]]:
    """Create overlapping sequences with rolling window Z-score normalization.

    For each stock: sort by date, for each sequence ending at day T,
    compute mean/std from [T - LOOKBACK_DAYS, T-1], normalize the sequence.

    Returns (X_3d, y_2d, norm_params).
    norm_params: {ts_code: {"means": ndarray, "stds": ndarray}}
    """
    X_list, y_list = [], []
    all_norm_params: Dict[str, Dict[str, np.ndarray]] = {}

    for _, group in df.groupby("ts_code"):
        group = group.sort_values("trade_date")
        values = group[feature_fields].values.astype(np.float64)
        labels = group[target_names].values.astype(np.float64)
        if len(values) < sequence_length + 1:
            continue

        ts_code = group.iloc[0]["ts_code"]

        for i in range(len(values) - sequence_length):
            seq_end = i + sequence_length
            seq = values[i:seq_end].copy()
            label = labels[seq_end - 1]
            if np.isnan(seq).any() or np.isnan(label).any():
                continue

            lookback_start = max(0, seq_end - LOOKBACK_DAYS - sequence_length)
            lookback_data = values[lookback_start:seq_end]
            seq_mean = lookback_data.mean(axis=0)
            seq_std = lookback_data.std(axis=0)
            seq_std[seq_std == 0] = 1.0
            seq = (seq - seq_mean) / seq_std
            X_list.append(seq)
            y_list.append(label)

        stock_data = values[:len(values)]
        overall_mean = stock_data.mean(axis=0)
        overall_std = stock_data.std(axis=0)
        overall_std[overall_std == 0] = 1.0
        all_norm_params[ts_code] = {
            "means": overall_mean.astype(np.float64),
            "stds": overall_std.astype(np.float64),
        }

    if not X_list:
        empty_params = {k: {"means": v["means"].reshape(-1), "stds": v["stds"].reshape(-1)}
                        for k, v in all_norm_params.items()} if all_norm_params else {}
        return np.empty((0, sequence_length, len(feature_fields))), \
               np.empty((0, len(target_names))), empty_params
    return np.array(X_list), np.array(y_list), all_norm_params
```

- [ ] **Step 2: 运行现有测试验证不破坏**

Run: `cd backend && python -m pytest tests/trade_alpha/unit/predict/test_lstm.py -v`
Expected: `FAILED` (因为 create_sequences 签名变了，classifier.py 还没改)

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/models/lstm/normalizer.py
git commit -m "feat: rewrite create_sequences with rolling window normalization (250d lookback)"
```

---

### Task 2: 修改 classifier.py - train 方法适配新 normalizer

**Files:**
- Modify: `backend/src/trade_alpha/models/lstm/classifier.py:75`

- [ ] **Step 1: 修改 train 方法中调用 create_sequences 的行**

原代码第75行：
```python
X_3d, y_2d = create_sequences(combined_df, config.feature_fields, target_names, seq_len)
```

改为：
```python
X_3d, y_2d, norm_params = create_sequences(combined_df, config.feature_fields, target_names, seq_len)
```

并在 `train` 方法中（紧接上面行之后）添加：
```python
self._norm_params = norm_params
```

- [ ] **Step 2: 运行测试验证不变坏**

Run: `cd backend && python -m pytest tests/trade_alpha/unit/predict/test_lstm.py -v`
Expected: 仍然 FAILED（predict 方法还没改）

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/models/lstm/classifier.py
git commit -m "feat: adapt training to new create_sequences signature"
```

---

### Task 3: 修改 classifier.py - predict/predict_proba 支持 ts_code

**Files:**
- Modify: `backend/src/trade_alpha/models/lstm/classifier.py:264-306`
- Modify: `backend/tests/trade_alpha/unit/predict/test_lstm.py`
- Test: `backend/tests/trade_alpha/unit/predict/test_lstm.py`

- [ ] **Step 1: 修改 `predict` 方法**

```python
def predict(self, features, target_names, ts_code):
    seq = np.array(features, dtype=np.float64)
    if len(seq) < self.sequence_length:
        return {}
    seq = seq[-self.sequence_length:]
    norm = self._norm_params.get(ts_code)
    if norm is None:
        return {}
    seq = (seq - norm["means"]) / norm["stds"]
    seq = np.nan_to_num(seq, nan=0.0, posinf=0.0, neginf=0.0)
    X_tensor = torch.FloatTensor(seq).unsqueeze(0)
    result = {}
    for target in target_names:
        if target not in self.models:
            continue
        self.models[target].eval()
        with torch.no_grad():
            logits = self.models[target](X_tensor)
            pred_idx = logits.argmax(dim=1)[0].item()
            result[target] = self._label_mapping[target][pred_idx]
    return result
```

- [ ] **Step 2: 修改 `predict_proba` 方法**

```python
def predict_proba(self, features, target_names, ts_code):
    seq = np.array(features, dtype=np.float64)
    if len(seq) < self.sequence_length:
        return {t: [0.0, 0.0, 0.0] for t in target_names}
    seq = seq[-self.sequence_length:]
    norm = self._norm_params.get(ts_code)
    if norm is None:
        return {t: [0.0, 0.0, 0.0] for t in target_names}
    seq = (seq - norm["means"]) / norm["stds"]
    seq = np.nan_to_num(seq, nan=0.0, posinf=0.0, neginf=0.0)
    X_tensor = torch.FloatTensor(seq).unsqueeze(0)
    result = {}
    for target in target_names:
        if target not in self.models:
            continue
        self.models[target].eval()
        with torch.no_grad():
            logits = self.models[target](X_tensor)
            proba_mapped = torch.softmax(logits / TEMPERATURE, dim=1)[0].numpy()
            label_map = self._label_mapping[target]
            proba = [0.0, 0.0, 0.0]
            for j, label in label_map.items():
                proba[label + 1] = proba_mapped[j]
            result[target] = proba
    return result
```

- [ ] **Step 3: 更新测试文件适配新的接口**

在 `_train_minimal_lstm` 函数末尾添加 norm_params 初始化：

```python
def _train_minimal_lstm(clf):
    seq_len = 5
    n_features = 5
    clf.input_size = n_features
    X = np.random.randn(30, n_features)
    for target in ["label_3d", "label_5d"]:
        label_map = {0: -1, 1: 0, 2: 1}
        reverse_map = {-1: 0, 0: 1, 1: 2}
        y = np.random.choice([-1, 0, 1], size=30)
        y_mapped = np.array([reverse_map[v] for v in y])
        model = LSTMModel(n_features, clf.config.lstm_hidden_size, clf.config.lstm_num_layers, 3)
        model.eval()
        clf.models[target] = model
        clf._label_mapping[target] = label_map
    clf._norm_params = {
        "000001.SZ": {"means": np.zeros(n_features), "stds": np.ones(n_features)}
    }
```

测试函数中 predict 调用增加 ts_code：

```python
def test_lstm_classifier_fit_predict():
    config = MockConfig()
    clf = LSTMClassifier(config)
    _train_minimal_lstm(clf)

    X = np.random.randn(10, 5)
    preds = clf.predict(X, ["label_3d", "label_5d"], ts_code="000001.SZ")
    assert "label_3d" in preds
    assert preds["label_3d"] in [-1, 0, 1]


def test_lstm_classifier_save_load(tmp_path):
    config = MockConfig()
    clf = LSTMClassifier(config)
    _train_minimal_lstm(clf)

    X = np.random.randn(10, 5)
    preds = clf.predict(X, ["label_3d"], ts_code="000001.SZ")

    path = tmp_path / "model.pt"
    clf.save(str(path))
    clf2 = LSTMClassifier(config)
    clf2.load(str(path))

    preds2 = clf2.predict(X, ["label_3d"], ts_code="000001.SZ")
    assert preds == preds2
```

- [ ] **Step 4: 运行测试验证**

Run: `cd backend && python -m pytest tests/trade_alpha/unit/predict/test_lstm.py -v`
Expected: PASSED

- [ ] **Step 5: 提交**

```bash
git add backend/src/trade_alpha/models/lstm/classifier.py backend/tests/trade_alpha/unit/predict/test_lstm.py
git commit -m "feat: add ts_code support to predict/predict_proba for rolling normalization"
```

---

### Task 4: 修改 classifier.py - save/load 支持 norm_params

**Files:**
- Modify: `backend/src/trade_alpha/models/lstm/classifier.py:308-328`
- Test: `backend/tests/trade_alpha/unit/predict/test_lstm.py`

- [ ] **Step 1: 修改 `save` 方法**

```python
def save(self, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    torch.save({
        "models": {k: v.state_dict() for k, v in self.models.items()},
        "label_mapping": self._label_mapping,
        "input_size": self.input_size,
        "sequence_length": self.sequence_length,
        "norm_params": self._norm_params,
    }, path)
```

- [ ] **Step 2: 修改 `load` 方法**

在 `load` 方法中 `self.sequence_length = state["sequence_length"]` 之后添加：
```python
self._norm_params = state.get("norm_params", {})
```

- [ ] **Step 3: 运行测试验证 save/load**

Run: `cd backend && python -m pytest tests/trade_alpha/unit/predict/test_lstm.py::test_lstm_classifier_save_load -v`
Expected: PASSED

- [ ] **Step 4: 提交**

```bash
git add backend/src/trade_alpha/models/lstm/classifier.py
git commit -m "feat: persist and restore norm_params in save/load"
```

---

### Task 5: 修改 predictor.py 传递 ts_code

**Files:**
- Modify: `backend/src/trade_alpha/execution/predictor.py:80-95` (`_predict_and_add`)
- Modify: `backend/src/trade_alpha/execution/predictor.py:113-140` (`_predict_single`)

- [ ] **Step 1: 修改 `_predict_and_add` 方法（第80-95行）**

```python
def _predict_and_add(self, result, ts_code, day_df, features, target_names):
    if self._config.model_type == "lstm":
        predictions = self._classifier.predict(features, target_names, ts_code=ts_code)
        probabilities = self._classifier.predict_proba(features, target_names, ts_code=ts_code)
    else:
        predictions = self._classifier.predict(features, target_names)
        probabilities = self._classifier.predict_proba(features, target_names)
    if not predictions:
        return
    up_prob_3d = probabilities.get("label_3d", [0, 0, 0])[2] if isinstance(probabilities.get("label_3d"), list) and len(probabilities["label_3d"]) == 3 else 0
    up_prob_5d = probabilities.get("label_5d", [0, 0, 0])[2] if isinstance(probabilities.get("label_5d"), list) and len(probabilities["label_5d"]) == 3 else 0
    down_prob_3d = probabilities.get("label_3d", [0, 0, 0])[0] if isinstance(probabilities.get("label_3d"), list) and len(probabilities["label_3d"]) == 3 else 0
    down_prob_5d = probabilities.get("label_5d", [0, 0, 0])[0] if isinstance(probabilities.get("label_5d"), list) and len(probabilities["label_5d"]) == 3 else 0
    score = (up_prob_3d - down_prob_3d) * 0.4 + (up_prob_5d - down_prob_5d) * 0.6
    day_row = day_df[day_df["ts_code"] == ts_code]
    result[ts_code] = {
        "up_prob_3d": up_prob_3d, "up_prob_5d": up_prob_5d,
        "down_prob_3d": down_prob_3d, "down_prob_5d": down_prob_5d,
        "score": score, "close": float(day_row.iloc[0]["close"]) if not day_row.empty else 0,
    }
```

- [ ] **Step 2: 修改 `_predict_single` 方法（第121-122行）- LSTM 路径传 ts_code**

第113-127行目前：
```python
async def _predict_single(self, df, ts_code):
    target_names = [f"label_{h}d" for h in self._training.classification_horizons]

    if self._config.model_type == "xgboost":
        from trade_alpha.models.xgboost.normalizer import normalize as xgb_normalize
        df_norm = xgb_normalize(df, self._config.feature_fields, self._config.standardize_fields, self._config.winsorize_fields)
        features = df_norm[self._config.feature_fields].iloc[-1:].values
    elif self._config.model_type == "lstm":
        features = df[self._config.feature_fields].values[-self._config.lstm_sequence_length:]
    else:
        raise ValueError(f"Unknown model type: {self._config.model_type}")

    predictions = self._classifier.predict(features, target_names)
    probabilities = self._classifier.predict_proba(features, target_names)
```

只需将最后两行改为按 model_type 分支传参：
```python
    if self._config.model_type == "lstm":
        predictions = self._classifier.predict(features, target_names, ts_code=ts_code)
        probabilities = self._classifier.predict_proba(features, target_names, ts_code=ts_code)
    else:
        predictions = self._classifier.predict(features, target_names)
        probabilities = self._classifier.predict_proba(features, target_names)
```

- [ ] **Step 3: 运行测试验证**

Run: `cd backend && python -m pytest tests/trade_alpha/unit/predict/test_lstm.py -v`
Expected: PASSED

- [ ] **Step 4: 提交**

```bash
git add backend/src/trade_alpha/execution/predictor.py
git commit -m "feat: pass ts_code to LSTM predict methods for per-stock normalization"
```

---

### Task 6: 修改 config.py 添加 close/vol 特征

**Files:**
- Modify: `backend/src/trade_alpha/models/training/config.py:20-35`

- [ ] **Step 1: 在 DEFAULT_INDICATOR_FIELDS 开头添加 close, vol**

```python
DEFAULT_INDICATOR_FIELDS = [
    "close", "vol",
    "ma_5", "ma_10", "ma_20", "ma_60",
    "macd", "macd_signal", "macd_hist",
    "pct_chg",
    ...
]
```

- [ ] **Step 2: 运行 import 测试**

Run: `cd backend && python -c "from trade_alpha.models.training.config import DEFAULT_INDICATOR_FIELDS; print(len(DEFAULT_INDICATOR_FIELDS))"`
Expected: 输出特征数量（比原来多2个）

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/models/training/config.py
git commit -m "feat: add close and vol to default feature fields"
```

---

### Task 7: 全量测试验证

**Files:**
- Test: `backend/tests/trade_alpha/unit/predict/test_lstm.py`

- [ ] **Step 1: 运行所有 LSTM 测试**

Run: `cd backend && python -m pytest tests/trade_alpha/unit/predict/test_lstm.py -v`
Expected: 2 PASSED

- [ ] **Step 2: 推送到远程**

```bash
git push
```
