# 策略类型命名重构

## 问题

项目中 "portfolio" 一词在不同上下文中含义不同，造成歧义：

| 上下文 | 当前命名 | 含义 |
|-------|---------|------|
| 策略类型 | `"portfolio"` / `PortfolioStrategy` | 多股票排名策略（与 single 对应） |
| 执行快照 | `ExecutionPortfolioDaily` | 每日投资组合持仓快照 |
| 账户配置 | `prod_account_config` | 生产环境账户配置 |

将多股票策略类型重命名为 `"multi"`，消除与"投资组合 (portfolio)"概念的混淆。

## 变更范围

### 1. 后端 — 类名 + 文件名

| 当前 | 改为 |
|------|------|
| `class PortfolioStrategy` | `class MultiStockStrategy` |
| `strategy/portfolio_strategy.py` | `strategy/multi_stock_strategy.py` |

### 2. 策略类型值（前后端协议 + 数据库）

- 所有 `"portfolio"` 策略类型 → `"multi"`
- 前端中文标签 `"组合"` → `"多股票"`，`"组合配置"` → `"多股票配置"`

### 3. 脚本文件名

| 当前 | 改为 |
|------|------|
| `backtest_portfolio.py` | `backtest_multi.py` |

### 4. 不移改的

- `ExecutionPortfolioDaily` — "portfolio" 指投资组合概念，保留
- `PROD_ACCOUNT_CONFIG_NAME` — 不久前才改过，保留
- 其他非策略类型的 `portfolio` 引用

## 影响文件清单

**后端源码（~8 个文件）：**
- `strategy/multi_stock_strategy.py`（新建，原 portfolio_strategy.py 删除）
- `strategy/__init__.py` — import 更新
- `strategy/service.py` — 参数名
- `execution/pipeline.py` — mode 值 + import
- `api/routers/backtest.py` — BacktestRunRequest.mode 默认值
- `dao/strategy_config.py` — type 默认值

**脚本（~2 个文件）：**
- `backtest_multi.py`（新建，原 backtest_portfolio.py 删除）
- `backtest_single.py` — 无变动
- `scripts.md`

**前端（~2 个文件）：**
- `StrategyConfigView.vue` — strategyTypes 数组 + 中文标签 + 逻辑判断
- `BacktestManageView.vue` — currentMode 判断逻辑 + 默认值

**测试（~1 个文件）：**
- `test_44_strategy_service.py` — 策略类型值

**文档（~4 个文件）：**
- `docs/system-design.md` — 文件名 + 策略模式名
- `docs/api.md` — API 示例中的值
- `docs/database-schema.md` — 数据库示例中的值
- `docs/scripts.md` — backtest_multi 脚本名

## 执行策略

所有改动在同一 commit 中完成，保持原子性。
