# 命名一致性重构设计

## 概述

集合名从 `portfolios` 重命名为 `account_configs` 后，API 路由、变量名、函数名、前端代码和文档尚未同步更新。本次重构的目标是保持命名一致性。

核心思路：将 `portfolio` 模块重构为 `account` 模块，`account_config` 作为账户的"配置"侧面（DAO 模型），`AccountManager` 作为运行时引擎。

## 命名映射

| 领域 | 当前 | 目标 | 说明 |
|------|------|------|------|
| Python 模块目录 | `portfolio/` | `account/` | 包名，后续可扩展账户其他内容 |
| 包导出 | `portfolio/__init__.py` | `account/__init__.py` | 导出函数名全部更新 |
| 服务文件 | `portfolio/service.py` | `account/service.py` | 完整服务层 |
| 引擎文件 + 类 | `portfolio/portfolio.py` / `Portfolio` | `account/account_manager.py` / `AccountManager` | 运行时投资组合引擎 |
| 运行时 Trade | `Trade` | `TradeRecord` | 轻量 dataclass，不与 DAO 耦合 |
| DAO 文件 + 模型 | `dao/portfolio.py` / `AccountConfig` | `dao/account_config.py` / `AccountConfig` | 模型名和集合名不变 |
| API 路由文件 | `api/routers/portfolio.py` | `api/routers/account_config.py` | 新文件 |
| API 路由前缀 | `/portfolios` | `/account-configs` | URL 路径 |
| API 标签 | `portfolios` | `account-configs` | Swagger 标签 |
| API Schema 类 | `PortfolioCreateRequest` 等 | `AccountConfigCreateRequest` 等 | 3 个 Pydantic 模型 |
| DB 字段 | `portfolio_id` | `account_config_id` | 不兼容变更，不迁移数据 |
| 前端 API 文件 | `src/api/portfolio.ts` | `src/api/account.ts` | 前端 API 模块 |
| 前端 API 接口/对象 | `Portfolio` / `portfolioApi` | `AccountConfig` / `accountConfigApi` | 接口名 |
| 前端组件 | `PortfolioView.vue` | `AccountsPage.vue` | Vue 组件 |
| 前端路由 | `/portfolios` | `/account-configs` | Vue 路由 |
| E2E 测试文件 | `test_portfolio_page.py` | `test_account_page.py` | 测试文件 |
| E2E 测试类 | `TestPortfolioPage` | `TestAccountPage` | 测试类 |
| 默认名称 | `default_portfolio` | `default_account_config` | 默认账户配置名称 |

## 不变部分

以下概念与"账户配置"不同，保持原名：

| 名称 | 说明 | 保持不变的原因 |
|------|------|---------------|
| `BacktestPortfolioDaily` (类) | 回测每日账户快照 | 记录投资组合的每日状态 |
| `backtest_portfolio_daily` (集合) | 每日快照集合 | 同上 |
| 导航标题 "账户管理" | 前端菜单文本 | 语义不变 |

## 修改范围

### 1. 后端 — 模块重命名

#### 文件重命名

| 当前路径 | 目标路径 |
|---------|---------|
| `portfolio/__init__.py` | `account/__init__.py` |
| `portfolio/service.py` | `account/service.py` |
| `portfolio/portfolio.py` | `account/account_manager.py` |
| `api/routers/portfolio.py` | `api/routers/account_config.py` |
| `dao/portfolio.py` | `dao/account_config.py` |

#### `account/__init__.py`

导出函数名更新：
- `create_portfolio` → `create_account_config`
- `get_portfolio_by_id` → `get_account_config_by_id`
- `get_portfolio_by_name` → `get_account_config_by_name`
- `list_portfolios` → `list_account_configs`
- `update_portfolio` → `update_account_config`
- `delete_portfolio` → `delete_account_config`
- `get_or_create_portfolio` → `get_or_create_account_config`
- `Portfolio` → `AccountManager`
- `Trade` → `TradeRecord`

#### `account/service.py`

函数名、参数名、日志全部更新：
- 参数 `portfolio_id` → `account_config_id`
- 内部变量 `portfolio` → `account_config`（指 AccountConfig 实例）
- DAO 导入路径 `dao.portfolio` → `dao.account_config`
- 日志标签 `portfolio` → `account_config`

#### `account/account_manager.py`

- 文件名变更，模块文档字符串更新
- 类名 `Portfolio` → `AccountManager`
- 运行时 Trade dataclass 改名 `Trade` → `TradeRecord`
- 内部逻辑不变

#### `api/routers/account_config.py`

