# 前端实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建 Vue 3 + Vuetify 4 前端界面，提供数据管理、账户管理、策略管理、回测、交易记录功能

**Architecture:** 前端独立项目目录 `frontend/`，通过 Axios 调用后端 FastAPI，Vue Router 管理路由

**Tech Stack:** Vue 3, TypeScript, Vuetify 4, Vue Router 4, Vite, Axios, ECharts

---

## 文件结构

```
frontend/
├── src/
│   ├── api/                    # API 调用封装
│   │   ├── index.ts
│   │   ├── data.ts
│   │   ├── portfolio.ts
│   │   ├── strategy.ts
│   │   └── backtest.ts
│   ├── components/             # 公共组件
│   │   └── AppLayout.vue
│   ├── views/                  # 页面视图
│   │   ├── DataView.vue
│   │   ├── PortfolioView.vue
│   │   ├── StrategyView.vue
│   │   ├── BacktestView.vue
│   │   └── TradesView.vue
│   ├── router/
│   │   └── index.ts
│   ├── App.vue
│   └── main.ts
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── .env.development
```

---

## Task 1: 创建前端项目

- [ ] **Step 1: 创建 frontend 目录**

Run: `mkdir -p d:/projects/trade-alpha/frontend`

- [ ] **Step 2: 初始化 Vue 3 + TypeScript 项目**

Run: `cd d:/projects/trade-alpha/frontend; npm create vite@latest . -- --template vue-ts`
Expected: Project created

- [ ] **Step 3: 安装依赖**

Run: `cd d:/projects/trade-alpha/frontend; npm install`
Expected: Dependencies installed

---

## Task 2: 安装 Vuetify 4 和其他依赖

- [ ] **Step 1: 安装 Vuetify 4**

Run: `cd d:/projects/trade-alpha/frontend; npm install vuetify@next @mdi/font`
Expected: Vuetify installed

- [ ] **Step 2: 安装 Vue Router 和 Axios**

Run: `cd d:/projects/trade-alpha/frontend; npm install vue-router@4 axios echarts vue-echarts`
Expected: Packages installed

---

## Task 3: 配置 Vuetify 和 Vite

**Files:**
- Create: `frontend/src/plugins/vuetify.ts`
- Modify: `frontend/vite.config.ts`

- [ ] **Step 1: 创建 Vuetify 插件**

```typescript
// src/plugins/vuetify.ts
import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'

export const vuetify = createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: 'light',
  },
})
```

- [ ] **Step 2: 更新 main.ts**

```typescript
// src/main.ts
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { vuetify } from './plugins/vuetify'

const app = createApp(App)
app.use(router)
app.use(vuetify)
app.mount('#app')
```

- [ ] **Step 3: 更新 vite.config.ts**

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
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

---

## Task 4: 创建路由配置

**Files:**
- Create: `frontend/src/router/index.ts`

- [ ] **Step 1: 创建路由**

```typescript
// src/router/index.ts
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/data'
  },
  {
    path: '/data',
    name: 'Data',
    component: () => import('@/views/DataView.vue')
  },
  {
    path: '/portfolios',
    name: 'Portfolios',
    component: () => import('@/views/PortfolioView.vue')
  },
  {
    path: '/strategies',
    name: 'Strategies',
    component: () => import('@/views/StrategyView.vue')
  },
  {
    path: '/backtest',
    name: 'Backtest',
    component: () => import('@/views/BacktestView.vue')
  },
  {
    path: '/trades',
    name: 'Trades',
    component: () => import('@/views/TradesView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
```

---

## Task 5: 创建布局组件

**Files:**
- Create: `frontend/src/components/AppLayout.vue`

- [ ] **Step 1: 创建 AppLayout.vue**

```vue
<template>
  <v-app>
    <v-app-bar color="primary" density="compact">
      <v-app-bar-title>Trade-Alpha</v-app-bar-title>
    </v-app-bar>

    <v-navigation-drawer permanent>
      <v-list nav>
        <v-list-item
          v-for="item in menuItems"
          :key="item.path"
          :to="item.path"
          :prepend-icon="item.icon"
          :title="item.title"
        />
      </v-list>
    </v-navigation-drawer>

    <v-main>
      <v-container fluid>
        <router-view />
      </v-container>
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
const menuItems = [
  { path: '/data', title: '数据管理', icon: 'mdi-database' },
  { path: '/portfolios', title: '账户管理', icon: 'mdi-wallet' },
  { path: '/strategies', title: '策略管理', icon: 'mdi-strategy' },
  { path: '/backtest', title: '回测', icon: 'mdi-chart-line' },
  { path: '/trades', title: '交易记录', icon: 'mdi-swap-horizontal' },
]
</script>
```

