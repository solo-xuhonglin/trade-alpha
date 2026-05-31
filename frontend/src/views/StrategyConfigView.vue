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
            策略配置
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

      <template v-slot:item.actions="{ item }">
        <div class="d-flex ga-1 justify-end">
          <v-btn size="small" variant="text" prepend-icon="mdi-pencil" @click="openDialog(item)">编辑</v-btn>
          <v-btn size="small" variant="text" color="error" prepend-icon="mdi-delete" @click="confirmDelete(item)">删除</v-btn>
        </div>
      </template>
    </v-data-table>
  </v-card>

  <v-dialog v-model="dialog" max-width="700px">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center">
        {{ editingId ? '编辑策略' : '新建策略' }}
        <v-btn icon variant="text" size="small" @click="dialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>
        <v-tabs v-model="activeTab" color="primary" v-if="form.type === 'multi'">
          <v-tab value="basic">基本配置</v-tab>
          <v-tab value="multi">多股票配置</v-tab>
          <v-tab value="ranking">排名优化</v-tab>
        </v-tabs>

        <v-window v-model="activeTab" v-if="form.type === 'multi'" class="mt-4">
          <v-window-item value="basic">
            <div>
              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field v-model="form.name" label="策略名称"></v-text-field>
                </v-col>
                <v-col cols="12" md="6">
                  <v-select v-model="form.type" :items="strategyTypes" label="策略类型"></v-select>
                </v-col>
              </v-row>

              <v-divider class="my-4"></v-divider>

              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="form.min_order_value"
                    type="number"
                    label="最小订单金额"
                    hint="避免买入金额过小的订单"
                    persistent-hint
                  ></v-text-field>
                </v-col>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="form.stop_loss_pct"
                    type="number"
                    label="止损比例"
                    hint="例如 -0.1 表示亏损10%止损"
                    persistent-hint
                  ></v-text-field>
                </v-col>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="form.max_hold_days"
                    type="number"
                    label="最大持仓天数"
                  ></v-text-field>
                </v-col>
              </v-row>

              <v-divider class="my-4"></v-divider>

              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="form.buy_threshold"
                    type="number"
                    step="0.05"
                    label="买入阈值"
                    hint="评分高于此值买入"
                    persistent-hint
                  ></v-text-field>
                </v-col>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="form.sell_threshold"
                    type="number"
                    step="0.05"
                    label="卖出阈值"
                    hint="评分低于此值卖出"
                    persistent-hint
                  ></v-text-field>
                </v-col>
              </v-row>
            </div>
          </v-window-item>

          <v-window-item value="multi">
            <div>
              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="form.max_positions"
                    type="number"
                    label="最大持仓数"
                    hint="买入排名前N的股票"
                    persistent-hint
                  ></v-text-field>
                </v-col>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="form.max_position_pct"
                    type="number"
                    label="单票最大仓位比例"
                    hint="例如 0.3 表示单票最多占30%"
                    persistent-hint
                  ></v-text-field>
                </v-col>
              </v-row>

              <v-divider class="my-4"></v-divider>

              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="form.sell_rank_n"
                    type="number"
                    label="卖出排名阈值"
                    hint="掉出此排名时考虑卖出"
                    persistent-hint
                  ></v-text-field>
                </v-col>
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="form.hold_score_threshold"
                    type="number"
                    step="0.01"
                    label="持仓评分保护阈值"
                    hint="掉出排名但评分高于此值可继续持有"
                    persistent-hint
                  ></v-text-field>
                </v-col>
              </v-row>
            </div>
          </v-window-item>

          <v-window-item value="ranking">
            <div>
              <div class="d-flex align-center mb-2">
                <v-switch v-model="form.use_momentum_boost" hide-details density="compact" color="primary"
                  class="mr-2" label="动量加权"></v-switch>
                <v-chip size="x-small" variant="outlined" color="info">连续正向评分加成</v-chip>
              </div>
              <v-row>
                <v-col cols="12" md="6">
                  <v-text-field v-model.number="form.momentum_window" type="number" label="窗口天数"
                    hint="统计过去 N 天评分 > 0 的比例" persistent-hint
                    :disabled="!form.use_momentum_boost"></v-text-field>
                </v-col>
                <v-col cols="12" md="6">
                  <v-text-field v-model.number="form.max_momentum_bonus" type="number" step="0.01"
                    label="最大动量加成" hint="排名分 = 评分 + 比例 × 最大加成" persistent-hint
                    :disabled="!form.use_momentum_boost"></v-text-field>
                </v-col>
              </v-row>

              <v-divider class="my-4"></v-divider>

              <div class="d-flex align-center mb-2">
                <v-switch v-model="form.use_explosion_filter" hide-details density="compact" color="primary"
                  class="mr-2" label="暴涨排除"></v-switch>
                <v-chip size="x-small" variant="outlined" color="warning">放量暴涨不买入</v-chip>
              </div>
              <v-row>
                <v-col cols="12" md="4">
                  <v-text-field v-model.number="form.explosion_price_threshold" type="number" step="0.01"
                    label="涨幅阈值" hint="高于参考均价此比例" persistent-hint
                    :disabled="!form.use_explosion_filter"></v-text-field>
                </v-col>
                <v-col cols="12" md="4">
                  <v-text-field v-model.number="form.explosion_volume_ratio" type="number" step="0.5"
                    label="量比阈值" hint="当前量/均量超过此倍数" persistent-hint
                    :disabled="!form.use_explosion_filter"></v-text-field>
                </v-col>
                <v-col cols="12" md="4">
                  <v-text-field v-model.number="form.explosion_window" type="number"
                    label="参考窗口" hint="均价和均量的计算天数" persistent-hint
                    :disabled="!form.use_explosion_filter"></v-text-field>
                </v-col>
              </v-row>

              <v-divider class="my-4"></v-divider>

              <div class="d-flex align-center mb-2">
                <v-switch v-model="form.use_trend_boost" hide-details density="compact" color="primary"
                  class="mr-2" label="趋势左移"></v-switch>
                <v-chip size="x-small" variant="outlined" color="info">分数趋势提前反映</v-chip>
              </div>
              <v-row>
                <v-col cols="12" md="4">
                  <v-text-field v-model.number="form.trend_window" type="number"
                    label="窗口天数" hint="斜率计算的天数" persistent-hint
                    :disabled="!form.use_trend_boost"></v-text-field>
                </v-col>
                <v-col cols="12" md="4">
                  <v-text-field v-model.number="form.trend_scale" type="number" step="0.1"
                    label="斜率系数" hint="斜率×系数=趋势加成" persistent-hint
                    :disabled="!form.use_trend_boost"></v-text-field>
                </v-col>
                <v-col cols="12" md="4">
                  <v-text-field v-model.number="form.max_trend_boost" type="number" step="0.01"
                    label="最大加成" hint="上下限，防止过度干预" persistent-hint
                    :disabled="!form.use_trend_boost"></v-text-field>
                </v-col>
              </v-row>
            </div>
          </v-window-item>
        </v-window>

        <div v-else>
          <v-row>
            <v-col cols="12" md="6">
              <v-text-field v-model="form.name" label="策略名称"></v-text-field>
            </v-col>
            <v-col cols="12" md="6">
              <v-select v-model="form.type" :items="strategyTypes" label="策略类型"></v-select>
            </v-col>
          </v-row>

          <v-divider class="my-4"></v-divider>

          <v-row>
            <v-col cols="12" md="6">
              <v-text-field
                v-model="form.min_order_value"
                type="number"
                label="最小订单金额"
                hint="避免买入金额过小的订单"
                persistent-hint
              ></v-text-field>
            </v-col>
            <v-col cols="12" md="6">
              <v-text-field
                v-model="form.stop_loss_pct"
                type="number"
                label="止损比例"
                hint="例如 -0.1 表示亏损10%止损"
                persistent-hint
              ></v-text-field>
            </v-col>
            <v-col cols="12" md="6">
              <v-text-field
                v-model="form.max_hold_days"
                type="number"
                label="最大持仓天数"
              ></v-text-field>
            </v-col>
          </v-row>

          <v-divider class="my-4"></v-divider>

          <v-row>
            <v-col cols="12" md="6">
              <v-text-field
                v-model="form.buy_threshold"
                type="number"
                step="0.05"
                label="买入阈值"
                hint="评分高于此值买入"
                persistent-hint
              ></v-text-field>
            </v-col>
            <v-col cols="12" md="6">
              <v-text-field
                v-model="form.sell_threshold"
                type="number"
                step="0.05"
                label="卖出阈值"
                hint="评分低于此值卖出"
                persistent-hint
              ></v-text-field>
            </v-col>
          </v-row>
        </div>
      </v-card-text>
      <v-divider></v-divider>
      <v-card-actions class="bg-surface-light">
        <v-btn text="取消" variant="plain" @click="dialog = false"></v-btn>
        <v-spacer></v-spacer>
        <v-btn text="保存" @click="saveStrategy"></v-btn>
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
      <v-card-text>此操作不可撤销，确定要删除策略「{{ deletingItem?.name }}」吗？</v-card-text>
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
import { strategyConfigApi, type Strategy } from '@/api/strategyConfig'

