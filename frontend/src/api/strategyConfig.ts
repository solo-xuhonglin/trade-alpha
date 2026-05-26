import api from './index'

export interface Strategy {
  id: string
  name: string
  type: string
  min_order_value: number
  stop_loss_pct: number
  max_hold_days: number
  buy_threshold: number
  sell_threshold: number
  max_positions?: number
  max_position_pct?: number
  sell_rank_n?: number
  hold_score_threshold?: number
  created_at: string
  updated_at?: string
}

export const strategyConfigApi = {
  list: () => api.get<Strategy[]>('/strategies'),
  get: (id: string) => api.get<Strategy>(`/strategies/${id}`),
  create: (data: Partial<Strategy>) => api.post<Strategy>('/strategies', data),
  update: (id: string, data: Partial<Strategy>) => api.put(`/strategies/${id}`, data),
  delete: (id: string) => api.delete(`/strategies/${id}`),
}
