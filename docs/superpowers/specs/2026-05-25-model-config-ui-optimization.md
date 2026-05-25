# 模型配置弹窗 UI 优化设计

## 概述

优化模型配置弹窗的用户体验，包括标签页分组、参数提示文本、不同模型的默认值差异化。

## 需求

1. **标签页分组**：将参数配置和字段配置拆分为两个标签页
2. **参数提示**：为每个参数添加简短中文说明（helper text）
3. **差异化默认值**：XGBoost 和 LSTM 推荐不同的标准化/缩尾字段

## 设计方案

### 1. 标签页结构

弹窗宽度从 `800px` 增加到 `900px`。

```
┌─────────────────────────────────────────────────────────────────┐
│ 编辑配置                                [x]                    │
├─────────────────────────────────────────────────────────────────┤
│ 模型类型: [xgboost ▼]   配置名称: [______________]              │
├─────────────────────────────────────────────────────────────────┤
│ [字段配置] [参数配置]                                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ （标签页内容）                                                  │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ [取消]                                      [保存]              │
└─────────────────────────────────────────────────────────────────┘
```

**标签页 1：字段配置**
- 特征字段
- 标准化字段
- 缩尾字段

**标签页 2：参数配置**
- 训练标签参数（预测周期、涨跌阈值）
- 模型超参数（XGBoost/LSTM 条件显示）

### 2. 参数提示文本

#### XGBoost 参数（顺序调整后）

| 参数 | 提示文本 |
|------|---------|
| `n_estimators` | 树的数量，值越大越准确但越慢 |
| `max_depth` | 树的最大深度，控制复杂度 |
| `min_child_weight` | 叶子节点最小权重和 |
| `learning_rate` | 每棵树的贡献权重 |
| `subsample` | 训练样本采样比例 |
| `colsample_bytree` | 特征采样比例 |

#### LSTM 参数（顺序调整后）

| 参数 | 提示文本 |
|------|---------|
| `hidden_size` | 隐藏层维度，控制模型容量 |
| `num_layers` | LSTM 层数 |
| `dropout` | Dropout 比例，防止过拟合 |
| `sequence_length` | 输入序列长度（天数） |
| `normalization_window` | 标准化统计窗口（天数） |
| `epochs` | 最大训练轮数 |
| `batch_size` | 每批训练样本数 |
| `learning_rate` | 学习率 |
| `early_stopping_patience` | 验证 AUC 不提升时停止的轮数 |

### 3. 差异化默认值

#### 字段分类

**受价格绝对值影响的字段（需要标准化）**：
```
ma_5, ma_10, ma_20, ma_60,
macd, macd_signal, macd_hist,
boll_upper, boll_middle, boll_lower
```

**相对值字段（不需要标准化）**：
```
pct_chg,
bias_5, bias_10, bias_20, bias_60,
close_position_5, close_position_10, close_position_20, close_position_60,
vol_ratio_5, vol_ratio_10, vol_ratio_20, vol_ratio_60,
kdj_k, kdj_d, kdj_j,
boll_position,
rsi_6, rsi_12,
trend_arrangement_5, trend_arrangement_10, trend_arrangement_20,
trend_slope_5, trend_slope_10, trend_slope_20,
trend_volume_5, trend_volume_10, trend_volume_20,
trend_stability_5, trend_stability_10, trend_stability_20,
obv,
candle_body_pct, candle_upper_pct, candle_lower_pct,
close_location_pct, gap_pct, gap_fill_pct
```

#### XGBoost 推荐默认值
```javascript
{
  feature_fields: [...priceIndependentFields],
  standardize_fields: [...indicatorFields], // 全部指标字段
  winsorize_fields: [...indicatorFields],   // 全部指标字段
}
```

#### LSTM 推荐默认值
```javascript
{
  feature_fields: [...lstmRecommendedFeatureFields],
  standardize_fields: [ // 仅受价格绝对值影响的字段
    'ma_5', 'ma_10', 'ma_20', 'ma_60',
    'macd', 'macd_signal', 'macd_hist',
    'boll_upper', 'boll_middle', 'boll_lower'
  ],
  winsorize_fields: [ // 同上
    'ma_5', 'ma_10', 'ma_20', 'ma_60',
    'macd', 'macd_signal', 'macd_hist',
    'boll_upper', 'boll_middle', 'boll_lower'
  ],
}
```

## 实现要点

1. 使用 Vuetify 的 `v-tabs` 组件实现标签页
2. 使用 `v-text-field` 的 `helper-text` 属性展示参数说明
3. 在 `lstmRecommendedParams` 中新增 `lstmAffectedByPriceFields` 常量
4. 编辑配置时也要正确加载 `early_stopping_patience` 字段

## 修改文件

- [frontend/src/views/ModelConfigView.vue](file:///d:/projects/trade-alpha/frontend/src/views/ModelConfigView.vue)
