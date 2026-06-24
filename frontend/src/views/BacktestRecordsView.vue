<template>
  <v-card border rounded>
    <v-data-table-server
      :headers="historyHeaders"
      :items="backtests"
      :loading="loading"
      :items-length="totalItems"
      :items-per-page="pageSize"
      :page="page"
      @update:options="handleOptionsChange"
    >
      <template v-slot:top>
        <v-toolbar flat>
          <v-toolbar-title>
            <v-icon color="medium-emphasis" icon="mdi-chart-line" size="x-small" start></v-icon>
            回测记录
          </v-toolbar-title>
          <v-btn
            prepend-icon="mdi-refresh"
            rounded="lg"
            text="刷新"
            border
            @click="loadBacktests"
            :loading="loading"
          ></v-btn>
        </v-toolbar>
      </template>

      <template v-slot:item.total_return="{ item }">
        <span :class="item.total_return >= 0 ? 'text-success' : 'text-error'">
          {{ (item.total_return * 100).toFixed(2) }}%
        </span>
      </template>
      <template v-slot:item.ts_codes="{ item }">
        <span v-if="item.ts_codes && item.ts_codes.length === 1">{{ item.ts_codes[0].ts_name }}</span>
        <span v-else-if="item.ts_codes && item.ts_codes.length > 1">{{ item.ts_codes.length }} 只</span>
        <span v-else>{{ item.ts_name || item.stock_name || item.ts_code || '-' }}</span>
      </template>
      <template v-slot:item.excess_return="{ item }">
        <span :class="(item.excess_return || 0) >= 0 ? 'text-success' : 'text-error'">
          {{ ((item.excess_return || 0) * 100).toFixed(2) }}%
        </span>
      </template>
      <template v-slot:item.max_drawdown="{ item }">
        <span :class="item.max_drawdown < 0.1 ? 'text-warning' : 'text-error'">
          {{ (item.max_drawdown * 100).toFixed(2) }}%
        </span>
      </template>
      <template v-slot:item.sharpe_ratio="{ item }">
        <span :class="(item.sharpe_ratio || 0) >= 1 ? 'text-success' : (item.sharpe_ratio || 0) >= 0 ? 'text-warning' : 'text-error'">
          {{ (item.sharpe_ratio || 0).toFixed(2) }}
        </span>
      </template>
      <template v-slot:item.analysis_action="{ item }">
        <div class="d-flex ga-1">
          <v-btn size="small" variant="text" prepend-icon="mdi-chart-bar" @click="viewResult(item)">统计</v-btn>
          <v-btn size="small" variant="text" color="info" prepend-icon="mdi-chart-timeline-variant" @click="viewPredictions(item)">K线</v-btn>
          <v-btn size="small" variant="text" color="teal" prepend-icon="mdi-calendar-text" @click="viewDailyDetail(item)">每日</v-btn>
        </div>
      </template>
      <template v-slot:item.actions="{ item }">
        <v-btn size="small" variant="text" color="error" prepend-icon="mdi-delete" @click="confirmDelete(item)">删除</v-btn>
      </template>
      <template v-slot:item.config_action="{ item }">
        <v-btn size="small" variant="text" color="primary" prepend-icon="mdi-cog" @click="openBacktestConfig(item)">配置</v-btn>
      </template>
    </v-data-table-server>
  </v-card>

  <v-dialog v-model="resultDialog" max-width="1300px">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center text-h6 pa-4">
        <div class="d-flex align-center ga-2">
          <v-icon color="primary">mdi-chart-line</v-icon>
          回测结果
          <v-chip v-if="selectedResult" size="small" variant="outlined" class="ml-2">{{ selectedResult.name }}</v-chip>
        </div>
        <v-btn icon variant="text" size="small" @click="resultDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-divider />
      <v-card-text class="overflow-hidden" style="max-height: 90vh;">
        <div v-if="selectedResult">
          <v-tabs v-model="resultTab" color="primary">
            <v-tab value="overview">概览</v-tab>
            <v-tab value="market">市场分析</v-tab>
            <v-tab value="pnl">盈亏分析</v-tab>
            <v-tab value="trading">交易优化</v-tab>
          </v-tabs>

          <v-window v-model="resultTab" class="mt-4" style="max-height: calc(90vh - 160px); overflow-y: auto;">
            <v-window-item value="overview">
              <v-table density="compact" class="metrics-table">
                <thead>
                  <tr>
                    <th class="text-left" style="width: 160px;">指标</th>
                    <th class="text-center">策略</th>
                    <th class="text-center">基准</th>
                    <th class="text-center" style="width: 130px;">对比</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td class="text-body-2">总收益率</td>
                    <td class="text-center" :class="selectedResult.total_return >= 0 ? 'text-success' : 'text-error'">{{ (selectedResult.total_return * 100).toFixed(2) }}%</td>
                    <td class="text-center">{{ ((selectedResult.baseline_return || 0) * 100).toFixed(2) }}%</td>
                    <td class="text-center" :class="(selectedResult.excess_return || 0) >= 0 ? 'text-success' : 'text-error'">{{ ((selectedResult.excess_return || 0) * 100).toFixed(2) }}%</td>
                  </tr>
                  <tr>
                    <td class="text-body-2">年化收益</td>
                    <td class="text-center" :class="(selectedResult.annual_return || 0) >= 0 ? 'text-success' : 'text-error'">{{ ((selectedResult.annual_return || 0) * 100).toFixed(2) }}%</td>
                    <td class="text-center" :class="(selectedResult.baseline_annual_return || 0) >= 0 ? 'text-success' : 'text-error'">{{ ((selectedResult.baseline_annual_return || 0) * 100).toFixed(2) }}%</td>
                    <td class="text-center" :class="((selectedResult.annual_return || 0) - (selectedResult.baseline_annual_return || 0)) >= 0 ? 'text-success' : 'text-error'">{{ (((selectedResult.annual_return || 0) - (selectedResult.baseline_annual_return || 0)) * 100).toFixed(2) }}%</td>
                  </tr>
                  <tr>
                    <td class="text-body-2">最大回撤</td>
                    <td class="text-center" :class="selectedResult.max_drawdown < 0.1 ? 'text-warning' : 'text-error'">{{ (selectedResult.max_drawdown * 100).toFixed(2) }}%</td>
                    <td class="text-center" :class="(selectedResult.baseline_max_drawdown || 0) < 0.1 ? 'text-warning' : 'text-error'">{{ ((selectedResult.baseline_max_drawdown || 0) * 100).toFixed(2) }}%</td>
                    <td class="text-center" :class="selectedResult.max_drawdown <= (selectedResult.baseline_max_drawdown || 0) ? 'text-success' : 'text-error'">{{ ((selectedResult.max_drawdown - (selectedResult.baseline_max_drawdown || 0)) * 100).toFixed(2) }}%</td>
                  </tr>
                  <tr>
                    <td class="text-body-2">波动率</td>
                    <td class="text-center">{{ ((selectedResult.volatility || 0) * 100).toFixed(2) }}%</td>
                    <td class="text-center">{{ ((selectedResult.baseline_volatility || 0) * 100).toFixed(2) }}%</td>
                    <td class="text-center" :class="(selectedResult.volatility || 0) <= (selectedResult.baseline_volatility || 0) ? 'text-success' : 'text-warning'">{{ ((selectedResult.volatility || 0) - (selectedResult.baseline_volatility || 0) > 0 ? '+' : '') }}{{ (((selectedResult.volatility || 0) - (selectedResult.baseline_volatility || 0)) * 100).toFixed(2) }}%</td>
                  </tr>
                  <tr>
                    <td class="text-body-2">夏普比率</td>
                    <td class="text-center" :class="(selectedResult.sharpe_ratio || 0) >= 1 ? 'text-success' : (selectedResult.sharpe_ratio || 0) >= 0 ? 'text-warning' : 'text-error'">{{ (selectedResult.sharpe_ratio || 0).toFixed(2) }}</td>
                    <td class="text-center" :class="(selectedResult.baseline_sharpe_ratio || 0) >= 1 ? 'text-success' : (selectedResult.baseline_sharpe_ratio || 0) >= 0 ? 'text-warning' : 'text-error'">{{ (selectedResult.baseline_sharpe_ratio || 0).toFixed(2) }}</td>
                    <td class="text-center" :class="((selectedResult.sharpe_ratio || 0) - (selectedResult.baseline_sharpe_ratio || 0)) >= 0 ? 'text-success' : 'text-error'">{{ ((selectedResult.sharpe_ratio || 0) - (selectedResult.baseline_sharpe_ratio || 0) > 0 ? '+' : '') }}{{ ((selectedResult.sharpe_ratio || 0) - (selectedResult.baseline_sharpe_ratio || 0)).toFixed(2) }}</td>
                  </tr>
                  <tr>
                    <td class="text-body-2">胜率</td>
                    <td class="text-center" :class="(selectedResult.win_rate || 0) >= 0.5 ? 'text-success' : 'text-error'">{{ ((selectedResult.win_rate || 0) * 100).toFixed(1) }}%</td>
                    <td class="text-center">-</td>
                    <td class="text-center">-</td>
                  </tr>
                  <tr>
                    <td class="text-body-2">交易次数</td>
                    <td class="text-center">{{ selectedResult.total_trades }}</td>
                    <td class="text-center">-</td>
                    <td class="text-center">-</td>
                  </tr>
                  <tr>
                    <td class="text-body-2">平均持仓天数</td>
                    <td class="text-center">{{ selectedResult.avg_hold_days || 0 }}</td>
                    <td class="text-center">-</td>
                    <td class="text-center">-</td>
                  </tr>
                  <tr>
                    <td class="text-body-2">总手续费</td>
                    <td class="text-center">{{ (selectedResult.total_fees || 0).toFixed(2) }}</td>
                    <td class="text-center">-</td>
                    <td class="text-center">-</td>
                  </tr>
                </tbody>
              </v-table>
            </v-window-item>

          <v-window-item value="market">
              <div v-if="marketChartData.length > 0">
                <OverviewChart :data="marketChartData" :trend-threshold="marketTrendThreshold" />
              </div>
              <div v-else class="text-center text-medium-emphasis py-8">暂无市场数据</div>
            </v-window-item>

          <v-window-item value="pnl">
              <div v-if="pnlLoading" class="text-center text-medium-emphasis py-8">加载中...</div>
              <div v-else-if="!pnlSummary" class="text-center text-medium-emphasis py-8">暂无盈亏数据</div>
              <div v-else>
                <v-row>
                  <v-col cols="6" sm="3">
                    <v-card variant="tonal" :color="pnlSummary.total_portfolio_pnl >= 0 ? 'success' : 'error'">
                      <v-card-text class="text-center pa-2">
                        <div class="text-caption text-medium-emphasis">总盈亏（含浮盈）</div>
                        <div class="text-h6">¥{{ pnlSummary.total_portfolio_pnl.toFixed(2) }}</div>
                      </v-card-text>
                    </v-card>
                  </v-col>
                  <v-col cols="6" sm="3">
                    <v-card variant="tonal" :color="pnlSummary.total_realized_pnl >= 0 ? 'success' : 'error'">
                      <v-card-text class="text-center pa-2">
                        <div class="text-caption text-medium-emphasis">已实现盈亏</div>
                        <div class="text-h6">¥{{ pnlSummary.total_realized_pnl.toFixed(2) }}</div>
                      </v-card-text>
                    </v-card>
                  </v-col>
                  <v-col cols="6" sm="3">
                    <v-card variant="tonal" color="default">
                      <v-card-text class="text-center pa-2">
                        <div class="text-caption text-medium-emphasis">盈亏次数</div>
                        <div class="text-h6">{{ pnlSummary.total_profit_trades }}:{{ pnlSummary.total_loss_trades }}</div>
                      </v-card-text>
                    </v-card>
                  </v-col>
                  <v-col cols="6" sm="3">
                    <v-card variant="tonal" :color="pnlSummary.overall_win_rate >= 0.5 ? 'success' : 'error'">
                      <v-card-text class="text-center pa-2">
                        <div class="text-caption text-medium-emphasis">胜率</div>
                        <div class="text-h6">{{ (pnlSummary.overall_win_rate * 100).toFixed(1) }}%</div>
                      </v-card-text>
                    </v-card>
                  </v-col>
                </v-row>

                <v-row class="mt-2">
                  <v-col cols="12" md="6">
                    <div ref="amountChartRef" style="height: 300px;"></div>
                  </v-col>
                  <v-col cols="12" md="6">
                    <div ref="countChartRef" style="height: 300px;"></div>
                  </v-col>
                </v-row>

                <v-data-table
                  v-if="pnlDetails.length > 0"
                  v-model:sort-by="pnlSortBy"
                  :headers="pnlHeaders"
                  :items="pnlDetails"
                  density="compact"
                  hide-default-footer
                  items-per-page="-1"
                  class="mt-2"
                >
                  <template v-slot:item.realized_pnl="{ item }">
                    <span :class="item.realized_pnl >= 0 ? 'text-success' : 'text-error'">
                      ¥{{ item.realized_pnl.toFixed(2) }}
                    </span>
                  </template>
                  <template v-slot:item.unrealized_pnl="{ item }">
                    <span :class="item.unrealized_pnl >= 0 ? 'text-success' : 'text-error'">
                      ¥{{ item.unrealized_pnl.toFixed(2) }}
                    </span>
                  </template>
                  <template v-slot:item.total_pnl="{ item }">
                    <span :class="item.total_pnl >= 0 ? 'text-success' : 'text-error'">
                      ¥{{ item.total_pnl.toFixed(2) }}
                    </span>
                  </template>
                  <template v-slot:item.trade_win_rate="{ item }">
                    <span :class="item.trade_win_rate >= 0.5 ? 'text-success' : 'text-error'">
                      {{ (item.trade_win_rate * 100).toFixed(1) }}%
                    </span>
                  </template>
                </v-data-table>
              </div>
            </v-window-item>

          <v-window-item value="trading">
            <div v-if="tradingLoading" class="text-center text-medium-emphasis py-8">加载中...</div>
            <div v-else>
              <div class="text-subtitle-2 font-weight-medium mb-2">暴涨排除</div>
              <v-data-table v-if="excludedStocks.length > 0" :headers="excludedHeaders" :items="excludedStocks"
                density="compact" hide-default-footer items-per-page="-1" class="mb-4"
                @click:row="(_, { item }) => item._detail = !item._detail" style="cursor: pointer;">
                <template v-slot:item.excluded_dates="{ item }">
                  <div v-if="item._detail">
                    <div v-for="d in item.excluded_dates" :key="d.date" class="text-caption">
                      {{ d.date }} 涨 {{ (d.price_surge_pct * 100).toFixed(1) }}% 量比 {{ d.volume_ratio.toFixed(1) }}x
                      → 5d <span :style="{color: retColor(d.actual_return_5d)}">{{ d.actual_return_5d != null ? (d.actual_return_5d * 100).toFixed(1) + '%' : '-' }}</span>
                      10d <span :style="{color: retColor(d.actual_return_10d)}">{{ d.actual_return_10d != null ? (d.actual_return_10d * 100).toFixed(1) + '%' : '-' }}</span>
                      20d <span :style="{color: retColor(d.actual_return_20d)}">{{ d.actual_return_20d != null ? (d.actual_return_20d * 100).toFixed(1) + '%' : '-' }}</span>
                    </div>
                  </div>
                  <span v-else class="text-caption text-medium-emphasis">点击展开 ({{ item.excluded_count }} 次)</span>
                </template>
              </v-data-table>
              <div v-else class="text-caption text-medium-emphasis mb-4">无记录</div>

              <v-divider class="mb-3"></v-divider>

              <div class="text-subtitle-2 font-weight-medium mb-2">满仓强制卖出</div>
              <v-data-table v-if="forcedSellStocks.length > 0" :headers="forcedSellHeaders" :items="forcedSellStocks"
                density="compact" hide-default-footer items-per-page="-1"
                @click:row="(_, { item }) => item._detail = !item._detail" style="cursor: pointer;">
                <template v-slot:item.forced_dates="{ item }">
                  <div v-if="item._detail">
                    <div v-for="d in item.forced_dates" :key="d.date" class="text-caption">
                      {{ d.date }} - {{ d.reason }}
                      → 5d <span :style="{color: retColor(d.actual_return_5d)}">{{ d.actual_return_5d != null ? (d.actual_return_5d * 100).toFixed(1) + '%' : '-' }}</span>
                      10d <span :style="{color: retColor(d.actual_return_10d)}">{{ d.actual_return_10d != null ? (d.actual_return_10d * 100).toFixed(1) + '%' : '-' }}</span>
                      20d <span :style="{color: retColor(d.actual_return_20d)}">{{ d.actual_return_20d != null ? (d.actual_return_20d * 100).toFixed(1) + '%' : '-' }}</span>
                    </div>
                  </div>
                  <span v-else class="text-caption text-medium-emphasis">点击展开 ({{ item.forced_count }} 次)</span>
                </template>
              </v-data-table>
              <div v-else class="text-caption text-medium-emphasis">无记录</div>
            </div>
          </v-window-item>
          </v-window>
        </div>
      </v-card-text>
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
      <v-card-text>此操作不可撤销，确定要删除回测记录「{{ deletingItem?.id }}」吗？</v-card-text>
      <v-divider></v-divider>
      <v-card-actions class="bg-surface-light">
        <v-btn text="取消" variant="plain" @click="deleteDialog = false"></v-btn>
        <v-spacer></v-spacer>
        <v-btn text="删除" color="error" @click="deleteBacktest" :loading="loadingDelete"></v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="dailyDetailDialog" max-width="1200px" scrollable>
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center pa-4">
        <div class="d-flex align-center ga-2">
          <v-icon color="teal">mdi-calendar-text</v-icon>
          每日详情
          <v-chip v-if="selectedResult" size="small" variant="outlined" class="ml-2">{{ selectedResult.name }}</v-chip>
          <v-select
            v-if="monthOptions.length > 0"
            v-model="selectedMonth"
            :items="monthOptions"
            variant="outlined"
            density="compact"
            hide-details
            class="ml-4"
            style="width: 140px;"
            @update:model-value="onMonthChange"
          />
        </div>
        <v-btn icon variant="text" size="small" @click="dailyDetailDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-divider />
      <v-card-text v-if="loadingDaily" class="text-center text-medium-emphasis py-8">
        <v-progress-circular indeterminate size="24" class="mr-2" />加载中...
      </v-card-text>
      <v-card-text v-else-if="dailyDetails.length === 0" class="text-center text-medium-emphasis py-8">
        暂无每日数据
      </v-card-text>
      <v-card-text v-else class="pa-2 py-0">
        <v-row v-for="d in paginatedItems" :key="d.date" no-gutters>
          <v-col cols="12">
            <v-card elevation="0" class="daily-card" @click="toggleExpand(d.date)" style="cursor: pointer;">
              <v-card-text class="pa-3">
                <v-row align="center" no-gutters style="white-space: nowrap;">
                  <v-col cols="2" class="text-body-2 font-weight-medium d-flex align-center">
                    {{ d.date }}
                    <v-icon class="ml-auto" size="small">{{ expandedDates.has(d.date) ? 'mdi-chevron-up' : 'mdi-chevron-down' }}</v-icon>
                  </v-col>
                  <v-col cols="1" class="text-caption">现金 ¥{{ d.cash.toFixed(0) }}</v-col>
                  <v-col cols="1" class="text-caption">市值 ¥{{ d.total_market_value.toFixed(0) }}</v-col>
                  <v-col cols="2" class="text-caption">总资产 ¥{{ d.total_value.toFixed(0) }}</v-col>
                  <v-col cols="2" :class="d.cml_return >= 0 ? 'text-success' : 'text-error'" class="text-caption font-weight-medium">
                    策略 {{ (d.cml_return * 100).toFixed(2) }}%
                  </v-col>
                  <v-col cols="2" class="text-caption text-medium-emphasis">
                    基准 {{ (d.baseline_cml_return * 100).toFixed(2) }}%
                  </v-col>
                  <v-col cols="1" class="text-caption">持仓 {{ d.positions.length }} 只</v-col>
                  <v-col cols="1" :class="d.day_return >= 0 ? 'text-success' : 'text-error'" class="text-caption">
                    日收益 {{ (d.day_return * 100).toFixed(2) }}%
                  </v-col>
                </v-row>
              </v-card-text>

              <div v-show="expandedDates.has(d.date)">
                  <v-divider />
                  <v-card-text class="pa-3">
                    <!-- 成交记录区域 -->
                    <div class="text-subtitle-2 text-medium-emphasis mb-2">
                      <v-icon size="small" class="mr-1">mdi-swap-horizontal-bold</v-icon>当日成交
                    </div>
                    <v-data-table
                      v-if="d.trades.length > 0"
                      :headers="dailyTradeHeaders"
                      :items="d.trades"
                      density="compact"
                      hide-default-footer
                      items-per-page="-1"
                      class="mb-4"
                    >
                      <template v-slot:item.action="{ item }">
                        <v-chip :color="item.action === 'buy' ? 'success' : 'error'" size="x-small">
                          {{ item.action === 'buy' ? '买入' : '卖出' }}
                        </v-chip>
                      </template>
                      <template v-slot:item.reason="{ item }">
                        <v-chip v-if="item.reason" :color="reasonColor(item.reason)" size="x-small" variant="flat">
                          {{ reasonLabel(item.reason) }}
                        </v-chip>
                        <span v-else class="text-caption text-disabled">-</span>
                      </template>
                      <template v-slot:item.pnl_amount="{ item }">
                        <span v-if="item.pnl_amount != null" :class="item.pnl_amount >= 0 ? 'text-success' : 'text-error'">
                          ¥{{ item.pnl_amount.toFixed(2) }}
                        </span>
                        <span v-else class="text-disabled">-</span>
                      </template>
                    </v-data-table>
                    <div v-else class="text-caption text-medium-emphasis mb-4">无成交记录</div>

                    <!-- 持仓明细区域 -->
                    <div class="text-subtitle-2 text-medium-emphasis mb-2">
                      <v-icon size="small" class="mr-1">mdi-briefcase</v-icon>持仓明细
                    </div>
                    <v-data-table
                      v-if="d.positions.length > 0"
                      :headers="dailyPositionHeaders"
                      :items="d.positions"
                      density="compact"
                      hide-default-footer
                      items-per-page="-1"
                    >
                      <template v-slot:item.unrealized_pnl="{ item }">
                        <span :class="item.unrealized_pnl >= 0 ? 'text-success' : 'text-error'">
                          ¥{{ item.unrealized_pnl.toFixed(2) }}
                        </span>
                      </template>
                      <template v-slot:item.unrealized_pnl_pct="{ item }">
                        <span :class="item.unrealized_pnl_pct >= 0 ? 'text-success' : 'text-error'">
                          {{ (item.unrealized_pnl_pct * 100).toFixed(2) }}%
                        </span>
                      </template>
                      <template v-slot:item.entry_score="{ item }">
                        {{ item.entry_score.toFixed(3) }}
                      </template>
                    </v-data-table>
                    <div v-else class="text-caption text-medium-emphasis">空仓</div>
                  </v-card-text>
                </div>
            </v-card>
          </v-col>
        </v-row>
      </v-card-text>
      <v-divider />
      <v-card-actions class="bg-surface-light d-flex align-center pa-2">
        <v-pagination
          v-if="totalPages > 1"
          v-model="dailyPage"
          :length="totalPages"
          :total-visible="7"
          size="small"
          class="mx-auto"
        />
        <v-spacer />
        <v-btn text="关闭" variant="plain" @click="dailyDetailDialog = false" />
      </v-card-actions>
    </v-card>
  </v-dialog>

  <PredictionChart v-model="predictionDialog" :backtest-id="predictionBacktestId" />

  <v-dialog v-model="backtestConfigDialog" max-width="800" scrollable>
    <v-card>
      <v-toolbar flat>
        <v-toolbar-title>
          <v-icon start>mdi-cog</v-icon>
          回测配置
          <v-chip v-if="backtestConfigItem" size="small" variant="outlined" class="ml-2">{{ backtestConfigItem.name }}</v-chip>
        </v-toolbar-title>
        <v-spacer />
        <v-btn size="small" variant="tonal" prepend-icon="mdi-compare" class="mr-1"
          @click="loadAccountConfigs()">对比账户</v-btn>
        <v-btn size="small" variant="tonal" prepend-icon="mdi-compare" class="mr-1"
          @click="loadStrategyConfigs()">对比策略</v-btn>
        <v-btn size="small" variant="tonal" prepend-icon="mdi-compare" class="mr-1"
          @click="loadModelConfigs()">对比模型</v-btn>
        <v-btn icon variant="text" @click="backtestConfigDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-toolbar>
      <v-tabs v-model="backtestConfigTab" bg-color="surface">
        <v-tab value="account">账户配置</v-tab>
        <v-tab value="strategy">策略配置</v-tab>
        <v-tab value="model">模型配置</v-tab>
        <v-tab value="features">特征配置</v-tab>
      </v-tabs>
      <v-divider />
      <v-card-text>
        <v-progress-linear v-if="backtestConfigLoading" indeterminate class="mb-4" />
        <v-window v-model="backtestConfigTab">
          <v-window-item value="account">
            <div class="text-subtitle-2 font-weight-medium mb-1">账户信息</div>
            <v-row class="py-0">
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">名称：</span>{{ backtestAccountConfig?.name || '-' }}</v-col>
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">初始资金：</span>¥{{ backtestAccountConfig?.initial_capital?.toLocaleString() || '-' }}</v-col>
            </v-row>

            <v-divider class="my-2" />
            <div class="text-subtitle-2 font-weight-medium mb-1">费率</div>
            <v-row class="py-0">
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">买入费率：</span>{{ backtestAccountConfig?.buy_fee_rate ? (backtestAccountConfig.buy_fee_rate * 100).toFixed(3) + '%' : '-' }}</v-col>
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">卖出费率：</span>{{ backtestAccountConfig?.sell_fee_rate ? (backtestAccountConfig.sell_fee_rate * 100).toFixed(3) + '%' : '-' }}</v-col>
            </v-row>
            <v-row class="py-0">
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">印花税率：</span>{{ backtestAccountConfig?.stamp_tax_rate ? (backtestAccountConfig.stamp_tax_rate * 100).toFixed(2) + '%' : '-' }}</v-col>
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">最低手续费：</span>¥{{ backtestAccountConfig?.min_fee ?? '-' }}</v-col>
            </v-row>

          </v-window-item>

          <v-window-item value="strategy">
            <div class="text-subtitle-2 font-weight-medium mb-1">策略信息</div>
            <v-row class="py-0">
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">名称：</span>{{ backtestStrategyConfig?.name || '-' }}</v-col>
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">类型：</span>{{ backtestStrategyConfig?.type || '-' }}</v-col>
            </v-row>

            <v-divider class="my-2" />
            <div class="text-subtitle-2 font-weight-medium mb-1">交易规则</div>
            <v-row class="py-0">
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">买入阈值：</span>{{ backtestStrategyConfig?.buy_threshold ?? '-' }}</v-col>
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">卖出阈值：</span>{{ backtestStrategyConfig?.sell_threshold ?? '-' }}</v-col>
            </v-row>
            <v-row class="py-0">
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">止损比例：</span>{{ backtestStrategyConfig?.stop_loss_pct ? (backtestStrategyConfig.stop_loss_pct * 100).toFixed(0) + '%' : '-' }}</v-col>
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">ATR止损乘数：</span>{{ backtestStrategyConfig?.atr_stop_multiplier ?? '3.0' }}</v-col>
            </v-row>
            <v-row class="py-0">
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">ATR上移比例：</span>{{ backtestStrategyConfig?.atr_trail_rate ?? '0.5' }}</v-col>
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">最大持仓天数：</span>{{ backtestStrategyConfig?.max_hold_days ?? '-' }}</v-col>
            </v-row>
            <v-row class="py-0">
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">每日最多买入：</span>{{ backtestStrategyConfig?.max_daily_buys ?? '2' }}</v-col>
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">最低持有天数：</span>{{ backtestStrategyConfig?.min_hold_days ?? '-' }}</v-col>
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">最小交易金额：</span>{{ backtestStrategyConfig?.min_order_value ?? '-' }}</v-col>
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">持仓评分阈值：</span>{{ backtestStrategyConfig?.hold_score_threshold ?? '-' }}</v-col>
            </v-row>
            <v-row class="py-0">
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">最大持仓数：</span>{{ backtestStrategyConfig?.max_positions ?? '-' }}</v-col>
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">单只持仓上限：</span>{{ backtestStrategyConfig?.max_position_pct ? (backtestStrategyConfig.max_position_pct * 100).toFixed(0) + '%' : '-' }}</v-col>
            </v-row>
            <v-row class="py-0">
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">卖出排名 N：</span>{{ backtestStrategyConfig?.sell_rank_n ?? '-' }}</v-col>
              <v-col cols="6"></v-col>
            </v-row>

            <v-divider class="my-2" />
            <div class="text-subtitle-2 font-weight-medium mb-1">排名优化</div>
            <v-row class="py-0">
              <v-col cols="12">
                <span class="text-body-2 text-medium-emphasis">动量加成：</span>
                <v-icon :color="backtestStrategyConfig?.use_momentum_boost ? 'success' : 'disabled'" size="small">
                  {{ backtestStrategyConfig?.use_momentum_boost ? 'mdi-check-circle' : 'mdi-close-circle' }}
                </v-icon>
                <span v-if="backtestStrategyConfig?.use_momentum_boost" class="text-body-2">
                  &nbsp;窗口{{ backtestStrategyConfig?.momentum_window ?? '-' }} 权重 0.3 上限{{ ((backtestStrategyConfig?.max_momentum_bonus ?? 0) * 100).toFixed(0) }}%
                </span>
              </v-col>
            </v-row>
            <v-row class="py-0">
              <v-col cols="12">
                <span class="text-body-2 text-medium-emphasis">趋势加分：</span>
                <v-icon :color="backtestStrategyConfig?.use_trend_bonus ? 'success' : 'disabled'" size="small">
                  {{ backtestStrategyConfig?.use_trend_bonus ? 'mdi-check-circle' : 'mdi-close-circle' }}
                </v-icon>
                <span v-if="backtestStrategyConfig?.use_trend_bonus" class="text-body-2">
                  &nbsp;窗口{{ backtestStrategyConfig?.trend_bonus_window ?? '-' }} 斜率{{ backtestStrategyConfig?.trend_bonus_scale ?? '0.03' }} R²阈值{{ ((backtestStrategyConfig?.trend_r2_threshold ?? 0) * 100).toFixed(0) }}% 上限{{ ((backtestStrategyConfig?.trend_max_bonus ?? 0) * 100).toFixed(0) }}%
                </span>
              </v-col>
            </v-row>
            <v-row class="py-0">
              <v-col cols="12">
                <span class="text-body-2 text-medium-emphasis">动量扣分：</span>
                <v-icon :color="backtestStrategyConfig?.use_momentum_penalty ? 'success' : 'disabled'" size="small">
                  {{ backtestStrategyConfig?.use_momentum_penalty ? 'mdi-check-circle' : 'mdi-close-circle' }}
                </v-icon>
                <span v-if="backtestStrategyConfig?.use_momentum_penalty" class="text-body-2">
                  &nbsp;窗口{{ backtestStrategyConfig?.momentum_window ?? '-' }} 最大扣分{{ ((backtestStrategyConfig?.max_momentum_bonus ?? 0) * 100).toFixed(0) }}%
                </span>
              </v-col>
            </v-row>
            <v-row class="py-0">
              <v-col cols="12">
                <span class="text-body-2 text-medium-emphasis">趋势扣分：</span>
                <v-icon :color="backtestStrategyConfig?.use_trend_penalty ? 'success' : 'disabled'" size="small">
                  {{ backtestStrategyConfig?.use_trend_penalty ? 'mdi-check-circle' : 'mdi-close-circle' }}
                </v-icon>
                <span v-if="backtestStrategyConfig?.use_trend_penalty" class="text-body-2">
                  &nbsp;窗口{{ backtestStrategyConfig?.trend_bonus_window ?? '-' }} 斜率{{ backtestStrategyConfig?.trend_bonus_scale ?? '0.03' }} R²阈值{{ ((backtestStrategyConfig?.trend_r2_threshold ?? 0) * 100).toFixed(0) }}% 上限{{ ((backtestStrategyConfig?.trend_max_bonus ?? 0) * 100).toFixed(0) }}%
                </span>
              </v-col>
            </v-row>
            <v-row class="py-0">
              <v-col cols="12">
                <span class="text-body-2 text-medium-emphasis">排名平滑：</span>
                <span class="text-body-2">
                  窗口{{ backtestStrategyConfig?.ranking_smooth_window ?? '3' }}
                  α{{ backtestStrategyConfig?.ranking_smooth_alpha ?? '0.5' }}
                </span>
              </v-col>
            </v-row>

            <v-divider class="my-2" />
            <div class="text-subtitle-2 font-weight-medium mb-1">交易优化</div>
            <v-row class="py-0">
              <v-col cols="12">
                <span class="text-body-2 text-medium-emphasis">暴涨排除：</span>
                <v-icon :color="backtestStrategyConfig?.use_explosion_filter ? 'success' : 'disabled'" size="small">
                  {{ backtestStrategyConfig?.use_explosion_filter ? 'mdi-check-circle' : 'mdi-close-circle' }}
                </v-icon>
                <span v-if="backtestStrategyConfig?.use_explosion_filter" class="text-body-2">
                  &nbsp;涨幅{{ ((backtestStrategyConfig?.explosion_price_threshold ?? 0) * 100).toFixed(0) }}% 量比{{ backtestStrategyConfig?.explosion_volume_ratio ?? '3.0' }}x 窗口{{ backtestStrategyConfig?.explosion_window ?? '5' }}
                </span>
              </v-col>
            </v-row>
            <v-row class="py-0">
              <v-col cols="12">
                <span class="text-body-2 text-medium-emphasis">满仓容忍卖出：</span>
                <v-icon :color="backtestStrategyConfig?.use_full_position_sell ? 'success' : 'disabled'" size="small">
                  {{ backtestStrategyConfig?.use_full_position_sell ? 'mdi-check-circle' : 'mdi-close-circle' }}
                </v-icon>
                <span v-if="backtestStrategyConfig?.use_full_position_sell" class="text-body-2">
                  &nbsp;阈值{{ ((backtestStrategyConfig?.full_position_threshold ?? 0) * 100).toFixed(0) }}% 连续{{ backtestStrategyConfig?.full_position_days ?? '-' }}天 每次卖出{{ backtestStrategyConfig?.full_position_sell_count ?? '1' }}只
                </span>
              </v-col>
            </v-row>
            <v-row class="py-0">
              <v-col cols="12">
                <span class="text-body-2 text-medium-emphasis">排名上涨优先：</span>
                <v-icon :color="backtestStrategyConfig?.use_rank_up_priority ? 'success' : 'disabled'" size="small">
                  {{ backtestStrategyConfig?.use_rank_up_priority ? 'mdi-check-circle' : 'mdi-close-circle' }}
                </v-icon>
                <span v-if="backtestStrategyConfig?.use_rank_up_priority" class="text-body-2">
                  &nbsp;窗口{{ backtestStrategyConfig?.rank_up_window ?? '-' }} 买入{{ backtestStrategyConfig?.rank_up_count ?? '-' }} 提升{{ ((backtestStrategyConfig?.rank_up_min_improvement_pct ?? 0) * 100).toFixed(0) }}%
                </span>
              </v-col>
            </v-row>

            <v-divider class="my-2" />
            <div class="text-subtitle-2 font-weight-medium mb-1">市场分析</div>
            <v-row class="py-0">
              <v-col cols="12">
                <span class="text-body-2 text-medium-emphasis">启用市场阶段策略：</span>
                <v-icon :color="backtestStrategyConfig?.use_phase_strategy ? 'success' : 'disabled'" size="small">
                  {{ backtestStrategyConfig?.use_phase_strategy ? 'mdi-check-circle' : 'mdi-close-circle' }}
                </v-icon>
                <span v-if="backtestStrategyConfig?.use_phase_strategy" class="text-body-2">
                  &nbsp;急跌空仓 / 企稳低阈值建仓
                </span>
              </v-col>
            </v-row>

            <v-divider class="my-2" />
            <div class="text-subtitle-2 font-weight-medium mb-1">轮动参数（横盘/下跌买入）</div>
            <v-row class="py-0">
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">历史最高排名：</span>{{ backtestStrategyConfig?.rotation_was_top_n ?? '15' }}</v-col>
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">历史检测窗口：</span>{{ backtestStrategyConfig?.rotation_was_top_window ?? '30' }}天</v-col>
            </v-row>
            <v-row class="py-0">
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">回调最低排名：</span>{{ backtestStrategyConfig?.rotation_bottom_threshold ?? '60' }}</v-col>
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">回调检测窗口：</span>{{ backtestStrategyConfig?.rotation_pullback_window ?? '5' }}天</v-col>
            </v-row>
            <v-row class="py-0">
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">排名上限：</span>{{ backtestStrategyConfig?.rotation_rank_min ?? '45' }}</v-col>
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">排名下限：</span>{{ backtestStrategyConfig?.rotation_rank_max ?? '75' }}</v-col>
            </v-row>
            <v-row class="py-0">
              <v-col cols="12">
                <span class="text-body-2 text-medium-emphasis">反转确认：</span>
                <v-icon :color="backtestStrategyConfig?.rotation_use_reversal_check ? 'success' : 'disabled'" size="small">
                  {{ backtestStrategyConfig?.rotation_use_reversal_check ? 'mdi-check-circle' : 'mdi-close-circle' }}
                </v-icon>
              </v-col>
            </v-row>
          </v-window-item>

          <v-window-item value="model">
            <div class="text-subtitle-2 font-weight-medium mb-1">基本信息</div>
            <v-row class="py-0">
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">名称：</span>{{ backtestModelConfig?.name || '-' }}</v-col>
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">模型类型：</span>{{ backtestModelConfig?.model_type || '-' }}</v-col>
            </v-row>

            <v-divider class="my-2" />
            <div class="text-subtitle-2 font-weight-medium mb-1">训练参数</div>
            <v-row class="py-0">
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">分类周期：</span>{{ backtestModelConfig?.classification_horizons?.join(', ') || '-' }}</v-col>
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">标签模式：</span>{{ backtestModelConfig?.label_mode || '-' }}</v-col>
            </v-row>
            <v-row class="py-0">
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">验证集比例：</span>{{ backtestModelConfig?.val_size ?? '-' }}</v-col>
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">阈值 3d：</span>{{ backtestModelConfig?.classification_threshold_3d ?? '-' }}</v-col>
            </v-row>
            <v-row class="py-0">
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">阈值 5d：</span>{{ backtestModelConfig?.classification_threshold_5d ?? '-' }}</v-col>
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">阈值 10d：</span>{{ backtestModelConfig?.classification_threshold_10d ?? '-' }}</v-col>
            </v-row>

            <template v-if="backtestModelConfig?.model_type === 'xgboost'">
              <v-divider class="my-2" />
              <div class="text-subtitle-2 font-weight-medium mb-1">XGB 参数</div>
              <v-row class="py-0">
                <v-col cols="6"><span class="text-body-2 text-medium-emphasis">Learning Rate：</span>{{ backtestModelConfig?.xgb_learning_rate ?? '-' }}</v-col>
                <v-col cols="6"><span class="text-body-2 text-medium-emphasis">Max Depth：</span>{{ backtestModelConfig?.xgb_max_depth ?? '-' }}</v-col>
              </v-row>
              <v-row class="py-0">
                <v-col cols="6"><span class="text-body-2 text-medium-emphasis">Subsample：</span>{{ backtestModelConfig?.xgb_subsample ?? '-' }}</v-col>
                <v-col cols="6"><span class="text-body-2 text-medium-emphasis">Colsample By Tree：</span>{{ backtestModelConfig?.xgb_colsample_bytree ?? '-' }}</v-col>
              </v-row>
              <v-row class="py-0">
                <v-col cols="6"><span class="text-body-2 text-medium-emphasis">Min Child Weight：</span>{{ backtestModelConfig?.xgb_min_child_weight ?? '-' }}</v-col>
                <v-col cols="6"><span class="text-body-2 text-medium-emphasis">N Estimators：</span>{{ backtestModelConfig?.xgb_n_estimators ?? '-' }}</v-col>
              </v-row>
            </template>

            <template v-if="backtestModelConfig?.model_type === 'lstm'">
              <v-divider class="my-2" />
              <div class="text-subtitle-2 font-weight-medium mb-1">LSTM 参数</div>
              <v-row class="py-0">
                <v-col cols="6"><span class="text-body-2 text-medium-emphasis">Hidden Size：</span>{{ backtestModelConfig?.lstm_hidden_size ?? '-' }}</v-col>
                <v-col cols="6"><span class="text-body-2 text-medium-emphasis">Num Layers：</span>{{ backtestModelConfig?.lstm_num_layers ?? '-' }}</v-col>
              </v-row>
              <v-row class="py-0">
                <v-col cols="6"><span class="text-body-2 text-medium-emphasis">Dropout：</span>{{ backtestModelConfig?.lstm_dropout ?? '-' }}</v-col>
                <v-col cols="6"><span class="text-body-2 text-medium-emphasis">Epochs：</span>{{ backtestModelConfig?.lstm_epochs ?? '-' }}</v-col>
              </v-row>
              <v-row class="py-0">
                <v-col cols="6"><span class="text-body-2 text-medium-emphasis">Batch Size：</span>{{ backtestModelConfig?.lstm_batch_size ?? '-' }}</v-col>
                <v-col cols="6"><span class="text-body-2 text-medium-emphasis">Learning Rate：</span>{{ backtestModelConfig?.lstm_learning_rate ?? '-' }}</v-col>
              </v-row>
              <v-row class="py-0">
                <v-col cols="6"><span class="text-body-2 text-medium-emphasis">Sequence Length：</span>{{ backtestModelConfig?.lstm_sequence_length ?? '-' }}</v-col>
                <v-col cols="6"><span class="text-body-2 text-medium-emphasis">Norm Window：</span>{{ backtestModelConfig?.lstm_normalization_window ?? '-' }}</v-col>
              </v-row>
              <v-row class="py-0">
                <v-col cols="6"><span class="text-body-2 text-medium-emphasis">Weight Decay：</span>{{ backtestModelConfig?.lstm_weight_decay ?? '-' }}</v-col>
                <v-col cols="6"></v-col>
              </v-row>
            </template>
          </v-window-item>

          <v-window-item value="features">
            <div class="text-subtitle-2 font-weight-medium mb-2">特征字段 <v-chip size="x-small" class="ml-1">{{ backtestModelConfig?.feature_fields?.length || 0 }} 个</v-chip></div>
            <template v-if="backtestModelConfig?.feature_fields?.length">
              <div class="text-caption text-medium-emphasis mb-1">日线基础字段</div>
              <div class="d-flex flex-wrap ga-1 mb-3">
                <v-chip v-for="f in backtestModelConfig.feature_fields.filter(isBasicField)" :key="f" size="x-small" variant="flat" color="indigo">{{ f }}</v-chip>
                <span v-if="!backtestModelConfig.feature_fields.filter(isBasicField).length" class="text-caption text-disabled">无</span>
              </div>
              <div class="text-caption text-medium-emphasis mb-1">技术指标字段</div>
              <div class="d-flex flex-wrap ga-1">
                <v-chip v-for="f in backtestModelConfig.feature_fields.filter(f => !isBasicField(f))" :key="f" size="x-small" variant="flat" color="teal">{{ f }}</v-chip>
                <span v-if="!backtestModelConfig.feature_fields.filter(f => !isBasicField(f)).length" class="text-caption text-disabled">无</span>
              </div>
            </template>
            <div v-else class="text-caption text-disabled">无特征字段配置</div>

            <v-divider class="my-3" />
            <div class="text-subtitle-2 font-weight-medium mb-2">标准化字段 <v-chip size="x-small" class="ml-1">{{ backtestModelConfig?.standardize_fields?.length || 0 }} 个</v-chip></div>
            <template v-if="backtestModelConfig?.standardize_fields?.length">
              <div class="d-flex flex-wrap ga-1">
                <v-chip v-for="f in backtestModelConfig.standardize_fields" :key="f" size="x-small" variant="flat" color="orange">{{ f }}</v-chip>
              </div>
            </template>
            <div v-else class="text-caption text-disabled">无配置</div>

            <v-divider class="my-3" />
            <div class="text-subtitle-2 font-weight-medium mb-2">去极值字段 <v-chip size="x-small" class="ml-1">{{ backtestModelConfig?.winsorize_fields?.length || 0 }} 个</v-chip></div>
            <template v-if="backtestModelConfig?.winsorize_fields?.length">
              <div class="d-flex flex-wrap ga-1">
                <v-chip v-for="f in backtestModelConfig.winsorize_fields" :key="f" size="x-small" variant="flat" color="deep-purple">{{ f }}</v-chip>
              </div>
            </template>
            <div v-else class="text-caption text-disabled">无配置</div>
          </v-window-item>
        </v-window>
      </v-card-text>
    </v-card>
  </v-dialog>

  <!-- Account Config Compare Picker -->
  <v-dialog v-model="accountCompareDialog" max-width="500px">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center pa-4">
        选择对比账户配置
        <v-btn icon variant="text" size="small" @click="accountCompareDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>
        <v-select
          v-model="selectedAccountForCompare"
          :items="accountConfigList"
          item-title="name"
          item-value="id"
          label="账户配置"
          return-object
          clearable
        />
      </v-card-text>
      <v-card-actions class="pa-4 pt-0">
        <v-spacer />
        <v-btn variant="text" @click="accountCompareDialog = false">取消</v-btn>
        <v-btn color="primary" variant="tonal" :disabled="!selectedAccountForCompare" @click="openAccountCompare">开始对比</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <ConfigCompareDialog
    v-model="accountCompareResultDialog"
    :configA="backtestAccountConfig ?? {}"
    :configB="selectedAccountForCompare ?? {}"
    :fields="accountCompareFields"
    titleA="当前回测"
    :titleB="selectedAccountForCompare?.name"
  />

  <!-- Strategy Config Compare Picker -->
  <v-dialog v-model="strategyCompareDialog" max-width="500px">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center pa-4">
        选择对比策略配置
        <v-btn icon variant="text" size="small" @click="strategyCompareDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>
        <v-select
          v-model="selectedStrategyForCompare"
          :items="strategyConfigList"
          item-title="name"
          item-value="id"
          label="策略配置"
          return-object
          clearable
        />
      </v-card-text>
      <v-card-actions class="pa-4 pt-0">
        <v-spacer />
        <v-btn variant="text" @click="strategyCompareDialog = false">取消</v-btn>
        <v-btn color="primary" variant="text" :disabled="!selectedStrategyForCompare" @click="openStrategyCompare">开始对比</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <ConfigCompareDialog
    v-model="strategyCompareResultDialog"
    :configA="backtestStrategyConfig ?? {}"
    :configB="selectedStrategyForCompare ?? {}"
    :fields="strategyCompareFields"
    titleA="当前回测"
    :titleB="selectedStrategyForCompare?.name"
  />

  <!-- Model Config Compare Picker -->
  <v-dialog v-model="modelCompareDialog" max-width="500px">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center pa-4">
        选择对比模型配置
        <v-btn icon variant="text" size="small" @click="modelCompareDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>
        <v-select
          v-model="selectedModelForCompare"
          :items="modelConfigList"
          item-title="name"
          item-value="id"
          label="模型配置"
          return-object
          clearable
        />
      </v-card-text>
      <v-card-actions class="pa-4 pt-0">
        <v-spacer />
        <v-btn variant="text" @click="modelCompareDialog = false">取消</v-btn>
        <v-btn color="primary" variant="tonal" :disabled="!selectedModelForCompare" @click="openModelCompare">开始对比</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <ConfigCompareDialog
    v-model="modelCompareResultDialog"
    :configA="backtestModelConfig ?? {}"
    :configB="selectedModelForCompare ?? {}"
    :fields="modelCompareFields"
    titleA="当前回测"
    :titleB="selectedModelForCompare?.name"
  />
