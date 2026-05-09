# 交易策略模块设计

## 概述

根据预测价格生成交易信号（买入/卖出/持有），支持多种交易策略。

## 设计原则

沿用现有模块的设计原则：**计算与存储分离**。

- **策略文件** (e.g., `price.py`): 纯决策逻辑，无副作用
- **服务文件** (`service.py`): 编排数据流，处理 I/O

## 目录结构

```
src/trade_alpha/
└── strategy/
    ├── __init__.py
    ├── base.py          # 策略基类
    ├── price.py        # 价格策略实现
    └── service.py      # 策略服务
```

## 模块说明

### 1. base.py - 策略基类

定义统一接口，所有策略需实现：

```python
@dataclass
class StrategyContext:
    """策略上下文数据"""
    ts_code: str
    trade_date: str
    current_price: float
    prediction: dict[str, float]
    indicators: dict[str, float]


class BaseStrategy(ABC):
    @abstractmethod
    def decide(self, context: StrategyContext) -> str:
        """决策

        Args:
            context: 策略上下文，包含当前价格、预测值、技术指标等

        Returns:
            交易动作: "buy", "sell", "hold"
        """
        pass
```

### 2. price.py - 价格策略

最简单的策略：基于预测价格与当前价格比较

- 预测收盘价 > 当前价格 → **买入 (buy)**
- 预测收盘价 ≤ 当前价格 → **空仓 (hold)**

### 3. service.py - 策略服务

```python
def generate_signal(
    ts_code: str,
    strategy: str = "price"
) -> dict[str, any]:
    """生成交易信号

    Args:
        ts_code: 股票代码
        strategy: 策略名称，默认 "price"

    Returns:
        信号结果字典
    """
```

## 数据库设计

### signals 集合

存储交易信号。

**索引**: `{ts_code: 1, trade_date: 1, strategy: 1}` 联合唯一索引

**字段**:

| 字段 | 类型 | 说明 |
|-----|------|------|
| `ts_code` | string | 股票代码 |
| `trade_date` | string | 决策日期 (YYYYMMDD) |
| `strategy` | string | 策略名称 (e.g., "price") |
| `action` | string | 交易动作 ("buy" / "sell" / "hold") |
| `current_price` | float | 当前价格 |
| `target_price` | float | 目标价格 |
| `reason` | string | 决策原因 |

## 接口设计

```python
from trade_alpha.strategy import generate_signal

signal = generate_signal("000001.SZ", strategy="price")
# signal = {"action": "buy", "current_price": 10.5, "target_price": 11.2, "reason": "..."}
```

## 扩展性

后续可扩展的策略：

- `ma.py` - 均线交叉策略
- `macd.py` - MACD 策略

新增策略只需：
1. 继承 `BaseStrategy`
2. 在 `service.py` 中注册策略名称
