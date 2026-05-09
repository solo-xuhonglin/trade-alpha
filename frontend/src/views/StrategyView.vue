<template>
  <v-data-table
    :headers="headers"
    :items="strategies"
    :loading="loading"
    class="border rounded"
  >
    <template v-slot:top>
      <v-toolbar flat>
        <v-toolbar-title>策略管理</v-toolbar-title>
        <v-spacer />
        <v-btn color="primary" @click="openDialog()">新建策略</v-btn>
      </v-toolbar>
    </template>
    <template v-slot:item.config="{ item }">
      <code>{{ JSON.stringify(item.config) }}</code>
    </template>
    <template v-slot:item.actions="{ item }">
      <v-icon class="me-2" @click="openDialog(item)">mdi-pencil</v-icon>
      <v-icon color="error" @click="confirmDelete(item)">mdi-delete</v-icon>
    </template>
  </v-data-table>

  <v-dialog v-model="dialog" max-width="500px">
    <v-card>
      <v-card-title class="text-h5">{{ editingId ? '编辑策略' : '新建策略' }}</v-card-title>
      <v-card-text>
        <v-container>
          <v-row>
            <v-col cols="12">
              <v-text-field v-model="form.name" label="策略名称" />
            </v-col>
            <v-col cols="12">
              <v-select v-model="form.type" :items="strategyTypes" label="策略类型" />
            </v-col>
            <template v-if="form.type === 'price'">
              <v-col cols="12" sm="6">
                <v-text-field
                  v-model.number="form.config.buy_threshold"
                  label="买入阈值"
                  type="number"
                  step="0.01"
                  hint="预测涨幅超过此值时买入，默认0.01(1%)"
                  persistent-hint
                />
              </v-col>
              <v-col cols="12" sm="6">
                <v-text-field
                  v-model.number="form.config.sell_threshold"
                  label="卖出阈值"
                  type="number"
                  step="0.01"
                  hint="预测跌幅超过此值时卖出，默认0.01(1%)"
                  persistent-hint
                />
              </v-col>
            </template>
            <template v-if="form.type === 'ma'">
              <v-col cols="12" sm="6">
                <v-text-field
                  v-model.number="form.config.ma_period"
                  label="MA周期"
                  type="number"
                  hint="移动平均线计算周期(天)，默认20"
                  persistent-hint
                />
              </v-col>
              <v-col cols="12" sm="6">
                <v-text-field
                  v-model.number="form.config.threshold"
                  label="阈值"
                  type="number"
                  step="0.01"
                  hint="价格与MA偏离阈值，默认0.01(1%)"
                  persistent-hint
                />
              </v-col>
            </template>
            <template v-if="form.type === 'macd'">
              <v-col cols="12">
                <v-text-field
                  v-model.number="form.config.threshold"
                  label="阈值"
                  type="number"
                  step="0.1"
                  hint="MACD与信号线差值阈值，默认0.5"
                  persistent-hint
                />
              </v-col>
            </template>
          </v-row>
        </v-container>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="dialog = false">取消</v-btn>
        <v-btn color="primary" variant="text" @click="saveStrategy">保存</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="deleteDialog" max-width="400px">
    <v-card>
      <v-card-title class="text-h5">确认删除</v-card-title>
      <v-card-text>确定要删除策略「{{ deletingItem?.name }}」吗？</v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="deleteDialog = false">取消</v-btn>
        <v-btn color="error" variant="text" @click="deleteStrategy">删除</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { strategyApi, type Strategy } from '@/api/strategy'

const loading = ref(false)
const dialog = ref(false)
const deleteDialog = ref(false)
const strategies = ref<Strategy[]>([])
const editingId = ref<string | null>(null)
const deletingItem = ref<Strategy | null>(null)
const strategyTypes = ['price', 'ma', 'macd']

const defaultConfigs: Record<string, Record<string, any>> = {
  price: { buy_threshold: 0.01, sell_threshold: 0.01 },
  ma: { ma_period: 20, threshold: 0.01 },
  macd: { threshold: 0.5 },
}

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
    form.value = {
      name: 'default_strategy',
      type: 'price',
      config: { ...defaultConfigs['price'] },
    }
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

const confirmDelete = (item: Strategy) => {
  deletingItem.value = item
  deleteDialog.value = true
}

const deleteStrategy = async () => {
  if (!deletingItem.value) return
  await strategyApi.delete(deletingItem.value.id)
  deleteDialog.value = false
  deletingItem.value = null
  await loadStrategies()
}

onMounted(() => {
  loadStrategies()
})
</script>
