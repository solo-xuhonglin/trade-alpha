# 模型评估指标简化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 移除交叉验证逻辑，简化评估流程，为 LSTM 添加训练 loss 指标

**Architecture:** 修改 XGBoost 和 LSTM 的 fit 方法统一返回训练结果，修改 trainer.py 移除交叉验证循环，直接使用 fit 方法返回值获取 loss 指标

**Tech Stack:** Python, PyTorch (LSTM), XGBoost, NumPy, MongoDB/Beanie

---

## 文件修改清单

| 文件 | 修改类型 | 说明 |
|------|---------|------|
| `backend/src/trade_alpha/models/classifiers/xgboost.py` | 修改 | fit 方法返回统一结果 |
| `backend/src/trade_alpha/models/classifiers/lstm.py` | 修改 | fit 方法返回 loss 记录 |
| `backend/src/trade_alpha/models/training/trainer.py` | 修改 | 移除交叉验证，使用返回值 |
| `frontend/src/api/trainingRecord.ts` | 修改 | 更新类型定义 |
| `frontend/src/views/TrainingRecordsView.vue` | 修改 | 移除 cv 相关显示 |
| `docs/database-schema.md` | 修改 | 更新字段文档 |
| `docs/frontend.md` | 修改 | 更新前端文档 |

---

## Task 1: 统一分类器接口

**Files:**
- Modify: `backend/src/trade_alpha/models/classifiers/xgboost.py:35-57`
- Modify: `backend/src/trade_alpha/models/classifiers/lstm.py:81-146`

- [ ] **Step 1: 修改 XGBoost fit 方法返回类型**

修改 `XGBoostClassifier.fit` 方法，添加返回类型注解和返回值。

原方法：
```python
def fit(self, X: np.ndarray, y: np.ndarray, target_names: List[str]) -> None:
    self.models = {}
    self._label_mapping = {}
    for i, target in enumerate(target_names):
        # ... 训练逻辑 ...
    # 无返回值
```

新方法：
```python
def fit(self, X: np.ndarray, y: np.ndarray, target_names: List[str]) -> Dict[str, Any]:
    """Train XGBoost models.
    
    Returns:
        Dict with 'final_train_loss' (None for XGBoost) and 'loss_per_epoch' (empty for XGBoost)
    """
    self.models = {}
    self._label_mapping = {}
    for i, target in enumerate(target_names):
        # ... 现有训练逻辑保持不变 ...
    
    # 返回统一的训练结果
    return {
        "final_train_loss": None,
        "loss_per_epoch": []
    }
```

- [ ] **Step 2: 修改 LSTM 添加类型导入**

在文件顶部修改导入：
```python
from typing import List, Dict, Any
```

- [ ] **Step 3: 修改 LSTM fit 方法返回类型和 loss 记录**

原方法：
```python
def fit(self, X: np.ndarray, y: np.ndarray, target_names: List[str]) -> None:
```

新方法：
```python
def fit(self, X: np.ndarray, y: np.ndarray, target_names: List[str]) -> Dict[str, Any]:
    """Train LSTM models and return training metrics.
    
    Returns:
        Dict with 'final_train_loss' and 'loss_per_epoch'
    """
```

- [ ] **Step 4: 修改 LSTM 训练循环，保存每个 epoch 的 loss**

在 `for target_idx, target in enumerate(target_names):` 之前初始化：
```python
all_epoch_losses = []
```

在训练循环结束后（第 146 行附近），在 `self.models[target] = model.cpu()` 之后添加：
```python
# 计算该 target 的平均 loss
avg_loss = epoch_loss / num_batches if num_batches > 0 else 0.0
all_epoch_losses.append(float(avg_loss))
```

- [ ] **Step 5: 修改 LSTM 返回值**

在方法末尾返回 loss 信息：

原代码：
```python
# 没有任何返回值
```

新代码：
```python
# 返回统一的训练结果
return {
    "final_train_loss": all_epoch_losses[-1] if all_epoch_losses else None,
    "loss_per_epoch": all_epoch_losses
}
```

- [ ] **Step 6: 运行单元测试验证**

```bash
cd backend && pytest tests/trade_alpha/unit/predict/test_lstm.py tests/trade_alpha/unit/predict/test_xgboost.py -v
```

---

## Task 2: Trainer 移除交叉验证

**Files:**
- Modify: `backend/src/trade_alpha/models/training/trainer.py:81-148`
- Modify: `backend/src/trade_alpha/models/training/trainer.py:214-225`

