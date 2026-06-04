# Config Copy & Compare Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) for syntax tracking.

**Goal:** Add copy and compare functionality to all three config pages (account, strategy, model configs).

**Architecture:** A shared `ConfigCompareDialog.vue` component handles comparison for all three config types. Each config page gets a copy button that reuses the existing edit dialog. Select-based comparison uses `show-select` on existing `v-data-table`.

**Tech Stack:** Vue 3 + Vuetify 3 + TypeScript

---

### Task 1: Create ConfigCompareDialog component

**Files:**
- Create: `frontend/src/components/ConfigCompareDialog.vue`

- [ ] **Step 1: Create the component file**

```vue
<template>
  <v-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)" max-width="900px">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center text-h6 pa-4">
        <div class="d-flex align-center ga-2">
          <v-icon color="primary">mdi-compare</v-icon>
          配置对比
        </div>
        <v-btn icon variant="text" size="small" @click="$emit('update:modelValue', false)">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-0">
        <v-table density="compact">
          <thead>
            <tr>
              <th class="text-left" style="width: 220px; min-width: 220px;">参数名</th>
              <th class="text-left" :class="diffClass(0)">{{ titleA || '配置A' }}</th>
              <th class="text-left" :class="diffClass(0)">{{ titleB || '配置B' }}</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="(field, idx) in fields" :key="field.key">
              <tr v-if="field.group && (idx === 0 || fields[idx - 1].group !== field.group)" class="bg-grey-lighten-3">
                <td colspan="3" class="font-weight-medium text-body-2">{{ field.group }}</td>
              </tr>
              <tr :class="isDifferent(field) ? 'bg-red-lighten-5' : ''">
                <td class="text-body-2">{{ field.label }}</td>
                <td :class="isDifferent(field) ? 'font-weight-medium' : ''">
                  <FormatValue :value="configA[field.key]" :type="field.type" />
                </td>
                <td :class="isDifferent(field) ? 'font-weight-medium' : ''">
                  <FormatValue :value="configB[field.key]" :type="field.type" />
                </td>
              </tr>
            </template>
          </tbody>
        </v-table>
      </v-card-text>
      <v-divider />
      <v-card-actions class="bg-surface-light">
        <v-spacer />
        <v-btn variant="text" @click="$emit('update:modelValue', false)">关闭</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import FormatValue from './FormatValue.vue'

export interface CompareField {
  key: string
  label: string
  group?: string
  type?: 'number' | 'string' | 'boolean' | 'array'
}

defineProps<{
  modelValue: boolean
  configA: Record<string, any>
  configB: Record<string, any>
  fields: CompareField[]
  titleA?: string
  titleB?: string
}>()

defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const isDifferent = (field: CompareField): boolean => {
  const a = field.key ? configA[field.key] : undefined
  const b = field.key ? configB[field.key] : undefined
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length !== b.length || a.some((v, i) => v !== b[i])
  }
  return a !== b
}

const diffClass = (colIdx: number): string => {
  // No column-level diff class needed; row-level bg handles it
  return ''
}
</script>
```

Wait — I referenced `configA`/`configB` directly in `<script>` without destructuring. Let me fix that.

- [ ] **Step 2: Create the FormatValue sub-component**

```vue
<template>
  <template v-if="type === 'boolean'">
    <v-chip :color="value ? 'success' : 'grey'" size="x-small">
      {{ value ? '是' : '否' }}
    </v-chip>
  </template>
  <template v-else-if="type === 'array' && Array.isArray(value)">
    <v-chip-group>
      <v-chip v-for="v in value" :key="v" size="x-small" variant="outlined">{{ v }}</v-chip>
    </v-chip-group>
  </template>
  <template v-else-if="type === 'number' && value !== undefined && value !== null">
    {{ typeof value === 'number' ? String(value) : value }}
  </template>
  <template v-else>
    {{ value ?? '-' }}
  </template>
</template>

<script setup lang="ts">
defineProps<{
  value: any
  type?: string
}>()
</script>
```

- [ ] **Step 3: Fix ConfigCompareDialog to use proper prop access**

In `ConfigCompareDialog.vue`, fix the `<script>` section — use `toRefs` or access props properly:

```vue
<script setup lang="ts">
import { toRefs } from 'vue'
import FormatValue from './FormatValue.vue'

export interface CompareField {
  key: string
  label: string
  group?: string
  type?: 'number' | 'string' | 'boolean' | 'array'
}

const props = defineProps<{
  modelValue: boolean
  configA: Record<string, any>
  configB: Record<string, any>
  fields: CompareField[]
  titleA?: string
  titleB?: string
}>()

const { configA, configB, fields, titleA, titleB } = toRefs(props)

defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const isDifferent = (field: CompareField): boolean => {
  const a = configA.value[field.key]
  const b = configB.value[field.key]
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length !== b.length || a.some((v, i) => v !== b[i])
  }
  return a !== b
}
</script>
```

