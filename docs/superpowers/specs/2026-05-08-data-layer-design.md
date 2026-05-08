# 股票预测程序 - 数据层设计

## 概述

从 Tushare 获取指定股票的数据，存储到 MongoDB。

## 功能

- **获取数据**：传入股票代码和时间范围，获取并存储数据到 MongoDB

## 数据模型

- **集合**：每日行情数据
- **字段**：使用 Tushare 返回的原始字段，不做预处理
- **索引**：股票代码 + 日期，联合唯一索引

## 技术选型

| 组件 | 选择 |
|-----|------|
| 数据源 | Tushare |
| 存储 | MongoDB |

## 目录结构

```
src/trade_alpha/
├── __init__.py
├── config.py
└── data/
    ├── __init__.py
    ├── fetcher.py
    └── storage.py

tests/trade_alpha/data/
├── test_fetcher.py
├── test_storage.py
└── test_data_integration.py
```

## 后续迭代

- 分析层：技术指标计算、统计分析
- 预测层：价格预测模型
- 回测层：策略验证、绩效分析
