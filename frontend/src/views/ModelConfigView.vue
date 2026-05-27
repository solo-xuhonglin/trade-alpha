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
      <template v-slot:item.created_at="{ item }">
        {{ formatDate(item.created_at) }}
      </template>
      <template v-slot:item.actions="{ item }">
        <div class="d-flex ga-1 justify-end">
          <v-btn size="small" variant="text" prepend-icon="mdi-pencil" @click="openDialog(item)">编辑</v-btn>
          <v-btn size="small" variant="text" color="error" prepend-icon="mdi-delete" @click="confirmDelete(item)">删除</v-btn>
        </div>
      </template>
    </v-data-table>
  </v-card>

  <v-dialog v-model="dialog" max-width="900px">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center">
        {{ editingId ? '编辑配置' : '新建配置' }}
        <v-btn icon variant="text" size="small" @click="dialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text class="overflow-y-auto" style="max-height: 70vh;">
        <v-row>
          <v-col cols="12" sm="6">
            <v-select v-model="form.model_type" :items="['xgboost', 'lstm']" label="模型类型"></v-select>
          </v-col>
          <v-col cols="12" sm="6">
            <v-text-field v-model="form.name" label="配置名称"></v-text-field>
          </v-col>
        </v-row>

        <v-tabs v-model="activeTab" color="primary">
          <v-tab value="fields">字段配置</v-tab>
          <v-tab value="params">参数配置</v-tab>
        </v-tabs>

        <v-window v-model="activeTab" class="mt-4">
          <v-window-item value="fields">
            <div>
              <v-row>
                <v-col cols="12">
                  <v-autocomplete v-model="form.feature_fields" :items="allFeatureFields" label="特征字段" multiple chips closable-chips dense></v-autocomplete>
                </v-col>
              </v-row>
              <v-row>
                <v-col cols="12" sm="6">
                  <v-autocomplete v-model="form.standardize_fields" :items="allFeatureFields" label="标准化字段" multiple chips closable-chips dense></v-autocomplete>
                </v-col>
                <v-col cols="12" sm="6">
                  <v-autocomplete v-model="form.winsorize_fields" :items="allFeatureFields" label="缩尾字段" multiple chips closable-chips dense></v-autocomplete>
                </v-col>
              </v-row>
            </div>
          </v-window-item>
          <v-window-item value="params">
            <div>
              <v-divider class="mb-4"></v-divider>
              <div class="text-subtitle-2 text-medium-emphasis mb-2">训练标签参数</div>
              <v-row>
                <v-col cols="12" sm="6">
                  <v-combobox v-model="form.classification_horizons" :items="[1, 2, 3, 5, 10, 20]" label="预测周期" multiple chips small-chips></v-combobox>
                </v-col>
                <v-col cols="12" sm="6">
                  <v-select v-model="form.label_mode" :items="[
                    { title: '涨跌幅阈值', value: 'threshold' },
                    { title: '均线趋势', value: 'trend' }
                  ]" label="标签计算模式"
                    hint="threshold: 基于未来涨跌幅阈值分类; trend: 基于均线位置斜率 + 涨跌幅阈值分类" persistent-hint></v-select>
                </v-col>
                  <v-col cols="12" sm="4">
                    <v-text-field v-model.number="form.classification_threshold_3d" label="3日涨跌阈值" type="number" step="0.005" hint="短周期，小阈值" persistent-hint></v-text-field>
                  </v-col>
                  <v-col cols="12" sm="4">
                    <v-text-field v-model.number="form.classification_threshold_5d" label="5日涨跌阈值" type="number" step="0.005" hint="中周期" persistent-hint></v-text-field>
                  </v-col>
                  <v-col cols="12" sm="4">
                    <v-text-field v-model.number="form.classification_threshold_10d" label="10日涨跌阈值" type="number" step="0.005" hint="长周期，大阈值" persistent-hint></v-text-field>
                  </v-col>
              </v-row>

              <template v-if="form.model_type === 'xgboost'">
                <v-divider class="my-4"></v-divider>
                <div class="text-subtitle-2 text-medium-emphasis mb-2">XGBoost 超参数</div>
                <v-row>
                  <v-col cols="12" sm="6">
                    <v-text-field v-model.number="form.xgb_n_estimators" label="n_estimators" type="number" hint="树的数量，值越大越准确但越慢" persistent-hint></v-text-field>
                  </v-col>
                  <v-col cols="12" sm="6">
                    <v-text-field v-model.number="form.xgb_learning_rate" label="learning_rate" type="number" step="0.01" hint="每棵树的贡献权重，与树数量配合调整" persistent-hint></v-text-field>
                  </v-col>
                  <v-col cols="12" sm="6">
                    <v-text-field v-model.number="form.xgb_max_depth" label="max_depth" type="number" hint="树的最大深度，控制模型复杂度" persistent-hint></v-text-field>
                  </v-col>
                  <v-col cols="12" sm="6">
                    <v-text-field v-model.number="form.xgb_min_child_weight" label="min_child_weight" type="number" step="0.1" hint="叶子节点最小权重和，与深度配合防止过拟合" persistent-hint></v-text-field>
                  </v-col>
                  <v-col cols="12" sm="6">
                    <v-text-field v-model.number="form.xgb_subsample" label="subsample" type="number" step="0.1" hint="训练样本采样比例" persistent-hint></v-text-field>
                  </v-col>
                  <v-col cols="12" sm="6">
                    <v-text-field v-model.number="form.xgb_colsample_bytree" label="colsample_bytree" type="number" step="0.1" hint="每棵树的特征采样比例" persistent-hint></v-text-field>
                  </v-col>
                </v-row>
              </template>

              <template v-if="form.model_type === 'lstm'">
                <v-divider class="my-4"></v-divider>
                <div class="text-subtitle-2 text-medium-emphasis mb-2">LSTM 超参数</div>
                <v-row>
                  <v-col cols="12" sm="6">
                    <v-text-field v-model.number="form.lstm_hidden_size" label="hidden_size" type="number" hint="隐藏层维度，控制模型容量" persistent-hint></v-text-field>
                  </v-col>
                  <v-col cols="12" sm="6">
                    <v-text-field v-model.number="form.lstm_num_layers" label="num_layers" type="number" hint="LSTM 层数" persistent-hint></v-text-field>
                  </v-col>
                  <v-col cols="12" sm="6">
                    <v-text-field v-model.number="form.lstm_dropout" label="dropout" type="number" step="0.1" hint="Dropout 比例，防止过拟合" persistent-hint></v-text-field>
                  </v-col>
                  <v-col cols="12" sm="6">
                    <v-text-field v-model.number="form.lstm_weight_decay" label="weight_decay" type="number" step="0.0001" hint="L2 正则化系数" persistent-hint></v-text-field>
                  </v-col>
                  <v-col cols="12" sm="6">
                    <v-text-field v-model.number="form.lstm_learning_rate" label="learning_rate" type="number" step="0.001" hint="学习率" persistent-hint></v-text-field>
                  </v-col>
                  <v-col cols="12" sm="6">
                    <v-text-field v-model.number="form.lr_scheduler_factor" label="lr_scheduler_factor" type="number" step="0.1" hint="验证 AUC 停滞时学习率衰减因子" persistent-hint></v-text-field>
                  </v-col>
                  <v-col cols="12" sm="6">
                    <v-text-field v-model.number="form.lstm_epochs" label="epochs" type="number" hint="最大训练轮数" persistent-hint></v-text-field>
                  </v-col>
                  <v-col cols="12" sm="6">
                    <v-text-field v-model.number="form.lstm_batch_size" label="batch_size" type="number" hint="每批训练样本数" persistent-hint></v-text-field>
                  </v-col>
                  <v-col cols="12" sm="6">
                    <v-text-field v-model.number="form.lstm_sequence_length" label="sequence_length" type="number" hint="输入序列长度（天数）" persistent-hint></v-text-field>
                  </v-col>
                  <v-col cols="12" sm="6">
                    <v-text-field v-model.number="form.lstm_normalization_window" label="normalization_window" type="number" hint="标准化统计窗口（天数）" persistent-hint></v-text-field>
                  </v-col>
                  <v-col cols="12" sm="6">
                    <v-text-field v-model.number="form.lr_scheduler_patience" label="lr_scheduler_patience" type="number" hint="学习率调度器等待轮数" persistent-hint></v-text-field>
                  </v-col>
                  <v-col cols="12" sm="6">
                    <v-text-field v-model.number="form.early_stopping_patience" label="early_stopping_patience" type="number" hint="验证 AUC 不提升时停止的轮数" persistent-hint></v-text-field>
                  </v-col>
                  <v-col cols="12" sm="6">
                    <v-text-field v-model.number="form.val_size" label="val_size" type="number" step="0.05" hint="验证集比例（按日期划分）" persistent-hint></v-text-field>
                  </v-col>
                </v-row>
              </template>
            </div>
          </v-window-item>
        </v-window>
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
import { formatDate } from '@/utils/date'
import {
  DAILY_BASIC_FIELDS,
  INDICATOR_FIELDS,
  ALL_FEATURE_FIELDS,
  PRICE_INDEPENDENT_FIELDS,
  LSTM_RECOMMENDED_FIELDS,
  LSTM_AFFECTED_BY_PRICE_FIELDS,
} from '@/api/featureFields'

