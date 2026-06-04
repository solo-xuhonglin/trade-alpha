# Live Suggestion 模块改造设计

## 1. 概述

对实盘建议模块进行全面改造，引入每日全量评分排名机制，支持定时自动运行 + 手动回填历史日期，新增每日排名展示页面。

## 2. 数据模型

### 2.1 改名

| 旧名 | 新名 | 文件 |
|------|------|------|
| `OrderSuggestion` | `LiveOrderSuggestion` | `dao/live_order_suggestion.py` |

### 2.2 新增模型 `LiveDailyStockScore`

文件：`dao/live_daily_stock_score.py`

```python
class LiveDailyStockScore(Document):
    ts_code: str                           # 股票代码
    trade_date: str                        # 交易日 YYYYMMDD
    stock_name: Optional[str] = None       # 股票名称
    rank: int = 0                          # 当日排名
    composite_score: float = 0.0           # 综合评分
    ranking_score: float = 0.0             # 排序评分
    up_prob_3d: float = 0.0                # 3日上涨概率
    up_prob_5d: float = 0.0                # 5日上涨概率
    up_prob_10d: float = 0.0               # 10日上涨概率
    trend_bonus: float = 0.0               # 趋势加分
    vol_penalty: float = 0.0               # 波动扣分
    momentum_bonus: float = 0.0            # 动量加成
    order_price: float = 0.0               # 参考价格
    order_shares: int = 0                  # 建议股数
    is_excluded: bool = False              # 是否被排除
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "live_daily_stock_score"
        indexes = [
            [("ts_code", 1), ("trade_date", 1)],  # 复合唯一键
            [("trade_date", -1), ("rank", 1)],     # 按日查询排序
        ]
```

唯一约束：`(ts_code, trade_date)` — upsert 语义，同一天同一只股票只有一份评分。

### 2.3 模型关系

```
LiveSuggestionRun (执行元数据)
  ├── 每次运行生成
  ├── LiveDailyStockScore (全量 N 只股票评分) ← 新增
  └── LiveOrderSuggestion (最终 top K 建议)  ← 原有，改名
```

## 3. Pipeline 改造

### 3.1 `run_live_suggestion` 方法变化

参数增加可选的 `target_dates`：

```python
async def run_live_suggestion(
    self,
    task_id: Optional[PydanticObjectId] = None,
    universe_limit: int = 300,
    target_dates: Optional[list[str]] = None,  # 新增
) -> PydanticObjectId:
```

**不传 `target_dates`**：沿用当前逻辑，跑最新交易日（自动触发默认行为）。

**传 `target_dates`**：逐个交易日执行评分流程：
1. 对每个日期，进行预热 → 评分 → 排名
2. 全量评分结果 upsert 到 `LiveDailyStockScore`
3. 筛选 top K 写入 `LiveOrderSuggestion`

### 3.2 评分输出变更

每次评分后，新增一步：

```python
# Upsert to LiveDailyStockScore
for stock_result in all_scores:
    await LiveDailyStockScore.find_one_and_update(
        {"ts_code": stock_result.ts_code, "trade_date": target_date},
        {"$set": {**stock_result.dict(), "updated_at": datetime.utcnow()}},
        upsert=True,
    )
```

## 4. API 接口

### 4.1 修改 `POST /live-suggestion/run`

Request body 增加可选字段：

```typescript
{
  account_config_id: string
  training_id: string
  strategy_config_id: string
  start_date?: string  // YYYYMMDD，可选
  end_date?: string    // YYYYMMDD，可选
}
```

- 不传 start_date/end_date：跑最新交易日（现有行为）
- 传了范围：逐个交易日回填

### 4.2 新增 `GET /live-suggestion/daily-scores`

```python
@router.get("/daily-scores")
async def list_daily_scores(
    trade_date: Optional[str] = None,  # 不传则查最新日
    page: int = 1,
    page_size: int = 100,
):
```

返回分页的 `LiveDailyStockScore` 列表，默认按 `rank` 升序。

### 4.3 其他接口不变

`GET /runs`、`GET /runs/{run_id}`、`DELETE /runs/{run_id}` 等保持现有逻辑。

## 5. 定时任务联动

18:00 定时任务保持不变（已在 `data_sync.py` 中配置 `_run_daily_update_and_auto_suggest`）。

pipeline 改造后，自动触发的实盘建议会自动写入 `LiveDailyStockScore`，无需额外改动。

## 6. 前端变更

### 6.1 菜单结构

```
实盘（一级）
├── 实盘管理    /live-suggestion/manage
├── 每日排名    /live-suggestion/daily-rankings  ← 新增
└── 实盘记录    /live-suggestion/records
```

### 6.2 实盘管理页修改

表单增加日期字段：

```
账户配置 | 训练结果 | 策略配置
开始日期 | 结束日期
[发起建议]
```

- 日期不填 = 跑最新交易日
- 日期填了 = 回填该范围内每个交易日

### 6.3 每日排名页（新增）

```
路由：/live-suggestion/daily-rankings
文件：DailyRankingsView.vue
```

页面结构：
- 顶部日期选择器（默认最新交易日）
- `v-data-table-server` 展示全量股票排名
- 列：排名、股票名称、代码、综合评分、排序评分、涨概率(3/5/10日)、趋势加分、波动扣分、动量加成、参考价格

### 6.4 新增前端 API

```typescript
export const liveSuggestionApi = {
  // 原有
  trigger: (body: { account_config_id, training_id, strategy_config_id, start_date?, end_date? }) => ...
  listRuns: ...
  getRun: ...
  deleteRun: ...

  // 新增
  listDailyScores: (tradeDate?: string, page?: number, pageSize?: number) =>
    api.get('/live-suggestion/daily-scores', { params: { trade_date: tradeDate, page, page_size: pageSize } }),
}
```

## 7. 涉及文件清单

| 文件 | 动作 |
|------|------|
| `dao/live_daily_stock_score.py` | 新建 |
| `dao/order_suggestion.py` | 重命名为 `live_order_suggestion.py` |
| `dao/__init__.py` | 更新导出 |
| `execution/pipeline.py` | 修改 `run_live_suggestion`，增加 `target_dates` 参数 + 写入 `LiveDailyStockScore` |
| `api/routers/live_suggestion.py` | 修改 run 接口参数 + 新增 daily-scores 接口 |
| `api/liveSuggestion.ts` | 新增 `listDailyScores` |
| `views/DailyRankingsView.vue` | 新建 |
| `views/LiveSuggestionManageView.vue` | 表单增加日期字段 |
| `router/index.ts` | 新增 `/live-suggestion/daily-rankings` 路由 |
| `components/AppLayout.vue` | 菜单增加「每日排名」 |

## 8. 未涉及事项

- 卖出建议：后期再扩展（当前只做买入评分排名）
- 旧 `OrderSuggestion` 数据迁移：保留原集合不动，代码层改名即可
- 每日排名的历史数据清理：暂时不做，留待后续