# Trade-Alpha 项目规则

## 项目概述
- **项目名称**：trade-alpha
- **项目类型**：股票数据分析与交易系统
- **Python 版本**：3.14+
- **许可证**：Apache License 2.0

## 核心原则

### 1. 设计文档优先
- 先设计后实现
- 根据任务复杂度自行判断设计深度
- 对于复杂功能，在 `docs/superpowers/` 创建临时设计文档
- **`docs/superpowers/` 为临时目录，会定期删除，不需要提交维护**
- **`docs/` 根目录下的文档需定期同步更新**

### 2. 代码可维护性
- 代码应易于理解、修改和扩展
- 关注模块化、命名清晰、结构合理

### 3. 测试覆盖
- 确保代码可验证
- 根据功能重要性自行判断测试深度
- 单元测试放在 `backend/tests/trade_alpha/unit/`
- 集成测试放在 `backend/tests/trade_alpha/integration/`

### 4. 文档同步
- 代码变更时，文档必须同步更新

### 5. 代码风格
- 遵循统一的命名、导入、类型注解规则

### 6. 安全性
- 敏感信息不外泄
- 注意依赖和配置的安全风险

## 开发流程
设计 → 实现 → 审查 → 测试 → 修复 → 再次审查 → 提交

## 项目结构

完整项目结构说明详见 [系统设计文档](./docs/system-design.md)。

```
trade-alpha/
├── backend/                          # 后端项目
├── frontend/                         # 前端项目
└── docs/                             # 文档
```

## 代码风格规则

### 命名约定
- 类名：PascalCase
- 函数/方法：snake_case
- 模块级常量：UPPER_SNAKE_CASE
- 私有方法：`_` 前缀
- 文件名：snake_case
- **变量命名禁止简写**，强调可读性。`n_pct`、`d` 这类简写不可接受
- 代码简洁指逻辑结构简明清晰，不是命名简短。命名应自解释、易读易维护

### 导入规范
- 三段式导入，每组间空行分隔（标准库 → 第三方库 → 本地库）
- **优先全局导入，禁止局部导入**（例外：`if __name__ == "__main__"`、循环引用、可选依赖，需注释原因）
- DAO 模块通过 `__init__.py` 批量重导出

### 类型注解
- 所有函数签名必须包含类型注解
- 使用 `Optional[X]` 和 `List[X]` 风格（统一，不混用 `list[int] | None`）
- 返回值类型不可省略，无返回用 `-> None`
- Pydantic 可变类型字段用 `default_factory=list`，不可变用直接默认值

### 错误处理
- DAO 层不捕获，向上抛出
- 服务层用 `raise ValueError("描述信息")` 处理业务错误
- API 层转为 `HTTPException`（400/404/500）
- 后台任务捕获异常后更新状态为 FAILED + 记录 error_message
- **禁止使用 `assert` 做参数校验**
- **配置字段不使用 `getattr` 兜底**，直接访问字段。配置一定有值，兜底会导致配置不生效时无法被发现

### 条件判断
- **判空必须有依据**，禁止随意判空
- 添加 `if xxx:` / `if xxx is None` 守卫前必须确认该变量确实可能为空/假值
- 如果调用链保证变量始终有值，不应添加冗余判空
- 冗余守卫会掩盖业务逻辑、增加嵌套深度、降低可读性

### 日志
- 所有日志消息必须使用英文
- **用户界面展示的进度消息（如 TaskService.update_progress）使用中文**
- **代码注释使用英文**
- 每个模块顶层创建 logger：`logger = get_logger("模块名")`
- 级别使用：`info`(流程节点) / `warning`(可恢复) / `debug`(细节) / `error`(不可恢复)

### 异步约定
- DAO / 服务 / API 层统一使用 `async/await`
- pandas 计算和 tushare 调用可在异步函数中同步执行
- 纯计算函数可保持同步

