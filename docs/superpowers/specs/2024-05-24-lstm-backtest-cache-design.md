# LSTM 回测数据缓存优化设计方案

## 一、问题背景

当前 LSTM 模型在回测过程中存在严重的性能问题：每个交易日都会重新加载完整的历史数据，导致大量重复的数据库查询。

### 问题示例
- 序列长度: 20天
- 回测时间: 100天
- 股票数量: 3000只
- **问题**: 每天重复查询几乎相同的数据，只有最后1天是新的

## 二、优化目标

- 只针对 LSTM 模型优化，不影响 XGBoost
- 同时优化回测和实盘两种场景
- 大幅减少重复数据库查询
- 控制内存占用，避免内存泄漏

## 三、核心设计方案

### 3.1 整体架构

在 DataLoader 内部实现滑动窗口缓存，对 Predictor 完全透明。

```
ExecutionPipeline → Predictor → DataLoader (with cache) → Database
                                              ↓
                                        缓存逻辑
```

### 3.2 DataLoader 新增状态

```python
class DataLoader:
    def __init__(self):
        # 原有的无状态属性保持不变
        # 新增: 缓存结构: { ts_code: [sorted_stock_records] }
        self._history_cache: Dict[str, List[StockDailyRecord]] = {}
```

### 3.3 辅助方法

```python
def _get_cache_start(self, ts_code: str) -> Optional[str]:
    """获取某只股票缓存的最早日期"""
    if ts_code not in self._history_cache or not self._history_cache[ts_code]:
        return None
    return self._history_cache[ts_code][0].trade_date

def _get_cache_end(self, ts_code: str) -> Optional[str]:
    """获取某只股票缓存的最新日期"""
    if ts_code not in self._history_cache or not self._history_cache[ts_code]:
        return None
    return self._history_cache[ts_code][-1].trade_date

def _trim_cache(self, ts_code: str, keep_days: int):
    """清理缓存，只保留最近 keep_days 天的数据"""
    if ts_code not in self._history_cache:
        return
    if len(self._history_cache[ts_code]) > keep_days:
        trim_count = len(self._history_cache[ts_code]) - keep_days
        self._history_cache[ts_code] = self._history_cache[ts_code][trim_count:]
```

### 3.4 load_history_data 优化流程

```python
async def load_history_data(self, end_date: str, ts_codes: List[str], days: int) -> pd.DataFrame:
    """
    加载历史数据，带缓存优化
    
    Args:
        end_date: 结束日期 (YYYYMMDD)
        ts_codes: 股票代码列表
        days: 需要的天数（序列长度 + buffer）
    
    Returns:
        DataFrame: 历史数据
    """
    # 1. 计算需要的安全缓冲: 2×days，确保足够用于特征工程
    keep_days = days * 2
    
    all_records = []
    
    for ts_code in ts_codes:
        cache_start = self._get_cache_start(ts_code)
        cache_end = self._get_cache_end(ts_code)
        
        if cache_start is None:
            # 情况1: 未缓存，加载完整数据
            load_start = self._calc_start_date(end_date, keep_days)
            new_records = await self._load_from_db(load_start, end_date, [ts_code])
            # 存入缓存
            self._history_cache[ts_code] = sorted(new_records, key=lambda r: r.trade_date)
        else:
            # 情况2: 已缓存，加载增量数据
            if cache_end < end_date:
                # 只加载缓存日期之后的数据
                incremental_records = await self._load_from_db(
                    self._next_date(cache_end), 
                    end_date, 
                    [ts_code]
                )
                # 追加到缓存
                self._history_cache[ts_code].extend(incremental_records)
                # 保持排序
                self._history_cache[ts_code].sort(key=lambda r: r.trade_date)
            
            # 清理缓存: 只保留最近 keep_days 天
            self._trim_cache(ts_code, keep_days)
        
        # 从缓存中收集数据
        if ts_code in self._history_cache:
            all_records.extend(self._history_cache[ts_code])
    
    # 转换为 DataFrame
    if not all_records:
        return pd.DataFrame()
    
    df = pd.DataFrame([r.model_dump() for r in all_records])
    return df
```

## 四、关键算法

### 4.1 日期计算

```python
def _calc_start_date(self, end_date: str, days: int) -> str:
    """
    计算开始日期，考虑周末
    实际加载: days * 2 天以确保覆盖
    """
    end_dt = datetime.strptime(end_date, "%Y%m%d")
    start_dt = end_dt - timedelta(days=days * 2)
    return start_dt.strftime("%Y%m%d")

def _next_date(self, date_str: str) -> str:
    """获取下一个日历日期"""
    dt = datetime.strptime(date_str, "%Y%m%d")
    dt += timedelta(days=1)
    return dt.strftime("%Y%m%d")
```

### 4.2 数据库加载（抽取私有方法）

```python
async def _load_from_db(self, start_date: str, end_date: str, ts_codes: List[str]) -> List[StockDailyRecord]:
    """从数据库加载指定时间范围的数据"""
    records = await StockDaily.find(
        StockDaily.trade_date >= start_date,
        StockDaily.trade_date <= end_date,
        In(StockDaily.ts_code, ts_codes),
    ).sort(StockDaily.ts_code, StockDaily.trade_date).to_list()
    return records
```

## 五、影响范围

### 5.1 需要修改的文件

- `backend/src/trade_alpha/execution/data_loader.py`: 主要修改文件

### 5.2 不需要修改的文件

- Predictor: 完全透明，无需改动
- ExecutionPipeline: 完全透明，无需改动
- 其他所有文件: 不受影响

## 六、性能预期

### 6.1 回测场景

**优化前**:
- 每天查询: 3000只 × 20天 = 60,000条记录
- 100天回测: 6,000,000条数据库记录

**优化后**:
- 第1天查询: 3000只 × 40天 = 120,000条记录
- 后续99天: 3000只 × 1天 = 3,000条记录
- 总计: **123,000条记录**（减少98%）

### 6.2 实盘场景

类似优化，每天只需加载当天数据。

## 七、风险评估

| 风险 | 影响 | 缓解措施 |
|-----|------|---------|
| DataLoader 变为有状态 | 低 | 每个 ExecutionPipeline 实例有自己的 DataLoader，隔离良好 |
| 内存占用 | 中 | 滑动窗口策略，只保留 2×days 数据 |
| 多个实例缓存不共享 | 低 | 正常设计，符合预期 |

## 八、测试计划

1. 单元测试: 验证缓存逻辑正确性
2. 集成测试: 完整回测验证
3. 性能对比: 优化前后速度对比

## 九、设计验证

### YAGNI 检查

- ✅ 只优化 LSTM，不影响 XGBoost
- ✅ 缓存策略基于实际需求（滑动窗口）
- ✅ 内存清理策略必要且合理

### 职责边界检查

- ✅ DataLoader 负责数据加载和缓存（单一职责）
- ✅ Predictor 完全透明
- ✅ ExecutionPipeline 完全透明
