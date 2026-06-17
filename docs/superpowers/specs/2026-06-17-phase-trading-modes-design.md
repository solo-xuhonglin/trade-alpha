# Three Trading Modes: Trend / Mean Reversion / Defensive

## 1. 背景与动机

当前 `MultiStockStrategy` 只有一个买卖逻辑通道，使用 `position_multiplier`（down=0.5）机械控制仓位大小，买卖逻辑本身与市场状态无关。但用户需要的是**不同的交易行为**：

| 市场阶段 | 交易行为 | 仓位 | 说明 |
|----------|----------|------|------|
| up | 满仓追涨 | 1.0 | 当前逻辑，不动 |
| flat | 满仓均值回归 | 1.0 | 新增：评分反转后买入，均值回归后止盈 |
| down | 轻仓防御 | 0.3 | 改進：不买入，放宽卖出条件 |

## 2. 代码组织

```
strategy/
├── base.py                          # BaseStrategy（不碰）
├── single_stock.py                  # SingleStockStrategy（不碰）
├── multi_stock_strategy.py          # 修改：入口根据 phase 选择 mode
└── modes/
    ├── __init__.py
    ├── base.py                      # PhaseMode 基类
    ├── trend_mode.py                # up：现有逻辑提取
    ├── mean_reversion_mode.py       # flat：均值回归
    └── defensive_mode.py            # down：不买入 + 宽松卖出
```

### 2.1 PhaseMode 基类

```python
class PhaseMode(ABC):
    def __init__(self, strategy: "MultiStockStrategy"):
        self._strategy = strategy

    @abstractmethod
    def run(
        self,
        scored_stocks: List[ScoredStock],
        trade_date: str,
        portfolio: PortfolioManager,
        close_prices: Dict[str, float],
        market_data: MarketDataEmbed,
        score_manager: "ScoreManager",
        suggestion_mode: bool = False,
    ) -> List[PendingOrder]:
        ...
```

Mode 通过 `self._strategy` 访问：
- 通用配置（`max_positions`, `max_position_pct`, `max_hold_days`, `min_hold_days` 等）
- 工具方法（`_build_order`, `_is_stop_loss_triggered` 等）

### 2.3 公共卖出逻辑提取

所有模式共享的卖出检查（止损、超期）提取为MultiStockStrategy的静态方法：

```python
@staticmethod
def check_common_sell(
    position: PositionEmbed,
    close_prices: Dict[str, float],
    stop_loss_pct: float,
    max_hold_days: int,
) -> Tuple[bool, str]:
    # 1. 止损
    if MultiStockStrategy._is_stop_loss_triggered(position, close_prices, stop_loss_pct):
        return True, SELL_REASON_STOP_LOSS
    # 2. 超期
    if position.hold_days >= max_hold_days:
        return True, SELL_REASON_MAX_HOLD_DAYS
    return False, ""
```

各模式的 `_check_sell_xx` 内部优先调用此方法，再检查模式特有条件。

### 2.2 MultiStockStrategy 改动

```python
class MultiStockStrategy(BaseStrategy):
    def __init__(self, strategy_config, ts_codes=None):
        # ... 现有初始化 ...
        self._modes: Dict[str, PhaseMode] = {
            "up": TrendMode(self),
            "flat": MeanReversionMode(self),
            "down": DefensiveMode(self),
        }

    async def make_orders(self, scored_stocks, trade_date, portfolio,
                          close_prices, market_data, score_manager, suggestion_mode=False):
        # 通用过滤（所有模式共享）
        if self.ts_codes:
            scored_stocks = [s for s in scored_stocks if s.ts_code in self.ts_codes]
        scored_stocks = [s for s in scored_stocks if not s.is_excluded]

        # 选择模式
        phase = market_data.market_phase if market_data else "up"
        mode = self._modes.get(phase, self._modes["up"])
        return await mode.run(
            scored_stocks, trade_date, portfolio,
            close_prices, market_data, score_manager,
            suggestion_mode=suggestion_mode,
        )
```

## 3. Trend Mode（up）

**源文件**: `modes/trend_mode.py`

**逻辑**: 完整保留当前 `make_orders()` 的买卖决策流程，包括 rank-up priority、分数过滤、正常填充等。

### 3.1 买入流程

```
full_candidates (按ranking_score降序)
  → 评分过滤: composite_score > buy_threshold (0.2)
  → 取前 max_positions 只 → top_stocks
  → Phase 1: rank-up priority（从 full_candidates 中选排名提升的）
  → Phase 2: 从 top_stocks 正常填充
  → reserve_funds 计算资金
```

**使用的参数**: `buy_threshold`, `max_positions`, `use_rank_up_priority/rank_up_*`, `use_score_decline_filter`

### 3.2 卖出流程

_check_sell 检查（按优先级）:
1. min_hold_days 内止损 → STOP_LOSS
2. 公共检查：止损、超期（调用 `check_common_sell`）
3. 评分低于 sell_threshold (-0.01) → SCORE_BELOW
4. 不在前 N 名且评分 < hold_score_threshold → HOLD_SCORE_LOW

**使用的参数**: `sell_threshold`, `hold_score_threshold`, `sell_rank_n`, `stop_loss_pct`, `min_hold_days`, `max_hold_days`

## 4. Defensive Mode（down）

**源文件**: `modes/defensive_mode.py`

### 4.1 买入

**不买入**。只执行卖出。

### 4.2 卖出流程

```python
def run(self, ...):
    # 现有仓位逐日+1
    for pos in portfolio.positions.values():
        pos.hold_days += 1

    orders = []
    for ts_code, pos in portfolio.positions.items():
        should_sell, reason = self._check_sell_defensive(...)
        if should_sell:
            orders.append(self._strategy._build_order(...))

    # + full_position_sell（通用风控）
    forced = self._strategy._apply_full_position_sell(...)
    orders.extend(forced)
    return orders
```

