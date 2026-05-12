# 统一回测与实盘执行框架设计

## 1. 背景与目标

### 1.1 问题
当前系统回测和实盘的流程分离，维护成本高。实盘逻辑缺失，无法实现"收盘后自动计算，生成委托单建议"的闭环。

### 1.2 目标
构建统一的执行框架，复用数据处理、预测、信号生成逻辑，仅在最后一步区分：
- **回测模式**：自动执行交易，记录结果
- **实盘模式**：输出委托单建议，供人工干预

### 1.3 核心原则
- 流程统一，末端区分
- 模型/策略可扩展（支持自定义预处理/后处理）
- 表结构统一，通过 mode 字段区分回测/实盘

---

## 2. 总体架构

### 2.1 流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                      执行引擎 (Execution Engine)                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. 数据加载 ──→ 2. 指标计算 ──→ 3. 模型预测 ──→ 4. 信号生成   │
│           │                                    │               │
│           ▼                                    ▼               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   5. 仓位管理                            │   │
│  │         (多股票信号 → 委托单权重分配)                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                   │
│           ┌────────────────┴────────────────┐                  │
│           ▼                                 ▼                  │
│  ┌──────────────────┐           ┌──────────────────┐           │
│  │   回测执行器      │           │   实盘建议生成器  │           │
│  │  (自动交易)       │           │  (输出委托单建议)  │           │
│  └──────────────────┘           └──────────────────┘           │
│           │                                 │                  │
│           ▼                                 ▼                  │
│  execution_results               order_suggestions              │
│  execution_trades                (人工干预后执行)               │
│  execution_portfolio_snapshots                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 目录结构

```
backend/src/trade_alpha/
├── data/                          # 数据加载
│   ├── service.py                 # 数据服务
│   └── loader.py                  # 数据加载器（新增）
├── indicators/                     # 指标计算
│   └── service.py                 # 指标服务
├── predict/                        # 预测模块
│   ├── base.py                    # 预测器基类（增强）
│   ├── service.py                 # 预测服务（增强）
│   ├── registry.py                # 预测器注册表（新增）
│   └── normalizer.py              # 数据标准化器（新增）
├── strategy/                       # 策略模块
│   ├── base.py                    # 策略基类（增强）
│   └── service.py                 # 策略服务（增强）
├── execution/                      # 执行引擎（重构/新增）
│   ├── __init__.py
│   ├── pipeline.py                # 统一流程编排
│   ├── data_loader.py             # 数据加载器
│   ├── predictor.py               # 预测管理器
│   ├── signal_generator.py        # 信号生成器
│   ├── position_manager.py         # 仓位管理器
│   ├── backtest_runner.py          # 回测执行器
│   ├── live_suggestor.py           # 实盘建议生成器
│   └── schemas.py                  # 数据结构
├── scheduler/                      # 定时任务（新增）
│   └── live_trading.py             # 实盘定时任务
├── account/                        # 账户管理
│   └── account_manager.py          # 账户管理器
├── dao/                            # DAO 层
│   ├── execution.py                # execution_results (重命名)
│   ├── execution_trade.py          # execution_trades (重命名)
│   ├── execution_portfolio_daily.py # execution_portfolio_snapshots (重命名)
│   └── order_suggestion.py         # order_suggestions (新增)
└── api/
    └── routers/
        ├── backtest.py             # 保留（向后兼容）
        └── execution.py            # 统一执行 API (新增/调整)
```

---

## 3. 数据库结构

### 3.1 集合重命名

| 原名 | 新名 | 说明 |
|------|------|------|
| `backtest_results` | `execution_results` | 执行结果主记录 |
| `backtest_trades` | `execution_trades` | 交易记录 |
| `backtest_portfolio_daily` | `execution_portfolio_snapshots` | 持仓快照 |

### 3.2 execution_results 新增字段

| 字段 | 类型 | 说明 |
|-----|------|------|
| `mode` | string | "backtest" \| "live" |

### 3.3 execution_trades 新增字段

| 字段 | 类型 | 说明 |
|-----|------|------|
| `mode` | string | "backtest" \| "live" |
| `status` | string | "pending" \| "executed" \| "cancelled" |
| `execution_time` | datetime | 执行时间（实盘用） |

### 3.4 execution_portfolio_snapshots 新增字段

| 字段 | 类型 | 说明 |
|-----|------|------|
| `mode` | string | "backtest" \| "live" |

