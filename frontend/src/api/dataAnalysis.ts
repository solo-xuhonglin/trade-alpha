import { INDICATOR_FIELDS } from './featureFields'
import api from './index'

export interface FieldStatistics {
  mean: number
  std: number
  median: number
  q1: number
  q3: number
  min: number
  max: number
  missing_rate: number
  outlier_rate: number
}

export interface HistogramData {
  bins: number[]
  counts: number[]
}

export interface BoxPlotData {
  min: number
  q1: number
  median: number
  q3: number
  max: number
  outliers: number[]
}

export interface MissingDataInfo {
  total: number
  missing: number
  rate: number
}

export interface AnalysisResult {
  statistics: Record<string, FieldStatistics>
  histograms: Record<string, HistogramData>
  boxplots: Record<string, BoxPlotData>
  missing_data: Record<string, MissingDataInfo>
}

export interface AnalysisTaskStatus {
  task_id: string
  name?: string
  status: string
  progress_message: string
  result?: AnalysisResult
  created_at?: string
  started_at?: string
  completed_at?: string
  error_message?: string
}

export interface AnalysisTaskListResponse {
  items: AnalysisTaskStatus[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface AnalysisCreateParams {
  name?: string
  ts_codes?: string[]
  start_rank?: number
  end_rank?: number
  start_date?: string
  end_date?: string
  feature_fields?: string[]
}

export interface AnalysisRecord {
  id: string
  name: string
  task_id: string
  ts_codes: string[]
  start_date: string
  end_date: string
  feature_fields: string[]
  created_at: string
}

export interface AnalysisRecordListResponse {
  items: AnalysisRecord[]
  total: number
}

export const dataAnalysisApi = {
  async triggerAnalysis(params: AnalysisCreateParams) {
    return await api.post<{
      task_id: string
      status: string
      message: string
    }>('/data-analysis', params)
  },

  async getTaskStatus(taskId: string) {
    return await api.get<AnalysisTaskStatus>(`/data-analysis/task/${taskId}`)
  },

  async listTasks(params?: { page?: number; page_size?: number; status?: string }) {
    const queryParams = new URLSearchParams()
    if (params?.page) queryParams.append('page', params.page.toString())
    if (params?.page_size) queryParams.append('page_size', params.page_size.toString())
    if (params?.status) queryParams.append('status', params.status)
    const query = queryParams.toString() ? `?${queryParams.toString()}` : ''
    return await api.get<AnalysisTaskListResponse>(`/data-analysis/tasks${query}`)
  },

  async listResults(limit: number = 20) {
    return await api.get<AnalysisRecord[]>(`/data-analysis/results?limit=${limit}`)
  },

  async deleteResult(id: string) {
    return await api.delete(`/data-analysis/results/${id}`)
  },
}

export const DEFAULT_FEATURE_FIELDS: readonly string[] = INDICATOR_FIELDS
