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

export interface TaskStatusResponse {
  task_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  result?: Backtest
  error_message?: string
  created_at: string
  started_at?: string
  completed_at?: string
}

export interface TaskListResponse {
  items: {
    task_id: string
    status: string
    progress: number
    created_at: string
    completed_at?: string
  }[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export const backtestApi = {
  run: (data: {
    account_config_id: string
    training_id: string
    start_date: string
    end_date: string
    name?: string
    mode?: string
    ts_codes?: string[]
    max_positions?: number
    top_n?: number
  }) => api.post<{ task_id: string; status: string; message: string }>('/backtest/run', data),

  getTask: (task_id: string) => api.get<TaskStatusResponse>(`/backtest/task/${task_id}`),

  cancelTask: (task_id: string) => api.delete(`/backtest/task/${task_id}`),

  listTasks: (page?: number, pageSize?: number, status?: string) => {
    const params: Record<string, any> = {}
    if (page) params.page = page
    if (pageSize) params.page_size = pageSize
    if (status) params.status = status
    return api.get<TaskListResponse>('/backtest/tasks', { params })
  },

  get: (id: string) => api.get<Backtest>(`/backtest/results/${id}`),

  list: (page: number = 1, pageSize: number = 20) =>
    api.get<BacktestListResponse>('/backtests', { params: { page, page_size: pageSize } }),

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