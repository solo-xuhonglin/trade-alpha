# 候选股预热评分设计文档

Date: 2026-06-20

## 背景

当前候选池每周刷新一次（Top 100 市值 + Top N 动量），新进入候选池的股票没有评分和排名历史，导致：
- EWMA 平滑（`ranking_smooth_window=5`）无历史 buffer → 首周 `ranking_score` = 原始分
- `rank_improvement` 无法计算（需要至少 2 条记录）
- Rotation Mode 因 `rank_history` 不足直接跳过
- 常规预热期只对第一周候选股打分，后面每周新换入的股票仍然没有历史

## 设计思路

不改变现有候选池的周级刷新结构，也不改变正式候选股（含 `top_n`、`up_n` 入参）的交易逻辑。而是在回测预热期，对**未来会进入候选池的股票**提前预测打分，积累 `score_buffer` 和 `rank_history`。

### 核心概念：预热股

```
预热股 = {未来几周会成为正式候选股的股票} - {当前周正式候选股}
```

- 预热股跟正式股一起预测、打分，但不实际交易
- 预热股的排名是"虚拟排名"——分数插入正式股排序确定位置，但**不改变正式股排名**
- 预热股正常积累 `score_buffer` 和 `rank_history`
- 当预热股在后续某周进入正式候选池时，已有完整评分和排名历史

## 预热周期计算

### 各功能的历史数据需求

| 依赖 | 配置 | 需要天数 |
|------|------|:--------:|
| EWMA 平滑 | `ranking_smooth_window=5`, `alpha=0.3` | 5~10 天 |
| Rank Improvement | `rank_up_window=5` | 6 天 |
| Rotation Mode | `rotation_was_top_window=30` + `rotation_pullback_window=5` | **36 天** |
| Score Decline | `score_decline_threshold` | 2 天 |
| 市场指标 | `retention_days=5`, `correlation_window=5` | 5~10 天 |

预热周期取最大值 **36 个交易日** ≈ 7 个交易周 ≈ 1.5 个月。

`_compute_warmup_days` 需改为从 `rotation_was_top_window + rotation_pullback_window + 1` 计算，而非当前仅取 `max(windows) + 10`。

### 预热池规模估算

正式候选池每周变动约 20~30 只，预热池 = 未来 7 周正式候选股 - 当前正式股：

```
预热池 ≈ 每周新增 25 只 × 7 周 ≈ 175 只
每日预测量 = 正式池 110 只 + 预热池 175 只 ≈ 285 只
```

预热股每天随正式股一起预测，`score_buffer` 每天追加一条，36 天积累 36 条。

## WarmupManager 设计

### 类定位

实例类，非静态。每个 `BacktestPipeline` 实例持有自己的 `WarmupManager`，避免多个回测互相影响。

### 存放位置

`PipelineContext` 中新增 `warmup_manager` 字段：

```python
class PipelineContext:
    def __init__(self, ..., warmup_manager: Optional[WarmupManager] = None):
        ...
        self.warmup_manager = warmup_manager
```

### 职责范围

**限定职责**：只管理"当前预热池中有哪些股票"，不管理评分 buffer 或 rank buffer。

- buffer 管理完全复用 `ScoreManager._score_buffer` 和 `MarketRegimeAnalyzer._rank_history`
- WarmupManager 只回答：**今天哪些股票是预热股？**

### 接口

```python
@dataclass
class WarmupRecord:
    ts_code: str
    first_seen_week_key: str      # 首次进入预热池的周


class WarmupManager:
    def __init__(self, candidate_map: Dict[str, List[str]]):
        self._pool: Dict[str, WarmupRecord] = {}
        self._ever_seen: Set[str] = set()  # 所有已见过（正式+预热）的股票

    def update_pool(self, current_week_key: str, formal_set: Set[str]) -> None:
        """每周更新预热池。

        遍历 candidate_map 中 future weeks 的候选股，
        只加入：未来正式股 - 当前正式股 - 从未见过的股票。

        _ever_seen 确保预热期积累大量预热股，正式期只有全新股。
        """
        future_codes = set()
        for wk, codes in self._candidate_map.items():
            if wk > current_week_key:
                future_codes.update(codes)

        already_covered = formal_set | self._ever_seen
        for ts_code in future_codes - already_covered:
            self._pool[ts_code] = WarmupRecord(ts_code, current_week_key)
            self._ever_seen.add(ts_code)

        # 从预热池移除已进入正式池的
        for ts_code in list(self._pool.keys()):
            if ts_code in formal_set:
                del self._pool[ts_code]

    @property
    def warmup_codes(self) -> List[str]:
        return list(self._pool.keys())

    def is_warmup(self, ts_code: str) -> bool:
        return ts_code in self._pool
```

