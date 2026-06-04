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

export interface LiveSuggestionRunDetailResponse {
  run: LiveSuggestionRun
  orders: OrderSuggestion[]
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

export const liveSuggestionApi = {
  trigger: (body: { account_config_id: string; training_id: string; strategy_config_id: string }) =>
    api.post<{ task_id: string; status: string; message: string }>('/live-suggestion/run', body),

  listRuns: (page: number = 1, page_size: number = 20) =>
    api.get<LiveSuggestionRunListResponse>('/live-suggestion/runs', { params: { page, page_size } }),

  getRun: (runId: string) =>
    api.get<LiveSuggestionRunDetailResponse>(`/live-suggestion/runs/${runId}`),

  deleteRun: (runId: string) =>
    api.delete(`/live-suggestion/runs/${runId}`),

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