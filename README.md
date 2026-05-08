# trade-alpha

股票预测程序

## 功能

- [x] 数据层：Tushare 数据获取，MongoDB 存储
- [x] 分析层：技术指标计算（MA、MACD）
- [ ] 预测层：价格预测
- [ ] 回测层：策略回测

## 项目结构

```
trade-alpha/
├── src/
│   └── trade_alpha/
│       ├── db/                # 数据库模块
│       ├── data/              # 数据获取模块
│       └── indicators/        # 技术指标模块
├── tests/
│   └── trade_alpha/
│       ├── db/
│       ├── data/
│       └── indicators/
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
