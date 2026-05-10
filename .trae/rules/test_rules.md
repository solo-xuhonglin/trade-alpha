# 测试规则

## 测试分类

### 单元测试
- **目的**：测试单个函数或类的行为
- **位置**：`backend/tests/trade_alpha/<模块>/test_<模块名>.py`
- **特点**：使用 mock 隔离外部依赖（数据库、API等）

### 集成测试
- **目的**：验证完整业务流程
- **位置**：`backend/tests/trade_alpha/integration/test_<order>_<模块名>.py`
- **特点**：使用真实环境（真实数据库、真实API）

## 目录结构

```
trade-alpha/
├── backend/
│   ├── src/
│   │   └── trade_alpha/           # 源码
│   │       ├── __init__.py
│   │       ├── config.py
│   │       └── data/
│   │           ├── __init__.py
│   │           ├── fetcher.py
│   │           └── storage.py
│   └── tests/
│       └── trade_alpha/
│           ├── data/              # 单元测试
│           │   ├── test_fetcher.py
│           │   └── test_storage.py
│           └── integration/       # 集成测试
│               ├── test_01_tushare_api.py
│               ├── test_10_mongodb_basic.py
│               └── ...
└── frontend/
    └── ...
```

## 测试命名规范

| 类型 | 命名格式 | 示例 |
|-----|---------|------|
| 单元测试文件 | `test_<模块名>.py` | `test_fetcher.py` |
| 集成测试文件 | `test_<order>_<模块名>.py` | `test_30_service_data.py` |
| 测试类 | `Test<功能名>` | `TestFetcher` |
| 测试方法 | `test_<具体行为>` | `test_fetch_stock_data_success` |

## 集成测试股票代码规范

| 类型 | 股票代码 | 名称 | 用途 |
|-----|---------|------|------|
| 主要代码 | `002594.SZ` | 比亚迪 | 默认测试数据，测试后保留 |
| 备用代码 | `601398.SH` | 工商银行 | 临时测试数据，测试后清理 |

**禁止使用**自定义拼接的测试代码（如 `TEST_*`、`test_code` 等）

## 运行命令

```bash
# 从 backend 目录运行测试
cd backend

# 运行所有测试
pytest tests/ -v

# 运行单元测试（排除集成测试）
pytest tests/ -v -m "not integration"

# 运行集成测试
pytest tests/ -v -m integration

# 运行特定模块测试
pytest tests/trade_alpha/data/ -v

# 运行集成测试（按层级）
pytest tests/trade_alpha/integration/ -v -k "test_0"  # Layer 1-2
pytest tests/trade_alpha/integration/ -v -k "test_4"  # Layer 4
```

## 测试原则

1. **隔离性**：单元测试不依赖外部环境
2. **可重复性**：测试可多次运行，结果一致
3. **清理性**：集成测试不污染数据库
4. **快速性**：单元测试应快速执行
5. **真实数据**：集成测试使用真实股票代码（002594.SZ / 601398.SH）
