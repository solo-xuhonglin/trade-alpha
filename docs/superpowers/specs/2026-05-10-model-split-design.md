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
    "targets": ["close"],           # 预测目标列
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
    "model_path": "models/xgboost/xxx.pkl",
    "created_at": datetime
}
```

## 训练策略

### 样本混合

当选择多个股票训练时，采用样本混合策略：
- 所有股票数据混合作为训练样本
- 每条记录独立，不区分股票来源
- 可选添加 `ts_code` 作为分类特征
- 模型学习价格变动的通用规律

### 训练流程

```
1. 获取所有指定股票的日线数据
2. 按日期范围过滤
3. 混合所有股票数据
4. 构建特征和目标
5. 训练模型
6. 计算评估指标
7. 保存模型文件
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
| DELETE | /model-configs/{id} | 删除配置（级联删除训练结果） |

### 训练 API

| 方法 | 端点 | 说明 |
|-----|------|------|
| POST | /trainings | 执行训练 |
| GET | /trainings | 列出训练结果 |
| GET | /trainings/{id} | 获取训练详情 |
| DELETE | /trainings/{id} | 删除训练结果 |
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
    "targets": ["close"]
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

## 回测关联

回测模块需要修改，使用 `training_id` 替代 `model_id`：

```python
# 回测请求
{
    "training_id": "xxx",  # 使用某次训练结果
    ...
}
```

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
