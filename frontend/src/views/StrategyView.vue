<template>
  <v-container>
    <v-card>
      <v-card-title class="d-flex align-center">
        策略管理
        <v-spacer />
        <v-btn color="primary" @click="openDialog()">新建策略</v-btn>
      </v-card-title>
      <v-data-table :headers="headers" :items="strategies" :loading="loading">
        <template v-slot:item.config="{ item }">
          <code>{{ JSON.stringify(item.config) }}</code>
        </template>
        <template v-slot:item.actions="{ item }">
          <v-btn size="small" variant="text" @click="openDialog(item)">编辑</v-btn>
          <v-btn size="small" color="error" variant="text" @click="deleteStrategy(item)">删除</v-btn>
        </template>
      </v-data-table>
    </v-card>

    <v-dialog v-model="dialog" max-width="500">
      <v-card>
        <v-card-title>{{ editingId ? '编辑策略' : '新建策略' }}</v-card-title>
        <v-card-text>
          <v-text-field v-model="form.name" label="策略名称" />
          <v-select v-model="form.type" :items="strategyTypes" label="策略类型" />
          <template v-if="form.type === 'price'">
            <v-text-field v-model.number="form.config.buy_threshold" label="买入阈值" type="number" step="0.01" />
            <v-text-field v-model.number="form.config.sell_threshold" label="卖出阈值" type="number" step="0.01" />
          </template>
          <template v-if="form.type === 'ma'">
            <v-text-field v-model.number="form.config.ma_period" label="MA周期" type="number" />
            <v-text-field v-model.number="form.config.threshold" label="阈值" type="number" step="0.01" />
          </template>
          <template v-if="form.type === 'macd'">
            <v-text-field v-model.number="form.config.threshold" label="阈值" type="number" step="0.1" />
          </template>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="dialog = false">取消</v-btn>
          <v-btn color="primary" @click="saveStrategy">保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
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
  { title: '操作', key: 'actions', sortable: false },
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
