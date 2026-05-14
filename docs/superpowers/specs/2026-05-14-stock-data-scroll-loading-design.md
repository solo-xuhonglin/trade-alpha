# 股票日线数据滚动加载优化设计文档

## 1. 概述

### 1.1 问题背景
当前在股票列表页面点击查看日线详情时，会一次性加载该股票的**所有历史数据**，数据量大时会导致性能问题。

### 1.2 目标
- 减少初始加载时间
- 支持按需加载更多历史数据
- 保持用户体验流畅

## 2. 技术方案

### 2.1 后端增强

#### 2.1.1 新增服务层函数 (`backend/src/trade_alpha/data/service.py`)
新增 `list_stock_daily_paginated` 函数，支持分页查询，按日期倒序排列：
```python
async def list_stock_daily_paginated(
    ts_code: str,
    page: int = 1,
    page_size: int = 500,
    start_date: str = None,
    end_date: str = None,
) -> Tuple[List[StockDaily], int]:
    """Paginated query for stock daily data, sorted by trade_date descending."""
```

#### 2.1.2 新增响应 Schema (`backend/src/trade_alpha/api/schemas.py`)
新增 `StockDataListResponse` 用于返回分页的日线数据。

#### 2.1.3 修改 API 接口 (`backend/src/trade_alpha/api/routers/data.py`)
修改 `GET /data/{ts_code}` 接口：
- 新增可选参数 `page`（默认 1）
- 新增可选参数 `page_size`（默认 500）
- 当不传分页参数时，保持向后兼容（返回全部数据）

### 2.2 前端改造 (`frontend/src/views/DataView.vue`)

#### 2.2.1 数据加载流程
1. 打开 K 线图时，加载第 1 页（最近 500 条数据）
2. 当用户向左滚动到最左边（最早日期）时，自动加载下一页
3. 新数据追加到现有数据的左边（更早的日期）

#### 2.2.2 ECharts 交互
- 监听 `dataZoom` 事件
- 当 `startValue` 接近当前数据最早日期时触发加载
- 加载完成后追加数据并更新图表，保持用户当前视图位置

## 3. 详细设计

### 3.1 后端 API 变更

**接口**：`GET /data/{ts_code}`

**请求参数**：
| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| ts_code | str | 是 | - | 股票代码 |
| start_date | str | 否 | None | 开始日期 |
| end_date | str | 否 | None | 结束日期 |
| page | int | 否 | 1 | 页码 |
| page_size | int | 否 | 500 | 每页条数 |

**响应示例（分页模式）**：
```json
{
  "items": [...],
  "total": 2500,
  "page": 1,
  "page_size": 500,
  "total_pages": 5
}
```

### 3.2 前端状态管理

```typescript
const stockData = ref<DataRecord[]>([])
const currentPage = ref(1)
const totalPages = ref(1)
const loadingMore = ref(false)
const hasMoreData = ref(true)
```

### 3.3 自动加载逻辑

**触发条件**：
- 当前图表最左侧日期（`startValue`）接近 `stockData[0].trade_date`
- `hasMoreData` 为 true
- `loadingMore` 为 false

**加载过程**：
1. 设置 `loadingMore` = true
2. 调用 API 加载下一页
3. 新数据追加到 `stockData` 数组开头
4. 更新 ECharts 图表
5. 设置 `loadingMore` = false
6. 如果 `currentPage` >= `totalPages`，设置 `hasMoreData` = false

## 4. 文件变更清单

### 后端
| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `backend/src/trade_alpha/data/service.py` | 修改 | 新增分页查询函数 |
| `backend/src/trade_alpha/api/schemas.py` | 修改 | 新增分页响应 Schema |
| `backend/src/trade_alpha/api/routers/data.py` | 修改 | 更新数据查询接口 |

### 前端
| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `frontend/src/api/data.ts` | 修改 | 更新 API 类型定义 |
| `frontend/src/views/DataView.vue` | 修改 | 实现滚动加载逻辑 |

## 5. 测试计划

- 测试初始加载 500 条数据
- 测试向左滚动自动加载更多
- 测试加载完所有数据后停止加载
- 验证图表更新后视图位置保持正确

## 6. 风险与注意事项

- 保持向后兼容：当不传分页参数时，原接口行为不变
- 处理边界条件：只有一页数据时的情况
- 避免重复加载：使用 `loadingMore` 状态防止多次触发