### 更新时机

每周第一个交易日，`get_candidates_for_date` 切换周时触发 `update_pool`。

## 预热排名算法

```python
# 正式股：正常排序，排名 1~N
formal_sorted = sorted(formal_stocks, key=lambda s: s.composite_score, reverse=True)
for rank, s in enumerate(formal_sorted, start=1):
    s.rank = rank  # 正式排名，用于交易决策

# 预热股：虚拟排名——按分数插入正式排序，不改变正式排名
formal_scores = sorted([s.composite_score for s in formal_stocks], reverse=True)
# 二分查找预热股在正式股中的位置
import bisect
for w in warmup_stocks:
    virtual_rank = bisect.bisect_left(formal_scores, w.composite_score, key=lambda x: -x) + 1
    # 预热股 rank 范围总是 1~110，分数最高就是1，最低就是110
    # 写入 ScoredStock.rank，供 record_ranking_scores 使用
    w.rank = virtual_rank
```

**关键**：预热股写入 `_rank_history` 时用的是虚拟 rank，后续它进入正式池后，历史排名是连续的（因为它一直是相对这 110 只的位置）。

## 架构变更

### 预热范围：贯穿整个回测

预热评分不只存在于预热期，而是贯穿两个阶段：

```
_run_warmup                          _run_daily_loop
（预热期，正式开始前）                （正式交易期）
┌──────────────────────┐            ┌──────────────────────────┐
│ 36天                  │            │ 数百天                    │
│                      │            │                          │
│ 每天：                │            │ 每天：                    │
│  正式+预热 预测打分     │            │  正式+预热 预测打分         │
│  不下单                │            │  settle_orders + 下单     │
│  积累所有 buffer       │            │  新进正式股已有历史         │
│                      │   正式       │                          │
│ 预热池 ~175只          │ ──────→   │ 预热池 ~0~15只             │
│ （首次积累量大）        │            │ （只有全新股，量很小）      │
└──────────────────────┘            └──────────────────────────┘
```

- **预热期**：`_ever_seen` 为空，第一次 `update_pool` 把未来 7 周候选股全部加入预热池 → ~175 只
- **正式期**：`_ever_seen` 已积累预热期的股票，只有全新出现的候选股才加入 → 通常 0~15 只

### WarmupManager
- 新建 `backend/src/trade_alpha/execution/warmup_manager.py`
- 实例类，管理 `_pool: Dict[str, WarmupRecord]`
- 放在 `PipelineContext.warmup_manager`

### ScoreManager.predict_and_score
**不修改。** 预热股的 `close_prices` 已经传入，`predict_batch` 自然会对所有股票（含预热）做预测。`_score_buffer` 由 `smooth_scores` 按 ts_code 追加，预热股也正常积累。

### MarketRegimeAnalyzer.record_ranking_scores
**不修改。** 预热股的 `ScoredStock.rank` 已在外部设为虚拟排名，`record_ranking_scores` 按 rank 写入 `_rank_history`，逻辑不变。

### BacktestPipeline._run_warmup
当前只对 `first_week_codes` 打分，改为：

