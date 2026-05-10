# 模型模块拆分设计文档

## 概述

将模型模块拆分为模型配置和模型训练两部分，支持一个配置多次训练，回测依赖训练结果。

## 数据模型

### model_configs 集合（模型配置）

定义模型的类型和参数，不包含训练数据。

```python
{
    "_id": ObjectId,
    "name": "my_xgboost",           # 配置名称（唯一）
    "model_type": "xgboost",        # 模型类型: linear/xgboost/lstm
    "params": {                     # 模型参数
        "n_estimators": 100,
        "max_depth": 6,
        "learning_rate": 0.1
    },
    "targets": ["open", "close", "high", "low"],  # 预测目标列（可多个）
    "created_at": datetime,
    "updated_at": datetime
}
```

### trainings 集合（训练结果）

记录每次训练的详细信息，关联模型配置。

```python
{
    "_id": ObjectId,
    "config_id": ObjectId,          # 关联 model_configs
    "name": "训练_20240101",        # 训练名称
    "ts_codes": ["002594.SZ", "601398.SH"],  # 训练股票列表
    "start_date": "20230101",       # 训练数据起始日期
    "end_date": "20231231",         # 训练数据结束日期
    "feature_cols": ["open", "high", "low", "close", "vol", ...],
    "metrics": {
        "mse": 0.05,
        "mae": 0.18,
        "sample_count": 500         # 训练样本总数
    },
    "model_path": "models/{config_id}/{training_id}.pkl",  # 按配置ID组织
    "created_at": datetime
}
```

### 文件存储结构

```
models/
├── {config_id_1}/
│   ├── {training_id_1}.pkl
│   ├── {training_id_2}.pkl
│   └── ...
├── {config_id_2}/
│   ├── {training_id_3}.pkl
│   └── ...
```

## 训练策略

### 样本混合

当选择多个股票训练时，采用样本混合策略：
- 所有股票数据混合作为训练样本
- 每条记录独立，不区分股票来源
- 可选添加 `ts_code` 作为分类特征
- 模型学习价格变动的通用规律

### 多目标预测

支持同时预测多个目标：
- `targets: ["open", "close", "high", "low"]`
- 模型输出多个预测值
- 评估指标按目标分别计算

### 训练流程

```
1. 获取所有指定股票的日线数据
2. 按日期范围过滤
3. 混合所有股票数据
4. 构建特征和目标（多目标）
5. 训练模型
6. 计算评估指标（每个目标）
7. 保存模型文件到 models/{config_id}/{training_id}.pkl
8. 记录训练结果
```

## API 设计

### 模型配置 API

| 方法 | 端点 | 说明 |
|-----|------|------|
| POST | /model-configs | 创建模型配置 |
| GET | /model-configs | 列出所有配置 |
| GET | /model-configs/{id} | 获取配置详情 |
| PUT | /model-configs/{id} | 更新配置 |
| DELETE | /model-configs/{id} | 删除配置（级联删除训练结果和模型文件） |

### 训练 API

| 方法 | 端点 | 说明 |
|-----|------|------|
| POST | /trainings | 执行训练 |
| GET | /trainings | 列出训练结果（可按 config_id 过滤） |
| GET | /trainings/{id} | 获取训练详情 |
| DELETE | /trainings/{id} | 删除训练结果和模型文件 |
| POST | /trainings/{id}/predict | 使用训练结果预测 |

### 请求示例

**创建模型配置**
```json
POST /model-configs
{
    "name": "my_xgboost",
    "model_type": "xgboost",
    "params": {
        "n_estimators": 100,
        "max_depth": 6
    },
    "targets": ["open", "close", "high", "low"]
}
```

**执行训练**
```json
POST /trainings
{
    "config_id": "xxx",
    "name": "训练_20240101",
    "ts_codes": ["002594.SZ", "601398.SH"],
    "start_date": "20230101",
    "end_date": "20231231"
}
```

**预测**
```json
POST /trainings/{id}/predict
{
    "ts_code": "002594.SZ"  # 可选，默认使用训练时的第一个股票
}
```

**响应示例**
```json
{
    "predictions": {
        "open": 45.2,
        "close": 46.1,
        "high": 47.0,
        "low": 44.8
    }
}
```

## 回测关联

回测模块需要修改，使用 `training_id` 替代 `model_id`：

```python
# 回测请求
{
    "training_id": "xxx",  # 使用某次训练结果
    ...
}
```

## 集成测试设计

### 测试层级

| 层级 | Order | 文件 | 类名 | 说明 |
|-------|------|------|------|------|
| Layer 4 | 41 | test_41_portfolio_service.py | TestPortfolioService | 验证账户管理服务 |
| Layer 4 | 42 | test_42_strategy_service.py | TestStrategyService | 验证策略管理服务 |
| Layer 4 | 43 | test_43_model_config_service.py | TestModelConfigService | 验证模型配置服务 |
| Layer 5 | 51 | test_51_training_service.py | TestTrainingService | 验证训练服务 |
| Layer 6 | 60 | test_60_backtest.py | TestBacktest | 验证回测服务 |

### 测试内容

**TestModelConfigService (Layer 4)**
- test_create_config：创建配置
- test_get_config：获取配置
- test_list_configs：列出配置
- test_update_config：更新配置
- test_delete_config：删除配置（验证级联删除训练结果）
- test_ensure_default_config：确保默认配置存在

**TestTrainingService (Layer 5)**
- test_create_training：创建训练（单股票）
- test_create_training_multi_stocks：创建训练（多股票）
- test_list_trainings：列出训练结果
- test_list_trainings_by_config：按配置过滤训练结果
- test_delete_training：删除训练
- test_predict：使用训练结果预测
- test_ensure_default_training：确保默认训练存在

### 默认记录

| 默认记录 | 用途 | 创建位置 |
|---------|------|---------|
| test_model_config | 默认模型配置 | TestModelConfigService |
| test_training | 默认训练结果 | TestTrainingService |

### 数据清理

- 测试数据使用 `test_*_temp` 命名
- 测试结束后自动清理
- 保留默认记录供后续测试使用

## 文件结构

```
backend/src/trade_alpha/predict/
├── __init__.py
├── base.py              # BasePredictor 抽象类
├── linear.py            # LinearPredictor
├── xgboost.py           # XGBoostPredictor
├── lstm.py              # LSTMPredictor
├── config_service.py    # 模型配置服务
├── training_service.py  # 训练服务
└── service.py           # 统一入口（可选）
```

## 迁移计划

1. 创建新的集合和服务
2. 迁移现有 models 数据到 model_configs 和 trainings
3. 更新 API 路由
4. 更新回测模块
5. 更新集成测试
