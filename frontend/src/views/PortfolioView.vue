<template>
  <v-data-table
    :headers="headers"
    :items="portfolios"
    :loading="loading"
    class="border rounded"
  >
    <template v-slot:top>
      <v-toolbar flat>
        <v-toolbar-title>账户管理</v-toolbar-title>
        <v-spacer />
        <v-btn color="primary" @click="openDialog()">新建账户</v-btn>
      </v-toolbar>
    </template>
    <template v-slot:item.actions="{ item }">
      <v-icon class="me-2" @click="openDialog(item)">mdi-pencil</v-icon>
      <v-icon color="error" @click="confirmDelete(item)">mdi-delete</v-icon>
    </template>
  </v-data-table>

  <v-dialog v-model="dialog" max-width="500px">
    <v-card>
      <v-card-title class="text-h5">{{ editingId ? '编辑账户' : '新建账户' }}</v-card-title>
      <v-card-text>
        <v-container>
          <v-row>
            <v-col cols="12">
              <v-text-field v-model="form.name" label="账户名称" />
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field v-model.number="form.initial_capital" label="初始资金" type="number" />
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field v-model.number="form.buy_fee_rate" label="买入费率" type="number" />
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field v-model.number="form.sell_fee_rate" label="卖出费率" type="number" />
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field v-model.number="form.stamp_tax_rate" label="印花税" type="number" />
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field v-model.number="form.min_fee" label="最低手续费" type="number" />
            </v-col>
          </v-row>
        </v-container>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="dialog = false">取消</v-btn>
        <v-btn color="primary" variant="text" @click="savePortfolio">保存</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="deleteDialog" max-width="400px">
    <v-card>
      <v-card-title class="text-h5">确认删除</v-card-title>
      <v-card-text>确定要删除账户「{{ deletingItem?.name }}」吗？</v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="deleteDialog = false">取消</v-btn>
        <v-btn color="error" variant="text" @click="deletePortfolio">删除</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { portfolioApi, type Portfolio } from '@/api/portfolio'

const loading = ref(false)
const dialog = ref(false)
const deleteDialog = ref(false)
const portfolios = ref<Portfolio[]>([])
const editingId = ref<string | null>(null)
const deletingItem = ref<Portfolio | null>(null)
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
    form.value = { name: 'default_portfolio', initial_capital: 100000, buy_fee_rate: 0.0003, sell_fee_rate: 0.0003, stamp_tax_rate: 0.001, min_fee: 5 }
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

const confirmDelete = (item: Portfolio) => {
  deletingItem.value = item
  deleteDialog.value = true
}

const deletePortfolio = async () => {
  if (!deletingItem.value) return
  await portfolioApi.delete(deletingItem.value.id)
  deleteDialog.value = false
  deletingItem.value = null
  await loadPortfolios()
}

onMounted(() => {
  loadPortfolios()
})
</script>
