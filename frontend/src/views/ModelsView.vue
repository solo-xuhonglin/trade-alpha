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
    <v-card :title="editingId ? '编辑配置' : '新建配置'">
      <template v-slot:text>
        <v-row>
          <v-col cols="12" sm="6">
            <v-text-field v-model="form.name" label="配置名称"></v-text-field>
          </v-col>
          <v-col cols="12" sm="6">
            <v-select v-model="form.model_type" :items="['linear', 'xgboost', 'lstm']" label="模型类型"></v-select>
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
      </template>
      <v-divider></v-divider>
      <v-card-actions class="bg-surface-light">
        <v-btn text="取消" variant="plain" @click="dialog = false"></v-btn>
        <v-spacer></v-spacer>
        <v-btn text="保存" @click="saveConfig"></v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="deleteDialog" max-width="400px">
    <v-card subtitle="此操作不可撤销" title="确认删除">
      <template v-slot:text>
        确定要删除配置「{{ deletingItem?.name }}」吗？
      </template>
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
import { ref, onMounted } from 'vue'
import { modelApi, type ModelConfig } from '@/api/model'

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
  'close_pct_rank_5', 'close_pct_rank_10', 'close_pct_rank_20', 'close_pct_rank_60',
  'vol_ratio_5', 'vol_ratio_10', 'vol_ratio_20', 'vol_ratio_60',
  'kdj_k', 'kdj_d', 'kdj_j',
  'boll_upper', 'boll_middle', 'boll_lower',
  'rsi_6', 'rsi_12', 'atr_14', 'obv',
]

const defaultForm = {
  name: '',
  model_type: 'xgboost',
  feature_fields: [...indicatorFields],
  standardize_fields: [...indicatorFields],
  winsorize_fields: [] as string[],
  classification_horizons: [3, 5],
  classification_threshold: 0.02,
  xgb_n_estimators: 100,
  xgb_max_depth: 6,
  xgb_learning_rate: 0.1,
  xgb_min_child_weight: 1,
  xgb_subsample: 1.0,
  xgb_colsample_bytree: 1.0,
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

const loadModels = async () => {
  loading.value = true
  try {
    const res = await modelApi.list()
    models.value = res.data
  } finally {
    loading.value = false
  }
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
    }
  } else {
    editingId.value = null
    form.value = { ...defaultForm, feature_fields: [...defaultForm.feature_fields], standardize_fields: [...defaultForm.standardize_fields] }
  }
  dialog.value = true
}

const saveConfig = async () => {
  if (editingId.value) {
    await modelApi.update(editingId.value, form.value)
  } else {
    await modelApi.create(form.value)
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
  await modelApi.delete(deletingItem.value.id)
  deleteDialog.value = false
  deletingItem.value = null
  await loadModels()
}

onMounted(() => {
  loadModels()
})
</script>
