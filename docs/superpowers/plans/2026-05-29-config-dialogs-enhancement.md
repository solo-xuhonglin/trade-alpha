# Config Dialogs Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild backtest config dialog and training config dialog with card-based tab layout, adding the missing feature fields display.

**Architecture:** Vuetify v-tabs + v-card layout replacing simple key-value v-table. Feature fields and model config loaded from existing API endpoints; no backend changes.

**Tech Stack:** Vue 3 + TypeScript + Vuetify 3 + Vite

**Files to modify:**
- `frontend/src/views/BacktestRecordsView.vue`
- `frontend/src/views/TrainingRecordsView.vue`

---

### Task 1: Add field grouping utility

**Files:**
- Modify: `frontend/src/views/BacktestRecordsView.vue`

- [ ] **Step 1: Add basic field classification set**

Add near the top of `<script setup lang="ts">` block (after imports):

```typescript
// Classification of feature fields for display grouping
const BASIC_FIELD_NAMES = new Set([
  'open', 'high', 'low', 'close', 'vol', 'amount',
  'pct_chg',
  'week_open', 'week_high', 'week_low', 'week_close',
  'week_vol_avg', 'week_amount_avg',
  'candle_body_pct', 'candle_upper_pct', 'candle_lower_pct',
])

const isBasicField = (name: string) => BASIC_FIELD_NAMES.has(name)
```

- [ ] **Step 2: Verify TypeScript**

Run: `cd frontend && npx vue-tsc -b`
Expected: Exit code 0

- [ ] **Step 3: Commit**

---

### Task 2: Rebuild backtest config dialog - template

**Files:**
- Modify: `frontend/src/views/BacktestRecordsView.vue`

- [ ] **Step 1: Replace the backtestConfigDialog template**

Replace lines ~312-356 entirely with the new card-based tab layout:

