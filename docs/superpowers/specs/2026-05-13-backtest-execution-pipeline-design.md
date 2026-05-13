# 回测/实盘执行引擎设计方案

> **日期:** 2026-05-13
> **状态:** 待审查

## 1. 概述

实现一个基于模型预测的执行引擎，同时支持回测(backtest)和实盘(live)两种模式。

每天对市值前300只股票进行模型预测评分，结合当前持仓按评分统一排名，动态维持约10只持仓。

## 2. 核心策略：统一排名换仓

**不固定"每日卖出+买入"分离流程，而是按当天评分统一排名换仓：**

```
每日决策逻辑:
1. 预测所有候选股（市值前300）的上涨概率
2. 获取当前持仓股的当天预测概率
3. 计算每只股票的当天评分
4. 按当天评分降序排列
5. 前10名 = 目标持仓

卖出条件（当前持仓不在前10，或触发以下条件）:
├─ 预测衰减：当天评分 < entry_score × 0.5（信号强度大幅下降）
├─ 止盈：收盘价 >= 买入价 × 1.10
├─ 止损：收盘价 <= 买入价 × 0.95
├─ 到期：hold_days >= 5（强制卖出）
└─ 被挤出前10（被更强信号替代）

买入条件（不在持仓，但在前10）:
├─ 等额分配现金
├─ 隔夜委托价格 = 收盘价 × 1.03
└─ 股数按100股取整
```

这种方式的优点：**新股票信号非常强时自动替换持仓中排名靠后的股票**，不需要硬编码"强制更换"逻辑。

## 3. 总体流程

```
初始化（账户配置、训练记录、日期范围、模式）
    │
    ▼
日循环（date = start_date → end_date）
    │
    ├─ 1. 核算前一天隔夜委托成交
    │    ├─ 加载当天最低价
    │    └─ day_low <= order_price → 成交，否则回滚
    │
    ├─ 2. 加载当天数据（市值前300 + 当前持仓）
    │
    ├─ 3. 对每只股票进行预测
    │    ├─ label_3d: [P(-1), P(0), P(1)] → up_prob_3d = P(1)
    │    └─ label_5d: [P(-1), P(0), P(1)] → up_prob_5d = P(1)
    │
    ├─ 4. 计算当天评分
    │    score = up_prob_3d × 0.4 + up_prob_5d × 0.6
    │
    ├─ 5. 统一排名换仓
    │    ├─ 所有股票按当天评分降序
    │    ├─ 对当前持仓：是否在前10？是否触发衰减/止盈/止损/到期？
    │    ├─ 卖出决议 → 结算，生成 ExecutionTrade
    │    └─ 买入决议 → 生成 OrderSuggestion（status=pending）
    │
    ├─ 6. 保存日快照 ExecutionPortfolioDaily
    │    ├─ 当天已卖出股票：按卖出价结算市值
    │    └─ 当天未卖出股票：按收盘价计算市值
    │
    └─ 7. date = next_day

回测结束 → 计算 ExecutionResult
```

## 4. 模式设计

| 模式 | 回测 backtest | 实盘 live |
|------|-------------|----------|
| 数据来源 | MongoDB 历史数据 | 实时API（预留） |
| 成交 | day_low <= order_price 模拟 | 实盘成交（预留） |
| 订单状态 | 自动核算 | 人工/系统处理 |
| 相同点 | 预测、排名、换仓逻辑完全一致 | |

pipeline 中统一控制：

```python
class ExecutionPipeline:
    async def run(
        self,
        mode: Literal["backtest", "live"],
        ...
    ):
        if mode == "backtest":
            # 走循环回测
        else:  # live
            # 单次执行（买入/卖出决策）
```

## 5. 数据模型变更

### 5.1 Position（嵌入模型）— 修改

```python
class PositionEmbed(BaseModel):
    ts_code: str
    stock_name: str
    buy_date: str
    buy_price: float
    shares: int
    fee: float
    entry_score: float      # 买入时的综合评分
    entry_3d_prob: float    # 买入时3日上涨概率
    entry_5d_prob: float    # 买入时5日上涨概率
    hold_days: int = 0
```

### 5.2 ExecutionResult — 重写

```python
class ExecutionResult(Document):
    account_config_id: PydanticObjectId
    training_id: PydanticObjectId
    name: str
    mode: str = "backtest"            # backtest / live
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float
    total_return: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    total_fees: float
    account_snapshot: Optional[AccountSnapshotEmbed] = None
    model_snapshot: Optional[ModelSnapshotEmbed] = None
    created_at: datetime = Field(default_factory=datetime.now)
    status: str = "completed"    # running / completed / failed
```

### 5.3 ExecutionPortfolioDaily — 重写

```python
class ExecutionPortfolioDaily(Document):
    backtest_id: PydanticObjectId
    date: str
    cash: float
    positions: List[PositionEmbed] = Field(default_factory=list)
    total_market_value: float = 0.0        # 持仓市值
    total_value: float = 0.0               # 总资产 = 现金 + 市值
    day_return: float = 0.0                # 当日收益率
    mode: str = "backtest"
```

