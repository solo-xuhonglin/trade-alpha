<template>
  <div>
    <!-- Portfolio Selector -->
    <v-card border rounded class="mb-4">
      <v-card-text class="d-flex align-center ga-4">
        <v-select
          v-model="selectedPortfolioId"
          :items="portfolioOptions"
          item-title="name"
          item-value="id"
          label="选择组合"
          style="max-width: 300px;"
          hide-details
          @update:model-value="onPortfolioChange"
        />
        <v-btn prepend-icon="mdi-plus" variant="tonal" color="primary" @click="createPortfolioDialog.show = true">
          新建组合
        </v-btn>
        <v-btn
          v-if="selectedPortfolioId"
          prepend-icon="mdi-delete"
          variant="tonal"
          color="error"
          :disabled="portfolioOptions.length <= 1"
          @click="deletePortfolioDialog.show = true"
        >
          删除组合
        </v-btn>
      </v-card-text>
    </v-card>

    <v-dialog v-model="createPortfolioDialog.show" max-width="400px">
      <v-card>
        <v-card-title>新建组合</v-card-title>
        <v-card-text>
          <v-text-field
            v-model="createPortfolioDialog.name"
            label="组合名称"
            hide-details
            :error-messages="createPortfolioDialog.error"
            @keyup.enter="confirmCreatePortfolio"
          />
        </v-card-text>
        <v-card-actions class="pa-4 pt-0">
          <v-spacer />
          <v-btn variant="text" @click="createPortfolioDialog.show = false">取消</v-btn>
          <v-btn color="primary" variant="tonal" :loading="createPortfolioDialog.loading" :disabled="!createPortfolioDialog.name" @click="confirmCreatePortfolio">
            创建
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Portfolio Confirmation Dialog -->
    <v-dialog v-model="deletePortfolioDialog.show" max-width="400px">
      <v-card>
        <v-card-title class="text-h6 d-flex justify-space-between align-center pa-4">
          确认删除组合
          <v-btn icon variant="text" size="small" @click="deletePortfolioDialog.show = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>
        <v-card-text>
          <p>确定删除选中的组合？</p>
          <p v-if="portfolio.positions.length > 0" class="text-red mt-2">
            该组合下还有 {{ portfolio.positions.length }} 个持仓，删除后不可恢复。
          </p>
          <p v-if="deletePortfolioDialog.error" class="text-error mt-2">{{ deletePortfolioDialog.error }}</p>
        </v-card-text>
        <v-card-actions class="pa-4 pt-0">
          <v-spacer />
          <v-btn variant="text" @click="deletePortfolioDialog.show = false">取消</v-btn>
          <v-btn color="error" variant="tonal" :loading="deletePortfolioDialog.loading" @click="confirmDeletePortfolio">
            删除
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Positions Table -->
    <v-card border rounded>
      <v-data-table
        :headers="positionHeaders"
        :items="portfolio.positions"
        hide-default-footer
        class="pa-0"
      >
        <template v-slot:top>
          <v-toolbar flat>
            <v-toolbar-title>持仓列表</v-toolbar-title>
            <v-btn prepend-icon="mdi-plus" rounded="lg" text="新增持仓" border @click="openAddDialog()"></v-btn>
          </v-toolbar>
        </template>
        <template v-slot:item.cost_price="{ item }">
          ¥{{ formatMoney(item.cost_price) }}
        </template>
        <template v-slot:item.total_cost="{ item }">
          ¥{{ formatMoney(item.total_cost) }}
        </template>
        <template v-slot:item.actions="{ item }">
          <v-btn icon variant="text" size="small" color="primary" @click="openEditDialog(item)">
            <v-icon>mdi-pencil</v-icon>
          </v-btn>
          <v-btn icon variant="text" size="small" color="error" @click="openDeleteDialog(item)">
            <v-icon>mdi-delete</v-icon>
          </v-btn>
        </template>
        <template v-slot:no-data>
          <div class="text-center text-medium-emphasis pa-4">暂无持仓，点击"新增持仓"添加</div>
        </template>
      </v-data-table>
    </v-card>

    <!-- Add/Edit Position Dialog -->
    <v-dialog v-model="positionDialog.show" max-width="500px">
      <v-card>
        <v-card-title class="d-flex justify-space-between align-center pa-4">
          {{ positionDialog.isEdit ? '编辑持仓' : '新增持仓' }}
          <v-btn icon variant="text" size="small" @click="positionDialog.show = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>
        <v-card-text>
          <v-autocomplete
            v-if="!positionDialog.isEdit"
            v-model="positionForm.ts_code"
            :items="stockSearchItems"
            item-title="label"
            item-value="ts_code"
            label="搜索股票（代码/名称）"
            :loading="searchingStock"
            hide-details
            class="mb-3"
            clearable
            return-object
            @update:search-input="onStockSearch"
          />
          <div v-if="positionDialog.isEdit" class="mb-3">
            <div class="text-caption text-medium-emphasis">股票</div>
            <div class="text-body-1 font-weight-medium">{{ positionDialog.editItem?.stock_name }} ({{ positionDialog.editItem?.ts_code }})</div>
          </div>
          <v-text-field
            v-model.number="positionForm.shares"
            label="股数"
            type="number"
            :min="1"
            :step="100"
            hide-details="auto"
            class="mb-3"
          />
          <v-text-field
            v-model="positionForm.trade_date"
            label="交易日期"
            type="text"
            placeholder="YYYYMMDD"
            hide-details="auto"
            class="mb-3"
            :disabled="!positionForm.ts_code"
            :readonly="positionDialog.isEdit"
          />
          <v-text-field
            v-model.number="positionForm.price"
            :label="positionDialog.isEdit ? '成本价' : '买入单价'"
            type="number"
            :min="0.01"
            step="0.01"
            hide-details="auto"
            class="mb-3"
          />
        </v-card-text>
        <v-card-actions class="pa-4 pt-0">
          <v-spacer />
          <v-btn variant="text" @click="positionDialog.show = false">取消</v-btn>
          <v-btn color="primary" variant="tonal" :loading="positionDialog.loading" :disabled="!positionValid" @click="savePosition">
            {{ positionDialog.isEdit ? '保存' : '确认' }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Confirmation Dialog -->
    <v-dialog v-model="deleteDialog.show" max-width="400px">
      <v-card>
        <v-card-title class="text-h6 d-flex justify-space-between align-center pa-4">
          确认删除
          <v-btn icon variant="text" size="small" @click="deleteDialog.show = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>
        <v-card-text>
          <p>确定删除 <strong>{{ deleteDialog.item?.stock_name }} ({{ deleteDialog.item?.ts_code }})</strong> 的持仓？</p>
        </v-card-text>
        <v-card-actions class="pa-4 pt-0">
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog.show = false">取消</v-btn>
          <v-btn color="error" variant="tonal" :loading="deleteDialog.loading" @click="confirmDelete">删除</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { livePortfolioApi, type LivePortfolio, type LivePosition, type StockSearchItem, type PortfolioOption } from '@/api/livePortfolio'
import { dataApi } from '@/api/data'

const portfolio = ref<LivePortfolio>({
  id: '',
  positions: [],
  created_at: '',
  updated_at: '',
})

const formatMoney = (v: number) => v.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

const selectedPortfolioId = ref<string | undefined>(undefined)
const portfolioOptions = ref<PortfolioOption[]>([])
const createPortfolioDialog = ref({
  show: false,
  loading: false,
  name: '',
  error: '',
})

const deletePortfolioDialog = ref({
  show: false,
  loading: false,
  error: '',
})

const positionHeaders = [
  { title: '股票名称', key: 'stock_name' },
  { title: '代码', key: 'ts_code' },
  { title: '股数', key: 'shares' },
  { title: '成本价', key: 'cost_price' },
  { title: '总成本', key: 'total_cost' },
  { title: '操作', key: 'actions', sortable: false, width: 100 },
]

// ---- Load ----
const loadPortfolio = async () => {
  try {
    const res = await livePortfolioApi.getPortfolio(selectedPortfolioId.value)
    portfolio.value = res.data
  } catch {
    // silent
  }
}

onMounted(async () => {
  await loadPortfolioOptions()
  await loadPortfolio()
})

async function loadPortfolioOptions() {
  try {
    const res = await livePortfolioApi.listOptions()
    portfolioOptions.value = res.data.items
    if (!selectedPortfolioId.value && portfolioOptions.value.length > 0) {
      const def = portfolioOptions.value.find(p => p.name === 'default') || portfolioOptions.value[0]
      selectedPortfolioId.value = def.id
    }
  } catch { /* silent */ }
}

async function onPortfolioChange(id: string) {
  selectedPortfolioId.value = id
  await loadPortfolio()
}

async function confirmCreatePortfolio() {
  createPortfolioDialog.value.loading = true
  createPortfolioDialog.value.error = ''
  try {
    const res = await livePortfolioApi.createPortfolio(createPortfolioDialog.value.name)
    createPortfolioDialog.value.show = false
    createPortfolioDialog.value.name = ''
    await loadPortfolioOptions()
    selectedPortfolioId.value = res.data.id
    await loadPortfolio()
  } catch (e: any) {
    createPortfolioDialog.value.error = e?.response?.data?.detail || e?.message || '创建失败'
  }
  finally { createPortfolioDialog.value.loading = false }
}

async function confirmDeletePortfolio() {
  if (!selectedPortfolioId.value) return
  deletePortfolioDialog.value.loading = true
  deletePortfolioDialog.value.error = ''
  try {
    await livePortfolioApi.deletePortfolio(selectedPortfolioId.value)
    deletePortfolioDialog.value.show = false
    await loadPortfolioOptions()
    // Switch to first available portfolio
    if (portfolioOptions.value.length > 0) {
      selectedPortfolioId.value = portfolioOptions.value[0].id
      await loadPortfolio()
    } else {
      portfolio.value = { id: '', positions: [], created_at: '', updated_at: '' }
    }
  } catch (e: any) {
    deletePortfolioDialog.value.error = e?.response?.data?.detail || e?.message || '删除失败'
  }
  finally { deletePortfolioDialog.value.loading = false }
}

// ---- Stock Search ----
const stockSearchItems = ref<(StockSearchItem & { label: string })[]>([])
const searchingStock = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | null = null

const onStockSearch = (val: string | undefined) => {
  if (searchTimer) clearTimeout(searchTimer)
  const q = val ?? ''
  searchTimer = setTimeout(async () => {
    searchingStock.value = true
    try {
      const res = await livePortfolioApi.searchStocks(q)
      stockSearchItems.value = res.data.items.map((s: StockSearchItem) => ({
        ...s,
        label: `${s.name} (${s.ts_code})`,
      }))
    } catch {
      // silent
    } finally {
      searchingStock.value = false
    }
  }, 300)
}

// ---- Add/Edit Position Dialog ----
const positionDialog = ref({
  show: false,
  isEdit: false,
  loading: false,
  editItem: null as LivePosition | null,
})

const positionForm = ref({
  ts_code: null as ({ ts_code: string; name: string } | null),
  trade_date: '',
  shares: 100,
  price: 0,
})

// ---- Auto-fill latest trade date & close when stock is selected ----
const fillLatestPrice = async (tsCode: string) => {
  try {
    const res = await dataApi.getDataPaginated(tsCode, 1, 1)
    const items = res.data.items
    if (items && items.length > 0) {
      positionForm.value.trade_date = items[0].trade_date
      positionForm.value.price = items[0].close
    }
  } catch {
    // silent
  }
}

// Watch for stock selection
watch(
  () => positionForm.value.ts_code,
  (newVal) => {
    if (newVal && newVal.ts_code && !positionDialog.value.isEdit) {
      fillLatestPrice(newVal.ts_code)
    }
  },
)

// ---- Auto-fill close price when trade date changes ----
watch(
  () => positionForm.value.trade_date,
  async (newDate, oldDate) => {
    if (!newDate || !positionForm.value.ts_code || positionDialog.value.isEdit) return
    if (newDate === oldDate) return
    try {
      const res = await dataApi.getData(positionForm.value.ts_code.ts_code, newDate, newDate)
      const items = res.data
      if (items && items.length > 0) {
        positionForm.value.price = items[0].close
      }
    } catch {
      // silent
    }
  },
)

const positionValid = computed(() => {
  if (!positionDialog.value.isEdit && !positionForm.value.ts_code) return false
  if (!positionForm.value.shares || positionForm.value.shares <= 0) return false
  if (!positionForm.value.price || positionForm.value.price <= 0) return false
  return true
})

const openAddDialog = () => {
  positionDialog.value = { show: true, isEdit: false, loading: false, editItem: null }
  positionForm.value = { ts_code: null, trade_date: '', shares: 100, price: 0 }
  onStockSearch('')
}

const openEditDialog = (item: LivePosition) => {
  positionDialog.value = { show: true, isEdit: true, loading: false, editItem: item }
  positionForm.value = { ts_code: null, trade_date: '', shares: item.shares, price: item.cost_price }
}

const savePosition = async () => {
  positionDialog.value.loading = true
  try {
    if (positionDialog.value.isEdit && positionDialog.value.editItem) {
      const res = await livePortfolioApi.updatePosition(positionDialog.value.editItem.id, {
        shares: positionForm.value.shares,
        cost_price: positionForm.value.price,
      }, selectedPortfolioId.value)
      portfolio.value = res.data
    } else if (positionForm.value.ts_code) {
      const res = await livePortfolioApi.addPosition({
        ts_code: positionForm.value.ts_code.ts_code,
        stock_name: positionForm.value.ts_code.name,
        shares: positionForm.value.shares,
        price: positionForm.value.price,
      }, selectedPortfolioId.value)
      portfolio.value = res.data
    }
    positionDialog.value.show = false
  } catch {
    // silent
  } finally {
    positionDialog.value.loading = false
  }
}

// ---- Delete ----
const deleteDialog = ref({
  show: false,
  loading: false,
  item: null as LivePosition | null,
})

const openDeleteDialog = (item: LivePosition) => {
  deleteDialog.value = { show: true, loading: false, item }
}

const confirmDelete = async () => {
  if (!deleteDialog.value.item) return
  deleteDialog.value.loading = true
  try {
    const res = await livePortfolioApi.deletePosition(deleteDialog.value.item.id, selectedPortfolioId.value)
    portfolio.value = res.data
    deleteDialog.value.show = false
  } catch {
    // silent
  } finally {
    deleteDialog.value.loading = false
  }
}
</script>