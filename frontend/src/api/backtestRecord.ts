import api from './index'

export interface Backtest {
  id: string
  name: string
  strategy_id: string
  training_id: string
  ts_codes: Array<{ ts_code: string; ts_name: string }>
  ts_code?: string
  ts_name?: string
  start_date: string
  end_date: string
  initial_capital: number
  final_value: number
  total_return: number
  annual_return: number
  benchmark_return: number
  max_drawdown: number
  sharpe_ratio: number
  win_rate: number
  total_trades: number
  total_fees: number
  volatility?: number
  baseline_return?: number
  excess_return?: number
  baseline_max_drawdown?: number
  avg_hold_days?: number
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
}

export interface PredictionItem {
  trade_date: string
  score: number
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
    api.get<{ items: { trade_date: string; action: string; filled_price: number; order_price: number; status: string }[] }>(
      `/backtests/${id}/trades/${tsCode}`
    ),

  getDailySnapshots: (id: string) =>
    api.get<{ items: DailySnapshot[] }>(`/backtests/${id}/daily-snapshots`),

  delete: (id: string) => api.delete(`/backtests/${id}`),
}
