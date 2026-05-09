<template>
  <v-container>
    <v-card>
      <v-card-title class="d-flex align-center">
        账户管理
        <v-spacer />
        <v-btn color="primary" @click="openDialog()">新建账户</v-btn>
      </v-card-title>
      <v-data-table :headers="headers" :items="portfolios" :loading="loading">
        <template v-slot:item.actions="{ item }">
          <v-btn size="small" variant="text" @click="openDialog(item)">编辑</v-btn>
          <v-btn size="small" color="error" variant="text" @click="deletePortfolio(item)">删除</v-btn>
        </template>
      </v-data-table>
    </v-card>

    <v-dialog v-model="dialog" max-width="500">
      <v-card>
        <v-card-title>{{ editingId ? '编辑账户' : '新建账户' }}</v-card-title>
        <v-card-text>
          <v-text-field v-model="form.name" label="账户名称" />
          <v-text-field v-model="form.initial_capital" label="初始资金" type="number" />
          <v-text-field v-model="form.buy_fee_rate" label="买入费率" type="number" />
          <v-text-field v-model="form.sell_fee_rate" label="卖出费率" type="number" />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="dialog = false">取消</v-btn>
          <v-btn color="primary" @click="savePortfolio">保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
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
  { title: '操作', key: 'actions', sortable: false },
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