### 3.5 新增集合：order_suggestions

| 字段 | 类型 | 说明 |
|-----|------|------|
| `execution_result_id` | ObjectId | 关联执行结果ID |
| `ts_code` | string | 股票代码 |
| `stock_name` | string | 股票名称 |
| `date` | string | 日期 YYYYMMDD |
| `action` | string | "buy" \| "sell" \| "hold" |
| `suggested_price` | float | 建议价格 |
| `suggested_shares` | int | 建议数量 |
| `signal_strength` | float | 信号强度 [0, 1] |
| `position_reason` | string | 仓位分配理由 |
| `risk_notes` | string | 风险提示 |
| `prediction_data` | object | 预测相关数据 |
| `account_config_id` | ObjectId | 账户配置ID |
| `strategy_id` | ObjectId | 策略ID |
| `training_id` | ObjectId | 训练结果ID |
| `status` | string | "pending" \| "accepted" \| "rejected" \| "executed" |
| `created_at` | datetime | 创建时间 |

---

## 4. 核心接口设计

### 4.1 数据标准化设计（两种方式）

训练一个统一模型预测 3000+ 只股票，根据模型类型选择不同的标准化方式。

#### 4.1.1 标准化器基类

```python
class BaseNormalizer(ABC):
    """数据标准化器基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """标准化器名称: "sliding_window" | "cross_sectional" """
        pass

    @abstractmethod
    def normalize(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        training_stats: Optional[Dict[str, dict]] = None
    ) -> Tuple[np.ndarray, Dict[str, dict]]:
        """
        标准化数据
        - df: 输入数据 (多股票、多时间点)
        - feature_cols: 需要标准化的特征列
        - training_stats: 训练时的统计量（用于实盘）
        返回: (标准化后的数组, 当前统计量)
        """
        pass

    @abstractmethod
    def inverse_transform(
        self,
        data: np.ndarray,
        feature_cols: List[str],
        stats: Dict[str, dict]
    ) -> np.ndarray:
        """反标准化（用于还原预测结果）"""
        pass
```

#### 4.1.2 滑动窗口标准化器（Sliding Window）

**适用模型**：LSTM

**场景**：每个股票取 60 天滑动窗口，在窗口内进行标准化

```python
class SlidingWindowNormalizer(BaseNormalizer):
    """滑动窗口标准化：每个股票取 N 天窗口，在窗口内标准化"""

    def __init__(self, window_size: int = 60):
        self.window_size = window_size

    @property
    def name(self) -> str:
        return "sliding_window"

    def normalize(self, df, feature_cols, training_stats=None):
        """
        对每只股票的每个时间点，取前后 window_size 天的窗口进行标准化
        训练时：使用全量历史数据计算窗口统计量
        预测时：使用训练时的统计量或滑动窗口统计量
        """
        if training_stats is None:
            # 训练时：计算全量历史统计量
            training_stats = {}
            for col in feature_cols:
                training_stats[col] = {
                    "mean": df[col].mean(),
                    "std": df[col].std(),
                    "min": df[col].min(),
                    "max": df[col].max(),
                }

        # 对每只股票分别标准化
        normalized_rows = []
        for ts_code, group in df.groupby("ts_code"):
            group = group.sort_values("trade_date").copy()
            for col in feature_cols:
                mean = training_stats[col]["mean"]
                std = training_stats[col]["std"]
                if std != 0:
                    group[f"{col}_normalized"] = (group[col] - mean) / std
                else:
                    group[f"{col}_normalized"] = 0
            normalized_rows.append(group)

        normalized_df = pd.concat(normalized_rows)
        return normalized_df[[f"{col}_normalized" for col in feature_cols]].values, training_stats

    def inverse_transform(self, data, feature_cols, stats):
        """根据统计量还原"""
        pass
```

#### 4.1.3 截面标准化器（Cross-sectional）

**适用模型**：XGBoost

**场景**：同一天，跨所有股票进行标准化（所有股票对齐当天）

