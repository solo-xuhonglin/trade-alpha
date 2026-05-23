# 子进程任务执行设计

## 概述

将训练和回测任务从 FastAPI BackgroundTasks 迁移到独立子进程执行，避免阻塞 API 服务。

## 问题背景

当前训练和回测使用 FastAPI 的 `BackgroundTasks` 在主进程内异步执行，会阻塞 API 服务线程。需要迁移到独立子进程，实现真正的异步执行。

## 设计目标

1. **进程隔离**：训练/回测在独立子进程执行，不阻塞 API
2. **统一入口**：`python -m trade_alpha.task.run_task --task-id xxx --task-type xxx`
3. **状态同步**：子进程直接连接 MongoDB 更新进度
4. **停止支持**：软停止（更新状态） + 强制停止（kill 进程）
5. **重启恢复**：服务重启时检测孤儿进程并清理

## 目录结构

```
backend/src/trade_alpha/task/
├── __init__.py
├── dao.py              # Task Document 定义（含 TaskStatus, TaskType）
├── service.py           # TaskService 状态管理
├── runner.py            # 子进程执行器基类
├── training_runner.py   # 训练子进程执行
├── backtest_runner.py   # 回测子进程执行
└── run_task.py          # 统一入口脚本
```

## 数据模型

### TaskStatus 枚举

```python
class TaskStatus(str, Enum):
    PENDING = "pending"      # 等待执行
    RUNNING = "running"      # 正在执行
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 异常失败
    CANCELLED = "cancelled"  # 用户取消
```

### Task Document

```python
class Task(Document):
    type: TaskType
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    progress_message: Optional[str] = None
    result_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = datetime.now()
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    params: Dict[str, Any] = {}
    pid: Optional[int] = None  # 子进程 PID

    class Settings:
        name = "tasks"
```

## 执行流程

### 1. 启动任务

```
API                          子进程
 │                            │
 │  TaskService.create_task() │
 │ ──────────────────────────► │
 │      (PENDING)              │
 │                            │
 │  subprocess.Popen()         │
 │ ─── spawn ─────────────────► │
 │                            │
 │  update(RUNNING, pid)      │
 │ ──────────────────────────► │
 │                            │
 │                      检查状态 == RUNNING?
 │                      是 → 继续执行
 │                      否 → 退出
```

### 2. 子进程执行

```python
# run_task.py
async def main():
    task_id = args.task_id
    await init_db()
    
    task = await TaskService.get_task(PydanticObjectId(task_id))
    if not task or task.status != TaskStatus.RUNNING:
        return  # 已停止，直接退出
    
    try:
        if args.task_type == "training":
            await TrainingRunner.run(task_id)
        elif args.task_type == "backtest":
            await BacktestRunner.run(task_id)
    except Exception as e:
        await TaskService.fail_task(task_id, str(e))
```

### 3. 停止任务

**软停止（force=False）**：
```python
# 子进程定期检查
if task.status != TaskStatus.RUNNING:
    return  # 退出执行

# API 调用
task.status = TaskStatus.CANCELLED
task.completed_at = datetime.now()
await task.save()
```

**强制停止（force=True）**：
```python
import os
os.kill(task.pid, signal.SIGTERM)
```

### 4. 重启恢复

```python
# main.py 或 lifespan
async def startup():
    await init_db()
    await recover_orphaned_tasks()

async def recover_orphaned_tasks():
    running_tasks = await Task.find(Task.status == TaskStatus.RUNNING).to_list()
    for task in running_tasks:
        if task.pid and not process_exists(task.pid):
            task.status = TaskStatus.FAILED
            task.error_message = "Process died during restart"
            await task.save()
            logger.warning(f"Orphaned task {task.id} marked as FAILED")
```

## API 改动

### trainings.py

```python
@router.post("")
async def trigger_training(body: TrainingRequest):
    task = await TaskService.create_task(TaskType.TRAINING, params)
    
    proc = subprocess.Popen([
        sys.executable, "-m", "trade_alpha.task.run_task",
        "--task-id", str(task.id),
        "--task-type", "training",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    
    await TaskService.start_task(task.id, proc.pid)
    
    return {"task_id": str(task.id), "status": "running"}

@router.post("/task/{task_id}/stop")
async def stop_training_task(task_id: str, force: bool = False):
    await TaskService.stop_task(task_id, force)
    return {"message": "Task stopped"}
```

### backtest.py

同上结构

## 核心逻辑不变

- `trainer.py` 的 `create_training()` 不修改
- `pipeline.py` 的 `run_backtest()` 不修改
- 仅包装一层子进程入口

## 进度更新

子进程通过 `TaskService.update_progress()` 直接更新 MongoDB：

```python
await TaskService.update_progress(task.id, 50, "正在训练模型...")
```

## 文件清单

| 文件 | 操作 | 说明 |
|-----|------|-----|
| `services/task_service.py` | 删除 | 迁移到 task 模块 |
| `dao/task.py` | 重命名 | 迁移到 task/dao.py |
| `task/__init__.py` | 新增 | 模块导出 |
| `task/dao.py` | 新增 | Task Document 定义 |
| `task/service.py` | 新增 | TaskService 状态管理 |
| `task/runner.py` | 新增 | 执行器基类 |
| `task/training_runner.py` | 新增 | 训练执行器 |
| `task/backtest_runner.py` | 新增 | 回测执行器 |
| `task/run_task.py` | 新增 | 统一入口 |
| `api/routers/trainings.py` | 修改 | 改用 subprocess |
| `api/routers/backtest.py` | 修改 | 改用 subprocess |
| `api/routers/data_analysis.py` | 修改 | 改用 subprocess |
| `main.py` | 修改 | 新增重启恢复逻辑 |

## 迁移步骤

1. 创建 `task/` 目录和基础文件
2. 实现 `TaskService.stop_task()` 和 `TaskService.start_task()`
3. 实现子进程执行器基类和具体实现
4. 修改 API 路由使用 subprocess
5. 实现重启恢复逻辑
6. 更新文档
7. 测试验证