- [ ] **Step 4: Verify TypeScript compilation**

Run: `cd frontend; npx vue-tsc --noEmit 2>&1`
Expected: Exit code 0, no errors related to ConfigCompareDialog or FormatValue

- [ ] **Step 5: Commit**

```
git add frontend/src/components/ConfigCompareDialog.vue frontend/src/components/FormatValue.vue
git commit -m "feat: add config compare dialog component"
```

---

### Task 2: Update AccountConfigView with copy & compare

**Files:**
- Modify: `frontend/src/views/AccountConfigView.vue`

- [ ] **Step 1: Add template changes**

Add `show-select` to the `v-data-table`, add `v-model="selected"`:

```diff
- <v-data-table :headers="headers" :items="accountConfigs" :loading="loading">
+ <v-data-table :headers="headers" :items="accountConfigs" :loading="loading" show-select v-model="selected">
```

Add "对比" button to toolbar, after the "新建账户" button:

```diff
           @click="openDialog()"
         ></v-btn>
+        <v-btn
+          prepend-icon="mdi-compare"
+          rounded="lg"
+          text="对比"
+          border
+          :disabled="selected.length !== 2"
+          @click="compareDialog = true"
+        ></v-btn>
```

Add "复制" button to actions column, between "编辑" and "删除":

```diff
          <v-btn size="small" variant="text" prepend-icon="mdi-pencil" @click="openDialog(item)">编辑</v-btn>
+         <v-btn size="small" variant="text" prepend-icon="mdi-content-copy" @click="openDialog(item, true)">复制</v-btn>
          <v-btn size="small" variant="text" color="error" prepend-icon="mdi-delete" @click="confirmDelete(item)">删除</v-btn>
```

Add compare dialog at bottom of template (before closing `</template>`):

```html
<ConfigCompareDialog
  v-model="compareDialog"
  :configA="selected[0]"
  :configB="selected[1]"
  :fields="compareFields"
  :titleA="selected[0]?.name"
  :titleB="selected[1]?.name"
/>
```

- [ ] **Step 2: Add script changes**

Add imports:

```typescript
import { ref } from 'vue'
import ConfigCompareDialog from '@/components/ConfigCompareDialog.vue'
import type { CompareField } from '@/components/ConfigCompareDialog.vue'
```

Add reactive state:

```typescript
const selected = ref<AccountConfig[]>([])
const compareDialog = ref(false)
```

Add compare fields definition:

```typescript
const compareFields: CompareField[] = [
  { key: 'name', label: '名称' },
  { key: 'initial_capital', label: '初始资金', type: 'number' },
  { key: 'buy_fee_rate', label: '买入费率', type: 'number' },
  { key: 'sell_fee_rate', label: '卖出费率', type: 'number' },
  { key: 'stamp_tax_rate', label: '印花税', type: 'number' },
  { key: 'min_fee', label: '最低手续费', type: 'number' },
]
```

Modify `openDialog` to accept `isCopy` parameter:

```typescript
const openDialog = (item?: AccountConfig, isCopy = false) => {
  if (item) {
    editingId.value = isCopy ? null : item.id
    form.value = {
      name: item.name + '_copy',
      initial_capital: item.initial_capital,
      buy_fee_rate: item.buy_fee_rate,
      sell_fee_rate: item.sell_fee_rate,
      stamp_tax_rate: item.stamp_tax_rate,
      min_fee: item.min_fee,
    }
  } else {
    editingId.value = null
    form.value = { name: 'default_account_config', initial_capital: 100000, buy_fee_rate: 0.0003, sell_fee_rate: 0.0003, stamp_tax_rate: 0.001, min_fee: 5 }
  }
  dialog.value = true
}
```

- [ ] **Step 3: Verify TypeScript compilation**

Run: `cd frontend; npx vue-tsc --noEmit 2>&1`
Expected: Exit code 0, no AccountConfigView errors

- [ ] **Step 4: Commit**

```
git add frontend/src/views/AccountConfigView.vue
git commit -m "feat: add copy and compare to account config page"
```

---

### Task 3: Update StrategyConfigView with copy & compare

**Files:**
- Modify: `frontend/src/views/StrategyConfigView.vue`

- [ ] **Step 1: Add template changes**

Same pattern as AccountConfigView:
- `show-select v-model="selected"` on `v-data-table`
- "对比" button in toolbar
- "复制" button in actions column
- `ConfigCompareDialog` at bottom

- [ ] **Step 2: Add script changes**

Imports:

```typescript
import ConfigCompareDialog from '@/components/ConfigCompareDialog.vue'
import type { CompareField } from '@/components/ConfigCompareDialog.vue'

const selected = ref<Strategy[]>([])
const compareDialog = ref(false)
```