```python
class CrossSectionalNormalizer(BaseNormalizer):
    """截面标准化：同一天，跨所有股票标准化"""

    @property
    def name(self) -> str:
        return "cross_sectional"

    def normalize(self, df, feature_cols, training_stats=None):
        """
        每个时间点，计算所有股票特征的 mean/std，
        然后对每个股票进行 z-score 标准化
        """
        if training_stats is None:
            # 按时间点分组计算统计量
            training_stats = {}
            for col in feature_cols:
                training_stats[col] = {
                    "mean": df.groupby("trade_date")[col].mean().to_dict(),
                    "std": df.groupby("trade_date")[col].std().to_dict(),
                }

        normalized = df.copy()
        for col in feature_cols:
            mean_dict = training_stats[col]["mean"]
            std_dict = training_stats[col]["std"]
            normalized[col] = df.apply(
                lambda row: (row[col] - mean_dict.get(row["trade_date"], 0)) / std_dict.get(row["trade_date"], 1)
                if std_dict.get(row["trade_date"], 1) != 0 else 0,
                axis=1
            )

        return normalized[feature_cols].values, training_stats

    def inverse_transform(self, data, feature_cols, stats):
        """根据统计量还原"""
        pass
```

#### 4.1.4 标准化器注册表

```python
class NormalizerRegistry:
    """标准化器注册表"""

    _normalizers: Dict[str, Type[BaseNormalizer]] = {}

    @classmethod
    def register(cls, normalizer: Type[BaseNormalizer]):
        cls._normalizers[normalizer().name] = normalizer

    @classmethod
    def get(cls, name: str) -> BaseNormalizer:
        if name not in cls._normalizers:
            raise ValueError(f"Unknown normalizer: {name}. Available: {list(cls._normalizers.keys())}")
        return cls._normalizers[name]()

    @classmethod
    def list_normalizers(cls) -> List[str]:
        return list(cls._normalizers.keys())
```

#### 4.1.5 模型配置扩展

```python
class ModelConfig(Document):
    # 现有字段...

    # 标准化配置
    normalizer: str = "cross_sectional"  # "sliding_window" | "cross_sectional"
    window_size: int = 60  # 滑动窗口大小（用于 LSTM）
    feature_cols: List[str] = []  # 输入特征列
    target_cols: List[str] = []   # 预测目标列
```

#### 4.1.6 不同模型的标准化配置

```python
# XGBoost：截面标准化（同一天，跨所有股票）
xgb_config = ModelConfig(
    model_type="xgboost",
    normalizer="cross_sectional",  # 同一天所有股票对齐
    feature_cols=["close", "volume", "ma5", "ma10", "rsi"],
    target_cols=["close"],
)

# LSTM：滑动窗口标准化（60天窗口内标准化）
lstm_config = ModelConfig(
    model_type="lstm",
    normalizer="sliding_window",
    window_size=60,  # 60天滑动窗口
    feature_cols=["close", "volume", "ma5", "ma10"],
    target_cols=["close"],
)
```

#### 4.1.7 流程中的标准化位置

```
1. 数据加载 ──→ 2. 指标计算 ──→ 3. 数据标准化 ──→ 4. 模型预测 ──→ 5. 反标准化
                                                        ↓
                                                   6. 信号生成
```

| 步骤 | 说明 |
|-----|------|
| 数据标准化 | 根据 model_config.normalizer 选择标准化方式 |
| 模型预测 | 使用标准化后的特征进行预测 |
| 反标准化 | 将预测结果还原为原始量纲 |

---

### 4.2 统一执行入口

```python
class ExecutionPipeline:
    """统一执行流程编排"""

    async def run(
        mode: Literal["backtest", "live"],
        account_config_id: ObjectId,
        strategy_id: ObjectId,
        training_id: ObjectId,
        # 回测模式参数
        ts_code: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        # 实盘模式参数
        ts_codes: Optional[List[str]] = None,
        date: Optional[str] = None,
    ) -> Union[ExecutionResult, List[OrderSuggestion]]:
        """
        统一执行入口
        - 回测模式：返回 ExecutionResult（包含 trades, portfolio_snapshots）
        - 实盘模式：返回 List[OrderSuggestion]
        """
        pass
```

### 4.3 数据加载器

```python
class DataLoader:
    """数据加载器，支持 backtest/live 模式"""

    async def load(
        ts_codes: List[str],
        start_date: str,
        end_date: str,
        mode: Literal["backtest", "live"] = "backtest",
    ) -> pd.DataFrame:
        """
        加载股票数据
        - backtest: 历史数据
        - live: 历史 + 当天数据
        """
        pass
```

### 4.4 预测器基类（支持自定义处理）

