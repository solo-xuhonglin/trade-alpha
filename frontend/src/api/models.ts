import api from './index'

export interface ModelConfig {
  id: string
  name: string
  model_type: 'linear' | 'xgboost' | 'lstm'
  params: Record<string, any>
  targets: string[]
}

export const modelsApi = {
  list: (modelType?: string) => {
    const params = modelType ? { model_type: modelType } : {}
    return api.get<ModelConfig[]>('/model-configs', { params })
  },
  get: (id: string) => api.get<ModelConfig>(`/model-configs/${id}`),
  create: (data: Partial<ModelConfig>) => api.post<ModelConfig>('/model-configs', data),
  update: (id: string, data: Partial<ModelConfig>) => api.put(`/model-configs/${id}`, data),
  delete: (id: string) => api.delete(`/model-configs/${id}`),
}
