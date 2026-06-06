<template>
  <div>
    <!-- Summary Card -->
    <v-card border rounded class="mb-4">
      <v-card-text>
        <v-row align="center">
          <v-col cols="6" sm="3" class="d-flex align-center">
            <div class="text-caption text-medium-emphasis mr-2">总现金</div>
            <div class="text-h6 font-weight-bold text-success" style="cursor:pointer" @click="openCashEdit">
              ¥{{ formatMoney(portfolio.total_cash) }}
            </div>
          </v-col>
          <v-col cols="6" sm="2">
            <div class="text-caption text-medium-emphasis">总市值(成本)</div>
            <div class="text-h6 font-weight-bold">¥{{ formatMoney(totalCost) }}</div>
          </v-col>
          <v-col cols="6" sm="2">
            <div class="text-caption text-medium-emphasis">总资产</div>
            <div class="text-h6 font-weight-bold">¥{{ formatMoney(portfolio.total_cash + totalCost) }}</div>
          </v-col>
          <v-col cols="6" sm="2">
            <div class="text-caption text-medium-emphasis">持仓数</div>
            <div class="text-h6 font-weight-bold">{{ portfolio.positions.length }}</div>
          </v-col>
          <v-col cols="12" sm="3" class="text-right">
            <v-btn variant="tonal" color="grey" size="small" prepend-icon="mdi-cog" @click="openSettings(); settingsDialog = true">
              账户设置
            </v-btn>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Positions Table -->
    <v-card border rounded>
      <v-card-title class="d-flex align-center pa-4">
        <span class="text-subtitle-1">持仓列表</span>
        <v-spacer />
        <v-btn color="primary" variant="tonal" size="small" prepend-icon="mdi-plus" @click="openAddDialog">
          新增持仓
        </v-btn>
      </v-card-title>
      <v-card-text class="pa-0">
        <v-data-table
          :headers="positionHeaders"
          :items="portfolio.positions"
          hide-default-footer
          class="pa-0"
        >
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
      </v-card-text>
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
          >
            <template v-slot:item="{ props, item }">
              <v-list-item v-bind="props" :title="`${item.raw.name} (${item.raw.ts_code})`" :subtitle="item.raw.industry || ''" />
            </template>
            <template v-slot:selection="{ item }">
              {{ item.raw.name }} ({{ item.raw.ts_code }})
            </template>
          </v-autocomplete>
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
            v-model.number="positionForm.price"
            :label="positionDialog.isEdit ? '成本价' : '买入单价'"
            type="number"
            :min="0.01"
            step="0.01"
            hide-details="auto"
            class="mb-3"
          />
          <v-divider class="mb-3" />
          <div v-if="!positionDialog.isEdit" class="d-flex justify-space-between text-caption mb-1">
            <span class="text-medium-emphasis">小计</span>
            <span class="font-weight-medium">¥{{ formatMoney(subtotal) }}</span>
          </div>
          <div v-if="!positionDialog.isEdit" class="d-flex justify-space-between text-caption mb-1">
            <span class="text-medium-emphasis">买入手续费</span>
            <span class="font-weight-medium">¥{{ formatMoney(buyFee) }}</span>
          </div>
          <div v-if="!positionDialog.isEdit" class="d-flex justify-space-between text-caption mb-1">
            <span class="text-medium-emphasis">现金变化</span>
            <span :class="['font-weight-bold', cashChange >= 0 ? 'text-success' : 'text-error']">
              {{ cashChange >= 0 ? '+' : '' }}¥{{ formatMoney(cashChange) }}
            </span>
          </div>
          <div v-if="positionDialog.isEdit" class="d-flex justify-space-between text-caption mb-1">
            <span class="text-medium-emphasis">原总成本</span>
            <span class="font-weight-medium">¥{{ formatMoney(originalTotalCost) }}</span>
          </div>
          <div v-if="positionDialog.isEdit" class="d-flex justify-space-between text-caption mb-1">
            <span class="text-medium-emphasis">新总成本</span>
            <span class="font-weight-medium">¥{{ formatMoney(newTotalCost) }}</span>
          </div>
          <div v-if="positionDialog.isEdit" class="d-flex justify-space-between text-caption">
            <span class="text-medium-emphasis">现金变化</span>
            <span :class="['font-weight-bold', editCashDelta >= 0 ? 'text-success' : 'text-error']">
              {{ editCashDelta >= 0 ? '+' : '' }}¥{{ formatMoney(editCashDelta) }}
            </span>
          </div>
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

    <!-- Settings Dialog -->
    <v-dialog v-model="settingsDialog" max-width="450px">
      <v-card>
        <v-card-title class="d-flex justify-space-between align-center pa-4">
          账户设置
          <v-btn icon variant="text" size="small" @click="settingsDialog = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>
        <v-card-text>
          <v-text-field
            v-model.number="settingsForm.buy_fee_rate"
            label="买入费率"
            type="number"
            step="0.0001"
            :min="0"
            :suffix="`(万分之${Math.round(settingsForm.buy_fee_rate * 10000)})`"
            hide-details="auto"
            class="mb-3"
          />
          <v-text-field
            v-model.number="settingsForm.sell_fee_rate"
            label="卖出费率"
            type="number"
            step="0.0001"
            :min="0"
            :suffix="`(万分之${Math.round(settingsForm.sell_fee_rate * 10000)})`"
            hide-details="auto"
            class="mb-3"
          />
          <v-text-field
            v-model.number="settingsForm.stamp_tax_rate"
            label="印花税率"
            type="number"
            step="0.001"
            :min="0"
            :suffix="`(千分之${Math.round(settingsForm.stamp_tax_rate * 1000)})`"
            hide-details="auto"
            class="mb-3"
          />
          <v-text-field
            v-model.number="settingsForm.min_fee"
            label="最低佣金"
            type="number"
            step="0.5"
            :min="0"
            suffix="元"
            hide-details="auto"
          />
        </v-card-text>
        <v-card-actions class="pa-4 pt-0">
          <v-btn variant="text" size="small" @click="resetSettings">恢复默认</v-btn>
          <v-spacer />
          <v-btn variant="text" @click="settingsDialog = false">取消</v-btn>
          <v-btn color="primary" variant="tonal" :loading="settingsLoading" @click="saveSettings">保存</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Cash Edit Dialog -->
    <v-dialog v-model="cashDialog.show" max-width="400px">
      <v-card>
        <v-card-title class="d-flex justify-space-between align-center pa-4">
          修改现金
          <v-btn icon variant="text" size="small" @click="cashDialog.show = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>
        <v-card-text>
          <v-text-field
            v-model.number="cashDialog.value"
            label="总现金"
            type="number"
            :min="0"
            step="100"
            prefix="¥"
            hide-details="auto"
          />
        </v-card-text>
        <v-card-actions class="pa-4 pt-0">
          <v-spacer />
          <v-btn variant="text" @click="cashDialog.show = false">取消</v-btn>
          <v-btn color="primary" variant="tonal" :loading="cashDialog.loading" :disabled="cashDialog.value < 0" @click="saveCash">保存</v-btn>
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
          <p class="text-caption text-medium-emphasis mt-1">将按成本价 ¥{{ formatMoney(deleteDialog.item?.total_cost ?? 0) }} 加回现金</p>
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
import { ref, computed, onMounted } from 'vue'
import { livePortfolioApi, type LivePortfolio, type LivePosition, type StockSearchItem } from '@/api/livePortfolio'

