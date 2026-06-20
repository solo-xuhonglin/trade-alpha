# 候选池周度更新设计方案

## 概述

将 `CandidateListProvider` 的候选池更新周期从月度改为周度，每周最后一个交易日筛选备选股，其余逻辑保持不变。

## 更新周期

- 周 key 格式：`2026W25`（ISO 周标识，`dt.isocalendar()`）
- 每周**最后一个交易日**进行候选池筛选
- 覆盖写入法：遍历该周所有交易日，反复覆盖同 week key → 自然得到最后一个交易日

## 选股逻辑（不变）

双选结构保持不变：

```
范围池：流通市值 top 300（StockListHistory.total_mv）
  ├── 基础池：取前 100 只（按市值）
  └── 动量池：从 300 只中按加权指标排名选前 20
```

加权指标：trend_slope_20(1.0)、trend_arrangement_20(1.0)、close_position_20(1.0)、close_position_60(1.0)、bias_20(1.0)、bias_60(1.0)、atr_14(0.3↓)、log_mv(1.0)

滚动留存：`final = dedup(current_base + prev_base)`，prev_base 存 current_base（非 final），连续落选 2 周期出池。

## WarmupManager 预热窗口

```
月度（改前）：lookahead_months = max(1, (warmup_days + 19) // 20)   # 40天→2个月
周度（改后）：lookahead_periods = max(1, (warmup_days + 4) // 5)    # 40天→8周
```

预热池逻辑不变：只取未来 `lookahead_periods` 个周期的候选股并集，`_ever_seen` 防重复入池。

## 改动范围

| 文件 | 改动 |
|------|------|
| `backend/.../candidate_list_provider.py` | `monthly` 分组→`weekly` 分组、ISO 周 key、日志/注释 |
| `backend/.../warmup_manager.py` | `lookahead_months`→`lookahead_periods`、注释 |
| `test_candidate_list_provider.py` | Mock 数据从月改为周 |

## 不变部分

- `backtest_pipeline.py`：已用 `get_period_key()` 通用调用，无感知
- `_get_period_key()`：key 仍是 YYYYMMDD 日期格式，向下兼容
- API / 前端：无参数变更
- 动量指标 / 权重 / 双选结构：不变