</template>

<script setup lang="ts">
import { ref, reactive, computed, nextTick, watch } from 'vue'
import { backtestRecordApi, type Backtest, type BacktestConfigSnapshots, type DailyDetail, type PnlDetailItem, type PnlDetailSummary } from '@/api/backtestRecord'
import { strategyConfigApi, type Strategy } from '@/api/strategyConfig'
import { accountConfigApi, type AccountConfig } from '@/api/accountConfig'
import { modelConfigApi, type ModelConfig } from '@/api/modelConfig'
import * as echarts from 'echarts'
import PredictionChart from '@/components/PredictionChart.vue'
import OverviewChart, { type OverviewChartItem } from '@/components/OverviewChart.vue'
import ConfigCompareDialog from '@/components/ConfigCompareDialog.vue'
import type { CompareField } from '@/components/ConfigCompareDialog.vue'

const loading = ref(false)
const loadingDelete = ref(false)
const deleteDialog = ref(false)
const resultDialog = ref(false)
const predictionDialog = ref(false)
const predictionBacktestId = ref('')
const deletingItem = ref<Backtest | null>(null)
const selectedResult = ref<Backtest | null>(null)
const resultTab = ref('overview')
const tabLoaded = reactive<Record<string, boolean>>({
  overview: true,
  market: false,
  pnl: false,
  trading: false,
})

