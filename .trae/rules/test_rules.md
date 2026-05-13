# 测试规则

## 测试分类

| 类型 | 位置 | 特点 |
|-----|------|------|
| 单元测试 | `backend/tests/trade_alpha/<模块>/` | mock 隔离外部依赖 |
| 集成测试 | `backend/tests/trade_alpha/integration/` | 真实环境（数据库、API） |
| E2E 测试 | `frontend/e2e/tests/` | Playwright 浏览器自动化 |

## 测试文档

- [后端集成测试](../docs/backend-integration-testing.md)
- [前端 E2E 测试](../docs/frontend-e2e-testing.md)

## 测试数据

| 股票代码 | 名称 | 用途 |
|---------|------|------|
| `002594.SZ` | 比亚迪 | 默认数据，测试后保留 |
| `601398.SH` | 工商银行 | 临时数据，测试后清理 |

### 测试数据创建位置
- 默认记录 `test_portfolio`：TestAccountConfigService.test_ensure_default_account_config
- 默认记录 `test_strategy`：TestStrategyService.test_ensure_default_strategy
- 默认记录 `test_model_config`：TestModelConfigService.test_ensure_default_config
- 默认记录 `002594.SZ` 股票数据：TestServiceData.test_ensure_default_data

## 运行命令

```bash
# 集成测试
cd backend && pytest tests/trade_alpha/integration/ -v

# E2E 测试
cd frontend/e2e && pytest -v --base-url=http://localhost:3000
```

## 全流程测试

1. 清理数据库（可选）
2. 运行集成测试
3. 启动后端服务
4. 启动前端服务
5. 运行 E2E 测试

## 测试与定时任务隔离

集成测试使用的股票代码由定时任务排除，避免并发修改 `sync_status` 造成冲突：

```python
# backend/src/trade_alpha/scheduler/data_sync.py
TEST_EXCLUDED_TS_CODES = ["002594.SZ", "601398.SH"]
```

定时任务的 `get_pending_stocks` 和 `get_data_completed_stocks` 查询会自动排除这些代码。

## 测试原则

1. 单元测试隔离外部依赖
2. 集成测试使用真实数据
3. E2E 测试依赖集成测试数据
4. 集成测试股票代码需在 `TEST_EXCLUDED_TS_CODES` 中声明