const loading = ref(false)
const dialog = ref(false)
const deleteDialog = ref(false)
const strategies = ref<Strategy[]>([])
const editingId = ref<string | null>(null)
const deletingItem = ref<Strategy | null>(null)
const strategyTypes = ['single', 'multi']
const activeTab = ref('basic')

const form = ref({
  name: '',
  type: 'single',
  min_order_value: 5000,
  stop_loss_pct: -0.1,
  max_hold_days: 30,
  buy_threshold: 0.1,
  sell_threshold: -0.1,
  max_positions: 10,
  max_position_pct: 0.3,
  sell_rank_n: 15,
  hold_score_threshold: 0.05,
  use_momentum_boost: false,
  momentum_window: 8,
  max_momentum_bonus: 0.1,
  use_explosion_filter: false,
  explosion_price_threshold: 0.15,
  explosion_volume_ratio: 3.0,
  explosion_window: 5,
  use_trend_boost: false,
  trend_window: 5,
  trend_scale: 0.5,
  max_trend_boost: 0.05,
})

const headers = [
  { title: '名称', key: 'name' },
  { title: '类型', key: 'type' },
  { title: '最小订单', key: 'min_order_value' },
  { title: '止损比例', key: 'stop_loss_pct' },
  { title: '持仓天数', key: 'max_hold_days' },
  { title: '操作', key: 'actions', sortable: false, align: 'end' as const },
]

