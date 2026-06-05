import api from './index'
import type { AnalysisResult } from './dataAnalysis'

export interface TrainingMetrics {
  sample_count: number
  accuracy?: Record<string, number>
  auc?: Record<string, number>
  final_train_loss?: number
  loss_per_epoch?: Record<string, number[]>
  val_loss_per_epoch?: Record<string, number[]>
  val_auc_per_epoch?: Record<string, number[]>
  feature_importance?: Record<string, Record<string, number>>
  class_distribution?: Record<string, Record<string, number>>
  actual_epochs?: number
  early_stopped?: boolean
  best_epoch?: Record<string, number>
  best_auc?: Record<string, number>
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
  accuracy_5d?: number
  accuracy_10d?: number
  accuracy_20d?: number
  model_snapshot?: Record<string, any> | null
  created_at: string
}

export interface TrainingDetail extends Training {
  model_type?: string
  model_metrics: TrainingMetrics
  model_snapshot?: Record<string, any> | null
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
