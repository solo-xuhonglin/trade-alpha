# LSTM Time Series Validation Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix LSTM training overfitting by changing random validation split to time series split

**Architecture:** Modify the validation split logic in classifier.py to preserve time order when dividing train/validation sets

**Tech Stack:** Python, PyTorch, NumPy

---

## File Structure

- `backend/src/trade_alpha/models/lstm/classifier.py`: Modify - change random split to time series split

---

## Task 1: Change Validation Split to Time Series

**Files:**
- Modify: `backend/src/trade_alpha/models/lstm/classifier.py:89-94`

- [ ] **Step 1: Read current code**

```python
# 划分训练集和验证集 (80% / 20%)
num_samples = len(X_3d)
train_size = int(num_samples * 0.8)
indices = np.random.permutation(num_samples)
train_indices = indices[:train_size]
val_indices = indices[train_size:]
```

- [ ] **Step 2: Modify to time series split**

Replace with:

```python
# 划分训练集和验证集 (80% / 20%) - 时间序列划分
num_samples = len(X_3d)
train_size = int(num_samples * 0.8)
train_indices = np.arange(train_size)
val_indices = np.arange(train_size, num_samples)
```

- [ ] **Step 3: Verify syntax**

```bash
cd backend
python -c "from trade_alpha.models.lstm.classifier import LSTMClassifier; print('Import OK')"
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/models/lstm/classifier.py
git commit -m "feat: use time series validation split in LSTM training"
```

---

## Task 2: Verify with Existing Tests

**Files:**
- Test: `backend/tests/trade_alpha/unit/predict/test_lstm.py`

- [ ] **Step 1: Run LSTM unit tests**

```bash
cd backend
python -m pytest tests/trade_alpha/unit/predict/test_lstm.py -v
```

- [ ] **Step 2: Verify tests pass**

Expected: All tests pass

- [ ] **Step 3: Commit (if no changes needed, commit empty to mark completion)**

```bash
git commit --allow-empty -m "test: LSTM time series validation split verified"
```

---

## Self-Review

### 1. Spec Coverage

✅ Time series validation split - Task 1
✅ Verify no regression - Task 2

### 2. Placeholder Scan

✅ No TBD/TODO
✅ Complete code blocks
✅ Exact file paths

### 3. Type Consistency

✅ No type changes needed (same data structures)
