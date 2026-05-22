<template>
  <v-card border rounded>
    <v-data-table :headers="headers" :items="models" :loading="loading">
      <template v-slot:top>
        <v-toolbar flat>
          <v-toolbar-title>
            <v-icon color="medium-emphasis" icon="mdi-brain" size="x-small" start></v-icon>
            模型配置
          </v-toolbar-title>
          <v-btn prepend-icon="mdi-plus" rounded="lg" text="新建配置" border @click="openDialog()"></v-btn>
        </v-toolbar>
      </template>
      <template v-slot:item.feature_fields="{ item }">
        <v-chip-group>
          <v-chip v-for="f in item.feature_fields.slice(0, 3)" :key="f" size="x-small" variant="outlined">
            {{ f }}
          </v-chip>
          <v-chip v-if="item.feature_fields.length > 3" size="x-small" variant="tonal">
            +{{ item.feature_fields.length - 3 }}
          </v-chip>
        </v-chip-group>
      </template>
      <template v-slot:item.classification_horizons="{ item }">
        <v-chip-group>
          <v-chip v-for="h in item.classification_horizons" :key="h" size="x-small" variant="outlined">
            {{ h }}日
          </v-chip>
        </v-chip-group>
      </template>
      <template v-slot:item.actions="{ item }">
        <div class="d-flex ga-1 justify-end">
          <v-btn size="small" variant="text" prepend-icon="mdi-pencil" @click="openDialog(item)">编辑</v-btn>
          <v-btn size="small" variant="text" color="error" prepend-icon="mdi-delete" @click="confirmDelete(item)">删除</v-btn>
        </div>
      </template>
    </v-data-table>
  </v-card>

  <v-dialog v-model="dialog" max-width="800px">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center">
        {{ editingId ? '编辑配置' : '新建配置' }}
        <v-btn icon variant="text" size="small" @click="dialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>
        <v-row>
          <v-col cols="12" sm="6">
            <v-select v-model="form.model_type" :items="['xgboost', 'lstm']" label="模型类型"></v-select>
          </v-col>
          <v-col cols="12" sm="6">
            <v-text-field v-model="form.name" label="配置名称"></v-text-field>
          </v-col>
        </v-row>

        <v-divider class="my-3"></v-divider>
        <div class="text-subtitle-2 text-medium-emphasis mb-2">特征与数据处理</div>
        <v-row>
          <v-col cols="12">
            <v-autocomplete v-model="form.feature_fields" :items="indicatorFields" label="特征字段" multiple chips closable-chips dense></v-autocomplete>
          </v-col>
        </v-row>
        <v-row>
          <v-col cols="12" sm="6">
            <v-autocomplete v-model="form.standardize_fields" :items="indicatorFields" label="标准化字段" multiple chips closable-chips dense></v-autocomplete>
          </v-col>
          <v-col cols="12" sm="6">
            <v-autocomplete v-model="form.winsorize_fields" :items="indicatorFields" label="缩尾字段" multiple chips closable-chips dense></v-autocomplete>
          </v-col>
        </v-row>

        <v-divider class="my-3"></v-divider>
        <div class="text-subtitle-2 text-medium-emphasis mb-2">训练标签参数</div>
        <v-row>
          <v-col cols="12" sm="6">
            <v-combobox v-model="form.classification_horizons" :items="[1, 2, 3, 5, 10, 20]" label="预测周期" multiple chips small-chips></v-combobox>
          </v-col>
          <v-col cols="12" sm="6">
            <v-text-field v-model.number="form.classification_threshold" label="涨跌阈值" type="number" step="0.01"></v-text-field>
          </v-col>
        </v-row>

        <template v-if="form.model_type === 'xgboost'">
          <v-divider class="my-3"></v-divider>
          <div class="text-subtitle-2 text-medium-emphasis mb-2">XGBoost 超参数</div>
          <v-row>
            <v-col cols="12" sm="4">
              <v-text-field v-model.number="form.xgb_n_estimators" label="n_estimators" type="number"></v-text-field>
            </v-col>
            <v-col cols="12" sm="4">
              <v-text-field v-model.number="form.xgb_max_depth" label="max_depth" type="number"></v-text-field>
            </v-col>
            <v-col cols="12" sm="4">
              <v-text-field v-model.number="form.xgb_learning_rate" label="learning_rate" type="number" step="0.01"></v-text-field>
            </v-col>
            <v-col cols="12" sm="4">
              <v-text-field v-model.number="form.xgb_min_child_weight" label="min_child_weight" type="number" step="0.1"></v-text-field>
            </v-col>
            <v-col cols="12" sm="4">
              <v-text-field v-model.number="form.xgb_subsample" label="subsample" type="number" step="0.1"></v-text-field>
            </v-col>
            <v-col cols="12" sm="4">
              <v-text-field v-model.number="form.xgb_colsample_bytree" label="colsample_bytree" type="number" step="0.1"></v-text-field>
            </v-col>
          </v-row>
        </template>

        <template v-if="form.model_type === 'lstm'">
          <v-divider class="my-3"></v-divider>
          <div class="text-subtitle-2 text-medium-emphasis mb-2">LSTM 超参数</div>
          <v-row>
            <v-col cols="12" sm="4">
              <v-text-field v-model.number="form.lstm_hidden_size" label="hidden_size" type="number"></v-text-field>
            </v-col>
            <v-col cols="12" sm="4">
              <v-text-field v-model.number="form.lstm_num_layers" label="num_layers" type="number"></v-text-field>
            </v-col>
            <v-col cols="12" sm="4">
              <v-text-field v-model.number="form.lstm_dropout" label="dropout" type="number" step="0.1"></v-text-field>
            </v-col>
            <v-col cols="12" sm="4">
              <v-text-field v-model.number="form.lstm_epochs" label="epochs" type="number"></v-text-field>
            </v-col>
            <v-col cols="12" sm="4">
              <v-text-field v-model.number="form.lstm_batch_size" label="batch_size" type="number"></v-text-field>
            </v-col>
            <v-col cols="12" sm="4">
              <v-text-field v-model.number="form.lstm_learning_rate" label="learning_rate" type="number" step="0.001"></v-text-field>
            </v-col>
            <v-col cols="12" sm="4">
              <v-text-field v-model.number="form.lstm_sequence_length" label="sequence_length（序列长度和标准化窗口）" type="number"></v-text-field>
            </v-col>
          </v-row>
        </template>
      </v-card-text>
      <v-divider></v-divider>
      <v-card-actions class="bg-surface-light">
        <v-btn text="取消" variant="plain" @click="dialog = false"></v-btn>
        <v-spacer></v-spacer>
        <v-btn text="保存" @click="saveConfig"></v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="deleteDialog" max-width="400px">
    <v-card>
      <v-card-title class="text-h6 d-flex justify-space-between align-center">
        确认删除
        <v-btn icon variant="text" size="small" @click="deleteDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>此操作不可撤销，确定要删除配置「{{ deletingItem?.name }}」吗？</v-card-text>
      <v-divider></v-divider>
      <v-card-actions class="bg-surface-light">
        <v-btn text="取消" variant="plain" @click="deleteDialog = false"></v-btn>
        <v-spacer></v-spacer>
        <v-btn text="删除" color="error" @click="deleteConfig"></v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { modelConfigApi, type ModelConfig } from '@/api/modelConfig'