_check_sell_defensive（放宽条件，更容易卖出）:

| # | 条件 | 理由 |
|---|------|------|
| 1 | hold_days < min_hold_days + 止损 | 保护期内止损照卖 |
| 2 | **评分 < down_sell_threshold (0.0)** | 比 up（-0.01）更严，正数就卖 |
| 3 | hold_days >= max_hold_days | 超期卖出 |
| 4 | 止损 (stop_loss_pct=-0.07) | 比 up（-0.1）更紧 |
| 5 | 不在前 N 名 + 评分 < hold_score_threshold | 同样适用 |

### 4.3 仓位控制

- `max_position_pct = 0.1 × 0.3 = 0.03`（通过 `pos_mult=0.3` 实现）
- `stop_loss_pct = -0.07`（单独参数，不使用 `_stop_loss_mult`）

### 4.4 卖出条件

1. 公共检查：止损、超期（调用 `check_common_sell`）
2. 评分 < down_sell_threshold (0.0) → SCORE_BELOW

**不检查**: `sell_rank_n`, `hold_score_threshold`（除了止损、超期、评分阈值外全部放宽，更容易卖出）

## 5. Mean Reversion Mode（flat）

**源文件**: `modes/mean_reversion_mode.py`

### 5.1 买入流程

```
1. 计算候选池
   对全量 scored_stocks（排除后）:
     score_mean[i] = avg(score_buffer[-(mr_exclude_recent_days + mr_score_window):-mr_exclude_recent_days])
     # 例如 mr_score_window=20, mr_exclude_recent_days=5:
     # 取 buffer[-25:-5] 的均值

   按 score_mean 降序 → 取前 mr_max_candidates (30) 只
   → 候选池

2. 筛选反转股票
   对候选池中每只股票:
     recent_mean = avg(score_buffer[-mr_exclude_recent_days:])
     # 最近5日评分均值
     if recent_mean > score_mean + mr_mean_reversion_threshold (0.05):
       → 反转候选

3. 按反转幅度 (recent_mean - score_mean) 降序排列
4. 依次 reserve_funds 买入
```

**使用的参数**: `mr_score_window=20`, `mr_exclude_recent_days=5`, `mr_mean_reversion_threshold=0.05`, `mr_max_candidates=30`

### 5.2 卖出流程

```python
def _check_sell_mr(self, position, close_prices, score_manager, stop_loss_pct, max_hold_days, mr_score_window, mr_exclude_recent_days, mr_sell_multiplier):
    # 1. 均值回归止盈
    score_buffer = score_manager.get_score_buffer(position.ts_code)
    if len(score_buffer) >= mr_score_window + mr_exclude_recent_days:
        score_mean = avg(score_buffer[-(mr_score_window + mr_exclude_recent_days):-mr_exclude_recent_days])
        current_score = score_buffer[-1] if score_buffer else 0
        if current_score > score_mean * mr_sell_multiplier:
            return True, SELL_REASON_MEAN_REVERSION

    # 2. 公共检查：止损、超期
     return self._strategy.check_common_sell(position, close_prices, stop_loss_pct, max_hold_days)
```

**不检查**: `sell_rank_n`, `hold_score_threshold`, `sell_threshold`（这些被均值回归止盈替代）

### 5.3 min_hold_days

flat 模式的 `min_hold_days = 10`（比 up 的 5 天更长），因为均值回归需要时间验证。

## 6. 参数变更总结

### StrategyConfig 新增字段

| 字段 | 类型 | 默认值 | 模式 |
|------|------|--------|------|
| `mr_score_window` | int | 20 | flat |
| `mr_exclude_recent_days` | int | 5 | flat |
| `mr_mean_reversion_threshold` | float | 0.05 | flat |
| `mr_sell_multiplier` | float | 1.0 | flat |
| `mr_max_candidates` | int | 30 | flat |
| `down_sell_threshold` | float | 0.0 | down |
| `down_stop_loss_pct` | float | -0.07 | down |

### Constants 新增

| 字段 | 值 |
|------|----|
| `SELL_REASON_MEAN_REVERSION` | `"mean_reversion"` |

### 修正

1. **`_stop_loss_mult` 删除**：旧方法读取 `market_phase == "crash"/"decline"`（已不存在的值），改为各模式自行控制止损。
2. **`check_common_sell` 新增**：作为 `BaseStrategy` 静态方法，提供止损 + 超期检查。
3. **down 的 `pos_mult` 改为 0.3**：在 `_compute_phase_multipliers` 中返回 `(0.3, 1.0, "down")`

## 7. 文件变更清单

| 文件 | 变更 |
|------|------|
| `execution/scoring.py` | 修改：down 的 pos_mult 改为 0.3 |
| `dao/strategy_config.py` | 新增 7 个字段 |
| `constants.py` | 新增 SELL_REASON_MEAN_REVERSION |
| `strategy/base.py` | 新增静态方法 `check_common_sell` |
| `strategy/modes/__init__.py` | 新建 |
| `strategy/modes/base.py` | 新建：PhaseMode 基类 |
| `strategy/modes/trend_mode.py` | 新建：up 逻辑 |
| `strategy/modes/mean_reversion_mode.py` | 新建：flat 逻辑 |
| `strategy/modes/defensive_mode.py` | 新建：down 逻辑 |
| `strategy/multi_stock_strategy.py` | 修改：接入 mode 调度 + 删除 `_stop_loss_mult` + 保留通用工具方法 |