watch(resultTab, (tab) => {
  if (tabLoaded[tab]) return
  tabLoaded[tab] = true
  if (tab === 'market') {
    loadMarketData()
  } else if (tab === 'pnl') {
    if (selectedResult.value) loadPnlDetails(selectedResult.value.id)
  } else if (tab === 'trading') {
    if (selectedResult.value) loadTradingData(selectedResult.value.id)
  }
})
const pnlDetails = ref<PnlDetailItem[]>([])
const pnlSummary = ref<PnlDetailSummary | null>(null)
const pnlLoading = ref(false)
const amountChartRef = ref<HTMLDivElement>()
const countChartRef = ref<HTMLDivElement>()
const pnlSortBy = ref<{ key: string; order: 'asc' | 'desc' }[]>([{ key: 'total_pnl_amount', order: 'desc' }])
const backtestConfigDialog = ref(false)
const backtestConfigLoading = ref(false)

// Compare state
const accountCompareDialog = ref(false)
const strategyCompareDialog = ref(false)
const modelCompareDialog = ref(false)
const accountCompareResultDialog = ref(false)
const strategyCompareResultDialog = ref(false)
const modelCompareResultDialog = ref(false)
const selectedAccountForCompare = ref<AccountConfig | null>(null)
const selectedStrategyForCompare = ref<Strategy | null>(null)
const selectedModelForCompare = ref<ModelConfig | null>(null)
const accountConfigList = ref<AccountConfig[]>([])
const strategyConfigList = ref<Strategy[]>([])
const modelConfigList = ref<ModelConfig[]>([])

