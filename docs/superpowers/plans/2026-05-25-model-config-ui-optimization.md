# 模型配置弹窗 UI 优化 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化模型配置弹窗，包括标签页分组、参数提示文本、不同模型的差异化默认值。

**Architecture:** 单文件修改，在现有的 `ModelConfigView.vue` 组件中重构 UI 结构。

**Tech Stack:** Vue 3, Vuetify 3

---

## 文件结构映射

| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/src/views/ModelConfigView.vue` | 修改 | 重构整个组件，添加标签页、参数提示、差异化默认值 |

---

## 任务分解

### Task 1: 新增常量和调整默认值

**Files:**
- Modify: `frontend/src/views/ModelConfigView.vue`

- [ ] **Step 1: 添加受价格影响的字段常量**

在 `lstmRecommendedFeatureFields` 之后添加：
```javascript
// 受价格绝对值影响的字段（LSTM 需要标准化）
const lstmAffectedByPriceFields = [
  'ma_5', 'ma_10', 'ma_20', 'ma_60',
  'macd', 'macd_signal', 'macd_hist',
  'boll_upper', 'boll_middle', 'boll_lower'
]
```

- [ ] **Step 2: 更新 `lstmRecommendedParams` 的默认值**

修改 `lstmRecommendedParams`，使用新的字段列表：
```javascript
const lstmRecommendedParams = {
  feature_fields: [...lstmRecommendedFeatureFields],
  standardize_fields: [...lstmAffectedByPriceFields],
  winsorize_fields: [...lstmAffectedByPriceFields],
  lstm_hidden_size: 64,
  lstm_num_layers: 2,
  lstm_dropout: 0.2,
  lstm_epochs: 50,
  lstm_batch_size: 256,
  lstm_learning_rate: 0.001,
  lstm_sequence_length: 60,
  lstm_normalization_window: 300,
  early_stopping_patience: 10,
}
```

- [ ] **Step 3: 确保 `openDialog` 编辑时加载 `early_stopping_patience`**

检查 `openDialog` 函数，确保从 item 中正确加载该字段（之前已经有了，确认一下即可）

---

### Task 2: 重构模板 - 添加标签页结构

**Files:**
- Modify: `frontend/src/views/ModelConfigView.vue:42-145`

- [ ] **Step 1: 增加弹窗宽度**

将 `max-width="800px"` 改为 `max-width="900px"`

- [ ] **Step 2: 重构模板内容**

将原来的内容替换为标签页结构：
```vue
<template>
  <v-card border rounded>
    <v-data-table :headers="headers" :items="models" :loading="loading">
      <template v-slot:top>
        <v-toolbar flat>
          <v-toolbar-title>
            <v-icon color="medium-emphasis" icon="mdi-brain" size="x-small" start></v-icon>
            模型配置
          </v-toolbar-title>
          <v-btn prepend-icon="mdi-plus" rounded="lg" text="新建配置" border @click="openDialog()"></v-btn>
        </v-toolbar>
      </template>
      <template v-slot:item.feature_fields="{ item }">
        <v-chip-group>
          <v-chip v-for="f in item.feature_fields.slice(0, 3)" :key="f" size="x-small" variant="outlined">
            {{ f }}
          </v-chip>
          <v-chip v-if="item.feature_fields.length > 3" size="x-small" variant="tonal">
            +{{ item.feature_fields.length - 3 }}
          </v-chip>
        </v-chip-group>
      </template>
      <template v-slot:item.classification_horizons="{ item }">
        <v-chip-group>
          <v-chip v-for="h in item.classification_horizons" :key="h" size="x-small" variant="outlined">
            {{ h }}日
          </v-chip>
        </v-chip-group>
      </template>
      <template v-slot:item.created_at="{ item }">
        {{ formatDate(item.created_at) }}
      </template>
      <template v-slot:item.actions="{ item }">
        <div class="d-flex ga-1 justify-end">
          <v-btn size="small" variant="text" prepend-icon="mdi-pencil" @click="openDialog(item)">编辑</v-btn>
          <v-btn size="small" variant="text" color="error" prepend-icon="mdi-delete" @click="confirmDelete(item)">删除</v-btn>
        </div>
      </template>
    </v-data-table>
  </v-card>

  <v-dialog v-model="dialog" max-width="900px">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center">
        {{ editingId ? '编辑配置' : '新建配置' }}
        <v-btn icon variant="text" size="small" @click="dialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>
        <v-row>
          <v-col cols="12" sm="6">
            <v-select v-model="form.model_type" :items="['xgboost', 'lstm']" label="模型类型"></v-select>
          </v-col>
          <v-col cols="12" sm="6">
            <v-text-field v-model="form.name" label="配置名称"></v-text-field>
          </v-col>
        </v-row>

        <v-tabs v-model="activeTab">
          <v-tab value="fields">字段配置</v-tab>
          <v-tab value="params">参数配置</v-tab>
          <v-window v-model="activeTab">
            <!-- 标签页 1: 字段配置 -->
            <v-window-item value="fields">
              <div class="pt-4">
                <v-row>
                  <v-col cols="12">
                    <v-autocomplete v-model="form.feature_fields" :items="allFeatureFields" label="特征字段" multiple chips closable-chips dense></v-autocomplete>
                  </v-col>
                </v-row>
                <v-row>
                  <v-col cols="12" sm="6">
                    <v-autocomplete v-model="form.standardize_fields" :items="allFeatureFields" label="标准化字段" multiple chips closable-chips dense></v-autocomplete>
                  </v-col>
                  <v-col cols="12" sm="6">
                    <v-autocomplete v-model="form.winsorize_fields" :items="allFeatureFields" label="缩尾字段" multiple chips closable-chips dense></v-autocomplete>
                  </v-col>
                </v-row>
              </div>
            </v-window-item>
            <!-- 标签页 2: 参数配置 -->
            <v-window-item value="params">
              <div class="pt-4">
                <v-divider class="mb-4"></v-divider>
                <div class="text-subtitle-2 text-medium-emphasis mb-2">训练标签参数</div>
                <v-row>
                  <v-col cols="12" sm="6">
                    <v-combobox v-model="form.classification_horizons" :items="[1, 2, 3, 5, 10, 20]" label="预测周期" multiple chips small-chips></v-combobox>
                  </v-col>
                  <v-col cols="12" sm="6">
                    <v-text-field v-model.number="form.classification_threshold" label="涨跌阈值" type="number" step="0.01"></v-text-field>
                  </v-col>
                </v-row>

                <template v-if="form.model_type === 'xgboost'">
                  <v-divider class="my-4"></v-divider>
                  <div class="text-subtitle-2 text-medium-emphasis mb-2">XGBoost 超参数</div>
                  <v-row>
                    <v-col cols="12" sm="6">
                      <v-text-field v-model.number="form.xgb_n_estimators" label="n_estimators" type="number" helper-text="树的数量，值越大越准确但越慢" persistent-helper></v-text-field>
                    </v-col>
                    <v-col cols="12" sm="6">
                      <v-text-field v-model.number="form.xgb_max_depth" label="max_depth" type="number" helper-text="树的最大深度，控制复杂度" persistent-helper></v-text-field>
                    </v-col>
                    <v-col cols="12" sm="6">
                      <v-text-field v-model.number="form.xgb_min_child_weight" label="min_child_weight" type="number" step="0.1" helper-text="叶子节点最小权重和" persistent-helper></v-text-field>
                    </v-col>
                    <v-col cols="12" sm="6">
                      <v-text-field v-model.number="form.xgb_learning_rate" label="learning_rate" type="number" step="0.01" helper-text="每棵树的贡献权重" persistent-helper></v-text-field>
                    </v-col>
                    <v-col cols="12" sm="6">
                      <v-text-field v-model.number="form.xgb_subsample" label="subsample" type="number" step="0.1" helper-text="训练样本采样比例" persistent-helper></v-text-field>
                    </v-col>
                    <v-col cols="12" sm="6">
                      <v-text-field v-model.number="form.xgb_colsample_bytree" label="colsample_bytree" type="number" step="0.1" helper-text="特征采样比例" persistent-helper></v-text-field>
                    </v-col>
                  </v-row>
                </template>

                <template v-if="form.model_type === 'lstm'">
                  <v-divider class="my-4"></v-divider>
                  <div class="text-subtitle-2 text-medium-emphasis mb-2">LSTM 超参数</div>
                  <v-row>
                    <v-col cols="12" sm="6">
                      <v-text-field v-model.number="form.lstm_hidden_size" label="hidden_size" type="number" helper-text="隐藏层维度，控制模型容量" persistent-helper></v-text-field>
                    </v-col>
                    <v-col cols="12" sm="6">
                      <v-text-field v-model.number="form.lstm_num_layers" label="num_layers" type="number" helper-text="LSTM 层数" persistent-helper></v-text-field>
                    </v-col>
                    <v-col cols="12" sm="6">
                      <v-text-field v-model.number="form.lstm_dropout" label="dropout" type="number" step="0.1" helper-text="Dropout 比例，防止过拟合" persistent-helper></v-text-field>
                    </v-col>
                    <v-col cols="12" sm="6">
                      <v-text-field v-model.number="form.lstm_sequence_length" label="sequence_length" type="number" helper-text="输入序列长度（天数）" persistent-helper></v-text-field>
                    </v-col>
                    <v-col cols="12" sm="6">
                      <v-text-field v-model.number="form.lstm_normalization_window" label="normalization_window" type="number" helper-text="标准化统计窗口（天数）" persistent-helper></v-text-field>
                    </v-col>
                    <v-col cols="12" sm="6">
                      <v-text-field v-model.number="form.lstm_epochs" label="epochs" type="number" helper-text="最大训练轮数" persistent-helper></v-text-field>
                    </v-col>
                    <v-col cols="12" sm="6">
                      <v-text-field v-model.number="form.lstm_batch_size" label="batch_size" type="number" helper-text="每批训练样本数" persistent-helper></v-text-field>
                    </v-col>
                    <v-col cols="12" sm="6">
                      <v-text-field v-model.number="form.lstm_learning_rate" label="learning_rate" type="number" step="0.001" helper-text="学习率" persistent-helper></v-text-field>
                    </v-col>
                    <v-col cols="12" sm="6">
                      <v-text-field v-model.number="form.early_stopping_patience" label="early_stopping_patience" type="number" helper-text="验证 AUC 不提升时停止的轮数" persistent-helper></v-text-field>
                    </v-col>
                  </v-row>
                </template>
              </div>
            </v-window-item>
          </v-window>
        </v-tabs>
      </v-card-text>
      <v-divider></v-divider>
      <v-card-actions class="bg-surface-light">
        <v-btn text="取消" variant="plain" @click="dialog = false"></v-btn>
        <v-spacer></v-spacer>
        <v-btn text="保存" @click="saveConfig"></v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="deleteDialog" max-width="400px">
    <v-card>
      <v-card-title class="text-h6 d-flex justify-space-between align-center">
        确认删除
        <v-btn icon variant="text" size="small" @click="deleteDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>此操作不可撤销，确定要删除配置「{{ deletingItem?.name }}」吗？</v-card-text>
      <v-divider></v-divider>
      <v-card-actions class="bg-surface-light">
        <v-btn text="取消" variant="plain" @click="deleteDialog = false"></v-btn>
        <v-spacer></v-spacer>
        <v-btn text="删除" color="error" @click="deleteConfig"></v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
