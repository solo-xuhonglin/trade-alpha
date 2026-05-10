<template>
  <v-card border rounded>
    <v-data-table
      :headers="headers"
      :items="strategies"
      :loading="loading"
    >
      <template v-slot:top>
        <v-toolbar flat>
          <v-toolbar-title>
            <v-icon color="medium-emphasis" icon="mdi-strategy" size="x-small" start></v-icon>
            策略管理
          </v-toolbar-title>
          <v-btn
            prepend-icon="mdi-plus"
            rounded="lg"
            text="新建策略"
            border
            @click="openDialog()"
          ></v-btn>
        </v-toolbar>
      </template>

      <template v-slot:item.config="{ item }">
        <code>{{ JSON.stringify(item.config) }}</code>
      </template>
      <template v-slot:item.actions="{ item }">
        <div class="d-flex ga-2 justify-end">
          <v-icon color="medium-emphasis" icon="mdi-pencil" size="small" @click="openDialog(item)"></v-icon>
          <v-icon color="error" icon="mdi-delete" size="small" @click="confirmDelete(item)"></v-icon>
        </div>
      </template>
    </v-data-table>
  </v-card>

  <v-dialog v-model="dialog" max-width="500px">
    <v-card
      :subtitle="editingId ? '修改策略参数' : '创建新的交易策略'"
      :title="editingId ? '编辑策略' : '新建策略'"
    >
      <template v-slot:text>
        <v-row>
          <v-col cols="12">
            <v-text-field v-model="form.name" label="策略名称"></v-text-field>
          </v-col>
          <v-col cols="12">
            <v-select v-model="form.type" :items="strategyTypes" label="策略类型"></v-select>
          </v-col>
          <template v-if="form.type === 'price'">
            <v-col cols="12">
              <v-text-field
                v-model.number="form.config.buy_threshold"
                label="买入阈值"
                type="number"
                step="0.01"
                hint="预测涨幅超过此值时买入，默认0.01(1%)"
                persistent-hint
              ></v-text-field>
            </v-col>
            <v-col cols="12">
              <v-text-field
                v-model.number="form.config.sell_threshold"
                label="卖出阈值"
                type="number"
                step="0.01"
                hint="预测跌幅超过此值时卖出，默认0.01(1%)"
                persistent-hint
              ></v-text-field>
            </v-col>
          </template>
          <template v-if="form.type === 'ma'">
            <v-col cols="12">
              <v-text-field
                v-model.number="form.config.ma_period"
                label="MA周期"
                type="number"
                hint="移动平均线计算周期(天)，默认20"
                persistent-hint
              ></v-text-field>
            </v-col>
            <v-col cols="12">
              <v-text-field
                v-model.number="form.config.threshold"
                label="偏离阈值"
                type="number"
                step="0.01"
                hint="价格与MA偏离阈值，默认0.01(1%)"
                persistent-hint
              ></v-text-field>
            </v-col>
          </template>
          <template v-if="form.type === 'macd'">
            <v-col cols="12">
              <v-text-field
                v-model.number="form.config.threshold"
                label="差值阈值"
                type="number"
                step="0.1"
                hint="MACD与信号线差值阈值，默认0.5"
                persistent-hint
              ></v-text-field>
            </v-col>
          </template>
        </v-row>
      </template>
      <v-divider></v-divider>
      <v-card-actions class="bg-surface-light">
        <v-btn text="取消" variant="plain" @click="dialog = false"></v-btn>
        <v-spacer></v-spacer>
        <v-btn text="保存" @click="saveStrategy"></v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="deleteDialog" max-width="400px">
    <v-card
      subtitle="此操作不可撤销"
      title="确认删除"
    >
      <template v-slot:text>
        确定要删除策略「{{ deletingItem?.name }}」吗？
      </template>
      <v-divider></v-divider>
      <v-card-actions class="bg-surface-light">
        <v-btn text="取消" variant="plain" @click="deleteDialog = false"></v-btn>
        <v-spacer></v-spacer>
        <v-btn text="删除" color="error" @click="deleteStrategy"></v-btn>
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
  { title: '操作', key: 'actions', sortable: false, align: 'end' },
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
