# LSTM 预测概率极端化优化设计文档

**日期**: 2026-05-24  
**项目**: Trade Alpha  
**目标**: 解决 LSTM 模型训练后预测概率过于极端的问题

---

## 1. 问题分析

### 1.1 核心问题：双重 softmax

当前代码存在严重的架构问题：

```python
# d:/projects/trade-alpha/backend/src/trade_alpha/models/lstm/classifier.py
class LSTMModel(nn.Module):
    def forward(self, x):
        out, _ = self.lstm(x)
        return torch.softmax(self.fc(out[:, -1, :]), dim=1)  # ❌ 问题1：提前做了 softmax
```

```python
# classifier.py - train()
criterion = nn.CrossEntropyLoss()  # ❌ 问题2：内部又做了一次 softmax + log
```

### 1.2 问题影响

- **梯度计算异常**：`CrossEntropyLoss` 期望输入原始 logits，但我们传入了 softmax 后的概率
- **模型过度自信**：训练过程中梯度异常，导致模型对预测结果过度自信
- **预测概率极端**：出现 [0.99, 0.01, 0.0] 这种极端分布

### 1.3 其他问题

1. **缺少验证集和早停**：固定 25 个 epoch，容易过拟合
2. **正则化不足**：dropout 只有 0.1，没有 L2 正则化
3. **缺少标签平滑**：可以让模型预测更加平滑

---

## 2. 优化方案

### 2.1 后端优化

| 优化项 | 当前值 | 修改后 |
|--------|--------|--------|
| 模型输出 | `softmax` | **移除 softmax，返回原始 logits** |
| 损失函数 | `CrossEntropyLoss()` | **`CrossEntropyLoss(label_smoothing=0.1)`** |
| Dropout | 0.1 | **0.2** |
| L2 正则化 | 无 | **`weight_decay=1e-4`** |
| 训练验证划分 | 无 | **80% 训练，20% 验证** |
| 早停 | 无 | **连续 5 epoch 验证 loss 不下降则停止** |

### 2.2 前端优化

1. **训练记录详情弹窗**：
   - 新增早停信息展示
   - 根据模型类型隐藏不相关的标签页（如 XGBoost 不显示「训练 Loss」，LSTM 不显示「特征重要性」）

2. **训练指标 API**：
   - 新增早停相关字段

---

## 3. 后端实现

### 3.1 新增配置参数

**文件**: `d:/projects/trade-alpha/backend/src/trade_alpha/models/training/config.py`

新增以下配置项到 `create_config()`：

```python
label_smoothing: float = 0.1  # 标签平滑系数
early_stopping_patience: int = 5  # 早停耐心值
```

同时更新 API 路由 `d:/projects/trade-alpha/backend/src/trade_alpha/api/routers/model_configs.py` 支持这两个参数。

### 3.2 修改 LSTM 模型

**文件**: `d:/projects/trade-alpha/backend/src/trade_alpha/models/lstm/classifier.py`

#### 3.2.1 LSTMModel 类

```python
class LSTMModel(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, num_class=3, dropout=0.2):  # dropout 从 0.1 改为 0.2
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True,
                            dropout=dropout if num_layers > 1 else 0)
        self.fc = nn.Linear(hidden_size, num_class)
    
    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])  # 移除 softmax，返回 logits
```

#### 3.2.2 LSTMClassifier.train() 方法

修改要点：

1. **划分训练/验证集**：按 80/20 划分
2. **添加标签平滑**：`CrossEntropyLoss(label_smoothing=label_smoothing)`
3. **添加 L2 正则化**：`Adam(..., weight_decay=1e-4)`
4. **实现早停**：监控验证 loss
5. **保存最佳模型**：在训练过程中保存最佳模型状态
6. **更新 metrics**：新增早停相关字段

**新增 TrainingResult.metrics 字段**：

```python
metrics = {
    "final_train_loss": all_epoch_losses[-1] if all_epoch_losses else None,
    "loss_per_epoch": all_epoch_losses,
    "val_loss_per_epoch": val_epoch_losses,  # 新增
    "sample_count": len(X_3d),
    "actual_epochs": actual_epochs,  # 新增：实际训练的 epoch 数
    "early_stopped": early_stopped,  # 新增：是否触发早停
    "best_epoch": best_epoch,  # 新增：最佳模型的 epoch
}
```

#### 3.2.3 修改 predict 和 predict_proba 方法

```python
def predict(self, features, target_names):
    # ... 前面代码不变
    for target in target_names:
        if target not in self.models:
            continue
        self.models[target].eval()
        with torch.no_grad():
            logits = self.models[target](X_tensor)  # 拿到 logits
            pred_idx = torch.argmax(logits, dim=1)[0].item()
            result[target] = self._label_mapping[target][pred_idx]
    return result
```

```python
def predict_proba(self, features, target_names):
    # ... 前面代码不变
    for target in target_names:
        if target not in self.models:
            continue
        self.models[target].eval()
        with torch.no_grad():
            logits = self.models[target](X_tensor)
            proba_mapped = torch.softmax(logits, dim=1)[0].numpy()  # 现在在这里做 softmax
            label_map = self._label_mapping[target]
            proba = [0.0, 0.0, 0.0]
            for j, label in label_map.items():
                proba[label + 1] = proba_mapped[j]
            result[target] = proba
    return result
```

### 3.3 DAO 层更新

**文件**: `d:/projects/trade-alpha/backend/src/trade_alpha/dao/training.py`（需查看 DAO 定义）

`TrainingResult` 无需修改，`model_metrics` 是动态字段，可以直接存储新键。

### 3.4 API 路由更新

