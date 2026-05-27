# 周线数据特征融合 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从 Tushare 拉取周线数据独立存储到 `stock_weekly` 集合，计算全套技术指标，在训练/回测时与日线特征合并。

**Architecture:** 新建 `stock_weekly` DAO 模型 → 拉取周线 OHLCV（`freq="W"`）→ 复用指标计算函数 → 新增 `merge_weekly_features()` 在训练/回测数据加载阶段将上周周线字段作为 `_w` 后缀特征合并到日线 DataFrame。前端在 `featureFields.ts` 中用自动生成方式添加周线字段供模型配置勾选。

**Tech Stack:** Python 3.14+, Beanie/MongoDB, Tushare, pandas, FastAPI, Vue 3 + TypeScript

**避免重复的原则:**
- indicators/service.py: 将计算+更新逻辑提取为通用 `_calculate_indicators_for_model(model_class, ts_code)`，日线和周线共用
- 前端 featureFields.ts: 用 `INDICATOR_FIELDS.map(f => f + '_w')` 自动生成周线字段列表，不手动列出

---

### Task 1: 创建 StockWeekly DAO 模型

**Files:**
- Create: `backend/src/trade_alpha/dao/stock_weekly.py`
- Modify: `backend/src/trade_alpha/dao/__init__.py`

- [ ] **Step 1: 创建 DAO 文件**

```python
"""StockWeekly Document model."""

import math
from typing import Optional
from pydantic import Field, model_validator
from beanie import Document


class StockWeekly(Document):
    """Stock weekly data document for MongoDB."""

    @model_validator(mode="before")
    @classmethod
    def nan_to_none(cls, data):
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, float) and math.isnan(v):
                    data[k] = None
        return data
    
    ts_code: str
    trade_date: str
    open: float
    high: float
    low: float
    close: float
    vol: float
    amount: float

    ma_5: Optional[float] = None
    ma_10: Optional[float] = None
    ma_20: Optional[float] = None
    ma_40: Optional[float] = None
    ma_60: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    pct_chg: Optional[float] = None
    bias_5: Optional[float] = None
    bias_10: Optional[float] = None
    bias_20: Optional[float] = None
    bias_60: Optional[float] = None
    close_position_5: Optional[float] = None
    close_position_10: Optional[float] = None
    close_position_20: Optional[float] = None
    close_position_60: Optional[float] = None
    vol_ratio_5: Optional[float] = None
    vol_ratio_10: Optional[float] = None
    vol_ratio_20: Optional[float] = None
    vol_ratio_60: Optional[float] = None
    kdj_k: Optional[float] = None
    kdj_d: Optional[float] = None
    kdj_j: Optional[float] = None
    boll_upper: Optional[float] = None
    boll_middle: Optional[float] = None
    boll_lower: Optional[float] = None
    boll_position: Optional[float] = None
    rsi_6: Optional[float] = None
    rsi_12: Optional[float] = None
    trend_arrangement_5: Optional[float] = None
    trend_arrangement_10: Optional[float] = None
    trend_arrangement_20: Optional[float] = None
    trend_slope_5: Optional[float] = None
    trend_slope_10: Optional[float] = None
    trend_slope_20: Optional[float] = None
    trend_volume_5: Optional[float] = None
    trend_volume_10: Optional[float] = None
    trend_volume_20: Optional[float] = None
    trend_stability_5: Optional[float] = None
    trend_stability_10: Optional[float] = None
    trend_stability_20: Optional[float] = None
    obv: Optional[float] = None
    obv_chg_5: Optional[float] = None
    obv_chg_10: Optional[float] = None
    obv_chg_20: Optional[float] = None
    candle_body_pct: Optional[float] = None
    candle_upper_pct: Optional[float] = None
    candle_lower_pct: Optional[float] = None
    close_location_pct: Optional[float] = None
    gap_pct: Optional[float] = None
    gap_fill_pct: Optional[float] = None

    class Settings:
        name = "stock_weekly"
        indexes = [
            [("ts_code", 1), ("trade_date", -1)],
        ]
```

- [ ] **Step 2: 在 dao/__init__.py 中导出 StockWeekly**

在 `backend/src/trade_alpha/dao/__init__.py` 中添加 `from trade_alpha.dao.stock_weekly import StockWeekly` 到导出列表。

- [ ] **Step 3: 验证导入**

Run: `cd backend && python -c "from trade_alpha.dao.stock_weekly import StockWeekly; print('OK')"`
Expected: `OK`

