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
  use_momentum_boost?: boolean
  momentum_window?: number
  max_momentum_bonus?: number
  use_explosion_filter?: boolean
  explosion_price_threshold?: number
  explosion_volume_ratio?: number
  explosion_window?: number
  use_trend_bonus?: boolean
  trend_bonus_window?: number
  trend_bonus_scale?: number
  trend_r2_threshold?: number
  trend_max_bonus?: number
  use_volatility_penalty?: boolean
  vol_penalty_window?: number
  vol_range_tolerance?: number
  vol_penalty_scale?: number
  vol_max_penalty?: number
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
