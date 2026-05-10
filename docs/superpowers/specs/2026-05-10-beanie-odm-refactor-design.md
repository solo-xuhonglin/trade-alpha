# Beanie ODM 重构设计文档

## 背景

当前项目使用自定义 DAO 层操作 MongoDB，存在以下问题：
- 多层转换：doc → obj → response，代码繁琐
- 每个模块都有相似的 DAO、Service、转换函数
- 类型不统一：Dict vs 实体类 vs Pydantic Model

## 目标

使用 Beanie ODM 简化数据层：
- Beanie Document = Pydantic Model，可直接用于 FastAPI 响应
- 内置 CRUD 方法，无需 DAO 层
- 统一异步架构

## 文件结构

```
src/trade_alpha/
├── dao/                       # Beanie Document 模型
│   ├── __init__.py
│   ├── mongodb.py            # 数据库初始化
│   ├── portfolio.py          # Portfolio Document
│   ├── strategy.py           # Strategy Document
│   ├── model_config.py       # ModelConfig Document
│   ├── training.py           # Training Document
│   ├── backtest.py           # Backtest Document
│   ├── backtest_trade.py     # BacktestTrade Document
│   ├── prediction.py         # Prediction Document
│   ├── signal.py             # Signal Document
│   ├── stock_daily.py        # StockDaily Document
│   └── stock_list.py         # StockList Document
├── portfolio/
│   └── service.py            # Portfolio 业务逻辑
├── strategy/
│   └── service.py
├── predict/
│   ├── config_service.py
│   └── training_service.py
├── backtest/
│   ├── engine.py
│   ├── metrics.py
│   └── service.py
└── api/routers/              # 异步路由
```

## 删除的文件

- `dao/portfolio_dao.py` 等旧 DAO 文件
- `portfolio/portfolio.py` 等实体类文件
- `predict/model_config.py`, `predict/training.py` 等实体类
- `api/schemas.py` 中的 Response 模型

## 实现步骤

1. 安装 beanie 依赖 ✅
2. 创建 Beanie Document 模型
3. 重构 mongodb.py 为异步初始化
4. 重构 Service 层为异步
5. 重构 API 路由为异步
6. 删除旧文件
7. 运行测试验证

## 示例代码

### Document 模型
```python
from beanie import Document
from pydantic import Field

class Portfolio(Document):
    name: str
    initial_capital: float
    buy_fee_rate: float = Field(default=0.0003)
    
    class Settings:
        collection = "portfolios"
```

### Service 层
```python
async def get_portfolio_by_id(portfolio_id: PydanticObjectId) -> Portfolio:
    return await Portfolio.get(portfolio_id)

async def list_portfolios() -> list[Portfolio]:
    return await Portfolio.find_all().to_list()
```

### API 路由
```python
@router.get("/{portfolio_id}", response_model=Portfolio)
async def get_portfolio(portfolio_id: PydanticObjectId):
    return await get_portfolio_by_id(portfolio_id)
```
