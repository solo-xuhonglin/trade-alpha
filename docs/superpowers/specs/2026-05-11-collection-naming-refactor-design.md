# 集合名称重命名设计

## 概述

将 MongoDB 集合名称统一为两个单词，并相应更新实体类和变量名。

## 命名规则

| 当前集合 | 新集合名 | 新类名 | 说明 |
|---------|---------|--------|------|
| portfolios | account_configs | AccountConfig | 账户配置 |
| strategies | strategy_configs | StrategyConfig | 策略配置 |
| predictions | prediction_results | PredictionResult | 预测结果 |
| trainings | training_results | TrainingResult | 训练结果 |
| signals | signal_results | SignalResult | 信号结果 |
| backtests | backtest_results | BacktestResult | 回测结果 |
| backtest_trades | backtest_trades | BacktestTrade | 回测交易（不变）|
| model_configs | model_configs | ModelConfig | 模型配置（已是两个单词，保持）|
| stock_daily | stock_daily | StockDaily | 股票日线（已是两个单词，保持）|
| stock_list | stock_list | StockList | 股票列表（已是两个单词，保持）|

## 设计原则

1. **一致性**：类名与集合名保持一致
2. **可读性**：两个单词命名更清晰
3. **兼容性**：回测交易和已有两个单词的保持不变

## 修改范围

### 1. DAO 层 (11 个文件)

#### 需要修改的文件：
- `dao/portfolio.py` → 类名 Portfolio → AccountConfig，集合名 portfolios → account_configs
- `dao/strategy.py` → 类名 Strategy → StrategyConfig，集合名 strategies → strategy_configs
- `dao/prediction.py` → 类名 Prediction → PredictionResult，集合名 predictions → prediction_results
- `dao/training.py` → 类名 Training → TrainingResult，集合名 trainings → training_results
- `dao/signal.py` → 类名 Signal → SignalResult，集合名 signals → signal_results
- `dao/backtest.py` → 类名 Backtest → BacktestResult，集合名 backtests → backtest_results

#### 不需要修改的文件：
- `dao/backtest_trade.py` - 保持不变
- `dao/model_config.py` - 保持不变
- `dao/stock_daily.py` - 保持不变
- `dao/stock_list.py` - 保持不变
- `dao/__init__.py` - 更新导入
- `dao/mongodb.py` - 保持不变

### 2. Service 层

需要更新的文件：
- `portfolio/service.py` - 更新导入和变量名
- `strategy/service.py` - 更新导入和变量名
- `predict/service.py` - 更新导入和变量名
- `predict/training_service.py` - 更新导入和变量名
- `backtest/service.py` - 更新导入和变量名

### 3. API 路由层

需要更新的文件：
- `api/routers/portfolio.py` - 更新导入
- `api/routers/predict.py` - 更新导入
- `api/routers/strategy.py` - 更新导入
- `api/routers/backtest.py` - 更新导入
- `api/main.py` - 更新导入（如有）

### 4. 测试层

需要更新的文件：
- `tests/trade_alpha/integration/*.py` - 所有集成测试
- `tests/trade_alpha/dao/*.py` - DAO 单元测试
- `tests/trade_alpha/portfolio/*.py` - Portfolio 单元测试
- `tests/trade_alpha/predict/*.py` - Predict 单元测试
- `tests/trade_alpha/strategy/*.py` - Strategy 单元测试
- `tests/trade_alpha/backtest/*.py` - Backtest 单元测试

### 5. 文档层

需要更新的文件：
- `docs/system-design.md` - 更新 DAO 模块说明
- `docs/database-schema.md` - 更新集合名称

## 执行顺序

1. **数据库清理**
   - 删除旧集合（portfolios, strategies, predictions, trainings, signals, backtests）

2. **DAO 层修改**
   - 重命名类
   - 更新集合名称
   - 更新索引名称
   - 更新 __init__.py 导出

3. **Service 层修改**
   - 更新导入语句
   - 更新变量名

4. **API 路由层修改**
   - 更新导入语句

5. **测试层修改**
   - 更新导入语句
   - 更新变量名和断言

6. **文档更新**
   - 更新 system-design.md
   - 更新 database-schema.md

7. **验证测试**
   - 运行集成测试
   - 运行 E2E 测试

## 数据迁移策略

采用**删除旧数据，重新生成**策略：
1. 运行清理脚本删除旧集合
2. 运行集成测试自动重新生成数据
3. 所有测试通过即迁移完成

## 风险评估

- **影响范围**：中（涉及 11 个实体类，多个服务）
- **回滚难度**：低（可通过 git 恢复）
- **数据风险**：低（测试数据可重新生成）
- **测试覆盖**：高（48 个集成测试 + 27 个 E2E 测试）

## 预期结果

- 所有集合名称统一为两个单词
- 类名与集合名保持一致
- 所有 48 个集成测试通过
- 所有 27 个 E2E 测试通过
- 文档更新完成
