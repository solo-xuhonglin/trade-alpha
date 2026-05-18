# 配置模块命名统一规范

## 目标

统一账户管理、策略管理、模型管理三个模块的命名规范，使代码命名、前端菜单、接口名称保持一致性和可读性。

## 现状分析

### 命名不一致问题

#### 前端

| 模块 | 菜单名称 | 文件名 | API 文件 |
|------|---------|--------|---------|
| 账户 | 账户管理 | AccountsPage.vue | account.ts |
| 策略 | 策略管理 | StrategyView.vue | strategy.ts |
| 模型 | 模型管理 | ModelsView.vue | model.ts |

#### 后端

| 模块 | DAO 文件 | 类名 | 路由文件 | 服务文件 |
|------|---------|------|---------|---------|
| 账户 | account_config.py | AccountConfig | account_config.py | account/service.py |
| 策略 | **strategy.py** | StrategyConfig | strategy_config.py | strategy/service.py |
| 模型 | model_config.py | ModelConfig | model_configs.py | predict/config_service.py |

**问题**：策略的 DAO 文件名为 `strategy.py`，与其他配置模块的命名不一致（应为 `strategy_config.py`）。

## 统一命名方案

### 命名原则

1. 所有配置模块统一使用 "配置" 命名
2. 文件命名、接口命名、显示命名保持一致
3. 使用 snake_case 风格命名文件
4. DAO 文件命名统一为 `xxx_config.py`

### 前端修改

#### 菜单命名
- 账户管理 → 账户配置
- 策略管理 → 策略配置
- 模型管理 → 模型配置

#### 文件重命名
```bash
# 账户配置
frontend/src/views/AccountsPage.vue → AccountConfigView.vue
frontend/src/api/account.ts → accountConfig.ts

# 策略配置
frontend/src/views/StrategyView.vue → StrategyConfigView.vue
frontend/src/api/strategy.ts → strategyConfig.ts

# 模型配置
frontend/src/views/ModelsView.vue → ModelConfigView.vue
frontend/src/api/model.ts → modelConfig.ts
```

#### API 文件内容修改
- TypeScript 接口类型名保持不变（如 `AccountConfig`, `Strategy`, `ModelConfig`）
- 函数名和导出名统一使用 camelCase

### 后端修改

#### DAO 文件重命名
```bash
# 策略配置
backend/src/trade_alpha/dao/strategy.py → strategy_config.py
```

#### 路由文件保持不变
- `account_config.py` → 保持
- `strategy_config.py` → 保持
- `model_configs.py` → 保持

#### 更新导入引用
需要更新以下文件中的导入：
- `backend/src/trade_alpha/dao/__init__.py`
- `backend/src/trade_alpha/strategy/service.py`
- `backend/src/trade_alpha/api/routers/strategy_config.py`
- 其他引用 `strategy.py` 的文件

### 数据库集合名保持不变

保持现有集合名，避免数据迁移：
- `account_configs`
- `strategy_configs`
- `model_configs`

## 实施步骤

### 1. 后端 DAO 文件重命名

```bash
git mv backend/src/trade_alpha/dao/strategy.py backend/src/trade_alpha/dao/strategy_config.py
```

### 2. 更新后端导入引用

#### `backend/src/trade_alpha/dao/__init__.py`
```python
# 修改导入路径
from trade_alpha.dao.strategy_config import StrategyConfig
```

#### `backend/src/trade_alpha/strategy/service.py`
```python
# 修改导入路径
from trade_alpha.dao import StrategyConfig
```

#### `backend/src/trade_alpha/api/routers/strategy_config.py`
```python
# 检查并确保导入正确
from trade_alpha.dao import StrategyConfig
```

### 3. 前端 API 文件重命名和内容更新

#### accountConfig.ts
```typescript
// 重命名：account.ts → accountConfig.ts
import api from './index'

export interface AccountConfig {
  id: string
  name: string
  initial_capital: number
  cash: number
  position: number
  buy_fee_rate: number
  sell_fee_rate: number
  stamp_tax_rate: number
  min_fee: number
  created_at: string
  updated_at?: string
}

export const accountConfigApi = {
  list: () => api.get<AccountConfig[]>('/account-configs'),
  get: (id: string) => api.get<AccountConfig>(`/account-configs/${id}`),
  create: (data: Partial<AccountConfig>) => api.post<AccountConfig>('/account-configs', data),
  update: (id: string, data: Partial<AccountConfig>) => api.put(`/account-configs/${id}`, data),
  delete: (id: string) => api.delete(`/account-configs/${id}`),
}
```

