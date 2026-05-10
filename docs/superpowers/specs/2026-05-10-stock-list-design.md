# 股票列表功能设计文档

## 概述

新增股票列表功能，从 Tushare 获取 A 股股票列表，按市值降序排列，供前端选择和下载数据使用。

## 数据库设计

### stock_list 集合

| 字段 | 类型 | 说明 |
|-----|------|------|
| ts_code | string | 股票代码 (主键) |
| name | string | 股票名称 |
| industry | string | 行业 |
| list_date | string | 上市日期 (YYYYMMDD) |
| market | string | 市场 ("主板"/"创业板"/"科创板"/"北交所") |
| total_mv | float | 总市值 (万元) |
| pe | float | 市盈率 |
| pb | float | 市净率 |
| updated_at | datetime | 更新时间 |

**索引:**
- `{ts_code: 1}` 唯一索引
- `{total_mv: -1}` (按市值降序排序)

## 后端架构

### DAO 层重构

#### mongodb.py
仅保留基础 MongoDB 操作方法：
- `_get_collection()`: 获取集合
- `close()`: 关闭连接
- `insert_many_generic()`: 通用批量插入/更新（接受 filter 函数参数）
- `find_generic()`: 通用查询方法

#### daily_dao.py
daily 集合业务方法：
- `find_by_ts_code(ts_code)`: 按股票代码查询

#### stock_list_dao.py
stock_list 集合业务方法：
- `insert_stock_list(records)`: 批量插入/更新股票列表
- `list_stocks()`: 按市值降序查询股票列表
- `get_downloaded_summary()`: 获取已下载股票的摘要（与 daily 集合聚合）

### 数据层

#### fetcher.py
新增:
- `fetch_stock_list()`: 获取股票基本信息（stock_basic）
- `fetch_daily_basic(trade_date)`: 获取每日基本面（市值、PE、PB）

#### service.py
新增:
- `update_stock_list()`: 更新股票列表（获取基本信息 + 基本面，合并后存储）

### API 层

#### data.py
新增:
- `GET /stocks`: 获取股票列表（按市值降序，包含是否已下载标识）
- `POST /stocks/update`: 手动触发更新股票列表

## 前端实现

### API 封装 (data.ts)
新增:
- `Stock` 类型定义
- `listStocks()`: 获取股票列表
- `updateStocks()`: 触发更新股票列表

### 页面 (DataView.vue)
改造:
1. 移除顶部输入框和下载按钮
2. 表格表头: 股票代码、名称、行业、市值、是否已下载、操作
3. 操作列: 下载、查看、删除
4. 新增下载对话框: 点击"下载"时弹出，选择日期范围
5. 新增"更新股票列表"按钮在表格顶部

## 更新频率

- 每天更新一次（可通过 cron 或脚本调用 `/stocks/update` API）
- 页面也可以手动触发更新