- [ ] **Step 2: 更新 App.vue**

```vue
<template>
  <AppLayout />
</template>

<script setup lang="ts">
import AppLayout from '@/components/AppLayout.vue'
</script>
```

---

## Task 6: 创建 API 封装

**Files:**
- Create: `frontend/src/api/index.ts`
- Create: `frontend/src/api/data.ts`
- Create: `frontend/src/api/portfolio.ts`
- Create: `frontend/src/api/strategy.ts`
- Create: `frontend/src/api/backtest.ts`

- [ ] **Step 1: 创建 API 基础配置**

```typescript
// src/api/index.ts
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

export default api
```

- [ ] **Step 2: 创建 data.ts**

```typescript
// src/api/data.ts
import api from './index'

export interface DataRecord {
  ts_code: string
  trade_date: string
  open: number
  high: number
  low: number
  close: number
  vol: number
  amount: number
  ma_5?: number
  ma_10?: number
  ma_20?: number
  ma_60?: number
  macd?: number
  macd_signal?: number
  macd_hist?: number
}

export const dataApi = {
  getData: (tsCode: string, startDate?: string, endDate?: string) =>
    api.get<DataRecord[]>(`/data/${tsCode}`, { params: { start_date: startDate, end_date: endDate } }),
  
  fetchData: (tsCode: string, startDate: string, endDate: string) =>
    api.post('/data', { ts_code: tsCode, start_date: startDate, end_date: endDate }),
  
  deleteData: (tsCode: string) =>
    api.delete(`/data/${tsCode}`),
}
```

- [ ] **Step 3: 创建 portfolio.ts**

```typescript
// src/api/portfolio.ts
import api from './index'

export interface Portfolio {
  id: string
  name: string
  initial_capital: number
  cash: number
  position: number
  buy_fee_rate: number
  sell_fee_rate: number
  stamp_tax_rate: number
  min_fee: number
}

export const portfolioApi = {
  list: () => api.get<Portfolio[]>('/portfolios'),
  get: (id: string) => api.get<Portfolio>(`/portfolios/${id}`),
  create: (data: Partial<Portfolio>) => api.post<Portfolio>('/portfolios', data),
  update: (id: string, data: Partial<Portfolio>) => api.put(`/portfolios/${id}`, data),
  delete: (id: string) => api.delete(`/portfolios/${id}`),
}
```

- [ ] **Step 4: 创建 strategy.ts**

```typescript
// src/api/strategy.ts
import api from './index'

export interface Strategy {
  id: string
  name: string
  type: string
  config: Record<string, any>
  created_at: string
}

export const strategyApi = {
  list: () => api.get<Strategy[]>('/strategies'),
  get: (id: string) => api.get<Strategy>(`/strategies/${id}`),
  create: (data: Partial<Strategy>) => api.post<Strategy>('/strategies', data),
  update: (id: string, data: Partial<Strategy>) => api.put(`/strategies/${id}`, data),
  delete: (id: string) => api.delete(`/strategies/${id}`),
}
```

- [ ] **Step 5: 创建 backtest.ts**

```typescript
// src/api/backtest.ts
import api from './index'

export interface Backtest {
  id: string
  portfolio_id?: string
  ts_code: string
  start_date: string
  end_date: string
  strategy: string
  initial_capital: number
  final_value: number
  total_return: number
  annual_return: number
  benchmark_return: number
  max_drawdown: number
  sharpe_ratio: number
  win_rate: number
  total_trades: number
  total_fees: number
}

export interface Trade {
  trade_date: string
  action: string
  price: number
  shares: number
  fee: number
  cash_after: number
  position_after: number
}

export const backtestApi = {
  list: (limit?: number) => api.get<Backtest[]>('/backtests', { params: { limit } }),
  get: (id: string) => api.get<Backtest>(`/backtests/${id}`),
  run: (data: { ts_code: string; start_date: string; end_date: string; strategy_id: string; portfolio_name?: string; initial_capital?: number }) =>
    api.post<Backtest>('/backtests', data),
  getTrades: (id: string) => api.get<Trade[]>(`/backtests/${id}/trades`),
  delete: (id: string) => api.delete(`/backtests/${id}`),
}
```

