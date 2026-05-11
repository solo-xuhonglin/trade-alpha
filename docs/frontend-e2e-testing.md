# 前端 E2E 测试文档

## 测试规则

### 测试数据
- 依赖后端集成测试创建的数据
- 主要使用 `002594.SZ` 相关数据
- 回测历史、交易记录由集成测试生成

### 数据清理
- E2E 测试不清理数据
- 仅读取后端集成测试创建的数据

## 测试顺序

| Order | 文件 | 类名 | 说明 |
|-------|------|------|------|
| 1 | test_data_page.py | TestDataPage | 数据管理页面测试 |
| 2 | test_account_page.py | TestAccountPage | 账户管理页面测试 |
| 3 | test_strategy_page.py | TestStrategyPage | 策略管理页面测试 |
| 4 | test_models_page.py | TestModelsPage | 模型管理页面测试 |
| 5 | test_trainings_page.py | TestTrainingsPage | 训练记录页面测试 |
| 6 | test_backtest_page.py | TestBacktestPage | 回测页面测试 |
| 7 | test_trades_page.py | TestTradesPage | 交易记录页面测试 |

## 测试覆盖

| 页面 | URL | 测试内容 |
|------|-----|---------|
| 数据管理 | `/data` | 导航、加载股票列表、验证表头、验证数据 |
| 账户管理 | `/account-configs` | 导航、加载账户列表、验证表头、验证数据 |
| 策略管理 | `/strategies` | 导航、加载策略列表、验证表头、验证数据 |
| 模型管理 | `/models` | 导航、加载配置列表、验证表头、新建配置按钮 |
| 训练记录 | `/trainings` | 导航、加载训练列表、验证表头、配置筛选 |
| 回测 | `/backtest` | 导航、验证表头、验证运行按钮、验证数据 |
| 交易记录 | `/trades` | 导航、加载交易列表、验证表头、验证数据 |

## 依赖关系

```
┌─────────────────────────┐
│   后端集成测试 (Layer 6) │  ← 创建回测历史、交易记录
└─────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│                   前端 E2E 测试                            │
├──────────┬──────────┬──────────┬──────────┬──────────┤
│ DataPage  │AccountConfig │Strategy  │Backtest  │ Trades   │
│           │  Page    │  Page    │  Page    │  Page    │
└──────────┴──────────┴──────────┴──────────┴──────────┘
```

## 运行命令

```bash
cd frontend/e2e

# 运行所有 E2E 测试
pytest -v --base-url=http://localhost:3000

# 运行单个测试文件
pytest tests/test_data_page.py -v

# 浏览器 UI 模式
pytest --headed

# 运行特定测试
pytest tests/test_data_page.py::TestDataPage::test_has_data -v
```

## 前置条件

1. 后端服务运行在端口 8000
2. 后端集成测试已运行（创建测试数据）
3. 前端服务运行中（npm run dev）

## 扩展指南

- 新增页面测试：`test_<页面>_page.py`
- 测试命名：`Test<页面名>Page`
- 测试方法：`test_<具体行为>`
