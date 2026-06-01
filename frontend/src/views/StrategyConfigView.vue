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
          <v-tab value="trading">交易优化</v-tab>
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
                <v-chip size="x-small" variant="outlined" color="info">连续上涨天数加成</v-chip>
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

              <div class="d-flex align-center mb-2">
                <v-switch v-model="form.use_trend_bonus" hide-details density="compact" color="primary"
                  class="mr-2" label="趋势加分"></v-switch>
                <v-chip size="x-small" variant="outlined" color="info">R² 加权趋势，股价温和上涨加分</v-chip>
              </div>
              <v-row>
                <v-col cols="12" md="4">
                  <v-text-field v-model.number="form.trend_bonus_window" type="number"
                    label="窗口天数" hint="收盘价回归计算的天数" persistent-hint
                    :disabled="!form.use_trend_bonus"></v-text-field>
                </v-col>
                <v-col cols="12" md="4">
                  <v-text-field v-model.number="form.trend_bonus_scale" type="number" step="0.01"
                    label="斜率系数" hint="斜率 × 系数 = 趋势加分" persistent-hint
                    :disabled="!form.use_trend_bonus"></v-text-field>
                </v-col>
                <v-col cols="12" md="4">
                  <v-text-field v-model.number="form.trend_r2_threshold" type="number" step="0.05"
                    label="R² 阈值" hint="拟合优度门槛，低于此值不加分" persistent-hint
                    :disabled="!form.use_trend_bonus"></v-text-field>
                </v-col>
              </v-row>
              <v-row>
                <v-col cols="12" md="4">
                  <v-text-field v-model.number="form.trend_max_bonus" type="number" step="0.01"
                    label="最大加分" hint="趋势加分上限" persistent-hint
                    :disabled="!form.use_trend_bonus"></v-text-field>
                </v-col>
              </v-row>

              <v-divider class="my-4"></v-divider>

              <div class="d-flex align-center mb-2">
                <v-switch v-model="form.use_volatility_penalty" hide-details density="compact" color="primary"
                  class="mr-2" label="波动扣分"></v-switch>
                <v-chip size="x-small" variant="outlined" color="warning">日内振幅过大扣分</v-chip>
              </div>
              <v-row>
                <v-col cols="12" md="4">
                  <v-text-field v-model.number="form.vol_penalty_window" type="number"
                    label="窗口天数" hint="日内振幅计算的天数" persistent-hint
                    :disabled="!form.use_volatility_penalty"></v-text-field>
                </v-col>
                <v-col cols="12" md="4">
                  <v-text-field v-model.number="form.vol_range_tolerance" type="number" step="0.005"
                    label="振幅容忍度" hint="低于此振幅不扣分" persistent-hint
                    :disabled="!form.use_volatility_penalty"></v-text-field>
                </v-col>
                <v-col cols="12" md="4">
                  <v-text-field v-model.number="form.vol_penalty_scale" type="number" step="0.001"
                    label="扣分系数" hint="超出容忍度 × 系数 = 扣分" persistent-hint
                    :disabled="!form.use_volatility_penalty"></v-text-field>
                </v-col>
              </v-row>
              <v-row>
                <v-col cols="12" md="4">
                  <v-text-field v-model.number="form.vol_max_penalty" type="number" step="0.01"
                    label="最大扣分" hint="波动扣分上限" persistent-hint
                    :disabled="!form.use_volatility_penalty"></v-text-field>
                </v-col>
              </v-row>
            </div>
          </v-window-item>

          <v-window-item value="trading">
            <div>
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
                <v-switch v-model="form.use_full_position_sell" hide-details density="compact" color="primary"
                  class="mr-2" label="满仓容忍度"></v-switch>
                <v-chip size="x-small" variant="outlined" color="warning">仓位超阈值持续N日时卖出最差评分股</v-chip>
              </div>
              <v-row>
                <v-col cols="12" md="4">
                  <v-text-field v-model.number="form.full_position_threshold" type="number" step="0.05"
                    label="仓位阈值" hint="总资产比例，如0.90=90%" persistent-hint
                    :disabled="!form.use_full_position_sell"></v-text-field>
                </v-col>
                <v-col cols="12" md="4">
                  <v-text-field v-model.number="form.full_position_days" type="number"
                    label="持续天数" hint="连续超过阈值N天触发" persistent-hint
                    :disabled="!form.use_full_position_sell"></v-text-field>
                </v-col>
                <v-col cols="12" md="4">
                  <v-text-field v-model.number="form.full_position_score_window" type="number"
                    label="评分窗口" hint="计算平均评分的天数" persistent-hint
                    :disabled="!form.use_full_position_sell"></v-text-field>
                </v-col>
              </v-row>
              <v-row>
                <v-col cols="12" md="4">
                  <v-text-field v-model.number="form.full_position_sell_count" type="number"
                    label="每次卖出数量" hint="每次触发卖几只" persistent-hint
                    :disabled="!form.use_full_position_sell"></v-text-field>
                </v-col>
              </v-row>

              <v-divider class="my-4"></v-divider>

              <div class="d-flex align-center mb-2">
                <v-switch v-model="form.use_acceleration_filter" hide-details density="compact" color="primary"
                  class="mr-2" label="加速排除"></v-switch>
                <v-chip size="x-small" variant="outlined" color="warning">历史N天越涨越快时不买入</v-chip>
              </div>
              <v-row>
                <v-col cols="12" md="4">
                  <v-text-field v-model.number="form.acceleration_window" type="number"
                    label="检测窗口" hint="计算的天数" persistent-hint
                    :disabled="!form.use_acceleration_filter"></v-text-field>
                </v-col>
                <v-col cols="12" md="4">
                  <v-text-field v-model.number="form.acceleration_cum_return" type="number" step="0.05"
                    label="累计涨幅阈值" hint="窗口总涨幅超此值" persistent-hint
                    :disabled="!form.use_acceleration_filter"></v-text-field>
                </v-col>
                <v-col cols="12" md="4">
                  <v-text-field v-model.number="form.acceleration_up_ratio" type="number" step="0.05"
                    label="上涨天数占比" hint="上涨天数/总天数超过此值" persistent-hint
                    :disabled="!form.use_acceleration_filter"></v-text-field>
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
  use_trend_bonus: false,
  trend_bonus_window: 10,
  trend_bonus_scale: 0.03,
  trend_r2_threshold: 0.30,
  trend_max_bonus: 0.05,
  use_volatility_penalty: false,
  vol_penalty_window: 10,
  vol_range_tolerance: 0.035,
  vol_penalty_scale: 0.005,
  vol_max_penalty: 0.05,
  use_full_position_sell: false,
  full_position_threshold: 0.90,
  full_position_days: 3,
  full_position_score_window: 5,
  full_position_sell_count: 1,
  use_acceleration_filter: false,
  acceleration_window: 5,
  acceleration_cum_return: 0.15,
  acceleration_up_ratio: 0.80,
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
      use_trend_bonus: item.use_trend_bonus ?? false,
      trend_bonus_window: item.trend_bonus_window ?? 10,
      trend_bonus_scale: item.trend_bonus_scale ?? 0.03,
      trend_r2_threshold: item.trend_r2_threshold ?? 0.30,
      trend_max_bonus: item.trend_max_bonus ?? 0.05,
      use_volatility_penalty: item.use_volatility_penalty ?? false,
      vol_penalty_window: item.vol_penalty_window ?? 10,
      vol_range_tolerance: item.vol_range_tolerance ?? 0.035,
      vol_penalty_scale: item.vol_penalty_scale ?? 0.005,
      vol_max_penalty: item.vol_max_penalty ?? 0.05,
      use_full_position_sell: item.use_full_position_sell ?? false,
      full_position_threshold: item.full_position_threshold ?? 0.90,
      full_position_days: item.full_position_days ?? 3,
      full_position_score_window: item.full_position_score_window ?? 5,
      full_position_sell_count: item.full_position_sell_count ?? 1,
      use_acceleration_filter: item.use_acceleration_filter ?? false,
      acceleration_window: item.acceleration_window ?? 5,
      acceleration_cum_return: item.acceleration_cum_return ?? 0.15,
      acceleration_up_ratio: item.acceleration_up_ratio ?? 0.80,
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
      use_trend_bonus: form.value.type === 'multi' ? form.value.use_trend_bonus : undefined,
      trend_bonus_window: form.value.type === 'multi' ? form.value.trend_bonus_window : undefined,
      trend_bonus_scale: form.value.type === 'multi' ? form.value.trend_bonus_scale : undefined,
      trend_r2_threshold: form.value.type === 'multi' ? form.value.trend_r2_threshold : undefined,
      trend_max_bonus: form.value.type === 'multi' ? form.value.trend_max_bonus : undefined,
      use_volatility_penalty: form.value.type === 'multi' ? form.value.use_volatility_penalty : undefined,
      vol_penalty_window: form.value.type === 'multi' ? form.value.vol_penalty_window : undefined,
      vol_range_tolerance: form.value.type === 'multi' ? form.value.vol_range_tolerance : undefined,
      vol_penalty_scale: form.value.type === 'multi' ? form.value.vol_penalty_scale : undefined,
      vol_max_penalty: form.value.type === 'multi' ? form.value.vol_max_penalty : undefined,
      use_full_position_sell: form.value.type === 'multi' ? form.value.use_full_position_sell : undefined,
      full_position_threshold: form.value.type === 'multi' ? form.value.full_position_threshold : undefined,
      full_position_days: form.value.type === 'multi' ? form.value.full_position_days : undefined,
      full_position_score_window: form.value.type === 'multi' ? form.value.full_position_score_window : undefined,
      full_position_sell_count: form.value.type === 'multi' ? form.value.full_position_sell_count : undefined,
      use_acceleration_filter: form.value.type === 'multi' ? form.value.use_acceleration_filter : undefined,
      acceleration_window: form.value.type === 'multi' ? form.value.acceleration_window : undefined,
      acceleration_cum_return: form.value.type === 'multi' ? form.value.acceleration_cum_return : undefined,
      acceleration_up_ratio: form.value.type === 'multi' ? form.value.acceleration_up_ratio : undefined,
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
      use_full_position_sell: form.value.type === 'multi' ? form.value.use_full_position_sell : undefined,
      full_position_threshold: form.value.type === 'multi' ? form.value.full_position_threshold : undefined,
      full_position_days: form.value.type === 'multi' ? form.value.full_position_days : undefined,
      full_position_score_window: form.value.type === 'multi' ? form.value.full_position_score_window : undefined,
      full_position_sell_count: form.value.type === 'multi' ? form.value.full_position_sell_count : undefined,
      use_acceleration_filter: form.value.type === 'multi' ? form.value.use_acceleration_filter : undefined,
      acceleration_window: form.value.type === 'multi' ? form.value.acceleration_window : undefined,
      acceleration_cum_return: form.value.type === 'multi' ? form.value.acceleration_cum_return : undefined,
      acceleration_up_ratio: form.value.type === 'multi' ? form.value.acceleration_up_ratio : undefined,
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