Compare fields (grouped):

```typescript
const compareFields: CompareField[] = [
  { key: 'name', label: '策略名称' },
  { key: 'type', label: '策略类型' },
  { key: 'min_order_value', label: '最小订单金额', group: '基本配置', type: 'number' },
  { key: 'stop_loss_pct', label: '止损比例', group: '基本配置', type: 'number' },
  { key: 'max_hold_days', label: '最大持仓天数', group: '基本配置', type: 'number' },
  { key: 'min_hold_days', label: '最低持有天数', group: '基本配置', type: 'number' },
  { key: 'buy_threshold', label: '买入阈值', group: '基本配置', type: 'number' },
  { key: 'sell_threshold', label: '卖出阈值', group: '基本配置', type: 'number' },
  { key: 'max_positions', label: '最大持仓数', group: '多股票配置', type: 'number' },
  { key: 'max_position_pct', label: '单票最大仓位', group: '多股票配置', type: 'number' },
  { key: 'sell_rank_n', label: '卖出排名阈值', group: '多股票配置', type: 'number' },
  { key: 'hold_score_threshold', label: '持仓评分保护阈值', group: '多股票配置', type: 'number' },
  { key: 'use_momentum_boost', label: '动量加权', group: '排名优化', type: 'boolean' },
  { key: 'momentum_window', label: '动量窗口', group: '排名优化', type: 'number' },
  { key: 'max_momentum_bonus', label: '最大动量加成', group: '排名优化', type: 'number' },
  { key: 'ranking_smooth_window', label: '平滑窗口', group: '排名优化', type: 'number' },
  { key: 'ranking_smooth_alpha', label: '平滑系数', group: '排名优化', type: 'number' },
  { key: 'use_trend_bonus', label: '趋势加分', group: '排名优化', type: 'boolean' },
  { key: 'trend_bonus_window', label: '趋势窗口', group: '排名优化', type: 'number' },
  { key: 'trend_bonus_scale', label: '趋势斜率系数', group: '排名优化', type: 'number' },
  { key: 'trend_r2_threshold', label: 'R²阈值', group: '排名优化', type: 'number' },
  { key: 'trend_max_bonus', label: '最大趋势加分', group: '排名优化', type: 'number' },
  { key: 'use_volatility_penalty', label: '波动扣分', group: '排名优化', type: 'boolean' },
  { key: 'vol_penalty_window', label: '波动窗口', group: '排名优化', type: 'number' },
  { key: 'vol_range_tolerance', label: '振幅容忍度', group: '排名优化', type: 'number' },
  { key: 'vol_penalty_scale', label: '扣分系数', group: '排名优化', type: 'number' },
  { key: 'vol_max_penalty', label: '最大扣分', group: '排名优化', type: 'number' },
  { key: 'use_explosion_filter', label: '暴涨排除', group: '交易优化', type: 'boolean' },
  { key: 'explosion_price_threshold', label: '涨幅阈值', group: '交易优化', type: 'number' },
  { key: 'explosion_volume_ratio', label: '量比阈值', group: '交易优化', type: 'number' },
  { key: 'explosion_window', label: '参考窗口', group: '交易优化', type: 'number' },
  { key: 'use_full_position_sell', label: '满仓容忍度', group: '交易优化', type: 'boolean' },
  { key: 'full_position_threshold', label: '仓位阈值', group: '交易优化', type: 'number' },
  { key: 'full_position_days', label: '持续天数', group: '交易优化', type: 'number' },
  { key: 'full_position_score_window', label: '评分窗口', group: '交易优化', type: 'number' },
  { key: 'full_position_sell_count', label: '每次卖出数量', group: '交易优化', type: 'number' },
  { key: 'use_acceleration_filter', label: '加速排除', group: '交易优化', type: 'boolean' },
  { key: 'acceleration_window', label: '检测窗口', group: '交易优化', type: 'number' },
  { key: 'acceleration_cum_return', label: '累计涨幅阈值', group: '交易优化', type: 'number' },
  { key: 'acceleration_up_ratio', label: '上涨天数占比', group: '交易优化', type: 'number' },
]
```

Modify `openDialog` signature to accept `isCopy`:

```typescript
const openDialog = (item?: Strategy, isCopy = false) => {
  activeTab.value = 'basic'
  if (item) {
    editingId.value = isCopy ? null : item.id
    form.value = {
      name: item.name + '_copy',
      type: item.type,
      min_order_value: item.min_order_value,
      // ... (same spread as current editing code)
    }
  } else {
    editingId.value = null
    form.value = { ...defaultForm }
  }
  dialog.value = true
}
```

- [ ] **Step 3: Verify TypeScript compilation**

