# 后端脚本说明

## 目录

`backend/scripts/` 下的脚本按用途分为五类：

| 类别 | 脚本 | 说明 |
|------|------|------|
| **模型训练** | `train_model.py` | 训练预测模型 |
| **实盘管理** | `run_live_suggestion.py` | 运行实盘建议流水线 |
| | `sync_live_portfolio.py` | 同步实盘持仓（配合 `positions.json`） |
| **数据维护** | `backfill_weekly_features.py` | 回填周线特征数据 |
| | `reset_stock_data.py` | 重置股票数据（清空日线数据，重新同步） |
| **回测分析** | `analyze_backtest.py` | 分析指定回测结果的交易记录 |
| | `analyze_backtest_today.py` | 分析当天所有回测结果，输出到 `backtest_analysis/` |
| | `analyze_backtest_vol.py` | 回测中熊市买入行为和止损效果分析 |
| | `analyze_bottom.py` | 底部检测分析——寻找领先指标 |
| | `analyze_buy_timing.py` | 买入时机深度分析（价格峰谷位置、市场状态） |
| | `analyze_phase_strategy.py` | 市场阶段策略分析（含 daily-rebalanced 基线对比） |
| | `analyze_regime.py` | 市场状态分类深度分析 |
| | `check_backtests.py` | 快速查看回测结果数量和参数分布 |
| **服务管理** | `check_server.py` | 检查后端服务是否运行 |

---

## 模型训练

### train_model.py — 训练预测模型

```bash
python scripts/train_model.py
python scripts/train_model.py --train-start 20160101 --train-end 20241231
```

流程：
1. 获取所有活跃股票（排除测试股票）
2. 筛选有足够数据的股票
3. 创建/使用 `prod_model_config` 模型配置
4. 删除旧的 `prod_training` 训练记录
5. 执行训练，保存为 `prod_training`

---

## 实盘管理

### run_live_suggestion.py — 运行实盘建议流水线

```bash
python scripts/run_live_suggestion.py --training <id> --strategy <id>
```

需要指定训练记录 ID 和策略配置 ID。执行结果输出到控制台。

### sync_live_portfolio.py — 同步实盘持仓

通过 JSON 文件指定目标持仓，自动对比当前 API 中的持仓数据并执行增/删/改操作。

```bash
# 预览变更（不实际执行）
python scripts/sync_live_portfolio.py positions.json --dry-run

# 实际执行同步
python scripts/sync_live_portfolio.py positions.json
```

#### JSON 格式

```json
{
    "603256.SH": {"name": "宏和科技", "shares": 1000, "cost_price": 189.789},
    "688347.SH": {"name": "华虹公司", "shares": 900, "cost_price": 209.056},
    "unknown_1": {"name": "生益科技", "shares": 1500, "cost_price": 147.757}
}
```

- **已知 ts_code**：直接以 `ts_code` 为 key
- **未知 ts_code**：key 使用任意不含 `.` 的字符串，脚本会自动通过名称搜索匹配股票代码
- 脚本会删除目标中不存在的持仓、更新股数/成本价变化的持仓、新增目标中未有的持仓

---

## 数据维护

### backfill_weekly_features.py — 回填周线特征

```bash
python scripts/backfill_weekly_features.py
python scripts/backfill_weekly_features.py --ts-code 002594.SZ
```

为已有日线数据的股票计算 `week_open`、`week_high`、`week_low`、`week_close`、`week_vol_avg`、`week_amount_avg` 等周线字段，显示实时进度。

### reset_stock_data.py — 重置股票数据

```bash
python scripts/reset_stock_data.py
```

将股票状态重置为 pending，清空日线和周线数据，用于触发调度器重新全量同步。

---

## 回测分析

### analyze_backtest.py — 分析回测结果

```bash
python scripts/analyze_backtest.py <backtest_name>
```

分析指定回测的交易记录，输出交易明细和关键指标。

### analyze_backtest_today.py — 分析当天回测

```bash
python scripts/analyze_backtest.py
```

分析当天运行的所有回测结果，输出到 `backtest_analysis/` 目录。

### analyze_backtest_vol.py — 成交量分析

```bash
python scripts/analyze_backtest_vol.py
```

分析回测中的熊市买入行为和止损效果。

### analyze_bottom.py — 底部检测分析

```bash
python scripts/analyze_bottom.py
```

寻找领先指标。比较 2022 和 2025 H1 验证不同市场状态下的有效性。

### analyze_buy_timing.py — 买入时机分析

```bash
python scripts/analyze_buy_timing.py
```

分析买入相对于价格峰谷的位置、趋势反转时的买入时机模式、盈亏分布、买入时市场状态 vs 最终结果。

### analyze_phase_strategy.py — 阶段策略分析

```bash
python scripts/analyze_phase_strategy.py
```

计算 daily equal-weight 基线，与现有基线对比，设计阶段依赖的调整策略。

### analyze_regime.py — 市场状态分析

```bash
python scripts/analyze_regime.py
```

提取回测快照中的每日市场指标，对比实际市场行为，识别真实信号与噪音特征。

### check_backtests.py — 查看回测列表

```bash
python scripts/check_backtests.py
```

快速查看数据库中回测结果的数量和参数分布。

---

## 服务管理

### 前置条件

使用 `service.bat` / `service.ps1` 管理服务前，需确保后端虚拟环境已创建并安装依赖：

```bash
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
```

`service.ps1` 会使用 `backend\.venv\Scripts\python.exe` 启动后端。如果虚拟环境缺少依赖（如 `fastapi`），后端进程会静默失败。

### check_server.py

```bash
python scripts/check_server.py
```

通过健康检查接口检查后端服务是否运行。可用 `service.ps1` 或 `service.bat` 管理服务启停：

```powershell
# 启动服务
service.bat start

# 停止服务
service.bat stop

# 重启服务（自动清理 debug.log、info.log、warning.log、error.log）
service.bat restart
```

> 服务管理优先使用 `service.bat` / `service.ps1`，检查服务状态优先使用 `check_server.py`。

---

## 配置文件

### positions.json

实盘持仓同步的配置文件，存放目标持仓信息。具体格式见 `sync_live_portfolio.py` 说明。
