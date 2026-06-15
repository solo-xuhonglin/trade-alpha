<template>
  <div v-if="strategy" class="mt-2 ml-1">
    <v-tooltip location="top" max-width="300">
      <template v-slot:activator="{ props }">
        <v-chip size="x-small" variant="tonal" color="info" class="mr-1 mb-1" v-bind="props"
          :prepend-icon="strategy.use_momentum_boost ? 'mdi-check' : 'mdi-close'">
          动量
        </v-chip>
      </template>
      <span v-if="strategy.use_momentum_boost">
        窗口{{ strategy.momentum_window ?? '-' }} 最大加成{{ ((strategy.max_momentum_bonus ?? 0) * 100).toFixed(0) }}%
      </span>
      <span v-else>未启用</span>
    </v-tooltip>
    <v-tooltip location="top" max-width="300">
      <template v-slot:activator="{ props }">
        <v-chip size="x-small" variant="tonal" color="info" class="mr-1 mb-1" v-bind="props"
          :prepend-icon="strategy.use_momentum_penalty ? 'mdi-check' : 'mdi-close'">
          动量扣分
        </v-chip>
      </template>
      <span v-if="strategy.use_momentum_penalty">
        窗口{{ strategy.momentum_window ?? '-' }} 最大扣分{{ ((strategy.max_momentum_bonus ?? 0) * 100).toFixed(0) }}%
      </span>
      <span v-else>未启用</span>
    </v-tooltip>
    <v-tooltip location="top" max-width="300">
      <template v-slot:activator="{ props }">
        <v-chip size="x-small" variant="tonal" color="info" class="mr-1 mb-1" v-bind="props"
          :prepend-icon="strategy.use_trend_bonus ? 'mdi-check' : 'mdi-close'">
          趋势加分
        </v-chip>
      </template>
      <span v-if="strategy.use_trend_bonus">
        窗口{{ strategy.trend_bonus_window ?? '-' }} 系数{{ strategy.trend_bonus_scale ?? '0.03' }} 上限{{ ((strategy.trend_max_bonus ?? 0) * 100).toFixed(0) }}%
      </span>
      <span v-else>未启用</span>
    </v-tooltip>
    <v-tooltip location="top" max-width="300">
      <template v-slot:activator="{ props }">
        <v-chip size="x-small" variant="tonal" color="info" class="mr-1 mb-1" v-bind="props"
          :prepend-icon="strategy.use_trend_penalty ? 'mdi-check' : 'mdi-close'">
          趋势扣分
        </v-chip>
      </template>
      <span v-if="strategy.use_trend_penalty">
        窗口{{ strategy.trend_bonus_window ?? '-' }} 系数{{ strategy.trend_bonus_scale ?? '0.03' }} 上限{{ ((strategy.trend_max_bonus ?? 0) * 100).toFixed(0) }}%
      </span>
      <span v-else>未启用</span>
    </v-tooltip>
    <v-tooltip location="top" max-width="300">
      <template v-slot:activator="{ props }">
        <v-chip size="x-small" variant="tonal" color="primary" class="mr-1 mb-1" v-bind="props">
          排名平滑
        </v-chip>
      </template>
      <span>窗口{{ strategy.ranking_smooth_window ?? '3' }} α{{ strategy.ranking_smooth_alpha ?? '0.5' }}</span>
    </v-tooltip>
    <v-tooltip location="top" max-width="300">
      <template v-slot:activator="{ props }">
        <v-chip size="x-small" variant="tonal" color="warning" class="mr-1 mb-1" v-bind="props"
          :prepend-icon="strategy.use_explosion_filter ? 'mdi-check' : 'mdi-close'">
          暴涨排除
        </v-chip>
      </template>
      <span v-if="strategy.use_explosion_filter">
        涨幅{{ ((strategy.explosion_price_threshold ?? 0) * 100).toFixed(0) }}% 量比{{ strategy.explosion_volume_ratio ?? '3.0' }}x
      </span>
      <span v-else>未启用</span>
    </v-tooltip>
    <v-tooltip location="top" max-width="300">
      <template v-slot:activator="{ props }">
        <v-chip size="x-small" variant="tonal" color="warning" class="mr-1 mb-1" v-bind="props"
          :prepend-icon="strategy.use_full_position_sell ? 'mdi-check' : 'mdi-close'">
          满仓卖出
        </v-chip>
      </template>
      <span v-if="strategy.use_full_position_sell">
        阈值{{ ((strategy.full_position_threshold ?? 0) * 100).toFixed(0) }}% 持续{{ strategy.full_position_days ?? '-' }}天
      </span>
      <span v-else>未启用</span>
    </v-tooltip>
    <v-tooltip location="top" max-width="300">
      <template v-slot:activator="{ props }">
        <v-chip size="x-small" variant="tonal" color="primary" class="mr-1 mb-1" v-bind="props"
          :prepend-icon="strategy.use_rank_up_priority ? 'mdi-check' : 'mdi-close'">
          排名上涨
        </v-chip>
      </template>
      <span v-if="strategy.use_rank_up_priority">
        窗口{{ strategy.rank_up_window ?? '-' }} 买入{{ strategy.rank_up_count ?? '-' }} 提升{{ ((strategy.rank_up_min_improvement_pct ?? 0) * 100).toFixed(0) }}%
      </span>
      <span v-else>未启用</span>
    </v-tooltip>
  </div>
</template>

<script setup lang="ts">
import type { Strategy } from '@/api/strategyConfig'

defineProps<{
  strategy: Strategy | null
}>()
</script>