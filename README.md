# trade-alpha

股票预测程序

## 功能

- [x] 数据层：Tushare 数据获取，MongoDB 存储
- [x] 分析层：技术指标计算（MA、MACD）
- [x] 预测层：价格预测（线性回归）
- [x] 策略层：交易信号生成
- [x] 账户层：资金管理、交易记录
- [x] 回测层：策略回测、指标计算

## 项目结构

```
trade-alpha/
├── src/
│   └── trade_alpha/
│       ├── dao/               # 数据访问层 (MongoDB)
│       ├── data/              # 数据获取模块
│       ├── indicators/        # 技术指标模块
│       ├── predict/           # 预测模块
│       ├── strategy/          # 交易策略模块
│       ├── portfolio/        # 账户管理模块
│       └── backtest/         # 回测模块
├── tests/
│   └── trade_alpha/
│       ├── dao/
│       ├── data/
│       ├── indicators/
│       ├── predict/
│       ├── strategy/
│       ├── portfolio/
│       └── backtest/
├── pyproject.toml
└── .env.example
```

## 环境配置

```bash
cp .env.example .env
# 编辑 .env 填入 TUSHARE_TOKEN
```

## 安装

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e . pytest
```

## 使用示例

```python
# 获取并存储股票数据
from trade_alpha.data import fetch_and_store
fetch_and_store("000001.SZ", "20240101", "20241231")

# 计算并存储均线
from trade_alpha.indicators import calculate_and_store_ma
calculate_and_store_ma("000001.SZ", periods=[5, 10, 20, 60])

# 计算并存储 MACD
from trade_alpha.indicators import calculate_and_store_macd
calculate_and_store_macd("000001.SZ")

# 预测价格
from trade_alpha.predict import predict
predict("000001.SZ", targets=["open", "close", "high", "low"])

# 生成交易信号
from trade_alpha.strategy import generate_signal
signal = generate_signal("000001.SZ", strategy="price")
print(f"Action: {signal['action']}, Current: {signal['current_price']}")

# 运行回测
from trade_alpha.backtest import run_backtest
result = run_backtest("000001.SZ", "20240101", "20241231", strategy="price")
print(f"总收益率: {result.total_return:.2%}, 最大回撤: {result.max_drawdown:.2%}")
```

## 开发

```bash
# 运行所有测试
pytest tests/ -v

# 运行单元测试
pytest tests/ -v -m "not integration"

# 运行集成测试
pytest tests/ -v -m integration
```
