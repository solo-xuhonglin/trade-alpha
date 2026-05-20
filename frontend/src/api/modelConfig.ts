import api from './index'

export interface ModelConfig {
  id: string
  name: string
  model_type: string
  feature_fields: string[]
  standardize_fields: string[]
  winsorize_fields: string[]
  classification_horizons: number[]
  classification_threshold: number
  xgb_n_estimators: number
  xgb_max_depth: number
  xgb_learning_rate: number
  xgb_min_child_weight: number
  xgb_subsample: number
  xgb_colsample_bytree: number
  created_at?: string
  updated_at?: string
}

export const modelConfigApi = {
  list: (modelType?: string) => {
    const params = modelType ? { model_type: modelType } : {}
    return api.get<ModelConfig[]>('/model-configs', { params })
  },
  get: (id: string) => api.get<ModelConfig>(`/model-configs/${id}`),
  create: (data: Partial<ModelConfig>) => api.post<ModelConfig>('/model-configs', data),
  update: (id: string, data: Partial<ModelConfig>) => api.put(`/model-configs/${id}`, data),
  delete: (id: string) => api.delete(`/model-configs/${id}`),
}
