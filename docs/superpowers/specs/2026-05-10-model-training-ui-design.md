# 模型配置和训练页面设计

## 概述

为 trade-alpha 前端新增模型配置和训练管理页面，与现有架构保持一致。

## 页面结构

| 路由 | 页面 | 说明 |
|-----|------|------|
| `/models` | ModelsView.vue | 模型配置管理 |
| `/trainings` | TrainingsView.vue | 训练结果管理 |

## 功能设计

### 模型配置页面 (/models)

- **列表**：显示配置名称、模型类型、参数、预测目标
- **操作**：创建、编辑、删除、训练按钮
- **创建/编辑对话框**：
  - 名称（文本输入）
  - 模型类型（选择：linear, xgboost, lstm）
  - 预测目标（多选复选框：open, close, high, low）
  - 参数（根据模型类型动态显示）
    - linear: fit_intercept (开关)
    - xgboost: n_estimators, max_depth, learning_rate
    - lstm: epochs, batch_size, units

### 训练页面 (/trainings)

- **列表**：显示名称、配置名称、股票、日期范围、样本数、MSE/MAE指标
- **操作**：删除、预测按钮
- **筛选**：下拉选择按模型配置筛选（从 `/api/model-configs` 获取选项）
- **预测对话框**：
  - 股票选择（可选，不选则用训练时的第一只）
  - 显示预测结果

## 菜单配置

AppLayout.vue 导航栏新增：
```typescript
{ path: '/models', title: '模型管理', icon: 'mdi-brain' },
{ path: '/trainings', title: '训练记录', icon: 'mdi-chart-scatter-plot' },
```

## API 调用

### models API (api/models.ts)
- `POST /api/model-configs` - 创建配置
- `GET /api/model-configs` - 获取列表
- `GET /api/model-configs/{id}` - 获取详情
- `PUT /api/model-configs/{id}` - 更新配置
- `DELETE /api/model-configs/{id}` - 删除配置

### trainings API (api/trainings.ts)
- `POST /api/trainings` - 创建训练
- `GET /api/trainings` - 获取列表
- `GET /api/trainings/{id}` - 获取详情
- `DELETE /api/trainings/{id}` - 删除训练
- `POST /api/trainings/{id}/predict` - 预测

## 实现顺序

1. API 客户端模块 (models.ts, trainings.ts)
2. 路由配置
3. 菜单配置
4. ModelsView.vue 页面
5. TrainingsView.vue 页面
6. E2E 测试
