import api from './index'

export interface Trade {
  trade_date: string
  action: string
  price: number
  shares: number
  fee: number
  cash_after: number
  position_after: number
  status: string
  ts_code?: string
  ts_name?: string
  reason?: string
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
  trainings: Array<{ id: string; name: string }>
  ts_codes: Array<{ code: string; name: string }>
  backtests: Array<{ id: string; name: string }>
  model_types: string[]
}

export interface TradeFilterParams {
  account_config_id?: string
  backtest_id?: string
  training_id?: string
  ts_code?: string
}

export const tradeApi = {
  list: (page: number = 1, pageSize: number = 20, filters?: TradeFilterParams) => {
    const params: Record<string, any> = { page, page_size: pageSize }
    if (filters?.account_config_id) params.account_config_id = filters.account_config_id
    if (filters?.backtest_id) params.backtest_id = filters.backtest_id
    if (filters?.training_id) params.training_id = filters.training_id
    if (filters?.ts_code) params.ts_code = filters.ts_code
    return api.get<TradeListResponse>('/backtests/trades', { params })
  },

  getOptions: () => api.get<TradeFilterOptions>('/backtests/trades/options'),
}
