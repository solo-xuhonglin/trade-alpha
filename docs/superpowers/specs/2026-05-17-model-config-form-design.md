# 模型配置表单重构设计

## 问题

前端模型配置页面（ModelsView.vue）的 `ModelConfig` 接口与后端 Document 字段定义严重不匹配：

- 前端使用 `params: Record<string, any>` 和 `targets: string[]` 的旧格式
- 后端已演进为扁平化的 `feature_fields`、`classification_horizons` 等字段
- 编辑时后端返回的扁平字段无法映射到 `form.params.xxx`，导致页面报错

## 目标

1. 前后端字段对齐，编辑页面不再报错
2. 支持 xgboost 超参数（n_estimators, max_depth 等）的存储与编辑
3. 参考 AccountsPage 的 v-row/v-col 网格布局，提升表单可用性
4. 适当调整弹窗宽度以容纳更多字段

## 范围限定

- 只处理 xgboost 模型类型（用户明确要求）
- 其他模型类型（lstm）暂时保持现有处理方式

## 后端改动

### ModelConfig Document（dao/model_config.py）

新增 6 个 xgboost 超参数字段（与 XGBoostClassifier.__init__ 参数一致）：

```
xgb_n_estimators: int = 100
xgb_max_depth: int = 6
xgb_learning_rate: float = 0.1
xgb_min_child_weight: int = 1
xgb_subsample: float = 1.0
xgb_colsample_bytree: float = 1.0
```

### API 路由（api/routers/model_configs.py）

- ConfigCreate / ConfigUpdate 新增上述 6 个 xgboost 可选字段
- 所有 API 响应中包含这些字段

### 配置服务（predict/config_service.py）

- create_config / update_config 接受并透传 xgboost 参数到 ModelConfig

### 训练服务（predict/training_service.py）

- create_training 中实例化 XGBoostClassifier 时从 config 读取 xgboost 超参数，而非使用默认值

## 前端改动

### API 接口（api/model.ts）

重写 `ModelConfig` 接口，移除 `params` 和 `targets`，替换为后端实际字段：

```typescript
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
```

### ModelsView.vue — 表单布局

参考 AccountsPage 使用 `v-row`/`v-col` 网格布局，弹窗宽度设为 `max-width="800px"`。

表单分区：

1. **基本信息行**（2 列）：
   - 配置名称（v-text-field）
   - 模型类型（v-select，选项：xgboost / lstm）

2. **特征与数据处理**：
   - 特征字段（v-autocomplete multiple chips，支持搜索过滤，备选 26 个技术指标）
   - 标准化字段（v-autocomplete multiple chips，同组备选）
   - 缩尾字段（v-autocomplete multiple chips，同组备选）

3. **训练标签参数行**（2 列）：
   - 预测周期（v-combobox multiple chips，默认 [3, 5]）
   - 涨跌阈值（v-text-field type="number" step="0.01"）

4. **XGBoost 超参数网格**（3 列，仅 model_type === 'xgboost' 时显示）：
   - n_estimators (number)
   - max_depth (number)
   - learning_rate (number, step=0.01)
   - min_child_weight (number)
   - subsample (number, step=0.1)
   - colsample_bytree (number, step=0.1)

### 表格列调整

- 移除 `targets` 和 `params` 列
- 新增 `feature_fields`（显示前几个字段 + 总数）、`classification_horizons`、`classification_threshold` 列

## 数据流

```
用户编辑 → form 绑定扁平字段 → saveConfig() 提交到 API
  → POST/PUT /api/model-configs  → config_service.create/update → MongoDB
  → 返回完整 ModelConfig → 刷新表格
```

训练时从 config 读取 xgb_* 字段注入 XGBoostClassifier 初始化参数。
