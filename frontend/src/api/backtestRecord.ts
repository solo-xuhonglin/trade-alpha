import api from './index'

export interface Backtest {
  id: string
  name: string
  strategy_id: string
  training_id: string
  ts_code: string
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
}

export interface Trade {
  trade_date: string
  action: string
  price: number
  shares: number
  fee: number
  cash_after: number
  position_after: number
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

export const backtestRecordApi = {
  get: (id: string) => api.get<Backtest>(`/backtest/results/${id}`),

  list: (page: number = 1, pageSize: number = 20) =>
    api.get<BacktestListResponse>('/backtests', { params: { page, page_size: pageSize } }),

  getTrades: (id: string, page: number = 1, pageSize: number = 20) =>
    api.get<TradeListResponse>(`/backtests/${id}/trades`, { params: { page, page_size: pageSize } }),

  delete: (id: string) => api.delete(`/backtests/${id}`),
}