const loading = ref(false)
const dialog = ref(false)
const activeTab = ref('fields')
const deleteDialog = ref(false)
const models = ref<ModelConfig[]>([])
const editingId = ref<string | null>(null)
const deletingItem = ref<ModelConfig | null>(null)
const error = ref('')

const allFeatureFields = ALL_FEATURE_FIELDS

const priceIndependentFields = PRICE_INDEPENDENT_FIELDS

const lstmRecommendedFeatureFields = LSTM_RECOMMENDED_FIELDS

const lstmAffectedByPriceFields = LSTM_AFFECTED_BY_PRICE_FIELDS

const defaultForm = {
  name: 'xgboost_config',
  model_type: 'xgboost',
  feature_fields: [...priceIndependentFields],
  standardize_fields: [...INDICATOR_FIELDS],
  winsorize_fields: [...INDICATOR_FIELDS],
  classification_horizons: [3, 5, 10],
  label_mode: 'threshold',
  classification_threshold_3d: 0.01,
  classification_threshold_5d: 0.015,
  classification_threshold_10d: 0.02,
  xgb_n_estimators: 100,
  xgb_max_depth: 6,
  xgb_learning_rate: 0.1,
  xgb_min_child_weight: 1,
  xgb_subsample: 1.0,
  xgb_colsample_bytree: 1.0,
  lstm_hidden_size: 64,
  lstm_num_layers: 2,
  lstm_dropout: 0.2,
  lstm_epochs: 50,
  lstm_batch_size: 256,
  lstm_learning_rate: 0.001,
  lstm_sequence_length: 60,
  lstm_normalization_window: 300,
  lstm_weight_decay: 0.0001,
  lr_scheduler_factor: 0.5,
  lr_scheduler_patience: 3,
  val_size: 0.2,
  early_stopping_patience: 10,
}