- [ ] **Step 1: 修改 _evaluate_classifier 函数**

移除 `n_splits` 参数：

原代码：
```python
async def _evaluate_classifier(
    classifier,
    X: np.ndarray,
    y: np.ndarray,
    feature_names: List[str],
    targets: List[str],
    n_splits: int = 5,
) -> Dict:
```

新代码：
```python
async def _evaluate_classifier(
    classifier,
    X: np.ndarray,
    y: np.ndarray,
    feature_names: List[str],
    targets: List[str],
) -> Dict:
```

- [ ] **Step 2: 移除交叉验证循环代码**

删除 111-146 行的交叉验证代码块：

删除内容：
```python
kf = KFold(n_splits=n_splits, shuffle=True, random_state=42)

is_lstm = hasattr(classifier, "sequence_length")

for fold_idx, (train_idx, val_idx) in enumerate(kf.split(X)):
    X_train, X_val = X[train_idx], X[val_idx]

    for i, target in enumerate(targets):
        y_train, y_val = y[train_idx, i], y[val_idx, i]

        if is_lstm:
            y_val_pred = classifier.predict(X_val, [target]).get(target, y_val[0])
            fold_accuracy = float(np.mean(y_val_pred == y_val))
        else:
            unique_labels = sorted(set(y_train))
            label_map = {label: j for j, label in enumerate(unique_labels)}
            y_train_mapped = np.array([label_map[v] for v in y_train])
            y_val_mapped = np.array([label_map[v] for v in y_val])

            model_cls = classifier.models[target].__class__
            model = model_cls(**classifier.models[target].get_params())
            model.fit(X_train, y_train_mapped)

            y_val_pred_mapped = model.predict(X_val)
            y_val_pred = np.array([unique_labels[j] for j in y_val_pred_mapped])
            fold_accuracy = float(np.mean(y_val_pred == y_val))

        if target not in metrics.get("cv_scores", {}):
            metrics.setdefault("cv_scores", {})[target] = []
        metrics["cv_scores"][target].append(fold_accuracy)

for target in targets:
    if target in metrics["cv_scores"]:
        scores = np.array(metrics["cv_scores"][target])
        metrics.setdefault("cv_mean", {})[target] = float(scores.mean())
        metrics.setdefault("cv_std", {})[target] = float(scores.std())
```

保留 92-109 行的基础指标计算（accuracy、class_distribution、feature_importance）。

- [ ] **Step 3: 修改 create_training 函数，获取 fit 返回值**

找到第 214 行的调用：
```python
classifier.fit(X, y, target_names)
```

修改为：
```python
training_metrics = classifier.fit(X, y, target_names)
```

- [ ] **Step 4: 修改评估调用，移除 n_splits 参数**

找到第 218-225 行的代码：
```python
eval_metrics = await _evaluate_classifier(
    classifier,
    X,
    y,
    config.feature_fields,
    target_names,
    n_splits=5,
)
```

修改为：
```python
eval_metrics = await _evaluate_classifier(
    classifier,
    X,
    y,
    config.feature_fields,
    target_names,
)
```

- [ ] **Step 5: 添加 loss 指标合并逻辑**

在 `eval_metrics = await _evaluate_classifier(...)` 之后，添加：

```python
# 合并训练 loss 指标
if training_metrics and training_metrics.get("final_train_loss") is not None:
    eval_metrics["final_train_loss"] = training_metrics["final_train_loss"]
    eval_metrics["loss_per_epoch"] = training_metrics["loss_per_epoch"]
```

- [ ] **Step 6: 运行集成测试**

```bash
cd backend && pytest tests/trade_alpha/integration/test_51_training_xgboost.py tests/trade_alpha/integration/test_53_training_lstm.py -v
```

---

## Task 3: 前端类型定义更新

**Files:**
- Modify: `frontend/src/api/trainingRecord.ts`

- [ ] **Step 1: 更新 TrainingMetrics 接口**

原接口：
```typescript
export interface TrainingMetrics {
  sample_count: number
  accuracy?: Record<string, number>
  cv_mean?: Record<string, number>
  cv_std?: Record<string, number>
  cv_scores?: Record<string, number[]>
  feature_importance?: Record<string, Record<string, number>>
  class_distribution?: Record<string, Record<string, number>>
}
```

