# 测试规则

## 测试分类

### 单元测试
- **目的**：测试单个函数或类的行为
- **位置**：`tests/trade_alpha/<模块>/test_<模块名>.py`
- **特点**：使用 mock 隔离外部依赖（数据库、API等）

### 集成测试
- **目的**：验证完整业务流程
- **位置**：`tests/trade_alpha/<模块>/test_<模块名>_integration.py`
- **特点**：使用真实环境（真实数据库、真实API）

## 目录结构

```
trade-alpha/
├── src/
│   └── trade_alpha/           # 源码
│       ├── __init__.py
│       ├── config.py
│       └── data/
│           ├── __init__.py
│           ├── fetcher.py
│           └── storage.py
└── tests/
    └── trade_alpha/           # 与源码层级对应
        └── data/
            ├── test_fetcher.py
            ├── test_storage.py
            └── test_data_integration.py
```

## 测试命名规范

| 类型 | 命名格式 | 示例 |
|-----|---------|------|
| 单元测试文件 | `test_<模块名>.py` | `test_fetcher.py` |
| 集成测试文件 | `test_<模块名>_integration.py` | `test_data_integration.py` |
| 测试类 | `Test<功能名>` | `TestFetcher` |
| 测试方法 | `test_<具体行为>` | `test_fetch_stock_data_success` |

## 运行命令

```bash
# 运行所有测试
pytest tests/ -v

# 运行单元测试（排除集成测试）
pytest tests/ -v -m "not integration"

# 运行集成测试
pytest tests/ -v -m integration
```

## 测试原则

1. **隔离性**：单元测试不依赖外部环境
2. **可重复性**：测试可多次运行，结果一致
3. **清理性**：集成测试不污染数据库
4. **快速性**：单元测试应快速执行
