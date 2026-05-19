# 数据分布统计分析功能设计

## 1. 功能概述

新增数据分布统计分析功能，支持用户分析股票日线特征的数据分布情况，包括统计、箱线图、直方图等多维度可视化分析。功能采用异步任务模式，处理大数据量场景。

## 2. 菜单结构调整

### 2.1 导航菜单

```
数据（子菜单）
├── 数据列表（原数据页面）
└── 数据分析（新增）
```

调整原“数据”菜单项由单页面改为子菜单：
- 原路由 `/data` 改为 `/data/list`，标题"数据列表"
- 新增路由 `/data/analysis`，标题"数据分析"

## 3. 后端架构设计

### 3.1 文件结构

```
backend/src/trade_alpha/
├── data/
│   ├── service.py              (现有)
│   ├── fetcher.py            (现有)
│   └── analysis_service.py   (新增：数据分析服务)
├── dao/
│   ├── task.py              (扩展)
│   └── data_analysis_result.py (新增：分析结果模型)
└── api/routers/
    └── data_analysis.py     (新增：数据分析API)
```

### 3.2 任务类型扩展

```python
class TaskType(str, Enum):
    BACKTEST = "backtest"
    TRAINING = "training"
    DATA_ANALYSIS = "data_analysis"  # 新增
```

### 3.3 数据模型

#### 3.3.1 DataAnalysisResult

```python
from beanie import Document
from datetime import datetime
from typing import Optional, Dict, Any, List


class DataAnalysisResult(Document):
    task_id: str
    ts_codes: List[str]
    start_date: str
    end_date: str
    feature_fields: List[str]
    # 统计表格数据
    statistics: Dict[str, Any]
    # 直方图数据（分箱）
    histograms: Dict[str, Any]
    # 箱线图数据
    boxplots: Dict[str, Any]
    # 缺失值数据
    missing_data: Dict[str, Any]
    created_at: datetime

    class Settings:
        name = "data_analysis_results"
```

## 4. API 设计

### 4.1 触发分析任务

```http
POST /api/data-analysis
```

**请求体:**

```json
{
  "ts_codes": ["000001.SZ", "000002.SZ"],
  "start_rank": 1,
  "end_rank": 1000,
  "start_date": "2020-01-01",
  "end_date": "2025-12-31",
  "feature_fields": ["ma_5", "ma_10", "rsi_6"]
}
```

**响应:**

```json
{
  "task_id": "664a34567890123456789012",
  "status": "pending",
  "message": "Data analysis task triggered"
}
```

### 4.2 获取任务状态

```http
GET /api/data-analysis/:id
```

**响应:**

```json
{
  "task_id": "664a34567890123456789012",
  "status": "completed",
  "progress": 100.0,
  "progress_message": "Analysis completed",
  "result": {
    "statistics": { ... },
    "histograms": { ... },
    "boxplots": { ... }
  }
}
```

### 4.3 获取历史分析记录

```http
GET /api/data-analysis/results
```

## 5. 前端架构设计

### 5.1 页面布局

```
┌───────────────────────────────────────────────────────────────────────────────┐
│  顶部筛选区（全屏宽度                                                          │
│  [股票筛选] □ 多选 □ 市值排名 1-1000  日期 2020-2025  [统计]              │
└───────────────────────────────────────────────────────────────────────────────┘
┌───────────────────────────────────────────────────────────────────────────────┐
│ 左侧（25%）          │  右侧（75%）                                    │
│                      │  ┌───────────────────────────────────────────┐    │
│  指标多选列表         │  │  状态提示区 (任务状态/进度/消息           │    │
│   □ ma_5             │  └───────────────────────────────────────────┘    │
│   ☑ ma_10            │  [概览][箱线图][直方图] 标签页              │    │
│   ☑ ma_20            │  ┌───────────────────────────────────────────┐    │
│   □ ma_60            │  │  图表区域                                 │    │
│   ☑ rsi_6            │  └───────────────────────────────────────────┘    │
│   ☑ rsi_12           │                                              │    │
│  ...                 │                                              │    │
│  [全选][取消全选]    │                                              │    │
│                      │                                              │    │
└───────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 默认值

| 配置项 | 默认值 |
|--------|--------|
| 市值排名范围 | 1-1000 |
| 开始日期 | 2020-01-01 |
| 结束日期 | 2025-12-31 |

## 6. 数据分析计算流程

### 6.1 异步任务处理流程

```
1. 用户点击"统计"按钮
   ↓
2. 创建 Task（DATA_ANALYSIS）
   ↓
3. 后台异步任务执行
   - 加载数据 → 计算统计 → 生成图表数据
   ↓
4. 保存 DataAnalysisResult
   ↓
5. 更新 Task 状态为 completed
   ↓
6. 前端轮询获取结果
   ↓
7. 展示图表
```

### 6.2 进度阶段

| 阶段 | 进度 | 说明 |
|------|------|
| 加载数据 | 0-30% | 从 MongoDB 加载日线数据 |
| 计算统计 | 30-60% | 计算均值、标准差、分位数等 |
| 生成图表数据 | 60-90% | 分箱数据、箱线图数据 |
| 保存结果 | 90-100% | 保存到数据库 |

## 7. 图表数据格式

### 7.1 统计表格数据

```json
{
  "statistics": {
    "ma_5": {
      "mean": 10.5,
      "std": 2.3,
      "median": 10.2,
      "q1": 8.5,
      "q3": 12.5,
      "min": 5.2,
      "max": 18.9,
      "missing_rate": 0.05,
      "outlier_rate": 0.02
    }
  }
}
```

### 7.2 直方图数据

```json
{
  "histograms": {
    "ma_5": {
      "bins": [5, 7, 9, 11, 13, 15, 17],
      "counts": [100, 200, 300, 250, 150, 50]
    }
  }
}
```

### 7.3 箱线图数据

```json
{
  "boxplots": {
    "ma_5": {
      "min": 5.2,
      "q1": 8.5,
      "median": 10.2,
      "q3": 12.5,
      "max": 18.9,
      "outliers": [1.2, 25.3]
    }
  }
}
```

## 8. 技术栈

| 层级 | 技术方案 |
|------|---------|
| 后端 | FastAPI + Beanie + MongoDB |
| 图表库 | ECharts |
| 前端 | Vue3 + Vuetify3 |