const accountCompareFields: CompareField[] = [
  { key: 'name', label: '名称', group: '基本信息' },
  { key: 'initial_capital', label: '初始资金', group: '基本信息', type: 'number' },
  { key: 'buy_fee_rate', label: '买入费率', group: '费率', type: 'number' },
  { key: 'sell_fee_rate', label: '卖出费率', group: '费率', type: 'number' },
  { key: 'stamp_tax_rate', label: '印花税率', group: '费率', type: 'number' },
  { key: 'min_fee', label: '最低手续费', group: '费率', type: 'number' },
  { key: 'cash', label: '现金', group: '资金', type: 'number' },
  { key: 'position', label: '持仓', group: '资金', type: 'number' },
]

const strategyCompareFields: CompareField[] = [
  { key: 'name', label: '策略名称' },
  { key: 'type', label: '策略类型' },
  { key: 'min_order_value', label: '最小订单金额', group: '基本配置', type: 'number' },
  { key: 'stop_loss_pct', label: '止损比例', group: '基本配置', type: 'number' },
  { key: 'atr_stop_multiplier', label: 'ATR止损乘数', group: '基本配置', type: 'number' },
  { key: 'atr_trail_rate', label: 'ATR上移比例', group: '基本配置', type: 'number' },
  { key: 'max_hold_days', label: '最大持仓天数', group: '基本配置', type: 'number' },
  { key: 'min_hold_days', label: '最低持有天数', group: '基本配置', type: 'number' },
  { key: 'buy_threshold', label: '买入阈值', group: '基本配置', type: 'number' },
  { key: 'max_daily_buys', label: '每日最多买入', group: '交易优化', type: 'number' },
  { key: 'sell_threshold', label: '卖出阈值', group: '基本配置', type: 'number' },
  { key: 'max_positions', label: '最大持仓数', group: '多股票配置', type: 'number' },
  { key: 'max_position_pct', label: '单票最大仓位', group: '多股票配置', type: 'number' },
  { key: 'sell_rank_n', label: '卖出排名阈值', group: '多股票配置', type: 'number' },
  { key: 'hold_score_threshold', label: '持仓评分保护阈值', group: '多股票配置', type: 'number' },
  { key: 'use_momentum_boost', label: '动量加权', group: '排名优化', type: 'boolean' },
  { key: 'use_momentum_penalty', label: '动量扣分', group: '排名优化', type: 'boolean' },
  { key: 'momentum_window', label: '动量窗口', group: '排名优化', type: 'number' },
  { key: 'max_momentum_bonus', label: '最大动量加成', group: '排名优化', type: 'number' },
  { key: 'ranking_smooth_window', label: '平滑窗口', group: '排名优化', type: 'number' },
  { key: 'ranking_smooth_alpha', label: '平滑系数', group: '排名优化', type: 'number' },
  { key: 'use_trend_bonus', label: '趋势加分', group: '排名优化', type: 'boolean' },
  { key: 'use_trend_penalty', label: '趋势扣分', group: '排名优化', type: 'boolean' },
  { key: 'trend_bonus_window', label: '趋势窗口', group: '排名优化', type: 'number' },
  { key: 'trend_bonus_scale', label: '趋势斜率系数', group: '排名优化', type: 'number' },
  { key: 'trend_r2_threshold', label: 'R²阈值', group: '排名优化', type: 'number' },
  { key: 'trend_max_bonus', label: '最大趋势加分', group: '排名优化', type: 'number' },
  { key: 'use_explosion_filter', label: '暴涨排除', group: '交易优化', type: 'boolean' },
  { key: 'explosion_price_threshold', label: '涨幅阈值', group: '交易优化', type: 'number' },
  { key: 'explosion_volume_ratio', label: '量比阈值', group: '交易优化', type: 'number' },
  { key: 'explosion_window', label: '参考窗口', group: '交易优化', type: 'number' },
  { key: 'use_full_position_sell', label: '满仓容忍度', group: '交易优化', type: 'boolean' },
  { key: 'full_position_threshold', label: '仓位阈值', group: '交易优化', type: 'number' },
  { key: 'full_position_days', label: '持续天数', group: '交易优化', type: 'number' },
  { key: 'full_position_score_window', label: '评分窗口', group: '交易优化', type: 'number' },
  { key: 'full_position_sell_count', label: '每次卖出数量', group: '交易优化', type: 'number' },
  { key: 'full_position_pnl_weight', label: 'PnL权重', group: '交易优化', type: 'number' },
  { key: 'use_rank_up_priority', label: '排名上涨优先', group: '交易优化', type: 'boolean' },
  { key: 'rank_up_window', label: '排名窗口', group: '交易优化', type: 'number' },
  { key: 'rank_up_count', label: '优先买入数', group: '交易优化', type: 'number' },
  { key: 'rank_up_min_score', label: '最低评分', group: '交易优化', type: 'number' },
  { key: 'rank_up_min_improvement_pct', label: '最小提升比例', group: '交易优化', type: 'number' },
  { key: 'score_decline_threshold', label: '评分下降阈值', group: '交易优化', type: 'number' },
  { key: 'use_score_decline_filter', label: '评分下降过滤', group: '交易优化', type: 'boolean' },
  { key: 'market_smooth_alpha', label: '市场平滑系数', group: '市场分析', type: 'number' },
  { key: 'top_n_retention', label: '留存率N值', group: '市场分析', type: 'number' },
  { key: 'retention_days', label: '留存天数', group: '市场分析', type: 'number' },
  { key: 'correlation_window', label: '关联度窗口', group: '市场分析', type: 'number' },
  { key: 'use_phase_strategy', label: '启用市场阶段策略', group: '市场分析', type: 'boolean' },
  { key: 'rotation_bottom_threshold', label: '轮动回调深度阈值', group: '轮动参数', type: 'number' },
  { key: 'rotation_rank_min', label: '排名上限', group: '轮动参数', type: 'number' },
  { key: 'rotation_rank_max', label: '排名下限', group: '轮动参数', type: 'number' },
  { key: 'rotation_use_reversal_check', label: '轮动反转确认', group: '轮动参数', type: 'boolean' },
  { key: 'rotation_was_top_n', label: '轮动历史最高排名', group: '轮动参数', type: 'number' },
  { key: 'rotation_was_top_window', label: '轮动历史检测窗口', group: '轮动参数', type: 'number' },
  { key: 'rotation_pullback_window', label: '轮动回调检测窗口', group: '轮动参数', type: 'number' },
]

