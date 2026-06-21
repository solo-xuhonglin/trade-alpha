# 选股参数配置 + 持仓保护设计方案

## 概述

两个独立但相关的改动：
1. 将动量选股算法参数（各指标权重、排名上升权重）从硬编码改为 StrategyConfig 可配置
2. 新增持仓保护开关，让持仓股在候选池中保持评分和排名

## 一、StrategyConfig 新增字段

所有选股权重统一加 `sel_` 前缀，便于前端分组和代码识别：

```python
class StrategyConfig(Document):
    # ... 现有字段（无改动）...

    # ── 选股参数 ──
    sel_trend_slope_weight: float = 1.0           # trend_slope_20 权重
    sel_trend_arrangement_weight: float = 1.0     # trend_arrangement_20 权重
    sel_close_position_20_weight: float = 1.0     # close_position_20 权重
    sel_close_position_60_weight: float = 1.0     # close_position_60 权重
    sel_bias_20_weight: float = 1.0               # bias_20 权重
    sel_bias_60_weight: float = 1.0               # bias_60 权重
    sel_atr_14_weight: float = 0.3                # atr_14 权重（越低越好）
    sel_log_mv_weight: float = 1.0                # log(总市值) 权重
    sel_rank_rise_weight: float = 0.2             # 排名上升权重（选股时评分改善占比）

    # ── 持仓保护 ──
    use_hold_protection: bool = False
    # 开启后：持仓股即使落选候选池，继续保留在评分池中
    # 策略通过 hold_score_low / stop_loss 等正常机制卖出
    # 不会触发 candidate_excluded 强制卖出
```

### 默认值说明

所有默认值与当前 `candidate_list_provider.py` 中的硬编码值一致，新配置未设置时行为不变。

## 二、选股参数传递路径

```
策略配置 → API → MongoDB
  ↓ 加载
Pipeline 创建 CandidateListProvider
  ↓ 传入 strategy_config（必有值，无需判空）
Provider 直接读取 self._strategy_config.sel_xxx 权重
```

### 2.1 Provider 初始化

```python
def __init__(self, params: dict, strategy_config: StrategyConfig):
    self._ts_codes: Optional[List[str]] = params.get("ts_codes")
    self._range_n: int = params.get("range_n", 300)
    self._top_n: int = params.get("top_n", 100)
    self._momentum_n: int = params.get("momentum_n", 20)

    # 选股权重直接从 strategy_config 读取（配置一定有值）
    self._strategy_config = strategy_config
```

### 2.2 Pipeline 传入

```python
# backtest_pipeline.py 中创建 provider 时
provider = CandidateListProvider(params, strategy_config)
```

### 2.3 _get_momentum_stocks 使用配置权重

```python
cfg = self._strategy_config
MOMENTUM_FIELDS = [
    ("trend_slope_20", True, cfg.sel_trend_slope_weight),
    ("trend_arrangement_20", True, cfg.sel_trend_arrangement_weight),
    ("close_position_20", True, cfg.sel_close_position_20_weight),
    ("close_position_60", True, cfg.sel_close_position_60_weight),
    ("bias_20", True, cfg.sel_bias_20_weight),
    ("bias_60", True, cfg.sel_bias_60_weight),
    ("atr_14", False, cfg.sel_atr_14_weight),
]
LOG_MV_WEIGHT = cfg.sel_log_mv_weight
# 排名上升权重：选中时 final = (1-w)*abs_score + w*rank_rise
RANK_RISE_WEIGHT = cfg.sel_rank_rise_weight
```

## 三、持仓保护实现

### 3.1 每日评分池扩展

持仓股被候选池排除时，仍然需要评分和排名来做出卖出决策。修改点：每日循环中构建 `candidate_close` 时，将持仓股加入评分列表。

```python
# 当前：
candidates = provider.get_candidates_for_date(date)
candidate_close = {k: v for k, v in close_prices.items() if k in candidates}

# 改后：
candidates = provider.get_candidates_for_date(date)
if self.strategy_config.use_hold_protection:
    hold_codes = set(ctx.portfolio.positions.keys())
    all_scored = set(candidates) | hold_codes
    candidate_close = {k: v for k, v in close_prices.items() if k in all_scored}
else:
    candidate_close = {k: v for k, v in close_prices.items() if k in candidates}
```

### 3.2 候选池排除跳过

`_detect_outdated_positions` 中，开启保护时跳过持仓股：

```python
def _detect_outdated_positions(self, date, close_prices, candidates):
    sell_orders = []
    for ts_code, pos in list(self.portfolio.positions.items()):
        if ts_code not in candidates:
            if self.strategy_config.use_hold_protection:
                continue
            # ... 原有强卖逻辑
```

### 3.3 效果

- 持仓股始终有评分和排名 → 策略可通过 `hold_score_low` / `stop_loss` 等正常卖出
- 不会触发 `candidate_excluded` 强制卖出
- 等策略自己判断需要卖出后才自然退出候选池

## 四、后端 API 改动

| 文件 | 改动 |
|------|------|
| `dao/strategy_config.py` | 新增 10 个字段 |
| `api/schemas.py` | StrategyCreateRequest、UpdateRequest 新增字段 |
| `strategy/service.py` | create_strategy、update_strategy 传递新字段 |
| `api/routers/strategy_config.py` | _strategy_to_dict 序列化新字段 |
| `execution/candidate_list_provider.py` | 接收 strategy_config，使用配置权重 |
| `execution/backtest_pipeline.py` | 持仓保护逻辑 |

## 五、前端改动

### 5.1 api/strategyConfig.ts

Strategy 接口新增 10 个字段。

### 5.2 StrategyConfigView.vue

新增 Tab "选股配置"：

```
┌─ 基本配置 ─┬─ 多股票配置 ─┬─ 市场分析 ─┬─ 轮动参数 ─┬─ 排名优化 ─┬─ 交易优化 ─┬─ 选股配置 ─┐
│                                                                             │
│  趋势斜率          权重 [1.0  ]                                             │
│  均线排列          权重 [1.0  ]                                             │
│  收盘位置(20日)    权重 [1.0  ]                                             │
│  收盘位置(60日)    权重 [1.0  ]                                             │
│  乖离率(20日)      权重 [1.0  ]                                             │
│  乖离率(60日)      权重 [1.0  ]                                             │
│  ATR(14日)         权重 [0.3  ]  (值越低越好)                               │
│  对数市值          权重 [1.0  ]                                             │
│                                                                             │
│  排名上升权重      [0.20 ]  (选股时评分改善的占比)                          │
│                                                                             │
│  ☐ 持仓保护（持仓股不退出候选池）                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

配置对比弹窗中增加新字段的比较。

### 5.3 BacktestManageView.vue

不变。range_n/top_n/momentum_n 仍作为回测入参。

## 六、改动范围清单

| 文件 | 改动类型 |
|------|---------|
| `backend/.../dao/strategy_config.py` | 新增 10 个字段 |
| `backend/.../api/schemas.py` | 新增字段 |
| `backend/.../strategy/service.py` | 传递新字段 |
| `backend/.../api/routers/strategy_config.py` | 序列化新字段 |
| `backend/.../execution/candidate_list_provider.py` | 接收 strategy_config，使用配置权重 |
| `backend/.../execution/backtest_pipeline.py` | 持仓保护逻辑 |
| `frontend/.../api/strategyConfig.ts` | 接口类型 |
| `frontend/.../views/StrategyConfigView.vue` | 新 tab + 字段 + 对比 |
