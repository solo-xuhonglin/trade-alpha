import api from './index'

export interface Backtest {
  id: string
  portfolio_id?: string
  ts_code: string
  start_date: string
  end_date: string
  strategy: string
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

export const backtestApi = {
  list: (limit?: number) => api.get<Backtest[]>('/backtests', { params: { limit } }),
  get: (id: string) => api.get<Backtest>(`/backtests/${id}`),
  run: (data: { ts_code: string; start_date: string; end_date: string; strategy_id: string; portfolio_name?: string; initial_capital?: number }) =>
    api.post<Backtest>('/backtests', data),
  getTrades: (id: string) => api.get<Trade[]>(`/backtests/${id}/trades`),
  delete: (id: string) => api.delete(`/backtests/${id}`),
}
