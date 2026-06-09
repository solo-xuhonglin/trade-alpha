import apiClient from './client'

export interface ScheduledTaskConfig {
  _id: string
  name: string
  task_key: string
  enabled: boolean
  trigger_type: 'interval' | 'cron'
  interval_seconds: number | null
  cron_hour: number | null
  cron_minute: number | null
  params: Record<string, string>
  created_at: string
  updated_at: string
  last_run_at: string | null
  last_status: string | null
  last_result_message: string | null
}

export interface ScheduledTaskLogItem {
  id: string
  config_id: string
  task_key: string
  task_name: string
  status: string
  started_at: string
  completed_at: string | null
  duration_ms: number | null
  error_message: string | null
  result_message: string | null
}

export interface LogListResponse {
  items: ScheduledTaskLogItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export async function getConfigs(): Promise<{ data: { items: ScheduledTaskConfig[] } }> {
  return apiClient.get('/scheduled-tasks')
}

export async function updateConfig(id: string, data: Partial<ScheduledTaskConfig>): Promise<void> {
  return apiClient.put(`/scheduled-tasks/${id}`, data)
}

export async function triggerConfig(id: string): Promise<{ data: { status: string; result_message: string | null } }> {
  return apiClient.post(`/scheduled-tasks/${id}/trigger`)
}

export async function getLogs(params: {
  task_key?: string
  page?: number
  page_size?: number
}): Promise<{ data: LogListResponse }> {
  return apiClient.get('/scheduled-tasks/logs', { params })
}