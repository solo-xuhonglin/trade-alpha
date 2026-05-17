# 模型配置表单重构 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 前后端对齐模型配置字段，编辑不再报错，支持 xgboost 超参数的存储与编辑

**Architecture:** ModelConfig DAO 新增 6 个 xgb 超参数字段 → config_service 透传 → API 路由增删改查响应包含这些字段 → 训练时从 config 读取传给 XGBoostClassifier → 前端重写接口和表单

**Tech Stack:** Python/Beanie/FastAPI (backend), Vue 3/Vuetify/TypeScript (frontend)

---

### Task 1: ModelConfig DAO — 新增 xgboost 超参数字段

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\dao\model_config.py`

- [ ] **向 ModelConfig 添加 6 个 xgboost 超参数字段**

在 `feature_fields` 字段定义之后添加：

```python
    # xgboost 超参数（仅 model_type="xgboost" 时使用）
    xgb_n_estimators: int = 100
    xgb_max_depth: int = 6
    xgb_learning_rate: float = 0.1
    xgb_min_child_weight: int = 1
    xgb_subsample: float = 1.0
    xgb_colsample_bytree: float = 1.0
```

插入位置：在 `classification_threshold: float = 0.02` 之后、`created_at` 之前。

---

### Task 2: config_service.py — 透传 xgboost 超参数

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\predict\config_service.py`

- [ ] **update_config 函数签名和调用处新增 xgb 参数**

```python
async def create_config(
    name: str,
    model_type: str,
    feature_fields: Optional[List[str]] = None,
    standardize_fields: Optional[List[str]] = None,
    winsorize_fields: Optional[List[str]] = None,
    output_fields: Optional[List[str]] = None,
    classification_horizons: Optional[List[int]] = None,
    classification_threshold: float = 0.02,
    xgb_n_estimators: int = 100,
    xgb_max_depth: int = 6,
    xgb_learning_rate: float = 0.1,
    xgb_min_child_weight: int = 1,
    xgb_subsample: float = 1.0,
    xgb_colsample_bytree: float = 1.0,
) -> ModelConfig:
```

在创建 `ModelConfig` 实例时添加这些参数：

```python
    config = ModelConfig(
        name=name,
        model_type=model_type,
        feature_fields=feature_fields,
        standardize_fields=standardize_fields,
        winsorize_fields=winsorize_fields,
        output_fields=output_fields,
        classification_horizons=classification_horizons,
        classification_threshold=classification_threshold,
        xgb_n_estimators=xgb_n_estimators,
        xgb_max_depth=xgb_max_depth,
        xgb_learning_rate=xgb_learning_rate,
        xgb_min_child_weight=xgb_min_child_weight,
        xgb_subsample=xgb_subsample,
        xgb_colsample_bytree=xgb_colsample_bytree,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
```

`update_config` 函数无需改动——它使用 `setattr(config, key, value)` 动态更新，只要 kwargs 中包含 xgb 字段名就会自动赋值。

---

### Task 3: API 路由 — 请求/响应添加 xgboost 超参数字段

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\api\routers\model_configs.py`

- [ ] **ConfigCreate Pydantic 模型添加 xgb 字段**

```python
class ConfigCreate(BaseModel):
    name: str
    model_type: str
    feature_fields: Optional[List[str]] = None
    standardize_fields: Optional[List[str]] = None
    winsorize_fields: Optional[List[str]] = None
    output_fields: Optional[List[str]] = None
    classification_horizons: Optional[List[int]] = None
    classification_threshold: Optional[float] = None
    xgb_n_estimators: Optional[int] = None
    xgb_max_depth: Optional[int] = None
    xgb_learning_rate: Optional[float] = None
    xgb_min_child_weight: Optional[int] = None
    xgb_subsample: Optional[float] = None
    xgb_colsample_bytree: Optional[float] = None
```

- [ ] **ConfigUpdate Pydantic 模型添加 xgb 字段（同上但全部 Optional）**

```python
class ConfigUpdate(BaseModel):
    name: Optional[str] = None
    feature_fields: Optional[List[str]] = None
    standardize_fields: Optional[List[str]] = None
    winsorize_fields: Optional[List[str]] = None
    output_fields: Optional[List[str]] = None
    classification_horizons: Optional[List[int]] = None
    classification_threshold: Optional[float] = None
    xgb_n_estimators: Optional[int] = None
    xgb_max_depth: Optional[int] = None
    xgb_learning_rate: Optional[float] = None
    xgb_min_child_weight: Optional[int] = None
    xgb_subsample: Optional[float] = None
    xgb_colsample_bytree: Optional[float] = None
