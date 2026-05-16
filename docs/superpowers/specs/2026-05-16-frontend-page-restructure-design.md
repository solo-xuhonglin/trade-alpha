# 前端页面重构设计

## 背景

当前前端页面结构中：
- 训练功能在一个页面（`TrainingsView.vue`），既包含训练列表，也包含预测功能
- 回测功能在一个页面（`BacktestView.vue`），既包含回测发起，也包含历史记录
- 交易记录在独立页面（`TradeListView.vue`）

为了提高用户体验，需要将这些功能进行拆分和重组。

---

## 设计目标

1. **功能解耦**：将管理和记录分离到不同页面
2. **导航清晰**：使用嵌套菜单组织相关功能
3. **代码可维护**：重构后保持代码结构清晰

---

## 导航结构

| 菜单项 | 子菜单 | 路由 |
|--------|--------|------|
| 数据管理 | - | `/data` |
| 账户管理 | - | `/account-configs` |
| 策略管理 | - | `/strategies` |
| 模型管理 | - | `/models` |
| **训练** | 训练管理 | `/trainings/manage` |
| | 训练记录 | `/trainings/records` |
| **回测** | 回测管理 | `/backtest/manage` |
| | 回测记录 | `/backtest/records` |
| | 交易记录 | `/backtest/trades` |

---

## 页面变更

### 1. 新增页面

| 文件名 | 路由 | 功能 |
|--------|------|------|
| `TrainingManageView.vue` | `/trainings/manage` | 新建训练任务 |
| `TrainingRecordsView.vue` | `/trainings/records` | 查看训练历史（重命名自 `TrainingsView.vue`） |
| `BacktestManageView.vue` | `/backtest/manage` | 新建回测任务 |
| `BacktestRecordsView.vue` | `/backtest/records` | 查看回测历史（重命名自 `BacktestView.vue`） |
| `TradesView.vue` | `/backtest/trades` | 查看交易记录（移动自 `TradeListView.vue`） |

### 2. 删除页面

| 文件名 | 说明 |
|--------|------|
| `TrainingsView.vue` | 重命名为 `TrainingRecordsView.vue` |
| `BacktestView.vue` | 重命名为 `BacktestRecordsView.vue` |
| `TradeListView.vue` | 移动为 `TradesView.vue` |

### 3. 保留页面

| 文件名 | 路由 | 功能 |
|--------|------|------|
| `DataView.vue` | `/data` | 数据管理 |
| `AccountsPage.vue` | `/account-configs` | 账户管理 |
| `StrategyView.vue` | `/strategies` | 策略管理 |
| `ModelsView.vue` | `/models` | 模型管理 |

---

## API 模块重组

### 当前结构

```
src/api/
├── index.ts
├── data.ts
├── account.ts
├── strategy.ts
├── models.ts
├── trainings.ts
└── backtest.ts
```

### 新结构

```
src/api/
├── index.ts
├── data.ts
├── account.ts
├── strategy.ts
├── model.ts           # 模型配置
├── training.ts         # 训练管理 API
├── trainingRecord.ts    # 训练记录 API
├── backtest.ts         # 回测管理 API
├── backtestRecord.ts   # 回测记录 API
└── trade.ts           # 交易记录 API
```

---

## 页面功能详解

### 训练管理 (`/trainings/manage`)

**功能**：
- 选择模型配置
- 选择股票（多选）
- 设置时间范围（开始/结束日期）
- 触发训练
- 显示训练任务状态

### 训练记录 (`/trainings/records`)

**功能**（自原 `TrainingsView.vue`）：
- 训练列表（按配置筛选）
- 查看训练指标
- 使用训练模型预测
- 删除训练

### 回测管理 (`/backtest/manage`)

**功能**：
- 选择账户配置
- 选择训练结果
- 设置回测参数
- 触发回测
- 显示回测任务状态

### 回测记录 (`/backtest/records`)

**功能**（自原 `BacktestView.vue`）：
- 回测历史列表
- 查看回测结果（收益率、夏普比率等）
- 查看详情（配置快照、每日快照）

