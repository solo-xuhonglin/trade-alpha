# LSTM Normalization Window Separation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate LSTM normalization window from sequence length — use 300-day mean/std to normalize last 60 days of each sliding window.

**Architecture:** Add `lstm_normalization_window` to ModelConfig (default 300). `create_sequences` uses it as the sliding window size for computing mean/std, only normalizes last `sequence_length` rows. `_load_year_data` uses `extra_days` as actual calendar days instead of a boolean. `predict_proba` stops doing internal normalization. `LSTMPredictor` loads more history data and normalizes using the larger window.

**Tech Stack:** Python, NumPy, PyTorch, Pydantic, MongoDB/Beanie

---

### Task 1: Add `lstm_normalization_window` to ModelConfig

**Files:**
- Modify: `backend/src/trade_alpha/dao/model_config.py:72`

- [ ] **Step 1: Add field to ModelConfig document**

Replace line 72 (the `lstm_sequence_length` line) to add `lstm_normalization_window` right after it:

```python
    lstm_sequence_length: int = 60  # 序列长度（用于模型输入）
    lstm_normalization_window: int = 300  # 标准化统计量计算窗口
    label_smoothing: float = 0.1  # 标签平滑系数
```

Also clean up the stale `lstm_window_size` docstring — change line 46 from:
```
        lstm_window_size: lstm 滑动窗口标准化窗口大小
```
to:
```
        lstm_normalization_window: lstm 标准化统计量计算窗口（默认 300 天）
```

- [ ] **Step 2: Verify**

Run: `python -c "from trade_alpha.dao.model_config import ModelConfig; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/dao/model_config.py
git commit -m "feat: add lstm_normalization_window field to ModelConfig"
```

---

### Task 2: Add `lstm_normalization_window` to config service

**Files:**
- Modify: `backend/src/trade_alpha/models/training/config.py:58`

- [ ] **Step 1: Add parameter to `create_config` signature**

Add `lstm_normalization_window: int = 300` between `lstm_sequence_length` and `label_smoothing` parameters (line 58):

```python
    lstm_sequence_length: int = 60,
    lstm_normalization_window: int = 300,
    label_smoothing: float = 0.1,
```

- [ ] **Step 2: Pass it to ModelConfig constructor**

In the `config = ModelConfig(` block (~line 123), add after `lstm_sequence_length=lstm_sequence_length`:

```python
        lstm_normalization_window=lstm_normalization_window,
```

- [ ] **Step 3: Verify**

Run: `python -c "from trade_alpha.models.training.config import create_config; print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/models/training/config.py
git commit -m "feat: add lstm_normalization_window param to create_config"
```

---

### Task 3: Fix `_load_year_data` to use `extra_days` as calendar days

**Files:**
- Modify: `backend/src/trade_alpha/models/training/helpers.py:25-34`

- [ ] **Step 1: Check existing imports and add `datetime`/`timedelta`**

Add at top of file:

```python
from datetime import datetime, timedelta
```

- [ ] **Step 2: Rewrite `_load_year_data` date calculation**

Replace lines 25-34:

```python
async def _load_year_data(year: int, ts_codes: List[str], horizon: int, extra_days: int = 0) -> Optional[pd.DataFrame]:
    """Load yearly data including future horizon days.

    Args:
        extra_days: extra calendar buffer days for LSTM normalization window
    """
    year_start = f"{year}0101"
    year_end = f"{year}1231"
    future_end = f"{year + (horizon + 180) // 365}1231"
    data_start = (datetime(year, 1, 1) - timedelta(days=extra_days)).strftime("%Y%m%d") if extra_days > 0 else year_start
```

- [ ] **Step 3: Verify**

Run: `python -m pytest tests/trade_alpha/unit/predict/test_lstm.py -v`
Expected: 2 passed

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/models/training/helpers.py
git commit -m "feat: make _load_year_data extra_days use actual calendar days"
```

---

### Task 4: Update `create_sequences` to accept `normalization_window`

**Files:**
- Modify: `backend/src/trade_alpha/models/lstm/normalizer.py:8-44`
- Modify: `backend/tests/trade_alpha/unit/predict/normalizers/test_sliding_window.py`

- [ ] **Step 1: Write the failing test — add `normalization_window` test case**

Add to `test_sliding_window.py`:

```python
def test_create_sequences_with_normalization_window():
    """Verify normalization_window > sequence_length works."""
    n_stocks = 3
    n_dates = 50
    n_features = 3
    rows = []
    for stock_idx in range(n_stocks):
        ts_code = f"{stock_idx:06d}.SZ"
        for date_idx in range(n_dates):
            rows.append({
                "ts_code": ts_code,
                "trade_date": f"2024{(date_idx+1):03d}",
                "f1": np.random.randn(),
                "f2": np.random.randn(),
                "f3": np.random.randn(),
                "label_3d": np.random.choice([-1, 0, 1]),
                "label_5d": np.random.choice([-1, 0, 1]),
            })
    df = pd.DataFrame(rows)
    X, y = create_sequences(
        df, ["f1", "f2", "f3"], ["label_3d", "label_5d"],
        sequence_length=10, normalization_window=30,
    )
    assert X.shape[0] > 0  # at least one sample
    assert X.shape[1] == 10  # sequence_length
    assert X.shape[2] == 3  # n_features
    assert y.shape[0] == X.shape[0]
    assert y.shape[1] == 2
    assert not np.isnan(X).any()
    assert not np.isnan(y).any()
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `python -m pytest tests/trade_alpha/unit/predict/normalizers/test_sliding_window.py::test_create_sequences_with_normalization_window -v`
Expected: TypeError about unexpected `normalization_window` argument

