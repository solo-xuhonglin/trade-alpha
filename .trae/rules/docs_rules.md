# 文档同步规则

## 原则

代码变更时，文档必须同步更新。文档是代码的延伸，而非可有可无的补充。

## 同步时机

当修改以下内容时，必须同步更新相关文档：

| 代码变更 | 需更新的文档 |
|---------|-------------|
| 新增/删除模块 | `docs/system-design.md` 模块说明 |
| 新增/删除公共方法/类 | `docs/system-design.md` 接口设计 |
| 数据库字段变更 | `docs/database-schema.md` |
| 配置文件变更 | `docs/system-design.md` 配置说明 |

## 文档目录结构

```
docs/
├── system-design.md    # 系统设计文档
├── database-schema.md  # 数据库表结构
└── ...
```

## 提交规范

修改代码时，在同一 commit 中更新文档：
- ✅ `feat: add RSI indicator and update docs`
- ❌ `feat: add RSI indicator` (忘记更新文档)

## 文档质量

- 文档应描述 **已实现** 的功能，而非计划实现
- 使用代码示例时，确保示例与实际接口一致
- 删除功能时，同步删除文档中相关内容