```html
<v-dialog v-model="backtestConfigDialog.show" max-width="800" scrollable>
  <v-card>
    <v-toolbar flat>
      <v-toolbar-title>回测配置</v-toolbar-title>
      <v-spacer />
      <v-btn icon variant="text" @click="backtestConfigDialog.show = false">
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
        <!-- Model Config Tab -->
        <v-window-item value="model">
          <v-card variant="outlined" class="mb-4">
            <v-card-title class="text-subtitle-1 d-flex align-center">
              <v-icon start>mdi-information-outline</v-icon> 基本信息
            </v-card-title>
            <v-divider />
            <v-card-text>
              <v-row>
                <v-col cols="6" class="py-1"><span class="text-caption text-medium-emphasis">名称</span><br />{{ backtestModelConfig?.name || '-' }}</v-col>
                <v-col cols="6" class="py-1"><span class="text-caption text-medium-emphasis">模型类型</span><br />{{ backtestModelConfig?.model_type || '-' }}</v-col>
                <v-col cols="6" class="py-1"><span class="text-caption text-medium-emphasis">创建时间</span><br />{{ backtestModelConfig?.created_at ? new Date(backtestModelConfig.created_at).toLocaleString() : '-' }}</v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <v-card variant="outlined" class="mb-4">
            <v-card-title class="text-subtitle-1 d-flex align-center">
              <v-icon start>mdi-tune</v-icon> 训练参数
            </v-card-title>
            <v-divider />
            <v-card-text>
              <v-row>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">分类周期</span><br />{{ backtestModelConfig?.classification_horizons?.join(', ') || '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">标签模式</span><br />{{ backtestModelConfig?.label_mode || '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">验证集比例</span><br />{{ backtestModelConfig?.val_size ?? '-' }}</v-col>
              </v-row>
              <v-divider class="my-2" />
              <div class="text-caption text-medium-emphasis mb-1">阈值</div>
              <v-row>
                <v-col v-for="(v, k) in backtestModelConfig?.thresholds" :key="k" cols="4" class="py-1">
                  <span class="text-caption text-medium-emphasis">{{ k }}</span><br />{{ v }}
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <v-card v-if="backtestModelConfig?.model_type === 'xgboost'" variant="outlined" class="mb-4">
            <v-card-title class="text-subtitle-1 d-flex align-center">
              <v-icon start>mdi-chart-line</v-icon> XGB 参数
            </v-card-title>
            <v-divider />
            <v-card-text>
              <v-row>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Learning Rate</span><br />{{ backtestModelConfig?.xgb_learning_rate ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Max Depth</span><br />{{ backtestModelConfig?.xgb_max_depth ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Subsample</span><br />{{ backtestModelConfig?.xgb_subsample ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Colsample By Tree</span><br />{{ backtestModelConfig?.xgb_colsample_bytree ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Min Child Weight</span><br />{{ backtestModelConfig?.xgb_min_child_weight ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">N Estimators</span><br />{{ backtestModelConfig?.xgb_n_estimators ?? '-' }}</v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <v-card v-if="backtestModelConfig?.model_type === 'lstm'" variant="outlined" class="mb-4">
            <v-card-title class="text-subtitle-1 d-flex align-center">
              <v-icon start>mdi-neural</v-icon> LSTM 参数
            </v-card-title>
            <v-divider />
            <v-card-text>
              <v-row>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Hidden Size</span><br />{{ backtestModelConfig?.lstm_hidden_size ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Num Layers</span><br />{{ backtestModelConfig?.lstm_num_layers ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Dropout</span><br />{{ backtestModelConfig?.lstm_dropout ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Epochs</span><br />{{ backtestModelConfig?.lstm_epochs ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Batch Size</span><br />{{ backtestModelConfig?.lstm_batch_size ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Learning Rate</span><br />{{ backtestModelConfig?.lstm_learning_rate ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Sequence Length</span><br />{{ backtestModelConfig?.lstm_sequence_length ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Norm Window</span><br />{{ backtestModelConfig?.lstm_normalization_window ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Weight Decay</span><br />{{ backtestModelConfig?.lstm_weight_decay ?? '-' }}</v-col>
              </v-row>
            </v-card-text>
          </v-card>
        </v-window-item>

        <!-- Strategy Config Tab -->
        <v-window-item value="strategy">
          <v-card variant="outlined" class="mb-4">
            <v-card-title class="text-subtitle-1 d-flex align-center">
              <v-icon start>mdi-information-outline</v-icon> 策略信息
            </v-card-title>
            <v-divider />
            <v-card-text>
              <v-row>
                <v-col cols="6" class="py-1"><span class="text-caption text-medium-emphasis">名称</span><br />{{ backtestStrategyConfig?.name || '-' }}</v-col>
                <v-col cols="6" class="py-1"><span class="text-caption text-medium-emphasis">类型</span><br />{{ backtestStrategyConfig?.type || '-' }}</v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <v-card variant="outlined" class="mb-4">
            <v-card-title class="text-subtitle-1 d-flex align-center">
              <v-icon start>mdi-swap-vertical</v-icon> 交易规则
            </v-card-title>
            <v-divider />
            <v-card-text>
              <v-row>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">买入阈值</span><br />{{ backtestStrategyConfig?.buy_threshold ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">卖出阈值</span><br />{{ backtestStrategyConfig?.sell_threshold ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">止损比例</span><br />{{ backtestStrategyConfig?.stop_loss_pct ? (backtestStrategyConfig.stop_loss_pct * 100).toFixed(0) + '%' : '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">最大持仓天数</span><br />{{ backtestStrategyConfig?.max_hold_days ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">最小交易金额</span><br />{{ backtestStrategyConfig?.min_order_value ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">持仓评分阈值</span><br />{{ backtestStrategyConfig?.hold_score_threshold ?? '-' }}</v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <v-card variant="outlined" class="mb-4">
            <v-card-title class="text-subtitle-1 d-flex align-center">
              <v-icon start>mdi-lock-pattern</v-icon> 持仓限制
            </v-card-title>
            <v-divider />
            <v-card-text>
              <v-row>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">最大持仓数</span><br />{{ backtestStrategyConfig?.max_positions ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">单只持仓上限</span><br />{{ backtestStrategyConfig?.max_position_pct ? (backtestStrategyConfig.max_position_pct * 100).toFixed(0) + '%' : '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">卖出排名N</span><br />{{ backtestStrategyConfig?.sell_rank_n ?? '-' }}</v-col>
              </v-row>
            </v-card-text>
          </v-card>
        </v-window-item>

        <!-- Features Config Tab (New) -->
        <v-window-item value="features">
          <v-card variant="outlined" class="mb-4">
            <v-card-title class="text-subtitle-1 d-flex align-center">
              <v-icon start>mdi-chart-timeline-variant</v-icon> 特征字段
              <v-chip size="small" variant="flat" color="primary" class="ml-2">{{ backtestModelConfig?.feature_fields?.length || 0 }} 个</v-chip>
            </v-card-title>
            <v-divider />
            <v-card-text>
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
            </v-card-text>
          </v-card>

          <v-card variant="outlined" class="mb-4">
            <v-card-title class="text-subtitle-1 d-flex align-center">
              <v-icon start>mdi-ruler-square-compass</v-icon> 标准化字段
              <v-chip size="small" variant="flat" color="orange" class="ml-2">{{ backtestModelConfig?.standardize_fields?.length || 0 }} 个</v-chip>
            </v-card-title>
            <v-divider />
            <v-card-text>
              <template v-if="backtestModelConfig?.standardize_fields?.length">
                <div class="d-flex flex-wrap ga-1">
                  <v-chip v-for="f in backtestModelConfig.standardize_fields" :key="f" size="x-small" variant="flat" color="orange">{{ f }}</v-chip>
                </div>
              </template>
              <div v-else class="text-caption text-disabled">无配置</div>
            </v-card-text>
          </v-card>

          <v-card variant="outlined" class="mb-4">
            <v-card-title class="text-subtitle-1 d-flex align-center">
              <v-icon start>mdi-alpha-x-circle-outline</v-icon> 去极值字段
              <v-chip size="small" variant="flat" color="deep-purple" class="ml-2">{{ backtestModelConfig?.winsorize_fields?.length || 0 }} 个</v-chip>
            </v-card-title>
            <v-divider />
            <v-card-text>
              <template v-if="backtestModelConfig?.winsorize_fields?.length">
                <div class="d-flex flex-wrap ga-1">
                  <v-chip v-for="f in backtestModelConfig.winsorize_fields" :key="f" size="x-small" variant="flat" color="deep-purple">{{ f }}</v-chip>
                </div>
              </template>
              <div v-else class="text-caption text-disabled">无配置</div>
            </v-card-text>
          </v-card>
        </v-window-item>
      </v-window>
    </v-card-text>
  </v-card>
</v-dialog>
```

