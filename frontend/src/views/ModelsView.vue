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
      <template v-slot:item.params="{ item }">
        <code>{{ JSON.stringify(item.params) }}</code>
      </template>
      <template v-slot:item.actions="{ item }">
        <div class="d-flex ga-2 justify-end">
          <v-icon color="medium-emphasis" icon="mdi-pencil" size="small" @click="openDialog(item)"></v-icon>
          <v-icon color="error" icon="mdi-delete" size="small" @click="confirmDelete(item)"></v-icon>
        </div>
      </template>
    </v-data-table>
  </v-card>

  <v-dialog v-model="dialog" max-width="600px">
    <v-card :title="editingId ? '编辑配置' : '新建配置'">
      <v-card-text>
        <v-text-field v-model="form.name" label="配置名称"></v-text-field>
        <v-select v-model="form.model_type" :items="['linear', 'xgboost', 'lstm']" label="模型类型"></v-select>
        <v-select v-model="form.targets" :items="['open', 'close', 'high', 'low']" label="预测目标" multiple chips></v-select>
        <template v-if="form.model_type === 'linear'">
          <v-switch v-model="form.params.fit_intercept" label="fit_intercept" color="primary"></v-switch>
        </template>
        <template v-if="form.model_type === 'xgboost'">
          <v-text-field v-model.number="form.params.n_estimators" label="n_estimators" type="number"></v-text-field>
          <v-text-field v-model.number="form.params.max_depth" label="max_depth" type="number"></v-text-field>
          <v-text-field v-model.number="form.params.learning_rate" label="learning_rate" type="number" step="0.01"></v-text-field>
        </template>
        <template v-if="form.model_type === 'lstm'">
          <v-text-field v-model.number="form.params.epochs" label="epochs" type="number"></v-text-field>
          <v-text-field v-model.number="form.params.batch_size" label="batch_size" type="number"></v-text-field>
          <v-text-field v-model.number="form.params.units" label="units" type="number"></v-text-field>
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

const form = ref({
  name: '',
  model_type: 'linear' as 'linear' | 'xgboost' | 'lstm',
  targets: ['open', 'close'] as string[],
  params: {} as Record<string, any>,
})

const defaultParams: Record<string, Record<string, any>> = {
  linear: { fit_intercept: true },
  xgboost: { n_estimators: 100, max_depth: 5, learning_rate: 0.1 },
  lstm: { epochs: 50, batch_size: 32, units: 64 },
}

const headers = [
  { title: '名称', key: 'name' },
  { title: '模型类型', key: 'model_type' },
  { title: '预测目标', key: 'targets' },
  { title: '参数', key: 'params' },
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
    form.value = { ...item }
  } else {
    editingId.value = null
    form.value = {
      name: 'new_config',
      model_type: 'linear',
      targets: ['open', 'close'],
      params: { ...defaultParams['linear'] },
    }
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
