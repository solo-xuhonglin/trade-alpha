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
          <v-btn size="small" variant="text" color="primary" prepend-icon="mdi-format-list-bulleted" @click="viewTrades(item)">交易</v-btn>
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

  <v-dialog v-model="resultDialog" max-width="1050px">
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
            <v-tab value="pnl">盈亏分析</v-tab>
            <v-tab value="explosion">暴涨排除</v-tab>
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

          <v-window-item value="pnl">
              <div v-if="pnlLoading" class="text-center text-medium-emphasis py-8">加载中...</div>
              <div v-else-if="!pnlSummary" class="text-center text-medium-emphasis py-8">暂无盈亏数据</div>
              <div v-else>
                <v-row>
                  <v-col cols="6" sm="3">
                    <v-card variant="tonal" :color="pnlSummary.total_pnl_amount >= 0 ? 'success' : 'error'">
                      <v-card-text class="text-center pa-2">
                        <div class="text-caption text-medium-emphasis">总盈亏</div>
                        <div class="text-h6">¥{{ pnlSummary.total_pnl_amount.toFixed(2) }}</div>
                      </v-card-text>
                    </v-card>
                  </v-col>
                  <v-col cols="6" sm="3">
                    <v-card variant="tonal" color="success">
                      <v-card-text class="text-center pa-2">
                        <div class="text-caption text-medium-emphasis">盈利次数</div>
                        <div class="text-h6">{{ pnlSummary.total_profit_trades }}</div>
                      </v-card-text>
                    </v-card>
                  </v-col>
                  <v-col cols="6" sm="3">
                    <v-card variant="tonal" color="error">
                      <v-card-text class="text-center pa-2">
                        <div class="text-caption text-medium-emphasis">亏损次数</div>
                        <div class="text-h6">{{ pnlSummary.total_loss_trades }}</div>
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
                  <template v-slot:item.total_pnl_amount="{ item }">
                    <span :class="item.total_pnl_amount >= 0 ? 'text-success' : 'text-error'">
                      ¥{{ item.total_pnl_amount.toFixed(2) }}
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

          <v-window-item value="explosion">
            <div v-if="excludedLoading" class="text-center text-medium-emphasis py-8">加载中...</div>
            <div v-else-if="excludedStocks.length === 0" class="text-center text-medium-emphasis py-8">无暴涨排除记录</div>
            <v-data-table v-else :headers="excludedHeaders" :items="excludedStocks" density="compact"
              hide-default-footer items-per-page="-1" class="mt-2"
              @click:row="(_, { item }) => toggleExcludedDetail(item)" style="cursor: pointer;">
              <template v-slot:item.excluded_dates="{ item }">
                <div v-if="item._detail">
                  <div v-for="d in item.excluded_dates" :key="d.date" class="text-caption">
                    {{ d.date }} 涨 {{ (d.price_surge_pct * 100).toFixed(1) }}% 量比 {{ d.volume_ratio.toFixed(1) }}x
                  </div>
                </div>
                <span v-else class="text-caption text-medium-emphasis">点击展开 ({{ item.excluded_count }} 次)</span>
              </template>
            </v-data-table>
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

  <v-dialog v-model="tradesDialog" max-width="1100px">
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center">
        交易记录
        <v-btn icon variant="text" size="small" @click="tradesDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>
        <v-data-table-server
          :headers="tradesHeaders"
          :items="trades"
          :loading="loadingTrades"
          :items-length="totalTrades"
          :items-per-page="tradesPageSize"
          :page="tradesPage"
          @update:options="handleTradesOptionsChange"
        >
          <template v-slot:item.action="{ item }">
            <v-chip :color="item.action === 'buy' ? 'success' : 'error'" size="small">
              {{ item.action === 'buy' ? '买入' : '卖出' }}
            </v-chip>
          </template>
          <template v-slot:item.ts_code="{ item }">
            {{ item.ts_name || item.stock_name || item.ts_code }}
          </template>
          <template v-slot:item.status="{ item }">
            <v-chip v-if="item.status === 'filled'" color="success" size="small">成交</v-chip>
            <v-chip v-else color="grey" size="small">未成交</v-chip>
          </template>
          <template v-slot:item.price="{ item }">
            {{ item.status === 'cancelled' ? '-' : item.filled_price.toFixed(2) }}
          </template>
          <template v-slot:item.shares="{ item }">
            {{ item.status === 'cancelled' ? '-' : item.shares }}
          </template>
          <template v-slot:item.fee="{ item }">
            {{ item.status === 'cancelled' ? '-' : item.fee.toFixed(2) }}
          </template>
          <template v-slot:item.cash_after="{ item }">
            {{ item.status === 'cancelled' ? '-' : item.cash_after.toFixed(2) }}
          </template>
        </v-data-table-server>
      </v-card-text>
      <v-divider></v-divider>
      <v-card-actions class="bg-surface-light">
        <v-spacer></v-spacer>
        <v-btn text="关闭" variant="plain" @click="tradesDialog = false"></v-btn>
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
        <v-btn icon variant="text" @click="backtestConfigDialog = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-toolbar>
      <v-tabs v-model="backtestConfigTab" bg-color="surface">
        <v-tab value="model">模型配置</v-tab>
        <v-tab value="strategy">策略配置</v-tab>
        <v-tab value="features">特征配置</v-tab>
      </v-tabs>
      <v-divider />
      <v-card-text>
        <v-window v-model="backtestConfigTab">
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
              <v-col cols="6"><span class="text-body-2 text-medium-emphasis">最大持仓天数：</span>{{ backtestStrategyConfig?.max_hold_days ?? '-' }}</v-col>
            </v-row>
            <v-row class="py-0">
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
              <v-col cols="6">
                <span class="text-body-2 text-medium-emphasis">动量加成：</span>
                <v-icon :color="backtestStrategyConfig?.use_momentum_boost ? 'success' : 'disabled'" size="small">
                  {{ backtestStrategyConfig?.use_momentum_boost ? 'mdi-check-circle' : 'mdi-close-circle' }}
                </v-icon>
                <span v-if="backtestStrategyConfig?.use_momentum_boost" class="text-body-2">
                  &nbsp;窗口{{ backtestStrategyConfig?.momentum_window ?? '-' }} 权重{{ backtestStrategyConfig?.momentum_weight ?? '0.3' }} 上限{{ ((backtestStrategyConfig?.max_momentum_bonus ?? 0) * 100).toFixed(0) }}%
                </span>
              </v-col>
              <v-col cols="6">
                <span class="text-body-2 text-medium-emphasis">趋势左移：</span>
                <v-icon :color="backtestStrategyConfig?.use_trend_boost ? 'success' : 'disabled'" size="small">
                  {{ backtestStrategyConfig?.use_trend_boost ? 'mdi-check-circle' : 'mdi-close-circle' }}
                </v-icon>
                <span v-if="backtestStrategyConfig?.use_trend_boost" class="text-body-2">
                  &nbsp;窗口{{ backtestStrategyConfig?.trend_window ?? '-' }} 斜率{{ backtestStrategyConfig?.trend_scale ?? '0.5' }} 上限{{ ((backtestStrategyConfig?.max_trend_boost ?? 0) * 100).toFixed(0) }}%
                </span>
              </v-col>
            </v-row>
            <v-row class="py-0 mt-1">
              <v-col cols="6">
                <span class="text-body-2 text-medium-emphasis">暴涨排除：</span>
                <v-icon :color="backtestStrategyConfig?.use_explosion_filter ? 'success' : 'disabled'" size="small">
                  {{ backtestStrategyConfig?.use_explosion_filter ? 'mdi-check-circle' : 'mdi-close-circle' }}
                </v-icon>
                <span v-if="backtestStrategyConfig?.use_explosion_filter" class="text-body-2">
                  &nbsp;涨幅{{ ((backtestStrategyConfig?.explosion_price_threshold ?? 0) * 100).toFixed(0) }}% 量比{{ backtestStrategyConfig?.explosion_volume_ratio ?? '3.0' }}x 窗口{{ backtestStrategyConfig?.explosion_window ?? '5' }}
                </span>
              </v-col>
              <v-col cols="6"></v-col>
            </v-row>
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
</template>

