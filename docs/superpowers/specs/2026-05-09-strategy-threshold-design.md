# 策略阈值设计文档

## 概述

为交易策略增加阈值控制，只有预测涨跌达到一定百分比才执行买卖操作。

## 设计目标

1. 支持自定义买入/卖出阈值
2. 根据持仓状态决定交易动作
3. 非对称阈值（买入和卖出阈值可独立设置）

## 修改内容

### 1. StrategyContext

增加 `position` 字段用于判断当前持仓状态：

```python
@dataclass
class StrategyContext:
    ts_code: str
    trade_date: str
    current_price: float
    prediction: dict[str, float]
    indicators: dict[str, float]
    position: int = 0  # 新增：当前持仓股数
```

### 2. PriceStrategy

修改为支持阈值参数的策略类：

```python
class PriceStrategy(BaseStrategy):
    def __init__(
        self,
        buy_threshold: float = 0.01,   # 上涨 1% 才买入
        sell_threshold: float = 0.01,  # 下跌 1% 才卖出
    ):
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    def decide(self, context: StrategyContext) -> str:
        """Make decision based on predicted price change percentage."""
        target_price = context.prediction.get("close")
        if target_price is None:
            return "hold"

        change_pct = (target_price - context.current_price) / context.current_price

        if context.position == 0:  # 空仓
            if change_pct >= self.buy_threshold:
                return "buy"
        else:  # 持仓
            if change_pct <= -self.sell_threshold:
                return "sell"

        return "hold"
```

### 3. 决策逻辑

| 状态 | 条件 | 动作 |
|-----|------|-----|
| 空仓 (position=0) | 预测涨幅 >= 买入阈值 | buy |
| 持仓 (position>0) | 预测跌幅 >= 卖出阈值 | sell |
| 其他 | - | hold |

## 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|-------|------|
| `buy_threshold` | float | 0.01 | 买入阈值（1%），预测涨幅达到此值才买入 |
| `sell_threshold` | float | 0.01 | 卖出阈值（1%），预测跌幅达到此值才卖出 |

## 使用示例

```python
from trade_alpha.strategy.price import PriceStrategy

# 使用默认阈值
strategy = PriceStrategy()

# 使用自定义阈值
strategy = PriceStrategy(buy_threshold=0.02, sell_threshold=0.015)  # 上涨2%买入，下跌1.5%卖出
```

## 影响范围

- `strategy/base.py` - StrategyContext 增加 position 字段
- `strategy/price.py` - PriceStrategy 增加阈值参数和持仓判断
- `strategy/service.py` - generate_signal 传递 position 给 Context
- `backtest/engine.py` - 回测时传递 Portfolio.position 给 Context
- 测试文件需要更新
