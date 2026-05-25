# LSTM 训练集验证集时间划分修复

## 概述

修复 LSTM 训练时训练集和验证集的划分方式，确保验证集使用完全在训练集之后的日期，模拟真实预测场景，避免数据泄露。

## 问题

当前按样本索引划分训练/验证集（80%/20%），可能导致验证集包含早于训练集的日期，无法正确评估模型在未来未知数据上的表现。

## 修复方案

### 修改位置

`backend/src/trade_alpha/models/lstm/classifier.py` 中的 `LSTMClassifier.train` 方法，第104-108行

### 修复逻辑

1. 保留当前 `create_sequences` 返回的 `dates` 数组已经按时间排序
2. 获取唯一日期并找到第80%位置的日期作为分割点
3. 使用布尔 mask 同时索引 `X_3d`、`y_2d`、`dates` 三个数组
4. 确保索引关系严格对应

### 具体修改

```python
# 按时间划分训练集和验证集 (80% / 20%)
# 确保验证集都是训练集之后的日期
num_samples = len(dates)
if num_samples > 0:
    unique_dates = np.unique(dates)
    split_idx = int(len(unique_dates) * 0.8)
    split_date = unique_dates[split_idx]
    train_mask = dates <= split_date
    val_mask = dates > split_date
    # 确保至少有一个验证样本
    if not np.any(val_mask):
        split_date = unique_dates[-1]
        train_mask = dates <= split_date
        val_mask = dates > split_date
```

## 确保对应关系

严格保留 `X_3d[i]` <-> `y_2d[i]` <-> `dates[i]` 的对应关系。
