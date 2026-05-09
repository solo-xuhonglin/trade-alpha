<template>
  <v-card class="ma-2" variant="outlined" rounded="xl">
    <v-card-title class="d-flex align-center">
      <span class="text-h5 font-weight-bold">策略管理</span>
      <v-spacer />
      <v-btn color="primary" @click="openDialog()" prepend-icon="mdi-plus" density="comfortable">新建策略</v-btn>
    </v-card-title>
    <v-divider />
    <v-data-table :headers="headers" :items="strategies" :loading="loading" density="comfortable" hover>
      <template v-slot:item.config="{ item }">
        <v-chip size="small" variant="outlined">{{ JSON.stringify(item.config) }}</v-chip>
      </template>
      <template v-slot:item.actions="{ item }">
        <v-btn size="small" variant="flat" @click="openDialog(item)" class="mr-2">编辑</v-btn>
        <v-btn size="small" color="error" variant="flat" @click="deleteStrategy(item)">删除</v-btn>
      </template>
    </v-data-table>
  </v-card>

  <v-dialog v-model="dialog" max-width="90vw" max-height="90vh" scrollable>
    <v-card rounded="xl">
      <v-card-title class="text-h6 font-weight-bold">{{ editingId ? '编辑策略' : '新建策略' }}</v-card-title>
      <v-divider />
      <v-card-text class="pt-4">
        <v-row dense>
          <v-col cols="12" sm="6">
            <v-text-field v-model="form.name" label="策略名称" variant="outlined" density="comfortable" hide-details />
          </v-col>
          <v-col cols="12" sm="6">
            <v-select v-model="form.type" :items="strategyTypes" label="策略类型" variant="outlined" density="comfortable" hide-details />
          </v-col>
        </v-row>
        <v-row v-if="form.type === 'price'" dense>
          <v-col cols="12" sm="6">
            <v-text-field v-model.number="form.config.buy_threshold" label="买入阈值" type="number" step="0.01" variant="outlined" density="comfortable" hide-details />
          </v-col>
          <v-col cols="12" sm="6">
            <v-text-field v-model.number="form.config.sell_threshold" label="卖出阈值" type="number" step="0.01" variant="outlined" density="comfortable" hide-details />
          </v-col>
        </v-row>
        <v-row v-if="form.type === 'ma'" dense>
          <v-col cols="12" sm="6">
            <v-text-field v-model.number="form.config.ma_period" label="MA周期" type="number" variant="outlined" density="comfortable" hide-details />
          </v-col>
          <v-col cols="12" sm="6">
            <v-text-field v-model.number="form.config.threshold" label="阈值" type="number" step="0.01" variant="outlined" density="comfortable" hide-details />
          </v-col>
        </v-row>
        <v-row v-if="form.type === 'macd'" dense>
          <v-col cols="12">
            <v-text-field v-model.number="form.config.threshold" label="阈值" type="number" step="0.1" variant="outlined" density="comfortable" hide-details />
          </v-col>
        </v-row>
      </v-card-text>
      <v-divider />
      <v-card-actions>
        <v-spacer />
        <v-btn @click="dialog = false" variant="outlined" density="comfortable">取消</v-btn>
        <v-btn color="primary" @click="saveStrategy" variant="flat" density="comfortable">保存</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { strategyApi, type Strategy } from '@/api/strategy'

const loading = ref(false)
const dialog = ref(false)
const strategies = ref<Strategy[]>([])
const editingId = ref<string | null>(null)
const strategyTypes = ['price', 'ma', 'macd']

const form = ref({
  name: '',
  type: 'price',
  config: {} as Record<string, any>,
})

const headers = [
  { title: '名称', key: 'name' },
  { title: '类型', key: 'type' },
  { title: '配置', key: 'config' },
  { title: '操作', key: 'actions', sortable: false, align: 'center' as const },
]

const loadStrategies = async () => {
  loading.value = true
  try {
    const res = await strategyApi.list()
    strategies.value = res.data
  } finally {
    loading.value = false
  }
}

const openDialog = (item?: Strategy) => {
  if (item) {
    editingId.value = item.id
    form.value = { name: item.name, type: item.type, config: { ...item.config } }
  } else {
    editingId.value = null
    form.value = { name: '', type: 'price', config: {} }
  }
  dialog.value = true
}

const saveStrategy = async () => {
  if (editingId.value) {
    await strategyApi.update(editingId.value, form.value)
  } else {
    await strategyApi.create(form.value)
  }
  dialog.value = false
  await loadStrategies()
}

const deleteStrategy = async (item: Strategy) => {
  await strategyApi.delete(item.id)
  await loadStrategies()
}

onMounted(() => {
  loadStrategies()
})
</script>
