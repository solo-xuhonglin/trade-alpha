import api from './index'

export interface TaskStatusResponse {
  task_id: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress_message?: string
  error_message?: string
  created_at: string
  started_at?: string
  completed_at?: string
}

export interface TaskListResponse {
  items: {
    task_id: string
    status: string
    progress_message?: string
    error_message?: string
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
    range_n?: number
    momentum_n?: number
    strategy_config_id?: string
  }) => api.post<{ task_id: string; status: string; message: string }>('/backtest/run', data),

  getTask: (task_id: string) => api.get<TaskStatusResponse>(`/backtest/task/${task_id}`),

  stopTask: (task_id: string, force = false) => api.post(`/backtest/task/${task_id}/stop?force=${force}`),

  deleteTask: (task_id: string) => api.delete(`/backtest/task/${task_id}`),

  listTasks: (page?: number, pageSize?: number, status?: string) => {
    const params: Record<string, any> = {}
    if (page) params.page = page
    if (pageSize) params.page_size = pageSize
    if (status) params.status = status
    return api.get<TaskListResponse>('/backtest/tasks', { params })
  },
}