const loadStrategies = async () => {
  loading.value = true
  const res = await strategyConfigApi.list()
  strategies.value = res.data
  loading.value = false
}

const openDialog = (item?: Strategy) => {
  activeTab.value = 'basic'
  if (item) {
    editingId.value = item.id
    form.value = {
      name: item.name,
      type: item.type,
      min_order_value: item.min_order_value,
      stop_loss_pct: item.stop_loss_pct,
      max_hold_days: item.max_hold_days,
      buy_threshold: item.buy_threshold ?? 0.1,
      sell_threshold: item.sell_threshold ?? -0.1,
      max_positions: item.max_positions ?? 10,
      max_position_pct: item.max_position_pct ?? 0.3,
      sell_rank_n: item.sell_rank_n ?? 15,
      hold_score_threshold: item.hold_score_threshold ?? 0.05,
      use_momentum_boost: item.use_momentum_boost ?? false,
      momentum_window: item.momentum_window ?? 8,
      max_momentum_bonus: item.max_momentum_bonus ?? 0.1,
      use_explosion_filter: item.use_explosion_filter ?? false,
      explosion_price_threshold: item.explosion_price_threshold ?? 0.15,
      explosion_volume_ratio: item.explosion_volume_ratio ?? 3.0,
      explosion_window: item.explosion_window ?? 5,
      use_trend_boost: item.use_trend_boost ?? false,
      trend_window: item.trend_window ?? 5,
      trend_scale: item.trend_scale ?? 0.5,
      max_trend_boost: item.max_trend_boost ?? 0.05,
    }
  } else {
    editingId.value = null
    form.value = {
      name: 'default_strategy',
      type: 'single',
      min_order_value: 5000,
      stop_loss_pct: -0.1,
      max_hold_days: 30,
      buy_threshold: 0.1,
      sell_threshold: -0.1,
      max_positions: 10,
      max_position_pct: 0.3,
      sell_rank_n: 15,
      hold_score_threshold: 0.05,
    }
  }
  dialog.value = true
}

