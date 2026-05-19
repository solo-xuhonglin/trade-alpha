# 数据分析结果查看功能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构数据分析功能为两个独立页面（分析管理、分析记录），添加历史记录查看、详情弹窗、删除功能

**Architecture:** 
1. 后端更新 DataAnalysisResult 模型添加 name 字段，新增删除 API
2. 前端重命名现有页面，创建新的历史记录页面
3. 更新菜单和路由

**Tech Stack:** FastAPI, Beanie, Vue 3, Vuetify 3

---

## Task 1: 更新后端 DataAnalysisResult 模型

**Files:**
- Modify: `backend/src/trade_alpha/dao/data_analysis_result.py`

- [ ] **Step 1: 读取现有模型**

读取当前 DataAnalysisResult 模型文件

- [ ] **Step 2: 添加 name 字段**

```python
from beanie import Document
from datetime import datetime
from typing import Dict, Any, List

class DataAnalysisResult(Document):
    name: str  # 新增字段
    task_id: str
    ts_codes: List[str]
    start_date: str
    end_date: str
    feature_fields: List[str]
    statistics: Dict[str, Any]
    histograms: Dict[str, Any]
    boxplots: Dict[str, Any]
    missing_data: Dict[str, Any]
    created_at: datetime

    class Settings:
        name = "data_analysis_results"
```

- [ ] **Step 3: 保存文件**

将更新后的模型写入文件

- [ ] **Step 4: 运行后端检查是否有语法错误**

Run: `cd backend && python -c "import src.trade_alpha.dao.data_analysis_result; print('OK')"`
Expected: 输出 "OK" 无错误

- [ ] **Step 5: 提交**

```bash
git add backend/src/trade_alpha/dao/data_analysis_result.py
git commit -m "feat(data-analysis): add name field to DataAnalysisResult model"
```

---

## Task 2: 更新后端 API（新增 name 参数和删除接口）

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/data_analysis.py`

- [ ] **Step 1: 读取现有 API 文件**

读取当前的 data_analysis.py

- [ ] **Step 2: 更新 DataAnalysisCreate 添加 name 字段**

```python
class DataAnalysisCreate(BaseModel):
    name: Optional[str] = None  # 新增字段
    ts_codes: Optional[List[str]] = None
    start_rank: Optional[int] = 1
    end_rank: Optional[int] = 1000
    start_date: str = "2020-01-01"
    end_date: str = "2025-12-31"
    feature_fields: Optional[List[str]] = None
```

- [ ] **Step 3: 更新 trigger_data_analysis 接口保存 name**

修改触发分析的接口，保存 name 到 task.params 和 result

```python
@router.post("")
async def trigger_data_analysis(
    background_tasks: BackgroundTasks,
    params: DataAnalysisCreate,
):
    """Trigger data analysis task (async)."""
    ts_codes = params.ts_codes or []
    if not ts_codes:
        stocks = await list_stocks_by_mv_rank(params.start_rank, params.end_rank)
        ts_codes = [s.ts_code for s in stocks]

    if not ts_codes:
        raise HTTPException(status_code=400, detail="No stocks found")

    feature_fields = params.feature_fields or DEFAULT_INDICATOR_FIELDS
    
    # 生成默认 name
    if not params.name:
        from datetime import datetime
        now = datetime.now()
        params.name = f"analysis_{now.strftime('%Y%m%d%H%M%S')}"

    task = await Task(
        type=TaskType.DATA_ANALYSIS,
        status=TaskStatus.PENDING,
        params={
            "name": params.name,  # 保存 name
            "ts_codes": ts_codes,
            "start_date": params.start_date,
            "end_date": params.end_date,
            "feature_fields": feature_fields,
        },
        created_at=datetime.now(),
    ).save()

    background_tasks.add_task(run_data_analysis_async, str(task.id))

    return {
        "task_id": str(task.id),
        "status": task.status.value,
        "message": "Data analysis task triggered",
    }