---

## Task 7: 创建数据管理页面

**Files:**
- Create: `frontend/src/views/DataView.vue`

- [ ] **Step 1: 创建 DataView.vue**

```vue
<template>
  <v-container>
    <v-card class="mb-4">
      <v-card-title>数据管理</v-card-title>
      <v-card-text>
        <v-row>
          <v-col cols="12" sm="4">
            <v-text-field v-model="newTsCode" label="股票代码" placeholder="000001.SZ" />
          </v-col>
          <v-col cols="12" sm="3">
            <v-text-field v-model="newStartDate" label="开始日期" placeholder="20240101" />
          </v-col>
          <v-col cols="12" sm="3">
            <v-text-field v-model="newEndDate" label="结束日期" placeholder="20241231" />
          </v-col>
          <v-col cols="12" sm="2">
            <v-btn color="primary" @click="fetchData" :loading="loading">下载</v-btn>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <v-card>
      <v-data-table :headers="headers" :items="stockList" :loading="loading">
        <template v-slot:item.actions="{ item }">
          <v-btn size="small" color="primary" variant="text" @click="viewChart(item)">查看</v-btn>
          <v-btn size="small" color="error" variant="text" @click="deleteStock(item)">删除</v-btn>
        </template>
      </v-data-table>
    </v-card>

    <v-dialog v-model="chartDialog" max-width="1200">
      <v-card>
        <v-card-title>{{ selectedStock }} K线图</v-card-title>
        <v-card-text>
          <div ref="chartRef" style="height: 500px;"></div>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="chartDialog = false">关闭</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { dataApi, type DataRecord } from '@/api/data'
import * as echarts from 'echarts'

const loading = ref(false)
const newTsCode = ref('')
const newStartDate = ref('')
const newEndDate = ref('')
const stockList = ref<{ ts_code: string; count: number; latest_date: string }[]>([])
const chartDialog = ref(false)
const selectedStock = ref('')
const chartRef = ref<HTMLElement>()
const stockData = ref<DataRecord[]>([])

const headers = [
  { title: '股票代码', key: 'ts_code' },
  { title: '数据条数', key: 'count' },
  { title: '最新日期', key: 'latest_date' },
  { title: '操作', key: 'actions', sortable: false },
]

const fetchData = async () => {
  if (!newTsCode.value || !newStartDate.value || !newEndDate.value) return
  loading.value = true
  try {
    await dataApi.fetchData(newTsCode.value, newStartDate.value, newEndDate.value)
    await loadStockList()
  } finally {
    loading.value = false
  }
}

const loadStockList = async () => {
  // 简化实现：从后端获取股票列表需要新增 API
  // 这里先硬编码测试
}

const viewChart = async (item: { ts_code: string }) => {
  selectedStock.value = item.ts_code
  chartDialog.value = true
  const res = await dataApi.getData(item.ts_code)
  stockData.value = res.data
  await nextTick()
  renderChart()
}

const renderChart = () => {
  if (!chartRef.value) return
  const chart = echarts.init(chartRef.value)
  const dates = stockData.value.map(d => d.trade_date)
  const data = stockData.value.map(d => [d.open, d.close, d.low, d.high])
  
  chart.setOption({
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', scale: true },
    series: [{
      type: 'candlestick',
      data: data,
    }],
  })
}

const deleteStock = async (item: { ts_code: string }) => {
  await dataApi.deleteData(item.ts_code)
  await loadStockList()
}

onMounted(() => {
  loadStockList()
})
</script>
```

---

## Task 8: 创建账户管理页面

**Files:**
- Create: `frontend/src/views/PortfolioView.vue`

- [ ] **Step 1: 创建 PortfolioView.vue**