- [ ] **Step 3: Rewrite `create_sequences` in normalizer.py**

```python
def create_sequences(
    df: pd.DataFrame,
    feature_fields: List[str],
    target_names: List[str],
    sequence_length: int,
    normalization_window: int = 60,  # default kept for backward compat
) -> Tuple[np.ndarray, np.ndarray]:
    X_list, y_list = [], []
    for _, group in df.groupby("ts_code"):
        group = group.sort_values("trade_date")
        values = group[feature_fields].values.astype(np.float64)
        labels = group[target_names].values.astype(np.float64)
        if len(values) < normalization_window:
            continue
        for i in range(normalization_window - 1, len(values)):
            window = values[i - normalization_window + 1 : i + 1].copy()
            label = labels[i]
            if np.isnan(window).any() or np.isnan(label).any():
                continue
            mean = window.mean(axis=0)
            std = window.std(axis=0)
            std[std == 0] = 1.0
            seq = (window[-sequence_length:] - mean) / std
            X_list.append(seq)
            y_list.append(label)
    if not X_list:
        return np.empty((0, sequence_length, len(feature_fields))), \
               np.empty((0, len(target_names)))
    return np.array(X_list), np.array(y_list)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/trade_alpha/unit/predict/normalizers/test_sliding_window.py -v`
Expected: 6 passed (5 existing + 1 new)

- [ ] **Step 5: Commit**

```bash
git add backend/src/trade_alpha/models/lstm/normalizer.py backend/tests/trade_alpha/unit/predict/normalizers/test_sliding_window.py
git commit -m "feat: add normalization_window param to create_sequences"
```

---

### Task 5: Update `LSTMClassifier` — training and `predict_proba`

**Files:**
- Modify: `backend/src/trade_alpha/models/lstm/classifier.py:40-75, 264-286`
- Modify: `backend/tests/trade_alpha/unit/predict/test_lstm.py:10-21`

- [ ] **Step 1: Add `lstm_normalization_window` to MockConfig in tests**

In `test_lstm.py`, add to MockConfig class:

```python
    lstm_normalization_window: int = 30  # for fast tests
```

- [ ] **Step 2: Adapt `train()` method — update extra_days and create_sequences call**

Find the lines in `train()`:

```python
        seq_len = self.sequence_length
        extra_days = seq_len + 10
```

Change to:

```python
        seq_len = self.sequence_length
        norm_window = config.lstm_normalization_window
        extra_days = int(norm_window * 1.5)
```

Find the `create_sequences` call:

```python
        X_3d, y_2d = create_sequences(combined_df, config.feature_fields, target_names, seq_len)
```

Change to:

```python
        X_3d, y_2d = create_sequences(
            combined_df, config.feature_fields, target_names,
            sequence_length=seq_len,
            normalization_window=norm_window,
        )
```

- [ ] **Step 3: Remove internal normalization from `predict_proba`**

Replace the entire `predict_proba` method:

```python
    def predict_proba(self, features, target_names):
        seq = np.array(features, dtype=np.float64)
        if len(seq) < self.sequence_length:
            return {t: [0.0, 0.0, 0.0] for t in target_names}
        seq = seq[-self.sequence_length:]
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

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/trade_alpha/unit/predict/test_lstm.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/src/trade_alpha/models/lstm/classifier.py backend/tests/trade_alpha/unit/predict/test_lstm.py
git commit -m "feat: update LSTMClassifier for normalization_window and remove predict_proba internal normalization"
```

---

### Task 6: Update `LSTMPredictor` to use normalization window

**Files:**
- Modify: `backend/src/trade_alpha/models/lstm/predictor.py:7-18`
- Modify: `backend/tests/trade_alpha/unit/models/test_predictor.py`

- [ ] **Step 1: Read the test file to find the LSTM MockConfig**

Read: `backend/tests/trade_alpha/unit/models/test_predictor.py`
Find the `FakeConfig` class and add `lstm_normalization_window` field.

- [ ] **Step 2: Rewrite `LSTMPredictor.predict`**

```python
class LSTMPredictor(BasePredictor):
    async def predict(self, ts_code, target_names, current_date):
        seq_len = self.config.lstm_sequence_length
        norm_win = self.config.lstm_normalization_window
        df = await self.data_loader.load_history_data(current_date, [ts_code], norm_win + seq_len)
        if df.empty:
            return None
        stock = df[df["ts_code"] == ts_code].sort_values("trade_date")
        if len(stock) < norm_win + seq_len:
            return None
        data = stock[self.config.feature_fields].values
        chunk = data[-(norm_win + seq_len):]
        norm_data = chunk[:-seq_len]
        feed = chunk[-seq_len:]
        mean = norm_data.mean(axis=0)
        std = norm_data.std(axis=0)
        std[std == 0] = 1.0
        features = (feed - mean) / std
        if np.isnan(features).any():
            return None
        return self.classifier.predict_proba(features, target_names)
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/trade_alpha/unit/models/test_predictor.py -v`
Expected: 4 passed

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/models/lstm/predictor.py backend/tests/trade_alpha/unit/models/test_predictor.py
git commit -m "feat: update LSTMPredictor to use normalization_window for data loading and normalization"
```

---

### Task 7: Verify full test suite

- [ ] **Step 1: Run all related tests**

Run: `python -m pytest tests/trade_alpha/unit/predict/ tests/trade_alpha/unit/models/test_predictor.py tests/trade_alpha/unit/indicators/test_close_position.py -v`
Expected: all passed

- [ ] **Step 2: Push**

```bash
git push
```