<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { backtestRecordApi, type Backtest, type Trade, type PnlDetailItem, type PnlDetailSummary } from '@/api/backtestRecord'
import { type Strategy } from '@/api/strategyConfig'
import * as echarts from 'echarts'
import PredictionChart from '@/components/PredictionChart.vue'

const loading = ref(false)
const loadingDelete = ref(false)
const loadingTrades = ref(false)
const deleteDialog = ref(false)
const tradesDialog = ref(false)
const resultDialog = ref(false)
const predictionDialog = ref(false)
const predictionBacktestId = ref('')
const deletingItem = ref<Backtest | null>(null)
const viewingBacktest = ref<Backtest | null>(null)
const selectedResult = ref<Backtest | null>(null)
const resultTab = ref('overview')
const pnlDetails = ref<PnlDetailItem[]>([])
const pnlSummary = ref<PnlDetailSummary | null>(null)
const pnlLoading = ref(false)
const amountChartRef = ref<HTMLDivElement>()
const countChartRef = ref<HTMLDivElement>()
const pnlSortBy = ref<{ key: string; order: 'asc' | 'desc' }[]>([{ key: 'total_pnl_amount', order: 'desc' }])
const backtestConfigDialog = ref(false)
const backtestConfigTab = ref('model')
const backtestConfigItem = ref<Backtest | null>(null)
const backtestModelConfig = ref<Record<string, any> | null>(null)
const backtestStrategyConfig = ref<Partial<Strategy> | null>(null)
const excludedStocks = ref<any[]>([])
const excludedLoading = ref(false)
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
const trades = ref<Trade[]>([])
const totalItems = ref(0)
const page = ref(1)
const pageSize = ref(20)
const totalTrades = ref(0)
const tradesPage = ref(1)
const tradesPageSize = ref(20)

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