```python
async def _run_warmup(self, ...):
    while date < actual_start:
        close_prices = day_data["close"]
        
        # 当天正式候选股
        formal_codes = provider.get_candidates_for_date(date)
        formal_close = {k: v for k, v in close_prices.items() if k in formal_codes}
        
        # 预热池
        warmup_codes = self.ctx.warmup_manager.warmup_codes
        warmup_close = {k: v for k, v in close_prices.items() if k in warmup_codes}
        
        # 合并预测
        all_close = {**formal_close, **warmup_close}
        stock_map = await self.score_manager.predict_and_score(
            predictor=self.predictor, data_loader=self.data_loader,
            date=date, close_prices=all_close,
            market_analyzer=self.market_analyzer,
        )
        
        # 虚拟排名：预热股的排名不改变正式股
        scored_list = list(stock_map.values())
        formal_list = [s for s in scored_list if not self.ctx.warmup_manager.is_warmup(s.ts_code)]
        # ... 应用虚拟排名算法 ...
        
        # 预热期同样记录市场指标
        self.market_analyzer.analyze(stock_map, ...)
```

### BacktestPipeline._run_daily_loop（正式期）
预热期结束后，正式交易循环中**也继续维护预热池**：
- 每周第一个交易日调用 `warmup_manager.update_pool()`，更新预热池
- 每天预测时 `close_prices` 包含预热股，预测结果计入 `_score_buffer`
- 预热股的虚拟排名独立计算，不干扰正式排名
- 只有全新出现的候选股才加入预热池（正式期 `_ever_seen` 已饱和）
- 正式池中此前是预热股的股票，此时已有完整的历史

### 预热期周期性更新
每周第一个交易日，在 `_run_warmup` 中调用 `warmup_manager.update_pool(current_week, formal_set)`，确保预热池覆盖未来数周。

## 新增配置

### StrategyConfig

```python
use_candidate_warmup: bool = True       # 是否启用候选股预热
warmup_batch_size: int = 200            # 预热池最大容量
```

预热天数 `warmup_period_days` 不由配置固定，而是由 `_compute_warmup_days` 根据策略参数自动计算（如下）。

### _compute_warmup_days 更新

当前实现：
```python
windows = [
    getattr(strategy_config, 'ranking_smooth_window', 5),
    getattr(strategy_config, 'market_smooth_window', 5),
    getattr(strategy_config, 'rotation_pullback_window', 5),
]
return max(windows) + 10
```

改为：
```python
rotation_needs = (
    getattr(strategy_config, 'rotation_was_top_window', 30)
    + getattr(strategy_config, 'rotation_pullback_window', 5)
    + 1
)
windows = [
    rotation_needs,
    getattr(strategy_config, 'ranking_smooth_window', 5) * 2,
    getattr(strategy_config, 'market_smooth_window', 5) * 2,
]
return max(windows)
```

## 实施计划

### 阶段 1：新建 WarmupManager

1. 新建 `backend/src/trade_alpha/execution/warmup_manager.py`
2. `WarmupRecord` 数据类 + `WarmupManager` 实例类
3. 实现 `update_pool`、`warmup_codes`、`is_warmup`

### 阶段 2：接入 PipelineContext

1. `context.py` 添加 `warmup_manager` 字段（`Optional[WarmupManager]`）
2. `backtest_pipeline.py` 初始化时创建 `WarmupManager` 并注入 ctx

### 阶段 3：修改预热循环

1. 修改 `_compute_warmup_days`，加入 rotation 完整需求
2. 修改 `_run_warmup`：从只打分 `first_week_codes` 改为 `正式 + 预热`
3. 添加虚拟排名逻辑
4. 每周触发 `warmup_manager.update_pool`

### 阶段 4：正式期联动

1. `_run_daily_loop` 中每周切换时调 `warmup_manager.update_pool`
2. 确认预热股转入正式池后 buffer/rank_history 可用

### 阶段 5：测试

1. 集成测试：预热池生成 + 虚拟排名 + 正式期历史连续性
2. 验证预热股积累的 buffer 在入正式池后生效

## 测试要点

- 预热池 = 未来正式股 - 当前正式股，验证不包含多余股票
- 预热股分数最高时虚拟排名=1，最低时=110（或正式股数量），不改变正式排名
- 预热股进入正式池后，`score_buffer` 和 `rank_history` 包含预热期的记录
- 预热池大小不超过 `warmup_batch_size`
- 多个 BacktestPipeline 实例各自持有独立的 WarmupManager
