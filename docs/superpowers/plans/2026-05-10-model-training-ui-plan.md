# 模型配置和训练页面实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 trade-alpha 前端新增模型配置和训练管理页面

**Architecture:** 遵循现有前端架构，使用 Vue 3 + Vuetify 4 + TypeScript，新建两个页面（/models, /trainings）和对应的 API 客户端模块

**Tech Stack:** Vue 3, Vuetify 4, TypeScript, Axios

---

## 文件结构

```
frontend/src/
├── api/
│   ├── models.ts          # 新建：模型配置 API
│   └── trainings.ts        # 新建：训练 API
├── views/
│   ├── ModelsView.vue     # 新建：模型配置页面
│   └── TrainingsView.vue   # 新建：训练页面
├── router/
│   └── index.ts           # 修改：添加路由
└── components/
    └── AppLayout.vue      # 修改：添加菜单项
```

---

### Task 1: 创建 API 客户端 - models.ts

**Files:**
- Create: `frontend/src/api/models.ts`
- Reference: `frontend/src/api/strategy.ts` (existing pattern)

- [ ] **Step 1: Write models.ts**

```typescript
import api from './index'

export interface ModelConfig {
  id: string
  name: string
  model_type: 'linear' | 'xgboost' | 'lstm'
  params: Record<string, any>
  targets: string[]
}

export const modelsApi = {
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

- [ ] **Step 2: 测试文件存在性**

Run: `ls frontend/src/api/models.ts`
Expected: models.ts exists

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/models.ts
git commit -m "feat: add models API client"
```

---

### Task 2: 创建 API 客户端 - trainings.ts

**Files:**
- Create: `frontend/src/api/trainings.ts`

- [ ] **Step 1: Write trainings.ts**

```typescript
import api from './index'

export interface Training {
  id: string
  config_id: string
  name: string
  ts_codes: string[]
  start_date: string
  end_date: string
  metrics: {
    open_mse?: number
    open_mae?: number
    close_mse?: number
    close_mae?: number
    high_mse?: number
    high_mae?: number
    low_mse?: number
    low_mae?: number
    sample_count: number
  }
}

export interface PredictResult {
  predictions: Record<string, number>
}

export const trainingsApi = {
  list: (configId?: string) => {
    const params = configId ? { config_id: configId } : {}
    return api.get<Training[]>('/trainings', { params })
  },
  get: (id: string) => api.get<Training>(`/trainings/${id}`),
  create: (data: {
    config_id: string
    name: string
    ts_codes: string[]
    start_date: string
    end_date: string
  }) => api.post<Training>('/trainings', data),
  delete: (id: string) => api.delete(`/trainings/${id}`),
  predict: (id: string, tsCode?: string) => {
    const data = tsCode ? { ts_code: tsCode } : {}
    return api.post<PredictResult>(`/trainings/${id}/predict`, data)
  },
}
```

- [ ] **Step 2: 测试文件存在性**

Run: `ls frontend/src/api/trainings.ts`
Expected: trainings.ts exists

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/trainings.ts
git commit -m "feat: add trainings API client"
```

---

### Task 3: 更新路由配置

**Files:**
- Modify: `frontend/src/router/index.ts:1-40`

- [ ] **Step 1: 添加新路由**

在 routes 数组中添加：

```typescript
{
  path: '/models',
  name: 'Models',
  component: () => import('@/views/ModelsView.vue')
},
{
  path: '/trainings',
  name: 'Trainings',
  component: () => import('@/views/TrainingsView.vue')
}
```

- [ ] **Step 2: 测试路由配置**

Run: 检查 router/index.ts 是否包含 /models 和 /trainings 路由

- [ ] **Step 3: Commit**

```bash
git add frontend/src/router/index.ts
git commit -m "feat: add /models and /trainings routes"
```

---

### Task 4: 更新菜单配置

**Files:**
- Modify: `frontend/src/components/AppLayout.vue:36-42`

- [ ] **Step 1: 添加菜单项**

在 menuItems 数组中添加：

```typescript
{ path: '/models', title: '模型管理', icon: 'mdi-brain' },
{ path: '/trainings', title: '训练记录', icon: 'mdi-chart-scatter-plot' },
```

- [ ] **Step 2: 测试菜单渲染**

确认 AppLayout 包含新增的菜单项

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/AppLayout.vue
git commit -m "feat: add models and trainings menu items"
```

