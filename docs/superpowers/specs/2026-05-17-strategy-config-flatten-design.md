# 策略配置扁平化设计

## 问题

策略配置目前以 `config: Dict[str, Any]` 存储在后端，前端用 textarea 编辑原始 JSON，存在以下问题：
- 编辑体验差，用户需要了解 JSON 结构，容易出错
- 字段类型不严格，后端没有做验证
- 前端无法提供表单级别的输入提示和约束

## 目标

将策略配置从嵌套 `config` 字典拆分为扁平字段，和模型配置保持一致的架构风格。

## 范围限定

- 只处理现有两种策略类型：`single` 和 `portfolio`
- 保持现有策略逻辑（single_stock.py、portfolio.py）功能不变，仅调整配置传递方式
- **注意**：`target_ts_code` 和 `ts_codes` 是**回测任务**的参数，不属于策略配置

## 后端改动

### StrategyConfig Document ([strategy.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/dao/strategy.py))

**移除**：`config: Dict[str, Any]`

**新增字段**：
```python
min_order_value: float = 5000.0
stop_loss_pct: float = -0.1  # 注意是负数，表示-10%
max_hold_days: int = 30
# portfolio 专属字段
max_positions: Optional[int] = 10
max_position_pct: Optional[float] = 0.3
```

### API Schemas ([schemas.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/api/schemas.py))

更新请求/响应模型为扁平字段，移除 `config`。

### API 路由 ([strategy_config.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/api/routers/strategy_config.py))

- `_strategy_to_dict` 响应函数返回所有字段
- 请求模型使用更新后的 Schemas

### 策略服务 ([service.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/strategy/service.py))

`create_strategy` 和 `update_strategy` 函数签名改为接受具体字段，不再接受 `config` 字典。

### 策略构造函数 ([single_stock.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/strategy/single_stock.py), [portfolio.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/strategy/portfolio.py))

构造函数签名保持不变，但在调用时从 StrategyConfig 扁平字段传参。

### 数据迁移（可选但建议）

对于现有 `config` 字典数据，提供迁移脚本，从旧字段填充到新的扁平字段。

## 前端改动

### API 接口 ([strategy.ts](file:///d:/projects/trade-alpha/frontend/src/api/strategy.ts))

Strategy 接口改为扁平字段，移除 `config`，新增 `updated_at`。

### StrategyView.vue — 重新设计表单

参考 [AccountsPage.vue](file:///d:/projects/trade-alpha/frontend/src/views/AccountsPage.vue) 和 [ModelsView.vue](file:///d:/projects/trade-alpha/frontend/src/views/ModelsView.vue) 的风格：

- 弹窗宽度设为 `max-width="600px"`
- 使用 v-row/v-col 网格布局
- 按策略类型动态显示对应字段：
  - **single 类型**：`min_order_value`, `stop_loss_pct`, `max_hold_days`
  - **portfolio 类型**：`max_positions`, `max_position_pct`, `min_order_value`, `stop_loss_pct`, `max_hold_days`
- 表格列添加 `min_order_value`、`stop_loss_pct`、`max_hold_days`，移除 `config` 列

### 字段类型约束

| 字段 | 类型 | 单位 | 默认值 | 约束 |
|------|------|------|--------|------|
| min_order_value | float | 元 | 5000 | ≥ 0 |
| stop_loss_pct | float | - | -0.1 | ≤ 0 |
| max_hold_days | int | 天 | 30 | ≥ 1 |
| max_positions | int | 只数 | 10 | ≥ 1 |
| max_position_pct | float | 比例 | 0.3 | 0 ~ 1 |
