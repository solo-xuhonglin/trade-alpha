# 回测配置对比功能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在回测记录配置详情弹窗中增加三个对比按钮（账户/策略/模型），复用已有 `ConfigCompareDialog` 完成配置对比

**Architecture:** 零新增组件，三个对比按钮各打开一个选择器弹窗，选择配置后打开 `ConfigCompareDialog` 展示差异

**Tech Stack:** Vue 3 + Vuetify 3 + TypeScript

---

### Task 1: BacktestRecordsView — 新增导入和数据状态

**Files:**
- Modify: `frontend/src/views/BacktestRecordsView.vue:731-736`

- [ ] **Step 1: 新增 import**

在 `BacktestRecordsView.vue` 的 `<script setup>` 顶部，替换原有 imports：

```typescript
import { ref, computed, nextTick, watch } from 'vue'
import { backtestRecordApi, type Backtest, type DailyDetail, type PnlDetailItem, type PnlDetailSummary } from '@/api/backtestRecord'
import { strategyConfigApi, type Strategy } from '@/api/strategyConfig'
import { accountConfigApi, type AccountConfig } from '@/api/accountConfig'
import { modelConfigApi, type ModelConfig } from '@/api/modelConfig'
import * as echarts from 'echarts'
import PredictionChart from '@/components/PredictionChart.vue'
import ConfigCompareDialog from '@/components/ConfigCompareDialog.vue'
import type { CompareField } from '@/components/ConfigCompareDialog.vue'
```

注意：需要先确认 `ConfigCompareDialog.vue` 是否导出了 `CompareField` 类型。如果没有，需要导出。

- [ ] **Step 2: Check ConfigCompareDialog exports**

Read `frontend/src/components/ConfigCompareDialog.vue` to check if `CompareField` interface is exported.

If not exported, add at the top of the `<script setup>` block:

```typescript
export interface CompareField {
  key: string
  label: string
  group?: string
  type?: 'string' | 'number' | 'boolean'
}
```

- [ ] **Step 3: 新增状态变量**

在 `backtestConfigDialog` 定义之后（约 line 753），新增所有对比相关状态：

```typescript
// Compare dialogs state
const accountCompareDialog = ref(false)
const strategyCompareDialog = ref(false)
const modelCompareDialog = ref(false)
const accountCompareResultDialog = ref(false)
const strategyCompareResultDialog = ref(false)
const modelCompareResultDialog = ref(false)
const selectedAccountForCompare = ref<AccountConfig | null>(null)
const selectedStrategyForCompare = ref<Strategy | null>(null)
const selectedModelForCompare = ref<ModelConfig | null>(null)
const accountConfigList = ref<AccountConfig[]>([])
const strategyConfigList = ref<Strategy[]>([])
const modelConfigList = ref<ModelConfig[]>([])
```

- [ ] **Step 4: 定义对比字段**

在 `backtestConfigDialog` 相关代码附近，新增三个 field 定义：

```typescript
const accountCompareFields: CompareField[] = [
  { key: 'name', label: '名称', group: '基本信息' },
  { key: 'initial_capital', label: '初始资金', group: '基本信息', type: 'number' },
  { key: 'buy_fee_rate', label: '买入费率', group: '费率', type: 'number' },
  { key: 'sell_fee_rate', label: '卖出费率', group: '费率', type: 'number' },
  { key: 'stamp_tax_rate', label: '印花税率', group: '费率', type: 'number' },
  { key: 'min_fee', label: '最低手续费', group: '费率', type: 'number' },
  { key: 'cash', label: '现金', group: '资金', type: 'number' },
  { key: 'position', label: '持仓', group: '资金', type: 'number' },
]
```