---

### Task 5: 创建模型配置页面 - ModelsView.vue

**Files:**
- Create: `frontend/src/views/ModelsView.vue`
- Reference: `frontend/src/views/StrategyView.vue` (existing pattern)

- [ ] **Step 1: Write ModelsView.vue**

页面结构：
- v-data-table 显示配置列表
- 创建/编辑对话框（名称、模型类型、目标、参数）
- 训练对话框（名称、股票多选、日期范围）
- 支持 linear/xgboost/lstm 三种类型

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
      <template v-slot:item.params="{ item }">
        <code>{{ JSON.stringify(item.params) }}</code>
      </template>
      <template v-slot:item.actions="{ item }">
        <div class="d-flex ga-2 justify-end">
          <v-btn size="small" variant="tonal" color="primary" @click="openTrainingDialog(item)">训练</v-btn>
          <v-icon color="medium-emphasis" icon="mdi-pencil" size="small" @click="openDialog(item)"></v-icon>
          <v-icon color="error" icon="mdi-delete" size="small" @click="confirmDelete(item)"></v-icon>
        </div>
      </template>
    </v-data-table>
  </v-card>

  <!-- 配置对话框 -->
  <v-dialog v-model="dialog" max-width="600px">
    <v-card :title="editingId ? '编辑配置' : '新建配置'">
      <v-card-text>
        <v-text-field v-model="form.name" label="配置名称"></v-text-field>
        <v-select v-model="form.model_type" :items="['linear', 'xgboost', 'lstm']" label="模型类型"></v-select>
        <v-select v-model="form.targets" :items="['open', 'close', 'high', 'low']" label="预测目标" multiple chips></v-select>
        <!-- 动态参数表单 -->
        <template v-if="form.model_type === 'linear'">
          <v-switch v-model="form.params.fit_intercept" label="fit_intercept" color="primary"></v-switch>
        </template>
        <template v-if="form.model_type === 'xgboost'">
          <v-text-field v-model.number="form.params.n_estimators" label="n_estimators" type="number"></v-text-field>
          <v-text-field v-model.number="form.params.max_depth" label="max_depth" type="number"></v-text-field>
          <v-text-field v-model.number="form.params.learning_rate" label="learning_rate" type="number" step="0.01"></v-text-field>
        </template>
        <template v-if="form.model_type === 'lstm'">
          <v-text-field v-model.number="form.params.epochs" label="epochs" type="number"></v-text-field>
          <v-text-field v-model.number="form.params.batch_size" label="batch_size" type="number"></v-text-field>
          <v-text-field v-model.number="form.params.units" label="units" type="number"></v-text-field>
        </template>
      </v-card-text>
      <v-card-actions>
        <v-btn text="取消" @click="dialog = false"></v-btn>
        <v-spacer></v-spacer>
        <v-btn text="保存" @click="saveConfig"></v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 训练对话框 -->
  <v-dialog v-model="trainingDialog" max-width="500px">
    <v-card title="创建训练">
      <v-card-text>
        <v-text-field v-model="trainingForm.name" label="训练名称"></v-text-field>
        <v-select v-model="trainingForm.ts_codes" :items="stockOptions" label="股票" multiple chips closable-chips></v-select>
        <v-text-field v-model="trainingForm.start_date" label="开始日期" placeholder="YYYYMMDD"></v-text-field>
        <v-text-field v-model="trainingForm.end_date" label="结束日期" placeholder="YYYYMMDD"></v-text-field>
      </v-card-text>
      <v-card-actions>
        <v-btn text="取消" @click="trainingDialog = false"></v-btn>
        <v-spacer></v-spacer>
        <v-btn text="开始训练" color="primary" @click="startTraining" :loading="training"></v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 删除确认对话框 -->
  <v-dialog v-model="deleteDialog" max-width="400px">
    <v-card title="确认删除">
      <v-card-text>确定要删除配置「{{ deletingItem?.name }}」吗？</v-card-text>
      <v-card-actions>
        <v-btn text="取消" @click="deleteDialog = false"></v-btn>
        <v-spacer></v-spacer>
        <v-btn text="删除" color="error" @click="deleteConfig"></v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { modelsApi, type ModelConfig } from '@/api/models'