const modelCompareFields: CompareField[] = [
  { key: 'name', label: '配置名称' },
  { key: 'model_type', label: '模型类型' },
  { key: 'feature_fields', label: '特征字段', group: '字段配置', type: 'array' },
  { key: 'standardize_fields', label: '标准化字段', group: '字段配置', type: 'array' },
  { key: 'winsorize_fields', label: '缩尾字段', group: '字段配置', type: 'array' },
  { key: 'label_mode', label: '标签计算模式', group: '标签参数' },
  { key: 'classification_horizons', label: '预测周期', group: '标签参数', type: 'array' },
  { key: 'classification_threshold_3d', label: '3日涨跌阈值', group: '标签参数', type: 'number' },
  { key: 'classification_threshold_5d', label: '5日涨跌阈值', group: '标签参数', type: 'number' },
  { key: 'classification_threshold_10d', label: '10日涨跌阈值', group: '标签参数', type: 'number' },
  { key: 'xgb_n_estimators', label: 'n_estimators', group: 'XGBoost', type: 'number' },
  { key: 'xgb_max_depth', label: 'max_depth', group: 'XGBoost', type: 'number' },
  { key: 'xgb_learning_rate', label: 'learning_rate', group: 'XGBoost', type: 'number' },
  { key: 'xgb_min_child_weight', label: 'min_child_weight', group: 'XGBoost', type: 'number' },
  { key: 'xgb_subsample', label: 'subsample', group: 'XGBoost', type: 'number' },
  { key: 'xgb_colsample_bytree', label: 'colsample_bytree', group: 'XGBoost', type: 'number' },
  { key: 'lstm_hidden_size', label: 'hidden_size', group: 'LSTM', type: 'number' },
  { key: 'lstm_num_layers', label: 'num_layers', group: 'LSTM', type: 'number' },
  { key: 'lstm_dropout', label: 'dropout', group: 'LSTM', type: 'number' },
  { key: 'lstm_epochs', label: 'epochs', group: 'LSTM', type: 'number' },
  { key: 'lstm_batch_size', label: 'batch_size', group: 'LSTM', type: 'number' },
  { key: 'lstm_learning_rate', label: 'learning_rate', group: 'LSTM', type: 'number' },
  { key: 'lstm_sequence_length', label: 'sequence_length', group: 'LSTM', type: 'number' },
  { key: 'lstm_normalization_window', label: 'normalization_window', group: 'LSTM', type: 'number' },
  { key: 'lstm_weight_decay', label: 'weight_decay', group: 'LSTM', type: 'number' },
  { key: 'lr_scheduler_factor', label: 'lr_scheduler_factor', group: 'LSTM', type: 'number' },
  { key: 'lr_scheduler_patience', label: 'lr_scheduler_patience', group: 'LSTM', type: 'number' },
  { key: 'val_size', label: 'val_size', group: 'LSTM', type: 'number' },
]

