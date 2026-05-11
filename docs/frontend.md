# 前端设计

## 概述

Trade-Alpha 前端基于 Vue 3 + Vuetify 4 实现，提供数据管理、账户管理、策略管理、模型管理、训练记录、回测、交易记录等功能。

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
│   │   ├── backtest.ts        # 回测 API
│   │   ├── models.ts          # 模型配置 API
│   │   └── trainings.ts       # 训练 API
│   ├── components/             # 公共组件
│   │   └── AppLayout.vue      # 应用布局
│   ├── views/                  # 页面视图
│   │   ├── DataView.vue       # 数据管理
│   │   ├── AccountsPage.vue   # 账户管理
│   │   ├── StrategyView.vue   # 策略管理
│   │   ├── ModelsView.vue     # 模型管理
│   │   ├── TrainingsView.vue  # 训练记录
│   │   ├── BacktestView.vue   # 回测
│   │   └── TradeListView.vue  # 交易记录
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
│  策略管理   │        主内容区                  │  ← router-view
│  模型管理   │                                 │
│  训练记录   │                                 │
│  回测      │                                 │
│  交易记录   │                                 │
│            │                                 │
└────────────┴─────────────────────────────────┘
     ↑
  左侧导航 (v-navigation-drawer)
```

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
- 训练按钮：创建训练

**组件**:
- 数据表格：配置列表
- 弹窗表单：配置编辑
- 训练弹窗：选择股票和时间段

### 5. 训练记录 `/trainings`

**功能**:
- 查看训练记录列表
- 按模型配置筛选
- 查看训练指标（MSE、MAE）
- 预测按钮：使用训练模型预测

**组件**:
- 数据表格：训练记录
- 筛选下拉：按配置筛选
- 预测弹窗：选择股票并显示预测结果

### 6. 回测 `/backtest`

**功能**:
- 运行回测（必填：账户、策略、训练结果）
- 查看回测结果（含配置快照、每日快照、交易记录）
- 查看回测历史和详情

**组件**:
- 表单：回测参数（账户、策略、训练结果、股票、时间段）
- 结果卡片：收益率、回撤、夏普比率等
- 数据表格：回测历史
- 详情弹窗：查看配置快照、每日账户快照、交易记录

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
  is_downloaded: boolean
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

### 使用示例

```typescript
import { strategyApi } from '@/api/strategy'

// 获取策略列表
const strategies = await strategyApi.list()

// 创建策略
await strategyApi.create({
  name: 'MA20策略',
  type: 'ma',
  config: { ma_period: 20, threshold: 0.01 }
})
```

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
