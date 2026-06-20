# 月度候选池重构设计方案

## 概述

将 `CandidateListProvider` 的候选池更新周期从周度改为月度，动量选股从市值周涨幅改为日线中长期指标复合评分。

## 参数默认值

| 参数 | 旧默认值 | 新默认值 | 说明 |
|------|---------|---------|------|
| `range_n` | 500 | 300 | 范围池（按流通市值取前 N） |
| `top_n` | 100 | 100 | 基础池（按流通市值取前 N） |
| `up_n` | 50 | 删除 | 旧周动量参数 |
| `momentum_n` | — | 20 | 动量池（按复合动量分取前 N） |

## 更新周期

- 月 key 格式：`2026M01`（ISO 月标识）
- 每月第一个交易日进行候选池筛选
- WarmupManager 的 `_last_update_key` 只做字符串比较，无需感知周/月类型

## 选股逻辑

```
范围池：流通市值 top 300（StockListHistory.total_mv 排序）
  ├── 基础池：取前 100 只（按市值）
  └── 动量池：从 300 只中按 6 指标排名法选前 20 只

最终月候选池 = list(dict.fromkeys(基础池 + 动量池)) + 上月留存
```

### 动量池评分指标

| 指标 | 含义 | 方向 |
|------|------|------|
| `trend_slope_20` | 20日均线斜率 | 正值 = 中期趋势向上 |
| `trend_arrangement_20` | MA20 与 MA60 偏离度 | 正值 = 多头排列 |
| `close_position_20` | 收盘价在20日区间位置 | 高 = 近期高位 |
| `close_position_60` | 收盘价在60日区间位置 | 高 = 中长期高位 |
| `bias_20` | 20日乖离率 | 正值 = 均线上方 |
| `bias_60` | 60日乖离率 | 正值 = 均线上方 |

**评分方法**：6 个指标在截面上分别升序排名，求和得复合排名分，取最低（即综合最强）的 momentum_n 只。

**缺失处理**：任一指标为 None 时不纳入动量池。

## 清理项

- 删除 `_get_weekly_mv_gainers()`（原周涨幅选股）
- 删除 `_get_prev_trade_date()`（原向前查找前一周交易日）
- 删除 `up_n` 参数和所有周度相关逻辑
- ISO 周 key → ISO 月 key

## 改动范围

| 文件 | 改动 |
|------|------|
| `candidate_list_provider.py` | 新增 `_get_momentum_stocks()`、月 key 生成、删除旧方法、更新参数 |
| `warmup_manager.py` | `_last_week_key` → `_last_update_key`（语义重命名） |
| `backtest_pipeline.py` | 变量名 `current_week_key` → `current_period_key`（可选） |
| `test_candidate_list_provider.py` | 同步更新测试用例 |

## 回测兼容性

- 预热天数公式不变（`max(windows) + 10`）
- WarmupManager 接口不变，`update_pool()` 的 key 类型无关
- 基线追踪范围不变（`baseline_codes = provider.get_candidates_for_date(start_date)`）