#### strategyConfig.ts
```typescript
// 重命名：strategy.ts → strategyConfig.ts
import api from './index'

export interface Strategy {
  id: string
  name: string
  type: string
  min_order_value: number
  stop_loss_pct: number
  max_hold_days: number
  max_positions?: number
  max_position_pct?: number
  created_at: string
  updated_at?: string
}

export const strategyConfigApi = {
  list: () => api.get<Strategy[]>('/strategies'),
  get: (id: string) => api.get<Strategy>(`/strategies/${id}`),
  create: (data: Partial<Strategy>) => api.post<Strategy>('/strategies', data),
  update: (id: string, data: Partial<Strategy>) => api.put(`/strategies/${id}`, data),
  delete: (id: string) => api.delete(`/strategies/${id}`),
}
```

#### modelConfig.ts
```typescript
// 重命名：model.ts → modelConfig.ts
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

export const modelConfigApi = {
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

### 4. 前端视图文件重命名和内容更新

#### AccountConfigView.vue
```vue
<!-- 重命名：AccountsPage.vue → AccountConfigView.vue -->
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { accountConfigApi, type AccountConfig } from '@/api/accountConfig'
// ... 其余保持不变
</script>
```

#### StrategyConfigView.vue
```vue
<!-- 重命名：StrategyView.vue → StrategyConfigView.vue -->
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { strategyConfigApi, type Strategy } from '@/api/strategyConfig'
// ... 其余保持不变
</script>
```

#### ModelConfigView.vue
```vue
<!-- 重命名：ModelsView.vue → ModelConfigView.vue -->
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { modelConfigApi, type ModelConfig } from '@/api/modelConfig'
// ... 其余保持不变
</script>
```

### 5. 更新视图文件中的标题

将所有视图文件中的标题从"管理"改为"配置"：

#### AccountConfigView.vue
```vue
<v-toolbar-title>
  <v-icon color="medium-emphasis" icon="mdi-wallet" size="x-small" start></v-icon>
  账户配置  <!-- 原为：账户管理 -->
</v-toolbar-title>
```

#### StrategyConfigView.vue
```vue
<v-toolbar-title>
  <v-icon color="medium-emphasis" icon="mdi-strategy" size="x-small" start></v-icon>
  策略配置  <!-- 原为：策略管理 -->
</v-toolbar-title>
```

#### ModelConfigView.vue
```vue
<v-toolbar-title>
  <v-icon color="medium-emphasis" icon="mdi-brain" size="x-small" start></v-icon>
  模型配置  <!-- 原为：模型配置（已正确）-->
</v-toolbar-title>
```

### 6. 菜单配置更新

修改 `frontend/src/components/AppLayout.vue`：

```typescript
const configItems = [
  { path: '/account-configs', title: '账户配置' },    // 原为：账户管理
  { path: '/strategies', title: '策略配置' },        // 原为：策略管理
  { path: '/models', title: '模型配置' },            // 原为：模型管理
]
```

## 影响范围

### 需要修改的文件

**前端 (10 个文件)：**
1. `frontend/src/api/account.ts` → `accountConfig.ts`
2. `frontend/src/api/strategy.ts` → `strategyConfig.ts`
3. `frontend/src/api/model.ts` → `modelConfig.ts`
4. `frontend/src/views/AccountsPage.vue` → `AccountConfigView.vue`
5. `frontend/src/views/StrategyView.vue` → `StrategyConfigView.vue`
6. `frontend/src/views/ModelsView.vue` → `ModelConfigView.vue`
7. `frontend/src/components/AppLayout.vue` - 更新菜单标题

**后端 (4 个文件)：**
1. `backend/src/trade_alpha/dao/strategy.py` → `strategy_config.py`
2. `backend/src/trade_alpha/dao/__init__.py` - 更新导入
3. `backend/src/trade_alpha/strategy/service.py` - 更新导入（如需要）
4. `backend/src/trade_alpha/api/routers/strategy_config.py` - 更新导入（如需要）

### 需要更新导入的文件

检查以下文件中是否直接导入了上述文件：
- 其他视图文件中的下拉框数据加载（如训练、回测页面）
- 测试文件
- 其他使用这些 API 的地方

## 测试计划

1. **手动测试**：
   - 访问各配置页面，确认数据加载正常
   - 测试新建、编辑、删除功能
   - 检查下拉框数据显示

2. **回归测试**：
   - 训练和回测功能，确保下拉框数据加载正常
   - 其他依赖配置数据的页面

## 回滚计划

如需回滚，使用 `git checkout` 恢复到修改前状态：

```bash
git checkout <commit-hash>
```

## 优先级

- 高优先级：后端 DAO 文件重命名和导入更新
- 高优先级：前端 API 文件和视图文件重命名
- 中优先级：菜单文本更新
- 低优先级：文档更新（如 README.md）

## 备注

- 保持现有接口和字段不变，仅修改命名
- 数据库集合名和字段名保持不变
- 后端 API 路由保持不变
- 确保 TypeScript 类型定义正确