const tradesHeaders = [
  { title: '股票', key: 'ts_code' },
  { title: '日期', key: 'trade_date' },
  { title: '操作', key: 'action' },
  { title: '状态', key: 'status' },
  { title: '价格', key: 'price' },
  { title: '数量', key: 'shares' },
  { title: '手续费', key: 'fee' },
  { title: '现金', key: 'cash_after' },
]

const excludedHeaders = [
  { title: '股票', key: 'stock_name' },
  { title: '排除次数', key: 'excluded_count', align: 'center' as const },
  { title: '排除明细（点击展开）', key: 'excluded_dates' },
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

const handleTradesOptionsChange = (options: { page: number; itemsPerPage: number }) => {
  tradesPage.value = options.page
  tradesPageSize.value = options.itemsPerPage
  loadTrades()
  }

  const viewResult = (item: Backtest) => {
    selectedResult.value = item
    resultDialog.value = true
    resultTab.value = 'overview'
    nextTick(() => {
      loadPnlDetails(item.id)
      loadExcludedStocks(item.id)
    })
  }

  const openBacktestConfig = (item: Backtest) => {
  backtestConfigItem.value = item
  backtestConfigTab.value = 'model'
  backtestModelConfig.value = item.model_snapshot ? { ...item.model_snapshot } : null
  backtestStrategyConfig.value = item.strategy_snapshot
    ? { ...item.strategy_snapshot } as Partial<Strategy>
    : item.strategy_name
      ? {
          name: item.strategy_name,
          type: item.strategy_type || '',
          min_order_value: item.min_order_value ?? 0,
          stop_loss_pct: item.stop_loss_pct ?? 0,
          max_hold_days: item.max_hold_days ?? 0,
          buy_threshold: item.buy_threshold ?? 0,
          sell_threshold: item.sell_threshold ?? 0,
          max_positions: item.max_positions,
          max_position_pct: item.max_position_pct,
          sell_rank_n: item.sell_rank_n,
          hold_score_threshold: item.hold_score_threshold,
        }
      : null
  backtestConfigDialog.value = true
}

const viewTrades = async (item: Backtest) => {
  viewingBacktest.value = item
  tradesPage.value = 1
  tradesDialog.value = true
  await loadTrades()
}

const loadTrades = async () => {
  if (!viewingBacktest.value) return
  loadingTrades.value = true
  const res = await backtestRecordApi.getTrades(viewingBacktest.value.id, tradesPage.value, tradesPageSize.value)
  trades.value = res.data.items
  totalTrades.value = res.data.total
  loadingTrades.value = false
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

const toggleExcludedDetail = (item: any) => {
  item._detail = !item._detail
}

const loadExcludedStocks = async (resultId: string) => {
  excludedLoading.value = true
  try {
    const res = await backtestRecordApi.getExcludedStocks(resultId)
    excludedStocks.value = res.data.items.map((s: any) => ({ ...s, _detail: false }))
  } catch {
    excludedStocks.value = []
  } finally {
    excludedLoading.value = false
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

  const sortKey = pnlSortBy.value[0]?.key || 'total_pnl_amount'
  const sortOrder = pnlSortBy.value[0]?.order || 'desc'
  const sortMultiplier = sortOrder === 'desc' ? 1 : -1

  const amountData = pnlDetails.value
    .filter(item => item.total_pnl_amount !== 0)
    .map(item => ({
      name: item.stock_name || item.ts_code,
      value: Math.abs(item.total_pnl_amount),
      sortValue: item[sortKey as keyof PnlDetailItem] as number || 0,
      itemStyle: { color: item.total_pnl_amount >= 0 ? '#4caf50' : '#f44336' },
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
    .filter(item => item.total_sells > 0)
    .map(item => ({
      name: item.stock_name || item.ts_code,
      value: item.total_sells,
      sortValue: item[sortKey as keyof PnlDetailItem] as number || 0,
      itemStyle: { color: item.total_pnl_amount >= 0 ? '#4caf50' : '#f44336' },
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
  { title: '总盈亏', key: 'total_pnl_amount' },
  { title: '盈利次数', key: 'profit_count' },
  { title: '亏损次数', key: 'loss_count' },
  { title: '卖出次数', key: 'total_sells' },
  { title: '胜率', key: 'trade_win_rate' },
]

watch(resultTab, () => {
  if (resultTab.value === 'pnl') {
    nextTick(() => renderCharts())
  }
})
</script>
