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
| 新增/修改 API 接口 | `docs/api.md` |
| 前端页面/组件变更 | `docs/frontend.md` |
| 配置文件变更 | `docs/system-design.md` 配置说明 |

## 文档目录结构

```
docs/
├── system-design.md    # 系统设计文档（整体架构、模块说明）
├── database-schema.md  # 数据库表结构
├── api.md              # API 接口文档
└── frontend.md         # 前端设计与架构文档
```

## 提交规范

修改代码时，在同一 commit 中更新文档：
- ✅ `feat: add RSI indicator and update docs`
- ❌ `feat: add RSI indicator` (忘记更新文档)

## 文档质量

- 文档应描述 **已实现** 的功能，而非计划实现
- 使用代码示例时，确保示例与实际接口一致
- 删除功能时，同步删除文档中相关内容

## 文档编写规范

### system-design.md
- 描述系统整体架构
- 各模块的职责和主要接口
- 技术栈和设计原则

### database-schema.md
- 每个集合/表的完整字段定义
- 索引信息
- 数据示例

### api.md
- 所有 RESTful 端点
- 请求/响应格式
- 错误码说明

### frontend.md
- 前端技术栈
- 项目结构
- 页面设计和路由
- 关键组件说明
