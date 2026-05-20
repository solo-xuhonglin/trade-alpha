# 训练标准化数据分析

## 背景

现有数据分析功能是对原始股票数据进行统计分析（statistics、histograms、boxplots、missing_data）。训练过程中会对数据进行 Z-score 标准化和缩尾处理，标准化后的数据分布与原始数据差异很大，单独分析标准化数据有助于理解模型看到的特征分布。

## 设计目标

1. 在训练流程中自动对标准化后的数据进行分析
2. 分析结果存入 `TrainingResult`，随详情接口返回
3. 在训练记录列表增加"分析"入口，复用数据分析详情弹窗
4. 原 `metrics` 字段重命名为 `model_metrics`，更明确语义

## 实现方案 — 复用原则

后端和前端的改动都遵循同一个原则：**不复制逻辑，只复用代码**。

### 1. 后端 — TrainingResult 数据结构扩展

**文件**: `backend/src/trade_alpha/dao/training.py`

```python
class TrainingResult(Document):
    ...
    model_metrics: Dict[str, Any] = Field(default_factory=dict)       # 原 metrics，重命名
    normalized_data_analysis: Optional[Dict[str, Any]] = None         # 新增
```

`normalized_data_analysis` 的数据结构与现有 `DataAnalysisResult` 的分析结果完全一致。

### 2. 后端 — 提取纯计算函数，两个场景复用

**文件**: `backend/src/trade_alpha/data/analysis_service.py`

核心改动：把现有 `run_data_analysis` 中针对单个字段的统计计算逻辑提取为纯函数，同时保留原有的完整流程。

```python
def compute_field_analysis(df: pd.DataFrame, feature_fields: List[str]) -> Dict[str, Any]:
    """纯函数：对 DataFrame 中的字段进行统计分析，不依赖数据库。

    入参: DataFrame（必须包含 feature_fields 中的列）
    出参: { statistics, histograms, boxplots, missing_data }
    
    被以下场景复用:
    - run_data_analysis: 从数据库查完数据后调用
    - 训练流程: 标准化后直接调用
    """
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

        # Histogram
        try:
            counts, bins = np.histogram(vals.dropna(), bins=30)
            histograms[field] = {
                "bins": [float(b) for b in bins],
                "counts": [int(c) for c in counts],
            }
        except:
            pass

        # Boxplot
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

然后 `run_data_analysis` 重构为：

```python
async def run_data_analysis(
    ts_codes: List[str],
    start_date: str,
    end_date: str,
    feature_fields: List[str],
    progress_callback: Optional[Callable] = None,
) -> Dict[str, Any]:
    # 1. 从数据库加载数据（原有逻辑）
    ...
    df = pd.concat(all_dfs, ignore_index=True)
    
    # 2. 复用纯函数计算
    await update_progress(30, "Calculating statistics...")
    result = compute_field_analysis(df, feature_fields)
    
    await update_progress(60, "Generating chart data...")
    await update_progress(90, "Saving results...")
    return result
```

### 3. 后端 — 训练流程提取 `_analyze_normalized_data` 函数

**文件**: `backend/src/trade_alpha/predict/training_service.py`

新增私有函数，封装标准化数据分析流程：

```python
from trade_alpha.data.analysis_service import compute_field_analysis


def _analyze_normalized_data(
    all_X: List[np.ndarray],
    feature_fields: List[str],
) -> Dict[str, Any]:
    """对训练过程中收集的标准化数据进行分析。

    Args:
        all_X: 各年标准化特征数据列表
        feature_fields: 特征字段列表

    Returns:
        分析结果字典，结构与 DataAnalysisResult 保持一致
    """
    normalized_df = pd.DataFrame(np.vstack(all_X), columns=feature_fields)
    result = compute_field_analysis(normalized_df, feature_fields)
    for field in result["statistics"]:
        result["statistics"][field]["missing_rate"] = 0.0
    for field in result["missing_data"]:
        result["missing_data"][field]["missing"] = 0
        result["missing_data"][field]["rate"] = 0.0
    return result
```

在 `create_training` 中调用该函数：

```python
# 训练和评估完成后
stage += 1
await update(stage, "正在分析标准化数据...")
training.normalized_data_analysis = _analyze_normalized_data(all_X, config.feature_fields)
```

同时将 `metrics` → `model_metrics` 的所有引用做全局替换。

### 4. 后端 — API 响应结构调整

**文件**: `backend/src/trade_alpha/api/routers/trainings.py`

列表接口 (`GET /trainings`) 精简，不返回 `model_metrics` 和 `normalized_data_analysis`：

```python
return {
    "id": str(t.id),
    "config_id": str(t.config_id),
    "name": t.name,
    "ts_codes": t.ts_codes,
    "start_date": to_api_format(t.start_date),
    "end_date": to_api_format(t.end_date),
    "created_at": t.created_at,
}
```

详情接口 (`GET /trainings/{training_id}`) 完整返回：

```python
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