```

---

### Task 3: 更新 script 部分

**Files:**
- Modify: `frontend/src/views/ModelConfigView.vue:170-400`

- [ ] **Step 1: 添加 `activeTab` 状态**

在 `const dialog = ref(false)` 后面添加：
```javascript
const activeTab = ref('fields')
```

- [ ] **Step 2: 更新 `defaultForm`**

确保 `defaultForm` 包含 `early_stopping_patience`（之前已有）

- [ ] **Step 3: 重置 `activeTab` 当打开弹窗时**

在 `openDialog` 函数开头添加：
```javascript
activeTab.value = 'fields'
```

---

### Task 4: 测试和验证

**Files:**
- 无需修改，运行测试

- [ ] **Step 1: 运行项目**

运行前端开发服务器：
```bash
cd frontend
npm run dev
```

- [ ] **Step 2: 手动测试功能**

1. 打开模型配置页面
2. 点击"新建配置"
3. 选择 `xgboost`，检查默认字段和参数
4. 切换标签页，确认内容正确
5. 选择 `lstm`，检查默认字段（标准化/缩尾只包含受价格影响的字段）
6. 保存配置
7. 编辑刚保存的配置，确认所有值正确加载
8. 删除配置

---

### Task 5: 提交更改

**Files:**
- 所有修改的文件

- [ ] **Step 1: 提交代码**

```bash
git add frontend/src/views/ModelConfigView.vue docs/superpowers/specs/2026-05-25-model-config-ui-optimization.md docs/superpowers/plans/2026-05-25-model-config-ui-optimization.md
git commit -m "feat: optimize model config dialog with tabs and parameter hints"
```

---

## 自审检查

### 1. Spec 覆盖检查
- ✅ 标签页分组 - Task 2
- ✅ 参数提示文本 - Task 2
- ✅ 差异化默认值 - Task 1
- ✅ 弹窗宽度增加 - Task 2
- ✅ 参数顺序调整 - Task 2

### 2. 占位符检查
- ✅ 无 TBD/TODO
- ✅ 所有步骤包含完整代码

### 3. 类型一致性检查
- ✅ 所有字段名与现有代码一致
- ✅ `early_stopping_patience` 正确加载

---

## 执行选项

Plan complete and saved to `docs/superpowers/plans/2026-05-25-model-config-ui-optimization.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