const dailyDetailDialog = ref(false)
const dailyDetails = ref<DailyDetail[]>([])
const loadingDaily = ref(false)
const expandedDates = ref<Set<string>>(new Set())
const dailyPage = ref(1)
const dailyPageSize = ref(15)
const selectedMonth = ref('全部')

const marketChartData = ref<OverviewChartItem[]>([])
const marketTrendThreshold = ref(0.05)

const monthOptions = computed(() => {
  if (!dailyDetails.value.length) return []
  const months = new Set(dailyDetails.value.map(d => d.date.substring(0, 6)))
  return ['全部', ...Array.from(months).sort()]
})

const totalPages = computed(() => {
  return Math.max(1, Math.ceil(dailyDetails.value.length / dailyPageSize.value))
})

const paginatedItems = computed(() => {
  const items = dailyDetails.value
  const start = (dailyPage.value - 1) * dailyPageSize.value
  return items.slice(start, start + dailyPageSize.value)
})

function onMonthChange(month: string) {
  if (month === '全部') {
    dailyPage.value = 1
    return
  }
  const idx = dailyDetails.value.findIndex(d => d.date.startsWith(month))
  if (idx >= 0) {
    dailyPage.value = Math.floor(idx / dailyPageSize.value) + 1
  }
}

function retColor(val: number | null | undefined): string {
  if (val == null) return '#9e9e9e'
  return val > 0 ? '#4caf50' : '#f44336'
}
const backtestConfigTab = ref('model')
const backtestConfigItem = ref<Backtest | null>(null)
const backtestModelConfig = ref<Record<string, any> | null>(null)
const backtestStrategyConfig = ref<Partial<Strategy> | null>(null)
const backtestAccountConfig = ref<BacktestConfigSnapshots['account_snapshot'] | null>(null)
const excludedStocks = ref<any[]>([])
const forcedSellStocks = ref<any[]>([])
const tradingLoading = ref(false)

