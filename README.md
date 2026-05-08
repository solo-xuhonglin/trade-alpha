# trade-alpha

股票预测程序

## 功能

- [x] 数据层：Tushare 数据获取，MongoDB 存储
- [ ] 分析层：技术指标计算
- [ ] 预测层：价格预测
- [ ] 回测层：策略回测

## 项目结构

```
trade-alpha/
├── src/
│   └── trade_alpha/           # 源码
│       ├── __init__.py
│       ├── config.py
│       └── data/
│           ├── __init__.py
│           ├── fetcher.py
│           └── storage.py
├── tests/
│   └── trade_alpha/           # 测试（与源码层级对应）
│       └── data/
│           ├── test_fetcher.py
│           ├── test_storage.py
│           └── test_data_integration.py
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
from trade_alpha.data import fetch_and_store

# 获取并存储股票数据
count = fetch_and_store("000001.SZ", "20240101", "20241231")
print(f"Stored {count} records")
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
