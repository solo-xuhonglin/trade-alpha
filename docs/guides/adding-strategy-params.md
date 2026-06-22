# 策略配置参数新增全流程

## 一、当前需要改动的 13 个位置

```
DAO ───────────────────────────────────────────────┐
  dao/strategy_config.py         ← 加字段          │
                                                    │
Service ────────────────────────────────────────────┤
  strategy/service.py            ← 3 处改动         │
  ├─ create_strategy() params    ← 加参数           │
  ├─ update_strategy() params    ← 加参数           │
  └─ update_strategy() body      ← 加 if 赋值块     │
                                                    │
API ────────────────────────────────────────────────┤
  api/schemas.py                 ← 2 处改动         │
  ├─ StrategyCreateRequest       ← 加字段           │
  └─ StrategyUpdateRequest       ← 加字段           │
                                                    │
  api/routers/strategy_config.py ← 3 处改动         │
  ├─ _strategy_to_dict()         ← 加序列化         │
  ├─ create handler              ← 加传参           │
  └─ update handler              ← 加传参           │
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

**按顺序改**：DAO → Service → API Schema → Router → Frontend → 业务逻辑

---

## 二、可优化的 3 个地方

### 优化点 1: Router 序列化改用 `model_dump()`（省去 70 行）

**当前**：`_strategy_to_dict()` 手写 70+ 个 `"field": s.field`

**改为**：
```python
def _strategy_to_dict(s) -> dict:
    exclude = {"id", "account_config_id", "training_id"}
    d = s.model_dump(exclude=exclude)
    d["id"] = str(s.id)
    return d
```

效果：DAO 加字段后自动出现在 API 响应中，router 无需改动。

### 优化点 2: Router 增删改查改用 `request.model_dump()`（省去 140 行）

**当前**：create/update handler 手写 70+ 个 `field=request.field`

**改为**：
```python
# Create handler
data = request.model_dump(exclude_none=True, exclude={"type"})
s = await create_strategy(**data, strategy_type=request.type)

# Update handler
data = request.model_dump(exclude_none=True)
s = await update_strategy(strategy_id, **data)
```

效果：API Schema 加字段后自动透传到 service，router 无需改动。

### 优化点 3: Service update body 改用循环赋值（省去 77 个 if 块）

**当前**：update_strategy() 底部 77 行 `if X is not None: strategy.X = X`

**改为**：
```python
# name 特殊处理（需要重名检查）
if name is not None:
    ...

# 其余字段自动循环赋值
field_names = StrategyConfig.model_fields.keys()
for f in field_names:
    val = locals().get(f)
    if val is not None and f != "name":
        setattr(strategy, f, val)
```

效果：Service 加参数后自动生效，不需要再加 if 块。

### 优化效果汇总

| 改动点 | 当前行数 | 优化后 | 新增参数时是否需要改 |
|--------|:-------:|:------:|:------------------:|
| Router `_strategy_to_dict` | 74 行 | 5 行 | **不需要** |
| Router create handler | ~70 行传参 | 2 行 | **不需要** |
| Router update handler | ~70 行传参 | 2 行 | **不需要** |
| Service update body | 77 个 if 块 | 5 行循环 | **不需要** |
| Service `create_strategy` params | ~80 行 | 不变 | **需要** |
| Service `update_strategy` params | ~80 行 | 不变 | **需要** |
| API Schema CreateRequest | ~70 行 | 不变 | **需要** |
| API Schema UpdateRequest | ~70 行 | 不变 | **需要** |
| DAO Model | ~80 行 | 不变 | **需要** |
| Frontend TS interface | ~75 行 | 不变 | **需要** |
| Frontend form/vue | ~150 行 | 不变 | **需要** |

**优化后新增参数只需改 5 个地方**：DAO、2 个 API Schema、Service 2 个函数签名。router 和 update body 完全自动化。

---

## 三、优化前后对比

### 当前流程
```
DAO加字段 → Service加参数×2 → Schema加字段×2 
→ Router序列化+create+update传参×3 → 前端TS+form+openDialog+save+template×5
= 13 处
```

### 优化后流程
```
DAO加字段 → Service加参数×2 → Schema加字段×2 
→ (router/update body 自动适配) → 前端TS+form+openDialog+save+template×5
= 9 处（后端从 8 处减到 4 处）
```

---

## 四、增删改查测试验证清单

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

## 五、常见遗漏点检查

| 遗漏场景 | 表现 |
|---------|------|
| Router serialize 漏了 | 前端读不到该字段 |
| Router create/update 漏了 | 新建/修改不保存 |
| Service update body 漏了 | 更新不生效（静默丢弃） |
| API Schema UpdateRequest 漏了 | 更新返回 422 或静默丢弃 |
| TS interface 字段名写错 | 编译报错或运行时 undefined |
| openDialog 漏了 `??` 回退 | 编辑时显示 undefined |

**最容易遗漏的**：`atr_stop_multiplier` 类的 bug — DAO 和 Schema 都有，但 router 和 service 漏了，导致更新不报错但也不生效。