const forcedSellHeaders = [
  { title: '股票', key: 'stock_name' },
  { title: '强制卖出次数', key: 'forced_count', align: 'center' as const },
  { title: '明细（点击展开）', key: 'forced_dates' },
]
let amountChart: echarts.ECharts | null = null
let countChart: echarts.ECharts | null = null

const BASIC_FIELD_NAMES = new Set([
  'open', 'high', 'low', 'close', 'vol', 'amount',
  'pct_chg',
  'week_open', 'week_high', 'week_low', 'week_close',
  'week_vol_avg', 'week_amount_avg',
  'candle_body_pct', 'candle_upper_pct', 'candle_lower_pct',
])

const isBasicField = (name: string) => BASIC_FIELD_NAMES.has(name)

const viewPredictions = (item: Backtest) => {
  predictionBacktestId.value = item.id
  predictionDialog.value = true
}
const backtests = ref<Backtest[]>([])
const totalItems = ref(0)
const page = ref(1)
const pageSize = ref(20)

const historyHeaders = [
  { title: '名称', key: 'name', width: 100, nowrap: true },
  { title: '股票', key: 'ts_codes', width: 100, nowrap: true },
  { title: '总收益', key: 'total_return', width: 100, nowrap: true },
  { title: '超额收益', key: 'excess_return', width: 100, nowrap: true },
  { title: '最大回撤', key: 'max_drawdown', width: 100, nowrap: true },
  { title: '夏普比', key: 'sharpe_ratio', width: 100, nowrap: true },
  { title: '分析', key: 'analysis_action', sortable: false, align: 'center' as const, width: 180, nowrap: true },
  { title: '配置', key: 'config_action', sortable: false, align: 'center' as const, width: 80, nowrap: true },
  { title: '操作', key: 'actions', sortable: false, align: 'center' as const, width: 80, nowrap: true },
]

const excludedHeaders = [
  { title: '股票', key: 'stock_name' },
  { title: '排除次数', key: 'excluded_count', align: 'center' as const },
  { title: '排除明细（点击展开）', key: 'excluded_dates' },
]

const dailyTradeHeaders = [
  { title: '股票', key: 'stock_name' },
  { title: '操作', key: 'action', align: 'center' as const },
  { title: '成交价', key: 'filled_price' },
  { title: '数量', key: 'shares' },
  { title: '手续费', key: 'fee' },
  { title: '理由', key: 'reason' },
  { title: '盈亏', key: 'pnl_amount' },
  { title: '收益率', key: 'pnl_pct' },
]

const dailyPositionHeaders = [
  { title: '股票', key: 'stock_name' },
  { title: '买入日期', key: 'buy_date' },
  { title: '成本价', key: 'buy_price' },
  { title: '现价', key: 'current_price' },
  { title: '持股', key: 'shares' },
  { title: '市值', key: 'market_value' },
  { title: '浮盈亏', key: 'unrealized_pnl' },
  { title: '收益率', key: 'unrealized_pnl_pct' },
  { title: '持有天数', key: 'hold_days' },
  { title: '入场评分', key: 'entry_score' },
]

const loadBacktests = async () => {
  loading.value = true
  const res = await backtestRecordApi.list(page.value, pageSize.value)
  backtests.value = res.data.items
  totalItems.value = res.data.total
  loading.value = false
}

const handleOptionsChange = (options: { page: number; itemsPerPage: number }) => {
  page.value = options.page
  pageSize.value = options.itemsPerPage
  loadBacktests()
}