```vue
<template>
  <v-container>
    <v-card>
      <v-card-title class="d-flex align-center">
        账户管理
        <v-spacer />
        <v-btn color="primary" @click="openDialog()">新建账户</v-btn>
      </v-card-title>
      <v-data-table :headers="headers" :items="portfolios" :loading="loading">
        <template v-slot:item.actions="{ item }">
          <v-btn size="small" variant="text" @click="openDialog(item)">编辑</v-btn>
          <v-btn size="small" color="error" variant="text" @click="deletePortfolio(item)">删除</v-btn>
        </template>
      </v-data-table>
    </v-card>

    <v-dialog v-model="dialog" max-width="500">
      <v-card>
        <v-card-title>{{ editingId ? '编辑账户' : '新建账户' }}</v-card-title>
        <v-card-text>
          <v-text-field v-model="form.name" label="账户名称" />
          <v-text-field v-model="form.initial_capital" label="初始资金" type="number" />
          <v-text-field v-model="form.buy_fee_rate" label="买入费率" type="number" />
          <v-text-field v-model="form.sell_fee_rate" label="卖出费率" type="number" />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="dialog = false">取消</v-btn>
          <v-btn color="primary" @click="savePortfolio">保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { portfolioApi, type Portfolio } from '@/api/portfolio'

const loading = ref(false)
const dialog = ref(false)
const portfolios = ref<Portfolio[]>([])
const editingId = ref<string | null>(null)
const form = ref({
  name: '',
  initial_capital: 100000,
  buy_fee_rate: 0.0003,
  sell_fee_rate: 0.0003,
  stamp_tax_rate: 0.001,
  min_fee: 5,
})

const headers = [
  { title: '名称', key: 'name' },
  { title: '初始资金', key: 'initial_capital' },
  { title: '当前现金', key: 'cash' },
  { title: '持仓', key: 'position' },
  { title: '操作', key: 'actions', sortable: false },
]

const loadPortfolios = async () => {
  loading.value = true
  try {
    const res = await portfolioApi.list()
    portfolios.value = res.data
  } finally {
    loading.value = false
  }
}

const openDialog = (item?: Portfolio) => {
  if (item) {
    editingId.value = item.id
    form.value = { ...item }
  } else {
    editingId.value = null
    form.value = { name: '', initial_capital: 100000, buy_fee_rate: 0.0003, sell_fee_rate: 0.0003, stamp_tax_rate: 0.001, min_fee: 5 }
  }
  dialog.value = true
}

const savePortfolio = async () => {
  if (editingId.value) {
    await portfolioApi.update(editingId.value, form.value)
  } else {
    await portfolioApi.create(form.value)
  }
  dialog.value = false
  await loadPortfolios()
}

const deletePortfolio = async (item: Portfolio) => {
  await portfolioApi.delete(item.id)
  await loadPortfolios()
}

onMounted(() => {
  loadPortfolios()
})
</script>
```

---

## Task 9: 创建策略管理页面

**Files:**
- Create: `frontend/src/views/StrategyView.vue`

- [ ] **Step 1: 创建 StrategyView.vue**

```vue
<template>
  <v-container>
    <v-card>
      <v-card-title class="d-flex align-center">
        策略管理
        <v-spacer />
        <v-btn color="primary" @click="openDialog()">新建策略</v-btn>
      </v-card-title>
      <v-data-table :headers="headers" :items="strategies" :loading="loading">
        <template v-slot:item.config="{ item }">
          <code>{{ JSON.stringify(item.config) }}</code>
        </template>
        <template v-slot:item.actions="{ item }">
          <v-btn size="small" variant="text" @click="openDialog(item)">编辑</v-btn>
          <v-btn size="small" color="error" variant="text" @click="deleteStrategy(item)">删除</v-btn>
        </template>
      </v-data-table>
    </v-card>

    <v-dialog v-model="dialog" max-width="500">
      <v-card>
        <v-card-title>{{ editingId ? '编辑策略' : '新建策略' }}</v-card-title>
        <v-card-text>
          <v-text-field v-model="form.name" label="策略名称" />
          <v-select v-model="form.type" :items="strategyTypes" label="策略类型" />
          <template v-if="form.type === 'price'">
            <v-text-field v-model.number="form.config.buy_threshold" label="买入阈值" type="number" step="0.01" />
            <v-text-field v-model.number="form.config.sell_threshold" label="卖出阈值" type="number" step="0.01" />
          </template>
          <template v-if="form.type === 'ma'">
            <v-text-field v-model.number="form.config.ma_period" label="MA周期" type="number" />
            <v-text-field v-model.number="form.config.threshold" label="阈值" type="number" step="0.01" />
          </template>
          <template v-if="form.type === 'macd'">
            <v-text-field v-model.number="form.config.threshold" label="阈值" type="number" step="0.1" />
          </template>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="dialog = false">取消</v-btn>
          <v-btn color="primary" @click="saveStrategy">保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { strategyApi, type Strategy } from '@/api/strategy'

const loading = ref(false)
const dialog = ref(false)
const strategies = ref<Strategy[]>([])
const editingId = ref<string | null>(null)
const strategyTypes = ['price', 'ma', 'macd']

const form = ref({
  name: '',
  type: 'price',
  config: {} as Record<string, any>,
})

const headers = [
  { title: '名称', key: 'name' },
  { title: '类型', key: 'type' },
  { title: '配置', key: 'config' },
  { title: '操作', key: 'actions', sortable: false },
]

const loadStrategies = async () => {
  loading.value = true
  try {
    const res = await strategyApi.list()
    strategies.value = res.data
  } finally {
    loading.value = false
  }
}

const openDialog = (item?: Strategy) => {
  if (item) {
    editingId.value = item.id
    form.value = { name: item.name, type: item.type, config: { ...item.config } }
  } else {
    editingId.value = null
    form.value = { name: '', type: 'price', config: {} }
  }
  dialog.value = true
}

const saveStrategy = async () => {
  if (editingId.value) {
    await strategyApi.update(editingId.value, form.value)
  } else {
    await strategyApi.create(form.value)
  }
  dialog.value = false
  await loadStrategies()
}

const deleteStrategy = async (item: Strategy) => {
  await strategyApi.delete(item.id)
  await loadStrategies()
}

onMounted(() => {
  loadStrategies()
})
</script>
```

