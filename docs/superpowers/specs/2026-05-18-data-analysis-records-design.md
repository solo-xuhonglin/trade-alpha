# 数据分析结果查看功能设计

## 背景

当前数据分析功能（DataAnalysisView.vue）只能发起分析并查看当前结果，无法查看历史分析记录。需要参考训练记录页面的模式，重构为两个独立页面。

## 需求

1. 参考发起训练和训练结果页面的模式
2. 做成两个页面：分析管理（发起分析）、分析记录（历史列表）
3. 分析记录列表操作里有入口
4. 弹窗查看之前的概览图表

## 菜单结构

```
数据
├── 数据列表     → /data/list
├── 分析管理     → /data/analysis/manage  # 发起分析
└── 分析记录     → /data/analysis/records  # 历史列表
```

## 页面设计

### 1. 分析管理页面（`/data/analysis/manage`）

基于当前 DataAnalysisView.vue 重构，参考训练管理页面的布局，去掉左右分栏。

**功能**：
- 顶部筛选区：名称输入、市值排名（起始/结束）、日期范围（起始/结束）
- 指标选择：使用 `v-autocomplete` + `multiple chips closable-chips dense`，参考模型配置界面
- 发起分析按钮
- 运行中的分析任务列表

**名称默认值**：`analysis_${YYYYMMDDHHmmss}`，参考训练的 `training_${formatDateTime()}`

**指标选择 UI**：
```vue
<v-autocomplete 
  v-model="form.feature_fields" 
  :items="indicatorFields" 
  label="特征字段" 
  multiple 
  chips 
  closable-chips 
  dense
></v-autocomplete>
```

### 2. 分析记录页面（`/data/analysis/records`）

新增页面，显示历史分析记录列表。

**列表表格列**：

| 列 | 说明 |
|------|------|
| 名称 | 分析名称 |
| 创建时间 | 分析任务创建时间 |
| 日期范围 | start_date ~ end_date |
| 市值排名 | start_rank ~ end_rank（如适用） |
| 股票数量 | ts_codes.length |
| 指标数量 | feature_fields.length |
| 操作 | 「查看详情」「删除」按钮 |

**删除功能**：
- 点击删除按钮弹出确认对话框
- 确认后调用删除 API
- 删除后刷新列表
- 参考训练记录页面的删除实现

**详情弹窗**：
- 标题：分析详情 + 创建时间
- 标签页：概览 | 箱线图 | 直方图
- 概览：统计表格（均值、标准差、中位数、Q1、Q3、最小值、最大值、缺失率、异常值率）
- 箱线图：ECharts 箱线图组件
- 直方图：字段选择下拉 + ECharts 直方图组件

## 后端 API

### 后端模型更新

在 `DataAnalysisResult` 模型中新增 `name` 字段：

```python
class DataAnalysisResult(Document):
    name: str  # 新增
    task_id: str
    # ... 其他字段
```

### API 更新
- `POST /api/data-analysis` - 新增 `name` 参数，默认值 `analysis_${YYYYMMDDHHmmss}`
- `GET /api/data-analysis/task/:id` - 保持不变
- `GET /api/data-analysis/results` - 返回结果包含 `name` 字段
- `DELETE /api/data-analysis/results/:id` - 新增删除接口

### Task 模型更新

Task 的 params 字段需要保存 name：

```python
params={
    "name": name,
    "ts_codes": ts_codes,
    # ... 其他字段
}
```

## 前端 API 更新

现有 `dataAnalysis.ts` 需要补充类型定义：

