# 前端设计

## 概述

Trade-Alpha 前端基于 Vue 3 + Vuetify 4 实现，提供数据管理、账户管理、策略管理、模型管理、训练管理、回测管理、交易记录等功能。

## 技术栈

| 技术 | 版本 | 用途 |
|-----|------|------|
| Vue | 3.x | 前端框架 |
| TypeScript | 5.x | 类型安全 |
| Vuetify | 4.x | UI 组件库 |
| Vue Router | 4.x | 路由管理 |
| Vite | 6.x | 构建工具 |
| Axios | 1.x | HTTP 客户端 |
| ECharts | 5.x | 图表库 |

## 项目结构

```
frontend/
├── src/
│   ├── api/                    # API 调用封装
│   │   ├── index.ts           # Axios 实例配置
│   │   ├── data.ts            # 数据 API
│   │   ├── accountConfig.ts   # 账户配置 API
│   │   ├── strategyConfig.ts  # 策略配置 API
│   │   ├── modelConfig.ts     # 模型配置 API
│   │   ├── training.ts         # 训练管理 API
│   │   ├── trainingRecord.ts    # 训练记录 API
│   │   ├── backtest.ts         # 回测管理 API
│   │   ├── backtestRecord.ts   # 回测记录 API
│   │   ├── dataAnalysis.ts     # 数据分析 API
│   │   └── trade.ts           # 交易记录 API
│   ├── components/             # 公共组件
│   │   └── AppLayout.vue      # 应用布局
│   ├── views/                  # 页面视图
│   │   ├── DataView.vue       # 数据管理
│   │   ├── DataAnalysisView.vue  # 数据分析
│   │   ├── AccountConfigView.vue   # 账户配置
│   │   ├── StrategyConfigView.vue  # 策略配置
│   │   ├── ModelConfigView.vue     # 模型配置
│   │   ├── TrainingManageView.vue     # 训练管理
│   │   ├── TrainingRecordsView.vue     # 训练记录
│   │   ├── BacktestManageView.vue     # 回测管理
│   │   ├── BacktestRecordsView.vue     # 回测记录
│   │   └── TradesView.vue     # 交易记录
│   ├── router/
│   │   └── index.ts           # 路由配置
│   ├── plugins/
│   │   └── vuetify.ts         # Vuetify 配置
│   ├── App.vue                 # 根组件
│   ├── main.ts                 # 入口文件
│   └── utils/
│       └── notify.ts           # 全局通知服务
├── index.html
├── package.json
├── tsconfig.json
├── tsconfig.app.json
└── vite.config.ts
```

## 布局设计

采用左侧导航 + 主内容区布局：

```
┌──────────────────────────────────────────────┐
│  Trade-Alpha                                │  ← 顶部栏 (v-app-bar)
├────────────┬─────────────────────────────────┤
│            │                                 │
│  数据管理   │                                 │
│  数据分析   │                                 │
│  账户配置   │                                 │
│  策略配置   │                                 │
│  模型配置   │        主内容区                  │  ← router-view
│  ▼ 训练    │                                 │
│    训练管理 │                                 │
│    训练记录 │                                 │
│  ▼ 回测    │                                 │
│    回测管理 │                                 │
│    回测记录 │                                 │
│    交易记录 │                                 │
│            │                                 │
└────────────┴─────────────────────────────────┘
     ↑
  左侧导航 (v-navigation-drawer)
```

## 路由配置

| 路由 | 页面 | 说明 |
|------|------|------|
| `/data` | 数据管理 | 股票列表、数据下载 |
| `/data-analysis` | 数据分析 | 数据特征分析、统计图表 |
| `/account-configs` | 账户配置 | 账户配置 |
| `/strategies` | 策略配置 | 策略配置 |
| `/models` | 模型配置 | 模型配置 |
| `/trainings/manage` | 训练管理 | 发起训练任务 |
| `/trainings/records` | 训练记录 | 查看训练历史 |
| `/backtest/manage` | 回测管理 | 发起回测任务 |
| `/backtest/records` | 回测记录 | 查看回测历史 |
| `/backtest/trades` | 交易记录 | 查看交易流水 |

## 页面设计

### 1. 数据分析 `/data-analysis`

**功能**:
- 查看数据分析历史列表
- 发起新的数据分析任务（选择股票、时间范围、特征字段）
- 查看数据分析结果（统计指标、直方图、箱线图、缺失值分析）
- 删除分析结果

**统计指标展示**:
- 均值、标准差、中位数、四分位数
- 最小值、最大值
- 缺失率
- 异常值率

**图表展示**:
- **直方图**：展示特征值分布（bins）
- **箱线图**：展示特征的四分位数、异常值

**详情面板**（3个标签页）:
- **统计**：表格展示所有特征的统计指标
- **直方图**：所有特征的直方图图表
- **箱线图**：所有特征的箱线图图表（更大尺寸）

**组件**:
- 数据分析历史表格
- 发起任务表单（选择股票、时间范围、特征）
- 运行中的任务状态列表
- 详情弹窗：3标签页展示完整分析结果
- 删除确认对话框

### 2. 数据管理 `/data`