- [ ] **Step 2: Add backtestConfigTab ref**

Add in script section:
```typescript
const backtestConfigTab = ref('model')
```

- [ ] **Step 3: Verify TypeScript**

Run: `cd frontend && npx vue-tsc -b`
Expected: Exit code 0

- [ ] **Step 4: Commit**

---

### Task 3: Rebuild training config dialog

**Files:**
- Modify: `frontend/src/views/TrainingRecordsView.vue`

- [ ] **Step 1: Add the same BASIC_FIELD_NAMES utility**

Add after imports:
```typescript
const BASIC_FIELD_NAMES = new Set([
  'open', 'high', 'low', 'close', 'vol', 'amount',
  'pct_chg',
  'week_open', 'week_high', 'week_low', 'week_close',
  'week_vol_avg', 'week_amount_avg',
  'candle_body_pct', 'candle_upper_pct', 'candle_lower_pct',
])

const isBasicField = (name: string) => BASIC_FIELD_NAMES.has(name)
```

- [ ] **Step 2: Replace training config dialog template**

Replace the `v-dialog` for trainingConfigDialog with the new 2-tab layout:

```html
<v-dialog v-model="trainingConfigDialog.show" max-width="800" scrollable>
  <v-card>
    <v-toolbar flat>
      <v-toolbar-title>训练配置</v-toolbar-title>
      <v-spacer />
      <v-btn icon variant="text" @click="trainingConfigDialog.show = false">
        <v-icon>mdi-close</v-icon>
      </v-btn>
    </v-toolbar>
    <v-tabs v-model="trainingConfigTab" bg-color="surface">
      <v-tab value="model">模型配置</v-tab>
      <v-tab value="features">特征配置</v-tab>
    </v-tabs>
    <v-divider />
    <v-card-text>
      <v-window v-model="trainingConfigTab">
        <!-- Model Config Tab -->
        <v-window-item value="model">
          <v-card variant="outlined" class="mb-4">
            <v-card-title class="text-subtitle-1 d-flex align-center">
              <v-icon start>mdi-information-outline</v-icon> 基本信息
            </v-card-title>
            <v-divider />
            <v-card-text>
              <v-row>
                <v-col cols="6" class="py-1"><span class="text-caption text-medium-emphasis">名称</span><br />{{ trainingConfigData?.name || '-' }}</v-col>
                <v-col cols="6" class="py-1"><span class="text-caption text-medium-emphasis">模型类型</span><br />{{ trainingConfigData?.model_type || '-' }}</v-col>
                <v-col cols="6" class="py-1"><span class="text-caption text-medium-emphasis">创建时间</span><br />{{ trainingConfigData?.created_at ? new Date(trainingConfigData.created_at).toLocaleString() : '-' }}</v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <v-card variant="outlined" class="mb-4">
            <v-card-title class="text-subtitle-1 d-flex align-center">
              <v-icon start>mdi-tune</v-icon> 训练参数
            </v-card-title>
            <v-divider />
            <v-card-text>
              <v-row>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">分类周期</span><br />{{ trainingConfigData?.classification_horizons?.join(', ') || '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">标签模式</span><br />{{ trainingConfigData?.label_mode || '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">验证集比例</span><br />{{ trainingConfigData?.val_size ?? '-' }}</v-col>
              </v-row>
              <v-divider class="my-2" />
              <div class="text-caption text-medium-emphasis mb-1">阈值</div>
              <v-row>
                <v-col v-for="(v, k) in trainingConfigData?.thresholds" :key="k" cols="4" class="py-1">
                  <span class="text-caption text-medium-emphasis">{{ k }}</span><br />{{ v }}
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <v-card v-if="trainingConfigData?.model_type === 'xgboost'" variant="outlined" class="mb-4">
            <v-card-title class="text-subtitle-1 d-flex align-center">
              <v-icon start>mdi-chart-line</v-icon> XGB 参数
            </v-card-title>
            <v-divider />
            <v-card-text>
              <v-row>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Learning Rate</span><br />{{ trainingConfigData?.xgb_learning_rate ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Max Depth</span><br />{{ trainingConfigData?.xgb_max_depth ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Subsample</span><br />{{ trainingConfigData?.xgb_subsample ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Colsample By Tree</span><br />{{ trainingConfigData?.xgb_colsample_bytree ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Min Child Weight</span><br />{{ trainingConfigData?.xgb_min_child_weight ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">N Estimators</span><br />{{ trainingConfigData?.xgb_n_estimators ?? '-' }}</v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <v-card v-if="trainingConfigData?.model_type === 'lstm'" variant="outlined" class="mb-4">
            <v-card-title class="text-subtitle-1 d-flex align-center">
              <v-icon start>mdi-neural</v-icon> LSTM 参数
            </v-card-title>
            <v-divider />
            <v-card-text>
              <v-row>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Hidden Size</span><br />{{ trainingConfigData?.lstm_hidden_size ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Num Layers</span><br />{{ trainingConfigData?.lstm_num_layers ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Dropout</span><br />{{ trainingConfigData?.lstm_dropout ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Epochs</span><br />{{ trainingConfigData?.lstm_epochs ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Batch Size</span><br />{{ trainingConfigData?.lstm_batch_size ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Learning Rate</span><br />{{ trainingConfigData?.lstm_learning_rate ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Sequence Length</span><br />{{ trainingConfigData?.lstm_sequence_length ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Norm Window</span><br />{{ trainingConfigData?.lstm_normalization_window ?? '-' }}</v-col>
                <v-col cols="4" class="py-1"><span class="text-caption text-medium-emphasis">Weight Decay</span><br />{{ trainingConfigData?.lstm_weight_decay ?? '-' }}</v-col>
              </v-row>
            </v-card-text>
          </v-card>
        </v-window-item>

        <!-- Features Config Tab -->
        <v-window-item value="features">
          <v-card variant="outlined" class="mb-4">
            <v-card-title class="text-subtitle-1 d-flex align-center">
              <v-icon start>mdi-chart-timeline-variant</v-icon> 特征字段
              <v-chip size="small" variant="flat" color="primary" class="ml-2">{{ trainingConfigData?.feature_fields?.length || 0 }} 个</v-chip>
            </v-card-title>
            <v-divider />
            <v-card-text>
              <template v-if="trainingConfigData?.feature_fields?.length">
                <div class="text-caption text-medium-emphasis mb-1">日线基础字段</div>
                <div class="d-flex flex-wrap ga-1 mb-3">
                  <v-chip v-for="f in trainingConfigData.feature_fields.filter(isBasicField)" :key="f" size="x-small" variant="flat" color="indigo">{{ f }}</v-chip>
                  <span v-if="!trainingConfigData.feature_fields.filter(isBasicField).length" class="text-caption text-disabled">无</span>
                </div>
                <div class="text-caption text-medium-emphasis mb-1">技术指标字段</div>
                <div class="d-flex flex-wrap ga-1">
                  <v-chip v-for="f in trainingConfigData.feature_fields.filter(f => !isBasicField(f))" :key="f" size="x-small" variant="flat" color="teal">{{ f }}</v-chip>
                  <span v-if="!trainingConfigData.feature_fields.filter(f => !isBasicField(f)).length" class="text-caption text-disabled">无</span>
                </div>
              </template>
              <div v-else class="text-caption text-disabled">无特征字段配置</div>
            </v-card-text>
          </v-card>

          <v-card variant="outlined" class="mb-4">
            <v-card-title class="text-subtitle-1 d-flex align-center">
              <v-icon start>mdi-ruler-square-compass</v-icon> 标准化字段
              <v-chip size="small" variant="flat" color="orange" class="ml-2">{{ trainingConfigData?.standardize_fields?.length || 0 }} 个</v-chip>
            </v-card-title>
            <v-divider />
            <v-card-text>
              <template v-if="trainingConfigData?.standardize_fields?.length">
                <div class="d-flex flex-wrap ga-1">
                  <v-chip v-for="f in trainingConfigData.standardize_fields" :key="f" size="x-small" variant="flat" color="orange">{{ f }}</v-chip>
                </div>
              </template>
              <div v-else class="text-caption text-disabled">无配置</div>
            </v-card-text>
          </v-card>

          <v-card variant="outlined" class="mb-4">
            <v-card-title class="text-subtitle-1 d-flex align-center">
              <v-icon start>mdi-alpha-x-circle-outline</v-icon> 去极值字段
              <v-chip size="small" variant="flat" color="deep-purple" class="ml-2">{{ trainingConfigData?.winsorize_fields?.length || 0 }} 个</v-chip>
            </v-card-title>
            <v-divider />
            <v-card-text>
              <template v-if="trainingConfigData?.winsorize_fields?.length">
                <div class="d-flex flex-wrap ga-1">
                  <v-chip v-for="f in trainingConfigData.winsorize_fields" :key="f" size="x-small" variant="flat" color="deep-purple">{{ f }}</v-chip>
                </div>
              </template>
              <div v-else class="text-caption text-disabled">无配置</div>
            </v-card-text>
          </v-card>
        </v-window-item>
      </v-window>
    </v-card-text>
  </v-card>
</v-dialog>
```

- [ ] **Step 3: Add trainingConfigTab ref**

Add in script:
```typescript
const trainingConfigTab = ref('model')
```

- [ ] **Step 4: Verify TypeScript**

Run: `cd frontend && npx vue-tsc -b`
Expected: Exit code 0

- [ ] **Step 5: Commit**

---

### Task 4: Verify build

- [ ] **Step 1: Run full TypeScript check**

Run: `cd frontend && npx vue-tsc -b`
Expected: Exit code 0, no errors

- [ ] **Step 2: Run Vite build**

Run: `cd frontend && npx vite build`
Expected: Exit code 0, built successfully

- [ ] **Step 3: Run E2E tests**

Run: `cd frontend && python -m pytest e2e/tests/ -v`
Expected: All tests pass (except known pre-existing failures)

- [ ] **Step 4: Final commit and push**

```bash
git add frontend/src/views/BacktestRecordsView.vue frontend/src/views/TrainingRecordsView.vue
git commit -m "feat: enhance config dialogs with card layout and feature fields"
git push
```