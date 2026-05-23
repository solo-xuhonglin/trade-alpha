import api from './index'
import type { AnalysisResult } from './dataAnalysis'

export interface TrainingMetrics {
  sample_count: number
  accuracy?: Record<string, number>
  final_train_loss?: number
  loss_per_epoch?: number[]
  val_loss_per_epoch?: number[]
  feature_importance?: Record<string, Record<string, number>>
  class_distribution?: Record<string, Record<string, number>>
  actual_epochs?: number
  early_stopped?: boolean
  best_epoch?: number
}

export interface Training {
  id: string
  config_id: string
  name: string
  model_type?: string
  ts_codes: string[]
  start_date: string
  end_date: string
  sample_count?: number
  accuracy_3d?: number
  created_at: string
}

export interface TrainingDetail extends Training {
  model_type?: string
  model_metrics: TrainingMetrics
  normalized_data_analysis: AnalysisResult | null
}

export const trainingRecordApi = {
  list: (configId?: string) => {
    const params = configId ? { config_id: configId } : {}
    return api.get<Training[]>('/trainings', { params })
  },

  get: (id: string) => api.get<TrainingDetail>(`/trainings/${id}`),

  delete: (id: string) => api.delete(`/trainings/${id}`),
}
