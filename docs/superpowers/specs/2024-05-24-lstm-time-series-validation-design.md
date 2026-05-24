# LSTM Training: Time Series Validation Split Design

## Problem Analysis

The current LSTM training uses **random split** to divide data into 80% training and 20% validation:
- Training and validation samples are interleaved in time
- Validation set cannot truly reflect the model's generalization ability to future data
- Early stopping mechanism is invalid: validation looks good but backtest performs poorly

**Symptoms:**
- Training loss and AUC improve with more data/epochs
- But backtest returns decrease
- Predictions become more extreme (probabilities near 0 or 1)

## Solution

Change to **time series split**:
- Sort data by time
- Training set: first 80% of time-ordered data
- Validation set: last 20% of time-ordered data

## Code Changes

### File: `backend/src/trade_alpha/models/lstm/classifier.py`

**Location:** Lines 89-94

**Before:**
```python
# 划分训练集和验证集 (80% / 20%)
num_samples = len(X_3d)
train_size = int(num_samples * 0.8)
indices = np.random.permutation(num_samples)
train_indices = indices[:train_size]
val_indices = indices[train_size:]
```

**After:**
```python
# 划分训练集和验证集 (80% / 20%) - 时间序列划分
num_samples = len(X_3d)
train_size = int(num_samples * 0.8)
train_indices = np.arange(train_size)
val_indices = np.arange(train_size, num_samples)
```

## Expected Effects

- Validation set comes from future time period relative to training data
- More realistically simulates backtest scenario
- Early stopping mechanism can more accurately reflect generalization ability
- Prevents model from overfitting to patterns in specific time periods

## Files to Modify

- `backend/src/trade_alpha/models/lstm/classifier.py`

## Testing

- Run existing LSTM unit tests to ensure no regression
- Verify training metrics still work correctly
- Compare validation AUC trend with time series split vs random split