const form = ref({ ...defaultForm })

const headers = [
  { title: '名称', key: 'name' },
  { title: '模型类型', key: 'model_type' },
  { title: '特征字段', key: 'feature_fields' },
  { title: '预测周期', key: 'classification_horizons' },
  { title: '涨跌阈值', key: 'classification_threshold' },
  { title: '创建时间', key: 'created_at' },
  { title: '操作', key: 'actions', sortable: false, align: 'end' as const },
]

const generateDefaultName = (modelType: string) => {
  const timestamp = new Date().toISOString().slice(0, 10)
  return `${modelType}_config_${timestamp}`
}

const xgbRecommendedParams = {
  feature_fields: [...priceIndependentFields],
  standardize_fields: [...INDICATOR_FIELDS],
  winsorize_fields: [...INDICATOR_FIELDS],
  label_mode: 'threshold',
  classification_threshold_3d: 0.01,
  classification_threshold_5d: 0.015,
  classification_threshold_10d: 0.02,
  xgb_n_estimators: 100,
  xgb_max_depth: 6,
  xgb_learning_rate: 0.1,
  xgb_min_child_weight: 1,
  xgb_subsample: 1.0,
  xgb_colsample_bytree: 1.0,
}

const lstmRecommendedParams = {
  feature_fields: [...lstmRecommendedFeatureFields],
  standardize_fields: [...lstmAffectedByPriceFields],
  winsorize_fields: [...lstmAffectedByPriceFields],
  label_mode: 'threshold',
  classification_threshold_3d: 0.01,
  classification_threshold_5d: 0.015,
  classification_threshold_10d: 0.02,
  lstm_hidden_size: 64,
  lstm_num_layers: 2,
  lstm_dropout: 0.2,
  lstm_epochs: 50,
  lstm_batch_size: 256,
  lstm_learning_rate: 0.001,
  lstm_sequence_length: 60,
  lstm_normalization_window: 300,
  lstm_weight_decay: 0.0001,
  lr_scheduler_factor: 0.5,
  lr_scheduler_patience: 3,
  val_size: 0.2,
  early_stopping_patience: 10,
}