const loading = ref(false)
const dialog = ref(false)
const trainingDialog = ref(false)
const deleteDialog = ref(false)
const training = ref(false)
const models = ref<ModelConfig[]>([])
const stockOptions = ref<string[]>([])
const editingId = ref<string | null>(null)
const deletingItem = ref<ModelConfig | null>(null)

const form = ref({
  name: '',
  model_type: 'linear',
  targets: ['open', 'close'] as string[],
  params: {} as Record<string, any>,
})

const trainingForm = ref({
  name: '',
  ts_codes: [] as string[],
  start_date: '20230101',
  end_date: '20231231',
})

const defaultParams: Record<string, Record<string, any>> = {
  linear: { fit_intercept: true },
  xgboost: { n_estimators: 100, max_depth: 5, learning_rate: 0.1 },
  lstm: { epochs: 50, batch_size: 32, units: 64 },
}

const headers = [
  { title: '名称', key: 'name' },
  { title: '模型类型', key: 'model_type' },
  { title: '预测目标', key: 'targets' },
  { title: '参数', key: 'params' },
  { title: '操作', key: 'actions', sortable: false, align: 'end' },
]

const loadModels = async () => {
  loading.value = true
  try {
    models.value = (await modelsApi.list()).data
  } finally {
    loading.value = false
  }
}

const loadStockOptions = async () => {
  stockOptions.value = (await import('@/api/data')).stockListApi.list()
    .then(res => res.data.map((s: any) => s.ts_code))
}

const openDialog = (item?: ModelConfig) => {
  if (item) {
    editingId.value = item.id
    form.value = { ...item }
  } else {
    editingId.value = null
    form.value = {
      name: 'new_config',
      model_type: 'linear',
      targets: ['open', 'close'],
      params: { ...defaultParams['linear'] },
    }
  }
  dialog.value = true
}

const openTrainingDialog = (item: ModelConfig) => {
  editingId.value = item.id
  trainingForm.value = {
    name: `${item.name}_training`,
    ts_codes: [],
    start_date: '20230101',
    end_date: '20231231',
  }
  loadStockOptions()
  trainingDialog.value = true
}

const saveConfig = async () => {
  if (editingId.value) {
    await modelsApi.update(editingId.value, form.value)
  } else {
    await modelsApi.create(form.value)
  }
  dialog.value = false
  await loadModels()
}

const startTraining = async () => {
  if (!editingId.value) return
  training.value = true
  try {
    await (await import('@/api/trainings')).trainingsApi.create({
      config_id: editingId.value,
      ...trainingForm.value,
    })
    trainingDialog.value = false
  } finally {
    training.value = false
  }
}

const confirmDelete = (item: ModelConfig) => {
  deletingItem.value = item
  deleteDialog.value = true
}

const deleteConfig = async () => {
  if (!deletingItem.value) return
  await modelsApi.delete(deletingItem.value.id)
  deleteDialog.value = false
  deletingItem.value = null
  await loadModels()
}

onMounted(() => {
  loadModels()
})
</script>
```

- [ ] **Step 2: 测试页面文件**

Run: `ls frontend/src/views/ModelsView.vue`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/ModelsView.vue
git commit -m "feat: add ModelsView page for model config management"
```

---

### Task 6: 创建训练页面 - TrainingsView.vue

**Files:**
- Create: `frontend/src/views/TrainingsView.vue`
- Reference: `frontend/src/views/StrategyView.vue` (existing pattern)

- [ ] **Step 1: Write TrainingsView.vue**

页面结构：
- v-data-table 显示训练列表
- 工具栏包含配置筛选下拉框
- 每行有预测按钮
- 预测结果显示在对话框中