策略和模型的对比字段从各自的 View 页面复制（策略 35 个字段、模型 20+ 个字段），使用相同的分组和类型。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/BacktestRecordsView.vue frontend/src/components/ConfigCompareDialog.vue
git commit -m "feat: add compare state and fields for backtest config"
```

---

### Task 2: BacktestRecordsView — 新增选择器弹窗和对比弹窗模板

**Files:**
- Modify: `frontend/src/views/BacktestRecordsView.vue`

- [ ] **Step 1: 在选择器弹窗之前添加 data loading functions**

在 `openBacktestConfig` 函数之后，新增三个加载函数：

```typescript
const loadAccountConfigs = async () => {
  const res = await accountConfigApi.list()
  accountConfigList.value = res.data
}

const loadStrategyConfigs = async () => {
  const res = await strategyConfigApi.list()
  strategyConfigList.value = res.data
}

const loadModelConfigs = async () => {
  const res = await modelConfigApi.list()
  modelConfigList.value = res.data
}

const openAccountCompare = () => {
  if (!selectedAccountForCompare.value) return
  accountCompareDialog.value = false
  accountCompareResultDialog.value = true
}

const openStrategyCompare = () => {
  if (!selectedStrategyForCompare.value) return
  strategyCompareDialog.value = false
  strategyCompareResultDialog.value = true
}

const openModelCompare = () => {
  if (!selectedModelForCompare.value) return
  modelCompareDialog.value = false
  modelCompareResultDialog.value = true
}
```

- [ ] **Step 2: 配置弹窗工具栏添加对比按钮**

在 `backtestConfigDialog` 中，找到 `v-card-title` 区域（约 line 470），修改为：

```vue
<v-card-title class="d-flex justify-space-between align-center text-h6 pa-4">
  <div class="d-flex align-center ga-2">
    <v-icon color="primary">mdi-cog</v-icon>
    回测配置
    <v-chip v-if="backtestConfigItem" size="small" variant="outlined" class="ml-2">{{ backtestConfigItem.name }}</v-chip>
  </div>
  <div class="d-flex ga-2">
    <v-btn size="small" variant="tonal" color="info" prepend-icon="mdi-compare"
      @click="loadAccountConfigs(); accountCompareDialog = true">对比账户</v-btn>
    <v-btn size="small" variant="tonal" color="info" prepend-icon="mdi-compare"
      @click="loadStrategyConfigs(); strategyCompareDialog = true">对比策略</v-btn>
    <v-btn size="small" variant="tonal" color="info" prepend-icon="mdi-compare"
      @click="loadModelConfigs(); modelCompareDialog = true">对比模型</v-btn>
    <v-btn icon variant="text" size="small" @click="backtestConfigDialog = false">
      <v-icon>mdi-close</v-icon>
    </v-btn>
  </div>
</v-card-title>
```

- [ ] **Step 3: 添加账户对比选择器弹窗**

在配置弹窗 `v-dialog` 关闭标签 `</v-dialog>` 之后，添加：

```vue
<!-- Account Config Compare Picker -->
<v-dialog v-model="accountCompareDialog" max-width="500px">
  <v-card>
    <v-card-title class="d-flex justify-space-between align-center pa-4">
      选择对比账户配置
      <v-btn icon variant="text" size="small" @click="accountCompareDialog = false">
        <v-icon>mdi-close</v-icon>
      </v-btn>
    </v-card-title>
    <v-card-text>
      <v-select
        v-model="selectedAccountForCompare"
        :items="accountConfigList"
        item-title="name"
        item-value="id"
        label="账户配置"
        return-object
        clearable
      />
    </v-card-text>
    <v-card-actions class="pa-4 pt-0">
      <v-spacer />
      <v-btn variant="text" @click="accountCompareDialog = false">取消</v-btn>
      <v-btn color="primary" variant="tonal" :disabled="!selectedAccountForCompare" @click="openAccountCompare">开始对比</v-btn>
    </v-card-actions>
  </v-card>
</v-dialog>