### 交易记录 (`/backtest/trades`)

**功能**（自原 `TradeListView.vue`）：
- 交易流水列表
- 按回测结果筛选

---

## 技术实现

### 1. 路由

使用 Vue Router 嵌套路由结构：

```typescript
const routes = [
  // ... 保留现有路由
  
  // 训练相关路由
  {
    path: '/trainings',
    redirect: '/trainings/manage',
    children: [
      {
        path: 'manage',
        name: 'TrainingManage',
        component: () => import('@/views/TrainingManageView.vue')
      },
      {
        path: 'records',
        name: 'TrainingRecords',
        component: () => import('@/views/TrainingRecordsView.vue')
      }
    ]
  },
  
  // 回测相关路由
  {
    path: '/backtest',
    redirect: '/backtest/manage',
    children: [
      {
        path: 'manage',
        name: 'BacktestManage',
        component: () => import('@/views/BacktestManageView.vue')
      },
      {
        path: 'records',
        name: 'BacktestRecords',
        component: () => import('@/views/BacktestRecordsView.vue')
      },
      {
        path: 'trades',
        name: 'BacktestTrades',
        component: () => import('@/views/TradesView.vue')
      }
    ]
  }
]
```

### 2. 导航菜单

使用 Vuetify 的 `v-list-group` 实现嵌套菜单：

```vue
<v-list>
  <v-list-item
    v-for="item in topLevelItems"
    :key="item.path"
    :to="item.path"
    :prepend-icon="item.icon"
    :title="item.title"
  />
  
  <v-list-group
    v-model="trainingExpanded"
    prepend-icon="mdi-chart-scatter-plot"
    title="训练"
  >
    <template v-slot:activator="{ props }">
      <v-list-item
        v-bind="props"
        :title="item.title"
      />
    </template>
    <v-list-item
      v-for="item in trainingItems"
      :key="item.path"
      :to="item.path"
      :title="item.title"
    />
  </v-list-group>
  
  <v-list-group
    v-model="backtestExpanded"
    prepend-icon="mdi-chart-line"
    title="回测"
  >
    <template v-slot:activator="{ props }">
      <v-list-item
        v-bind="props"
        :title="item.title"
      />
    </template>
    <v-list-item
      v-for="item in backtestItems"
      :key="item.path"
      :to="item.path"
      :title="item.title"
    />
  </v-list-group>
</v-list>
```

---

## 文件变更清单

| 操作 | 原文件 | 新文件 | 说明 |
|------|--------|--------|------|
| 重命名 | `src/views/TrainingsView.vue` | `src/views/TrainingRecordsView.vue` | |
| 重命名 | `src/views/BacktestView.vue` | `src/views/BacktestRecordsView.vue` | |
| 移动 | `src/views/TradeListView.vue` | `src/views/TradesView.vue` | |
| 新增 | - | `src/views/TrainingManageView.vue` | |
| 新增 | - | `src/views/BacktestManageView.vue` | |
| 修改 | `src/components/AppLayout.vue` | - | 导航菜单 |
| 修改 | `src/router/index.ts` | - | 路由配置 |
| 重构 | `src/api/trainings.ts` | `src/api/training.ts` + `src/api/trainingRecord.ts` | API 拆分 |
| 重构 | `src/api/backtest.ts` | `src/api/backtest.ts` + `src/api/backtestRecord.ts` + `src/api/trade.ts` | API 拆分 |

---

## 向后兼容性

- 现有页面功能保持不变，只是拆分到不同页面
- API 函数签名保持不变，只是拆分到不同模块

---

## 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 页面重命名导致 URL 失效 | 低 | 高 | 考虑添加重定向路由 |
| API 模块重组导致导入错误 | 中 | 中 | 逐个模块迁移，保留旧模块兼容 |

---

## 验收标准

- 所有原功能在新页面中正常工作
- 导航菜单可正确展开/收起
- 页面切换流畅
- 无控制台错误