### 5. 前端 — 提取公共分析详情组件

**文件**: `frontend/src/components/AnalysisDetailDialog.vue`（新建）

从 `DataAnalysisRecordsView.vue` 中提取详情弹窗部分为一个独立组件：

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
        <!-- 完整的 tabs/window 结构：概览表格、箱线图、直方图 -->
        <!-- 与 DataAnalysisRecordsView 现有弹窗完全一致，移过来即可 -->
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

defineEmits<{
  'update:dialog': [value: boolean]
}>()

// 内部逻辑：tabs、echarts 渲染、resize 处理等，从 DataAnalysisRecordsView 移过来
</script>
```

### 6. 前端 — DataAnalysisRecordsView.vue 使用公共组件

移除内联的详情弹窗模板，改为引入 `AnalysisDetailDialog`，传入 `dialog`、`title`、`result` 即可。

### 7. 前端 — TrainingRecordsView.vue 增加分析入口 + 改造现有详情

现有详情弹窗的问题：当前从 `detailItem.metrics.*` 读取数据，但列表接口不再返回 `model_metrics`。需要改为调详情 API。

**改造现有详情弹窗** — `openDetailDialog` 改为调详情 API：

```typescript
const openDetailDialog = async (item: Training) => {
  const res = await trainingRecordApi.get(item.id)
  detailItem.value = res.data
  featureTarget.value = 'label_3d'
  detailTab.value = 'overview'
  detailDialog.value = true
}
```

同时将所有 `detailItem.metrics.*` 引用改为 `detailItem.model_metrics.*`。

**新增分析入口** — 操作列增加"分析"按钮：

```vue
<v-btn size="small" variant="text" color="secondary" prepend-icon="mdi-chart-box-outline" @click="openAnalysisDialog(item)">分析</v-btn>

<AnalysisDetailDialog
  v-model:dialog="analysisDialog"
  :title="analysisTitle"
  :result="analysisResult"
/>
```

```typescript
const analysisDialog = ref(false)
const analysisResult = ref<AnalysisResult | null>(null)
const analysisTitle = ref('')

const openAnalysisDialog = async (item: Training) => {
  const res = await trainingRecordApi.get(item.id)
  if (res.data.normalized_data_analysis) {
    analysisResult.value = res.data.normalized_data_analysis
    analysisTitle.value = `${item.name} - 标准化数据分析`
    analysisDialog.value = true
  }
}
```

### 8. 前端 — 类型定义更新

**文件**: `frontend/src/api/trainingRecord.ts`

```typescript
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

## 文件修改清单

| 文件 | 修改方式 | 说明 |
|------|---------|------|
| `backend/src/trade_alpha/data/analysis_service.py` | 重构 | 提取 `compute_field_analysis` 纯函数，`run_data_analysis` 调用它 |
| `backend/src/trade_alpha/dao/training.py` | 修改 | `metrics` → `model_metrics`，新增 `normalized_data_analysis` |
| `backend/src/trade_alpha/predict/training_service.py` | 修改 | `metrics` → `model_metrics`，训练后复用 `compute_field_analysis` |
| `backend/src/trade_alpha/api/routers/trainings.py` | 修改 | `metrics` → `model_metrics`，列表/详情响应拆分 |
| `frontend/src/components/AnalysisDetailDialog.vue` | **新建** | 从 DataAnalysisRecordsView 提取的公共弹窗组件 |
| `frontend/src/views/DataAnalysisRecordsView.vue` | 修改 | 移除内联详情弹窗，改用 AnalysisDetailDialog |
| `frontend/src/views/TrainingRecordsView.vue` | 修改 | 新增分析按钮和分析弹窗，使用 AnalysisDetailDialog |
| `frontend/src/api/trainingRecord.ts` | 修改 | 类型定义拆分，新增详情API |

## 风险与注意事项

1. **向后兼容**：旧记录的 `metrics` 字段名变更，需迁移。旧记录无 `normalized_data_analysis`，前端需空值判断
2. **组件提取**：提取 `AnalysisDetailDialog` 时要确保 echart 实例的生命周期正确管理（onUnmounted dispose）
