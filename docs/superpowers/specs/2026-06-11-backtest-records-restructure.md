# Backtest Records Restructure Design

## Goal

Restructure the backend `backtest_records.py` (985 lines, 14 endpoints) by extracting business logic into `backtest_service.py`, following the same pattern used for `live_suggestion.py`. Delete the unused `HelloWorld.vue` frontend component. The frontend `BacktestRecordsView.vue` (1343 lines) stays intact since its content is all backtest-specific with no reusable patterns.

## Current Problems

### 1. `backtest_records.py` (985 lines) — Mixed concerns

Contains 14 endpoints plus a helper function (`_enrich_future_returns`) in a single file. Each endpoint has inline MongoDB queries, aggregation pipelines, and response serialization mixed together. This is the same pattern as `live_suggestion.py` before it was restructured.

| Endpoint | Lines | Responsibility |
|---|---|---|
| `GET /` | ~62 | List backtest results (pagination + name lookup) |
| `DELETE /{id}` | ~16 | Delete backtest + related trades |
| `GET /{id}/trades` | ~47 | Get trades for a backtest |
| `GET /{id}/trades/{ts_code}` | ~27 | Get trades by stock |
| `GET /{id}/pnl-details` | ~135 | PnL analysis (aggregation + unrealized calc) |
| `GET /{id}/prediction-stocks` | ~58 | Prediction stock rankings |
| `GET /{id}/predictions/{ts_code}` | ~92 | Stock prediction detail + actual returns |
| `GET /{id}/excluded-stocks` | ~50 | Explosion filter stats |
| `GET /{id}/acceleration-excluded` | ~48 | Acceleration filter stats |
| `GET /{id}/forced-sell-stocks` | ~47 | Forced sell records |
| `GET /trades` | ~92 | Global trade list with filters |
| `GET /{id}/daily-snapshots` | ~24 | Equity curve data |
| `GET /{id}/daily-details` | ~95 | Daily positions + trades |
| `GET /trades/options` | ~53 | Filter dropdown options |
| `_enrich_future_returns` | ~50 | Helper (could be in service layer) |

### 2. `HelloWorld.vue` — Dead code

Default Vue scaffold component, never imported or used by any view.

## Design

### File changes

| Action | File | Lines |
|---|---|---|
| **Modify** | `backend/src/trade_alpha/execution/backtest_service.py` | 46 → ~360 |
| **Modify** | `backend/src/trade_alpha/api/routers/backtest_records.py` | 985 → ~120 |
| **Delete** | `frontend/src/components/HelloWorld.vue` | — |

### `backtest_service.py` — New functions

All functions return plain dicts (not HTTP response objects), following the pattern from `suggestion_service.py`:

```python
# Existing (keep):
get_execution_by_name(name) -> Optional[ExecutionResult]
get_execution_by_id(execution_id) -> Optional[ExecutionResult]
list_executions(account_config_id, training_id) -> list[ExecutionResult]
delete_execution_by_name(name) -> bool

# New:
list_backtest_results(page, page_size) -> dict
delete_backtest_result(result_id) -> None
get_backtest_trades(result_id, page, page_size) -> dict
get_trades_by_ts_code(result_id, ts_code) -> dict
get_pnl_details(result_id) -> dict
get_prediction_stocks(result_id) -> dict
get_stock_predictions(result_id, ts_code) -> dict
_enrich_future_returns(items, date_key, horizons) -> None  # private
get_excluded_stocks(result_id) -> dict
get_acceleration_excluded(result_id) -> dict
get_forced_sell_stocks(result_id) -> dict
list_all_trades(page, page_size, filters) -> dict
get_daily_snapshots(result_id) -> dict
get_daily_details(result_id) -> DailyDetailResponse
get_trade_filter_options() -> dict
```

### `backtest_records.py` — Thin pass-through

Each endpoint becomes a ~3-7 line pass-through. Example:

```python
@router.get("/{result_id}/pnl-details")
async def get_pnl_details(result_id: str):
    try:
        obj_id = PydanticObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result ID")
    from trade_alpha.execution.backtest_service import get_pnl_details as svc
    return await svc(obj_id)
```

Imports kept at function level to avoid circular dependencies (same pattern as `live_suggestion.py`).

### Error handling pattern

Validation is kept in the router layer (result_id format, existence check). Business logic errors bubble from service to router as `ValueError` → `HTTPException(400)`.

### `HelloWorld.vue`

Simple deletion. No dependency changes needed since it's never imported.

### Non-goals

- No changes to `backtest.py` (trigger router, 234 lines, kept as-is)
- No changes to `backtest_pipeline.py`
- No changes to frontend `BacktestRecordsView.vue` (1343 lines, kept as-is)
- No changes to tests (service layer functions follow existing patterns)