```vue
<template>
  <v-card border rounded>
    <v-toolbar flat>
      <v-toolbar-title>
        <v-icon color="medium-emphasis" icon="mdi-chart-scatter-plot" size="x-small" start></v-icon>
        训练记录
      </v-toolbar-title>
      <v-select
        v-model="filterConfig"
        :items="configOptions"
        label="按配置筛选"
        clearable
        hide-details
        style="max-width: 200px;"
        class="ml-4"
      ></v-select>
    </v-toolbar>
    <v-data-table :headers="headers" :items="trainings" :loading="loading">
      <template v-slot:item.ts_codes="{ item }">
        {{ item.ts_codes.join(', ') }}
      </template>
      <template v-slot:item.metrics="{ item }">
        <span v-for="target in item.targets" :key="target" class="mr-2">
          {{ target }}: {{ item.metrics[`${target}_mae`]?.toFixed(4) || '-' }}
        </span>
      </template>
      <template v-slot:item.actions="{ item }">
        <div class="d-flex ga-2 justify-end">
          <v-btn size="small" variant="tonal" color="primary" @click="openPredictDialog(item)">预测</v-btn>
          <v-icon color="error" icon="mdi-delete" size="small" @click="confirmDelete(item)"></v-icon>
        </div>
      </template>
    </v-data-table>
  </v-card>

  <!-- 预测对话框 -->
  <v-dialog v-model="predictDialog" max-width="500px">
    <v-card title="使用模型预测">
      <v-card-text>
        <v-select
          v-model="predictForm.ts_code"
          :items="stockOptions"
          label="股票代码（可选）"
          clearable
          hint="不选择则使用训练时的第一只股票"
          persistent-hint
        ></v-select>
        <v-alert v-if="predictions" type="success" class="mt-4">
          <div v-for="(value, key) in predictions" :key="key">
            {{ key }}: {{ value.toFixed(4) }}
          </div>
        </v-alert>
      </v-card-text>
      <v-card-actions>
        <v-btn text="关闭" @click="predictDialog = false"></v-btn>
        <v-spacer></v-spacer>
        <v-btn text="预测" color="primary" @click="runPredict" :loading="predicting"></v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 删除确认对话框 -->
  <v-dialog v-model="deleteDialog" max-width="400px">
    <v-card title="确认删除">
      <v-card-text>确定要删除训练「{{ deletingItem?.name }}」吗？</v-card-text>
      <v-card-actions>
        <v-btn text="取消" @click="deleteDialog = false"></v-btn>
        <v-spacer></v-spacer>
        <v-btn text="删除" color="error" @click="deleteTraining"></v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { trainingsApi, type Training } from '@/api/trainings'
import { modelsApi } from '@/api/models'

const loading = ref(false)
const predictDialog = ref(false)
const deleteDialog = ref(false)
const predicting = ref(false)
const trainings = ref<(Training & { targets: string[] })[]>([])
const configs = ref<{ id: string; name: string }[]>([])
const filterConfig = ref<string | null>(null)
const stockOptions = ref<string[]>([])
const predictions = ref<Record<string, number> | null>(null)
const deletingItem = ref<Training | null>(null)

const predictForm = ref({
  ts_code: null as string | null,
})

const headers = [
  { title: '名称', key: 'name' },
  { title: '配置', key: 'config_id' },
  { title: '股票', key: 'ts_codes' },
  { title: '日期范围', key: 'date_range' },
  { title: '样本数', key: 'sample_count' },
  { title: '指标(MAE)', key: 'metrics' },
  { title: '操作', key: 'actions', sortable: false, align: 'end' },
]

const configOptions = ref<{ title: string; value: string }[]>([])

const loadConfigs = async () => {
  const res = await modelsApi.list()
  configs.value = res.data.map(c => ({ id: c.id, name: c.name }))
  configOptions.value = configs.value.map(c => ({ title: c.name, value: c.id }))
}

const loadTrainings = async () => {
  loading.value = true
  try {
    const res = await trainingsApi.list(filterConfig.value || undefined)
    trainings.value = res.data.map(t => {
      const config = configs.value.find(c => c.id === t.config_id)
      const targets = res.data[0] ? ['open', 'close'] : []
      return {
        ...t,
        targets,
        config_id: config?.name || t.config_id,
        date_range: `${t.start_date} ~ ${t.end_date}`,
        sample_count: t.metrics.sample_count,
      }
    })
  } finally {
    loading.value = false
  }
}

const loadStockOptions = async () => {
  const { stockListApi } = await import('@/api/data')
  const res = await stockListApi.list()
  stockOptions.value = res.data.map((s: any) => s.ts_code)
}

const openPredictDialog = async (item: Training) => {
  predictForm.value.ts_code = null
  predictions.value = null
  if (stockOptions.value.length === 0) {
    await loadStockOptions()
  }
  predictDialog.value = true
}

const runPredict = async () => {
  if (!deletingItem.value) return
  predicting.value = true
  try {
    const res = await trainingsApi.predict(deletingItem.value.id, predictForm.value.ts_code || undefined)
    predictions.value = res.data.predictions
  } finally {
    predicting.value = false
  }
}

const confirmDelete = (item: Training) => {
  deletingItem.value = item
  deleteDialog.value = true
}

const deleteTraining = async () => {
  if (!deletingItem.value) return
  await trainingsApi.delete(deletingItem.value.id)
  deleteDialog.value = false
  deletingItem.value = null
  await loadTrainings()
}

watch(filterConfig, () => {
  loadTrainings()
})

onMounted(async () => {
  await loadConfigs()
  await loadTrainings()
})
</script>
```

