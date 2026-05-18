# 训练评估指标实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在训练完成后自动计算并存储评估指标（准确率、交叉验证分数、特征重要性、类别分布），为用户提供模型调优指导。

**Architecture:** 修改 `training_service.py` 新增评估函数，在训练流程中集成评估步骤，更新进度阶段计算，前端显示评估指标。

**Tech Stack:** Python 3.14+, FastAPI, XGBoost, scikit-learn, Vue 3

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `backend/src/trade_alpha/predict/training_service.py` | 训练流程和评估指标计算 |
| `backend/src/trade_alpha/api/routers/trainings.py` | 训练 API，返回评估指标 |
| `frontend/src/api/trainingRecord.ts` | 前端类型定义 |
| `frontend/src/views/TrainingRecordsView.vue` | 训练记录列表和详情 |

---

### Task 1: 修改 training_service.py - 新增评估函数

**Files:**
- Modify: `backend/src/trade_alpha/predict/training_service.py`

- [ ] **Step 1: 读取当前文件内容**

```bash
cat backend/src/trade_alpha/predict/training_service.py
```

- [ ] **Step 2: 新增 _evaluate_classifier 函数**

在 `_create_classifier` 函数后添加：

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

    update_progress(base_stage, "正在计算准确率...")
    for i, target in enumerate(targets):
        y_pred = classifier.models[target].predict(X)
        accuracy = (y_pred == y[:, i]).mean()
        metrics.setdefault("accuracy", {})[target] = float(accuracy)

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

    for target in targets:
        scores = np.array(cv_scores[target])
        metrics.setdefault("cv_scores", {})[target] = scores.tolist()
        metrics.setdefault("cv_mean", {})[target] = float(scores.mean())
        metrics.setdefault("cv_std", {})[target] = float(scores.std())

    update_progress(base_stage + cv_folds, "正在提取特征重要性...")
    for target in targets:
        model = classifier.models[target]
        if hasattr(model, "feature_importances_"):
            importances = model.feature_importances_
            importance_dict = {
                f: float(imp) for f, imp in zip(feature_fields, importances)
            }
            metrics.setdefault("feature_importance", {})[target] = importance_dict

    for i, target in enumerate(targets):
        unique, counts = np.unique(y[:, i], return_counts=True)
        dist = {str(int(k)): float(v) / len(y) for k, v in zip(unique, counts)}
        metrics.setdefault("class_distribution", {})[target] = dist

    return metrics
```

- [ ] **Step 3: 修改 create_training 函数**

修改进度计算和训练后评估：

```python
# 修改进度阶段计算（约第130行）
cv_folds = 5
total_stages = len(years) * 2 + 1 + cv_folds + 1

# 在 classifier.fit() 后添加评估逻辑（约第182行）
eval_base_stage = stage + 1
eval_metrics = _evaluate_classifier(
    classifier, X, y, all_targets, config.feature_fields,
    update, eval_base_stage, cv_folds
)

stage = total_stages
await update(stage, "训练完成")

# 修改 metrics 赋值（约第194行）
metrics={"sample_count": sample_count, **eval_metrics}
```

- [ ] **Step 4: 验证语法**

```bash
cd backend && python -c "from trade_alpha.predict.training_service import _evaluate_classifier; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/trade_alpha/predict/training_service.py
git commit -m "feat: add training evaluation metrics calculation"
```

---

### Task 2: 更新前端类型定义

**Files:**
- Modify: `frontend/src/api/trainingRecord.ts`

- [ ] **Step 1: 更新 Training 接口**

```typescript
export interface Training {
  id: string
  config_id: string
  name: string
  ts_codes: string[]
  start_date: string
  end_date: string
  metrics: {
    sample_count: number
    accuracy?: Record<string, number>
    cv_mean?: Record<string, number>
    cv_std?: Record<string, number>
    feature_importance?: Record<string, Record<string, number>>
    class_distribution?: Record<string, Record<string, number>>
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/trainingRecord.ts
git commit -m "feat: update training metrics type definition"
```

---

### Task 3: 更新前端训练记录列表显示

**Files:**
- Modify: `frontend/src/views/TrainingRecordsView.vue`

- [ ] **Step 1: 更新表头配置**

```typescript
const headers = [
  { title: '名称', key: 'name' },
  { title: '配置', key: 'configName' },
  { title: '股票', key: 'ts_codes' },
  { title: '日期范围', key: 'date_range' },
  { title: '样本数', key: 'sample_count' },
  { title: '准确率', key: 'accuracy' },
  { title: 'CV分数', key: 'cv_score' },
  { title: '操作', key: 'actions', sortable: false, align: 'end' as const },
]
```

- [ ] **Step 2: 更新训练列表项映射**

```typescript
trainings.value = res.data.map(t => {
  const config = configs.value.find(c => c.id === t.config_id)
  const acc3d = t.metrics.accuracy?.label_3d?.toFixed(4) || '-'
  const cv3d = t.metrics.cv_mean?.label_3d ? 
    `${t.metrics.cv_mean.label_3d.toFixed(4)}±${t.metrics.cv_std?.label_3d.toFixed(4) || '0'}` : '-'
  return {
    ...t,
    configName: config?.name || t.config_id,
    date_range: `${t.start_date} ~ ${t.end_date}`,
    sample_count: t.metrics.sample_count,
    accuracy: acc3d,
    cv_score: cv3d,
  }
})
```

- [ ] **Step 3: 更新模板显示**

```vue
<template v-slot:item.accuracy="{ item }">
  <span>{{ item.accuracy }}</span>
</template>
<template v-slot:item.cv_score="{ item }">
  <span>{{ item.cv_score }}</span>
</template>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/TrainingRecordsView.vue
git commit -m "feat: display training evaluation metrics in list"
```

---

### Task 4: 测试验证

**Files:**
- Test: `backend/scripts/test_training_small.py`

- [ ] **Step 1: 运行小型训练测试**

```bash
cd backend && python scripts/test_training_small.py
```

Expected: 训练完成后 metrics 包含 accuracy、cv_mean、cv_std、feature_importance、class_distribution

- [ ] **Step 2: 检查数据库记录**

```bash
cd backend && python -c "
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from trade_alpha.config import load_config
from trade_alpha.dao import TrainingResult
import asyncio

async def check():
    config = load_config()
    client = AsyncIOMotorClient(config.mongodb_uri)
    await init_beanie(database=client[config.mongodb_db], document_models=[TrainingResult])
    latest = await TrainingResult.find_one(sort=[('created_at', -1)])
    print('Metrics:', latest.metrics if latest else 'No training found')

asyncio.run(check())
"
```

Expected: 输出包含 accuracy、cv_mean 等字段

---

## 自我审查

1. **Spec 覆盖:**
   - ✓ 准确率计算
   - ✓ 5-fold 交叉验证（每 fold 进度）
   - ✓ 特征重要性提取
   - ✓ 类别分布统计
   - ✓ 进度显示集成

2. **占位符检查:**
   - ✓ 无 TBD/TODO
   - ✓ 所有步骤有具体代码
   - ✓ 所有命令完整

3. **类型一致性:**
   - ✓ 后端 metrics 结构与前端接口一致
   - ✓ 函数参数类型一致