- 路由前缀 `/portfolios` → `/account-configs`
- 路由参数 `/{portfolio_id}` → `/{account_config_id}`
- `PortfolioCreateRequest` → `AccountConfigCreateRequest`
- `PortfolioUpdateRequest` → `AccountConfigUpdateRequest`
- 函数名和变量名全部更新

#### `api/schemas.py`

- `PortfolioCreateRequest` → `AccountConfigCreateRequest`
- `PortfolioUpdateRequest` → `AccountConfigUpdateRequest`
- `PortfolioResponse` → `AccountConfigResponse`
- `BacktestRunRequest.portfolio_id` → `account_config_id`
- `BacktestResponse.portfolio_id` → `account_config_id`

#### `backtest/service.py`

- 导入 `list_portfolios_for_filter` → `list_account_configs_for_filter`
- 函数名 `list_portfolios_for_filter` → `list_account_configs_for_filter`
- 参数 `portfolio: Any` → `account_config: Any`
- 变量 `portfolio`（指 AccountConfig 实例） → `account_config`
- 参数 `portfolio_id` → `account_config_id`

#### `backtest/engine.py`

- `BacktestResult.portfolio_id` → `account_config_id`
- 注释和日志更新

#### `api/routers/backtest.py`

- 导入 `list_portfolios_for_filter` → `list_account_configs_for_filter`
- 变量 `portfolios` → `account_configs`
- 响应字段 `portfolios` → `account_configs`
- 查询参数 `portfolio_id` → `account_config_id`

#### 导入路径更新

以下文件需更新导入路径：

| 文件 | 变更 |
|------|------|
| `api/main.py` | `portfolio` router 导入路径更新 |
| `api/routers/__init__.py` | 导出 `account_config` 替代 `portfolio` |
| `dao/__init__.py` | 导入路径 `dao.portfolio` → `dao.account_config` |
| `dao/mongodb.py` | 文档导入 `dao.portfolio` → `dao.account_config` |
| `backtest/metrics.py` | 导入 `portfolio import Trade` → `account import TradeRecord` |

### 2. 后端 — 测试文件

#### 文件重命名

| 当前路径 | 目标路径 |
|---------|---------|
| `tests/portfolio/test_portfolio.py` | `tests/account/test_account_manager.py` |
| `tests/portfolio/test_service_portfolio.py` | `tests/account/test_service_account_config.py` |
| `tests/integration/test_41_portfolio_service.py` | `tests/integration/test_41_account_config_service.py` |

#### `tests/account/test_account_manager.py`

- 导入 `from trade_alpha.portfolio import Portfolio, Trade` → `from trade_alpha.account import AccountManager, TradeRecord`
- 类名 `TestPortfolio` → `TestAccountManager`
- 变量 `portfolio = Portfolio(...)` → `manager = AccountManager(...)`
- `trade = portfolio.buy(...)` → `trade_record = manager.buy(...)`
- 断言中的 `trade.field` → `trade_record.field`

#### `tests/account/test_service_account_config.py`

- 导入函数名全部更新（`create_portfolio` → `create_account_config` 等）
- Mock 路径 `trade_alpha.portfolio.service.Portfolio` → `trade_alpha.account.service.AccountConfig`
- 类名 `TestPortfolioService` → `TestAccountConfigService`
- 测试方法名和内部变量名全部更新

#### `tests/integration/test_41_account_config_service.py`

- 导入 `trade_alpha.portfolio` → `trade_alpha.account`
- 类名 `TestPortfolioService` → `TestAccountConfigService`
- 变量和方法全部更新

#### `tests/integration/test_60_backtest.py`

- 导入 `trade_alpha.portfolio` → `trade_alpha.account`
- 调用函数更新（`list_portfolios` → `list_account_configs` 等）
- 变量名更新（`portfolio` → `account_config`）
- 字段 `portfolio_id` → `account_config_id`

#### `tests/backtest/test_backtest_integration.py`

- 导入 `trade_alpha.portfolio` → `trade_alpha.account`
- 函数调用名更新
- 字段 `portfolio_id` → `account_config_id`

#### `tests/backtest/test_engine.py`

- 导入 `Portfolio` → `AccountManager`
- 变量 `portfolio = Portfolio(...)` → `manager = AccountManager(...)`
- 传入 `engine = BacktestEngine(..., manager)`

#### `tests/backtest/test_metrics.py`

- 导入 `Trade` → `TradeRecord`

#### `tests/backtest/test_service_backtest.py`

- 字段 `portfolio_id` → `account_config_id`

#### `tests/dao/test_dao_integration.py`

