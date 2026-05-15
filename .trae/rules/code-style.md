# 代码风格规则

## 命名约定

| 元素 | 风格 | 示例 |
|------|------|------|
| 类名 | PascalCase | `ExecutionPipeline`, `StockDaily` |
| 函数/方法 | snake_case | `fetch_and_store()`, `_calc_max_drawdown()` |
| 模块级常量 | UPPER_SNAKE_CASE | `DEFAULT_INDICATOR_FIELDS` |
| 私有方法 | `_` 前缀 | `_next_date()`, `_calc_win_rate()` |
| 文件名 | snake_case | `stock_daily.py`, `config_service.py` |

## 导入规范

三段式导入，每组间空行分隔：

```python
# 标准库
from datetime import datetime
from typing import Optional, List

# 第三方库
import pandas as pd
from beanie import Document, PydanticObjectId

# 本地库（绝对导入）
from trade_alpha.dao import StockDaily
from trade_alpha.logging import get_logger
```

DAO 模块通过 `__init__.py` 批量重导出，外部使用 `from trade_alpha.dao import Xxx`。

## 类型注解

- 所有函数签名必须包含类型注解
- 使用 `Optional[X]` 和 `List[X]` 风格（统一，不混用 `list[int] | None`）
- 返回值类型不可省略，无返回用 `-> None`
- Pydantic 可变类型字段用 `default_factory=list`，不可变用直接默认值

## 错误处理

- DAO 层不捕获，向上抛出
- 服务层用 `raise ValueError("描述信息")` 处理业务错误
- API 层转为 `HTTPException`（400/404/500）
- 后台任务捕获异常后更新状态为 FAILED + 记录 error_message
- **禁止使用 `assert` 做参数校验**

## 日志

- 所有日志消息必须使用英文
- 每个模块顶层创建 logger：

```python
logger = get_logger("模块名")
```

级别使用：`info`(流程节点) / `warning`(可恢复) / `debug`(细节) / `error`(不可恢复)。

## 异步约定

- DAO / 服务 / API 层统一使用 `async/await`
- pandas 计算和 tushare 调用可在异步函数中同步执行
- 纯计算函数可保持同步

## Docstring

- 简单函数：单行双引号 docstring
- 复杂函数：Google 风格（Args / Returns）
- 模块级：双引号一行说明

## Git 提交

- 所有 commit message 必须使用英文
- 遵循 Conventional Commits 规范：`<type>: <description>`
