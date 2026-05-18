# 训练评估指标方案

## 背景

新增 RSI、ATR、OBV 指标后，回测效果下降。用户需要训练完成后的评估指标（准确率、特征重要性等）作为调整模型的参考。

## 现有状态

### 后端
- `TrainingResult.metrics` 字段：`Dict[str, Any]`，目前仅存储 `sample_count`
- 进度机制：`total_stages = len(years) * 2 + 1`（加载→打标签→训练）
- 进度回调：`progress_callback(stage / total_stages * 100, message)`

### 前端
- `TrainingRecordsView.vue`：训练列表页，目前显示样本数和 MAE
- `trainingRecord.ts`：`Training` 接口的 `metrics` 字段沿用旧的回归任务结构

## 设计目标

训练完成后自动计算并存储评估指标，为用户提供模型调优指导：

1. **准确率** — 各目标的分类准确率
2. **交叉验证分数** — 5-fold CV 平均准确率（分 fold 显示进度）
3. **特征重要性** — 各特征对模型的贡献度
4. **预测分布** — 各目标类别分布统计

## 实现方案

### 1. 扩展 TrainingResult.metrics 结构

```python
# 训练完成后计算的指标
metrics: {
    "sample_count": int,
    "accuracy": {
        "label_3d": 0.52,
        "label_5d": 0.51
    },
    "cv_scores": {
        "label_3d": [0.51, 0.52, 0.50, 0.53, 0.51],  # 5-fold
        "label_5d": [0.50, 0.51, 0.52, 0.50, 0.51]
    },
    "cv_mean": {
        "label_3d": 0.514,
        "label_5d": 0.508
    },
    "cv_std": {
        "label_3d": 0.010,
        "label_5d": 0.008
    },
    "feature_importance": {
        "label_3d": {
            "pct_chg": 0.045,
            "volume": 0.038,
            "rsi_6": 0.012
        },
        "label_5d": {
            "pct_chg": 0.042,
            "volume": 0.035,
            "rsi_6": 0.015
        }
    },
    "class_distribution": {
        "label_3d": {"-1": 0.35, "0": 0.30, "1": 0.35},
        "label_5d": {"-1": 0.33, "0": 0.34, "1": 0.33}
    }
}
```

### 2. 修改 training_service.py

**进度阶段调整**：
- 原：`total_stages = len(years) * 2 + 1`（加载→标签→训练）
- 改：`total_stages = len(years) * 2 + 1 + 5 + 1`（加载→标签→训练→CV 1-5→评估完成）

**新增 `_evaluate_classifier` 函数**：

```python
def _evaluate_classifier(
    classifier,
    X: np.ndarray,
    y: np.ndarray,
    targets: List[str],
    feature_fields: List[str],
    update_progress: callable,
    base_stage: int,
    cv_folds: int = 5,
) -> dict:
    """计算分类器评估指标"""
    from sklearn.model_selection import KFold

    metrics = {}

    # 1. 计算准确率（用训练集）
    update_progress(base_stage, "正在计算准确率...")
    for i, target in enumerate(targets):
        y_pred = classifier.models[target].predict(X)
        accuracy = (y_pred == y[:, i]).mean()
        metrics.setdefault("accuracy", {})[target] = float(accuracy)

    # 2. 交叉验证（5-fold，每 fold 单独进度）
    kf = KFold(n_splits=cv_folds, shuffle=True, random_state=42)
    cv_scores = {target: [] for target in targets}

    for fold_idx, (train_idx, val_idx) in enumerate(kf.split(X)):
        stage = base_stage + fold_idx + 1
        update_progress(stage, f"交叉验证 Fold {fold_idx + 1}/{cv_folds}...")

        X_train, X_val = X[train_idx], X[val_idx]
        for i, target in enumerate(targets):
            y_train, y_val = y[train_idx, i], y[val_idx, i]
            model_cls = classifier.models[target].__class__
            model = model_cls(**classifier.models[target].get_params())
            model.fit(X_train, y_train)
            y_pred = model.predict(X_val)
            acc = (y_pred == y_val).mean()
            cv_scores[target].append(acc)

    # 整理 CV 分数
    for target in targets:
        scores = np.array(cv_scores[target])
        metrics.setdefault("cv_scores", {})[target] = scores.tolist()
        metrics.setdefault("cv_mean", {})[target] = float(scores.mean())
        metrics.setdefault("cv_std", {})[target] = float(scores.std())

    # 3. 特征重要性
    update_progress(base_stage + cv_folds, "正在提取特征重要性...")
    for target in targets:
        model = classifier.models[target]
        if hasattr(model, "feature_importances_"):
            importances = model.feature_importances_
            importance_dict = {
                f: float(imp) for f, imp in zip(feature_fields, importances)
            }
            metrics.setdefault("feature_importance", {})[target] = importance_dict

    # 4. 类别分布
    for i, target in enumerate(targets):
        unique, counts = np.unique(y[:, i], return_counts=True)
        dist = {str(int(k)): float(v) / len(y) for k, v in zip(unique, counts)}
        metrics.setdefault("class_distribution", {})[target] = dist

    return metrics
```