- `Portfolio.find(...)` → `AccountConfig.find(...)`
- 变量 `portfolio = Portfolio(...)` → `account_config = AccountConfig(...)`

### 3. 前端

#### 文件重命名

| 当前路径 | 目标路径 |
|---------|---------|
| `src/api/portfolio.ts` | `src/api/account.ts` |
| `src/views/PortfolioView.vue` | `src/views/AccountsPage.vue` |
| `e2e/tests/test_portfolio_page.py` | `e2e/tests/test_account_page.py` |

#### `src/api/account.ts`

- 接口 `Portfolio` → `AccountConfig`
- API 对象 `portfolioApi` → `accountConfigApi`
- API 路径 `/portfolios` → `/account-configs`
- 方法 `getPortfolios` → `getAccountConfigs` 等

#### `src/router/index.ts`

- 路由路径 `/portfolios` → `/account-configs`
- 路由名称 `Portfolios` → `AccountConfigs`
- 组件导入 `PortfolioView` → `AccountsPage`

#### `src/components/AppLayout.vue`

- 导航路径 `/portfolios` → `/account-configs`

#### `src/views/AccountsPage.vue`

- 变量 `portfolios` → `accountConfigs`
- 类型 `Portfolio` → `AccountConfig`
- API 调用 `portfolioApi` → `accountConfigApi`
- 方法名 `loadPortfolios` → `loadAccountConfigs` 等
- 默认名称 `default_portfolio` → `default_account_config`

#### `src/views/BacktestView.vue`

- 表单字段 `portfolio_name` → `account_config_name`

#### `src/views/TradeListView.vue`

- 过滤器选项 `filterOptions.portfolios` → `filterOptions.account_configs`
- 过滤器字段 `filters.portfolio_id` → `filters.account_config_id`

#### `src/api/backtest.ts`

- 接口字段 `portfolio_id` → `account_config_id`（请求参数和响应）
- `backtestApi.run()` 参数 `portfolio_id` → `account_config_id`

#### E2E 测试

- 类名 `TestPortfolioPage` → `TestAccountPage`
- 方法名 `test_navigate_to_portfolios_page` → `test_navigate_to_account_page`
- 路径 `/portfolios` → `/account-configs`

### 4. 文档 (4 个文件)

#### `docs/api.md`

- 所有 `/portfolios` 路径 → `/account-configs`
- 类名更新
- 响应示例更新

#### `docs/database-schema.md`

- 字段名 `portfolio_id` → `account_config_id`
- 集合 `account_configs` 的字段说明更新

#### `docs/system-design.md`

- 模块名 `portfolio/` → `account/`
- 路由 `/portfolios` → `/account-configs`
- 模块说明更新

#### `docs/frontend.md`

- 文件路径 `portfolio.ts` → `account.ts`
- 路由 `/portfolios` → `/account-configs`

## 执行顺序

1. **后端 DAO + 模块重命名**
   - 创建 `dao/account_config.py`，删除 `dao/portfolio.py`
   - 创建 `account/` 目录，移动文件
   - 创建 `account/service.py`，函数名全部更新
   - 创建 `account/account_manager.py`，类名和方法更新
   - 更新 `account/__init__.py` 导出

2. **后端 API + 其他模块**
   - 创建 `api/routers/account_config.py`
   - 更新 `api/schemas.py`
   - 更新 `backtest/service.py`、`backtest/engine.py`
   - 更新 `api/routers/backtest.py`
   - 更新所有导入路径（`api/main.py`、`api/routers/__init__.py`、`dao/__init__.py`、`dao/mongodb.py`、`backtest/metrics.py`）

3. **后端测试**
   - 重命名测试文件
   - 更新所有测试中的导入、类名、函数名、变量名

4. **前端代码更新**
   - 重命名 API 文件和视图组件
   - 更新路由和导航
   - 更新变量名和类型引用

5. **E2E 测试更新**
   - 重命名测试文件
   - 更新类名、方法名、路径

6. **文档更新**
   - 同步更新 4 个文档文件

7. **验证测试**
   - 运行后端集成测试
   - 运行后端单元测试
   - 运行 E2E 测试

## 风险评估

- **影响范围**：大（后端 + 前端 + 文档共 35+ 个文件）
- **回滚难度**：低（可通过 git 恢复）
- **API 兼容性**：破坏性变更，`/portfolios` 端点不再可用
- **数据兼容性**：破坏性变更，`portfolio_id` 字段改为 `account_config_id`，不迁移数据（测试环境）
- **测试覆盖**：高（集成测试 + 单元测试 + E2E 测试可验证）
