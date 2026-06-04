# 配置复制与对比功能设计

## 1. 概述

为账户配置、策略配置、模型配置三个页面统一增加配置复制和对比功能，提升配置管理效率。

### 涉及页面

| 页面 | 路由 | 文件 |
|------|------|------|
| 账户配置 | `/account-configs` | `AccountConfigView.vue` |
| 策略配置 | `/strategies` | `StrategyConfigView.vue` |
| 模型配置 | `/model-configs` | `ModelConfigView.vue` |

## 2. 复制功能

### 交互流程

1. 每个配置列表的「操作」列增加「复制」按钮，位于「编辑」和「删除」之间
2. 点击「复制」→ 弹出已有的编辑弹窗
3. 表单自动填入源配置的全部字段，名称末尾追加 `_copy` 后缀
4. 用户可以修改任意字段
5. 点击「保存」→ 调用 `create` API 创建新配置（非 update）
6. 保存成功后关闭弹窗并刷新列表

### 关键点

- **复用现有编辑弹窗**：不新增对话框，利用 `openDialog` 打开编辑模式，但传入一个标记 `isCopy = true`
- **API 调用**：编辑模式调 `update`，复制模式调 `create`
- **名称规则**：源名称为 `策略A` → 复制时默认 `策略A_copy`，允许用户修改

### 代码改动

每个配置页的 `openDialog` 方法增加 `isCopy` 参数：

```typescript
const openDialog = (item?: ConfigType, isCopy = false) => {
  if (item) {
    editingId.value = isCopy ? null : item.id      // 复制模式：不设 editingId → create
    form.value = { ...item, name: item.name + '_copy' }  // 预填全部字段 + 名称加 _copy
  } else {
    editingId.value = null
    form.value = { ...defaultForm }
  }
  dialog.value = true
}
```

操作列：

```html
<v-btn size="small" variant="text" prepend-icon="mdi-content-copy" @click="openDialog(item, true)">复制</v-btn>
```

## 3. 对比功能

### 3.1 通用组件 `ConfigCompareDialog.vue`

新建文件 `frontend/src/components/ConfigCompareDialog.vue`，抽取对比逻辑为通用组件，三种配置页共用。

### 3.2 Props

```typescript
interface CompareField {
  key: string                           // 配置对象的字段名
  label: string                         // 显示的中文标签
  group?: string                        // 分组标题（可选）
  type?: 'number' | 'string' | 'boolean' | 'array'  // 值类型，影响显示格式
}

interface Props {
  configA: Record<string, any>          // 配置 A
  configB: Record<string, any>          // 配置 B
  fields: CompareField[]                // 字段定义列表
  titleA?: string                       // A 的名称（显示在表头）
  titleB?: string                       // B 的名称（显示在表头）
}
```

### 3.3 UI 结构

| 区域 | 说明 |
|------|------|
| 弹窗标题 | 图标 + "配置对比" |
| 表头三列 | 参数名 / 配置A（名称）/ 配置B（名称） |
| 分组行 | 当字段 `group` 变化时插入分组标题行（如"基本配置""排名优化"） |
| 数据行 | 显示出两个值，**不相等时用红色背景高亮差异行** |
| 底部 | 关闭按钮 |

### 3.4 值显示规则

| type | 显示格式 |
|------|---------|
| `number` | `toFixed` 或直接显示 |
| `boolean` | `v-chip` 显示「是/否」 |
| `array` | `v-chip-group` 展示 |
| `string` | 直接展示 |

### 3.5 列表页改动

1. 表格开启 `show-select`
2. 监听选择变化，最多选 2 条
3. 工具栏新增「对比」按钮，选中 2 条时激活
4. 点击「对比」→ 打开 `ConfigCompareDialog`

```html
<v-data-table show-select v-model="selected" ...>

<template v-slot:top>
  <v-toolbar ...>
    ...
    <v-btn :disabled="selected.length !== 2" ... @click="compareDialog = true">对比</v-btn>
  </v-toolbar>
</template>
```

### 3.6 字段定义映射

每个配置页定义自己的 `compareFields` 数组，描述要展示的字段及其标签：

**账户配置字段**：

| key | label | type |
|-----|-------|------|
| name | 名称 | string |
| initial_capital | 初始资金 | number |
| buy_fee_rate | 买入费率 | number |
| sell_fee_rate | 卖出费率 | number |
| stamp_tax_rate | 印花税 | number |
| min_fee | 最低手续费 | number |

**策略配置字段**（分组展示）：

