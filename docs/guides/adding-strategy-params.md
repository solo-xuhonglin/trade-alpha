# 策略配置参数新增全流程

## 一、当前需要改动的 9 个位置（优化后）

```
DAO ───────────────────────────────────────────────┐
  dao/strategy_config.py         ← 加字段          │
                                                    │
Service ────────────────────────────────────────────┤
  strategy/service.py            ← 2 处改动         │
  ├─ create_strategy() params    ← 加参数           │
  └─ update_strategy() params    ← 加参数           │
  (update body 已自动化，无需改动)                   │
                                                    │
API ────────────────────────────────────────────────┤
  api/schemas.py                 ← 2 处改动         │
  ├─ StrategyCreateRequest       ← 加字段           │
  └─ StrategyUpdateRequest       ← 加字段           │
                                                    │
  api/routers/strategy_config.py ← 已自动化          │
  (serialize / create / update 全自动适配)           │
                                                    │
Frontend ───────────────────────────────────────────┤
  api/strategyConfig.ts          ← TS 接口加字段    │
                                                    │
  views/StrategyConfigView.vue   ← 4 处改动         │
  ├─ form 默认值                 ← 加初始值         │
  ├─ openDialog()                 ← 从 API 取值      │
  ├─ saveStrategy()               ← 发给后端         │
  └─ template UI                  ← 加输入控件       │
                                                    │
业务逻辑 ───────────────────────────────────────────┤
  使用该参数的业务代码                                │
  如: scoring.py / candidate_list_provider.py /     │
      multi_stock_strategy.py / trend_mode.py       │
```

**按顺序改**：DAO → Service → API Schema → (Router 自动) → Frontend → 业务逻辑

---

## 二、各层改动说明

| 层 | 说明 | 新增参数时 |
|--------|------|:---------:|
| DAO `StrategyConfig` | 直接声明字段 | **需要** |
| Service `create_strategy()` | 函数参数列表加参数 | **需要** |
| Service `update_strategy()` | 函数参数列表加参数（函数体内自动循环赋值，无需加 if 块） | **需要** |
| API Schema CreateRequest | 加 `Optional` 字段 | **需要** |
| API Schema UpdateRequest | 加 `Optional` 字段 | **需要** |
| Router `_strategy_to_dict` | `model_dump()` 自动序列化 | **不需要** |
| Router create handler | `request.model_dump()` 自动传参 | **不需要** |
| Router update handler | `request.model_dump()` 自动传参 | **不需要** |
| Frontend TS interface | 加字段声明 | **需要** |
| Frontend form/vue | 加默认值、弹窗取值、保存传参、模板控件 | **需要** |

后端只需改 **DAO + 2 个 Service 签名 + 2 个 Schema**，Router 和 update body 自动适配。

---

## 三、增删改查测试验证

每次新增参数后，用以下命令验证全链路：

```powershell
cd backend
.venv\Scripts\python -c "
import requests
base = 'http://localhost:8000/api/strategies'
items = requests.get(base, timeout=5).json()

# 1. 检查新建
r = requests.post(base, json={'name':'test_temp','type':'multi'}, timeout=5)
sid = r.json()['id']
print('new_field exists in create:', 'new_field' in r.json())

# 2. 检查读取
s = next(x for x in requests.get(base, timeout=5).json() if x.get('id')==sid)
print('new_field exists in list:', 'new_field' in s)

# 3. 检查更新
r2 = requests.put(f'{base}/{sid}', json={'new_field': ...}, timeout=5)
print('update returns new_field:', r2.json().get('new_field'))

# 4. 清除
requests.delete(f'{base}/{sid}', timeout=5)
"
```

---

## 四、常见遗漏点检查

| 遗漏场景 | 表现 |
|---------|------|
| API Schema UpdateRequest 漏了 | 更新返回 422 或静默丢弃 |
| Service 函数签名漏了 | 编译报错 IDE 会提示 |
| TS interface 字段名写错 | 编译报错或运行时 undefined |
| openDialog 漏了 `??` 回退 | 编辑时显示 undefined |

**最容易遗漏的**：UpdateRequest 和 Service 签名不一致——DAO 和 CreateRequest 加了，但 UpdateRequest 或 Service 签名漏了，更新静默不生效。
