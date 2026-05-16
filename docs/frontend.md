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
│   │   ├── account.ts         # 账户 API
│   │   ├── strategy.ts        # 策略 API
│   │   ├── model.ts           # 模型配置 API
│   │   ├── training.ts         # 训练管理 API
│   │   ├── trainingRecord.ts    # 训练记录 API
│   │   ├── backtest.ts         # 回测管理 API
│   │   ├── backtestRecord.ts   # 回测记录 API
│   │   └── trade.ts           # 交易记录 API
│   ├── components/             # 公共组件
│   │   └── AppLayout.vue      # 应用布局
│   ├── views/                  # 页面视图
│   │   ├── DataView.vue       # 数据管理
│   │   ├── AccountsPage.vue   # 账户管理
│   │   ├── StrategyView.vue   # 策略管理
│   │   ├── ModelsView.vue     # 模型管理
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
│   └── main.ts                 # 入口文件
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
│  账户管理   │                                 │
│  策略管理   │                                 │
│  模型管理   │        主内容区                  │  ← router-view
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
| `/account-configs` | 账户管理 | 账户配置 |
| `/strategies` | 策略管理 | 策略配置 |
| `/models` | 模型管理 | 模型配置 |
| `/trainings/manage` | 训练管理 | 发起训练任务 |
| `/trainings/records` | 训练记录 | 查看训练历史 |
| `/backtest/manage` | 回测管理 | 发起回测任务 |
| `/backtest/records` | 回测记录 | 查看回测历史 |
| `/backtest/trades` | 交易记录 | 查看交易流水 |

## 页面设计

### 1. 数据管理 `/data`

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

### 2. 账户管理 `/account-configs`

**功能**:
- 查看账户列表
- 创建/编辑/删除账户

**组件**:
- 数据表格：账户列表
- 弹窗表单：账户编辑

### 3. 策略管理 `/strategies`

**功能**:
- 查看策略列表
- 创建/编辑/删除策略
- 动态配置字段（根据策略类型）

**组件**:
- 数据表格：策略列表
- 弹窗表单：策略编辑
- 动态表单字段

### 4. 模型管理 `/models`

**功能**:
- 查看模型配置列表
- 创建/编辑/删除模型配置
- 支持 linear、xgboost、lstm 三种模型类型
- 动态参数表单（根据模型类型显示不同参数）
- 训练按钮：跳转至训练管理页面

**组件**:
- 数据表格：配置列表
- 弹窗表单：配置编辑

### 5. 训练管理 `/trainings/manage`

**功能**:
- 选择模型配置
- 选择股票（通过市值排名范围）
- 设置时间范围和训练名称（默认 `training_YYYYMMDDHHmmss`）
- 发起训练
- 查看运行中的任务状态

**组件**:
- 表单：选择配置、输入名称和时间范围
- 任务列表：运行中的训练任务

### 6. 训练记录 `/trainings/records`

**功能**:
- 查看训练记录列表
- 按模型配置筛选
- 查看训练指标（MSE、MAE）
- 预测按钮：使用训练模型预测
- 删除训练记录

**组件**:
- 数据表格：训练记录
- 筛选下拉：按配置筛选
- 预测弹窗：选择股票并显示预测结果

### 7. 回测管理 `/backtest/manage`

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

### 8. 回测记录 `/backtest/records`

**功能**:
- 查看回测历史列表
- 查看回测结果详情（收益率、夏普比率等）
- 查看交易记录
- 删除回测记录

**组件**:
- 数据表格：回测历史
- 详情弹窗：回测指标
- 交易记录弹窗

### 9. 交易记录 `/backtest/trades`

**功能**:
- 查看交易流水列表
- 按账户、策略、训练、股票筛选

**组件**:
- 数据表格：交易流水
- 筛选下拉：多维度筛选

## API 封装

### 基础配置

```typescript
// src/api/index.ts
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

export default api
```

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
| 账户 | `account.ts` | 账户配置 CRUD |
| 策略 | `strategy.ts` | 策略配置 CRUD |
| 模型 | `model.ts` | 模型配置 CRUD |
| 训练管理 | `training.ts` | 发起训练、任务状态 |
| 训练记录 | `trainingRecord.ts` | 训练列表、预测、删除 |
| 回测管理 | `backtest.ts` | 发起回测、任务状态 |
| 回测记录 | `backtestRecord.ts` | 回测列表、详情、删除 |
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
