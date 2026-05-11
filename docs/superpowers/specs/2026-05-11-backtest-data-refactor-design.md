# 回测数据重构设计

## 背景

当前 `backtest_trades` 独立存储，存在配置后续更新导致历史回测不一致的问题。

## 目标

回测记录自包含配置快照，确保历史数据完整性；交易记录和每日账户快照独立存储以支持灵活查询。

## 变更内容

### 1. AccountConfig 调整

移除运行时状态字段，转为纯配置模型：

| 移除字段 | 说明 |
|---------|------|
| cash | 运行时状态 |
| position | 运行时状态 |

**保留字段**：name, initial_capital, buy_fee_rate, sell_fee_rate, stamp_tax_rate, min_fee, created_at, updated_at

### 2. BacktestResult 新增字段

```python
class BacktestResult(Document):
    # 原有字段保持不变...
    portfolio_snapshot: AccountSnapshot    # 账户配置快照
    strategy_snapshot: StrategySnapshot     # 策略配置快照
```

#### AccountSnapshot
复用 AccountConfig，序列化时排除 id, created_at, updated_at

#### StrategySnapshot
复用 StrategyConfig，序列化时排除 id, created_at, updated_at

### 3. 独立集合

#### backtest_trades
存储交易记录

**索引**: `{backtest_id: 1}` 索引

**字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| backtest_id | ObjectId | 关联的回测ID |
| ts_code | string | 股票代码 |
| trade_date | string | 交易日期 |
| action | string | "buy" / "sell" |
| price | float | 成交价格 |
| shares | int | 成交股数 |
| fee | float | 手续费 |
| cash_after | float | 交易后现金 |
| position_after | int | 交易后持仓 |

#### backtest_portfolio_daily
存储每日账户快照

**索引**: `{backtest_id: 1, date: 1}` 索引

**字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| backtest_id | ObjectId | 关联的回测ID |
| date | string | 日期 |
| cash | float | 当日现金 |
| positions | array | 持仓列表 [{ts_code, shares}] |
| market_value | float | 持仓市值 |
| total_value | float | 总资产 |
| position_ratio | float | 仓位比例 |

### 4. BacktestEngine 修改

在 `run()` 方法中新增每日快照生成：

```python
def run(self, records: List[Dict]) -> BacktestResult:
    # 原有逻辑...
    # 新增：每日收盘后记录快照
    self.daily_snapshots.append(DailySnapshot(
        date=record["trade_date"],
        cash=self.portfolio.cash,
        positions=[Position(ts_code=self.ts_code, shares=self.portfolio.position)],
        market_value=self.portfolio.position * float(record["close"]),
        total_value=self.portfolio.cash + self.portfolio.position * float(record["close"]),
        position_ratio=...
    ))
```

### 5. Service 层修改

- `save_backtest()` 序列化配置快照到主文档
- 新增 `save_daily_snapshots()` 保存每日快照到独立集合
- `save_trades()` 保持不变（独立集合）

### 6. API 调整

| 接口 | 调整 |
|------|------|
| `GET /backtests/{id}` | 响应包含 portfolio_snapshot, strategy_snapshot |
| `GET /backtests/{id}/trades` | 从 backtest_trades 集合查询 |
| `GET /backtests/{id}/daily` | 新增接口，从 backtest_portfolio_daily 集合查询 |

## 文件变更清单

| 文件 | 操作 |
|------|------|
| `dao/portfolio.py` | 移除 cash, position 字段 |
| `dao/backtest.py` | 新增嵌入字段（AccountSnapshotEmbed, StrategySnapshotEmbed） |
| `dao/position.py` | 新增（持仓嵌入模型） |
| `dao/backtest_portfolio_daily.py` | 新增 |
| `dao/__init__.py` | 新增导出 |
| `backtest/service.py` | 修改保存逻辑 |
| `backtest/engine.py` | 新增每日快照生成 |
| `api/routers/backtest.py` | 调整接口 |

## 数据迁移

1. AccountConfig：删除 cash, position 字段
2. 新增 backtest_portfolio_daily 集合

## 测试更新

- `tests/integration/test_60_backtest.py` - 更新断言逻辑
