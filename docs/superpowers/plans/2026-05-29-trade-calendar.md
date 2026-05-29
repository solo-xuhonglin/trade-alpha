# 交易日历功能计划

## 目标
新增交易日历功能，查看上交所/深交所的交易日和非交易日分布，支持前端按钮手动同步数据。

## 设计文档
`docs/superpowers/specs/2026-05-29-trade-calendar-design.md`

## 实现步骤

### 1. 后端
- **DAO**: `backend/src/trade_alpha/dao/trade_calendar.py` — Beanie Document 模型
- **Fetcher**: `backend/src/trade_alpha/data/fetcher.py` — 新增 `fetch_trading_calendar()`，调用 Tushare `trade_cal` API
- **Service**: `backend/src/trade_alpha/data/service.py` — 新增 `fetch_and_store_trade_calendar()` 和 `get_trade_calendar_records()`
- **Router**: `backend/src/trade_alpha/api/routers/trade_calendar.py` — 两个接口：同步 + 查询
- **注册**: 更新 DAO \_\_init\_\_.py、mongodb.py、router \_\_init\_\_.py

### 2. 前端
- **API**: `frontend/src/api/tradeCalendar.ts` — 前端 API 调用
- **View**: `frontend/src/views/TradeCalendarView.vue` — 日历页面（自定义网格日历）
- **Router**: 路由注册
- **侧边栏**: AppLayout.vue 添加菜单项

### 3. 日历 UI 设计
- 自定义日历网格（非第三方日历组件）
- 月度视图，支持上下月导航
- 绿色=交易日，红色=非交易日，灰色=无数据
- 点击日期弹出详情对话框
- 顶部"同步日历"按钮触发后端同步