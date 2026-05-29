# 交易日历功能设计文档

## 1. 概述
交易日历功能允许用户查看上交所（SSE）和深交所（SZSE）的交易日/非交易日分布，以日历网格形式直观展示。数据通过前端按钮触发，调用 Tushare `trade_cal` API 获取并存储到 MongoDB。

## 2. 数据模型

### TradeCalendar (MongoDB 集合: `trade_calendar`)

| 字段 | 类型 | 说明 |
|------|------|------|
| exchange | str | 交易所代码 (SSE/SZSE) |
| cal_date | str | 日历日期 (YYYYMMDD) |
| is_open | int | 是否交易日 (1=交易日, 0=非交易日) |
| pretrade_date | str | 上一个交易日 (YYYYMMDD) |
| updated_at | datetime | 更新时间 |

**复合唯一索引**: (cal_date, exchange)
**单字段索引**: cal_date

## 3. 后端 API 设计

### POST /api/trade-calendar/sync
- **说明**: 从 Tushare 同步交易日历数据
- **参数**: 无（默认使用 data_years 范围，并覆盖未来 1 年）
- **响应**: `{ "start_date": "20140601", "end_date": "20270601", "stored_count": 10000 }`

### GET /api/trade-calendar
- **说明**: 查询交易日历数据
- **参数**: 
  - `start_date` (可选, YYYYMMDD)
  - `end_date` (可选, YYYYMMDD)
- **响应**: `[{ exchange, cal_date, is_open, pretrade_date }, ...]`

## 4. 前端页面设计

### 页面: TradeCalendarView.vue
路由: `/data/trade-calendar`

### 日历网格布局

```
┌─ 顶部工具栏 ───────────────────────────────────┐
│ [同步日历按钮]         2026年6月          [<] [>] │
├──────────────────────────────────────────────────┤
│  日  一  二  三  四  五  六                       │
│                    1    2    3    4    5    6     │
│  7    8    9   10   11   12   13                 │
│ 14   15   16   17   18   19   20                 │
│ 21   22   23   24   25   26   27                 │
│ 28   29   30                                      │
├──────────────────────────────────────────────────┤
│  图例: ■ 交易日  ■ 非交易日  ■ 无数据             │
└──────────────────────────────────────────────────┘
```

### 颜色方案
- **交易日**: 背景色 `success` (浅绿), 文字深色
- **非交易日**: 背景色 `#FFE0E0` (浅红), 文字深色
- **无数据**: 背景色 `grey-lighten-3`, 文字灰色
- **今日**: 边框加粗高亮
- **点击**: 弹出对话框显示详情

### 同步按钮行为
- 点击后调 `POST /api/trade-calendar/sync`
- 显示 loading 状态
- 完成后刷新日历数据
- 失败时显示错误通知

## 5. 数据范围
- 过去 `data_years` 年（默认12年）的数据，从 `today - 365*data_years` 开始
- 未来 1 年的数据，到 `today + 365` 结束
- 跨越未来确保用户可以提前查看节假日安排

## 6. 实现计划
1. DAO 模型
2. Fetcher 函数
3. Service 层
4. API Router
5. 前端 API
6. 前端页面
7. 路由和菜单