const loading = ref(false)
const dialog = ref(false)
const deleteDialog = ref(false)
const models = ref<ModelConfig[]>([])
const editingId = ref<string | null>(null)
const deletingItem = ref<ModelConfig | null>(null)

const indicatorFields = [
  'ma_5', 'ma_10', 'ma_20', 'ma_60',
  'macd', 'macd_signal', 'macd_hist',
  'pct_chg',
  'bias_5', 'bias_10', 'bias_20', 'bias_60',
  'close_position_5', 'close_position_10', 'close_position_20', 'close_position_60',
  'vol_ratio_5', 'vol_ratio_10', 'vol_ratio_20', 'vol_ratio_60',
  'kdj_k', 'kdj_d', 'kdj_j',
  'boll_upper', 'boll_middle', 'boll_lower', 'boll_position',
  'rsi_6', 'rsi_12',
  'trend_arrangement_5', 'trend_arrangement_10', 'trend_arrangement_20',
  'trend_slope_5', 'trend_slope_10', 'trend_slope_20',
  'trend_volume_5', 'trend_volume_10', 'trend_volume_20',
  'trend_stability_5', 'trend_stability_10', 'trend_stability_20',
  'obv',
]

// 与价格绝对值无关的字段（特征字段默认只选这些）
const priceIndependentFields = [
  'pct_chg',
  'bias_5', 'bias_10', 'bias_20', 'bias_60',
  'close_position_5', 'close_position_10', 'close_position_20', 'close_position_60',
  'vol_ratio_5', 'vol_ratio_10', 'vol_ratio_20', 'vol_ratio_60',
  'kdj_k', 'kdj_d', 'kdj_j',
  'boll_position',
  'rsi_6', 'rsi_12',
  'trend_arrangement_5', 'trend_arrangement_10', 'trend_arrangement_20',
  'trend_slope_5', 'trend_slope_10', 'trend_slope_20',
  'trend_volume_5', 'trend_volume_10', 'trend_volume_20',
  'trend_stability_5', 'trend_stability_10', 'trend_stability_20',
  'obv',
]

// LSTM 推荐特征字段（时序模型更适合精简核心特征）
const lstmRecommendedFeatureFields = [
  'macd', 'macd_signal', 'macd_hist',
  'rsi_6', 'rsi_12',
  'bias_5', 'bias_10', 'bias_20',
  'boll_position',
  'kdj_k', 'kdj_d', 'kdj_j',
  'vol_ratio_5', 'vol_ratio_10',
  'trend_slope_5', 'trend_slope_10',
  'trend_volume_5', 'trend_volume_10',
]

