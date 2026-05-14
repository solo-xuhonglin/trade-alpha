import api from './index'

export interface Training {
  id: string
  config_id: string
  name: string
  ts_codes: string[]
  start_date: string
  end_date: string
  metrics: {
    open_mse?: number
    open_mae?: number
    close_mse?: number
    close_mae?: number
    high_mse?: number
    high_mae?: number
    low_mse?: number
    low_mae?: number
    sample_count: number
  }
}

export interface PredictResult {
  predictions: Record<string, number>
}

export interface TrainingTaskStatus {
  task_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  training?: Training
  error_message?: string
  created_at: string
  started_at?: string
  completed_at?: string
}

export interface TrainingTaskListResponse {
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

export const trainingsApi = {
  list: (configId?: string) => {
    const params = configId ? { config_id: configId } : {}
    return api.get<Training[]>('/trainings', { params })
  },

  get: (id: string) => api.get<Training>(`/trainings/${id}`),

  create: (data: {
    config_id: string
    name: string
    ts_codes: string[]
    start_date: string
    end_date: string
  }) => api.post<{ task_id: string; status: string; message: string }>('/trainings', data),

  getTask: (task_id: string) => api.get<TrainingTaskStatus>(`/trainings/task/${task_id}`),

  cancelTask: (task_id: string) => api.delete(`/trainings/task/${task_id}`),

  listTasks: (page?: number, pageSize?: number, status?: string) => {
    const params: Record<string, any> = {}
    if (page) params.page = page
    if (pageSize) params.page_size = pageSize
    if (status) params.status = status
    return api.get<TrainingTaskListResponse>('/trainings/tasks', { params })
  },

  delete: (id: string) => api.delete(`/trainings/${id}`),

  predict: (id: string, tsCode?: string) => {
    const data = tsCode ? { ts_code: tsCode } : {}
    return api.post<PredictResult>(`/trainings/${id}/predict`, data)
  },
}