---

### Task 2: 添加周线数据获取函数到 fetcher.py

**Files:**
- Modify: `backend/src/trade_alpha/data/fetcher.py`

- [ ] **Step 1: 添加 fetch_stock_weekly_data 函数**

在 `fetch_stock_data` 函数之后新增：

```python
def fetch_stock_weekly_data(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame | None:
    """Fetch stock weekly data from Tushare."""
    api = get_pro_api()
    df = ts.pro_bar(
        api=api,
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        adj="qfq",
        freq="W"
    )
    if df is None or df.empty:
        return None
    return df.sort_values("trade_date")
```

- [ ] **Step 2: 验证导入**

Run: `cd backend && python -c "from trade_alpha.data.fetcher import fetch_stock_weekly_data; print('OK')"`
Expected: `OK`

---

### Task 3: 添加周线数据存储/查询/删除服务函数

**Files:**
- Modify: `backend/src/trade_alpha/data/service.py`

- [ ] **Step 1: 导入 StockWeekly 和 fetcher 函数**

```python
from trade_alpha.dao.stock_weekly import StockWeekly
```

`fetch_stock_weekly_data` 已经在 import 中通过 `from trade_alpha.data.fetcher import ...` 引入，不需要额外导入。

- [ ] **Step 2: 添加 fetch_and_store_stock_weekly + 查询/删除函数**

在现有 `fetch_and_store_stock_daily` 函数下方追加：

```python
async def fetch_and_store_stock_weekly(ts_code: str, start_date: str, end_date: str) -> int:
    """Fetch weekly data from Tushare and store to MongoDB."""
    logger.info(f"Fetching weekly data for {ts_code} from {start_date} to {end_date}")
    df = fetch_stock_weekly_data(ts_code, start_date, end_date)
    if df is None or df.empty:
        logger.warning(f"No weekly data fetched for {ts_code}")
        return 0

    records = df.to_dict("records")
    for record in records:
        record["trade_date"] = str(record["trade_date"])

    REQUIRED_FIELDS = ["open", "high", "low", "close", "vol", "amount"]
    records = [r for r in records if all(r.get(f) is not None for f in REQUIRED_FIELDS)]

    existing = await StockWeekly.find(StockWeekly.ts_code == ts_code).to_list()
    existing_dates = {r.trade_date for r in existing}
    new_records = [r for r in records if r["trade_date"] not in existing_dates]

    if new_records:
        await StockWeekly.insert_many([StockWeekly(**r) for r in new_records])

    return len(new_records)


async def find_stock_weekly_by_ts_code(
    ts_code: str,
    start_date: str = None,
    end_date: str = None,
) -> list[StockWeekly]:
    """Find stock weekly records by ts_code with optional date filter."""
    conditions = [StockWeekly.ts_code == ts_code]
    if start_date:
        conditions.append(StockWeekly.trade_date >= start_date)
    if end_date:
        conditions.append(StockWeekly.trade_date <= end_date)
    query = StockWeekly.find(*conditions)
    return await query.sort(StockWeekly.trade_date).to_list()


async def delete_stock_weekly_by_ts_code(ts_code: str) -> int:
    """Delete stock weekly records by ts_code."""
    result = await StockWeekly.find(StockWeekly.ts_code == ts_code).delete()
    return result.deleted_count
```

- [ ] **Step 3: 验证导入**

Run: `cd backend && python -c "from trade_alpha.data.service import fetch_and_store_stock_weekly, find_stock_weekly_by_ts_code, delete_stock_weekly_by_ts_code; print('OK')"`
Expected: `OK`

---

### Task 4: 重构指标计算 — 提取通用函数，添加周线版本

**Files:**
- Modify: `backend/src/trade_alpha/indicators/service.py`

- [ ] **Step 1: 导入 StockWeekly**

在顶部添加 `from trade_alpha.dao.stock_weekly import StockWeekly`

- [ ] **Step 2: 将通用计算+更新逻辑提取为内部函数**

在文件末尾新增通用函数和 `calculate_all_indicators_weekly`，日线的 `calculate_all_indicators` 和 `calculate_and_store_ma` 等保持原样不变：

