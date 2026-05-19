# 数据分布统计分析功能实施计划

## 任务分解

### 1. 后端数据模型扩展
| 任务 | 文件 | 说明 |
|------|------|------|
| 1.1 扩展 TaskType | `backend/src/trade_alpha/dao/task.py` | 添加 `DATA_ANALYSIS` |
| 1.2 创建 DataAnalysisResult 模型 | `backend/src/trade_alpha/dao/data_analysis_result.py` | 新增 DAO 模型 |
| 1.3 更新 dao/__init__.py 导出 | `backend/src/trade_alpha/dao/__init__.py` | 导出新模型 |

### 2. 后端分析服务
| 任务 | 文件 | 说明 |
|------|------|------|
| 2.1 创建分析服务 | `backend/src/trade_alpha/data/analysis_service.py` | 包含完整分析逻辑 |
| 2.2 集成到 data/__init__.py | `backend/src/trade_alpha/data/__init__.py` | 导出服务 |

### 3. 后端 API 开发
| 任务 | 文件 | 说明 |
|------|------|------|
| 3.1 创建 API 路由 | `backend/src/trade_alpha/api/routers/data_analysis.py` | 触发任务、获取状态 API |
| 3.2 注册路由 | `backend/src/trade_alpha/api/main.py` | 添加到应用 |

### 4. 前端菜单调整
| 任务 | 文件 | 说明 |
|------|------|------|
| 4.1 调整 AppLayout 菜单 | `frontend/src/components/AppLayout.vue` | 数据改为子菜单，添加数据分析 |
| 4.2 调整路由 | `frontend/src/router/index.ts` | 更新路由配置 |

### 5. 前端页面开发
| 任务 | 文件 | 说明 |
|------|------|------|
| 5.1 创建数据列表页面 | `frontend/src/views/DataListView.vue` | 原数据页面重命名 |
| 5.2 创建数据分析页面 | `frontend/src/views/DataAnalysisView.vue` | 完整分析页面 |
| 5.3 创建 API 类型定义 | `frontend/src/api/dataAnalysis.ts` | API 类型和调用函数 |

## 实施顺序

1. **Phase 1: 后端数据模型** (任务 1.1-1.3)
2. **Phase 2: 后端分析服务** (任务 2.1-2.2)
3. **Phase 3: 后端 API** (任务 3.1-3.2)
4. **Phase 4: 前端菜单和路由** (任务 4.1-4.2)
5. **Phase 5: 前端页面** (任务 5.1-5.3)