### Docstring
- 简单函数：单行双引号 docstring
- 复杂函数：Google 风格（Args / Returns）
- 模块级：双引号一行说明
- **代码注释不放历史注解**（如"取代 sell_rank_n"、"新增"等），变动历史由 git 管理

### Git 提交
- 所有 commit message 必须使用英文
- 遵循 Conventional Commits 规范：`<type>: <description>`

## 文档同步规则

### 同步时机

| 代码变更 | 需更新的文档 |
|---------|-------------|
| 新增/删除模块 | `docs/system-design.md` 模块说明 + `README.md` |
| 新增/删除公共方法/类 | `docs/system-design.md` 接口设计 |
| 数据库字段变更 | `docs/database-schema.md` + `README.md` |
| 新增/修改 API 接口 | `docs/api.md` |
| 前端页面/组件变更 | `docs/frontend.md` |
| 配置文件变更 | `docs/system-design.md` 配置说明 |
| 新增技术指标 | `docs/features-indicators.md` |
| 数据处理流程变更 | `docs/data-processing.md` |

### 提交规范
修改代码时，在同一 commit 中更新文档：
- ✅ `feat: add RSI indicator and update docs`
- ❌ `feat: add RSI indicator` (忘记更新文档)

### 文档质量
- 文档应描述 **已实现** 的功能，而非计划实现
- 使用代码示例时，确保示例与实际接口一致
- 删除功能时，同步删除文档中相关内容

## 测试规则

完整测试规则详见 [后端集成测试文档](./docs/backend-integration-testing.md) 和 [前端 E2E 测试文档](./docs/frontend-e2e-testing.md)。

## 相关文档链接

- [系统设计文档](./docs/system-design.md) - 整体架构、模块说明、项目结构
- [数据库表结构](./docs/database-schema.md) - 数据模型、索引、字段定义
- [API 接口文档](./docs/api.md) - RESTful 接口说明
- [前端设计文档](./docs/frontend.md) - 前端架构、页面设计
- [股票字段与技术指标](./docs/features-indicators.md) - 字段定义、指标计算方法
- [后端脚本说明](./docs/scripts.md) - 脚本工具使用指南

## 全量测试指南

### 执行顺序

```
1. 运行后端集成测试（创建测试数据）
2. 重启后端服务（让 REST API 载入最新数据）
3. 运行前端 E2E 测试
```

### 步骤 1：运行后端集成测试

```powershell
cd backend
.venv\Scripts\pytest tests\trade_alpha\integration\ -v
```

集成测试按文件名数字排序执行（test_01 → test_10 → test_20 → ... → test_99）。

### 步骤 2：重启后端

```powershell
cd d:\projects\trade-alpha
.\service.bat restart
```

等待后端就绪后验证：

```powershell
cd backend
python scripts/check_server.py
```

Expected: `✓ Server is running at http://localhost:8000`

### 步骤 3：运行前端 E2E 测试

前置条件：后端 8000 + 前端 3000 均运行中。

```powershell
cd frontend\e2e
pytest -v --base-url=http://localhost:3000
```

### 依赖准备

#### 后端

已在 `backend\.venv\` 中安装，无需额外操作。如需重装：

```powershell
cd backend
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install pytest pytest-asyncio
```

#### 前端 E2E

Python 3.14+ 全局安装，playwright 和依赖已全局安装，无需重复安装。

如需首次安装：

```bash
pip install playwright pytest-playwright
playwright install chromium
```

### 测试数据说明

- 后端集成测试自行管理测试数据，`test_*_temp` 命名自动清理
- 比亚迪 `002594.SZ` 的数据由生命周期测试维护
- 前端 E2E 测试仅读取不写入，依赖后端集成测试创建的数据
- 定时任务自动排除集成测试使用的股票代码

### 避坑

- 不要在后端 `.venv` 以外的目录安装 Python 依赖（前端 E2E 用全局 Python）
- Windows PowerShell 不支持 `&&`，用 `;` 分隔命令
