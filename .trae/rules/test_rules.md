# 测试规则

## 测试分类

### 单元测试
- **目的**：测试单个函数或类的行为
- **位置**：`tests/unit/trade_alpha/<模块>/`
- **特点**：使用 mock 隔离外部依赖（数据库、API等）
- **运行**：`.venv\Scripts\pytest tests/unit/ -v`

### 集成测试
- **目的**：验证完整业务流程
- **位置**：`tests/integration/trade_alpha/<模块>/`
- **标记**：`@pytest.mark.integration`
- **特点**：使用真实环境（真实数据库、真实API）
- **运行**：`.venv\Scripts\pytest tests/integration/ -v`

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
    ├── unit/
    │   └── trade_alpha/       # 与源码层级对应
    │       └── data/
    │           ├── test_fetcher.py
    │           └── test_storage.py
    └── integration/
        └── trade_alpha/       # 与源码层级对应
            └── data/
                └── test_data.py
```

## 测试流程

### 单元测试流程
1. Mock 外部依赖
2. 准备测试数据
3. 调用被测函数
4. 验证返回结果
5. 验证 mock 调用

### 集成测试流程
1. **清理环境**：删除测试数据
2. **执行操作**：调用真实接口
3. **验证结果**：检查数据库状态
4. **清理环境**：删除测试数据

## 测试命名规范

| 类型 | 命名格式 | 示例 |
|-----|---------|------|
| 测试文件 | `test_<模块名>.py` | `test_fetcher.py` |
| 测试类 | `Test<功能名>` | `TestFetcher` |
| 测试方法 | `test_<具体行为>` | `test_fetch_stock_data_success` |

## 运行命令

```bash
# 运行所有测试
.venv\Scripts\pytest tests/ -v

# 运行单元测试
.venv\Scripts\pytest tests/unit/ -v

# 运行集成测试
.venv\Scripts\pytest tests/integration/ -v
```

## 测试原则

1. **隔离性**：单元测试不依赖外部环境
2. **可重复性**：测试可多次运行，结果一致
3. **清理性**：集成测试不污染数据库
4. **快速性**：单元测试应快速执行
