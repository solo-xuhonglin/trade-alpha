# Import Rules

## Prefer global imports over local imports

- 所有 import 语句必须放在文件顶部，禁止在函数/方法体内部使用 `from ... import ...` 或 `import ...`
- 例外情况（必须添加注释说明原因）：
  1. `if __name__ == "__main__"` 块内的导入
  2. 循环引用（如 `dao/mongodb.py` 延迟导入所有 Model）
  3. 可选的第三方依赖（try/except ImportError 块）
- 全局导入的好处：加载一次即可，便于代码审查，IDE 能正确分析依赖关系