### 5.4 OrderSuggestion — 重写

```python
class OrderSuggestion(Document):
    backtest_id: PydanticObjectId
    ts_code: str
    stock_name: str
    trade_date: str                   # 下单日期（预测日）
    settle_date: str                  # 成交结算日期（次日）
    action: str                       # buy
    order_price: float                # 委托价格 = close × 1.03
    order_shares: int                 # 委托股数
    score: float                      # 当天评分
    up_prob_3d: float
    up_prob_5d: float
    status: str = "pending"           # pending / executed / failed
    actual_price: Optional[float] = None
    actual_shares: Optional[int] = None
    fee: Optional[float] = None
    cash_after: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.now)
```

### 5.5 ExecutionTrade — 修改（增加买入参考信息）

```python
class ExecutionTrade(Document):
    backtest_id: PydanticObjectId
    ts_code: str
    trade_date: str
    action: str                       # buy / sell
    price: float
    shares: int
    fee: float
    cash_after: float
    reason: Optional[str] = None      # 卖出原因
    entry_score: Optional[float] = None    # 买入时评分（仅buy）
    up_prob_3d: Optional[float] = None
    up_prob_5d: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.now)
    mode: str = "backtest"
```

## 6. 模块设计

### 6.1 模块结构

```
execution/
├── __init__.py
├── schemas.py           → 非持久化 dataclass（运行状态）
├── data_loader.py       → 加载日数据 + top300过滤
├── predictor.py         → 调用 predict_proba 获取上涨概率
├── position_manager.py  → 持仓管理、排名、买卖决策
├── pipeline.py          → 主循环编排
└── backtest_service.py  → 回测服务（API调用入口）

strategy/
├── __init__.py          → 清空，删除所有策略引用
├── service.py           → 移除废弃的generate_signal
  （删除 base.py, price.py, ma.py, macd.py）
```

### 6.2 DataLoader

```python
class DataLoader:
    async def get_top_stocks(self, date: str, limit: int = 300) -> List[Dict]:
        """获取当天市值前N只股票（ts_code, name, close等）."""

    async def load_day_data(self, date: str, ts_codes: List[str]) -> pd.DataFrame:
        """加载某天所有股票数据（含指标字段），用于预测."""

    async def load_day_low(self, date: str, ts_codes: List[str]) -> Dict[str, float]:
        """加载某天最低价，用于成交核算."""

    async def load_day_close(self, date: str, ts_codes: List[str]) -> Dict[str, float]:
        """加载某天收盘价，用于市值计算."""
```

### 6.3 Predictor

```python
class Predictor:
    def __init__(self, training_id: PydanticObjectId):
        self.training_id = training_id
        # 初始化时加载 training, config, normalizer, classifier

    async def predict_batch(
        self, df: pd.DataFrame, ts_codes: List[str], date: str
    ) -> Dict[str, Dict]:
        """批量预测，返回 {ts_code: {up_prob_3d, up_prob_5d, score}}"""

    async def predict_single(
        self, df: pd.DataFrame, ts_code: str, date: str
    ) -> Dict:
        """单只预测，用于持仓股当天重新预测."""
```

### 6.4 PositionManager

```python
class PositionManager:
    def __init__(self, account_config: AccountConfig):
        self.cash = account_config.initial_capital
        self.positions: List[PositionEmbed] = []
        self.acc_config = account_config

    def make_decisions(
        self,
        all_scores: Dict[str, Dict],    # {ts_code: {score, up_prob_3d, up_prob_5d, close, stock_name}}
        top_n: int = 10,
        max_hold_days: int = 5,
        stop_loss: float = 0.95,
        take_profit: float = 1.10,
        decay_ratio: float = 0.5,
    ) -> (List[OrderSuggestion], List[ExecutionTrade]):
        """
        统一排名换仓决策:
        1. 预测分数排名取前10
        2. 卖出：不在前10的持仓 / 触发衰减/止盈/止损/到期的持仓
        3. 买入：在前10但不在持仓的股票
        """
```

#### 买入决策详细逻辑

```python
def _allocate_buy(self, close_price: float, available_cash: float) -> Optional[Tuple[int, float, float]]:
    """等额分配，100股取整."""
    cash_per_stock = available_cash / max(1, remaining_slots)
    order_price = round(close_price * 1.03, 2)
    shares = int(cash_per_stock / order_price / 100) * 100
    if shares < 100:
        return None

    total_cost = shares * order_price
    fee = max(total_cost * self.acc_config.buy_fee_rate, self.acc_config.min_fee)
    return shares, order_price, fee
```

#### 卖出条件详细逻辑