Run: `cd frontend; npx vue-tsc --noEmit 2>&1`
Expected: Exit code 0, no StrategyConfigView errors

- [ ] **Step 4: Commit**

```
git add frontend/src/views/StrategyConfigView.vue
git commit -m "feat: add copy and compare to strategy config page"
```

---

### Task 4: Update ModelConfigView with copy & compare

**Files:**
- Modify: `frontend/src/views/ModelConfigView.vue`

- [ ] **Step 1: Add template changes**

Same pattern as Task 2/3:
- `show-select v-model="selected"` on `v-data-table`
- "对比" button in toolbar
- "复制" button in actions column
- `ConfigCompareDialog` at bottom

- [ ] **Step 2: Add script changes**

Imports and state:

```typescript
import ConfigCompareDialog from '@/components/ConfigCompareDialog.vue'
import type { CompareField } from '@/components/ConfigCompareDialog.vue'

const selected = ref<ModelConfig[]>([])
const compareDialog = ref(false)
```

Compare fields:

```typescript
const compareFields: CompareField[] = [
  { key: 'name', label: '配置名称' },
  { key: 'model_type', label: '模型类型' },
  { key: 'feature_fields', label: '特征字段', group: '字段配置', type: 'array' },
  { key: 'standardize_fields', label: '标准化字段', group: '字段配置', type: 'array' },
  { key: 'winsorize_fields', label: '缩尾字段', group: '字段配置', type: 'array' },
  { key: 'label_mode', label: '标签计算模式', group: '标签参数' },
  { key: 'classification_horizons', label: '预测周期', group: '标签参数', type: 'array' },
  { key: 'classification_threshold_3d', label: '3日涨跌阈值', group: '标签参数', type: 'number' },
  { key: 'classification_threshold_5d', label: '5日涨跌阈值', group: '标签参数', type: 'number' },
  { key: 'classification_threshold_10d', label: '10日涨跌阈值', group: '标签参数', type: 'number' },
  { key: 'xgb_n_estimators', label: 'n_estimators', group: 'XGBoost', type: 'number' },
  { key: 'xgb_max_depth', label: 'max_depth', group: 'XGBoost', type: 'number' },
  { key: 'xgb_learning_rate', label: 'learning_rate', group: 'XGBoost', type: 'number' },
  { key: 'xgb_min_child_weight', label: 'min_child_weight', group: 'XGBoost', type: 'number' },
  { key: 'xgb_subsample', label: 'subsample', group: 'XGBoost', type: 'number' },
  { key: 'xgb_colsample_bytree', label: 'colsample_bytree', group: 'XGBoost', type: 'number' },
  { key: 'lstm_hidden_size', label: 'hidden_size', group: 'LSTM', type: 'number' },
  { key: 'lstm_num_layers', label: 'num_layers', group: 'LSTM', type: 'number' },
  { key: 'lstm_dropout', label: 'dropout', group: 'LSTM', type: 'number' },
  { key: 'lstm_epochs', label: 'epochs', group: 'LSTM', type: 'number' },
  { key: 'lstm_batch_size', label: 'batch_size', group: 'LSTM', type: 'number' },
  { key: 'lstm_learning_rate', label: 'learning_rate', group: 'LSTM', type: 'number' },
  { key: 'lstm_sequence_length', label: 'sequence_length', group: 'LSTM', type: 'number' },
  { key: 'lstm_normalization_window', label: 'normalization_window', group: 'LSTM', type: 'number' },
  { key: 'lstm_weight_decay', label: 'weight_decay', group: 'LSTM', type: 'number' },
  { key: 'lr_scheduler_factor', label: 'lr_scheduler_factor', group: 'LSTM', type: 'number' },
  { key: 'lr_scheduler_patience', label: 'lr_scheduler_patience', group: 'LSTM', type: 'number' },
  { key: 'val_size', label: 'val_size', group: 'LSTM', type: 'number' },
]
```

Modify `openDialog` to accept `isCopy`:

```typescript
const openDialog = (item?: ModelConfig, isCopy = false) => {
  activeTab.value = 'fields'
  if (item) {
    editingId.value = isCopy ? null : item.id
    form.value = {
      name: item.name + '_copy',
      model_type: item.model_type,
      // ... (same spread as current editing code)
    }
  } else {
    editingId.value = null
    form.value = { ...defaultForm, name: generateDefaultName(defaultForm.model_type) }
  }
  dialog.value = true
}
```

- [ ] **Step 3: Verify TypeScript compilation**

Run: `cd frontend; npx vue-tsc --noEmit 2>&1`
Expected: Exit code 0, no ModelConfigView errors

- [ ] **Step 4: Commit**

```
git add frontend/src/views/ModelConfigView.vue
git commit -m "feat: add copy and compare to model config page"
```