- [ ] **Step 2: 测试页面文件**

Run: `ls frontend/src/views/TrainingsView.vue`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/TrainingsView.vue
git commit -m "feat: add TrainingsView page for training results management"
```

---

### Task 7: 添加 E2E 测试

**Files:**
- Create: `frontend/e2e/tests/test_models_page.py`
- Create: `frontend/e2e/tests/test_trainings_page.py`
- Reference: `frontend/e2e/tests/test_strategy_page.py` (existing pattern)

- [ ] **Step 1: Write test_models_page.py**

```python
import pytest
from playwright.sync_api import Page, expect


def test_models_page_loads(page: Page):
    page.goto("/models")
    expect(page.get_by_text("模型配置")).to_be_visible()


def test_create_model_config(page: Page):
    page.goto("/models")
    page.get_by_text("新建配置").click()
    page.get_by_label("配置名称").fill("test_model")
    page.get_by_role("button", name="保存").click()
    expect(page.get_by_text("test_model")).to_be_visible()


def test_training_button_visible(page: Page):
    page.goto("/models")
    expect(page.get_by_role("button", name="训练").first).to_be_visible()
```

- [ ] **Step 2: Write test_trainings_page.py**

```python
import pytest
from playwright.sync_api import Page, expect


def test_trainings_page_loads(page: Page):
    page.goto("/trainings")
    expect(page.get_by_text("训练记录")).to_be_visible()


def test_config_filter(page: Page):
    page.goto("/trainings")
    expect(page.get_by_label("按配置筛选")).to_be_visible()
```

- [ ] **Step 3: 运行测试验证**

Run: `cd frontend/e2e && pytest tests/test_models_page.py tests/test_trainings_page.py -v --base-url=http://localhost:3000`

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/tests/test_models_page.py frontend/e2e/tests/test_trainings_page.py
git commit -m "test: add E2E tests for models and trainings pages"
```

---

### Task 8: 更新文档

**Files:**
- Modify: `docs/system-design.md`
- Modify: `docs/frontend.md`
- Modify: `README.md`

- [ ] **Step 1: 更新 system-design.md**

添加模型管理模块说明

- [ ] **Step 2: 更新 frontend.md**

添加 /models 和 /trainings 页面说明

- [ ] **Step 3: 更新 README.md**

添加新增功能说明

- [ ] **Step 4: Commit**

```bash
git add docs/ README.md
git commit -m "docs: update docs for models and trainings pages"
```

---

## 自检清单

- [ ] Spec coverage: 每个设计需求都有对应任务？
  - /models 页面 ✓
  - /trainings 页面 ✓
  - 配置 CRUD ✓
  - 训练创建 ✓
  - 预测功能 ✓
  - 筛选功能 ✓
  - 菜单路由 ✓
  - E2E 测试 ✓
  - 文档更新 ✓

- [ ] Placeholder scan: 无 TBD/TODO？
- [ ] Type consistency: 类型一致？
- [ ] API 端点正确？ (/model-configs, /trainings)
