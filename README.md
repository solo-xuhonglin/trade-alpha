# trade-alpha

股票预测程序

## 功能

- [x] 数据层：Tushare 数据获取，MongoDB 存储
- [ ] 分析层：技术指标计算
- [ ] 预测层：价格预测
- [ ] 回测层：策略回测

## 环境配置

```bash
cp .env.example .env
# 编辑 .env 填入 TUSHARE_TOKEN
```

## 安装

```bash
pip install -e .
```

## 使用示例

```python
from data import fetch_and_store

# 获取并存储股票数据
count = fetch_and_store("000001.SZ", "20240101", "20241231")
print(f"Stored {count} records")
```

## 开发

```bash
# 运行测试
pytest tests/ -v
```