---

## Task 10: 创建回测页面

**Files:**
- Create: `frontend/src/views/BacktestView.vue`

- [ ] **Step 1: 创建 BacktestView.vue**

```vue
<template>
  <v-container>
    <v-card class="mb-4">
      <v-card-title>运行回测</v-card-title>
      <v-card-text>
        <v-row>
          <v-col cols="12" sm="3">
            <v-text-field v-model="form.ts_code" label="股票代码" placeholder="000001.SZ" />
          </v-col>
          <v-col cols="12" sm="2">
            <v-text-field v-model="form.start_date" label="开始日期" placeholder="20240101" />
          </v-col>
          <v-col cols="12" sm="2">
            <v-text-field v-model="form.end_date" label="结束日期" placeholder="20241231" />
          </v-col>
          <v-col cols="12" sm="3">
            <v-select v-model="form.strategy_id" :items="strategies" item-title="name" item-value="id" label="策略" />
          </v-col>
          <v-col cols="12" sm="2">
            <v-btn color="primary" @click="runBacktest" :loading="running">运行</v-btn>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <v-card v-if="result">
      <v-card-title>回测结果</v-card-title>
      <v-card-text>
        <v-row>
          <v-col cols="6" sm="3">
            <div class="text-caption">总收益率</div>
            <div class="text-h5" :class="result.total_return >= 0 ? 'text-success' : 'text-error'">
              {{ (result.total_return * 100).toFixed(2) }}%
            </div>
          </v-col>
          <v-col cols="6" sm="3">
            <div class="text-caption">年化收益</div>
            <div class="text-h5">{{ (result.annual_return * 100).toFixed(2) }}%</div>
          </v-col>
          <v-col cols="6" sm="3">
            <div class="text-caption">最大回撤</div>
            <div class="text-h5 text-error">{{ (result.max_drawdown * 100).toFixed(2) }}%</div>
          </v-col>
          <v-col cols="6" sm="3">
            <div class="text-caption">夏普比率</div>
            <div class="text-h5">{{ result.sharpe_ratio.toFixed(2) }}</div>
          </v-col>
        </v-row>
        <v-row class="mt-4">
          <v-col cols="6" sm="3">
            <div class="text-caption">胜率</div>
            <div class="text-h5">{{ (result.win_rate * 100).toFixed(1) }}%</div>
          </v-col>
          <v-col cols="6" sm="3">
            <div class="text-caption">交易次数</div>
            <div class="text-h5">{{ result.total_trades }}</div>
          </v-col>
          <v-col cols="6" sm="3">
            <div class="text-caption">总手续费</div>
            <div class="text-h5">{{ result.total_fees.toFixed(2) }}</div>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <v-card class="mt-4">
      <v-card-title>回测历史</v-card-title>
      <v-data-table :headers="historyHeaders" :items="backtests" :loading="loading">
        <template v-slot:item.total_return="{ item }">
          <span :class="item.total_return >= 0 ? 'text-success' : 'text-error'">
            {{ (item.total_return * 100).toFixed(2) }}%
          </span>
        </template>
        <template v-slot:item.actions="{ item }">
          <v-btn size="small" variant="text" @click="viewResult(item)">查看</v-btn>
          <v-btn size="small" color="error" variant="text" @click="deleteBacktest(item)">删除</v-btn>
        </template>
      </v-data-table>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { strategyApi, type Strategy } from '@/api/strategy'
import { backtestApi, type Backtest } from '@/api/backtest'

const loading = ref(false)
const running = ref(false)
const strategies = ref<Strategy[]>([])
const backtests = ref<Backtest[]>([])
const result = ref<Backtest | null>(null)

const form = ref({
  ts_code: '',
  start_date: '',
  end_date: '',
  strategy_id: '',
  portfolio_name: 'default',
})

const headers = [
  { title: '股票代码', key: 'ts_code' },
  { title: '开始日期', key: 'start_date' },
  { title: '结束日期', key: 'end_date' },
  { title: '策略', key: 'strategy' },
  { title: '总收益', key: 'total_return' },
  { title: '操作', key: 'actions', sortable: false },
]

const historyHeaders = [
  { title: '股票代码', key: 'ts_code' },
  { title: '策略', key: 'strategy' },
  { title: '总收益', key: 'total_return' },
  { title: '最大回撤', key: 'max_drawdown' },
  { title: '操作', key: 'actions', sortable: false },
]

const loadData = async () => {
  loading.value = true
  try {
    const [sRes, bRes] = await Promise.all([
      strategyApi.list(),
      backtestApi.list(),
    ])
    strategies.value = sRes.data
    backtests.value = bRes.data
  } finally {
    loading.value = false
  }
}

const runBacktest = async () => {
  running.value = true
  try {
    const res = await backtestApi.run(form.value)
    result.value = res.data
    await loadData()
  } finally {
    running.value = false
  }
}

const viewResult = (item: Backtest) => {
  result.value = item
}

const deleteBacktest = async (item: Backtest) => {
  await backtestApi.delete(item.id)
  await loadData()
}

onMounted(() => {
  loadData()
})
</script>
```

