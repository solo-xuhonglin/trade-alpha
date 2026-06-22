# BuyOrderPlanner — 买入委托单延迟执行设计

## 背景

当前买入委托单直接以当日收盘价成交。当股票单日涨幅过大时，策略追高买入，随后易触发止损。分析显示问题不是选错了股票（如 688347.SH 海光信息买入后最终涨了 +78%），而是**买入时机错误**——在极端超买时入场，回调触发止损后被洗出。

## 架构变更

```
Before:
Strategy.make_orders() → PendingOrder (close price)

After:
Strategy.make_orders() → (sell_orders, recommendations)
                              │
                              ▼
                   BuyOrderPlanner
                   ├─ 缓存推荐股票 (cache_days)
                   ├─ 每日计算 target_price
                   ├─ 计算 priority → 排序
                   └─ 生成 PendingOrder
```

### BuyRecommendation

策略输出的买入建议，不含分数（分数从 ScoreManager 每日评分中实时获取）：

```python
class BuyRecommendation(BaseModel):
    ts_code: str
    stock_name: str
    reason: str
    candidate_group: str = "base"
    added_date: str          # YYYYMMDD
    expire_date: str         # added_date + cache_days
```

### BuyOrderPlanner

新增类，位于 `execution/buy_order_planner.py`：

```python
class BuyOrderPlanner:
    def __init__(self, strategy_config, data_loader):
        self._cache: Dict[str, BuyRecommendation] = {}
        self._config = strategy_config
        self._data_loader = data_loader

    def add_recommendations(self, recs: List[BuyRecommendation]) -> None
        # 新增推荐到缓存，已存在的不覆盖（保留最早 added_date）

    async def generate_orders(
        self, date: str, stock_map: Dict[str, ScoredStock],
        close_prices: Dict[str, float], portfolio, max_daily_buys: int,
    ) -> List[PendingOrder]:
        # 1. 清理过期缓存
        # 2. 批量加载 MA 数据
        # 3. 对每个有效候选：
        #    a. 从 stock_map 获取最新分数
        #    b. target_price = (w_close×close + w_ma5×ma5 + w_ma10×ma10) × (1+buffer)
        #    c. prob = 1 - |close - target| / max(target, 0.01)
        #    d. priority = score_weight × ranking_score + prob_weight × prob
        # 4. 按 priority 降序 → 取 top_n → 生成 PendingOrder

    def expire_before(self, date: str) -> None
        # 清理指定日期前的过期缓存（用于回测初始化）
```

### 价格计算

```
target_price = (w_close × close + w_ma5 × ma5 + w_ma10 × ma10) × (1 + buffer_pct)
```

MA 数据通过 `DataLoader.load_ma_data(date, ts_codes)` 批量加载，复用已有 `stock_daily` 集合。

### 优先级计算

```
priority = score_weight × ranking_score + prob_weight × prob
```

- `ranking_score`: 当日评分结果（每日更新）
- `prob = 1 - |close - target| / max(target, 0.01)` — 价格越接近目标概率越高
- `score_weight`、`prob_weight` 独立配置，不要求归一化

## 策略改造

`multi_stock_strategy.py::make_orders()` 返回类型改为 `Tuple[List[PendingOrder], List[BuyRecommendation]]`：

- 卖出分支不变，仍返回 PendingOrder
- 买入分支（含 rank_up + normal_buy）改为输出 BuyRecommendation
- `max_daily_buys` 限制从策略移至 Planner

## Pipeline 整合

每日循环中：

```python
sell_orders, recommendations = await self.strategy.make_orders(...)
planner.add_recommendations(recommendations)
buy_orders = await planner.generate_orders(
    date, stock_map, close_prices, ctx.portfolio, max_daily_buys,
)
pending_orders = sell_orders + buy_orders
```

## 新增配置参数

前端新增「买入执行」tab：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|:------:|------|
| `buy_cache_days` | int | 3 | 推荐缓存天数 |
| `buy_price_close_weight` | float | 0.3 | 价格计算-收盘价权重 |
| `buy_price_ma5_weight` | float | 0.3 | 价格计算-MA5 权重 |
| `buy_price_ma10_weight` | float | 0.4 | 价格计算-MA10 权重 |
| `buy_price_buffer_pct` | float | 0.01 | 限价单上浮比例 |
| `buy_score_weight` | float | 1.0 | 优先级-分数权重 |
| `buy_prob_weight` | float | 1.0 | 优先级-概率权重 |

## 涉及文件

- **新增**: `backend/src/trade_alpha/execution/buy_order_planner.py`
- **新增**: `backend/src/trade_alpha/schemas.py` (BuyRecommendation)
- **修改**: `backend/src/trade_alpha/strategy/multi_stock_strategy.py` (make_orders 返回 recommendation)
- **修改**: `backend/src/trade_alpha/execution/backtest_pipeline.py` (整合 Planner)
- **修改**: `backend/src/trade_alpha/execution/data_loader.py` (load_ma_data)
- **修改**: `backend/src/trade_alpha/execution/context.py` (可选，传入 Planner)
- **修改**: `backend/src/trade_alpha/dao/strategy_config.py` (7 个新字段)
- **修改**: `backend/src/trade_alpha/strategy/service.py` (参数签名)
- **修改**: `backend/src/trade_alpha/api/schemas.py` (CreateRequest + UpdateRequest)
- **修改**: `frontend/src/api/strategyConfig.ts` (TS 接口)
- **修改**: `frontend/src/views/StrategyConfigView.vue` (新增 tab + 7 个控件 + compareFields)
- **修改**: `backend/src/trade_alpha/dao/execution.py` (StrategySnapshotEmbed)