```python
ALL_INDICATOR_FIELDS = [
    "ma_5", "ma_10", "ma_20", "ma_40", "ma_60",
    "macd", "macd_signal", "macd_hist",
    "pct_chg",
    "bias_5", "bias_10", "bias_20", "bias_60",
    "close_position_5", "close_position_10", "close_position_20", "close_position_60",
    "vol_ratio_5", "vol_ratio_10", "vol_ratio_20", "vol_ratio_60",
    "kdj_k", "kdj_d", "kdj_j",
    "boll_upper", "boll_middle", "boll_lower", "boll_position",
    "rsi_6", "rsi_12",
    "trend_arrangement_5", "trend_arrangement_10", "trend_arrangement_20",
    "trend_slope_5", "trend_slope_10", "trend_slope_20",
    "trend_volume_5", "trend_volume_10", "trend_volume_20",
    "trend_stability_5", "trend_stability_10", "trend_stability_20",
    "obv", "obv_chg_5", "obv_chg_10", "obv_chg_20",
    "candle_body_pct", "candle_upper_pct", "candle_lower_pct",
    "close_location_pct", "gap_pct", "gap_fill_pct",
]


async def _calculate_and_store_indicators(ts_code: str, model_class, document_name: str) -> int:
    """Generic indicator calculation for any model class (StockDaily or StockWeekly).

    Reads records from model_class, computes all indicators, writes back.
    """
    records = await model_class.find(model_class.ts_code == ts_code).to_list()
    if not records:
        logger.warning(f"No data found for {ts_code} in {document_name}")
        return 0

    df = pd.DataFrame([r.model_dump() for r in records])
    df = df.sort_values("trade_date").reset_index(drop=True)

    df = calculate_ma(df, periods=[5, 10, 20, 40, 60])
    df = calculate_macd(df)
    df = calculate_pct_chg(df)
    df = calculate_bias(df, periods=[5, 10, 20, 60])
    df = calculate_close_position(df)
    df = calculate_vol_ratio(df)
    df = calculate_kdj(df)
    df = calculate_boll(df)
    df = calculate_rsi(df)
    df = calculate_atr(df)
    df = calculate_obv(df)

    prev_close_series = df["close"].shift(1)
    df = calculate_candle_features(df, prev_close_series)
    df = calculate_trend(df)

    updated_count = 0
    for _, row in df.iterrows():
        update_data = {}
        for f in ALL_INDICATOR_FIELDS:
            if f in row and pd.notna(row[f]):
                update_data[f] = row[f]
        if update_data:
            await model_class.find_one(
                model_class.ts_code == ts_code,
                model_class.trade_date == row["trade_date"]
            ).update({"$set": update_data})
            updated_count += 1

    logger.info(f"Calculated indicators for {ts_code} in {document_name}: {updated_count} records")
    return updated_count


async def calculate_all_indicators_weekly(ts_code: str) -> int:
    """Calculate all indicators for weekly data using the stock_weekly collection."""
    return await _calculate_and_store_indicators(ts_code, StockWeekly, "stock_weekly")
```

- [ ] **Step 3: 验证导入**

Run: `cd backend && python -c "from trade_alpha.indicators.service import calculate_all_indicators_weekly; print('OK')"`
Expected: `OK`

---

### Task 5: 更新数据同步流程

**Files:**
- Modify: `backend/src/trade_alpha/scheduler/data_sync.py`

- [ ] **Step 1: 更新导入**

```python
from trade_alpha.data.service import (
    fetch_and_store_stock_daily,
    fetch_and_store_stock_weekly,
    fetch_and_store_stock_list,
    update_stock_data_count,
)
from trade_alpha.indicators.service import (
    calculate_all_indicators,
    calculate_all_indicators_weekly,
)
```

- [ ] **Step 2: 更新 process_single_stock**

```python
async def process_single_stock(stock: StockList) -> bool:
    try:
        start_date, end_date = get_data_period()

        count = await fetch_and_store_stock_daily(stock.ts_code, start_date, end_date)
        logger.info(f"Fetched {count} daily records for {stock.ts_code}")
        await asyncio.sleep(API_REQUEST_DELAY)
        await calculate_all_indicators(stock.ts_code)
        logger.info(f"Completed daily indicators for {stock.ts_code}")

        weekly_count = await fetch_and_store_stock_weekly(stock.ts_code, start_date, end_date)
        logger.info(f"Fetched {weekly_count} weekly records for {stock.ts_code}")
        await asyncio.sleep(API_REQUEST_DELAY)
        await calculate_all_indicators_weekly(stock.ts_code)
        logger.info(f"Completed weekly indicators for {stock.ts_code}")

        stock.sync_status = "active"
        await stock.save()
        await update_single_stock_data_count(stock.ts_code)
        return True
    except Exception as e:
        logger.error(f"Failed to process {stock.ts_code}: {e}")
        return False
```

