# XGBoost 训练与回测数据处理

## 数据流总览

```
Tushare API（前复权日线）
  → StockDaily（MongoDB）
    → 指标计算（30 个技术指标）
      → 训练：多股票加载 → 分类标签 → 横截面标准化 → XGBoost 训练 → 模型文件
        → 回测：逐日加载 → 横截面标准化 → 批量预测 → 得分排序 → 策略决策 → 撮合成交
```

---

## 一、数据获取

### 1.1 数据源

通过 Tushare `ts.pro_bar(adj="qfq")` 获取前复权日线数据，字段包括：

| 字段 | 类型 | 说明 |
|------|------|------|
| `ts_code` | str | 股票代码（如 `002594.SZ`） |
| `trade_date` | str | 交易日期（YYYYMMDD） |
| `open` | float | 开盘价 |
| `high` | float | 最高价 |
| `low` | float | 最低价 |
| `close` | float | 收盘价（前复权） |
| `vol` | float | 成交量（手） |
| `amount` | float | 成交额（千元） |

### 1.2 存储

数据经过去重（`ts_code` + `trade_date`）和空值过滤（OHLCV 任一为 null 则跳过）后，存入 MongoDB `stock_daily` 集合。

### 1.3 数据同步

通过 APScheduler 定时任务自动同步：

**股票列表同步**（`scheduler/stock_list_sync_job.py`）：
- 每日凌晨 01:00 执行
- 从 Tushare 拉取最新股票列表，合并市值/PE/PB 数据
- 检测新增股票和新入排名股票，标记为 `pending`
- 已有数据的股票不会改变状态

**全量初始化同步**（`scheduler/stock_data_init_job.py`）：
- 每日凌晨 02:00 执行
- 仅处理 `sync_status == "pending"` 的股票
- 拉取全部历史数据 → 计算全部技术指标 → 更新为 `active`
- 可通过前端任务配置页设置 `stock_count`（股票数量）和 `data_years`（数据年限）参数

**每日增量更新**（`scheduler/daily_update_job.py`）：
- 每天 17:00 执行
- 仅处理 `sync_status == "active"` 的股票
- 自动补齐最新的交易日数据
- **除权检测**：每次拉取时会多查已有数据的最后一天，对比新拉的 close 是否一致
  - 不一致 → 发生除权除息 → 该股票标记为 `pending` → 等待全量同步重新拉取
- 限速 200次/分钟，顺序处理
- 写入新数据后立即计算新日期的技术指标

**状态流转**:
- `pending` → `active`：全量初始化同步处理
- `active` → `pending`：每日增量更新检测到除权
- `pending`（新增/新入排名）：股票列表同步标记

---

## 二、技术指标计算

### 2.1 指标列表（共 30 个）

| 类别 | 指标 | 字段名 | 计算方式 |
|------|------|--------|----------|
| 均线 | MA5/10/20/60 | `ma_5`, `ma_10`, `ma_20`, `ma_60` | `close.rolling(N).mean()` |
| MACD | DIF/DEA/Hist | `macd`, `macd_signal`, `macd_hist` | EMA12 - EMA26 / EMA9 |
| 涨跌幅 | 日涨跌幅 | `pct_chg` | `close.pct_change() * 100` |
| 乖离率 | BIAS5/10/20/60 | `bias_5`, `bias_10`, `bias_20`, `bias_60` | `(close - MA) / MA * 100` |
| 分位数 | Close Pct Rank | `close_pct_rank_5/10/20/60` | N 日内收盘价百分位排名 |
| 量比 | Vol Ratio | `vol_ratio_5/10/20/60` | `vol / vol_rolling_mean(N)` |
| KDJ | K/D/J | `kdj_k`, `kdj_d`, `kdj_j` | RSV(9) → K=SMA(3) → D=SMA(3) → J=3K-2D |
| 布林带 | Upper/Middle/Lower | `boll_upper`, `boll_middle`, `boll_lower` | MID=MA(20), ±2×STD(20) |
| 震荡类 | RSI6/12 | `rsi_6`, `rsi_12` | 100 - 100/(1+RS), RS=avg_gain/avg_loss |
| 波动率类 | ATR14 | `atr_14` | TR 的 14 日平滑均值 |
| 量能类 | OBV | `obv` | 累计价量配合指标 |