```

- [ ] **create_config 端点：把 xgb 参数传给 service**

```python
@router.post("")
async def create_config(body: ConfigCreate):
    try:
        c = await config_service.create_config(
            name=body.name,
            model_type=body.model_type,
            feature_fields=body.feature_fields,
            standardize_fields=body.standardize_fields,
            winsorize_fields=body.winsorize_fields,
            output_fields=body.output_fields,
            classification_horizons=body.classification_horizons,
            classification_threshold=body.classification_threshold or 0.02,
            xgb_n_estimators=body.xgb_n_estimators or 100,
            xgb_max_depth=body.xgb_max_depth or 6,
            xgb_learning_rate=body.xgb_learning_rate or 0.1,
            xgb_min_child_weight=body.xgb_min_child_weight or 1,
            xgb_subsample=body.xgb_subsample or 1.0,
            xgb_colsample_bytree=body.xgb_colsample_bytree or 1.0,
        )
        return { ... }  # 现有逻辑
```

- [ ] **所有 API 响应（create/list/get/update）中添加 xgb 字段**

在每个 `return {` 字典中添加：
```python
            "xgb_n_estimators": c.xgb_n_estimators,
            "xgb_max_depth": c.xgb_max_depth,
            "xgb_learning_rate": c.xgb_learning_rate,
            "xgb_min_child_weight": c.xgb_min_child_weight,
            "xgb_subsample": c.xgb_subsample,
            "xgb_colsample_bytree": c.xgb_colsample_bytree,
```

4 个端点（create、list、get、update）都需要加。delete 不需要。

---

### Task 4: training_service.py — 从 config 读取 xgb 超参数

**Files:**
- Modify: `d:\projects\trade-alpha\backend\src\trade_alpha\predict\training_service.py` (line 136)

- [ ] **create_training 中实例化 XGBoostClassifier 时传入 config 的超参数**

从第 136 行：
```python
    classifier = CLASSIFIERS[config.model_type]()
```

改为：
```python
    if config.model_type == "xgboost":
        classifier = XGBoostClassifier(
            n_estimators=config.xgb_n_estimators,
            max_depth=config.xgb_max_depth,
            learning_rate=config.xgb_learning_rate,
            min_child_weight=config.xgb_min_child_weight,
            subsample=config.xgb_subsample,
            colsample_bytree=config.xgb_colsample_bytree,
        )
    else:
        classifier = CLASSIFIERS[config.model_type]()
```

---

### Task 5: 前端 API 接口 — 重写 ModelConfig

**Files:**
- Modify: `d:\projects\trade-alpha\frontend\src\api\model.ts`

- [ ] **完全替换 ModelConfig 接口和 create 方法调用**

```typescript
import api from './index'

export interface ModelConfig {
  id: string
  name: string
  model_type: string
  feature_fields: string[]
  standardize_fields: string[]
  winsorize_fields: string[]
  output_fields: string[]
  classification_horizons: number[]
  classification_threshold: number
  xgb_n_estimators: number
  xgb_max_depth: number
  xgb_learning_rate: number
  xgb_min_child_weight: number
  xgb_subsample: number
  xgb_colsample_bytree: number
  created_at?: string
  updated_at?: string
}

export const modelApi = {
  list: (modelType?: string) => {
    const params = modelType ? { model_type: modelType } : {}
    return api.get<ModelConfig[]>('/model-configs', { params })
  },
  get: (id: string) => api.get<ModelConfig>(`/model-configs/${id}`),
  create: (data: Partial<ModelConfig>) => api.post<ModelConfig>('/model-configs', data),
  update: (id: string, data: Partial<ModelConfig>) => api.put(`/model-configs/${id}`, data),
  delete: (id: string) => api.delete(`/model-configs/${id}`),
}
```

---

### Task 6: 前端 ModelsView.vue — 重新设计表单

**Files:**
- Modify: `d:\projects\trade-alpha\frontend\src\views\ModelsView.vue`

- [ ] **替换模板中的表单部分为新的网格布局**

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
        {{ item.feature_fields.slice(0, 4).join(', ') }}{{ item.feature_fields.length > 4 ? ' ...' : '' }}
      </template>
      <template v-slot:item.classification_horizons="{ item }">
        {{ item.classification_horizons.map((h: number) => h + '日').join(', ') }}
      </template>
      <template v-slot:item.actions="{ item }">
        <div class="d-flex ga-1 justify-end">
          <v-btn size="small" variant="text" prepend-icon="mdi-pencil" @click="openDialog(item)">编辑</v-btn>
          <v-btn size="small" variant="text" color="error" prepend-icon="mdi-delete" @click="confirmDelete(item)">删除</v-btn>
        </div>
      </template>
    </v-data-table>
  </v-card>

  <v-dialog v-model="dialog" max-width="800px">
    <v-card :title="editingId ? '编辑配置' : '新建配置'">
      <template v-slot:text>
        <!-- 基本信息 -->
        <v-row>
          <v-col cols="12" sm="6">
            <v-text-field v-model="form.name" label="配置名称"></v-text-field>
          </v-col>
          <v-col cols="12" sm="6">
            <v-select v-model="form.model_type" :items="['xgboost', 'lstm']" label="模型类型"></v-select>
          </v-col>
        </v-row>

        <!-- 特征与数据处理 -->
        <v-row>
          <v-col cols="12">
            <v-autocomplete
              v-model="form.feature_fields"
              :items="indicatorFields"
              label="特征字段"
              multiple
              chips
              closable-chips
              clearable
              hint="选择模型输入的技术指标特征"
              persistent-hint
            ></v-autocomplete>
          </v-col>
          <v-col cols="12">
            <v-autocomplete
              v-model="form.standardize_fields"
              :items="indicatorFields"
              label="标准化字段"
              multiple
              chips
              closable-chips
              clearable
              hint="需要 Z-score 标准化的字段（通常与特征字段相同）"
              persistent-hint
            ></v-autocomplete>
          </v-col>
          <v-col cols="12">
            <v-autocomplete
              v-model="form.winsorize_fields"
              :items="indicatorFields"
              label="缩尾字段"
              multiple
              chips
              closable-chips
              clearable
              hint="需要缩尾处理的字段（通常为空）"
              persistent-hint
            ></v-autocomplete>
          </v-col>
        </v-row>

        <!-- 训练标签参数 -->
        <v-row>
          <v-col cols="12" sm="6">
            <v-combobox
              v-model="form.classification_horizons"
              :items="[3, 5, 10, 20]"
              label="预测周期（日）"
              multiple
              chips
              closable-chips
              hint="未来 N 日的涨跌方向"
              persistent-hint
            ></v-combobox>
          </v-col>
          <v-col cols="12" sm="6">
            <v-text-field
              v-model.number="form.classification_threshold"
              label="涨跌阈值"
              type="number"
              step="0.01"
              hint="涨幅超过此值视为上涨，跌幅超过视为下跌（0.02 = 2%）"
              persistent-hint
            ></v-text-field>
          </v-col>
        </v-row>

        <!-- XGBoost 超参数 -->
        <template v-if="form.model_type === 'xgboost'">
          <v-divider class="my-3"></v-divider>
          <div class="text-subtitle-2 mb-2 text-medium-emphasis">XGBoost 超参数</div>
          <v-row>
            <v-col cols="12" sm="4">
              <v-text-field v-model.number="form.xgb_n_estimators" label="n_estimators" type="number"></v-text-field>
            </v-col>
            <v-col cols="12" sm="4">
              <v-text-field v-model.number="form.xgb_max_depth" label="max_depth" type="number"></v-text-field>
            </v-col>
            <v-col cols="12" sm="4">
              <v-text-field v-model.number="form.xgb_learning_rate" label="learning_rate" type="number" step="0.01"></v-text-field>
            </v-col>
            <v-col cols="12" sm="4">
              <v-text-field v-model.number="form.xgb_min_child_weight" label="min_child_weight" type="number"></v-text-field>
            </v-col>
            <v-col cols="12" sm="4">
              <v-text-field v-model.number="form.xgb_subsample" label="subsample" type="number" step="0.1"></v-text-field>
            </v-col>
            <v-col cols="12" sm="4">
              <v-text-field v-model.number="form.xgb_colsample_bytree" label="colsample_bytree" type="number" step="0.1"></v-text-field>
            </v-col>
          </v-row>
        </template>
      </template>
      <v-divider></v-divider>
      <v-card-actions class="bg-surface-light">
        <v-btn text="取消" variant="plain" @click="dialog = false"></v-btn>
        <v-spacer></v-spacer>
        <v-btn text="保存" @click="saveConfig"></v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 删除确认弹窗（不变） -->
  <v-dialog v-model="deleteDialog" max-width="400px">
    <v-card subtitle="此操作不可撤销" title="确认删除">
      <template v-slot:text>
        确定要删除配置「{{ deletingItem?.name }}」吗？
      </template>
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

- [ ] **替换 script setup 中的类型和逻辑**

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { modelApi, type ModelConfig } from '@/api/model'

const loading = ref(false)
const dialog = ref(false)
const deleteDialog = ref(false)
const models = ref<ModelConfig[]>([])
const editingId = ref<string | null>(null)
const deletingItem = ref<ModelConfig | null>(null)

const indicatorFields = [
  'ma_5', 'ma_10', 'ma_20', 'ma_60',
  'macd', 'macd_signal', 'macd_hist',
  'pct_chg',
  'bias_5', 'bias_10', 'bias_20', 'bias_60',
  'close_pct_rank_5', 'close_pct_rank_10', 'close_pct_rank_20', 'close_pct_rank_60',
  'vol_ratio_5', 'vol_ratio_10', 'vol_ratio_20', 'vol_ratio_60',
  'kdj_k', 'kdj_d', 'kdj_j',
  'boll_upper', 'boll_middle', 'boll_lower',
]

const defaultForm = {
  name: '',
  model_type: 'xgboost' as string,
  feature_fields: [...indicatorFields],
  standardize_fields: [...indicatorFields],
  winsorize_fields: [] as string[],
  classification_horizons: [3, 5],
  classification_threshold: 0.02,
  xgb_n_estimators: 100,
  xgb_max_depth: 6,
  xgb_learning_rate: 0.1,
  xgb_min_child_weight: 1,
  xgb_subsample: 1.0,
  xgb_colsample_bytree: 1.0,
}

const form = ref({ ...defaultForm })

const headers = [
  { title: '名称', key: 'name' },
  { title: '模型类型', key: 'model_type' },
  { title: '特征字段', key: 'feature_fields' },
  { title: '预测周期', key: 'classification_horizons' },
  { title: '涨跌阈值', key: 'classification_threshold' },
  { title: '操作', key: 'actions', sortable: false, align: 'end' as const },
]

const loadModels = async () => {
  loading.value = true
  try {
    const res = await modelApi.list()
    models.value = res.data
  } finally {
    loading.value = false
  }
}

const openDialog = (item?: ModelConfig) => {
  if (item) {
    editingId.value = item.id
    form.value = {
      name: item.name,
      model_type: item.model_type,
      feature_fields: [...item.feature_fields],
      standardize_fields: [...item.standardize_fields],
      winsorize_fields: [...item.winsorize_fields],
      classification_horizons: [...item.classification_horizons],
      classification_threshold: item.classification_threshold,
      xgb_n_estimators: item.xgb_n_estimators,
      xgb_max_depth: item.xgb_max_depth,
      xgb_learning_rate: item.xgb_learning_rate,
      xgb_min_child_weight: item.xgb_min_child_weight,
      xgb_subsample: item.xgb_subsample,
      xgb_colsample_bytree: item.xgb_colsample_bytree,
    }
  } else {
    editingId.value = null
    form.value = {
      name: 'new_config',
      model_type: 'xgboost',
      feature_fields: [...indicatorFields],
      standardize_fields: [...indicatorFields],
      winsorize_fields: [],
      classification_horizons: [3, 5],
      classification_threshold: 0.02,
      xgb_n_estimators: 100,
      xgb_max_depth: 6,
      xgb_learning_rate: 0.1,
      xgb_min_child_weight: 1,
      xgb_subsample: 1.0,
      xgb_colsample_bytree: 1.0,
    }
  }
  dialog.value = true
}

const saveConfig = async () => {
  if (editingId.value) {
    await modelApi.update(editingId.value, form.value)
  } else {
    await modelApi.create(form.value)
  }
  dialog.value = false
  await loadModels()
}

const confirmDelete = (item: ModelConfig) => {
  deletingItem.value = item
  deleteDialog.value = true
}

const deleteConfig = async () => {
  if (!deletingItem.value) return
  await modelApi.delete(deletingItem.value.id)
  deleteDialog.value = false
  deletingItem.value = null
  await loadModels()
}

onMounted(() => {
  loadModels()
})
</script>
```

- [ ] **headers 移除 targets/params 列，新增 feature_fields/classification_horizons/classification_threshold 列**

已在上面代码中包含。

---

### Task 7: 运行后端测试验证

**Files:**
- Test: Backend integration tests

- [ ] **运行 model config service 测试**

Run from `d:\projects\trade-alpha\backend`:
```powershell
cd d:\projects\trade-alpha\backend
pytest tests/trade_alpha/integration/test_42_model_config_service.py -v
```

Expected: 6 tests passed (test_create_config, test_create_duplicate_config, test_list_configs, test_update_config, test_delete_config, test_ensure_default_config)

- [ ] **运行 training service 测试**（验证训练流程兼容新增字段）

```powershell
cd d:\projects\trade-alpha\backend
pytest tests/trade_alpha/integration/test_51_training_service.py -v
```

Expected: 5 tests passed

- [ ] **前端构建验证**

Run from `d:\projects\trade-alpha\frontend`:
```powershell
cd d:\projects\trade-alpha\frontend
npm run build
```

Expected: Build succeeds with no type errors.