---

### Task 6: 添加周线特征合并函数

**Files:**
- Create: `backend/src/trade_alpha/data/weekly_merger.py`

- [ ] **Step 1: 创建合并函数文件**

```python
"""Weekly feature merger for training and backtest data loading."""

import pandas as pd
from typing import List, Optional
from trade_alpha.dao.stock_weekly import StockWeekly


async def load_weekly_data(
    ts_codes: List[str],
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Load weekly data for the given stocks and date range."""
    records = await StockWeekly.find(
        StockWeekly.trade_date >= start_date,
        StockWeekly.trade_date <= end_date,
    ).sort(StockWeekly.trade_date).to_list()

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame([r.model_dump() for r in records])
    df = df[df["ts_code"].isin(ts_codes)]
    return df


def merge_weekly_features(
    daily_df: pd.DataFrame,
    weekly_df: pd.DataFrame,
) -> pd.DataFrame:
    """Merge previous week's weekly features into daily dataframe.

    For each daily row, finds the previous Friday's weekly data
    and appends it as _w suffixed columns.
    """
    if weekly_df.empty:
        return daily_df.copy()

    daily = daily_df.copy()
    daily_dt = pd.to_datetime(daily["trade_date"], format="%Y%m%d")
    # 上一周周五 = dayofweek(0=Mon), +3天到上周五
    last_friday = daily_dt - pd.to_timedelta(daily_dt.dt.dayofweek + 3, unit="D")
    daily["_week_key"] = last_friday.dt.strftime("%Y%m%d")

    weekly = weekly_df.copy()
    weekly["_week_key"] = weekly["trade_date"]

    weekly_fields = [c for c in weekly.columns if c not in ["ts_code", "trade_date", "_week_key"]]
    weekly_renamed = {f: f"{f}_w" for f in weekly_fields}
    weekly = weekly.rename(columns=weekly_renamed)

    merge_cols = ["ts_code", "_week_key"] + list(weekly_renamed.values())

    merged = daily.merge(
        weekly[merge_cols],
        on=["ts_code", "_week_key"],
        how="left",
    )
    merged = merged.drop(columns=["_week_key"])
    return merged
```

- [ ] **Step 2: 验证导入**

Run: `cd backend && python -c "from trade_alpha.data.weekly_merger import merge_weekly_features, load_weekly_data; print('OK')"`
Expected: `OK`

---

### Task 7: 训练数据加载中合并周线特征

**Files:**
- Modify: `backend/src/trade_alpha/models/training/helpers.py`

- [ ] **Step 1: 导入周线合并函数**

在顶部添加 `from trade_alpha.data.weekly_merger import merge_weekly_features, load_weekly_data`

- [ ] **Step 2: 更新 _load_year_data**

在 `pd.concat(year_dfs, ignore_index=True)` 之后添加：

```python
    # 合并周线特征
    weekly_start = str(year - 1) + "0101"  # 往前多加载一年确保有上周数据
    weekly_df = await load_weekly_data(ts_codes, weekly_start, future_end)
    if not weekly_df.empty:
        result_df = merge_weekly_features(result_df, weekly_df)
```

- [ ] **Step 3: 验证导入**

Run: `cd backend && python -c "from trade_alpha.models.training.helpers import _load_year_data; print('OK')"`
Expected: `OK`

---

### Task 8: 回测数据加载中合并周线特征

**Files:**
- Modify: `backend/src/trade_alpha/execution/data_loader.py`

- [ ] **Step 1: 导入周线合并函数**

```python
from trade_alpha.data.weekly_merger import merge_weekly_features, load_weekly_data
```

- [ ] **Step 2: 更新 load_day_data**

在返回 `df` 之前添加：

```python
    # 合并周线特征
    weekly_df = await load_weekly_data(ts_codes, date[:4] + "0101", date)
    if not weekly_df.empty:
        df = merge_weekly_features(df, weekly_df)
```

- [ ] **Step 3: 更新 load_history_data**

在返回 `df` 之前添加：

```python
    # 合并周线特征
    load_start = self._calc_start_date(end_date, keep_days)
    weekly_df = await load_weekly_data(ts_codes, load_start, end_date)
    if not weekly_df.empty:
        df = merge_weekly_features(df, weekly_df)
```

- [ ] **Step 4: 验证导入**