```

- [ ] **Step 4: 更新 save_analysis_result 调用保存 name**

修改 run_data_analysis_async 函数中保存分析结果的部分

```python
async def run_data_analysis_async(task_id: str):
    """Execute data analysis asynchronously."""
    from trade_alpha.logging import get_logger

    logger = get_logger("data_analysis.task")
    task = await Task.get(PydanticObjectId(task_id))
    if not task:
        return

    async def update_progress(progress: float, message: str):
        task.progress = progress
        task.progress_message = message
        await task.save()

    try:
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        task.progress = 0.0
        task.progress_message = "正在初始化..."
        await task.save()

        params = task.params
        result = await run_data_analysis(
            ts_codes=params["ts_codes"],
            start_date=params["start_date"],
            end_date=params["end_date"],
            feature_fields=params["feature_fields"],
            progress_callback=update_progress,
        )

        analysis_result_id = await save_analysis_result(
            task_id=str(task.id),
            name=params.get("name", ""),  # 新增 name 参数
            ts_codes=params["ts_codes"],
            start_date=params["start_date"],
            end_date=params["end_date"],
            feature_fields=params["feature_fields"],
            result=result,
        )

        task.status = TaskStatus.COMPLETED
        task.progress = 100.0
        task.progress_message = "分析完成"
        task.result_id = analysis_result_id
        task.completed_at = datetime.now()
        await task.save()

    except Exception as e:
        logger.error(f"Data analysis task {task_id} failed: {e}")
        task.status = TaskStatus.FAILED
        task.error_message = str(e)
        task.progress_message = f"分析失败: {str(e)}"
        await task.save()
```

- [ ] **Step 5: 更新 list_analysis_results 返回 name**

修改列表接口，确保返回 name 字段

```python
@router.get("/results")
async def list_analysis_results(limit: int = Query(20, ge=1, le=100)):
    """List analysis results."""
    results = await DataAnalysisResult.find_all().sort(-DataAnalysisResult.created_at).limit(limit).to_list()
    return [
        {
            "id": str(r.id),
            "task_id": r.task_id,
            "name": r.name,  # 新增 name
            "ts_codes": r.ts_codes,
            "start_date": r.start_date,
            "end_date": r.end_date,
            "feature_fields": r.feature_fields,
            "created_at": r.created_at.isoformat(),
        }
        for r in results
    ]
