import api from './index'

export interface Backtest {
  id: string
  name: string
  training_id: string
  ts_codes: Array<{ ts_code: string; ts_name: string }>
  ts_code?: string
  ts_name?: string
  stock_name?: string
  start_date: string
  end_date: string
  initial_capital: number
  final_value: number
  total_return: number
  annual_return: number
  max_drawdown: number
  sharpe_ratio: number
  win_rate: number
  total_trades: number
  total_fees: number
  volatility?: number
  baseline_return?: number
  baseline_annual_return?: number
  baseline_volatility?: number
  baseline_sharpe_ratio?: number
  excess_return?: number
  baseline_max_drawdown?: number
  avg_hold_days?: number
  trade_win_rate?: number
  created_at?: string
}

export interface Trade {
  trade_date: string
  action: string
  filled_price: number
  order_price: number
  shares: number
  fee: number
  cash_after: number
  position_after: number
  status: string
  ts_code?: string
  stock_name?: string
  ts_name?: string
  reason?: string
}

export interface BacktestListResponse {
  items: Backtest[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface BacktestConfigSnapshots {
  id: string
  name: string
  account_snapshot?: {
    name: string
    initial_capital: number
    buy_fee_rate: number
    sell_fee_rate: number
    stamp_tax_rate: number
    min_fee: number
  }
  model_snapshot?: Record<string, any>
  strategy_snapshot?: Record<string, any>
}

export interface TradeListResponse {
  items: Trade[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface PredictionStock {
  ts_code: string
  stock_name: string
  avg_score?: number
  avg_rank?: number
}

export interface PredictionItem {
  trade_date: string
  composite_score: number
  weighted_score?: number
  raw_score?: number
  rank?: number
  momentum_bonus?: number
  trend_bonus?: number
  vol_penalty?: number
  ranking_score?: number
  // 动态字段，根据 horizons 动态生成
  [key: string]: any
}

export interface PredictionResponse {
  ts_code: string
  stock_name: string
  horizons: number[]
  start_date: string
  end_date: string
  items: PredictionItem[]
}

export interface DailySnapshot {
  date: string
  total_value: number
  baseline_value: number
  day_return: number
  ranking_high_pct: number
  ranking_low_pct: number
  market_phase?: string
  daily_rebalanced_cum?: number
  rebalanced_ma10_pct?: number
  rebalanced_ma60_pct?: number
  position_pct?: number
  top_n_retention_rate_smoothed: number
  score_return_corr_smoothed: number
}

export interface PnlDetailItem {
  ts_code: string
  stock_name: string
  realized_pnl: number
  unrealized_pnl: number
  total_pnl: number
  profit_count: number
  loss_count: number
  trade_win_rate: number
}

export interface PnlDetailSummary {
  total_portfolio_pnl: number
  total_realized_pnl: number
  total_profit_trades: number
  total_loss_trades: number
  overall_win_rate: number
}

export interface PnlDetailResponse {
  items: PnlDetailItem[]
  summary: PnlDetailSummary
}

export interface ExcludedStockDate {
  date: string
  price_surge_pct: number
  volume_ratio: number
}

export interface ExcludedStock {
  ts_code: string
  stock_name: string
  excluded_count: number
  excluded_dates: ExcludedStockDate[]
}

export interface DailyPosition {
  ts_code: string
  stock_name: string
  buy_date: string
  buy_price: number
  current_price: number
  shares: number
  fee: number
  cost_basis: number
  market_value: number
  unrealized_pnl: number
  unrealized_pnl_pct: number
  hold_days: number
  entry_score: number
}

export interface DailyTrade {
  ts_code: string
  stock_name: string
  action: string
  filled_price: number
  shares: number
  fee: number
  reason?: string
  pnl_amount?: number
  pnl_pct?: number
}

export interface PlannerCandidate {
  ts_code: string
  stock_name: string
  ranking_score: number
  composite_score: number
  rank: number
  norm_score: number
  norm_prob: number
  norm_ri: number
  norm_rank: number
  final_priority: number
  reason: string
  target_price: number
  cache_days: number
  is_ordered: boolean
}

export interface DailyDetail {
  date: string
  cash: number
  total_market_value: number
  total_value: number
  baseline_value: number
  day_return: number
  cml_return: number
  baseline_cml_return: number
  positions: DailyPosition[]
  trades: DailyTrade[]
  planner_candidates?: PlannerCandidate[]
}

export interface DailyDetailResponse {
  items: DailyDetail[]
  months?: string[]
}

export const backtestRecordApi = {
  get: (id: string) => api.get<Backtest>(`/backtest/results/${id}`),

  list: (page: number = 1, pageSize: number = 20) =>
    api.get<BacktestListResponse>('/backtests', { params: { page, page_size: pageSize } }),

  getTrades: (id: string, page: number = 1, pageSize: number = 20) =>
    api.get<TradeListResponse>(`/backtests/${id}/trades`, { params: { page, page_size: pageSize } }),

  getPredictionStocks: (id: string) =>
    api.get<{ items: PredictionStock[] }>(`/backtests/${id}/prediction-stocks`),

  getPredictions: (id: string, tsCode: string) =>
    api.get<PredictionResponse>(`/backtests/${id}/predictions/${tsCode}`),

  getTradesByTsCode: (id: string, tsCode: string) =>
    api.get<{ items: { trade_date: string; action: string; filled_price: number; order_price: number; status: string; pnl_amount?: number; pnl_pct?: number }[] }>(
      `/backtests/${id}/trades/${tsCode}`
    ),

  getDailySnapshots: (id: string) =>
    api.get<{ items: DailySnapshot[] }>(`/backtests/${id}/daily-snapshots`),

  getConfigSnapshots: (id: string) =>
    api.get<BacktestConfigSnapshots>(`/backtests/${id}/config-snapshots`),

  getPnlDetails: (id: string) =>
    api.get<PnlDetailResponse>(`/backtests/${id}/pnl-details`),

  getExcludedStocks: (id: string) =>
    api.get<{ items: ExcludedStock[] }>(`/backtests/${id}/excluded-stocks`),

  getForcedSellStocks: (id: string) =>
    api.get<{ items: any[] }>(`/backtests/${id}/forced-sell-stocks`),

    getDailyDetails: (id: string, yearMonth?: string) =>
    api.get<DailyDetailResponse>(`/backtests/${id}/daily-details`, {
      params: { year_month: yearMonth }
    }),

  delete: (id: string) => api.delete(`/backtests/${id}`),
}
