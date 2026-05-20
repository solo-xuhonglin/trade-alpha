# 训练标准化数据分析 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在训练流程中自动分析标准化后的数据，在训练记录列表增加分析入口，复用数据分析弹窗

**Architecture:** 后端从 `analysis_service.py` 提取 `compute_field_analysis` 纯函数，训练流程新增 `_analyze_normalized_data` 函数复用该函数；前端从 `DataAnalysisRecordsView.vue` 提取 `AnalysisDetailDialog.vue` 公共组件，两边共用

**Tech Stack:** Python (FastAPI, Beanie, pandas/numpy), Vue 3 (Vuetify, ECharts), TypeScript

---

## 文件映射

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/src/trade_alpha/data/analysis_service.py` | 重构 | 提取 `compute_field_analysis` 纯函数 |
| `backend/src/trade_alpha/dao/training.py` | 修改 | 字段重命名 + 新增 `normalized_data_analysis` |
| `backend/src/trade_alpha/predict/training_service.py` | 修改 | 新增 `_analyze_normalized_data`；字段重命名 |
| `backend/src/trade_alpha/api/routers/trainings.py` | 修改 | 列表/详情响应拆分；字段重命名 |
| `frontend/src/components/AnalysisDetailDialog.vue` | **新建** | 公共分析详情弹窗组件 |
| `frontend/src/views/DataAnalysisRecordsView.vue` | 修改 | 改用公共组件 |
| `frontend/src/views/TrainingRecordsView.vue` | 修改 | 详情调 API + 分析入口 + 字段名更新 |
| `frontend/src/api/trainingRecord.ts` | 修改 | 类型定义拆分 + 详情API |

---

### Task 1: 重构 `analysis_service.py` — 提取 `compute_field_analysis` 纯函数

**Files:**
- Modify: `backend/src/trade_alpha/data/analysis_service.py`

- [ ] **Step 1: 提取 `compute_field_analysis` 纯函数**

在 `analysis_service.py` 中，把循环计算每个字段的统计逻辑提取为独立函数。该函数接受 DataFrame + feature_fields，返回分析结果字典，不依赖数据库。

```python
def compute_field_analysis(df: pd.DataFrame, feature_fields: List[str]) -> Dict[str, Any]:
    """Analyze fields in a DataFrame and return statistics/histograms/boxplots/missing_data.

    Pure function - no database dependency. Can be reused by both
    run_data_analysis (raw data) and training pipeline (normalized data).

    Args:
        df: DataFrame containing feature_fields columns
        feature_fields: List of field names to analyze

    Returns:
        Dict with keys: statistics, histograms, boxplots, missing_data
    """
    from trade_alpha.data.analysis_service import calculate_outlier_rate
    import numpy as np

    statistics = {}
    histograms = {}
    boxplots = {}
    missing_data = {}

    for field in feature_fields:
        if field not in df.columns:
            continue

        vals = df[field].dropna()
        if len(vals) == 0:
            continue

        statistics[field] = {
            "mean": float(vals.mean()),
            "std": float(vals.std()),
            "median": float(vals.median()),
            "q1": float(vals.quantile(0.25)),
            "q3": float(vals.quantile(0.75)),
            "min": float(vals.min()),
            "max": float(vals.max()),
            "missing_rate": float(1 - len(vals) / len(df)),
            "outlier_rate": float(calculate_outlier_rate(vals)),
        }

        try:
            counts, bins = np.histogram(vals.dropna(), bins=30)
            histograms[field] = {
                "bins": [float(b) for b in bins],
                "counts": [int(c) for c in counts],
            }
        except Exception:
            pass

        q1 = vals.quantile(0.25)
        q3 = vals.quantile(0.75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        outliers = vals[(vals < lower_bound) | (vals > upper_bound)].tolist()

        boxplots[field] = {
            "min": float(vals.min()),
            "q1": float(q1),
            "median": float(vals.median()),
            "q3": float(q3),
            "max": float(vals.max()),
            "outliers": [float(o) for o in outliers[:100]],
        }

        missing_data[field] = {
            "total": len(df),
            "missing": int(df[field].isna().sum()),
            "rate": float(df[field].isna().mean()),
        }

    return {
        "statistics": statistics,
        "histograms": histograms,
        "boxplots": boxplots,
        "missing_data": missing_data,
    }
```

将该函数放在 `calculate_outlier_rate` 之后、`run_data_analysis` 之前。注意需要在文件顶部添加 `from typing import Dict, Any`（如果还没有的话）。

- [ ] **Step 2: 重构 `run_data_analysis` 复用 `compute_field_analysis`**

```python
async def run_data_analysis(
    ts_codes: List[str],
    start_date: str,
    end_date: str,
    feature_fields: List[str],
    progress_callback: Optional[Callable] = None,
) -> Dict[str, Any]:
    """Run data analysis and return results."""

    async def update_progress(progress: float, message: str):
        if progress_callback:
            await progress_callback(progress, message)

    start_date = to_db_format(start_date)
    end_date = to_db_format(end_date)

    await update_progress(10, "Loading data from database...")

    all_dfs = []
    for ts_code in ts_codes:
        records = await StockDaily.find(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date >= start_date,
            StockDaily.trade_date <= end_date,
        ).sort(StockDaily.trade_date).to_list()
        if records:
            df = pd.DataFrame([r.model_dump() for r in records])
            df["ts_code"] = ts_code
            all_dfs.append(df)

    if not all_dfs:
        raise ValueError("No data found")

    df = pd.concat(all_dfs, ignore_index=True)
    await update_progress(30, "Calculating statistics...")

    result = compute_field_analysis(df, feature_fields)

    await update_progress(60, "Generating chart data...")
    await update_progress(90, "Saving results...")

    return result
```

移除原有的循环计算逻辑（statistics/histograms/boxplots/missing_data 的 for 循环体）。

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/data/analysis_service.py
git commit -m "refactor: extract compute_field_analysis pure function from run_data_analysis"
```

---

### Task 2: 更新 `TrainingResult` 数据模型

**Files:**
- Modify: `backend/src/trade_alpha/dao/training.py`

- [ ] **Step 1: 修改字段定义**

将 `metrics` 重命名为 `model_metrics`，并新增 `normalized_data_analysis` 字段：

```python
class TrainingResult(Document):
    """Training result document for MongoDB."""

    config_id: PydanticObjectId
    name: str
    ts_codes: List[str] = Field(default_factory=list)
    start_date: str
    end_date: str
    feature_fields: List[str] = Field(default_factory=list)
    classification_horizons: List[int] = Field(default_factory=lambda: [3, 5])
    model_metrics: Dict[str, Any] = Field(default_factory=dict)       # 原 metrics
    normalized_data_analysis: Optional[Dict[str, Any]] = None          # 新增
    model_path: Optional[str] = None
    created_at: Optional[datetime] = None

    class Settings:
        name = "training_results"
        indexes = [
            IndexModel("name", unique=True),
            "config_id"
        ]
```

- [ ] **Step 2: 提交**

```bash
git add backend/src/trade_alpha/dao/training.py
git commit -m "feat: rename metrics to model_metrics, add normalized_data_analysis field"
```

---

### Task 3: 修改训练流程 — 新增 `_analyze_normalized_data`

**Files:**
- Modify: `backend/src/trade_alpha/predict/training_service.py`

- [ ] **Step 1: 新增 `_analyze_normalized_data` 函数**

在 `_normalize_data` 函数之后添加：

```python
def _analyze_normalized_data(
    all_X: List[np.ndarray],
    feature_fields: List[str],
) -> Dict[str, Any]:
    """Analyze normalized data collected during training.

    Args:
        all_X: List of normalized feature arrays from each year
        feature_fields: Feature field names

    Returns:
        Analysis result dict with statistics/histograms/boxplots/missing_data
    """
    from trade_alpha.data.analysis_service import compute_field_analysis

    normalized_df = pd.DataFrame(np.vstack(all_X), columns=feature_fields)
    result = compute_field_analysis(normalized_df, feature_fields)
    for field in result["statistics"]:
        result["statistics"][field]["missing_rate"] = 0.0
    for field in result["missing_data"]:
        result["missing_data"][field]["missing"] = 0
        result["missing_data"][field]["rate"] = 0.0
    return result
```

- [ ] **Step 2: 在 `create_training` 中调用**

在评估完成后、保存之前，添加调用：

```python
# 评估完成后，分析标准化数据
stage += 1
await update(stage, "正在分析标准化数据...")
training.normalized_data_analysis = _analyze_normalized_data(all_X, config.feature_fields)
```

- [ ] **Step 3: 全局替换 `metrics` → `model_metrics`**

搜索文件中所有 `metrics` 引用，替换为 `model_metrics`，包括：
- `create_training` 函数中：`"metrics": {"sample_count": sample_count, **eval_metrics}` → `"model_metrics": {"sample_count": sample_count, **eval_metrics}`
- 其他函数中所有 `training.metrics` → `training.model_metrics`

调整 `total_stages` 计算，增加一个 stages：

```python
total_stages = len(years) * 2 + 1 + 5 + 1 + 1  # 加载→标签→训练→CV5→评估→标准化分析
```

- [ ] **Step 4: 提交**

```bash
git add backend/src/trade_alpha/predict/training_service.py
git commit -m "feat: add normalized data analysis in training pipeline, rename metrics to model_metrics"
```

---

### Task 4: 修改训练 API 路由

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/trainings.py`

- [ ] **Step 1: 精简列表接口 `GET /trainings`**

将所有 `t.metrics` 替换为 `t.model_metrics`。列表接口不返回 `model_metrics` 和 `normalized_data_analysis`：

```python
@router.get("")
async def list_trainings(config_id: str = Query(None)):
    """List trainings."""
    try:
        if config_id:
            c_id = PydanticObjectId(config_id)
            trainings = await training_service.list_trainings(config_id=c_id)
        else:
            trainings = await training_service.list_trainings()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid config ID format")

    return [
        {
            "id": str(t.id),
            "config_id": str(t.config_id),
            "name": t.name,
            "ts_codes": t.ts_codes,
            "start_date": to_api_format(t.start_date),
            "end_date": to_api_format(t.end_date),
            "created_at": t.created_at,
        }
        for t in trainings
    ]
```

- [ ] **Step 2: 详情接口 `GET /trainings/{training_id}` 完整返回**

将所有 `t.metrics` 替换为 `t.model_metrics`，并新增 `normalized_data_analysis`：

```python
@router.get("/{training_id}")
async def get_training(training_id: str):
    """Get training by ID."""
    try:
        obj_id = PydanticObjectId(training_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid training ID")

    t = await training_service.get_training_by_id(obj_id)
    if not t:
        raise HTTPException(status_code=404, detail="Training not found")
    return {
        "id": str(t.id),
        "config_id": str(t.config_id),
        "name": t.name,
        "ts_codes": t.ts_codes,
        "start_date": to_api_format(t.start_date),
        "end_date": to_api_format(t.end_date),
        "model_metrics": t.model_metrics,
        "normalized_data_analysis": t.normalized_data_analysis,
        "created_at": t.created_at,
    }
```

- [ ] **Step 3: 提交**

```bash
git add backend/src/trade_alpha/api/routers/trainings.py
git commit -m "feat: split training list/detail API, add normalized_data_analysis to detail"
```

---

### Task 5: 更新前端类型定义 — `trainingRecord.ts`

**Files:**
- Modify: `frontend/src/api/trainingRecord.ts`

- [ ] **Step 1: 重写类型定义和API**

```typescript
import api from './index'
import type { AnalysisResult } from './dataAnalysis'

export interface TrainingMetrics {
  sample_count: number
  accuracy?: Record<string, number>
  cv_mean?: Record<string, number>
  cv_std?: Record<string, number>
  cv_scores?: Record<string, number[]>
  feature_importance?: Record<string, Record<string, number>>
  class_distribution?: Record<string, Record<string, number>>
}

export interface Training {
  id: string
  config_id: string
  name: string
  ts_codes: string[]
  start_date: string
  end_date: string
  created_at: string
}

export interface TrainingDetail extends Training {
  model_metrics: TrainingMetrics
  normalized_data_analysis: AnalysisResult | null
}

export const trainingRecordApi = {
  list: (configId?: string) => {
    const params = configId ? { config_id: configId } : {}
    return api.get<Training[]>('/trainings', { params })
  },

  get: (id: string) => api.get<TrainingDetail>(`/trainings/${id}`),

  delete: (id: string) => api.delete(`/trainings/${id}`),
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/api/trainingRecord.ts
git commit -m "feat: update training API types with detail endpoint and model_metrics"
```

---

### Task 6: 提取公共分析详情组件 `AnalysisDetailDialog.vue`

**Files:**
- Create: `frontend/src/components/AnalysisDetailDialog.vue`

- [ ] **Step 1: 创建公共组件**

从 `DataAnalysisRecordsView.vue` 中提取详情弹窗逻辑到一个独立组件：

```vue
<template>
  <v-dialog :model-value="dialog" @update:model-value="$emit('update:dialog', $event)" max-width="1200px">
    <v-card v-if="result">
      <v-card-title class="d-flex justify-space-between align-center">
        {{ title }}
        <v-btn icon variant="text" size="small" @click="$emit('update:dialog', false)">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text class="overflow-hidden" style="max-height: 95vh;">
        <v-tabs v-model="tab" color="primary">
          <v-tab value="overview">概览</v-tab>
          <v-tab value="boxplot">箱线图</v-tab>
          <v-tab value="histogram">直方图</v-tab>
        </v-tabs>

        <v-window v-model="tab" class="mt-4" style="max-height: calc(95vh - 150px); overflow-y: auto;">
          <v-window-item value="overview">
            <v-table density="compact" fixed-header style="max-height: calc(95vh - 250px);">
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
                <tr v-for="(stats, field) in result.statistics" :key="field">
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
            <v-select
              v-model="boxplotField"
              label="选择字段"
              :items="Object.keys(result.boxplots || {})"
              class="mb-2"
            />
            <div ref="boxplotChartRef" style="width: 100%; height: calc(95vh - 350px); min-height: 450px;"></div>
          </v-window-item>

          <v-window-item value="histogram">
            <v-select
              v-model="histogramField"
              label="选择字段"
              :items="Object.keys(result.histograms || {})"
              class="mb-2"
            />
            <div ref="histogramChartRef" style="width: 100%; height: calc(95vh - 350px); min-height: 450px;"></div>
          </v-window-item>
        </v-window>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import type { AnalysisResult } from '@/api/dataAnalysis'
import * as echarts from 'echarts'

const props = defineProps<{
  dialog: boolean
  title: string
  result: AnalysisResult | null
}>()

const emit = defineEmits<{
  'update:dialog': [value: boolean]
}>()

const tab = ref('overview')
const boxplotField = ref<string | null>(null)
const histogramField = ref<string | null>(null)

const boxplotChartRef = ref<HTMLElement>()
const histogramChartRef = ref<HTMLElement>()

let boxplotChartInstance: echarts.ECharts | null = null
let histogramChartInstance: echarts.ECharts | null = null

const renderBoxplot = () => {
  if (!boxplotChartRef.value || !props.result || !boxplotField.value || !props.result.boxplots[boxplotField.value]) return
  if (boxplotChartInstance) {
    boxplotChartInstance.dispose()
    boxplotChartInstance = null
  }
  boxplotChartInstance = echarts.init(boxplotChartRef.value)

  const field = boxplotField.value
  const bp = props.result.boxplots[field]
  const data = [[bp.min, bp.q1, bp.median, bp.q3, bp.max]]
  const outliers = bp.outliers.map((o: number) => [0, o])

  boxplotChartInstance.setOption({
    title: { text: `箱线图 - ${field}` },
    tooltip: { trigger: 'item' },
    xAxis: { type: 'category', data: [field] },
    yAxis: { type: 'value' },
    series: [
      { name: 'boxplot', type: 'boxplot', data: data },
      { name: 'outliers', type: 'scatter', data: outliers },
    ],
  }, true)
}

const renderHistogram = () => {
  if (!histogramChartRef.value || !props.result || !histogramField.value || !props.result.histograms[histogramField.value]) return
  if (histogramChartInstance) {
    histogramChartInstance.dispose()
    histogramChartInstance = null
  }
  histogramChartInstance = echarts.init(histogramChartRef.value)

  const hist = props.result.histograms[histogramField.value]
  const binCenters = hist.bins.slice(0, -1).map((b: number, i: number) => (b + hist.bins[i + 1]) / 2)

  histogramChartInstance.setOption({
    title: { text: `直方图 - ${histogramField.value}` },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: binCenters },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', data: hist.counts }],
  }, true)
}

const handleResize = () => {
  boxplotChartInstance?.resize()
  histogramChartInstance?.resize()
}

watch([() => props.result, tab], () => {
  if (props.result && tab.value === 'boxplot' && boxplotField.value) {
    renderBoxplot()
  } else if (props.result && tab.value === 'histogram' && histogramField.value) {
    renderHistogram()
  }
})

watch(boxplotField, () => {
  if (props.result) renderBoxplot()
})

watch(histogramField, () => {
  if (props.result) renderHistogram()
})

onUnmounted(() => {
  boxplotChartInstance?.dispose()
  histogramChartInstance?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/AnalysisDetailDialog.vue
git commit -m "feat: extract AnalysisDetailDialog shared component"
```

---

### Task 7: 改造 `DataAnalysisRecordsView.vue` 使用公共组件

**Files:**
- Modify: `frontend/src/views/DataAnalysisRecordsView.vue`

- [ ] **Step 1: 移除内联详情弹窗，引入 `AnalysisDetailDialog`**

在 `<script>` 中引入组件：

```typescript
import AnalysisDetailDialog from '@/components/AnalysisDetailDialog.vue'
```

移除现有的 `<v-dialog>` 详情弹窗块（从 `v-model="detailDialog"` 到对应的 `</v-dialog>`），替换为：

```vue
<AnalysisDetailDialog
  v-model:dialog="detailDialog"
  :title="detailItem?.name || ''"
  :result="detailResult"
/>
```

同时移除原有的 detailDialog 内部相关变量：`detailTab`、`boxplotField`、`histogramField`、`boxplotChartRef`、`histogramChartRef`、`boxplotChartInstance`、`histogramChartInstance`、`renderBoxplot`、`renderHistogram`、`handleResize`，以及 `onUnmounted` 中的 dispose 逻辑。这些已经移到公共组件中。

保留 `detailItem`、`detailResult`、`detailDialog` 变量和 `openDetailDialog` 函数。

移除 `import * as echarts from 'echarts'`（组件内已包含）。

移除 `watch` 和 `onUnmounted` 中对 echart 相关逻辑的引用。

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/DataAnalysisRecordsView.vue
git commit -m "refactor: use AnalysisDetailDialog in data analysis records view"
```

---

### Task 8: 改造 `TrainingRecordsView.vue` — 详情调API + 新增分析入口

**Files:**
- Modify: `frontend/src/views/TrainingRecordsView.vue`

- [ ] **Step 1: 引入新组件和类型**

```typescript
import { trainingRecordApi, type Training, type TrainingDetail } from '@/api/trainingRecord'
import AnalysisDetailDialog from '@/components/AnalysisDetailDialog.vue'
import type { AnalysisResult } from '@/api/dataAnalysis'
```

- [ ] **Step 2: 修改 `detailItem` 类型和 `openDetailDialog`**

```typescript
const detailItem = ref<TrainingDetail | null>(null)
```

```typescript
const openDetailDialog = async (item: Training) => {
  const res = await trainingRecordApi.get(item.id)
  detailItem.value = res.data
  featureTarget.value = 'label_3d'
  detailTab.value = 'overview'
  detailDialog.value = true
}
```

- [ ] **Step 3: 替换所有 `metrics` 引用为 `model_metrics`**

在模板和 script 中搜索替换：
- `detailItem.metrics` → `detailItem.model_metrics`
- `item.metrics` → `item.model_metrics`

涉及位置（模板中）：
- `detailItem.metrics.sample_count`
- `detailItem.metrics.accuracy`
- `detailItem.metrics.class_distribution`
- `detailItem.metrics.cv_mean`
- `detailItem.metrics.cv_std`
- `detailItem.metrics.cv_scores`
- `detailItem.metrics.feature_importance`

script 中：
- `t.metrics` → `t.model_metrics`
- 列表映射中的 `t.metrics.accuracy`, `t.metrics.cv_mean` 等
- `detailItem.value?.metrics.feature_importance` → `detailItem.value?.model_metrics.feature_importance`

- [ ] **Step 4: 新增分析入口**

操作列增加分析按钮：

```vue
<v-btn size="small" variant="text" color="secondary" prepend-icon="mdi-chart-box-outline" @click="openAnalysisDialog(item)">分析</v-btn>
```

新增状态变量：

```typescript
const analysisDialog = ref(false)
const analysisResult = ref<AnalysisResult | null>(null)
const analysisTitle = ref('')
```

新增 `openAnalysisDialog`：

```typescript
const openAnalysisDialog = async (item: Training) => {
  const res = await trainingRecordApi.get(item.id)
  if (res.data.normalized_data_analysis) {
    analysisResult.value = res.data.normalized_data_analysis
    analysisTitle.value = `${item.name} - 标准化数据分析`
    analysisDialog.value = true
  }
}
```

在模板末尾（`</v-card>` 之后）添加组件：

```vue
<AnalysisDetailDialog
  v-model:dialog="analysisDialog"
  :title="analysisTitle"
  :result="analysisResult"
/>
```

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/TrainingRecordsView.vue
git commit -m "feat: add analysis entry in training records, use detail API for metrics"
```

---

## 自审

1. **Spec 覆盖** — 所有 spec section 都有对应 task：
   - 后端 `compute_field_analysis` 提取 → Task 1
   - `TrainingResult` 字段扩展 → Task 2
   - `_analyze_normalized_data` 函数 → Task 3
   - API 列表/详情拆分 → Task 4
   - 前端类型定义 → Task 5
   - `AnalysisDetailDialog` 公共组件 → Task 6
   - `DataAnalysisRecordsView` 改造 → Task 7
   - `TrainingRecordsView` 改造 → Task 8
2. **占位符** — 所有步骤包含完整代码，无 "TBD"、"TODO"
3. **类型一致性** — `model_metrics` 在 Task 2(DAO定义) → Task 3(写入) → Task 4(API返回) → Task 5(前端类型) → Task 8(使用) 保持一致
