# Task Service Design

## Overview

创建统一的 Task 服务类，封装所有异步任务的状态管理和查询操作。

## Core Design

**统一入口 + 自动初始化**，一个 `create_task()` 方法处理所有类型，根据 `TaskType` 自动设置初始状态。

## API Methods

### Task Creation
```python
async def create_task(task_type: TaskType, params: dict) -> Task
```
- 自动设置 status=PENDING, progress=0.0
- 记录 created_at 时间戳
- 返回创建好的 Task 对象

### Status Management
```python
async def start_task(task_id: PydanticObjectId) -> Task
async def complete_task(task_id: PydanticObjectId, result_id: str = None) -> Task
async def fail_task(task_id: PydanticObjectId, error_message: str) -> Task
```

### Progress Update
```python
async def update_progress(task_id: PydanticObjectId, progress: float, message: str) -> None
```
- 原子更新 progress 和 progress_message 字段
- 无返回值

### Query Operations
```python
async def get_task(task_id: PydanticObjectId) -> Optional[Task]
async def list_tasks(
    task_type: TaskType = None,
    status: TaskStatus = None,
    page: int = 1,
    page_size: int = 20
) -> dict
```

## Usage Examples

### Training Task
```python
task = await task_service.create_task(TaskType.TRAINING, {
    "config_id": "xxx", "name": "训练1", "ts_codes": [...], ...
})

# Execute training with task_id
await training.create_training(..., task_id=task.id)
```

### Backtest Task
```python
task = await task_service.create_task(TaskType.BACKTEST, {
    "account_config_id": "xxx", "training_id": "yyy", ...
})

# Execute backtest with task_id
await pipeline.run_backtest(..., task_id=task.id)
```

## File Structure

```
backend/src/trade_alpha/services/
  └── task_service.py
```

## Migration

- 将 backtest.py, trainings.py, data_analysis.py 中的 Task 操作迁移到 TaskService
- API 路由调用 TaskService 方法
- 移除各路由中的重复 Task 查询逻辑