Run: `cd backend && python -c "from trade_alpha.execution.data_loader import DataLoader; print('OK')"`
Expected: `OK`

---

### Task 9: 添加后端 API 接口

**Files:**
- Modify: `backend/src/trade_alpha/api/routers/data.py`

- [ ] **Step 1: 更新导入**

```python
from trade_alpha.data.service import (
    fetch_and_store,
    fetch_and_store_stock_weekly,
    update_stock_list,
    list_stocks,
    list_stocks_by_mv_rank,
    find_stock_daily_by_ts_code,
    find_stock_weekly_by_ts_code,
    find_stock_daily_paginated,
    delete_stock_daily_by_ts_code,
    delete_stock_weekly_by_ts_code,
)
from trade_alpha.indicators.service import (
    calculate_all_indicators,
    calculate_all_indicators_weekly,
)
```

- [ ] **Step 2: 添加三个周线接口**

```python
@router.get("/{ts_code}/weekly")
async def get_weekly_data(
    ts_code: str,
    start_date: TradeDateQuery = None,
    end_date: TradeDateQuery = None,
):
    """Get stock weekly data by date range."""
    records = await find_stock_weekly_by_ts_code(
        ts_code,
        to_db_format(start_date) if start_date else None,
        to_db_format(end_date) if end_date else None,
    )
    return records


@router.post("/weekly")
async def fetch_weekly_data_endpoint(request: DataFetchRequest):
    """Fetch and store weekly data, then calculate indicators."""
    count = await fetch_and_store_stock_weekly(
        ts_code=request.ts_code,
        start_date=request.start_date,
        end_date=request.end_date,
    )
    if count > 0:
        await calculate_all_indicators_weekly(ts_code=request.ts_code)
    return {"ts_code": request.ts_code, "stored_count": count}


@router.delete("/{ts_code}/weekly")
async def delete_weekly_data_endpoint(ts_code: str):
    """Delete stock weekly data."""
    count = await delete_stock_weekly_by_ts_code(ts_code)
    return {"deleted_count": count}
```

- [ ] **Step 3: 验证 API 路由加载**

Run: `cd backend && python -c "from trade_alpha.api.routers.data import router; print('OK')"`
Expected: `OK`

---

### Task 10: 前端 — 自动生成周线特征字段列表

**Files:**
- Modify: `frontend/src/api/featureFields.ts`

- [ ] **Step 1: 调整文件顺序，添加 WEEKLY_FIELDS**

需要将 `WEEKLY_FIELDS` 定义移到 `ALL_FEATURE_FIELDS` 之前，因为后者引用前者。

```typescript
export const WEEKLY_FIELDS = [
  'open_w', 'high_w', 'low_w', 'close_w', 'vol_w', 'amount_w',
  ...INDICATOR_FIELDS.map(f => f + '_w'),
]

export const ALL_FEATURE_FIELDS = [...DAILY_BASIC_FIELDS, ...INDICATOR_FIELDS, ...WEEKLY_FIELDS]
```

---

### Task 11: 前端 — 添加周线数据 API

**Files:**
- Modify: `frontend/src/api/data.ts`

- [ ] **Step 1: 添加三个周线接口方法**

```typescript
getWeeklyData: (tsCode: string, startDate?: string, endDate?: string) =>
    api.get<DataRecord[]>(`/data/${tsCode}/weekly`, { params: { start_date: startDate, end_date: endDate } }),

fetchWeeklyData: (tsCode: string, startDate: string, endDate: string) =>
    api.post('/data/weekly', { ts_code: tsCode, start_date: startDate, end_date: endDate }),

deleteWeeklyData: (tsCode: string) =>
    api.delete(`/data/${tsCode}/weekly`),
```

---

### Task 12: 集成测试 — 周线数据全流程验证

**Files:**
- Create: `backend/tests/trade_alpha/integration/test_26_weekly_data.py`

- [ ] **Step 1: 创建测试文件**

