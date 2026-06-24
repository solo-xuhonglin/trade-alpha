# 选股添加 MA 下降趋势过滤

## 概述

在候选池构建最后阶段增加一个可配置的硬过滤：剔除 MA5 在 MA60 下方超过阈值的股票，排除下降趋势个股。过滤作用于最终候选池（`final`），不影响市值分组和动量选股过程。

## 参数

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `use_ma_trend_filter` | bool | false | 开关 |
| `ma_trend_ratio_threshold` | float | 1.0 | MA5/MA60 < 此值则剔除 |

## 后端

### 候选池过滤

`candidate_list_provider.py` 的 `__init__` 新增读取配置。`_get_candidates` 在计算出 `final` 列表后，若开关开启，查询所有 final 股票的 MA5 和 MA60，过滤掉 `ma_5 / ma_60 < threshold` 的股票。MA5 或 MA60 为 None 的股票保留。

过滤时序：
```
universe_codes → mv_group + momentum_group → current_base → final → 过滤 → result
```

### StrategyConfig DAO

`strategy_config.py` 新增 2 个字段。`execution.py` 的 `StrategySnapshotEmbed` 同步新增。

### API

`api/schemas.py` 的 `CreateRequest` 和 `UpdateRequest` 新增 2 个字段。Router 和 Service 已有自动化处理（model_dump + setattr），无需额外修改。

## 前端

### StrategyConfigView.vue

选股 tab 新增开关和阈值输入，阈值范围 0.5~1.5，步长 0.01。

### 类型定义

`api/strategyConfig.ts` 新增 2 个字段。`BacktestRecordsView.vue` 的 `compareFields` 新增字段描述。