**修改 `create_training` 流程**：

```python
# 进度计算调整
cv_folds = 5
total_stages = len(years) * 2 + 1 + cv_folds + 1  # +训练 +CV5 +收尾

# 训练阶段
stage += 1
await update(stage, "正在训练模型...")

X = np.vstack(all_X)
y = np.vstack(all_y) if len(all_y) > 1 else all_y[0]
sample_count = len(X)

classifier = _create_classifier(config)
classifier.fit(X, y, all_targets)

# 评估阶段
eval_base_stage = stage + 1
eval_metrics = _evaluate_classifier(
    classifier, X, y, all_targets, config.feature_fields,
    update_progress, eval_base_stage, cv_folds
)

stage = total_stages
await update(stage, "训练完成")

# 更新训练记录
training = TrainingResult(...)
training.metrics = {"sample_count": sample_count}
training.metrics.update(eval_metrics)
```

### 3. 修改前端 TrainingRecordsView.vue

新增训练详情展开面板，显示：
- 各目标准确率卡片
- CV 分数均值 ± 标准差
- 特征重要性柱状图（Top 10）
- 类别分布饼图

### 4. 更新前端类型定义

```typescript
// trainingRecord.ts
interface TrainingMetrics {
  sample_count: number
  accuracy?: Record<string, number>
  cv_mean?: Record<string, number>
  cv_std?: Record<string, number>
  feature_importance?: Record<string, Record<string, number>>
  class_distribution?: Record<string, Record<string, number>>
}
```

## 文件修改清单

| 文件 | 修改内容 |
|------|---------|
| `backend/src/trade_alpha/predict/training_service.py` | 新增 `_evaluate_classifier` 函数，调整进度阶段，支持逐 fold 进度 |
| `frontend/src/api/trainingRecord.ts` | 更新 `Training` 接口 |
| `frontend/src/views/TrainingRecordsView.vue` | 新增详情展开面板 |

## 进度显示变更

| 阶段 | 消息 | 进度(%) |
|------|------|---------|
| 原训练 | "正在训练模型..." → 完成 | ~70 |
| 评估 | "正在计算准确率..." → 完成 | ~72 |
| CV | "交叉验证 Fold 1/5..." | ~76 |
| CV | "交叉验证 Fold 2/5..." | ~80 |
| CV | "交叉验证 Fold 3/5..." | ~84 |
| CV | "交叉验证 Fold 4/5..." | ~88 |
| CV | "交叉验证 Fold 5/5..." | ~92 |
| 评估 | "正在提取特征重要性..." | ~96 |
| 完成 | "训练完成" | 100 |

用户训练时将看到交叉验证每一个 fold 的进度。

## 风险与注意事项

1. **性能影响**：交叉验证会增加训练时间（约 5-6 倍），但进度显示更细致
2. **向后兼容**：旧训练记录没有新指标，前端需处理缺失字段
3. **存储大小**：特征重要性存所有特征，评估完成后约占 1-2 KB/训练
