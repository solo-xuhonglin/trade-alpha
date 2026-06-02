# 实盘委托单建议（基础版）

## 概述

实现一个无副作用、可重复运行的实盘委托单建议模块。当前阶段不对接真实交易系统，只生成下一交易日的买入建议，供人工审阅。

## 设计原则

1. **最大程度复用回测代码** — `_predict`、`_smooth_scores`、`make_decisions` 等直接复用，回测中任何评分/过滤/平滑的改进自动带到实盘
2. **幂等可重复** — 每次运行生成独立 `run_id`，不覆盖已有数据
3. **无副作用** — 不修改持仓、不下真实订单、不删除任何数据

## 数据模型

### OrderSuggestion（改造现有）

```python
class OrderSuggestion(Document):
    """Live order suggestion document."""

    run_id: PydanticObjectId          # 关联 LiveSuggestionRun
    ts_code: str
    stock_name: str

    # 日期
    trade_date: str                   # 预测日期（最新交易日）
    settle_date: str                  # 建议交易日期（下一交易日）

    # 买卖信息
    action: str                       # "buy"
    order_price: float                # 最新收盘价
    order_shares: int                 # 建议股数

    # 评分体系
    raw_score: float                  # 模型原始评分
    composite_score: float            # 加分/扣分调整后
    ranking_score: float = 0.0        # EWMA 平滑后排位分
    rank: int = 0                     # 当日排名

    # 概率
    up_prob_3d: float
    up_prob_5d: float
    up_prob_10d: float = 0.0

    # 加减分明细
    trend_bonus: float = 0.0
    vol_penalty: float = 0.0
    momentum_bonus: float = 0.0

    # 排除标记
    is_excluded: bool = False
    excluded_reason: Optional[str] = None

    # 状态
    status: str = "pending"           # pending / executed / cancelled
    reason: Optional[str] = None      # 建议理由
    created_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "order_suggestions"
        indexes = ["run_id", "ts_code", "trade_date", "status"]
```

去掉的旧字段：`backtest_id`、`actual_price`、`actual_shares`、`fee`、`cash_after`

### LiveSuggestionRun（新增）

```python
class LiveSuggestionRun(Document):
    """记录一次实盘建议运行的上下文。"""

    account_config_id: PydanticObjectId
    training_id: PydanticObjectId
    strategy_config_id: PydanticObjectId

    target_date: str                  # 预测目标日（最新交易日）
    warmup_start: str                 # 预热起始日
    warmup_days: int                  # 实际预热天数

    status: str = "running"           # running → completed | failed | no_data
    order_count: int = 0
    error_message: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "live_suggestion_runs"
        indexes = ["target_date", "strategy_config_id", "status"]
```

## 核心流程

```
run_live_suggestion(account_config, training_id, model_config, strategy_config)
  │
  ├─ 1. 创建 LiveSuggestionRun(status="running")
  │
  ├─ 2. 计算 target_date = 数据库中最新可用的交易日
  │     warmup_days = int(max_lookback × 1.5)
  │     warmup_start = 从 target_date 向前推 warmup_days 个自然日
  │     (日循环中会自动跳过非交易日)
  │
  ├─ 3. Phase 1: 预热逐日回放
  │    for date in [warmup_start → target_date]:
  │      if 非交易日: continue
  │      day_data = _load_day_data(date, ts_codes)
  │      if 无数据: continue
  │      scored, pred_results = _predict(date, ...)
  │      if 无评分结果: continue
  │      # 仅累积 _score_buffer，不下单、不存快照
  │
  ├─ 4. Phase 2: 目标日出单
  │    day_data = _load_day_data(target_date, ts_codes)
  │    scored, pred_results = _predict(target_date, ...)  # 含完整平滑/过滤
  │    pending_orders = strategy.make_decisions(
  │        scored_stocks=scored, portfolio=空仓, ...)
  │    每条 PendingOrder → OrderSuggestion(run_id=..., ...)
  │
  ├─ 5. Phase 3: 持久化
  │    批量写入 OrderSuggestion
  │    LiveSuggestionRun.order_count = len(orders)
  │    LiveSuggestionRun.status = "completed"
  │
  └─ 返回 run_id + order_count
```

### 预热期的关键行为

- **不生成委托单** — 跳过 `_settle_orders`、`_make_orders`、`_save_snapshot`
- **不修改持仓** — PortfolioManager 始终为空仓状态
- **只做**：`_load_day_data` → `_predict`（含趋势/波动/动量/暴涨排除/加速排除） → `_smooth_scores`（累积 buffer）
- 某天无数据则 `continue`，不影响后续

### 目标日出单

- 经过预热期后，`_score_buffer` 中已含有足够的历史平滑值
- `make_decisions` 传入空仓 PortfolioManager，只生成**买入建议**（不卖）
- 建议股数由 `reserve_funds` 按账户资金计算

## 新增/修改文件清单

| 文件 | 操作 |
|------|------|
| `backend/src/trade_alpha/dao/order_suggestion.py` | 改造：新字段 + run_id |
| `backend/src/trade_alpha/dao/live_suggestion_run.py` | 新建 |
| `backend/src/trade_alpha/dao/__init__.py` | 导出 LiveSuggestionRun |
| `backend/src/trade_alpha/dao/mongodb.py` | 注册 LiveSuggestionRun |
| `backend/src/trade_alpha/execution/pipeline.py` | 新增 `run_live_suggestion()` 方法 |
| `backend/scripts/run_live_suggestion.py` | 新建：入口脚本 |
| `backend/src/trade_alpha/api/routers/live.py` | 新建（可选）：API 端点 |

## 错误处理

- 数据库无数据：状态设为 `no_data`，返回空列表
- 预测/评分异常：状态设为 `failed` + `error_message`
- 预热期数据不连续：跳过缺失日，仍正常继续
- 同一日可反复运行（不同 run_id），互不干扰