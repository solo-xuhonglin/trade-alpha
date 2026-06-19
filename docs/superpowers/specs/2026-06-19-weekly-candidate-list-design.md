# 周度动态候选股票列表设计文档

## 问题

现有月度动态候选股票列表的局限：

1. **更新频率低**：每月只在首个交易日更新一次，候选池变化滞后
2. **选股维度单一**：仅依赖总市值排名，未考虑市值短期动量（市值快速增长的股票）
3. **动量股票生命周期短**：市值周涨幅靠前的股票如果只被选入一个月，可能刚建仓就落选

## 方案：周度双选股 + 滚动保留

### 核心思路

每周第一个交易日，从 StockListHistory 中：
1. 取市值前 `range_n`（默认 500）作为计算池
2. 从计算池中取市值前 `top_n`（默认 100）→ 市值组
3. 从计算池中计算市值周变化率，取前 `up_n`（默认 50）→ 动量组
4. 当前周基础池 = union(市值组, 动量组)
5. 当前周最终候选 = 当前周基础池 ∪ 上周基础池（滚动保留）

### 参数

| 参数 | 默认值 | 来源 | 含义 |
|------|--------|------|------|
| `range_n` | 500 | **新增** | 计算池大小，从 StockListHistory 取市值前 N |
| `top_n` | 100 | **已有** | 市值组大小，从计算池中按 total_mv 取前 N |
| `up_n` | 50 | **新增** | 动量组大小，从计算池中按市值周变化率取前 N |

### 数据流

```
Week N:
  StockListHistory.get_top(range_n=500)
    ├─ sort by total_mv DESC → top top_n=100      → 市值组 A
    └─ calc weekly_mv_change → top up_n=50         → 动量组 B

  base_N = union(A, B)                              → ≤150只
  final_N = base_N ∪ base_{N-1}                     → 滚动保留，约200~280只

Week N+1:
  final_{N+1} = base_{N+1} ∪ base_N
```

### 候选池数据格式

```python
# key 由 YYYYMM 改为 YYYYMMDD（每周首个交易日日期）
candidate_map = {
    "20240102": [ts_codes...],   # Week 1 final
    "20240108": [ts_codes...],   # Week 2 final
    "20240116": [ts_codes...],   # Week 3 final
    ...
}
```

### Pipeline 匹配逻辑

Pipeline 不再用 `date[:6]` 查找月度 key，改用最近邻查找：

```python
def _get_week_key(self, date: str) -> Optional[str]:
    """找到当前日期所属的周（最大的 week_key <= date）。"""
    sorted_keys = sorted(self.candidate_map.keys())
    for key in reversed(sorted_keys):
        if date >= key:
            return key
    return None
```

## 影响范围

### 涉及文件

| # | 文件 | 操作 | 说明 |
|---|------|------|------|
| 1 | `backend/src/trade_alpha/execution/candidate_list_provider.py` | **重写** ~100 行 | 周度 key、三参数、市值变化率计算、滚动保留 |
| 2 | `backend/src/trade_alpha/execution/backtest_pipeline.py` | 修改 ~20 行 | 新增 `_get_week_key()`，替换 `date[:6]` 查找 |
| 3 | `backend/src/trade_alpha/task/backtest_runner.py` | 修改 ~10 行 | 传递 `range_n`, `up_n` |
| 4 | `backend/src/trade_alpha/api/routers/backtest.py` | 修改 ~5 行 | Request schema 新增 `range_n`, `up_n` |
| 5 | `backend/tests/trade_alpha/unit/execution/test_candidate_list_provider.py` | **重写** | 适配周度+双选股+滚动保留 |
| 6 | `frontend/src/views/BacktestManageView.vue` | 修改 ~15 行 | 前端表单新增 range_n, up_n 输入 |
| 7 | `frontend/src/api/backtest.ts` | 修改 ~3 行 | 接口类型补充 |

### 不涉及改动的文件

| 文件 | 原因 |
|------|------|
| `BaselineTracker` | 逻辑不变，仅候选池来源变化 |
| `constants.py` | 常量和新增已在上一次提交完成 |
| `DataLoader` | 数据加载逻辑不变 |
| `ScoreManager` | 评分逻辑不变 |
| `MultiStockStrategy` | 策略逻辑不变 |
| `MarketRegimeAnalyzer` | 市况分析逻辑不变 |
| `SuggestionPipeline` | 仅影响回测，不影响实盘建议 |

## 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| key 格式 | `YYYYMMDD`（周首个交易日） | 每周期约 5 个交易日，key 足够区分且可排序 |
| 周变化率计算 | (本周mv - 上周mv) / 上周mv | 与市场通用的周涨跌幅定义一致 |
| 滚动保留 | 保留上周基础池 | up_n 股票最少存续 2 周，减少频繁换仓 |
| 变化率来源 | StockListHistory.total_mv | 与市值排名同一数据源，无需额外查询 |
| range_n 作为独立参数 | 可自定义计算池大小 | 灵活应对不同市场规模 |
