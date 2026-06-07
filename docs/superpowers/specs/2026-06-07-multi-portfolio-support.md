# Multiple Portfolio Support

Date: 2026-06-07

## Overview

Currently there is a single `LivePortfolio` document in the `live_portfolio` collection. This spec adds support for multiple named portfolios, allowing users to create and switch between different portfolios in the UI.

## Changes

### 1. Backend — Live Portfolio Router

#### GET /live-portfolio/options

New endpoint returning all portfolio names and IDs:

```json
{
  "items": [
    {"id": "...", "name": "default"},
    {"id": "...", "name": "test_live_portfolio"}
  ]
}
```

#### GET /live-portfolio/

Add optional `id` query parameter. When provided, return the portfolio with that ID. When omitted, return portfolio with `name="default"` (auto-create if missing).

```python
@router.get("/")
async def get_portfolio(id: Optional[str] = None):
    if id:
        portfolio = await LivePortfolio.get(PydanticObjectId(id))
    else:
        portfolio = await LivePortfolio.find_one(LivePortfolio.name == "default")
        if portfolio is None:
            portfolio = LivePortfolio(name="default", positions=[], ...)
            await portfolio.insert()
    return _portfolio_to_dict(portfolio)
```

#### POST /live-portfolio/

New endpoint to create a named portfolio:

```python
@router.post("/")
async def create_portfolio(name: str):
    existing = await LivePortfolio.find_one(LivePortfolio.name == name)
    if existing:
        raise HTTPException(400, "Portfolio name already exists")
    portfolio = LivePortfolio(name=name, positions=[], ...)
    await portfolio.insert()
    return _portfolio_to_dict(portfolio)
```

All existing position CRUD endpoints (`POST /positions`, `PUT /positions/{id}`, `DELETE /positions/{id}`) add optional `portfolio_id` query parameter to specify which portfolio to operate on. Default to the "default" portfolio when omitted.

### 2. Backend — Live Suggestion Router

#### POST /live-suggestion/run

Add optional `portfolio_id` field to `LiveSuggestionRunRequest`. When provided, pass it to `SuggestionPipeline.run()` as `live_portfolio_id`. The pipeline fetches the portfolio by ID.

```python
class LiveSuggestionRunRequest(BaseModel):
    training_id: str
    strategy_config_id: str
    portfolio_id: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    top_n: int = 100
```

### 3. Backend — SuggestionPipeline

Add `live_portfolio_id: Optional[PydanticObjectId] = None` parameter to `run()`. When provided:
- Fetch portfolio by ID instead of using `live_portfolio` object
- Fallback: use injected `live_portfolio` (for tests)
- Fallback: use `find_one(LivePortfolio.name == "default")`

### 4. Frontend — LivePositionManageView

- Add a dropdown/selector at the top of the page to switch between portfolios
- Load options from `GET /live-portfolio/options`
- Default selection: `"default"`
- On change: reload portfolio data with selected ID
- Add a "新建组合" button that opens a dialog to input portfolio name (calls `POST /live-portfolio/`)

### 5. Frontend — LiveSuggestionManageView

- Add `<v-select>` for portfolio selection after the strategy config field
- Load options from `GET /live-portfolio/options`
- Default: `"default"`
- Pass `portfolio_id` in the trigger request body

### 6. Frontend — API layer

Update `livePortfolio.ts`:

```typescript
export const livePortfolioApi = {
  // New
  listOptions(): Promise<{ data: { items: { id: string; name: string }[] } }> {
    return request.get('/live-portfolio/options')
  },
  createPortfolio(name: string): Promise<{ data: LivePortfolio }> {
    return request.post('/live-portfolio/', { name })
  },
  // Changed: add id param
  getPortfolio(id?: string): Promise<{ data: LivePortfolio }> {
    const params = id ? { id } : {}
    return request.get('/live-portfolio/', { params })
  },
  // Changed: add portfolio_id param
  addPosition(data, portfolioId?: string): Promise<{ data: LivePortfolio }> {
    const params = portfolioId ? { portfolio_id: portfolioId } : {}
    return request.post('/live-portfolio/positions', data, { params })
  },
  // ... same for update/delete
}
```

Update `liveSuggestion.ts` trigger signature:

```typescript
trigger: (body: { training_id: string; strategy_config_id: string; portfolio_id?: string; start_date?: string; end_date?: string; top_n?: number }) =>
  api.post('/live-suggestion/run', body),
```

### 7. Tests — test_46

- `test_ensure_default_live_portfolio`: already creates `test_live_portfolio` (no change)
- CRUD tests: use temp portfolio with unique name (already implemented)

### 8. Tests — test_65

- `test_02`: find `test_live_portfolio` by name, add temp positions, pass `live_portfolio_id` to pipeline via `live_portfolio` object (already implemented)
- All tests use fixed dates 2026-01-05~2026-01-06 (already implemented)

## Migration

Existing production `live_portfolio` documents without a `name` field will have `name=""`. The first time `GET /live-portfolio/` is called without an `id`, it will find the existing unnamed portfolio and return it. No data migration needed.