watch(() => form.value.model_type, (newType) => {
  if (!editingId.value) {
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
  error.value = ''
  try {
    const res = await modelConfigApi.list()
    models.value = res.data
  } catch (e) {
    console.error('Failed to load models:', e)
    error.value = '加载失败'
  } finally {
    loading.value = false
  }
}

const openDialog = (item?: ModelConfig) => {
  activeTab.value = 'fields'
  if (item) {
    editingId.value = item.id
    form.value = {
      name: item.name,
      model_type: item.model_type,
      feature_fields: [...item.feature_fields],
      standardize_fields: [...item.standardize_fields],
      winsorize_fields: [...item.winsorize_fields],
      classification_horizons: [...item.classification_horizons],
      label_mode: (item as any).label_mode || 'threshold',
      classification_threshold_3d: (item as any).classification_threshold_3d ?? 0.01,
      classification_threshold_5d: (item as any).classification_threshold_5d ?? 0.015,
      classification_threshold_10d: (item as any).classification_threshold_10d ?? 0.02,
      xgb_n_estimators: item.xgb_n_estimators,
      xgb_max_depth: item.xgb_max_depth,
      xgb_learning_rate: item.xgb_learning_rate,
      xgb_min_child_weight: item.xgb_min_child_weight,
      xgb_subsample: item.xgb_subsample,
      xgb_colsample_bytree: item.xgb_colsample_bytree,
      lstm_hidden_size: (item as any).lstm_hidden_size || 64,
      lstm_num_layers: (item as any).lstm_num_layers || 2,
      lstm_dropout: (item as any).lstm_dropout || 0.1,
      lstm_epochs: (item as any).lstm_epochs || 50,
      lstm_batch_size: (item as any).lstm_batch_size || 256,
      lstm_learning_rate: (item as any).lstm_learning_rate || 0.001,
      lstm_sequence_length: (item as any).lstm_sequence_length || 60,
      lstm_normalization_window: (item as any).lstm_normalization_window || 300,
      lstm_weight_decay: (item as any).lstm_weight_decay ?? 0.0001,
      lr_scheduler_factor: (item as any).lr_scheduler_factor ?? 0.5,
      lr_scheduler_patience: (item as any).lr_scheduler_patience ?? 3,
      val_size: (item as any).val_size ?? 0.2,
      early_stopping_patience: (item as any).early_stopping_patience || 10,
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
  loading.value = true
  error.value = ''
  try {
    if (editingId.value) {
      await modelConfigApi.update(editingId.value, form.value)
    } else {
      await modelConfigApi.create(form.value)
    }
    dialog.value = false
    await loadModels()
  } catch (e) {
    console.error('Failed to save config:', e)
    error.value = '保存失败'
  } finally {
    loading.value = false
  }
}

const confirmDelete = (item: ModelConfig) => {
  deletingItem.value = item
  deleteDialog.value = true
}

const deleteConfig = async () => {
  if (!deletingItem.value) return
  loading.value = true
  error.value = ''
  try {
    await modelConfigApi.delete(deletingItem.value.id)
    deleteDialog.value = false
    deletingItem.value = null
    await loadModels()
  } catch (e) {
    console.error('Failed to delete config:', e)
    error.value = '删除失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadModels()
})
</script>