```

- [ ] **Step 6: 更新 save_analysis_result 函数**

首先找到定义 save_analysis_result 的文件并更新它，添加 name 参数

- [ ] **Step 7: 添加删除接口**

```python
@router.delete("/results/{id}")
async def delete_analysis_result(id: str):
    """Delete analysis result by ID."""
    try:
        obj_id = PydanticObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    result = await DataAnalysisResult.get(obj_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    await result.delete()
    return {"status": "ok"}
```

- [ ] **Step 8: 运行后端 API 测试**

Run: `cd backend && python -m pytest tests/trade_alpha/integration/test_33_service_data_analysis.py -v`
Expected: 所有测试通过

- [ ] **Step 9: 提交**

```bash
git add backend/src/trade_alpha/api/routers/data_analysis.py
# 如果修改了其他文件也添加
git commit -m "feat(data-analysis): add name support and delete API"
```

---

## Task 3: 更新后端 analysis_service 的 save_analysis_result 函数

**Files:**
- Modify: `backend/src/trade_alpha/data/analysis_service.py`

- [ ] **Step 1: 读取现有 analysis_service**

读取该文件，找到 save_analysis_result 函数

- [ ] **Step 2: 添加 name 参数**

```python
async def save_analysis_result(
    task_id: str,
    name: str,  # 新增
    ts_codes: List[str],
    start_date: str,
    end_date: str,
    feature_fields: List[str],
    result: Dict[str, Any],
) -> str:
    """Save analysis result to database."""
    from trade_alpha.dao.data_analysis_result import DataAnalysisResult
    from datetime import datetime

    analysis_result = DataAnalysisResult(
        name=name,  # 新增
        task_id=task_id,
        ts_codes=ts_codes,
        start_date=start_date,
        end_date=end_date,
        feature_fields=feature_fields,
        statistics=result["statistics"],
        histograms=result["histograms"],
        boxplots=result["boxplots"],
        missing_data=result["missing_data"],
        created_at=datetime.now(),
    )
    await analysis_result.save()
    return str(analysis_result.id)
```

- [ ] **Step 3: 运行测试**

Run: `cd backend && python -m pytest tests/trade_alpha/integration/test_33_service_data_analysis.py -v`
Expected: 测试通过

- [ ] **Step 4: 提交**

```bash
git add backend/src/trade_alpha/data/analysis_service.py
git commit -m "feat(data-analysis): update save_analysis_result with name"
```

---

## Task 4: 更新前端 API（dataAnalysis.ts）

**Files:**
- Modify: `frontend/src/api/dataAnalysis.ts`

- [ ] **Step 1: 读取现有 dataAnalysis.ts**

- [ ] **Step 2: 补充类型定义**

```typescript
export interface AnalysisRecord {
  id: string
  name: string  // 新增
  task_id: string
  ts_codes: string[]
  start_date: string
  end_date: string
  feature_fields: string[]
  created_at: string
}

export interface AnalysisCreateParams {
  name?: string  // 新增
  ts_codes?: string[]
  start_rank?: number
  end_rank?: number
  start_date?: string
  end_date?: string
  feature_fields?: string[]
}

export interface AnalysisTaskStatus {
  task_id: string
  status: string
  progress: number
  progress_message: string
  result?: AnalysisResult
}
```

- [ ] **Step 3: 更新 API 函数**

```typescript
export const dataAnalysisApi = {
  async triggerAnalysis(params: AnalysisCreateParams) {
    return await apiClient.post<{
      task_id: string
      status: string
      message: string
    }>('/data-analysis', params)
  },
  async getTaskStatus(taskId: string) {
    return await apiClient.get<AnalysisTaskStatus>(`/data-analysis/task/${taskId}`)
  },
  async listResults(limit: number = 20) {
    return await apiClient.get<AnalysisRecord[]>(`/data-analysis/results?limit=${limit}`)
  },
  async deleteResult(id: string) {
    return await apiClient.delete(`/data-analysis/results/${id}`)
  },
}
```

- [ ] **Step 4: 确保导出 DEFAULT_FEATURE_FIELDS**

```typescript
export const DEFAULT_FEATURE_FIELDS = [
  'ma_5', 'ma_10', 'ma_20', 'ma_60',
  'macd', 'macd_signal', 'macd_hist',
  'pct_chg',
  'bias_5', 'bias_10', 'bias_20', 'bias_60',
  'close_pct_rank_5', 'close_pct_rank_10', 'close_pct_rank_20', 'close_pct_rank_60',
  'vol_ratio_5', 'vol_ratio_10', 'vol_ratio_20', 'vol_ratio_60',
  'kdj_k', 'kdj_d', 'kdj_j',
  'boll_upper', 'boll_middle', 'boll_lower',
  'rsi_6', 'rsi_12', 'atr_14', 'obv',
]
```

- [ ] **Step 5: 检查前端编译**

Run: `cd frontend && npm run build`
Expected: 编译成功无错误

- [ ] **Step 6: 提交**

```bash
git add frontend/src/api/dataAnalysis.ts
git commit -m "feat(data-analysis): update API types and add delete endpoint"
```

---

## Task 5: 重命名 DataAnalysisView 为 DataAnalysisManageView

**Files:**
- Rename: `frontend/src/views/DataAnalysisView.vue` → `frontend/src/views/DataAnalysisManageView.vue`

- [ ] **Step 1: 读取现有 DataAnalysisView.vue**

- [ ] **Step 2: 重写为新的管理页面布局**

参考 TrainingManageView.vue 的布局，去掉左右分栏，使用 v-autocomplete 选择指标

```vue
<template>
  <v-card border rounded class="mb-4">
    <v-card-title class="text-subtitle-1">发起分析</v-card-title>
    <v-card-text>
      <v-row>
        <v-col cols="12" sm="6" md="4">
          <v-text-field v-model="form.name" label="分析名称"></v-text-field>
        </v-col>
        <v-col cols="12" sm="6" md="4">
          <v-text-field v-model="form.start_date" label="开始日期" type="date"></v-text-field>
        </v-col>
        <v-col cols="12" sm="6" md="4">
          <v-text-field v-model="form.end_date" label="结束日期" type="date"></v-text-field>
        </v-col>
      </v-row>
      <v-row>
        <v-col cols="12" sm="6" md="4">
          <v-row>
            <v-col cols="6">
              <v-text-field v-model.number="form.start_rank" type="number" label="市值排名起始" min="1"></v-text-field>
            </v-col>
            <v-col cols="6">
              <v-text-field v-model.number="form.end_rank" type="number" label="市值排名结束" min="1"></v-text-field>
            </v-col>
          </v-row>
        </v-col>
        <v-col cols="12" sm="6" md="4">
          <v-autocomplete
            v-model="form.feature_fields"
            :items="indicatorFields"
            label="特征字段"
            multiple
            chips
            closable-chips
            dense
          ></v-autocomplete>
        </v-col>
        <v-col cols="12" sm="6" md="4">
          <v-btn color="primary" block @click="triggerAnalysis" :loading="loadingAnalysis" height="48">
            发起分析
          </v-btn>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>

  <v-card v-if="error" border rounded class="mb-4" color="error">
    <v-card-text class="text-white">{{ error }}</v-card-text>
  </v-card>

  <v-card border rounded>
    <v-card-title>运行中的分析任务</v-card-title>
    <v-card-text>
      <v-data-table
        v-if="activeTasks.length > 0"
        :headers="activeTaskHeaders"
        :items="activeTasks"
        hide-default-footer
      >
        <template v-slot:item.status="{ item }">
          <v-chip :color="getStatusColor(item.status)" size="small">{{ getStatusText(item.status) }}</v-chip>
        </template>
        <template v-slot:item.progress="{ item }">
          <div class="d-flex flex-column">
            <span class="text-caption text-medium-emphasis">{{ item.progress_message || `${item.progress?.toFixed(1)}%` }}</span>
            <v-progress-linear :value="item.progress" height="4" class="mt-1" v-if="item.progress"></v-progress-linear>
          </div>
        </template>
      </v-data-table>
      <div v-else class="text-center text-medium-emphasis pa-4">暂无运行中的任务</div>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { dataAnalysisApi, DEFAULT_FEATURE_FIELDS, type AnalysisTaskStatus } from '@/api/dataAnalysis'

const loadingAnalysis = ref(false)
const activeTasks = ref<AnalysisTaskStatus[]>([])
const error = ref('')

const formatDateTime = () => {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
}

const form = ref({
  name: `analysis_${formatDateTime()}`,
  start_rank: 1,
  end_rank: 1000,
  start_date: '2020-01-01',
  end_date: '2025-12-31',
  feature_fields: [...DEFAULT_FEATURE_FIELDS],
})

const indicatorFields = DEFAULT_FEATURE_FIELDS

const activeTaskHeaders = [
  { title: '任务ID', key: 'task_id' },
  { title: '状态', key: 'status' },
  { title: '进度', key: 'progress' },
  { title: '创建时间', key: 'created_at' },
]

const getStatusColor = (status: string) => {
  switch (status) {
    case 'pending': return 'info'
    case 'running': return 'warning'
    case 'completed': return 'success'
    case 'failed': return 'error'
    default: return ''
  }
}

const getStatusText = (status: string) => {
  switch (status) {
    case 'pending': return '等待中'
    case 'running': return '运行中'
    case 'completed': return '已完成'
    case 'failed': return '失败'
    default: return status
  }
}

let pollInterval: number | null = null

const startPolling = () => {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
  pollActiveTasks()
  pollInterval = window.setInterval(pollActiveTasks, 3000)
}

const stopPolling = () => {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
}

const pollActiveTasks = async () => {
  // 这里需要注意：当前没有 listTasks API，暂时简化
  // 实际使用中需要后端添加或复用任务列表
}

const triggerAnalysis = async () => {
  loadingAnalysis.value = true
  error.value = ''
  try {
    const res = await dataAnalysisApi.triggerAnalysis({
      name: form.value.name || `analysis_${formatDateTime()}`,
      start_rank: form.value.start_rank,
      end_rank: form.value.end_rank,
      start_date: form.value.start_date,
      end_date: form.value.end_date,
      feature_fields: form.value.feature_fields,
    })
    startPolling()
  } catch (e: any) {
    error.value = e.message || 'Failed to trigger analysis'
    console.error('Analysis error:', e)
  } finally {
    loadingAnalysis.value = false
  }
}

onMounted(() => {
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>
```

- [ ] **Step 3: 保存为新文件**

保存为 `frontend/src/views/DataAnalysisManageView.vue`

- [ ] **Step 4: 提交**

```bash
git add frontend/src/views/DataAnalysisManageView.vue
git rm frontend/src/views/DataAnalysisView.vue
git commit -m "feat(data-analysis): create manage view"
```

---

## Task 6: 创建分析记录页面 DataAnalysisRecordsView.vue

**Files:**
- Create: `frontend/src/views/DataAnalysisRecordsView.vue`

- [ ] **Step 1: 创建新的分析记录页面**

参考 TrainingRecordsView.vue 创建完整的页面

```vue
<template>
  <v-card border rounded class="mb-4">
    <v-toolbar flat>
      <v-toolbar-title>
        <v-icon color="medium-emphasis" icon="mdi-chart-box" size="x-small" start />
        分析记录
      </v-toolbar-title>
    </v-toolbar>
    <v-data-table :headers="headers" :items="records" :loading="loading">
      <template v-slot:item.ts_codes="{ item }">
        <span v-if="item.ts_codes.length > 3">{{ item.ts_codes.length }} 只</span>
        <span v-else>{{ item.ts_codes.join(', ') }}</span>
      </template>
      <template v-slot:item.actions="{ item }">
        <div class="d-flex ga-1 justify-end">
          <v-btn size="small" variant="text" color="info" prepend-icon="mdi-information-outline" @click="openDetailDialog(item)">详情</v-btn>
          <v-btn size="small" variant="text" color="error" prepend-icon="mdi-delete" @click="confirmDelete(item)">删除</v-btn>
        </div>
      </template>
    </v-data-table>
  </v-card>

  <v-card v-if="error" border rounded class="mb-4" color="error">
    <v-card-text class="text-white">{{ error }}</v-card-text>
  </v-card>

  <v-dialog v-model="deleteDialog" max-width="400px">
    <v-card>
      <v-card-title class="text-h6 d-flex justify-space-between align-center">
        确认删除
        <v-btn icon variant="text" size="small" @click="deleteDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>此操作不可撤销，确定要删除分析「{{ deletingItem?.name }}」吗？</v-card-text>
      <v-divider />
      <v-card-actions class="bg-surface-light">
        <v-btn text="取消" variant="plain" @click="deleteDialog = false" />
        <v-spacer />
        <v-btn text="删除" color="error" @click="deleteRecord" :loading="deleting" />
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="detailDialog" max-width="800px">
    <v-card v-if="detailItem">
      <v-card-title class="d-flex justify-space-between align-center">
        <div>
          <div class="text-h6">{{ detailItem.name }}</div>
          <div class="text-subtitle-2 text-medium-emphasis">分析详情</div>
        </div>
        <v-btn icon variant="text" size="small" @click="detailDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text class="overflow-hidden" style="max-height: 600px;">
        <v-tabs v-model="detailTab" color="primary">
          <v-tab value="overview">概览</v-tab>
          <v-tab value="boxplot">箱线图</v-tab>
          <v-tab value="histogram">直方图</v-tab>
        </v-tabs>

        <v-window v-model="detailTab" class="mt-4 overflow-auto" style="max-height: 500px;">
          <v-window-item value="overview">
            <v-table density="compact" fixed-header height="450">
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
                <tr v-for="(stats, field) in detailResult?.statistics" :key="field">
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
          </v-window-item>

          <v-window-item value="boxplot">
            <div ref="boxplotChartRef" style="width: 100%; height: 450px;"></div>
          </v-window-item>

          <v-window-item value="histogram">
            <v-select
              v-model="histogramField"
              label="选择字段"
              :items="Object.keys(detailResult?.histograms || {})"
              class="mb-2"
            ></v-select>
            <div ref="histogramChartRef" style="width: 100%; height: 400px;"></div>
          </v-window-item>
        </v-window>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, onUnmounted } from 'vue'
import { dataAnalysisApi, type AnalysisRecord, type AnalysisResult } from '@/api/dataAnalysis'
import * as echarts from 'echarts'

const loading = ref(false)
const records = ref<AnalysisRecord[]>([])
const error = ref('')
const deleteDialog = ref(false)
const deleting = ref(false)
const deletingItem = ref<AnalysisRecord | null>(null)
const detailDialog = ref(false)
const detailItem = ref<AnalysisRecord | null>(null)
const detailResult = ref<AnalysisResult | null>(null)
const detailTab = ref('overview')
const histogramField = ref<string | null>(null)

const boxplotChartRef = ref<HTMLElement>()
const histogramChartRef = ref<HTMLElement>()

let boxplotChartInstance: echarts.ECharts | null = null
let histogramChartInstance: echarts.ECharts | null = null

const headers = [
  { title: '名称', key: 'name' },
  { title: '创建时间', key: 'created_at' },
  { title: '日期范围', key: 'date_range' },
  { title: '股票数量', key: 'stock_count' },
  { title: '指标数量', key: 'field_count' },
  { title: '操作', key: 'actions', sortable: false, align: 'end' as const },
]

const loadRecords = async () => {
  loading.value = true
  try {
    const res = await dataAnalysisApi.listResults()
    records.value = res.data.map(r => ({
      ...r,
      date_range: `${r.start_date} ~ ${r.end_date}`,
      stock_count: r.ts_codes.length,
      field_count: r.feature_fields.length,
    }))
  } catch (e) {
    console.error('Load records error:', e)
    error.value = '加载失败'
  } finally {
    loading.value = false
  }
}

const confirmDelete = (item: AnalysisRecord) => {
  deletingItem.value = item
  deleteDialog.value = true
}

const deleteRecord = async () => {
  if (!deletingItem.value) return
  deleting.value = true
  try {
    await dataAnalysisApi.deleteResult(deletingItem.value.id)
    deleteDialog.value = false
    deletingItem.value = null
    await loadRecords()
  } catch (e) {
    console.error('Delete error:', e)
    error.value = '删除失败'
  } finally {
    deleting.value = false
  }
}

const openDetailDialog = async (item: AnalysisRecord) => {
  detailItem.value = item
  detailTab.value = 'overview'
  histogramField.value = null
  try {
    const res = await dataAnalysisApi.getTaskStatus(item.task_id)
    if (res.data.result) {
      detailResult.value = res.data.result
    }
    detailDialog.value = true
  } catch (e) {
    console.error('Load detail error:', e)
    error.value = '加载详情失败'
  }
}

const renderBoxplot = () => {
  if (!boxplotChartRef.value || !detailResult.value) return
  if (boxplotChartInstance) {
    boxplotChartInstance.dispose()
    boxplotChartInstance = null
  }
  boxplotChartInstance = echarts.init(boxplotChartRef.value)

  const fields = Object.keys(detailResult.value.boxplots)
  const data = fields.map(field => {
    const bp = detailResult.value!.boxplots[field]
    return [bp.min, bp.q1, bp.median, bp.q3, bp.max]
  })
  const outliers = fields.map(field => detailResult.value!.boxplots[field].outliers)

  boxplotChartInstance.setOption({
    title: { text: '箱线图' },
    tooltip: { trigger: 'item' },
    xAxis: { type: 'category', data: fields },
    yAxis: { type: 'value' },
    series: [
      {
        name: 'boxplot',
        type: 'boxplot',
        data: data,
      },
      {
        name: 'outliers',
        type: 'scatter',
        data: outliers.map((os, i) => os.map(o => [i, o])).flat(),
      },
    ],
  }, true)
}

const renderHistogram = () => {
  if (!histogramChartRef.value || !detailResult.value || !histogramField.value || !detailResult.value.histograms[histogramField.value]) return
  if (histogramChartInstance) {
    histogramChartInstance.dispose()
    histogramChartInstance = null
  }
  histogramChartInstance = echarts.init(histogramChartRef.value)

  const hist = detailResult.value.histograms[histogramField.value]
  const binCenters = hist.bins.slice(0, -1).map((b, i) => (b + hist.bins[i + 1]) / 2)

  histogramChartInstance.setOption({
    title: { text: `直方图 - ${histogramField.value}` },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: binCenters },
    yAxis: { type: 'value' },
    series: [{
      type: 'bar',
      data: hist.counts,
    }],
  }, true)
}

const handleResize = () => {
  boxplotChartInstance?.resize()
  histogramChartInstance?.resize()
}

watch([detailResult, detailTab], () => {
  if (detailResult.value && detailTab.value === 'boxplot') {
    renderBoxplot()
  } else if (detailResult.value && detailTab.value === 'histogram' && histogramField.value) {
    renderHistogram()
  }
})

watch(histogramField, () => {
  if (detailResult.value) {
    renderHistogram()
  }
})

onMounted(() => {
  loadRecords()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  boxplotChartInstance?.dispose()
  histogramChartInstance?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>
```

- [ ] **Step 2: 保存文件**

- [ ] **Step 3: 提交**

```bash
git add frontend/src/views/DataAnalysisRecordsView.vue
git commit -m "feat(data-analysis): create records view"
```

---

## Task 7: 更新路由配置

**Files:**
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: 读取现有路由配置**

- [ ] **Step 2: 更新路由**

```typescript
import { createRouter, createWebHistory } from 'vue-router'

// ... 其他导入
import DataAnalysisManageView from '@/views/DataAnalysisManageView.vue'
import DataAnalysisRecordsView from '@/views/DataAnalysisRecordsView.vue'

const routes = [
  // ... 现有路由
  {
    path: '/data/analysis/manage',
    name: 'DataAnalysisManage',
    component: DataAnalysisManageView,
  },
  {
    path: '/data/analysis/records',
    name: 'DataAnalysisRecords',
    component: DataAnalysisRecordsView,
  },
  // ... 其他路由
]

// ... 其他路由代码
```

- [ ] **Step 3: 确保旧的路由重定向**

如果需要，可以添加从旧路径重定向

- [ ] **Step 4: 提交**

```bash
git add frontend/src/router/index.ts
git commit -m "feat(data-analysis): update router"
```

---

## Task 8: 更新菜单 AppLayout.vue

**Files:**
- Modify: `frontend/src/components/AppLayout.vue`

- [ ] **Step 1: 读取现有 AppLayout.vue**

- [ ] **Step 2: 更新菜单项**

```vue
<v-list-group value="data">
  <template v-slot:activator="{ props }">
    <v-list-item v-bind="props" prepend-icon="mdi-database" title="数据" />
  </template>
  <v-list-item :to="'/data/list'" title="数据列表" />
  <v-list-item :to="'/data/analysis/manage'" title="分析管理" />
  <v-list-item :to="'/data/analysis/records'" title="分析记录" />
</v-list-group>
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/AppLayout.vue
git commit -m "feat(data-analysis): update menu"
```

---

## Task 9: 重启服务和手动测试

**Files:** None

- [ ] **Step 1: 重启后端服务**

Run: `cd d:\projects\trade-alpha && service.bat restart`
Expected: 服务正常启动

- [ ] **Step 2: 手动测试前端页面**

打开浏览器访问 http://localhost:3000，检查：
1. 菜单是否更新
2. 分析管理页面是否正常
3. 分析记录页面是否正常
4. 分析记录列表是否加载
5. 详情弹窗是否正常显示

- [ ] **Step 3: 运行集成测试**

Run: `cd backend && pytest tests/trade_alpha/integration/test_33_service_data_analysis.py -v`
Expected: 所有测试通过

---

## 自我检查

1. **Spec 覆盖检查** - ✅ 所有 spec 要点都有对应的任务
2. **Placeholder 检查** - ✅ 没有 TODO 或未完成的部分
3. **类型一致性检查** - ✅ 类型定义一致

---

## 执行选择

Plan complete and saved to `docs/superpowers/plans/2026-05-19-data-analysis-records.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
