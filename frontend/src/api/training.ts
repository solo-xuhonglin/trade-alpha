import api from './index'

export interface TrainingTaskStatus {
  task_id: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress: number
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
    progress: number
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

export const trainingApi = {
  create: (data: {
    config_id: string
    name: string
    start_rank: number
    end_rank: number
    start_date: string
    end_date: string
  }) => api.post<{ task_id: string; status: string; message: string }>('/trainings', null, { params: data }),

  getTask: (task_id: string) => api.get<TrainingTaskStatus>(`/trainings/task/${task_id}`),

  stopTask: (task_id: string, force = false) => api.post(`/trainings/task/${task_id}/stop?force=${force}`),

  deleteTask: (task_id: string) => api.delete(`/trainings/task/${task_id}`),

  listTasks: (page?: number, pageSize?: number, status?: string) => {
    const params: Record<string, any> = {}
    if (page) params.page = page
    if (pageSize) params.page_size = pageSize
    if (status) params.status = status
    return api.get<TaskListResponse>('/trainings/tasks', { params })
  },
}