### 2.2 计算入口

`indicators/service.py` → `calculate_all_indicators(ts_code, start_date, end_date)` 统一调度上述所有指标计算，结果写回 `stock_daily` 文档。

支持指定日期范围（`start_date`/`end_date`），增量更新时只计算新日期的指标。

---

## 三、分类标签生成

### 3.1 标签定义

`training_service.py` → `_create_classification_labels()`

```python
# 对每只股票，按每 N 天未来涨跌幅生成标签
future_pct = (close_{t+N} - close_t) / close_t

label = +1   if future_pct >  threshold   # 涨
label = -1   if future_pct < -threshold   # 跌
label =  0   otherwise                     # 平
```

### 3.2 默认参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `classification_horizons` | `[3, 5]` | 预测 3 日和 5 日后涨跌 |
| `classification_threshold` | `0.02` | 涨跌幅超过 ±2% 才标记为涨/跌 |

### 3.3 标签生成逻辑

```
输入：多股票 DataFrame（含 close、ts_code、trade_date）
      horizons = [3, 5]
      threshold = 0.02

按 ts_code 分组：
  close.shift(-3) → 计算 3 日后涨跌幅 → label_3d ∈ {-1, 0, 1}
  close.shift(-5) → 计算 5 日后涨跌幅 → label_5d ∈ {-1, 0, 1}

末尾 N 行因无法计算未来涨跌幅，直接丢弃（dropna）
```

### 3.4 标签分布特点

- **不平衡三分类**：平盘（label=0）样本最多，涨/跌样本相对较少
- 每只股票独立计算，股票间标签分布可能因波动率不同而差异较大

---

## 四、横截面标准化

### 4.1 标准化器

`CrossSectionalNormalizer`（`predict/normalizers/cross_sectional.py`）

### 4.2 处理流程

```
输入：多股票同日 DataFrame（含 feature_fields + trade_date + ts_code）

按 trade_date 分组（横截面）：
  1. 可选：缩尾处理（winsorize）
     对每个字段，clip 到 [1%分位, 95%分位]
     默认不启用（winsorize_fields = []）

  2. Z-Score 标准化
     对每个字段：z = (x - mean) / std
     同一天的所有股票一起计算 mean 和 std

输出：feature_fields + target_names
```

### 4.3 关键特性

- **横截面**：同一交易日所有股票相互比较，消除市场整体波动的影响
- **NaN 保留**：不填充 NaN，XGBoost 原生支持缺失值
- **训练和预测使用相同的标准化逻辑**：确保特征分布一致

### 4.4 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `standardize_fields` | 等于 `feature_fields` | 需要 Z-score 的字段 |
| `winsorize_fields` | `[]`（空） | 需要缩尾的字段 |

**注意**：输出字段由 `feature_fields` + `classification_horizons` 动态生成。

---

## 五、XGBoost 模型训练

### 5.1 模型架构

`predict/models/xgboost.py` → `XGBoostClassifier`

**多标签分类器**：每个 horizon（3d / 5d）训练一个独立的 `XGBClassifier`。

### 5.2 超参数

| 参数 | 值 |
|------|-----|
| `n_estimators` | 100 |
| `max_depth` | 6 |
| `learning_rate` | 0.1 |
| `min_child_weight` | 1 |
| `subsample` | 1.0 |
| `colsample_bytree` | 1.0 |
| `eval_metric` | `mlogloss`（多分类对数损失） |

### 5.3 标签映射

原始标签 `{-1, 0, 1}` 映射到 XGBoost 内部索引 `{0, 1, 2}`：

```
label = -1  → 内部索引 0  → proba[0] = P(跌)
label =  0  → 内部索引 1  → proba[1] = P(平)
label =  1  → 内部索引 2  → proba[2] = P(涨)
```

