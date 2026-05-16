# 前端页面重构实现计划

## 概述

根据设计文档，将前端页面拆分为「管理」和「记录」两部分，并重组 API 模块。

---

## 任务 1：创建回测管理页面

**文件**：`frontend/src/views/BacktestManageView.vue`

**内容**：
- 选择账户配置（dropdown）
- 选择训练结果（dropdown）
- 触发回测按钮
- 任务状态显示

**参考**：从 `BacktestRecordsView.vue`（原 `BacktestView.vue`）中提取回测发起相关代码

---

## 任务 2：创建训练管理页面

**文件**：`frontend/src/views/TrainingManageView.vue`

**内容**：
- 选择模型配置（dropdown）
- 选择股票（多选）
- 设置时间范围
- 触发训练按钮
- 任务状态显示

**参考**：从 `TrainingsView.vue` 中提取训练发起相关代码

---

## 任务 3：拆分 API 模块

### 3.1 重命名 `models.ts` → `model.ts`

**操作**：重命名文件，更新内部函数名

### 3.2 创建 `trainingRecord.ts`

**内容**：
```typescript
import { get, del } from './index'

export const getTrainingRecords = (params?: { model_config_id?: string }) =>
  get('/api/v1/trainings/', params)

export const deleteTraining = (id: string) =>
  del(`/api/v1/trainings/${id}`)

export const predictWithTraining = (id: string, data: PredictRequest) =>
  post(`/api/v1/trainings/${id}/predict`, data)
```

### 3.3 创建 `backtestRecord.ts`

**内容**：
```typescript
import { get, del } from './index'

export const getBacktestRecords = (params?: { account_config_id?: string }) =>
  get('/api/v1/backtests/', params)

export const getBacktestDetail = (id: string) =>
  get(`/api/v1/backtests/${id}`)

export const deleteBacktest = (id: string) =>
  del(`/api/v1/backtests/${id}`)
```

### 3.4 创建 `trade.ts`

**内容**：
```typescript
import { get } from './index'

export const getTrades = (params?: { backtest_id?: string }) =>
  get('/api/v1/trades/', params)
```

### 3.5 更新 `index.ts` 导出

移除已拆分到独立文件的函数导出

---

## 任务 4：更新路由配置

**文件**：`frontend/src/router/index.ts`

**操作**：
- 删除 `/trainings` 和 `/backtest` 的旧路由
- 添加嵌套路由结构

```typescript
{
  path: '/trainings',
  redirect: '/trainings/manage',
  children: [
    { path: 'manage', component: () => import('@/views/TrainingManageView.vue') },
    { path: 'records', component: () => import('@/views/TrainingRecordsView.vue') }
  ]
},
{
  path: '/backtest',
  redirect: '/backtest/manage',
  children: [
    { path: 'manage', component: () => import('@/views/BacktestManageView.vue') },
    { path: 'records', component: () => import('@/views/BacktestRecordsView.vue') },
    { path: 'trades', component: () => import('@/views/TradesView.vue') }
  ]
}
```

---

## 任务 5：更新导航菜单

**文件**：`frontend/src/components/AppLayout.vue`

**操作**：
- 使用 `v-list-group` 实现嵌套菜单
- 训练和回测改为可展开的分组菜单
- 交易记录移到回测分组下

---

## 任务 6：重命名/移动页面文件

| 操作 | 原文件 | 新文件 |
|------|--------|--------|
| 重命名 | `TrainingsView.vue` | `TrainingRecordsView.vue` |
| 重命名 | `BacktestView.vue` | `BacktestRecordsView.vue` |
| 移动 | `TradeListView.vue` | `TradesView.vue` |

---

## 任务 7：更新页面组件引用

**文件**：`TrainingRecordsView.vue`、`BacktestRecordsView.vue`、`TradesView.vue`

**操作**：
- 更新 API 导入路径
- 更新组件名称（如有引用）

---

## 任务 8：更新文档

**文件**：`docs/frontend.md`

**操作**：
- 更新页面路由说明
- 更新导航结构
- 更新 API 模块说明

---

## 执行顺序

1. 任务 3：拆分 API 模块（基础依赖）
2. 任务 1：创建回测管理页面
3. 任务 2：创建训练管理页面
4. 任务 6：重命名/移动页面文件
5. 任务 4：更新路由配置
6. 任务 5：更新导航菜单
7. 任务 7：更新页面组件引用
8. 任务 8：更新文档
9. 测试验证

---

## 验收标准

- [ ] 所有页面可正常访问
- [ ] 导航菜单可正确展开/收起
- [ ] 训练/回测可正常发起
- [ ] 历史记录可正常查看
- [ ] 交易记录可正常查看
- [ ] 无控制台错误
