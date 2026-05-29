# Config Dialogs Enhancement Design

## Overview

Improve the backtest config dialog and training config dialog to display all three relevant configurations (model, strategy, feature fields) with a more polished card-based layout.

## Current State

Both dialogs use a simple key-value `v-table` with `{label, value}[]` rows. The backtest config has two tabs (model, strategy); the training config has only model config. The feature fields (`feature_fields`, `standardize_fields`, `winsorize_fields`) stored in the model config are not displayed at all.

## Design

### Backtest Config Dialog

3 tabs with card sections:

| Tab | Sections | Status |
|-----|----------|--------|
| **模型配置** | Basic info + Training params + Model-specific params (XGB/LSTM) | Existing, reorganized |
| **策略配置** | Strategy info + Trade rules + Position limits | Existing, reorganized |
| **特征配置** | Basic fields + Indicator fields + Preprocess fields | New |

### Training Config Dialog

2 tabs (no strategy config for training):

| Tab | Sections | Status |
|-----|----------|--------|
| **模型配置** | Same as backtest model tab | Existing, reorganized |
| **特征配置** | Same as backtest feature tab | New |

### Card Layout

Each tab contains multiple card-based sections:
- Section title with icon (e.g. `mdi-information-outline`, `mdi-tune`, `mdi-chart-timeline-variant`)
- Fields displayed as labeled values using chips or styled text
- Feature fields displayed as colored chips grouped by category

### Feature Fields Display

- `feature_fields`: displayed as chips, grouped into 日线基础字段 and 技术指标字段
- `standardize_fields`: displayed as chips with distinct color
- `winsorize_fields`: displayed as chips with distinct color
- Fields shown with original names (e.g. `ma_5`, `macd`, `rsi_6`)

### Field Organization

#### Model Config Tab

- **基本信息**: name, model_type, created_at
- **训练参数**: classification_horizons, label_mode, thresholds (3d/5d/10d), val_size
- **XGB 参数**: (if model_type === 'xgboost') xgb_learning_rate, xgb_max_depth, xgb_subsample, xgb_colsample_bytree, xgb_min_child_weight, xgb_n_estimators
- **LSTM 参数**: (if model_type === 'lstm') lstm_hidden_size, lstm_num_layers, lstm_dropout, lstm_epochs, lstm_batch_size, lstm_learning_rate, lstm_sequence_length, lstm_normalization_window, lstm_weight_decay

#### Strategy Config Tab

- **策略信息**: name, type
- **交易规则**: buy_threshold, sell_threshold, stop_loss_pct, max_hold_days, min_order_value
- **持仓限制**: max_positions, max_position_pct, sell_rank_n, hold_score_threshold

#### Feature Config Tab

- **特征字段**: feature_fields listed as chips, split into basic fields vs indicator fields
- **标准化字段**: standardize_fields chips
- **去极值字段**: winsorize_fields chips

## Files to Modify

- `frontend/src/views/BacktestRecordsView.vue` - backtest config dialog template and logic
- `frontend/src/views/TrainingRecordsView.vue` - training config dialog template and logic

## Non-Goals

- No new API endpoints
- No changes to backend
- No changes to feature selection logic