`predict()` 时反向映射回原始标签，`predict_proba()` 返回 `[P(跌), P(平), P(涨)]`。

### 5.4 训练流程

`training_service.py` → `create_training()`

```
1. 校验 name 唯一性、config 存在、model_type 有效
2. 遍历 ts_codes：
   a. 检查 StockList.sync_status == "active"
   b. 加载 StockDaily（start_date ~ end_date）→ DataFrame
3. pd.concat 所有股票 → 按 trade_date + ts_code 排序
4. _create_classification_labels() → 生成 label_3d / label_5d
5. CrossSectionalNormalizer 标准化：
   - 输入：feature_fields + target_names + [trade_date, ts_code]
   - 按 trade_date 分组做横截面 Z-score
6. dropna → X(feature_fields) + y(target_names)
7. XGBoostClassifier.fit(X, y)
8. 保存模型到 models/{config_id}/{training_id}.pkl
9. 保存 TrainingResult 到 MongoDB
```

### 5.5 模型文件

```python
# 模型保存为 pickle，包含两个子模型和标签映射
{
    "models": {
        "label_3d": XGBClassifier,  # 3 日涨跌分类器
        "label_5d": XGBClassifier,  # 5 日涨跌分类器
    },
    "label_mapping": {
        "label_3d": {0: -1, 1: 0, 2: 1},
        "label_5d": {0: -1, 1: 0, 2: 1},
    }
}
```

---

## 六、回测预测

### 6.1 预测器

`execution/predictor.py` → `Predictor.predict_batch_with_history()`

### 6.2 逐日预测流程

```
输入：当日所有股票的 StockDaily DataFrame

1. 延迟加载模型和配置（首次调用时加载）
2. 对 day_df 做横截面标准化（与训练时相同的标准化器）
3. 对每只股票：
   a. 提取标准化后的 feature_fields → 检查 NaN（跳过）
   b. classifier.predict() → 分类标签（用于日志）
   c. classifier.predict_proba() → 三分类概率
   d. 计算得分（见 6.3）
4. 返回 {ts_code: {up_prob_3d, up_prob_5d, down_prob_3d, down_prob_5d, score, close}}
```

### 6.3 得分公式

```
score_3d = P(涨|3d) - P(跌|3d)
score_5d = P(涨|5d) - P(跌|5d)

score = score_3d × 0.4 + score_5d × 0.6
```

- 得分范围：`[-1, 1]`
- 正分表示模型看涨，负分表示看跌
- 5 日权重（0.6）高于 3 日（0.4）

### 6.4 与训练时标准化的一致性

训练和预测使用**完全相同的标准化逻辑**：
- 同一个 `CrossSectionalNormalizer` 实例
- 同一个 `standardize_fields` / `winsorize_fields` 配置
- 同一个 `feature_fields` 字段列表

区别仅在于：
- 训练时：对所有历史数据一次性标准化
- 预测时：对当日数据单独标准化（mean/std 仅基于当日股票池计算）

---

## 七、回测执行管线

### 7.1 完整流程

`execution/pipeline.py` → `ExecutionPipeline`

```
1. 创建 ExecutionResult(status="running")
2. 构建股票池（universe）：
   - sync_status == "active"
   - 排除 TEST_EXCLUDED_TS_CODES
   - 按 total_mv 降序取 top N（单股 200，组合 3000）
3. 逐日循环（start_date → end_date，跳过周末）：
   a. DataLoader.load_day_close() → 当日收盘价
   b. DataLoader.load_day_data() → 当日 StockDaily DataFrame
   c. Predictor.predict_batch_with_history() → 预测得分
   d. 构造 ScoredStock 列表
   e. 评分调整管线（按顺序执行）：
      i.  评分平滑（EWMA）：_smooth_scores()
      ii. 趋势加分：_apply_trend_bonus()
          基于收盘价 R² 加权线性回归，稳定上涨趋势加分
      iii.波动扣分：_apply_volatility_penalty()
          基于日内振幅比（OHLC），大起大落扣分
      iv. 动量加成：_apply_momentum_boost()
          基于收盘价日涨跌比，连续上涨天数加分
      v.  暴涨排除：_filter_explosions()
          放量暴涨/暴跌标记排除，不参与排名
      vi. 记录排名：_record_ranks()
          按最终分从高到低排序
   f. Strategy.make_decisions() → PendingOrder
   g. Strategy.settle_orders() → ExecutionTrade + 更新现金/持仓
   h. Strategy.daily_snapshot() → ExecutionDailySnapshot（含 predictions）
4. 计算最终指标 → 更新 ExecutionResult(status="completed")
```

