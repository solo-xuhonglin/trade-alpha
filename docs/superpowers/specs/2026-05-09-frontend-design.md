# 前端设计

## 概述

为 Trade-Alpha 添加 Vue 3 + Vuetify 4 前端界面。

## 目录结构

```
trade-alpha/
├── frontend/                    # 前端项目
│   ├── src/
│   │   ├── api/               # API 调用封装
│   │   ├── components/        # 公共组件
│   │   ├── views/             # 页面视图
│   │   ├── router/            # 路由配置
│   │   ├── App.vue
│   │   └── main.ts
│   ├── package.json
│   └── vite.config.ts
├── src/                        # 后端 (现有)
├── docs/                       # 文档 (现有)
```

## 技术栈

- Vue 3 + TypeScript
- Vuetify 4
- Vue Router 4
- Vite (构建工具)
- Axios (HTTP 客户端)

## 布局设计

左侧导航 + 主内容区布局（标准后台管理布局）：

```
┌──────────────────────────────────────────────┐
│  Trade-Alpha                                │  ← 顶部栏
├────────────┬─────────────────────────────────┤
│            │                                 │
│  数据管理   │        主内容区                  │
│  账户管理   │                                 │
│  策略管理   │                                 │
│  回测      │                                 │
│  交易记录   │                                 │
│            │                                 │
└────────────┴─────────────────────────────────┘
```

## 页面设计

### 1. 数据管理 `/data`

- 股票列表表格：每行一条股票记录
- 显示：股票代码、数据条数、最新日期
- 操作：下载新数据、查看详情、删除
- 查看详情 → K线图表展示（含 MA/MACD 指标叠加）
- 下载新数据：弹窗输入日期范围

### 2. 账户管理 `/portfolios`

- 账户列表表格
- 创建账户按钮 → 弹窗表单
- 编辑/删除按钮
- 显示：名称、初始资金、当前现金、持仓

### 3. 策略管理 `/strategies`

- 策略列表表格
- 创建策略按钮 → 弹窗表单
- 策略类型选择：price, ma, macd
- 动态配置字段
- 编辑/删除按钮

### 4. 回测 `/backtest`

- 参数表单：股票代码、日期范围、策略选择、账户选择
- 运行回测按钮
- 结果展示：收益率、回撤、夏普比率等
- 交易列表展示

### 5. 交易记录 `/trades`

- 回测选择下拉框
- 交易记录表格
- 显示：日期、动作、价格、手续费等

## API 层对接

前端通过 Axios 调用后端 FastAPI：

```typescript
// API 端点
GET    /api/data/{ts_code}
POST   /api/data
GET    /api/indicators/ma
GET    /api/indicators/macd
GET    /api/predict/{ts_code}
POST   /api/predict
GET    /api/strategies
POST   /api/strategies
PUT    /api/strategies/{id}
DELETE /api/strategies/{id}
GET    /api/portfolios
POST   /api/portfolios
PUT    /api/portfolios/{id}
DELETE /api/portfolios/{id}
GET    /api/backtests
POST   /api/backtests
GET    /api/backtests/{id}
GET    /api/backtests/{id}/trades
DELETE /api/backtests/{id}
```

## 开发环境

- 前端 dev server: `http://localhost:3000`
- 后端 API: `http://localhost:8000`
- 开发时通过代理转发 API 请求到后端
