# 均线策略与MACD策略设计

## 概述

为交易系统添加两个基于技术指标的策略：
- MAStrategy：基于价格与移动平均线关系的策略
- MACDStrategy：基于MACD与信号线交叉的策略

## MAStrategy

### 逻辑

- 当无持仓时：价格上穿MA，且差值达到阈值 → 买入
- 当有持仓时：价格下穿MA，且差值达到阈值 → 卖出
- 否则持有

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|-------|------|
| ma_period | int | 20 | MA周期（5, 10, 20, 60） |
| threshold | float | 0.01 | 价格与MA差值百分比阈值 |

### 指标依赖

- `ma_{period}`：对应周期的移动平均线值

## MACDStrategy

### 逻辑

- 当无持仓时：MACD上穿信号线，且差值达到阈值 → 买入
- 当有持仓时：MACD下穿信号线，且差值达到阈值 → 卖出
- 否则持有

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|-------|------|
| threshold | float | 0.5 | MACD与信号线差值阈值 |

### 指标依赖

- `macd`：MACD值
- `macd_signal`：信号线值

## 文件结构

```
src/trade_alpha/strategy/
├── base.py          # BaseStrategy, StrategyContext
├── price.py         # PriceStrategy
├── ma.py            # MAStrategy (新增)
└── macd.py          # MACDStrategy (新增)

tests/trade_alpha/strategy/
├── test_price.py    # PriceStrategy tests
├── test_ma.py       # MAStrategy tests (新增)
└── test_macd.py     # MACDStrategy tests (新增)
```

## 实现要点

1. 两个策略继承 BaseStrategy，实现 decide 方法
2. 通过 context.indicators 获取指标值
3. 根据 context.position 判断当前持仓状态
4. 策略之间独立，无依赖关系