```python
"""Integration tests for weekly data — fetch, indicators, and feature merging."""

import pytest
import pytest_asyncio
import pandas as pd
from trade_alpha.dao.stock_weekly import StockWeekly
from trade_alpha.data.service import fetch_and_store_stock_weekly
from trade_alpha.indicators.service import calculate_all_indicators_weekly
from trade_alpha.data.weekly_merger import merge_weekly_features
from trade_alpha.test_config import TEST_STOCK

TS_CODE = TEST_STOCK


@pytest.mark.integration
@pytest.mark.order(26)
class TestWeeklyData:
    """Weekly data integration tests."""

    @pytest_asyncio.fixture(autouse=True)
    async def cleanup(self):
        yield
        await StockWeekly.find(StockWeekly.ts_code == TS_CODE).delete()

    @pytest.mark.asyncio
    async def test_fetch_and_store_weekly_data(self):
        """Verify weekly data is fetched from Tushare and stored."""
        start_date, end_date = "20200101", "20251231"
        count = await fetch_and_store_stock_weekly(TS_CODE, start_date, end_date)

        assert count > 0, "No weekly records inserted"

        records = await StockWeekly.find(StockWeekly.ts_code == TS_CODE).sort(StockWeekly.trade_date).to_list()
        assert len(records) == count

        # Verify fields
        for r in records[:3]:
            assert r.open > 0
            assert r.high > 0
            assert r.low > 0
            assert r.close > 0
            assert r.vol > 0

    @pytest.mark.asyncio
    async def test_calculate_weekly_indicators(self):
        """Verify weekly indicators are computed and stored."""
        await fetch_and_store_stock_weekly(TS_CODE, "20200101", "20251231")
        updated = await calculate_all_indicators_weekly(TS_CODE)

        assert updated > 0, "No weekly records updated with indicators"

        records = await StockWeekly.find(StockWeekly.ts_code == TS_CODE).to_list()
        records_with_ma = [r for r in records if r.ma_5 is not None]
        assert len(records_with_ma) > 0, "No records with weekly ma_5"
        assert any(r.macd is not None for r in records)
        assert any(r.rsi_6 is not None for r in records)

    @pytest.mark.asyncio
    async def test_merge_weekly_features(self):
        """Verify merge_weekly_features correctly appends _w fields."""
        # Prepare daily data
        daily_df = pd.DataFrame({
            "ts_code": [TS_CODE, TS_CODE],
            "trade_date": ["20250305", "20250306"],
            "close": [10.0, 10.5],
        })

        # Prepare weekly data (previous Friday = 20250228)
        weekly_df = pd.DataFrame({
            "ts_code": [TS_CODE],
            "trade_date": ["20250228"],
            "close": [9.5],
            "ma_5": [9.3],
            "macd": [0.1],
        })

        merged = merge_weekly_features(daily_df, weekly_df)

        assert "_week_key" not in merged.columns
        assert "close_w" in merged.columns
        assert "ma_5_w" in merged.columns
        assert "macd_w" in merged.columns
        assert merged["close_w"].iloc[0] == 9.5
        assert merged["close_w"].iloc[1] == 9.5
        assert merged["close"].iloc[0] == 10.0
        assert merged["close"].iloc[1] == 10.5

    @pytest.mark.asyncio
    async def test_merge_weekly_features_empty_weekly(self):
        """Verify merge_weekly_features returns daily_df unchanged when weekly is empty."""
        daily_df = pd.DataFrame({
            "ts_code": [TS_CODE],
            "trade_date": ["20250305"],
            "close": [10.0],
        })
        weekly_df = pd.DataFrame()

        merged = merge_weekly_features(daily_df, weekly_df)
        assert list(merged.columns) == ["ts_code", "trade_date", "close"]
        assert merged["close"].iloc[0] == 10.0

    @pytest.mark.asyncio
    async def test_merge_weekly_features_missing_week(self):
        """Verify merge_weekly_features handles missing weekly data (NaNs)."""
        daily_df = pd.DataFrame({
            "ts_code": [TS_CODE],
            "trade_date": ["20200102"],  # First trading day of 2020, no previous week
            "close": [10.0],
        })
        weekly_df = pd.DataFrame()  # No weekly data before 2020

        merged = merge_weekly_features(daily_df, weekly_df)
        assert list(merged.columns) == ["ts_code", "trade_date", "close"]
```

- [ ] **Step 2: 运行测试**

Run: `cd backend && pytest tests/trade_alpha/integration/test_26_weekly_data.py -v`
Expected: 5 个测试全部通过

---

### Task 13: 完整验证

- [ ] **Step 1: 运行全部后端集成测试**

Run: `cd backend && pytest tests/trade_alpha/integration/ -v`
Expected: 所有测试通过（包括新增的 test_26）

- [ ] **Step 2: 运行前端构建**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 3: 提交所有变更**

```bash
git add -A
git commit -m "feat: add weekly data as features merged with daily data"
```
