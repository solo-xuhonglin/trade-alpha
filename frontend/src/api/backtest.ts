import api from './index'

export interface Backtest {
  id: string
  ptrldol?o string
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

export interface TradeFilterOptions {
  account_configs: Array<{ id: string; name: string }>
  strategies: Array<{ id: string; name: string }>
  trainings: Array<{ id: string; name: string }>
  ts_codes: string[]
}

export interface TradeFilterParams {
  account_config_id?: string
  strategy_id?: string
  training_id?: string
  ts_code?: string
}

export const backtestApi = {
  list: (page: number = 1, pageSize: number = 20) =>
    api.get<BacktestListResponse>('/backtests', { params: { page, page_size: pageSize } }),

  get: (id: string) => api.get<Backtest>(`/backtests/${id}`),

  run: (data: {
    ts_code: string
    start_date: string
    end_date: string
    portfolio_id: string
    strategy_id: string
    training_id: string
  }) => api.post<Backtest>('/backtests', data),

  getTrades: (id: string, page: number = 1, pageSize: number = 20) =>
    api.get<TradeListResponse>(`/backtests/${id}/trades`, { params: { page, page_size: pageSize } }),

  listTrades: (page: number = 1, pageSize: number = 20, filters?: TradeFilterParams) => {
    const params: Record<string, any> = { page, page_size: pageSize }
    if (filters?.account_config_id) params.account_config_id = filters.account_config_id
    if (filters?.strategy_id) params.strategy_id = filters.strategy_id
    if (filters?.training_id) params.training_id = filters.training_id
    if (filters?.ts_code) params.ts_code = filters.ts_code
    return api.get<TradeListResponse>('/backtests/trades', { params })
  },

  getTradeOptions: () => api.get<TradeFilterOptions>('/backtests/trades/options'),

  delete: (id: string) => api.delete(`/backtests/${id}`),
}