const defaultForm = {
  name: 'xgboost_config',
  model_type: 'xgboost',
  feature_fields: [...priceIndependentFields],
  standardize_fields: [...indicatorFields],
  winsorize_fields: [...indicatorFields],
  classification_horizons: [3, 5],
  classification_threshold: 0.01,
  xgb_n_estimators: 100,
  xgb_max_depth: 6,
  xgb_learning_rate: 0.1,
  xgb_min_child_weight: 1,
  xgb_subsample: 1.0,
  xgb_colsample_bytree: 1.0,
  lstm_hidden_size: 64,
  lstm_num_layers: 2,
  lstm_dropout: 0.1,
  lstm_epochs: 25,
  lstm_batch_size: 256,
  lstm_learning_rate: 0.001,
  lstm_sequence_length: 60,
}

const form = ref({ ...defaultForm })

const headers = [
  { title: '名称', key: 'name' },
  { title: '模型类型', key: 'model_type' },
  { title: '特征字段', key: 'feature_fields' },
  { title: '预测周期', key: 'classification_horizons' },
  { title: '涨跌阈值', key: 'classification_threshold' },
  { title: '操作', key: 'actions', sortable: false, align: 'end' as const },
]

const generateDefaultName = (modelType: string) => {
  const timestamp = new Date().toISOString().slice(0, 10)
  return `${modelType}_config_${timestamp}`
}

// XGBoost 推荐参数
const xgbRecommendedParams = {
  feature_fields: [...priceIndependentFields],
  standardize_fields: [...indicatorFields],
  winsorize_fields: [...indicatorFields],
  xgb_n_estimators: 100,
  xgb_max_depth: 6,
  xgb_learning_rate: 0.1,
  xgb_min_child_weight: 1,
  xgb_subsample: 1.0,
  xgb_colsample_bytree: 1.0,
}

// LSTM 推荐参数（使用精简的时序特征）
const lstmRecommendedParams = {
  feature_fields: [...lstmRecommendedFeatureFields],
  standardize_fields: [...indicatorFields],
  winsorize_fields: [...indicatorFields],
  lstm_hidden_size: 64,
  lstm_num_layers: 2,
  lstm_dropout: 0.1,
  lstm_epochs: 25,
  lstm_batch_size: 256,
  lstm_learning_rate: 0.001,
  lstm_sequence_length: 60,
}

// 监听模型类型变化，新建时自动更新推荐参数
watch(() => form.value.model_type, (newType) => {
  if (!editingId.value) { // 只有新建时才自动更新
    form.value.name = generateDefaultName(newType)
    if (newType === 'xgboost') {
      Object.assign(form.value, xgbRecommendedParams)
    } else if (newType === 'lstm') {
      Object.assign(form.value, lstmRecommendedParams)
    }
  }
})

const loadModels = async () => {
  loading.value = true
  const res = await modelConfigApi.list()
  models.value = res.data
  loading.value = false
}

const openDialog = (item?: ModelConfig) => {
  if (item) {
    editingId.value = item.id
    form.value = {
      name: item.name,
      model_type: item.model_type,
      feature_fields: [...item.feature_fields],
      standardize_fields: [...item.standardize_fields],
      winsorize_fields: [...item.winsorize_fields],
      classification_horizons: [...item.classification_horizons],
      classification_threshold: item.classification_threshold,
      xgb_n_estimators: item.xgb_n_estimators,
      xgb_max_depth: item.xgb_max_depth,
      xgb_learning_rate: item.xgb_learning_rate,
      xgb_min_child_weight: item.xgb_min_child_weight,
      xgb_subsample: item.xgb_subsample,
      xgb_colsample_bytree: item.xgb_colsample_bytree,
      lstm_hidden_size: (item as any).lstm_hidden_size || 64,
      lstm_num_layers: (item as any).lstm_num_layers || 2,
      lstm_dropout: (item as any).lstm_dropout || 0.1,
      lstm_epochs: (item as any).lstm_epochs || 25,
      lstm_batch_size: (item as any).lstm_batch_size || 256,
      lstm_learning_rate: (item as any).lstm_learning_rate || 0.001,
      lstm_sequence_length: (item as any).lstm_sequence_length || 60,
    }
  } else {
    editingId.value = null
    form.value = { 
      ...defaultForm, 
      name: generateDefaultName(defaultForm.model_type),
      feature_fields: [...defaultForm.feature_fields], 
      standardize_fields: [...defaultForm.standardize_fields], 
      winsorize_fields: [...defaultForm.winsorize_fields] 
    }
  }
  dialog.value = true
}

const saveConfig = async () => {
  if (editingId.value) {
    await modelConfigApi.update(editingId.value, form.value)
  } else {
    await modelConfigApi.create(form.value)
  }
  dialog.value = false
  await loadModels()
}

const confirmDelete = (item: ModelConfig) => {
  deletingItem.value = item
  deleteDialog.value = true
}

const deleteConfig = async () => {
  if (!deletingItem.value) return
  await modelConfigApi.delete(deletingItem.value.id)
  deleteDialog.value = false
  deletingItem.value = null
  await loadModels()
}

onMounted(() => {
  loadModels()
})
</script>