**功能**:
- 查看 A 股股票列表（按市值降序）
- 更新股票列表
- 下载股票数据
- 查看 K 线图
- 删除股票数据

**组件**:
- 服务端分页表格：股票列表（v-data-table-server）
- 下载对话框：选择日期范围
- 弹窗：ECharts K 线图
- 删除确认对话框

### 3. 账户配置 `/account-configs`

**功能**:
- 查看账户列表
- 创建/编辑/删除账户

**组件**:
- 数据表格：账户列表
- 弹窗表单：账户编辑

### 4. 策略配置 `/strategies`

**功能**:
- 查看策略列表
- 创建/编辑/删除策略
- 组合模式：基础参数 + 排名优化（动量加成/趋势加分/波动扣分/暴涨排除四个独立开关）
- 策略回测列表显示状态 chip（动量加成/趋势加分/波动扣分启用标记）

**组件**:
- 数据表格：策略列表
- 弹窗表单：策略编辑（基础配置 tab + 排名优化 tab）
- 动态表单字段

### 5. 模型配置 `/models`

**功能**:
- 查看模型配置列表
- 创建/编辑/删除模型配置
- 支持 xgboost、lstm 两种模型类型
- 动态参数表单（根据模型类型显示不同参数）
- 训练按钮：跳转至训练管理页面

**组件**:
- 数据表格：配置列表
- 弹窗表单：配置编辑

### 6. 训练管理 `/trainings/manage`

**功能**:
- 选择模型配置
- 选择股票（通过市值排名范围）
- 设置时间范围和训练名称（默认 `training_YYYYMMDDHHmmss`）
- 发起训练
- 查看运行中的任务状态

**组件**:
- 表单：选择配置、输入名称和时间范围
- 任务列表：运行中的训练任务

### 7. 训练记录 `/trainings/records`

**功能**:
- 查看训练记录列表
- 按模型配置筛选
- 查看训练指标（准确率、CV分数）
- 详情按钮：查看完整训练评估指标
- 预测按钮：使用训练模型预测
- 删除训练记录

**训练评估指标**:
- `sample_count`：训练样本数
- `accuracy`：各目标（label_3d/label_5d）的分类准确率
- `auc`：各目标（label_3d/label_5d）的 AUC 指标（仅 LSTM 模型）
- `final_train_loss`：LSTM 最终训练 loss（仅 LSTM 模型）
- `loss_per_epoch`：LSTM 每 epoch 的训练 loss 列表（仅 LSTM 模型）
- `val_loss_per_epoch`：LSTM 每 epoch 的验证 loss 列表（仅 LSTM 模型）
- `val_auc_per_epoch`：LSTM 每 epoch 的验证 AUC 列表（仅 LSTM 模型）
- `actual_epochs`：实际训练的 epoch 数（仅 LSTM 模型）
- `early_stopped`：是否触发早停（仅 LSTM 模型）
- `best_epoch`：最佳模型所在的 epoch（仅 LSTM 模型）
- `best_auc`：最佳验证 AUC 值（仅 LSTM 模型）
- `feature_importance`：各特征的重要性排名（仅 XGBoost 模型）
- `class_distribution`：类别（-1/0/1）的分布比例

**详情面板**（条件显示标签页）:
- **概览**：样本数、准确率卡片、类别分布、早停信息（仅 LSTM）
- **准确率**：训练准确率表格
- **特征重要性**：仅 XGBoost 模型显示，所有特征的重要性进度条（按重要性排序）
- **训练Loss**：仅 LSTM 模型显示，表格化展示 Train Loss、Val Loss 和 Val AUC，包含最佳 AUC 信息

**前端改进**:
1. **条件标签页显示**：根据模型类型只显示相关标签页
2. **训练损失表格化**：LSTM 训练详情使用表格展示，更清晰易读
3. **回测指标样式优化**：移除回测结果的加粗样式，界面更加简洁
4. **交易筛选器重新排序**：训练结果筛选器移到回测结果之前

**组件**:
- 数据表格：训练记录
- 筛选下拉：按配置筛选
- 详情弹窗：4标签页展示完整评估指标
- 预测弹窗：选择股票并显示预测结果

### 8. 回测管理 `/backtest/manage`

**功能**:
- 选择账户配置、训练结果
- 选择策略配置（自动推断单股票/组合模式）
- 设置时间范围（默认 2025 年全年）
- 输入回测名称（默认 `backtest_YYYYMMDDHHmmss`）
- 单股票模式输入股票代码，组合模式输入最大持仓数
- 发起回测
- 查看运行中的任务状态

**组件**:
- 表单：选择参数
- 任务列表：运行中的回测任务

### 9. 回测记录 `/backtest/records`

**功能**:
- 查看回测历史列表
- 查看回测详情（收益指标、账户配置、策略配置、模型配置、特征配置）
- 查看交易记录
- 查看预测分析（K线 + 评分趋势）

