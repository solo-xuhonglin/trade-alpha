# 模型评估指标简化方案

## 目标

移除训练后的交叉验证逻辑，简化评估流程，并为 LSTM 添加必要的训练 loss 指标。

## 背景

当前训练完成后执行 5 折交叉验证，对于 XGBoost 需要重新训练 5 个模型（耗时较长），而 LSTM 则直接复用已训练模型进行预测。

简化后，两个模型保留通用指标，LSTM 额外记录训练 loss 以监控收敛情况。

## 保留的指标

| 指标 | XGBoost | LSTM | 说明 |
|------|---------|------|------|
| `accuracy` | ✅ | ✅ | 训练集准确率 |
| `class_distribution` | ✅ | ✅ | 类别分布 |
| `feature_importance` | ✅ | ❌ | 特征重要性 |
| `sample_count` | ✅ | ✅ | 样本数量 |

## 移除的指标

| 指标 | 说明 |
|------|------|
| `cv_scores` | 5 折交叉验证各 fold 准确率 |
| `cv_mean` | 交叉验证平均准确率 |
| `cv_std` | 交叉验证标准差 |

## 新增的指标（LSTM 专用）

| 指标 | 说明 |
|------|------|
| `final_train_loss` | 最终训练 loss（最后一个 epoch） |
| `loss_per_epoch` | 每 epoch 的 loss 列表 |

## 修改范围

### Backend

#### 1. `backend/src/trade_alpha/models/classifiers/lstm.py`
- 修改 `fit` 方法，保存每个 epoch 的平均 loss
- 返回 final_train_loss 和 loss_per_epoch

#### 2. `backend/src/trade_alpha/models/training/trainer.py`
- 移除 `_evaluate_classifier` 中的交叉验证循环（111-146 行）
- 保留 accuracy、class_distribution、feature_importance 计算
- 在训练后调用分类器获取 loss 指标
- 将 loss 指标合并到 model_metrics

#### 3. `backend/src/trade_alpha/models/classifiers/base.py`
- 考虑在基类中添加可选的 loss 指标返回接口（可选）

### Frontend

#### 4. `frontend/src/api/trainingRecord.ts`
- 移除 `cv_mean`、`cv_std`、`cv_scores` 类型定义
- 新增 `train_loss`、`loss_per_epoch` 类型定义

#### 5. `frontend/src/views/TrainingRecordsView.vue`
- 移除 cv_mean、cv_std、cv_scores 相关显示（表格列、详情弹窗）
- 在详情弹窗中新增 LSTM loss 曲线或数值显示

### Documents

#### 6. `docs/database-schema.md`
- 更新 TrainingResult.model_metrics 字段说明
- 移除 cv 相关字段描述
- 新增 train_loss、loss_per_epoch 字段描述

#### 7. `docs/frontend.md`
- 更新前端显示相关说明

## 数据结构变更

### model_metrics 最终结构

```json
{
  "sample_count": 10000,
  "accuracy": {
    "label_3d": 0.65,
    "label_5d": 0.62
  },
  "class_distribution": {
    "label_3d": {"-1": 0.3, "0": 0.4, "1": 0.3},
    "label_5d": {"-1": 0.35, "0": 0.3, "1": 0.35}
  },
  "feature_importance": {
    "label_3d": {"ma_5": 0.15, "rsi_6": 0.12},
    "label_5d": {"ma_5": 0.18, "rsi_6": 0.10}
  },
  "final_train_loss": 0.123,
  "loss_per_epoch": [0.45, 0.32, 0.25, 0.18, 0.15, 0.13, 0.12]
}
```

> 注：XGBoost 不包含 `final_train_loss` 和 `loss_per_epoch`。

## 测试影响

- 集成测试 `test_51_training_xgboost.py` 和 `test_53_training_lstm.py` 中的断言可能需要调整
- 检查 model_metrics 中的 cv 相关字段是否已移除
- 验证 LSTM loss 指标正确记录

## 实现顺序

1. 后端 LSTM 分类器添加 loss 记录
2. 后端 trainer 移除交叉验证逻辑
3. 前端类型定义更新
4. 前端 UI 调整
5. 文档更新
6. 测试修复

## 风险评估

- **低风险**：仅移除冗余计算，添加简单指标
- **向后兼容**：历史训练记录的 cv 字段保留，前端做兼容显示
