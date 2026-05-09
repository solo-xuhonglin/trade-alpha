<template>
  <v-card class="ma-2" variant="outlined" rounded="xl">
    <v-card-title class="d-flex align-center">
      <span class="text-h5 font-weight-bold">账户管理</span>
      <v-spacer />
      <v-btn color="primary" @click="openDialog()" prepend-icon="mdi-plus" density="comfortable">新建账户</v-btn>
    </v-card-title>
    <v-divider />
    <v-data-table :headers="headers" :items="portfolios" :loading="loading" density="comfortable" hover>
      <template v-slot:item.actions="{ item }">
        <v-btn size="small" variant="flat" @click="openDialog(item)" class="mr-2">编辑</v-btn>
        <v-btn size="small" color="error" variant="flat" @click="deletePortfolio(item)">删除</v-btn>
      </template>
    </v-data-table>
  </v-card>

  <v-dialog v-model="dialog" max-width="90vw" max-height="90vh" scrollable>
    <v-card rounded="xl">
      <v-card-title class="text-h6 font-weight-bold">{{ editingId ? '编辑账户' : '新建账户' }}</v-card-title>
      <v-divider />
      <v-card-text class="pt-4">
        <v-row dense>
          <v-col cols="12" sm="6">
            <v-text-field v-model="form.name" label="账户名称" variant="outlined" density="comfortable" hide-details />
          </v-col>
          <v-col cols="12" sm="6">
            <v-text-field v-model.number="form.initial_capital" label="初始资金" type="number" variant="outlined" density="comfortable" hide-details />
          </v-col>
          <v-col cols="12" sm="4">
            <v-text-field v-model.number="form.buy_fee_rate" label="买入费率" type="number" variant="outlined" density="comfortable" hide-details />
          </v-col>
          <v-col cols="12" sm="4">
            <v-text-field v-model.number="form.sell_fee_rate" label="卖出费率" type="number" variant="outlined" density="comfortable" hide-details />
          </v-col>
          <v-col cols="12" sm="4">
            <v-text-field v-model.number="form.stamp_tax_rate" label="印花税" type="number" variant="outlined" density="comfortable" hide-details />
          </v-col>
          <v-col cols="12" sm="6">
            <v-text-field v-model.number="form.min_fee" label="最低手续费" type="number" variant="outlined" density="comfortable" hide-details />
          </v-col>
        </v-row>
      </v-card-text>
      <v-divider />
      <v-card-actions>
        <v-spacer />
        <v-btn @click="dialog = false" variant="outlined" density="comfortable">取消</v-btn>
        <v-btn color="primary" @click="savePortfolio" variant="flat" density="comfortable">保存</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { portfolioApi, type Portfolio } from '@/api/portfolio'

const loading = ref(false)
const dialog = ref(false)
const portfolios = ref<Portfolio[]>([])
const editingId = ref<string | null>(null)
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
  { title: '当前现金', key: 'cash' },
  { title: '持仓', key: 'position' },
  { title: '操作', key: 'actions', sortable: false, align: 'center' as const },
]

const loadPortfolios = async () => {
  loading.value = true
  try {
    const res = await portfolioApi.list()
    portfolios.value = res.data
  } finally {
    loading.value = false
  }
}

const openDialog = (item?: Portfolio) => {
  if (item) {
    editingId.value = item.id
    form.value = { ...item }
  } else {
    editingId.value = null
    form.value = { name: '', initial_capital: 100000, buy_fee_rate: 0.0003, sell_fee_rate: 0.0003, stamp_tax_rate: 0.001, min_fee: 5 }
  }
  dialog.value = true
}

const savePortfolio = async () => {
  if (editingId.value) {
    await portfolioApi.update(editingId.value, form.value)
  } else {
    await portfolioApi.create(form.value)
  }
  dialog.value = false
  await loadPortfolios()
}

const deletePortfolio = async (item: Portfolio) => {
  await portfolioApi.delete(item.id)
  await loadPortfolios()
}

onMounted(() => {
  loadPortfolios()
})
</script>
