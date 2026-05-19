import api from './index'

export interface Training {
  id: string
  config_id: string
  name: string
  ts_codes: string[]
  start_date: string
  end_date: string
  metrics: {
    sample_count: number
    accuracy?: Record<string, number>
    cv_mean?: Record<string, number>
    cv_std?: Record<string, number>
    cv_scores?: Record<string, number[]>
    feature_importance?: Record<string, Record<string, number>>
    class_distribution?: Record<string, Record<string, number>>
  }
}

export const trainingRecordApi = {
  list: (configId?: string) => {
    const params = configId ? { config_id: configId } : {}
    return api.get<Training[]>('/trainings', { params })
  },

  get: (id: string) => api.get<Training>(`/trainings/${id}`),

  delete: (id: string) => api.delete(`/trainings/${id}`),
}