<ConfigCompareDialog
  v-model="accountCompareResultDialog"
  :configA="backtestAccountConfig"
  :configB="selectedAccountForCompare"
  :fields="accountCompareFields"
  titleA="当前回测"
  :titleB="selectedAccountForCompare?.name"
/>
```

- [ ] **Step 4: 添加策略对比选择器弹窗**

```vue
<!-- Strategy Config Compare Picker -->
<v-dialog v-model="strategyCompareDialog" max-width="500px">
  <v-card>
    <v-card-title class="d-flex justify-space-between align-center pa-4">
      选择对比策略配置
      <v-btn icon variant="text" size="small" @click="strategyCompareDialog = false">
        <v-icon>mdi-close</v-icon>
      </v-btn>
    </v-card-title>
    <v-card-text>
      <v-select
        v-model="selectedStrategyForCompare"
        :items="strategyConfigList"
        item-title="name"
        item-value="id"
        label="策略配置"
        return-object
        clearable
      />
    </v-card-text>
    <v-card-actions class="pa-4 pt-0">
      <v-spacer />
      <v-btn variant="text" @click="strategyCompareDialog = false">取消</v-btn>
      <v-btn color="primary" variant="tonal" :disabled="!selectedStrategyForCompare" @click="openStrategyCompare">开始对比</v-btn>
    </v-card-actions>
  </v-card>
</v-dialog>

<ConfigCompareDialog
  v-model="strategyCompareResultDialog"
  :configA="backtestStrategyConfig"
  :configB="selectedStrategyForCompare"
  :fields="strategyCompareFields"
  titleA="当前回测"
  :titleB="selectedStrategyForCompare?.name"
/>
```

- [ ] **Step 5: 添加模型对比选择器弹窗**

```vue
<!-- Model Config Compare Picker -->
<v-dialog v-model="modelCompareDialog" max-width="500px">
  <v-card>
    <v-card-title class="d-flex justify-space-between align-center pa-4">
      选择对比模型配置
      <v-btn icon variant="text" size="small" @click="modelCompareDialog = false">
        <v-icon>mdi-close</v-icon>
      </v-btn>
    </v-card-title>
    <v-card-text>
      <v-select
        v-model="selectedModelForCompare"
        :items="modelConfigList"
        item-title="name"
        item-value="id"
        label="模型配置"
        return-object
        clearable
      />
    </v-card-text>
    <v-card-actions class="pa-4 pt-0">
      <v-spacer />
      <v-btn variant="text" @click="modelCompareDialog = false">取消</v-btn>
      <v-btn color="primary" variant="tonal" :disabled="!selectedModelForCompare" @click="openModelCompare">开始对比</v-btn>
    </v-card-actions>
  </v-card>
</v-dialog>

<ConfigCompareDialog
  v-model="modelCompareResultDialog"
  :configA="backtestModelConfig"
  :configB="selectedModelForCompare"
  :fields="modelCompareFields"
  titleA="当前回测"
  :titleB="selectedModelForCompare?.name"
/>
```

- [ ] **Step 6: Copy strategy compare fields from StrategyConfigView and model compare fields from ModelConfigView**

从 `frontend/src/views/StrategyConfigView.vue` 复制 `compareFields` 定义，命名为 `strategyCompareFields`。
从 `frontend/src/views/ModelConfigView.vue` 复制 `compareFields` 定义，命名为 `modelCompareFields`。

- [ ] **Step 7: 验证 TypeScript 编译**

Run: `npx vue-tsc -b --noEmit`
Expected: EXIT CODE 0, no errors

- [ ] **Step 8: Commit**

```bash
git add frontend/src/views/BacktestRecordsView.vue
git commit -m "feat: add compare picker dialogs and ConfigCompareDialog instances"
```

---

### Task 3: 验证前端功能

- [ ] **Step 1: 检查前端是否运行**

Run: `npx vue-tsc -b --noEmit`
Expected: 无编译错误

- [ ] **Step 2: 提价并推送**

```bash
git push
```