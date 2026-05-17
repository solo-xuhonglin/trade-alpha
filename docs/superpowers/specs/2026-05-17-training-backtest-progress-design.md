# 训练和回测进度优化设计方案

> **Date**: 2026-05-17
> **Status**: Draft

## 1. 概述

优化训练和回测的进度显示，实现细粒度的阶段性进度更新。

### 目标
- 训练：按年加载数据、按年计算标签、逐年逐月标准化和训练，进度显示具体阶段
- 回测：按月更新进度，显示当前处理到哪一年哪一月

## 2. 训练流程

### 新流程
```
1. 确定年份范围 (start_date 到 end_date)
2. 逐年处理:
   a. 加载当年数据（包括未来N天用于计算Y标签）
   b. 计算当年Y标签
   c. 逐年逐月标准化
   d. 逐年逐月训练（使用累积数据训练一个模型）
3. 保存模型
```

### 进度格式
```
正在加载2015年数据 (1/10)
正在计算2015年标签 (1/10)
正在标准化2015年1月 (1/10)
正在训练2015年1月 (1/10)
正在标准化2015年2月 (1/10)
正在训练2015年2月 (1/10)
...
正在加载2016年数据 (2/10)
正在计算2016年标签 (2/10)
正在标准化2016年1月 (2/10)
正在训练2016年1月 (2/10)
...
训练完成
```

## 3. 回测流程

### 进度格式
```
正在回测2025年1月 (1/12)
正在回测2025年2月 (2/12)
...
回测完成
```

## 4. 技术设计

### 4.1 数据模型改动

#### Task Document 新增字段
```python
class Task(Document):
    # ... existing fields ...
    progress_message: Optional[str] = None  # 新增：详细进度信息
```

### 4.2 后端改动

#### training_service.py 重构
- 新增 `create_training_batch` 函数
- 按年分组数据
- 逐年计算Y标签
- 逐年逐月标准化
- 逐年逐月训练（累积数据）
- 每个阶段更新 Task.progress 和 Task.progress_message

#### pipeline.py 改动
- 计算总月份数
- 按月循环处理
- 每月更新 Task.progress 和 Task.progress_message

#### API Response 改动
```python
{
    "task_id": "xxx",
    "status": "running",
    "progress": 45.5,  # 0-100 百分比
    "progress_message": "正在标准化2015年1月 (1/10)",
    "error_message": null,
    ...
}
```

### 4.3 前端改动

#### TrainingManageView.vue
- 进度列显示 progress_message 文本
- 移除简单的 v-progress-linear，改为文字显示

#### BacktestManageView.vue
- 进度列显示 progress_message 文本
- 移除简单的 v-progress-linear，改为文字显示

### 4.4 进度计算

#### 训练进度计算
```
总阶段数 = 年数 * (1 + 1 + 月数)  # 加载 + 计算标签 + (标准化+训练)*月数
当前阶段 = 已完成年 * 月数 * 2 + 当前年内阶段
进度 = (当前阶段 / 总阶段数) * 100
```

#### 回测进度计算
```
总月数 = 月份差 + 1
当前月 = (当前年 - 开始年) * 12 + 当前月 - 开始月 + 1
进度 = (当前月 / 总月数) * 100
```

## 5. 实现计划

### Phase 1: 后端改动
1. Task 模型添加 progress_message 字段
2. 重构 training_service.py 实现分年分月处理
3. 修改 pipeline.py 实现按月进度更新
4. 更新 API 响应包含 progress_message

### Phase 2: 前端改动
1. 更新 TrainingTaskStatus 接口
2. 更新 BacktestTaskStatus 接口
3. 修改 TrainingManageView.vue 显示进度信息
4. 修改 BacktestManageView.vue 显示进度信息

## 6. 注意事项

- 训练使用累积数据训练一个模型，不是每年一个模型
- 标准化是逐年逐月标准化（截面标准化）
- 进度更新频率：每处理一个月更新一次
- progress 字段仍保留用于兼容，progress_message 显示详细文字信息