const portfolio = ref<LivePortfolio>({
  id: '',
  total_cash: 0,
  buy_fee_rate: 0.0003,
  sell_fee_rate: 0.0003,
  stamp_tax_rate: 0.001,
  min_fee: 5.0,
  positions: [],
  created_at: '',
  updated_at: '',
})

const totalCost = computed(() =>
  portfolio.value.positions.reduce((sum, p) => sum + p.total_cost, 0)
)

const formatMoney = (v: number) => v.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

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
    const res = await livePortfolioApi.getPortfolio()
    portfolio.value = res.data
  } catch {
    // silent
  }
}

onMounted(loadPortfolio)

// ---- Stock Search ----
const stockSearchItems = ref<(StockSearchItem & { label: string })[]>([])
const searchingStock = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | null = null

const onStockSearch = (val: string | undefined) => {
  if (searchTimer) clearTimeout(searchTimer)
  const q = val ?? ''
  if (!q.trim()) {
    stockSearchItems.value = []
    return
  }
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
  shares: 100,
  price: 0,
})

const subtotal = computed(() => (positionForm.value.shares || 0) * (positionForm.value.price || 0))
const buyFee = computed(() => {
  if (subtotal.value <= 0) return 0
  return Math.max(subtotal.value * portfolio.value.buy_fee_rate, portfolio.value.min_fee)
})
const cashChange = computed(() => -(subtotal.value + buyFee.value))
const positionValid = computed(() => {
  if (!positionDialog.value.isEdit && !positionForm.value.ts_code) return false
  if (!positionForm.value.shares || positionForm.value.shares <= 0) return false
  if (!positionForm.value.price || positionForm.value.price <= 0) return false
  return true
})

