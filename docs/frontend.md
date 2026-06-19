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
│   │   ├── trade.ts           # 交易记录 API
│   │   ├── liveSuggestion.ts  # 实盘建议 API
│   │   ├── livePortfolio.ts   # 实盘仓位 API
│   │   ├── tradeCalendar.ts   # 交易日历 API
│   │   └── scheduledTask.ts   # 定时任务 API
│   ├── components/             # 公共组件
│   │   ├── AppLayout.vue      # 应用布局
│   │   ├── ActiveTaskPanel.vue # 运行中任务面板（可复用）
│   │   ├── StatusChip.vue     # 任务状态标签（可复用）
│   │   └── StrategyChips.vue  # 策略排名优化标签（可复用）
│   ├── views/                  # 页面视图
│   │   ├── DataListView.vue   # 数据管理
│   │   ├── DataAnalysisManageView.vue  # 数据分析管理
│   │   ├── DataAnalysisRecordsView.vue # 数据分析记录
│   │   ├── AccountConfigView.vue   # 账户配置
│   │   ├── StrategyConfigView.vue  # 策略配置
│   │   ├── ModelConfigView.vue     # 模型配置
│   │   ├── TrainingManageView.vue     # 训练管理
│   │   ├── TrainingRecordsView.vue     # 训练记录
│   │   ├── BacktestManageView.vue     # 回测管理
│   │   ├── BacktestRecordsView.vue     # 回测记录
│   │   ├── TradesView.vue     # 交易记录
│   │   ├── LivePositionManageView.vue  # 仓位管理
│   │   ├── LiveSuggestionManageView.vue # 实盘建议管理
│   │   ├── LiveDailySuggestionsView.vue # 每日建议
│   │   ├── DailyRankingsView.vue       # 每日评分排名
│   │   ├── TradeCalendarView.vue       # 交易日历
│   │   ├── ScheduledTaskConfigView.vue  # 定时任务配置
│   │   └── ScheduledTaskLogView.vue     # 定时任务日志
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
│  ▼ 实盘建议 │                                 │
│    管理     │                                 │
│    仓位管理 │                                 │
│    每日建议 │                                 │
│    每日排名 │                                 │
│  ▼ 定时任务 │                                 │
│    配置     │                                 │
│    日志     │                                 │
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
| `/live-suggestion/manage` | 实盘建议管理 | 发起建议任务、查看运行中任务 |
| `/live-suggestion/positions` | 仓位管理 | 手动管理持仓、现金调整、费率设置 |
| `/live-suggestion/daily-suggestions` | 每日建议 | 查看每日建议股票列表 |
| `/live-suggestion/daily-rankings` | 每日排名 | 全市场评分排名 |
| `/scheduled-tasks/config` | 定时任务配置 | 查看/编辑定时任务 |
| `/scheduled-tasks/logs` | 定时任务日志 | 查看执行历史 |

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
- 行业筛选下拉框（从 `GET /data/industries` 加载行业列表）
- 历史日期输入（基于 StockListHistory 回溯指定日期的股票列表）
- 回测状态筛选（active/inactive/all）
- 单只股票回测开关切换（`is_active_for_backtest`）
- 批量设置回测状态（选择多只股票一键开关）
- 更新股票列表
- 下载股票数据
- 查看 K 线图
- 删除股票数据

**组件**:
- 服务端分页表格：股票列表（v-data-table-server），新增 `is_active_for_backtest` 切换列
- 行业筛选下拉框（v-select）
- 历史日期输入（v-text-field type="date"）
- 回测状态筛选（v-select: active/inactive/all）
- 批量操作按钮组（全选、批量启用、批量禁用）
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
- 组合模式：基础参数 + 排名优化（动量加成/趋势加分/暴跌排除/排名上涨优先/评分下滑过滤/ATR 动态止损等开关）
- 策略回测列表显示状态 chip（动量加成/趋势加分/排名上涨优先/ATR 止损/评分下滑过滤启用标记）
- ATR 止损参数（atr_stop_multiplier, atr_trail_rate）
- 每日买入上限（max_daily_buys）
- 评分下滑过滤（use_score_decline_filter, score_decline_threshold）
- 满仓容忍卖出增加 PnL 权重（full_position_pnl_weight）

**组件**:
- 数据表格：策略列表
- 弹窗表单：策略编辑（基础配置 tab + 排名优化 tab + 止损 tab）
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
- 任务列表：运行中的训练任务（ActiveTaskPanel）

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
- 单股票模式输入股票代码，组合模式输入市值前N、计算范围、涨幅前N（用于周度候选池）
- 发起回测
- 查看运行中的任务状态

**表单布局**（2 行 × 5 列，Vuetify grid）:
- 第 1 行：账户配置(2) | 策略配置(2) | 训练结果(2) | 开始日期(3) | 结束日期(3)
- 第 2 行：计算范围(2) | 市值前N/股票(2) | 涨幅前N(2) | 回测名称(3) | 发起回测(3)
- 响应式：md+ 5列，sm 2列，xs 1列

**组件**:
- 表单：选择参数
- 任务列表：运行中的回测任务（ActiveTaskPanel）

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

### 11. 实盘建议管理 `/live-suggestion/manage`

**功能**:
- 选择训练结果、策略配置、实盘组合
- 设置时间范围和市值排行前 N
- 发起实盘建议任务
- 查看运行中任务状态