```python
class BasePredictor:
    """预测器基类，支持预处理/后处理钩子"""

    async def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        """自定义预处理钩子（可选实现）"""
        return df

    async def predict(
        self,
        features: np.ndarray,
        targets: List[str]
    ) -> Dict[str, float]:
        """预测（子类实现）"""
        raise NotImplementedError

    async def postprocess(self, predictions: Dict[str, float]) -> Dict[str, float]:
        """自定义后处理钩子（可选实现）"""
        return predictions
```

### 4.5 策略基类（增强）

```python
class BaseStrategy:
    """策略基类，增强信号强度支持"""

    async def generate_signals(
        self,
        df: pd.DataFrame,
        predictions: Dict[str, float]
    ) -> List[StockSignal]:
        """生成交易信号"""
        raise NotImplementedError

    async def calculate_strength(
        self,
        signal_data: dict
    ) -> float:
        """计算信号强度 [0, 1]（可选实现）"""
        return 0.5  # 默认中等强度
```

### 4.6 仓位管理器

```python
class PositionManager:
    """仓位管理器"""

    def __init__(
        self,
        account_config: AccountConfig,
        max_position_pct: float = 0.3,  # 单只最大仓位 30%
        min_order_value: float = 5000,   # 最小委托金额
    ):
        pass

    async def allocate(
        self,
        signals: List[StockSignal],
        current_portfolio: Dict[str, int],
        current_cash: float,
    ) -> List[OrderSuggestion]:
        """
        仓位分配
        1. 按信号强度排序
        2. 过滤低强度信号
        3. 分配权重
        4. 应用风险控制
        5. 生成委托单建议
        """
        pass
```

### 4.7 信号数据结构

```python
@dataclass
class StockSignal:
    ts_code: str                          # 股票代码
    action: Literal["buy", "sell", "hold"] # 操作方向
    signal_strength: float                # 信号强度 [0, 1]
    current_price: float                 # 当前价格
    prediction: Dict[str, float]         # 预测数据
    reason: str                           # 信号理由
```

### 4.8 委托单建议结构

```python
@dataclass
class OrderSuggestion:
    ts_code: str
    stock_name: str
    action: Literal["buy", "sell", "hold"]
    suggested_price: float
    suggested_shares: int
    signal_strength: float
    position_reason: str
    risk_notes: Optional[str] = None
    prediction_data: Optional[dict] = None
    status: str = "pending"
```

---

## 5. 子项目拆分

### 子项目 1：DAO 层重构
- 重命名 backtest_* → execution_*
- 新增 order_suggestions Document
- 新增索引（ts_code+date, mode+date 等）

### 子项目 2：数据管道重构
- 重构 data/service.py（支持 mode 参数）
- 新增 execution/data_loader.py
- 重构 indicators/service.py（工具函数化）

### 子项目 3：预测和信号层重构
- 重构 predict/base.py（新增 preprocess/normalize/postprocess）
- 新增 predict/normalizer.py（标准化器基类和实现）
- 新构 predict/service.py（支持批量预测、标准化）
- 重构 strategy/base.py（新增 calculate_strength）
- 新增 execution/predictor.py, execution/signal_generator.py

### 子项目 4：执行引擎核心
- 新增 execution/pipeline.py（统一流程编排）
- 新增 execution/position_manager.py
- 新增 execution/backtest_runner.py
- 新增 execution/live_suggestor.py
- 调整 account/account_manager.py

### 子项目 5：后台定时任务
- 新增 scheduler/live_trading.py
- 新增 scheduler/config.py

### 子项目 6：API 调整
- 调整 api/routers/backtest.py（调用新执行引擎）
- 可选：新增 api/routers/execution.py

### 子项目 7：文档同步
- 更新 docs/database-schema.md
- 更新 docs/system-design.md
- 更新 docs/api.md

---

## 6. 执行顺序

```
子项目 1 (DAO) → 子项目 2 (数据) → 子项目 3 (预测信号) → 子项目 4 (执行引擎)
     → 子项目 5 (定时任务) → 子项目 6 (API) → 子项目 7 (文档)
```

每个子项目完成后可独立运行测试，确保基础功能可用。

---

## 7. 向后兼容

- 现有 `/api/backtests` 接口保持兼容
- 内部调用新的 execution/pipeline.py
- 现有 backtest_* 代码可选废弃，但保持可回滚