### 7.2 数据快照

每日快照 `ExecutionDailySnapshot.predictions` 存储：

```python
{
    ts_code: {
        "score": float,              # 最终综合评分（含所有调整）
        "raw_score": float,          # 原始评分（模型直接输出）
        "composite_score": float,    # 综合评分（同 score）
        "rank": int,                 # 当日排名
        "momentum_bonus": float,     # 动量加成值
        "trend_bonus": float,        # 趋势加分值
        "vol_penalty": float,        # 波动扣分值
        "up_prob_3d": float,         # 3日上涨概率
        "up_prob_5d": float,         # 5日上涨概率
        "down_prob_3d": float,       # 3日下跌概率
        "down_prob_5d": float,       # 5日下跌概率
        "close": float,              # 当日收盘价
    }
}
```

### 7.3 回测指标

| 指标 | 计算方式 |
|------|----------|
| `total_return` | `(final_value - initial_capital) / initial_capital` |
| `max_drawdown` | 最大回撤 |
| `win_rate` | 盈利交易 / 总交易 |
| `sharpe_ratio` | 日收益均值 / 日收益标准差 × √252 |
| `volatility` | 日收益标准差 |
| `baseline_return` | 买入持有策略收益（单股模式） |
| `excess_return` | `total_return - baseline_return` |
| `avg_hold_days` | 平均持仓天数 |

---

## 八、配置参数速查

### 8.1 模型配置（ModelConfig）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `model_type` | `"xgboost"` | 模型类型 |
| `feature_fields` | 26 个指标 | 输入特征 |
| `classification_horizons` | `[3, 5]` | 预测周期 |
| `classification_threshold` | `0.02` | 涨跌阈值（±2%） |
| `standardize_fields` | 等于 feature_fields | Z-score 字段 |
| `winsorize_fields` | `[]` | 缩尾字段（不启用） |

### 8.2 XGBoost 超参

| 参数 | 值 |
|------|-----|
| `n_estimators` | 100 |
| `max_depth` | 6 |
| `learning_rate` | 0.1 |
| `eval_metric` | `mlogloss` |

### 8.3 得分权重

| 周期 | 权重 |
|------|------|
| 3 日 | 0.4 |
| 5 日 | 0.6 |

---

## 九、文件索引

| 模块 | 文件 | 职责 |
|------|------|------|
| 数据获取 | `data/fetcher.py` | Tushare API 调用 |
| 数据存储 | `data/service.py` | 数据写入 MongoDB |
| 指标计算 | `indicators/service.py` | 30 个指标统一计算入口 |
| 模型配置 | `predict/config_service.py` | 配置 CRUD + 默认值 |
| 标准化 | `predict/normalizers/cross_sectional.py` | 横截面 Z-score |
| 标签生成 | `predict/training_service.py` | 分类标签 + 训练流程 |
| XGBoost | `predict/models/xgboost.py` | 多标签分类器 |
| 预测器 | `execution/predictor.py` | 批量预测 + 得分计算 |
| 数据加载 | `execution/data_loader.py` | 逐日数据查询 |
| 回测管线 | `execution/pipeline.py` | 回测执行主流程 |
| 训练 API | `api/routers/trainings.py` | 训练任务接口 |
| 回测 API | `api/routers/backtest.py` | 回测任务接口 |
| 训练脚本 | `scripts/train_model.py` | 命令行训练入口 |