**组件**:
- 表单：选择参数
- `StrategyChips`：显示策略排名优化状态（含排名上涨优先 chip）
- `ActiveTaskPanel`：运行中任务面板（支持停止/删除任务）

### 12. 仓位管理 `/live-suggestion/positions`

**功能**:
- 选择/创建实盘组合
- 手动添加/编辑/删除持仓
- 搜索股票（模糊匹配 ts_code 或名称）
- 查看持仓汇总（持仓数、总成本）

**组件**:
- 组合选择器
- 数据表格：持仓列表
- 持仓表单弹窗
- 股票搜索框

### 13. 每日建议 `/live-suggestion/daily-suggestions`

**功能**:
- 选择建议日期
- 卡片布局展示建议股票列表（评分、排名、方向概率、排除标记、评分明细）
- 展开行查看评分明细（raw_score、trend_bonus、vol_penalty、momentum_bonus）
- 支持分页浏览

**组件**:
- 日期选择器
- Vuetify 卡片表格布局
- 展开行：评分明细表格

### 14. 每日排名 `/live-suggestion/daily-rankings`

**功能**:
- 选择交易日期
- 查看全市场评分排名
- 多日均值排名（avg_rank_3d/5d/20d）
- 排名变化（rank_change）
- 评分明细列合并为 `composite_score`（含公式：score + trend_bonus - vol_penalty + momentum_bonus）
- 悬浮提示显示评分公式组成

**组件**:
- 日期选择器
- 数据表格：评分排名列表
- 列头：综合评分（含 tooltip 显示评分公式）

### 15. 定时任务配置 `/scheduled-tasks/config`

**功能**:
- 查看定时任务配置列表
- 编辑任务配置（启用/禁用、触发类型、间隔/定时参数、任务参数）
- 手动触发任务执行
- 查看最后执行状态

**组件**:
- 数据表格：任务配置列表（含最后执行时间/状态）
- 弹窗表单：编辑配置
- 触发按钮：立即执行

### 16. 定时任务日志 `/scheduled-tasks/logs`

**功能**:
- 查看定时任务执行历史
- 按任务类型筛选
- 查看执行状态、耗时、结果/错误信息

**组件**:
- 数据表格：执行日志列表
- 筛选下拉：按任务类型

## 共享组件

### ActiveTaskPanel.vue

运行中任务面板，用于管理训练/回测/实盘建议等异步任务的实时状态：

- 自动轮询任务进度
- 支持停止（可选强制）和删除任务
- 可配置任务标签、错误列显示
- 通过 `api-stop` 和 `api-delete` 属性注入具体 API

### StatusChip.vue

任务状态标签：
- `pending` → 灰色
- `running` → 蓝色
- `completed` → 绿色
- `failed` → 红色
- `cancelled` → 黄色

### StrategyChips.vue

策略排名优化标签，显示策略中启用的排名优化项（动量加成/趋势加分/暴涨排除/排名上涨优先/评分下滑过滤/ATR 止损）。启用项包括：
- `use_momentum_boost` → "动量加成"
- `use_trend_bonus` → "趋势加分"
- `use_explosion_filter` → "暴涨排除"
- `use_rank_up_priority` → "排名上涨优先"
- `use_score_decline_filter` → "评分下滑过滤"
- `use_trend_penalty` → "趋势扣分"
- `atr_stop_multiplier > 0` → "ATR止损"

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
import { notifyService } from '@/utils/notify'

// 使用方式
notifyService.success('操作成功')
notifyService.error('操作失败')
notifyService.info('提示信息')
notifyService.warning('警告信息')
```

**特点**:
- 基于 Vuetify 的 `useDisplay()` 组件自适应显示位置
- 支持链式操作
- 自动错误处理集成

### 实盘建议 API

```typescript
// src/api/liveSuggestion.ts
export const liveSuggestionApi = {
  trigger: (body: {
    training_id: string,
    strategy_config_id: string,
    portfolio_id?: string,
    start_date?: string,
    end_date?: string,
    top_n?: number
  }) => api.post('/live-suggestion/run', body),

  listDailyScores: (tradeDate?: string, page?: number, pageSize?: number) =>
    api.get('/live-suggestion/daily-scores', { params: { trade_date: tradeDate, page, page_size: pageSize } }),

  listSuggestionDates: (page?: number, pageSize?: number) =>
    api.get('/live-suggestion/suggestion-dates', { params: { page, page_size: pageSize } }),

  listSuggestions: (tradeDate: string, page?: number, pageSize?: number) =>
    api.get('/live-suggestion/suggestions', { params: { trade_date: tradeDate, page, page_size: pageSize } }),

  listRuns: (page?: number, pageSize?: number) =>
    api.get('/live-suggestion/runs', { params: { page, page_size: pageSize } }),

  listTasks: (page?: number, pageSize?: number, status?: string) =>
    api.get('/live-suggestion/tasks', { params: { page, page_size: pageSize, status } }),

  getTask: (taskId: string) =>
    api.get(`/live-suggestion/task/${taskId}`),

  stopTask: (taskId: string, force = false) =>
    api.post(`/live-suggestion/task/${taskId}/stop?force=${force}`),

  deleteTask: (taskId: string) =>
    api.delete(`/live-suggestion/task/${taskId}`),

  listStockDailyScores: (tsCode: string) =>
    api.get(`/live-suggestion/daily-scores/stock/${encodeURIComponent(tsCode)}`),
}
```