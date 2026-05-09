# 回测模块设计文档

## 概述

回测模块用于验证交易策略在历史数据上的表现，支持收益计算、风险评估和交易记录持久化。

## 设计目标

1. **策略验证** - 在历史数据上模拟交易，计算收益率
2. **风险评估** - 最大回撤、夏普比率、胜率
3. **参数优化** - 支持不同参数组合的回测
4. **成本分析** - 总手续费、净收益

## 交易规则

### 数据粒度
- 日线级别

### 委托方式
- 夜盘委托（T+1）
- 当日收盘后根据策略信号生成委托
- 次日开盘价成交

### 交易成本
| 类型 | 费率 | 最低收费 |
|-----|------|---------|
| 买入手续费 | 0.03% | 5元 |
| 卖出手续费 | 0.03% | 5元 |
| 印花税 | 0.1% | - |

## 模块结构

```
trade-alpha/
├── portfolio/              # 账户管理模块
│   ├── __init__.py        # 模块导出
│   └── portfolio.py       # 账户资金管理
├── backtest/              # 回测模块
│   ├── __init__.py        # 模块导出
│   ├── engine.py          # 回测引擎核心
│   ├── metrics.py         # 指标计算
│   └── service.py         # 服务层（持久化）
```

## 核心组件

### 1. BacktestEngine

回测引擎，负责遍历历史数据、执行交易逻辑。

```python
class BacktestEngine:
    def __init__(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
        strategy: BaseStrategy,
        portfolio: Portfolio,
    ):
        ...

    def run(self) -> BacktestResult:
        """执行回测，返回结果"""
        ...
```

### 2. Portfolio (portfolio 模块)

账户管理，跟踪现金、持仓、交易记录。可复用于实盘交易。

```python
from trade_alpha.portfolio import Portfolio

class Portfolio:
    def __init__(
        self,
        initial_capital: float,
        buy_fee_rate: float = 0.0003,
        sell_fee_rate: float = 0.0003,
        stamp_tax_rate: float = 0.001,
        min_fee: float = 5.0,
    ):
        self.cash = initial_capital
        self.position = 0
        self.buy_fee_rate = buy_fee_rate
        self.sell_fee_rate = sell_fee_rate
        self.stamp_tax_rate = stamp_tax_rate
        self.min_fee = min_fee
        self.trades: list[Trade] = []

    def buy(self, date: str, price: float, shares: int) -> Trade:
        """买入，返回交易记录"""
        ...

    def sell(self, date: str, price: float, shares: int) -> Trade:
        """卖出，返回交易记录"""
        ...
```

### 3. 指标计算

```python
def calculate_metrics(
    trades: list[Trade],
    daily_values: list[tuple[str, float]],
    initial_capital: float,
    benchmark_return: float,
) -> Metrics:
    """计算回测指标"""
    ...
```

计算指标包括：
- 总收益率
- 年化收益率
- 基准收益率
- 最大回撤
- 夏普比率
- 胜率
- 盈亏比
- 总交易次数
- 平均持仓天数
- 总手续费

## 数据持久化

### portfolios 集合

存储账户信息，包括手续费配置。

| 字段 | 类型 | 说明 | 默认值 |
|-----|------|------|-------|
| `name` | string | 账户名称 | - |
| `initial_capital` | float | 初始资金 | - |
| `buy_fee_rate` | float | 买入手续费率 | 0.0003 |
| `sell_fee_rate` | float | 卖出手续费率 | 0.0003 |
| `stamp_tax_rate` | float | 印花税率 | 0.001 |
| `min_fee` | float | 最低手续费 | 5.0 |
| `cash` | float | 当前现金 | initial_capital |
| `position` | int | 当前持仓 | 0 |

### backtests 集合

存储回测汇总结果。

| 字段 | 类型 | 说明 |
|-----|------|------|
| `portfolio_id` | ObjectId | 关联的账户ID |
| `ts_code` | string | 股票代码 |
| `start_date` | string | 回测开始日期 |
| `end_date` | string | 回测结束日期 |
| `strategy` | string | 策略名称 |
| `initial_capital` | float | 初始资金 |
| `final_value` | float | 最终资产 |
| `total_return` | float | 总收益率 |
| `annual_return` | float | 年化收益率 |
| `benchmark_return` | float | 基准收益率 |
| `max_drawdown` | float | 最大回撤 |
| `sharpe_ratio` | float | 夏普比率 |
| `win_rate` | float | 胜率 |
| `total_trades` | int | 总交易次数 |
| `total_fees` | float | 总手续费 |

### backtest_trades 集合

存储每笔交易记录（买入/卖出分开）。

| 字段 | 类型 | 说明 |
|-----|------|------|
| `backtest_id` | ObjectId | 关联的回测ID |
| `portfolio_id` | ObjectId | 关联的账户ID |
| `ts_code` | string | 股票代码 |
| `trade_date` | string | 交易日期 |
| `action` | string | "buy" / "sell" |
| `price` | float | 成交价格 |
| `shares` | int | 成交股数 |
| `fee` | float | 手续费 |
| `cash_after` | float | 交易后现金 |
| `position_after` | int | 交易后持仓 |

## 接口设计

### 主入口

```python
from trade_alpha.backtest import run_backtest

result = run_backtest(
    ts_code="002594.SZ",
    start_date="20240101",
    end_date="20241231",
    strategy="price",
    portfolio_name="default",
    initial_capital=100000,
)

print(f"总收益率: {result.total_return:.2%}")
print(f"最大回撤: {result.max_drawdown:.2%}")
print(f"总手续费: {result.total_fees:.2f}")
```

### 返回结果

```python
@dataclass
class BacktestResult:
    backtest_id: str          # MongoDB ID
    portfolio_id: str         # 关联账户ID
    ts_code: str
    start_date: str
    end_date: str
    strategy: str
    initial_capital: float
    final_value: float
    total_return: float
    annual_return: float
    benchmark_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    total_trades: int
    total_fees: float
```

## 回测流程

1. **加载账户** - 从 MongoDB 获取或创建账户
2. **加载数据** - 从 MongoDB 获取历史数据
3. **初始化** - 创建 Portfolio，设置初始资金和手续费配置
4. **遍历日期** - 逐日处理
   - 当日收盘后，策略根据数据生成信号
   - 次日开盘价执行交易
   - 记录交易到 Portfolio
5. **计算指标** - 回测结束后计算各项指标
6. **持久化** - 保存回测结果和交易记录

## 设计原则

1. **计算与存储分离** - engine 只做回测计算，service 处理持久化
2. **可扩展** - 支持多种策略，通过 BaseStrategy 接口
3. **可测试** - 纯计算逻辑易于单元测试
4. **账户复用** - portfolio 模块独立，可复用于实盘交易
