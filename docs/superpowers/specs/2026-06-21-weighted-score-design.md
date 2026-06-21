# Weighted Score — 预测分数外部因子加权

## 背景

策略的预测分数（`composite_score`）是模型的原始输出，未考虑市值等外部因素。分析显示，同样的预测涨幅在大市值股票上更可靠，小市值股票的高波动性容易导致追高后止损。

通过引入可配置的外部因子（当前仅 log 市值），对预测分数进行加权，让大市值股票的分数更可信，降低小市值波动对决策的干扰。

## 设计要点

### 1. 新增配置字段

后端 `StrategyConfig` DAO：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|:------:|------|
| `use_weighted_score` | bool | `false` | 是否启用加权（开关） |
| `weighted_score_factor` | float | `0.2` | 外部因子权重 |

### 2. 新增分数段

`ScoredStock` (schemas.py)：

```python
weighted_score: float = 0.0  # 经外部因子加权后的分数，用于决策
```

`weighted_score` 命名通用化，不绑定具体加权因子（未来可扩展其他因子）。

### 3. 决策链路替换

| 环节 | 原用字段 | 改为 |
|------|---------|------|
| `smooth_scores` → `ranking_score` | `composite_score` | `weighted_score` |
| `hold_score_low`/`score_below_sell` | `composite_score` | `weighted_score`（通过 `score_map`） |
| 买入 `buy_threshold` | `composite_score` | `weighted_score` |
| 排名 `record_ranking_scores` | `ranking_score` | 代码不变，但 `ranking_score` 的输入变为 `weighted_score`，所以排名效果受加权影响 |
| 持久化 | `composite_score` | 保留 + 新增 `weighted_score` 作为独立字段 |

`composite_score` 原样保留，仅用于记录和分析对比。所有决策逻辑基于 `weighted_score`。

### 4. 加权计算公式

```
log_mv 归一化: norm = (log_mv - min) / (max - min)     → [0, 1]
weighted_score = composite_score × (1 + factor × norm)  → 大市值放大，小市值不变
```

开关关闭时：`weighted_score = composite_score`。

### 5. DataLoader 缓存

新增 `_mv_cache: Dict[str, Dict[str, float]]`，格式 `{trade_date: {ts_code: log_mv}}`。

新增方法 `load_market_cap(date, ts_codes)`：
- 按 `(trade_date, ts_codes)` 批量查询 `StockListHistory`
- 计算 log(total_mv) 后缓存
- ScoreManager 每日调用一次

### 6. 前后端适配

按现有 pattern：

| 层 | 文件 | 改动 |
|----|------|------|
| DAO | `dao/strategy_config.py` | 加 `use_weighted_score` + `weighted_score_factor` |
| Schema | `schemas.py` (ScoredStock) | 加 `weighted_score: float = 0.0` |
| 评分 | `execution/scoring.py` | 新增 `_apply_mv_weight()` + 在 `predict_and_score()` 中调用 |
| 平滑 | `execution/scoring.py` | `smooth_scores()` 改用 `weighted_score` |
| DataLoader | `execution/data_loader.py` | 加 `_mv_cache` + `load_market_cap()` |
| API Schema | `api/schemas.py` | CreateRequest + UpdateRequest 加字段 |
| API Router | `api/routers/strategy_config.py` | 序列化 + 传参 |
| Service | `strategy/service.py` | 创建/更新赋值 |
| 前端 API | `api/strategyConfig.ts` | 类型定义 |
| 前端 UI | `StrategyConfigView.vue` | 选股配置 tab 加开关 + 权重输入 + 配置对比 |

### 7. 数据流

```
ScoreManager.predict_and_score()
  → compute_scores()           → pred_results["score"]
  → apply_trend_*              → pred_results["composite_score"]
  → _apply_mv_weight()         → pred_results["weighted_score"]
  → smooth_scores()            → pred_results["ranking_score"]  (基于 weighted_score)
  → record_ranking_scores()    → stock.rank                     (基于 ranking_score)
  → build ScoredStock           → stock.weighted_score, stock.composite_score (都持久化)
```