---

## Task 11: 创建交易记录页面

**Files:**
- Create: `frontend/src/views/TradesView.vue`

- [ ] **Step 1: 创建 TradesView.vue**

```vue
<template>
  <v-container>
    <v-card>
      <v-card-title class="d-flex align-center">
        交易记录
        <v-spacer />
        <v-select v-model="selectedBacktestId" :items="backtests" item-title="id" item-value="id" label="选择回测" style="max-width: 300px" @update:modelValue="loadTrades" />
      </v-card-title>
      <v-data-table :headers="headers" :items="trades" :loading="loading">
        <template v-slot:item.action="{ item }">
          <v-chip :color="item.action === 'buy' ? 'success' : 'error'" size="small">
            {{ item.action === 'buy' ? '买入' : '卖出' }}
          </v-chip>
        </template>
      </v-data-table>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { backtestApi, type Backtest, type Trade } from '@/api/backtest'

const loading = ref(false)
const backtests = ref<Backtest[]>([])
const trades = ref<Trade[]>([])
const selectedBacktestId = ref<string | null>(null)

const headers = [
  { title: '日期', key: 'trade_date' },
  { title: '动作', key: 'action' },
  { title: '价格', key: 'price' },
  { title: '股数', key: 'shares' },
  { title: '手续费', key: 'fee' },
  { title: '剩余现金', key: 'cash_after' },
  { title: '持仓', key: 'position_after' },
]

const loadBacktests = async () => {
  const res = await backtestApi.list()
  backtests.value = res.data
}

const loadTrades = async () => {
  if (!selectedBacktestId.value) return
  loading.value = true
  try {
    const res = await backtestApi.getTrades(selectedBacktestId.value)
    trades.value = res.data
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadBacktests()
})
</script>
```

---

## Task 12: 验证前端

- [ ] **Step 1: 启动前端开发服务器**

Run: `cd d:/projects/trade-alpha/frontend; npm run dev`
Expected: Server running on http://localhost:3000

- [ ] **Step 2: 验证页面可访问**

打开浏览器访问 http://localhost:3000，验证各页面正常显示

---

## Task 13: 提交代码

- [ ] **Step 1: 提交变更**

```bash
git add frontend/
git commit -m "feat: add Vue 3 + Vuetify 4 frontend"
```