// Edit mode fields
const originalTotalCost = computed(() => {
  if (!positionDialog.value.editItem) return 0
  return positionDialog.value.editItem.total_cost
})
const newTotalCost = computed(() => {
  if (!positionDialog.value.isEdit) return 0
  return (positionForm.value.shares || 0) * (positionForm.value.price || 0)
})
const editCashDelta = computed(() => {
  if (!positionDialog.value.isEdit) return 0
  return originalTotalCost.value - newTotalCost.value
})

const openAddDialog = () => {
  positionDialog.value = { show: true, isEdit: false, loading: false, editItem: null }
  positionForm.value = { ts_code: null, shares: 100, price: 0 }
  stockSearchInput.value = ''
  stockSearchItems.value = []
}

const openEditDialog = (item: LivePosition) => {
  positionDialog.value = { show: true, isEdit: true, loading: false, editItem: item }
  positionForm.value = { ts_code: null, shares: item.shares, price: item.cost_price }
}

const savePosition = async () => {
  positionDialog.value.loading = true
  try {
    if (positionDialog.value.isEdit && positionDialog.value.editItem) {
      const res = await livePortfolioApi.updatePosition(positionDialog.value.editItem.id, {
        shares: positionForm.value.shares,
        cost_price: positionForm.value.price,
      })
      portfolio.value = res.data
    } else if (positionForm.value.ts_code) {
      const res = await livePortfolioApi.addPosition({
        ts_code: positionForm.value.ts_code.ts_code,
        stock_name: positionForm.value.ts_code.name,
        shares: positionForm.value.shares,
        price: positionForm.value.price,
      })
      portfolio.value = res.data
    }
    positionDialog.value.show = false
  } catch (e: any) {
    // TODO: show error
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
    const res = await livePortfolioApi.deletePosition(deleteDialog.value.item.id)
    portfolio.value = res.data
    deleteDialog.value.show = false
  } catch {
    // silent
  } finally {
    deleteDialog.value.loading = false
  }
}

// ---- Cash Edit ----
const cashDialog = ref({
  show: false,
  loading: false,
  value: 0,
})

const openCashEdit = () => {
  cashDialog.value = { show: true, loading: false, value: portfolio.value.total_cash }
}

const saveCash = async () => {
  cashDialog.value.loading = true
  try {
    const res = await livePortfolioApi.updateCash(cashDialog.value.value)
    portfolio.value = res.data
    cashDialog.value.show = false
  } catch {
    // silent
  } finally {
    cashDialog.value.loading = false
  }
}

// ---- Settings ----
const settingsDialog = ref(false)
const settingsLoading = ref(false)
const settingsForm = ref({
  buy_fee_rate: 0.0003,
  sell_fee_rate: 0.0003,
  stamp_tax_rate: 0.001,
  min_fee: 5.0,
})

const openSettings = () => {
  settingsForm.value = {
    buy_fee_rate: portfolio.value.buy_fee_rate,
    sell_fee_rate: portfolio.value.sell_fee_rate,
    stamp_tax_rate: portfolio.value.stamp_tax_rate,
    min_fee: portfolio.value.min_fee,
  }
}

const resetSettings = () => {
  settingsForm.value = { buy_fee_rate: 0.0003, sell_fee_rate: 0.0003, stamp_tax_rate: 0.001, min_fee: 5.0 }
}

const saveSettings = async () => {
  settingsLoading.value = true
  try {
    const res = await livePortfolioApi.updateSettings(settingsForm.value)
    portfolio.value = res.data
    settingsDialog.value = false
  } catch {
    // silent
  } finally {
    settingsLoading.value = false
  }
}
</script>