```typescript
export interface AnalysisRecord {
  id: string
  name: string  # 新增
  task_id: string
  ts_codes: string[]
  start_date: string
  end_date: string
  feature_fields: string[]
  created_at: string
}

export interface AnalysisCreateParams {
  name?: string  # 新增
  ts_codes?: string[]
  start_rank?: number
  end_rank?: number
  start_date?: string
  end_date?: string
  feature_fields?: string[]
}

export interface AnalysisRecordListResponse {
  items: AnalysisRecord[]
  total: number
}

export const dataAnalysisApi = {
  async triggerAnalysis(params: AnalysisCreateParams) {
    return await apiClient.post&lt;{
      task_id: string
      status: string
      message: string
    }&gt;('/data-analysis', params)
  },
  async getTaskStatus(taskId: string) {
    return await apiClient.get&lt;AnalysisTaskStatus&gt;(`/data-analysis/task/${taskId}`)
  },
  async listResults(limit: number = 20) {
    return await apiClient.get&lt;AnalysisRecord[]&gt;(`/data-analysis/results?limit=${limit}`)
  },
  async deleteResult(id: string) {
    return await apiClient.delete(`/data-analysis/results/${id}`)
  },
  // ... 其他 API
}
```

## 文件变更

### 新增文件

| 文件 | 说明 |
|------|------|
| `frontend/src/views/DataAnalysisRecordsView.vue` | 历史记录列表页面 |

### 重命名文件

| 原文件 | 新文件 | 说明 |
|--------|--------|------|
| `frontend/src/views/DataAnalysisView.vue` | `frontend/src/views/DataAnalysisManageView.vue` | 发起分析页面 |

### 修改文件

| 文件 | 说明 |
|------|------|
| `backend/src/trade_alpha/dao/data_analysis_result.py` | 新增 name 字段 |
| `backend/src/trade_alpha/api/routers/data_analysis.py` | 更新 API 支持 name，新增删除接口 |
| `frontend/src/router/index.ts` | 更新路由配置 |
| `frontend/src/components/AppLayout.vue` | 更新菜单项 |
| `frontend/src/api/dataAnalysis.ts` | 补充类型定义，新增删除接口 |
| `frontend/src/views/DataAnalysisView.vue`（重命名前） | 添加名称输入框 |

## 组件结构

```
frontend/src/views/
├── DataAnalysisManageView.vue   # 发起分析（重构自 DataAnalysisView）
└── DataAnalysisRecordsView.vue  # 历史记录 + 详情弹窗（新增）

frontend/src/api/
└── dataAnalysis.ts              # 已有，保持不变
```

## 详情弹窗标签页内容

### 概览标签页

```vue
<v-table density="compact" fixed-header height="500">
  <thead>
    <tr>
      <th>字段</th>
      <th>均值</th>
      <th>标准差</th>
      <th>中位数</th>
      <th>Q1</th>
      <th>Q3</th>
      <th>最小</th>
      <th>最大</th>
      <th>缺失率</th>
      <th>异常值率</th>
    </tr>
  </thead>
  <tbody>
    <tr v-for="(stats, field) in result?.statistics" :key="field">
      <td>{{ field }}</td>
      <td>{{ stats.mean.toFixed(4) }}</td>
      <td>{{ stats.std.toFixed(4) }}</td>
      <td>{{ stats.median.toFixed(4) }}</td>
      <td>{{ stats.q1.toFixed(4) }}</td>
      <td>{{ stats.q3.toFixed(4) }}</td>
      <td>{{ stats.min.toFixed(4) }}</td>
      <td>{{ stats.max.toFixed(4) }}</td>
      <td>{{ (stats.missing_rate * 100).toFixed(2) }}%</td>
      <td>{{ (stats.outlier_rate * 100).toFixed(2) }}%</td>
    </tr>
  </tbody>
</v-table>
```

### 箱线图标签页

```vue
<div ref="boxplotChartRef" style="width: 100%; height: 500px;"></div>
```

### 直方图标签页

```vue
<v-select
  v-model="histogramField"
  label="选择字段"
  :items="Object.keys(result?.histograms || {})"
  class="mb-2"
/>
<div ref="histogramChartRef" style="width: 100%; height: 450px;"></div>
```

## 实现顺序

1. 修改菜单结构（AppLayout.vue）
2. 创建 DataAnalysisRecordsView.vue（历史记录列表）
3. 重命名 DataAnalysisView.vue → DataAnalysisManageView.vue
4. 更新路由配置
5. 更新菜单导航
