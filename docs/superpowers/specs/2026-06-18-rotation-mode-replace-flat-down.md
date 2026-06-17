# Rotation Mode: 合并 flat/down 的排名轮动交易模式

## 1. 背景

当前 flat（均值回归）和 down（防御）两套模式的回测表现不佳:

- **均值回归模式**: `sell_multiplier=1.0` 导致刚买就卖，平均持仓 1-2 天，频繁亏损
- **防御模式**: 熊市空仓经常错过早期快速上涨
- **共同问题**: 趋势短的行情中，模型不是没有预测能力，而是买入时机不对

## 2. 核心思路

**熊市和横盘使用相同的交易模式**。非牛市行情趋势非常短，股票表现为"排名轮动"——排名靠前开始下跌，排名靠后开始回升。目标是**在上升初期买入**。

## 3. 架构变更

### 3.1 模式映射

```python
self._modes = {
    "up":   TrendMode(self),      # 不变
    "flat": RotationMode(self),   # 新建，替换 MeanReversionMode
    "down": RotationMode(self),   # 与 flat 共享同一实例
}
```

三个 market_phase 值保留（不影响显示、日志、统计），但 flat 和 down 的交易逻辑完全一致。

### 3.2 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| **新建** | `strategy/modes/rotation_mode.py` | 排名轮动模式 |
| **删除** | `strategy/modes/mean_reversion_mode.py` | 被 RotationMode 替代 |
| **删除** | `strategy/modes/defensive_mode.py` | 被 RotationMode 替代 |
| **修改** | `strategy/multi_stock_strategy.py` | 移除 `check_common_sell`，flat/down 指向 RotationMode |
| **修改** | `execution/scoring.py` | 新增 `get_rank_history()` 公开方法 |
| **修改** | `dao/strategy_config.py` | 清理 mr_*、down_* 字段 |
| **删除** | `constants.py` | 可选的 `SELL_REASON_MEAN_REVERSION` 清理 |

## 4. RotationMode 设计

### 4.1 参数刷新

RotationMode 初始化时直接刷写策略参数，确保 _check_sell 和 _apply_full_position_sell 内部使用正确的值（一天只有一个 mode 执行，不会冲突）：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `self._strategy.min_hold_days` | 10 | 最小持仓 10 天，给轮动信号足够时间兑现 |
| `self._strategy.sell_threshold` | -0.5 | 评分低于 -0.5 才卖出，显著拉胯才触发 |
| `self._strategy_config.full_position_score_window` | 10 | 满仓卖出评分窗口 10 天 |

### 4.2 买入条件：排名轮动信号

```python
rank_history = score_manager.get_rank_history(ts_code)
# rank_history 是过去 N 天的 rank 值列表，[最旧, ..., 最新]

was_top       = any(r <= 10 for r in rank_history[:-5])    # 20d~5d 至少一天前10
recent_bottom = any(r >= 91 for r in rank_history[-5:])    # 最近5天至少一天后10
current_mid   = 70 <= st.rank <= 90                        # 当日排名 70-90

if was_top and recent_bottom and current_mid:
    candidates.append(st)
```

**候选排序**: 按 rank 值升序（rank 越小越好），优先买入排名更靠前的候选。

### 4.3 卖出条件

RotationMode 中的 `_check_sell` 方法实现完整 4 步检查：

```python
def _check_sell(self, position, close_prices, score_map):
    # 1. 止损（任何时候都检查）
    if self._strategy._is_stop_loss_triggered(position, close_prices, self._strategy.stop_loss_pct):
        return True, SELL_REASON_STOP_LOSS

    # 2. 最小持仓期内，只止损不出售
    if position.hold_days < self._strategy.min_hold_days:
        return False, ""

    # 3. 评分太低（sell_threshold 已被刷新为 -0.5）
    score = score_map.get(position.ts_code, 0.0)
    if score < self._strategy.sell_threshold:
        return True, SELL_REASON_SCORE_BELOW

    # 4. 超期
    if position.hold_days >= self._strategy.max_hold_days:
        return True, SELL_REASON_MAX_HOLD_DAYS

    return False, ""
```

### 4.4 仓位缩放

RotationMode 运行时，**忽略 `_compute_phase_multipliers` 返回的 `position_multiplier`**，始终使用满仓：

```python
# 忽略 market_data.position_multiplier，始终满仓
position_multiplier = 1.0
```

Note: `buy_threshold_multiplier` 仍从 `_market_multipliers` 获取（由相位检测决定），但买入时 RotationMode 不依赖 buy_threshold，因此实际不影响行为。

## 5. `get_rank_history()` 方法

在 `ScoreManager` 中新增公开方法，供 RotationMode 查询排名历史：

```python
def get_rank_history(self, ts_code: str) -> List[int]:
    """Return daily rank history for a stock, oldest first."""
    records = self._rank_history.get(ts_code, [])
    return [s.rank for s in records if s.rank > 0]
```

## 6. StrategyConfig 字段清理

删除以下不再使用的字段：

| 字段 | 原默认值 | 用途 |
|------|----------|------|
| `mr_score_window` | 20 | 均值回归评分窗口 |
| `mr_exclude_recent_days` | 5 | 均值回归排除天数 |
| `mr_mean_reversion_threshold` | 0.05 | 均值回归阈值 |
| `mr_sell_multiplier` | 1.0 | 均值回归卖出乘数 |
| `mr_ranking_window` | 50 | 均值回归排名窗口 |
| `mr_max_candidates` | 30 | 均值回归候选数 |
| `down_sell_threshold` | 0.0 | 防御卖出阈值 |
| `down_stop_loss_pct` | -0.07 | 防御止损 |

## 7. MultiStockStrategy 的 `check_common_sell` 移除

将该静态方法移除，原引用点改为直接内联逻辑或改用 `_check_sell`。defensive_mode.py 中引用该方法的 `_check_sell_defensive` 也随文件一起删除。

## 8. 测试

- 集成测试 126 个全部通过
- 无新建测试（行为变更由回测验证）
