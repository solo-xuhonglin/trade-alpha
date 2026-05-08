# 分析层设计

## 概述

计算技术指标（均线、MACD），从数据库读取数据，计算后将结果更新回数据库。

## 重构：计算与存储分离

将数据库操作提取到公共模块，计算与存储职责分离。

## 目录结构

```
src/trade_alpha/
├── db/                    # 数据库公共模块
│   ├── __init__.py
│   └── storage.py         # MongoDB 存储操作
├── data/                  # 数据获取模块
│   ├── __init__.py
│   ├── fetcher.py         # Tushare 数据获取（纯计算）
│   └── service.py         # 数据流调度
└── indicators/            # 技术指标模块
    ├── __init__.py
    ├── ma.py              # 均线计算（纯计算）
    ├── macd.py            # MACD 计算（纯计算）
    └── service.py         # 指标数据流调度
```

## 职责划分

| 模块 | 职责 |
|-----|------|
| `db.storage` | 数据库 CRUD 操作 |
| `data.fetcher` | 从 Tushare 获取数据 |
| `data.service` | 调度：获取 → 存储 |
| `indicators.ma` | 均线计算 |
| `indicators.macd` | MACD 计算 |
| `indicators.service` | 调度：读取 → 计算 → 存储 |

## 功能

1. **均线计算**：支持可配置周期列表
2. **MACD 计算**：固定参数 (12, 26, 9)
3. **数据持久化**：计算结果更新到 MongoDB

## 接口设计

```python
# data 模块
from trade_alpha.data.service import fetch_and_store
fetch_and_store("000001.SZ", "20240101", "20241231")

# indicators 模块
from trade_alpha.indicators.service import calculate_and_store_ma, calculate_and_store_macd
calculate_and_store_ma("000001.SZ", periods=[5, 10, 20, 60])
calculate_and_store_macd("000001.SZ")
```

## 数据流

```
MongoDB (db.storage) → 读取数据 → indicators 计算 → 更新回 MongoDB
```