const saveStrategy = async () => {
  if (editingId.value) {
    await strategyConfigApi.update(editingId.value, {
      name: form.value.name,
      min_order_value: form.value.min_order_value,
      stop_loss_pct: form.value.stop_loss_pct,
      max_hold_days: form.value.max_hold_days,
      buy_threshold: form.value.buy_threshold,
      sell_threshold: form.value.sell_threshold,
      max_positions: form.value.type === 'multi' ? form.value.max_positions : undefined,
      max_position_pct: form.value.type === 'multi' ? form.value.max_position_pct : undefined,
      sell_rank_n: form.value.type === 'multi' ? form.value.sell_rank_n : undefined,
      hold_score_threshold: form.value.type === 'multi' ? form.value.hold_score_threshold : undefined,
      use_momentum_boost: form.value.type === 'multi' ? form.value.use_momentum_boost : undefined,
      momentum_window: form.value.type === 'multi' ? form.value.momentum_window : undefined,
      max_momentum_bonus: form.value.type === 'multi' ? form.value.max_momentum_bonus : undefined,
      use_explosion_filter: form.value.type === 'multi' ? form.value.use_explosion_filter : undefined,
      explosion_price_threshold: form.value.type === 'multi' ? form.value.explosion_price_threshold : undefined,
      explosion_volume_ratio: form.value.type === 'multi' ? form.value.explosion_volume_ratio : undefined,
      explosion_window: form.value.type === 'multi' ? form.value.explosion_window : undefined,
      use_trend_boost: form.value.type === 'multi' ? form.value.use_trend_boost : undefined,
      trend_window: form.value.type === 'multi' ? form.value.trend_window : undefined,
      trend_scale: form.value.type === 'multi' ? form.value.trend_scale : undefined,
      max_trend_boost: form.value.type === 'multi' ? form.value.max_trend_boost : undefined,
    })
  } else {
    await strategyConfigApi.create({
      name: form.value.name,
      type: form.value.type,
      min_order_value: form.value.min_order_value,
      stop_loss_pct: form.value.stop_loss_pct,
      max_hold_days: form.value.max_hold_days,
      buy_threshold: form.value.buy_threshold,
      sell_threshold: form.value.sell_threshold,
      max_positions: form.value.type === 'multi' ? form.value.max_positions : undefined,
      max_position_pct: form.value.type === 'multi' ? form.value.max_position_pct : undefined,
      sell_rank_n: form.value.type === 'multi' ? form.value.sell_rank_n : undefined,
      hold_score_threshold: form.value.type === 'multi' ? form.value.hold_score_threshold : undefined,
      use_momentum_boost: form.value.type === 'multi' ? form.value.use_momentum_boost : undefined,
      momentum_window: form.value.type === 'multi' ? form.value.momentum_window : undefined,
      max_momentum_bonus: form.value.type === 'multi' ? form.value.max_momentum_bonus : undefined,
      use_explosion_filter: form.value.type === 'multi' ? form.value.use_explosion_filter : undefined,
      explosion_price_threshold: form.value.type === 'multi' ? form.value.explosion_price_threshold : undefined,
      explosion_volume_ratio: form.value.type === 'multi' ? form.value.explosion_volume_ratio : undefined,
      explosion_window: form.value.type === 'multi' ? form.value.explosion_window : undefined,
      use_trend_boost: form.value.type === 'multi' ? form.value.use_trend_boost : undefined,
      trend_window: form.value.type === 'multi' ? form.value.trend_window : undefined,
      trend_scale: form.value.type === 'multi' ? form.value.trend_scale : undefined,
      max_trend_boost: form.value.type === 'multi' ? form.value.max_trend_boost : undefined,
    })
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
  await strategyConfigApi.delete(deletingItem.value.id)
  deleteDialog.value = false
  deletingItem.value = null
  await loadStrategies()
}

onMounted(() => {
  loadStrategies()
})
</script>