| key | label | group | type |
|-----|-------|-------|------|
| name | 策略名称 | - | string |
| type | 策略类型 | - | string |
| min_order_value | 最小订单金额 | 基本配置 | number |
| stop_loss_pct | 止损比例 | 基本配置 | number |
| max_hold_days | 最大持仓天数 | 基本配置 | number |
| min_hold_days | 最低持有天数 | 基本配置 | number |
| buy_threshold | 买入阈值 | 基本配置 | number |
| sell_threshold | 卖出阈值 | 基本配置 | number |
| max_positions | 最大持仓数 | 多股票配置 | number |
| max_position_pct | 单票最大仓位 | 多股票配置 | number |
| sell_rank_n | 卖出排名阈值 | 多股票配置 | number |
| hold_score_threshold | 持仓评分保护阈值 | 多股票配置 | number |
| use_momentum_boost | 动量加权 | 排名优化 | boolean |
| momentum_window | 动量窗口 | 排名优化 | number |
| max_momentum_bonus | 最大动量加成 | 排名优化 | number |
| ranking_smooth_window | 平滑窗口 | 排名优化 | number |
| ranking_smooth_alpha | 平滑系数 | 排名优化 | number |
| use_trend_bonus | 趋势加分 | 排名优化 | boolean |
| trend_bonus_window | 趋势窗口 | 排名优化 | number |
| trend_bonus_scale | 趋势斜率系数 | 排名优化 | number |
| trend_r2_threshold | R²阈值 | 排名优化 | number |
| trend_max_bonus | 最大趋势加分 | 排名优化 | number |
| use_volatility_penalty | 波动扣分 | 排名优化 | boolean |
| vol_penalty_window | 波动窗口 | 排名优化 | number |
| vol_range_tolerance | 振幅容忍度 | 排名优化 | number |
| vol_penalty_scale | 扣分系数 | 排名优化 | number |
| vol_max_penalty | 最大扣分 | 排名优化 | number |
| use_explosion_filter | 暴涨排除 | 交易优化 | boolean |
| explosion_price_threshold | 涨幅阈值 | 交易优化 | number |
| explosion_volume_ratio | 量比阈值 | 交易优化 | number |
| explosion_window | 参考窗口 | 交易优化 | number |
| use_full_position_sell | 满仓容忍度 | 交易优化 | boolean |
| full_position_threshold | 仓位阈值 | 交易优化 | number |
| full_position_days | 持续天数 | 交易优化 | number |
| full_position_score_window | 评分窗口 | 交易优化 | number |
| full_position_sell_count | 每次卖出数量 | 交易优化 | number |
| use_acceleration_filter | 加速排除 | 交易优化 | boolean |
| acceleration_window | 检测窗口 | 交易优化 | number |
| acceleration_cum_return | 累计涨幅阈值 | 交易优化 | number |
| acceleration_up_ratio | 上涨天数占比 | 交易优化 | number |

**模型配置字段**（分组展示）：

| key | label | group | type |
|-----|-------|-------|------|
| name | 配置名称 | - | string |
| model_type | 模型类型 | - | string |
| feature_fields | 特征字段 | 字段配置 | array |
| standardize_fields | 标准化字段 | 字段配置 | array |
| winsorize_fields | 缩尾字段 | 字段配置 | array |
| label_mode | 标签计算模式 | 标签参数 | string |
| classification_horizons | 预测周期 | 标签参数 | array |
| classification_threshold_3d | 3日涨跌阈值 | 标签参数 | number |
| classification_threshold_5d | 5日涨跌阈值 | 标签参数 | number |
| classification_threshold_10d | 10日涨跌阈值 | 标签参数 | number |
| xgb_n_estimators | n_estimators | XGBoost | number |
| xgb_max_depth | max_depth | XGBoost | number |
| xgb_learning_rate | learning_rate | XGBoost | number |
| xgb_min_child_weight | min_child_weight | XGBoost | number |
| xgb_subsample | subsample | XGBoost | number |
| xgb_colsample_bytree | colsample_bytree | XGBoost | number |
| lstm_hidden_size | hidden_size | LSTM | number |
| lstm_num_layers | num_layers | LSTM | number |
| lstm_dropout | dropout | LSTM | number |
| lstm_epochs | epochs | LSTM | number |
| lstm_batch_size | batch_size | LSTM | number |
| lstm_learning_rate | learning_rate | LSTM | number |
| lstm_sequence_length | sequence_length | LSTM | number |
| lstm_normalization_window | normalization_window | LSTM | number |
| lstm_weight_decay | weight_decay | LSTM | number |
| lr_scheduler_factor | lr_scheduler_factor | LSTM | number |
| lr_scheduler_patience | lr_scheduler_patience | LSTM | number |
| val_size | val_size | LSTM | number |

## 4. 涉及文件清单

| 文件 | 改动类型 |
|------|---------|
| `frontend/src/components/ConfigCompareDialog.vue` | 新建 |
| `AccountConfigView.vue` | 修改（复制按钮 + show-select + 对比弹窗） |
| `StrategyConfigView.vue` | 修改（复制按钮 + show-select + 对比弹窗） |
| `ModelConfigView.vue` | 修改（复制按钮 + show-select + 对比弹窗） |

后端无需改动，复用已有 CRUD API。

## 5. 未涉及事项（明确不做的）

- 不做三配置同时对比（仅支持两两对比）
- 不做对比结果导出
- 不做配置历史版本对比