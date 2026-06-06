# 回测配置对比功能设计

## 概述

在回测记录的配置详情弹窗中，增加三个对比入口，分别用于对比账户配置、策略配置和模型配置。复用已有的 `ConfigCompareDialog` 组件，与策略/账户/模型配置页面的对比体验保持一致。

## 交互设计

### 入口位置

回测配置弹窗的 `v-card-title` 工具栏区域，在标题右侧增加三个按钮：

```
[回测配置 - 回测名称]  [对比账户] [对比策略] [对比模型] [X]
```

### 流程

1. 点击「对比账户」→ 打开选择器弹窗
2. 选择器弹窗：`v-select` 下拉列出所有账户配置，单选一条
3. 点击「开始对比」→ 打开 `ConfigCompareDialog`
4. 对比弹窗关闭后回到配置详情弹窗

策略对比和模型对比流程相同。

### 对比弹窗

完全复用 `ConfigCompareDialog` 组件，参数：

| 参数 | 账户对比 | 策略对比 | 模型对比 |
|------|----------|----------|----------|
| configA | `backtestAccountConfig` (快照) | `backtestStrategyConfig` (快照) | `backtestModelConfig` (快照) |
| configB | 从列表选中的 AccountConfig | 从列表选中的 StrategyConfig | 从列表选中的 ModelConfig |
| fields | 账户字段定义 | 策略字段定义 | 模型字段定义 |
| titleA | 快照名称 | 快照名称 | 快照名称 |
| titleB | 选中配置名称 | 选中配置名称 | 选中配置名称 |

## 字段定义

### 账户配置对比字段

| 分组 | key | 标签 | 类型 |
|------|-----|------|------|
| 基本信息 | name | 名称 | string |
| 基本信息 | initial_capital | 初始资金 | number |
| 费率 | buy_fee_rate | 买入费率 | number |
| 费率 | sell_fee_rate | 卖出费率 | number |
| 费率 | stamp_tax_rate | 印花税率 | number |
| 费率 | min_fee | 最低手续费 | number |

### 策略配置对比字段

复用 `StrategyConfigView.vue` 中的 `compareFields` 定义（4 个分组、35 个字段）。

### 模型配置对比字段

复用 `ModelConfigView.vue` 中的 `compareFields` 定义。

## 前端实现

### 涉及文件

| 文件 | 改动 |
|------|------|
| `BacktestRecordsView.vue` | 新增 3 个对比按钮、3 个选择器弹窗、字段定义、API 调用 |
| `ConfigCompareDialog.vue` | 无需改动（完全复用） |

### 新增状态

```typescript
// 选择器弹窗
const accountCompareDialog = ref(false)
const strategyCompareDialog = ref(false)
const modelCompareDialog = ref(false)

// 对比弹窗
const accountCompareResultDialog = ref(false)
const strategyCompareResultDialog = ref(false)
const modelCompareResultDialog = ref(false)

// 选中对比的对象
const selectedAccountForCompare = ref<AccountConfig | null>(null)
const selectedStrategyForCompare = ref<Strategy | null>(null)
const selectedModelForCompare = ref<ModelConfig | null>(null)
```

### 新增 API 调用

```typescript
import { accountConfigApi, type AccountConfig } from '@/api/accountConfig'
import { modelConfigApi, type ModelConfig } from '@/api/modelConfig'
import { strategyConfigApi } from '@/api/strategyConfig'
```

### 账户对比选择器模板

```vue
<v-dialog v-model="accountCompareDialog" max-width="500px">
  <v-card>
    <v-card-title>选择对比账户配置</v-card-title>
    <v-card-text>
      <v-select
        v-model="selectedAccountForCompare"
        :items="accountConfigList"
        item-title="name"
        item-value="id"
        label="账户配置"
        return-object
      />
    </v-card-text>
    <v-card-actions>
      <v-btn @click="accountCompareDialog = false">取消</v-btn>
      <v-btn color="primary" @click="openAccountCompare">开始对比</v-btn>
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

策略和模型对比结构相同。

## 后端

无后端改动。所有 API 接口已存在：
- `GET /account-configs` — 列出账户配置
- `GET /strategy-configs` — 列出策略配置
- `GET /model-configs` — 列出模型配置

## 测试

- 点击各对比按钮应弹出选择器
- 选择配置后应打开对比弹窗
- 对比弹窗应正确显示差异（新增行、删除行、无变化行）
- 关闭对比弹窗后应回到配置详情弹窗