`d:/projects/trade-alpha/backend/src/trade_alpha/api/routers/trainings.py` 无需修改，自动兼容。

---

## 4. 前端实现

### 4.1 更新 TypeScript 类型定义

**文件**: `d:/projects/trade-alpha/frontend/src/api/trainingRecord.ts`

```typescript
export interface TrainingMetrics {
  sample_count: number
  accuracy?: Record<string, number>
  final_train_loss?: number
  loss_per_epoch?: number[]
  val_loss_per_epoch?: number[]  // 新增
  feature_importance?: Record<string, Record<string, number>>
  class_distribution?: Record<string, Record<string, number>>
  actual_epochs?: number  // 新增
  early_stopped?: boolean  // 新增
  best_epoch?: number  // 新增
}
```

### 4.2 更新训练记录详情弹窗

**文件**: `d:/projects/trade-alpha/frontend/src/views/TrainingRecordsView.vue`

#### 4.2.1 标签页按模型类型条件显示

```vue
<v-tabs v-model="detailTab" color="primary">
  <v-tab value="overview">概览</v-tab>
  <v-tab value="accuracy">准确率</v-tab>
  <v-tab v-if="detailItem?.model_type === 'lstm'" value="loss">训练Loss</v-tab>
  <v-tab v-if="detailItem?.model_type === 'xgboost'" value="features">特征重要性</v-tab>
</v-tabs>
```

#### 4.2.2 概览页新增早停信息卡片

```vue
<v-row>
  <v-col cols="12" sm="4">
    <v-card variant="outlined">
      <v-card-text class="text-center">
        <div class="text-h5">{{ detailItem.model_metrics.sample_count?.toLocaleString() }}</div>
        <div class="text-caption">样本数</div>
      </v-card-text>
    </v-card>
  </v-col>
  
  <!-- 新增：早停信息 -->
  <v-col v-if="detailItem?.model_type === 'lstm'" cols="12" sm="4">
    <v-card variant="outlined">
      <v-card-text class="text-center">
        <div class="text-h5">
          <span v-if="detailItem.model_metrics.early_stopped">早停于第 {{ detailItem.model_metrics.actual_epochs }} 轮</span>
          <span v-else>{{ detailItem.model_metrics.actual_epochs || detailItem.lstm_epochs || 25 }} 轮</span>
        </div>
        <div class="text-caption">
          <span v-if="detailItem.model_metrics.early_stopped">
            最佳: 第 {{ detailItem.model_metrics.best_epoch }} 轮
          </span>
          <span v-else>训练完成</span>
        </div>
      </v-card-text>
    </v-card>
  </v-col>
  
  <v-col v-for="target in ['label_3d', 'label_5d']" :key="target" cols="12" sm="4">
    <!-- ... 原有准确率卡片 ... -->
  </v-col>
</v-row>
```

#### 4.2.3 Loss 页添加验证 Loss

```vue
<v-window-item value="loss">
  <div v-if="detailItem.model_metrics.loss_per_epoch">
    <div class="text-subtitle-2 mb-2">训练 Loss</div>
    <div class="text-caption mb-1">
      Final Loss: {{ detailItem.model_metrics.final_train_loss?.toFixed(4) }}
    </div>
    <div v-for="(loss, idx) in detailItem.model_metrics.loss_per_epoch" :key="idx">
      Epoch {{ idx + 1 }}: Train={{ loss.toFixed(4) }}
      <span v-if="detailItem.model_metrics.val_loss_per_epoch?.[idx]">
        Val={{ detailItem.model_metrics.val_loss_per_epoch[idx].toFixed(4) }}
      </span>
    </div>
  </div>
  <div v-else class="text-caption text-medium-emphasis">
    仅 LSTM 模型记录训练 Loss
  </div>
</v-window-item>
```

---

## 5. 数据兼容性

| 影响范围 | 兼容性方案 |
|----------|------------|
| 旧训练记录 | 完全兼容，新字段为可选 |
| 保存的模型 | 无需迁移，模型结构未变（仅 forward 逻辑改变） |
| API 接口 | 向前兼容，新增字段可选 |

---

## 6. 验收标准

1. ✅ 修复双重 softmax 问题，模型输出 logits
2. ✅ 预测概率不再极端，分布更加平滑
3. ✅ 训练过程中显示验证 loss 和早停信息
4. ✅ 前端根据模型类型显示对应的标签页
5. ✅ 前端正确展示早停状态
6. ✅ 所有相关测试通过

---

## 7. 文件清单

### 后端文件

| 文件路径 | 修改类型 |
|----------|----------|
| [classifier.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/models/lstm/classifier.py) | ✅ 主要修改 |
| [config.py](file:///d:/projects/trade-alpha/backend/src/trade-alpha/models/training/config.py) | ✅ 新增配置 |
| [model_configs.py](file:///d:/projects/trade-alpha/backend/src/trade-alpha/api/routers/model_configs.py) | ✅ 更新 API |

### 前端文件

| 文件路径 | 修改类型 |
|----------|----------|
| [trainingRecord.ts](file:///d:/projects/trade-alpha/frontend/src/api/trainingRecord.ts) | ✅ 更新类型 |
| [TrainingRecordsView.vue](file:///d:/projects/trade-alpha/frontend/src/views/TrainingRecordsView.vue) | ✅ 更新 UI |

---

## 8. 实施计划

1. 后端：修改 classifier.py，修复双重 softmax + 添加早停
2. 后端：更新配置和 API
3. 前端：更新类型和 UI
4. 测试：运行集成测试
5. 验证：手动测试 LSTM 训练和预测
