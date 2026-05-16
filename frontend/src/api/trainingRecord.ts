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

export const trainingRecordApi = {
  list: (configId?: string) => {
    const params = configId ? { config_id: configId } : {}
    return api.get<Training[]>('/trainings', { params })
  },

  get: (id: string) => api.get<Training>(`/trainings/${id}`),

  delete: (id: string) => api.delete(`/trainings/${id}`),

  predict: (id: string, tsCode?: string) => {
    const data = tsCode ? { ts_code: tsCode } : {}
    return api.post<PredictResult>(`/trainings/${id}/predict`, data)
  },
}
