# 选股参数配置 + 持仓保护设计方案

## 概述

两个独立但相关的改动：
1. 将动量选股算法参数（指标权重、improvement_weight）从硬编码改为 StrategyConfig 可配置
2. 新增持仓保护开关，让持仓股在候选池中保持评分和排名

## 一、StrategyConfig 新增字段

```python
class StrategyConfig(Document):
    # ... 现有字段 ...

    # 选股参数（动量指标权重，None 时使用代码默认值）
    momentum_fields_weights: Optional[Dict[str, float]] = None
    # 默认: {"trend_slope_20": 1.0, "trend_arrangement_20": 1.0,
    #        "close_position_20": 1.0, "close_position_60": 1.0,
    #        "bias_20": 1.0, "bias_60": 1.0, "atr_14": 0.3}
    log_mv_weight: float = 1.0
    improvement_weight: float = 0.2

    # 持仓保护：持仓股始终留在候选池中，确保有评分和排名
    use_hold_protection: bool = False
```

## 二、选股参数传递路径

```
策略配置 → API → MongoDB
  ↓ 加载
Pipeline 创建 CandidateListProvider
  ↓ 传入 params dict
Provider._get_momentum_stocks() 读取 self._range_n 等
  ↓ 改为从 strategy_config 读取权重
```

### 2.1 Provider 初始化

当前 `CandidateListProvider.__init__(params)` 接收 `range_n/top_n/momentum_n`。改为直接接收 `strategy_config`：

```python
def __init__(self, params: dict, strategy_config: Optional[StrategyConfig] = None):
    self._ts_codes: Optional[List[str]] = params.get("ts_codes")
    self._range_n: int = params.get("range_n", 300)
    self._top_n: int = params.get("top_n", 100)
    self._momentum_n: int = params.get("momentum_n", 20)
    # 选股权重从 strategy_config 读取
    if strategy_config:
        self._momentum_fields_weights = strategy_config.momentum_fields_weights
        self._log_mv_weight = strategy_config.log_mv_weight
        self._improvement_weight = strategy_config.improvement_weight
    else:
        self._momentum_fields_weights = None
        self._log_mv_weight = 1.0
        self._improvement_weight = 0.2
```

### 2.2 Pipeline 传入 strategy_config

```python
# backtest_pipeline.py 中创建 provider 时
provider = CandidateListProvider(params, strategy_config)
```

### 2.3 _get_momentum_stocks 使用配置权重

```python
# 从 self 读取权重替代硬编码
field_weights = self._momentum_fields_weights or DEFAULT_FIELD_WEIGHTS
LOG_MV_WEIGHT = self._log_mv_weight
IMPROVEMENT_WEIGHT = self._improvement_weight
```

## 三、持仓保护实现

### 3.1 核心逻辑

持仓股被候选池排除时，不是因为它们不好，而是选股逻辑没选中。但它们仍然被策略持有，需要评分排名来做卖出决策。

**修改点：每日循环中构建 scored_stocks 时，将持仓股加入候选列表**

```python
# 当前 daily loop:
candidates = provider.get_candidates_for_date(date)
candidate_close = {k: v for k, v in close_prices.items() if k in candidates}

# 改后（enable 时）:
candidates = provider.get_candidates_for_date(date)
if strategy_config.use_hold_protection:
    hold_codes = set(ctx.portfolio.positions.keys())
    # 将持仓股也纳入评分池
    all_scored_codes = set(candidates) | hold_codes
    candidate_close = {k: v for k, v in close_prices.items() if k in all_scored_codes}
else:
    candidate_close = {k: v for k, v in close_prices.items() if k in candidates}
```

### 3.2 _detect_outdated_positions 同步调整

当 `use_hold_protection` 开启时，跳过持仓股：

```python
def _detect_outdated_positions(self, date, close_prices, candidates):
    sell_orders = []
    for ts_code, pos in list(self.portfolio.positions.items()):
        if ts_code not in candidates:
            # 持仓保护开启时，持仓股不强制退出
            if self.strategy_config.use_hold_protection:
                continue
            # ... 原有逻辑
```

### 3.3 效果

开启后：
- 持仓股即使落选，继续有评分和排名
- 策略通过 `hold_score_low`、`stop_loss` 等正常机制卖出
- 不会触发 `candidate_excluded` 强制卖出
- 避免"候选池刚刷新就强卖，错过反弹"的问题

## 四、后端 API 改动

| 文件 | 改动 |
|------|------|
| `dao/strategy_config.py` | 新增 4 个字段 |
| `api/schemas.py` | StrategyCreateRequest、UpdateRequest 新增字段 |
| `strategy/service.py` | create_strategy、update_strategy 传递新字段 |
| `api/routers/strategy_config.py` | _strategy_to_dict 序列化新字段 |

## 五、前端改动

### 5.1 api/strategyConfig.ts

Strategy 接口新增字段。

### 5.2 StrategyConfigView.vue

新增 Tab "选股配置"：

```
┌─ 基本配置 ─┬─ 多股票配置 ─┬─ 市场分析 ─┬─ 轮动参数 ─┬─ 排名优化 ─┬─ 交易优化 ─┬─ 选股配置 ─┐
│                                                                             │
│  趋势斜率       权重: [1.0  ]                                               │
│  均线排列       权重: [1.0  ]                                               │
│  收盘位置20     权重: [1.0  ]                                               │
│  收盘位置60     权重: [1.0  ]                                               │
│  乖离率20       权重: [1.0  ]                                               │
│  乖离率60       权重: [1.0  ]                                               │
│  ATR 14         权重: [0.3  ]  (越低越好)                                   │
│  对数市值       权重: [1.0  ]                                               │
│                                                                             │
│  改进权重: [0.20 ]                                                          │
│                                                                             │
│  ☐ 持仓保护（持仓股不退出候选池）                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

配置对比（diff 弹窗）中增加新 tab 字段的比较。

### 5.3 BacktestManageView.vue

不变。range_n/top_n/momentum_n 仍作为回测入参。

## 六、改动范围清单

| 文件 | 改动类型 |
|------|---------|
| `backend/.../dao/strategy_config.py` | 新增字段 |
| `backend/.../api/schemas.py` | 新增字段 |
| `backend/.../strategy/service.py` | 传递新字段 |
| `backend/.../api/routers/strategy_config.py` | 序列化新字段 |
| `backend/.../execution/candidate_list_provider.py` | 读取配置权重替代硬编码 |
| `backend/.../execution/backtest_pipeline.py` | 持仓保护逻辑 |
| `frontend/.../api/strategyConfig.ts` | 接口类型 |
| `frontend/.../views/StrategyConfigView.vue` | 新 tab + 字段 + 对比 |