```python
def _check_sell(
    self, pos: PositionEmbed, current_score: float,
    current_close: float, max_hold: int, decay_ratio: float
) -> Optional[str]:
    if pos.hold_days >= max_hold:
        return "expired"
    if current_close >= pos.buy_price * 1.10:
        return "take_profit"
    if current_close <= pos.buy_price * 0.95:
        return "stop_loss"
    if current_score < pos.entry_score * decay_ratio:
        return "decay"
    return None
```

### 6.5 Pipeline

```python
class ExecutionPipeline:
    """主循环编排，同时支持回测和实盘."""

    def __init__(self, account_config, training_id, mode="backtest"):
        self.mode = mode
        self.data_loader = DataLoader()
        self.predictor = Predictor(training_id)
        self.position_manager = PositionManager(account_config)

    async def run_backtest(
        self, start_date: str, end_date: str,
        top_n: int = 300, max_positions: int = 10, ...
    ) -> ExecutionResult:

        date = start_date
        while date <= end_date:
            # 1. 结算昨日订单（第一天跳过）
            if date > start_date:
                day_low = await self.data_loader.load_day_low(date, pending_ts_codes)
                self.position_manager.settle_orders(day_low)

            # 2. 加载当天 top300 数据
            top_stocks = await self.data_loader.get_top_stocks(date, top_n)
            ts_codes = [s["ts_code"] for s in top_stocks]
            df = await self.data_loader.load_day_data(date, ts_codes)

            # 3. 预测所有股票
            predictions = await self.predictor.predict_batch(df, ts_codes, date)

            # 4. 统一排名换仓
            buys, sells = self.position_manager.make_decisions(
                predictions, top_n=max_positions
            )

            # 5. 保存日快照
            snapshot = self.position_manager.daily_snapshot(date)
            await snapshot.insert()

            date = self._next_date(date)
    ↑
    ↓

    async def run_live(self, date: str) -> List[OrderSuggestion]:
        """实盘单次执行（不循环，由调度器定时触发）."""
        # ... 类似逻辑，只执行当天决策，不循环
```

## 7. 买入算法

```python
cash_per_stock = available_cash / buy_count
order_price = round(close * 1.03, 2)
shares = int(cash_per_stock / order_price / 100) * 100

# 至少一手
if shares < 100:
    return None

# 验证费用
fee_rate = account_config.buy_fee_rate
min_fee = account_config.min_fee
fee = max(shares * order_price * fee_rate, min_fee)
total_needed = shares * order_price + fee

# 如果不够，递减
while total_needed > cash_per_stock and shares >= 100:
    shares -= 100
    fee = max(shares * order_price * fee_rate, min_fee)
    total_needed = shares * order_price + fee

return shares, order_price, fee
```

## 8. 成交核算算法

```python
def settle_orders(self, day_low: Dict[str, float]):
    """核算隔夜委托."""
    for order in self.pending_orders:
        low = day_low.get(order.ts_code)
        if low is None:
            order.status = "failed"
            continue

        if low <= order.order_price:
            # 成交
            order.status = "executed"
            order.actual_price = order.order_price
            order.actual_shares = order.order_shares
            fee = max(order.order_shares * order.order_price * fee_rate, min_fee)
            order.fee = fee
            total_cost = order.actual_price * order.actual_shares + fee

            # 更新持仓和现金
            self.cash -= total_cost
            self.positions.append(PositionEmbed(
                ts_code=order.ts_code,
                stock_name=order.stock_name,
                buy_date=order.trade_date,
                buy_price=order.actual_price,
                shares=order.actual_shares,
                fee=fee,
                entry_score=order.score,
                entry_3d_prob=order.up_prob_3d,
                entry_5d_prob=order.up_prob_5d,
            ))
            order.cash_after = self.cash
        else:
            # 未成交，资金回滚
            order.status = "failed"
```

## 9. 文件变更清单

| 文件 | 操作 |
|------|------|
| `dao/position.py` | **重写**：PositionEmbed 增加字段 |
| `dao/execution.py` | **重写**：支持多股票 |
| `dao/execution_portfolio_daily.py` | **重写**：增加市值/收益字段 |
| `dao/execution_trade.py` | **重写**：增加原因/评分字段 |
| `dao/order_suggestion.py` | **重写**：适配新字段 |
| `execution/schemas.py` | **重写** |
| `execution/data_loader.py` | **重写** |
| `execution/predictor.py` | **重写** |
| `execution/position_manager.py` | **重写** |
| `execution/pipeline.py` | **重写** |
| `execution/__init__.py` | **重写** |
| `strategy/base.py` | **删除** |
| `strategy/price.py` | **删除** |
| `strategy/ma.py` | **删除** |
| `strategy/macd.py` | **删除** |
| `strategy/__init__.py` | **重写** |
| `strategy/service.py` | **简化** |

## 10. 文档更新

- `docs/database-schema.md`：更新 execution_* 表结构
- `docs/api.md`：添加回测 API / 实盘 API
- `docs/system-design.md`：更新模块说明
