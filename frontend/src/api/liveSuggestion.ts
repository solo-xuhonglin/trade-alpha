import api from './index'

export interface LiveSuggestionRun {
  id: string
  account_config_id: string
  training_id: string
  strategy_config_id: string
  target_date: string
  warmup_start: string
  warmup_days: number
  status: string
  order_count: number
  error_message: string | null
  created_at: string
}

export interface OrderSuggestion {
  id: string
  run_id: string
  ts_code: string
  stock_name: string
  trade_date: string
  settle_date: string
  action: string
  order_price: number
  order_shares: number
  raw_score: number
  composite_score: number
  ranking_score: number
  rank: number
  up_prob_3d: number
  up_prob_5d: number
  up_prob_10d: number
  up_prob_20d: number
  trend_bonus: number
  vol_penalty: number
  momentum_bonus: number
  is_excluded: boolean
  excluded_reason: string | null
  status: string
  reason: string | null
  created_at: string
}

export interface LiveSuggestionRunListResponse {
  items: LiveSuggestionRun[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface SuggestionDateSummary {
  trade_date: string
  total_count: number
  excluded_count: number
}

export interface LiveSuggestion {
  ts_code: string
  stock_name: string
  trade_date: string
  raw_score: number
  composite_score: number
  ranking_score: number
  rank: number
  up_prob_3d: number
  up_prob_5d: number
  up_prob_10d: number
  up_prob_20d: number
  trend_bonus: number
  vol_penalty: number
  momentum_bonus: number
  is_excluded: boolean
  excluded_reason: string | null
  actual_return_3d?: number | null
  actual_return_5d?: number | null
  actual_return_10d?: number | null
  actual_return_20d?: number | null
  reason: string | null
}

export interface LiveSuggestionTaskItem {
  task_id: string
  task_type: string
  status: string
  progress: number
  progress_message?: string
  error_message?: string
  created_at: string
  completed_at?: string
}

export interface LiveSuggestionTaskListResponse {
  items: LiveSuggestionTaskItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface LiveDailyStockScore {
  id: string
  ts_code: string
  stock_name: string | null
  trade_date: string
  rank: number
  composite_score: number
  ranking_score: number
  up_prob_3d: number
  up_prob_5d: number
  up_prob_10d: number
  trend_bonus: number
  vol_penalty: number
  momentum_bonus: number
  order_price: number
  order_shares: number
  is_excluded: boolean
  avg_rank_3d?: number | null
  avg_rank_5d?: number | null
  avg_rank_20d?: number | null
  rank_change?: number | null
  updated_at: string
}

export interface DailyScoresResponse {
  items: LiveDailyStockScore[]
  total: number
  page: number
  page_size: number
  total_pages: number
  trade_date: string
}

export const liveSuggestionApi = {
  trigger: (body: {
    training_id: string
    strategy_config_id: string
    portfolio_id?: string
    start_date?: string
    end_date?: string
    top_n?: number
  }) => api.post<{ task_id: string; status: string; message: string }>('/live-suggestion/run', body),

  listDailyScores: (tradeDate?: string, page: number = 1, pageSize: number = 100) =>
    api.get<DailyScoresResponse>('/live-suggestion/daily-scores', {
      params: { trade_date: tradeDate, page, page_size: pageSize },
    }),

  listStockDailyScores: (tsCode: string) =>
    api.get<{ items: LiveDailyStockScore[]; start_date: string | null; end_date: string | null }>(
      `/live-suggestion/daily-scores/stock/${encodeURIComponent(tsCode)}`
    ),

  listRuns: (page: number = 1, page_size: number = 20) =>
    api.get<LiveSuggestionRunListResponse>('/live-suggestion/runs', { params: { page, page_size } }),

  listSuggestionDates: (page?: number, pageSize?: number) =>
    api.get<{ items: SuggestionDateSummary[]; total: number; page: number; page_size: number; total_pages: number }>(
      '/live-suggestion/suggestion-dates',
      { params: { page, page_size: pageSize } }
    ),

  listSuggestions: (tradeDate: string, page?: number, pageSize?: number) =>
    api.get<{ items: LiveSuggestion[]; total: number; page: number; page_size: number; total_pages: number; trade_date: string }>(
      '/live-suggestion/suggestions',
      { params: { trade_date: tradeDate, page, page_size: pageSize } }
    ),

  listTasks: (page?: number, pageSize?: number, status?: string) => {
    const params: Record<string, any> = {}
    if (page) params.page = page
    if (pageSize) params.page_size = pageSize
    if (status) params.status = status
    return api.get<LiveSuggestionTaskListResponse>('/live-suggestion/tasks', { params })
  },

  getTask: (taskId: string) =>
    api.get<LiveSuggestionTaskItem>(`/live-suggestion/task/${taskId}`),

  stopTask: (taskId: string, force = false) =>
    api.post(`/live-suggestion/task/${taskId}/stop?force=${force}`),

  deleteTask: (taskId: string) =>
    api.delete(`/live-suggestion/task/${taskId}`),
}