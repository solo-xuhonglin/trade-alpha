# Suggestion Service + Backend Test 重构设计

## 背景

将 `test_65`（SuggestionPipeline 运行）、`test_66`（suggestion 验证字段）、`test_67`（daily scores 字段）三个测试类合并为一个编号 71 的测试类。同时将 API router 中内联的查询/计算逻辑提取到 service 层，对齐 backtest 的 pipeline + service 模式。

## 文件结构变更

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `execution/suggestion_service.py` | 建议/分数查询 service |
| 重命名 | `execution/service.py` → `execution/backtest_service.py` | 对齐 backtest 命名 |
| 修改 | `api/routers/live_suggestion.py` | `list_suggestions`、`list_daily_scores`、`list_stock_daily_scores` 改调 service |
| 修改 | `tests/test_61_backtest_lstm.py` | import 更新 |
| 新建 | `tests/test_71_suggestion.py` | 合并 65/66/67 |
| 删除 | `tests/test_65_live_suggestion.py` | 已合并 |
| 删除 | `tests/test_66_suggestion_validation.py` | 已合并 |
| 删除 | `tests/test_67_daily_rankings_avg.py` | 已合并 |

## SuggestionService 设计

### 位置
`backend/src/trade_alpha/execution/suggestion_service.py`

### 函数签名

```python
async def list_suggestions(
    trade_date: str,
    page: int = 1,
    page_size: int = 100,
) -> dict
```

从 `LiveOrderSuggestion` 查询指定交易日的建议，`StockDaily` 计算 `actual_return_{n}d` 字段。返回分页 dict。

```python
async def list_daily_scores(
    trade_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 100,
) -> dict
```

从 `LiveDailyStockScore` 查询分数，计算 `avg_rank_{N}d` 和 `rank_change` 字段。返回分页 dict。

```python
async def list_stock_daily_scores(ts_code: str) -> dict
```

从 `LiveDailyStockScore` 查询指定股票的全部分数。返回 dict。

### API 变薄

```python
@router.get("/suggestions")
async def list_suggestions(trade_date: str, page: int = 1, page_size: int = 100):
    return await suggestion_service.list_suggestions(trade_date, page, page_size)
```

## 测试设计（test_71）

### 位置
`backend/tests/trade_alpha/integration/test_71_suggestion.py`

### Fixture

class-scoped `pipeline_run` fixture：运行一次 SuggestionPipeline（固定日期 20260105-20260106），创建建议数据供后续测试复用。teardown 清理全部创建的数据。

### 测试用例（4 个）

| 测试 | 说明 |
|------|------|
| `test_pipeline_completes_successfully` | Pipeline 运行完成，状态 = completed |
| `test_actual_return_computation` | `list_suggestions` 返回的 actual_return_3d 是有效 float |
| `test_avg_rank_computation` | `list_daily_scores` 返回 avg_rank/rank_change 满足基本约束 |
| `test_stock_detail_query` | `list_stock_daily_scores` 返回有效数据 |

### 约束满足

- 不使用 API client（直接调 service函数）
- 固定历史日期，不影响最新实盘建议
- 测试 service 层
- 不使用 direction_correct 字段（已移除）

## backtest_service 重命名

`execution/service.py` → `execution/backtest_service.py`

- logger name 改为 `"backtest.service"`
- 更新 `test_61_backtest_lstm.py` import