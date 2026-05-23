<template>
  <v-card border rounded>
    <v-card-title class="d-flex justify-space-between align-center pa-4">
      <div class="d-flex align-center ga-2">
        <v-icon color="primary">mdi-wallet</v-icon>
        <span class="text-h6">账户配置</span>
      </div>
      <v-btn
        prepend-icon="mdi-plus"
        rounded="lg"
        text="新建账户"
        border
        @click="openDialog()"
      ></v-btn>
    </v-card-title>
    <v-data-table
      :headers="headers"
      :items="accountConfigs"
      :loading="loading"
    >
      <template v-slot:item.initial_capital="{ item }">
        {{ formatMoney(item.initial_capital) }}
      </template>
      <template v-slot:item.buy_fee_rate="{ item }">
        {{ formatPercent(item.buy_fee_rate) }}
      </template>
      <template v-slot:item.sell_fee_rate="{ item }">
        {{ formatPercent(item.sell_fee_rate) }}
      </template>
      <template v-slot:item.stamp_tax_rate="{ item }">
        {{ formatPercent(item.stamp_tax_rate) }}
      </template>
      <template v-slot:item.min_fee="{ item }">
        {{ formatMoney(item.min_fee) }}
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

  <v-dialog v-model="dialog" max-width="500px">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center">
        {{ editingId ? '编辑账户' : '新建账户' }}
        <v-btn icon variant="text" size="small" @click="dialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>
        <v-row>
          <v-col cols="12">
            <v-text-field v-model="form.name" label="账户名称"></v-text-field>
          </v-col>
          <v-col cols="12" sm="6">
            <v-text-field v-model.number="form.initial_capital" label="初始资金" type="number"></v-text-field>
          </v-col>
          <v-col cols="12" sm="6">
            <v-text-field v-model.number="form.buy_fee_rate" label="买入费率" type="number"></v-text-field>
          </v-col>
          <v-col cols="12" sm="6">
            <v-text-field v-model.number="form.sell_fee_rate" label="卖出费率" type="number"></v-text-field>
          </v-col>
          <v-col cols="12" sm="6">
            <v-text-field v-model.number="form.stamp_tax_rate" label="印花税" type="number"></v-text-field>
          </v-col>
          <v-col cols="12" sm="6">
            <v-text-field v-model.number="form.min_fee" label="最低手续费" type="number"></v-text-field>
          </v-col>
        </v-row>
      </v-card-text>
      <v-divider></v-divider>
      <v-card-actions class="bg-surface-light">
        <v-btn text="取消" variant="plain" @click="dialog = false"></v-btn>
        <v-spacer></v-spacer>
        <v-btn text="保存" @click="saveAccountConfig"></v-btn>
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
      <v-card-text>此操作不可撤销，确定要删除账户「{{ deletingItem?.name }}」吗？</v-card-text>
      <v-divider></v-divider>
      <v-card-actions class="bg-surface-light">
        <v-btn text="取消" variant="plain" @click="deleteDialog = false"></v-btn>
        <v-spacer></v-spacer>
        <v-btn text="删除" color="error" @click="deleteAccountConfig"></v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { accountConfigApi, type AccountConfig } from '@/api/accountConfig'

const loading = ref(false)
const dialog = ref(false)
const deleteDialog = ref(false)
const accountConfigs = ref<AccountConfig[]>([])
const editingId = ref<string | null>(null)
const deletingItem = ref<AccountConfig | null>(null)
const form = ref({
  name: '',
  initial_capital: 100000,
  buy_fee_rate: 0.0003,
  sell_fee_rate: 0.0003,
  stamp_tax_rate: 0.001,
  min_fee: 5,
})

const headers = [
  { title: '名称', key: 'name' },
  { title: '初始资金', key: 'initial_capital' },
  { title: '买入费率', key: 'buy_fee_rate' },
  { title: '卖出费率', key: 'sell_fee_rate' },
  { title: '印花税', key: 'stamp_tax_rate' },
  { title: '最低手续费', key: 'min_fee' },
  { title: '创建时间', key: 'created_at' },
  { title: '操作', key: 'actions', sortable: false, align: 'end' },
]

const formatMoney = (val: number) => {
  return val.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const formatPercent = (val: number) => {
  return (val * 100).toFixed(3) + '%'
}

const formatDate = (val: string) => {
  if (!val) return ''
  const d = val.split('T')[0]
  const t = val.split('T')[1]?.split('.')[0]?.substring(0, 5)
  return t ? `${d} ${t}` : d
}

const loadAccountConfigs = async () => {
  loading.value = true
  const res = await accountConfigApi.list()
  accountConfigs.value = res.data
  loading.value = false
}

const openDialog = (item?: AccountConfig) => {
  if (item) {
    editingId.value = item.id
    form.value = { ...item }
  } else {
    editingId.value = null
    form.value = { name: 'default_account_config', initial_capital: 100000, buy_fee_rate: 0.0003, sell_fee_rate: 0.0003, stamp_tax_rate: 0.001, min_fee: 5 }
  }
  dialog.value = true
}

const saveAccountConfig = async () => {
  if (editingId.value) {
    await accountConfigApi.update(editingId.value, form.value)
  } else {
    await accountConfigApi.create(form.value)
  }
  dialog.value = false
  await loadAccountConfigs()
}

const confirmDelete = (item: AccountConfig) => {
  deletingItem.value = item
  deleteDialog.value = true
}

const deleteAccountConfig = async () => {
  if (!deletingItem.value) return
  await accountConfigApi.delete(deletingItem.value.id)
  deleteDialog.value = false
  deletingItem.value = null
  await loadAccountConfigs()
}

onMounted(() => {
  loadAccountConfigs()
})
</script>