const viewResult = (item: Backtest) => {
    selectedResult.value = item
    resultDialog.value = true
    resultTab.value = 'overview'
    // Reset tab load flags and clear old data for new record
    tabLoaded.market = false
    tabLoaded.pnl = false
    tabLoaded.trading = false
    marketChartData.value = []
    pnlDetails.value = []
    pnlSummary.value = null
    excludedStocks.value = []
    forcedSellStocks.value = []
  }

  const openBacktestConfig = async (item: Backtest) => {
  backtestConfigItem.value = item
  backtestConfigTab.value = 'account'
  backtestConfigDialog.value = true
  backtestConfigLoading.value = true
  backtestAccountConfig.value = null
  backtestStrategyConfig.value = null
  backtestModelConfig.value = null
  try {
    const res = await backtestRecordApi.getConfigSnapshots(item.id)
    const data = res.data
    backtestAccountConfig.value = data.account_snapshot ? { ...data.account_snapshot } : null
    backtestStrategyConfig.value = data.strategy_snapshot
      ? { ...data.strategy_snapshot } as Partial<Strategy>
      : null
    backtestModelConfig.value = data.model_snapshot ? { ...data.model_snapshot } : null
  } finally {
    backtestConfigLoading.value = false
  }
}

const loadAccountConfigs = async () => {
  accountCompareDialog.value = true
  const res = await accountConfigApi.list()
  accountConfigList.value = res.data
}

const loadStrategyConfigs = async () => {
  strategyCompareDialog.value = true
  const res = await strategyConfigApi.list()
  strategyConfigList.value = res.data
}

const loadModelConfigs = async () => {
  modelCompareDialog.value = true
  const res = await modelConfigApi.list()
  modelConfigList.value = res.data
}

const openAccountCompare = () => {
  if (!selectedAccountForCompare.value) return
  accountCompareDialog.value = false
  accountCompareResultDialog.value = true
}

const openStrategyCompare = () => {
  if (!selectedStrategyForCompare.value) return
  strategyCompareDialog.value = false
  strategyCompareResultDialog.value = true
}

const openModelCompare = () => {
  if (!selectedModelForCompare.value) return
  modelCompareDialog.value = false
  modelCompareResultDialog.value = true
}

const confirmDelete = (item: Backtest) => {
  deletingItem.value = item
  deleteDialog.value = true
}

const deleteBacktest = async () => {
  if (!deletingItem.value) return
  loadingDelete.value = true
  await backtestRecordApi.delete(deletingItem.value.id)
  deleteDialog.value = false
  deletingItem.value = null
  await loadBacktests()
  loadingDelete.value = false
}

const loadTradingData = async (resultId: string) => {
  tradingLoading.value = true
  try {
    const [excludedRes, forcedRes] = await Promise.all([
      backtestRecordApi.getExcludedStocks(resultId),
      backtestRecordApi.getForcedSellStocks(resultId),
    ])
    excludedStocks.value = excludedRes.data.items.map((s: any) => ({ ...s, _detail: false }))
    forcedSellStocks.value = forcedRes.data.items.map((s: any) => ({ ...s, _detail: false }))
  } catch {
    excludedStocks.value = []
    forcedSellStocks.value = []
  } finally {
    tradingLoading.value = false
  }
}

const loadPnlDetails = async (backtestId: string) => {
  pnlLoading.value = true
  try {
    const res = await backtestRecordApi.getPnlDetails(backtestId)
    pnlDetails.value = res.data.items
    pnlSummary.value = res.data.summary
    if (resultTab.value === 'pnl') {
      await nextTick()
      renderCharts()
    }
  } catch {
    pnlDetails.value = []
    pnlSummary.value = null
  } finally {
    pnlLoading.value = false
  }
}

const renderCharts = () => {
  if (!amountChartRef.value || !countChartRef.value) return

  amountChart?.dispose()
  countChart?.dispose()

  amountChart = echarts.init(amountChartRef.value)
  countChart = echarts.init(countChartRef.value)

  const sortOrder = pnlSortBy.value[0]?.order || 'desc'
  const sortMultiplier = sortOrder === 'desc' ? 1 : -1

  const amountData = pnlDetails.value
    .filter(item => item.total_pnl !== 0)
    .map(item => ({
      name: item.stock_name || item.ts_code,
      value: Math.abs(item.total_pnl),
      sortValue: item.total_pnl || 0,
      itemStyle: { color: item.total_pnl >= 0 ? '#4caf50' : '#f44336' },
    }))
    .sort((a, b) => (b.sortValue - a.sortValue) * sortMultiplier)

  amountChart.setOption({
    title: { text: '盈亏金额分布', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'item', formatter: '{b}: ¥{c} ({d}%)' },
    series: [{
      type: 'pie', radius: ['30%', '70%'],
      data: amountData,
      label: { formatter: '{b}\n¥{c}', fontSize: 11 },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' } },
      sort: 'none',
    }],
  })

  const countData = pnlDetails.value
    .filter(item => (item.profit_count + item.loss_count) > 0)
    .map(item => ({
      name: item.stock_name || item.ts_code,
      value: item.profit_count + item.loss_count,
      sortValue: item.total_pnl || 0,
      itemStyle: { color: item.total_pnl >= 0 ? '#4caf50' : '#f44336' },
    }))
    .sort((a, b) => (b.sortValue - a.sortValue) * sortMultiplier)

  countChart.setOption({
    title: { text: '交易次数分布', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'item', formatter: '{b}: {c}次 ({d}%)' },
    series: [{
      type: 'pie', radius: ['30%', '70%'],
      data: countData,
      label: { formatter: '{b}\n{c}次', fontSize: 11 },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' } },
      sort: 'none',
    }],
  })
}

const pnlHeaders = [
  { title: '股票', key: 'stock_name' },
  { title: '已实现盈亏', key: 'realized_pnl' },
  { title: '浮盈亏', key: 'unrealized_pnl' },
  { title: '总盈亏', key: 'total_pnl' },
  { title: '盈利', key: 'profit_count' },
  { title: '亏损', key: 'loss_count' },
  { title: '胜率', key: 'trade_win_rate' },
]

const toggleExpand = (date: string) => {
  const s = new Set(expandedDates.value)
  if (s.has(date)) s.delete(date)
  else s.add(date)
  expandedDates.value = s
}

const reasonColor = (reason: string | undefined | null): string => {
  const map: Record<string, string> = {
    'stop_loss': 'error',
    'score_below_sell': 'warning',
    'max_hold_days': 'info',
    'hold_score_low': 'orange',
    'full_position_forced_sell': 'deep-purple',
    'candidate_excluded': 'grey',
    'normal_buy': 'success',
    'priority_rank_up': 'info',
    'rotation_buy': 'indigo',
    '': 'grey',
  }
  return map[reason || ''] || 'grey'
}

const reasonLabel = (reason: string | undefined | null): string => {
  const map: Record<string, string> = {
    'stop_loss': '止损卖出',
    'score_below_sell': '评分低于阈值',
    'max_hold_days': '达最大持仓天数',
    'hold_score_low': '排名靠后评分低',
    'full_position_forced_sell': '满仓强制卖出',
    'candidate_excluded': '候选排除',
    'normal_buy': '常规买入',
    'priority_rank_up': '排名上涨优先买入',
    'rotation_buy': '轮动买入',
    '': '-',
  }
  return map[reason || ''] || reason || '-'
}

const calculateReturns = (snapshots: { total_value: number; baseline_value: number }[]) => {
  if (!snapshots.length) return { strategy_returns: [], baseline_returns: [] }
  const firstStrat = snapshots[0].total_value
  const firstBase = snapshots[0].baseline_value
  return {
    strategy_returns: snapshots.map(s => firstStrat > 0 ? ((s.total_value - firstStrat) / firstStrat * 100) : 0),
    baseline_returns: snapshots.map(s => firstBase > 0 ? ((s.baseline_value - firstBase) / firstBase * 100) : 0),
  }
}

const loadMarketData = async () => {
  if (!selectedResult.value) return
  try {
    const res = await backtestRecordApi.getDailySnapshots(selectedResult.value.id)
    const snaps = res.data.items
    const { strategy_returns, baseline_returns } = calculateReturns(snaps)
    marketChartData.value = snaps.map((s, i) => ({
      date: s.date,
      strategy_return: strategy_returns[i] || 0,
      baseline_return: baseline_returns[i] || 0,
      ranking_high_pct: s.ranking_high_pct,
      ranking_low_pct: s.ranking_low_pct,
      market_phase: s.market_phase,
      daily_rebalanced_cum: s.daily_rebalanced_cum ?? 0,
      rebalanced_ma10_pct: s.rebalanced_ma10_pct ?? 0,
      rebalanced_ma60_pct: s.rebalanced_ma60_pct ?? 0,
      baseline_vol_multiplier: s.baseline_vol_multiplier ?? 1.0,
      position_pct: s.position_pct ?? 50,
      top_n_retention_rate_smoothed: s.top_n_retention_rate_smoothed ?? 0,
      score_return_corr_smoothed: s.score_return_corr_smoothed ?? 0,
    }))
    // No longer using phase_crash_threshold for market trend
    marketTrendThreshold.value = -0.06
  } catch (e) {
    marketChartData.value = []
  }
}

const viewDailyDetail = async (item: Backtest) => {
  selectedResult.value = item
  dailyDetailDialog.value = true
  loadingDaily.value = true
  dailyDetails.value = []
  expandedDates.value = new Set()
  dailyPage.value = 1
  selectedMonth.value = '全部'
  try {
    const res = await backtestRecordApi.getDailyDetails(item.id)
    dailyDetails.value = res.data.items
  } catch (e) {
    dailyDetails.value = []
  } finally {
    loadingDaily.value = false
  }
}

watch(resultTab, () => {
  if (resultTab.value === 'pnl') {
    nextTick(() => renderCharts())
  }
})
</script>