新接口：
```typescript
export interface TrainingMetrics {
  sample_count: number
  accuracy?: Record<string, number>
  final_train_loss?: number
  loss_per_epoch?: number[]
  feature_importance?: Record<string, Record<string, number>>
  class_distribution?: Record<string, Record<string, number>>
}
```

- [ ] **Step 2: 验证前端编译**

```bash
cd frontend && npm run build
```

---

## Task 4: 前端训练记录页面更新

**Files:**
- Modify: `frontend/src/views/TrainingRecordsView.vue`

- [ ] **Step 1: 移除 CV 表格列**

删除 115-126 行的 CV 均值和标准差列：
```html
<th>CV均值</th>
<th>CV标准差</th>
<!-- 和对应的表格数据行 -->
<td>{{ ((detailItem.model_metrics.cv_mean?.[target] || 0) * 100).toFixed(2) }}%</td>
<td>{{ ((detailItem.model_metrics.cv_std?.[target] || 0) * 100).toFixed(4) }}%</td>
```

- [ ] **Step 2: 移除 CV Tab**

删除 131-148 行的 CV Tab 内容：
```html
<v-window-item value="cv">
  <!-- 整个 cv_scores 表格 -->
</v-window-item>
```

- [ ] **Step 3: 添加训练 Loss 显示**

在训练准确率表格之后添加 Loss 显示：

```html
<v-window-item value="loss">
  <div v-if="detailItem.model_metrics.loss_per_epoch">
    <div class="text-subtitle-2 mb-2">训练 Loss</div>
    <div class="text-caption mb-1">
      Final Loss: {{ detailItem.model_metrics.final_train_loss?.toFixed(4) }}
    </div>
    <div v-for="(loss, idx) in detailItem.model_metrics.loss_per_epoch" :key="idx">
      Epoch {{ idx + 1 }}: {{ loss.toFixed(4) }}
    </div>
  </div>
  <div v-else class="text-caption text-medium-emphasis">
    仅 LSTM 模型记录训练 Loss
  </div>
</v-window-item>
```

- [ ] **Step 4: 确保 Loss Tab 存在于 v-window 的 tabs 中**

检查并确保存在：
```html
<v-tab value="loss">训练Loss</v-tab>
```

- [ ] **Step 5: 验证页面功能**

```bash
cd frontend && npm run dev
```

---

## Task 5: 文档更新

**Files:**
- Modify: `docs/database-schema.md`
- Modify: `docs/frontend.md`

- [ ] **Step 1: 更新 database-schema.md**

找到 TrainingResult.model_metrics 相关内容，删除：
```
| `cv_scores` | 5折交叉验证各fold的准确率 |
| `cv_mean` | 交叉验证平均准确率 |
| `cv_std` | 交叉验证标准差 |
```

添加新字段：
```
| `final_train_loss` | LSTM 最终训练 loss（仅 LSTM） |
| `loss_per_epoch` | LSTM 每 epoch 的 loss 列表（仅 LSTM） |
```

- [ ] **Step 2: 更新 frontend.md**

找到前端显示相关章节，删除 cv_mean、cv_std、cv_scores 相关说明，添加 final_train_loss、loss_per_epoch 说明。

---

## Task 6: 测试验证

**Files:**
- 测试: `backend/tests/trade_alpha/integration/test_51_training_xgboost.py`
- 测试: `backend/tests/trade_alpha/integration/test_53_training_lstm.py`

- [ ] **Step 1: 检查并修复 XGBoost 测试**

检查 `test_51_training_xgboost.py` 中断言 cv 相关字段的代码，如有则移除。

- [ ] **Step 2: 检查并修复 LSTM 测试**

检查 `test_53_training_lstm.py` 中断言 cv 相关字段的代码，如有则移除。
验证 final_train_loss 和 loss_per_epoch 字段存在。

- [ ] **Step 3: 运行完整集成测试**

```bash
cd backend && pytest tests/trade_alpha/integration/ -v
```

---

## 执行顺序

1. Task 1: 统一分类器接口
2. Task 2: Trainer 移除交叉验证
3. Task 3: 前端类型定义更新
4. Task 4: 前端训练记录页面更新
5. Task 5: 文档更新
6. Task 6: 测试验证

---

## 预期结果

- 训练时间显著缩短（移除交叉验证）
- model_metrics 结构简化
- XGBoost 和 LSTM 接口统一
- LSTM 提供额外的 loss 监控能力
- 前端显示更清晰，无冗余字段