**组件**:
- 数据表格：回测历史
- 详情弹窗：5标签页（账户配置/策略配置/模型配置/特征配置）
- 交易记录弹窗
- 预测分析弹窗：左右布局（md=3 + md=9）
  - 左侧：股票下拉框（按平均综合评分降序）、方向准确率、关键指标（平均分/排名/交易盈亏）
  - 右侧：ECharts K线图 + 评分曲线 + 排名曲线
  - 悬浮提示：显示趋势加分/波动扣分/动量加成明细 + 综合分 + 排名

### 10. 交易记录 `/backtest/trades`

**功能**:
- 查看交易流水列表
- 按账户、策略、训练、股票筛选

**组件**:
- 数据表格：交易流水
- 筛选下拉：多维度筛选

## API 封装

### 基础配置与全局错误处理

```typescript
// src/api/index.ts
import axios, { AxiosError } from 'axios'
import type { ApiErrorResponse } from './types'
import { notifyService } from '@/utils/notify'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorResponse>) => {
    let errorMessage = '请求失败，请稍后重试'
    
    if (error.response) {
      const { data, status } = error.response
      
      if (data?.error?.message) {
        errorMessage = data.error.message
      } else {
        switch (status) {
          case 400: errorMessage = '请求参数错误'; break
          case 401: errorMessage = '未授权，请重新登录'; break
          case 403: errorMessage = '无权限访问'; break
          case 404: errorMessage = '资源不存在'; break
          case 409: errorMessage = '资源冲突'; break
          case 422: errorMessage = '数据验证失败'; break
          case 500: errorMessage = '服务器内部错误'; break
          default: errorMessage = `请求失败 (${status})`
        }
      }
    } else if (error.request) {
      errorMessage = '网络连接失败，请检查网络'
    } else {
      errorMessage = error.message || '请求失败'
    }
    
    notifyService.error(errorMessage)
    return Promise.reject(error)
  }
)

export default api
```

**错误响应格式**（与后端统一）：
```typescript
// src/api/types.ts
export interface ApiErrorDetail {
  code: string
  message: string
  fields?: Record<string, string>
}

export interface ApiErrorResponse {
  success: false
  error: ApiErrorDetail
}

export interface ApiSuccessResponse<T> {
  success: true
  data: T
}
```

### 全局通知服务

```typescript
// src/utils/notify.ts
export interface Notification {
  id: number
  message: string
  type: 'success' | 'error' | 'info' | 'warning'
  duration?: number
}

export const notifyService = {
  success(message: string, duration?: number): number
  error(message: string, duration?: number): number
  info(message: string, duration?: number): number
  warning(message: string, duration?: number): number
}
```

**使用方式**：
```typescript
// 在组件中
notifyService.success('操作成功')
notifyService.error('操作失败')
```

**特性**：
- 自动显示在页面顶部
- 支持自动关闭（默认5秒）
- 支持手动关闭
- 自动处理重复消息

### 数据 API

```typescript
// src/api/data.ts
export interface Stock {
  ts_code: string
  name: string
  industry?: string
  market?: string
  total_mv?: number
  pe?: number
  pb?: number
  sync_status: string
  data_count?: number
  latest_date?: string
}

export interface StockListResponse {
  items: Stock[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export const dataApi = {
  listStocks: (page = 1, pageSize = 20) =>
    api.get<StockListResponse>('/data/stocks', { params: { page, page_size: pageSize } }),
  updateStocks: () => api.post('/data/stocks/update'),
  getData: (tsCode: string) => api.get(`/data/${tsCode}`),
  fetchData: (tsCode: string, startDate: string, endDate: string) =>
    api.post('/data', { ts_code: tsCode, start_date: startDate, end_date: endDate }),
  deleteData: (tsCode: string) => api.delete(`/data/${tsCode}`),
}
```

### API 模块说明

| 模块 | 文件 | 功能 |
|------|------|------|
| 数据 | `data.ts` | 股票列表、数据下载 |
| 账户配置 | `accountConfig.ts` | 账户配置 CRUD |
| 策略配置 | `strategyConfig.ts` | 策略配置 CRUD |
| 模型配置 | `modelConfig.ts` | 模型配置 CRUD |
| 训练管理 | `training.ts` | 发起训练、任务状态 |
| 训练记录 | `trainingRecord.ts` | 训练列表、预测、删除 |
| 回测管理 | `backtest.ts` | 发起回测、任务状态 |
| 回测记录 | `backtestRecord.ts` | 回测列表、详情、删除 |
| 数据分析 | `dataAnalysis.ts` | 数据分析任务、结果列表 |
| 交易 | `trade.ts` | 交易流水列表 |

## 开发配置

### Vite 代理

开发时通过代理转发 API 请求：

```typescript
// vite.config.ts
export default defineConfig({
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
})
```

### TypeScript 配置

路径别名配置：

```json
// tsconfig.app.json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  }
}
```

## 启动命令

```bash
# 安装依赖
cd frontend
npm install

# 开发模式
npm run dev

# 构建生产版本
npm run build

# 预览生产版本
npm run preview
```

## 构建产物

构建后生成 `dist/` 目录：

```
dist/
├── index.html
├── assets/
│   ├── index-xxx.js
│   └── index-xxx.css
└── ...
```

生产部署时，将 `dist/` 目录部署到 Web 服务器，或由后端 FastAPI 托管。
