import api from './index'

export interface Strategy {
  id: string
  name: string
  type: string
  min_order_value: number
  stop_loss_pct: number
  max_hold_days: number
  min_hold_days: number
  buy_threshold: number
  sell_threshold: number
  max_positions?: number
  max_position_pct?: number
  sell_rank_n?: number
  hold_score_threshold?: number
  use_momentum_boost?: boolean
  momentum_window?: number
  max_momentum_bonus?: number
  use_momentum_penalty?: boolean
  use_explosion_filter?: boolean
  explosion_price_threshold?: number
  explosion_volume_ratio?: number
  explosion_window?: number
  use_full_position_sell?: boolean
  full_position_threshold?: number
  full_position_days?: number
  full_position_score_window?: number
  full_position_sell_count?: number
  use_rank_up_priority?: boolean
  rank_up_window?: number
  rank_up_count?: number
  rank_up_min_score?: number
  rank_up_min_improvement_pct?: number
  ranking_smooth_window?: number
  use_trend_bonus?: boolean
  score_decline_threshold?: number
  use_score_decline_filter?: boolean
  full_position_pnl_weight?: number
  trend_bonus_window?: number
  trend_bonus_scale?: number
  trend_r2_threshold?: number
  trend_max_bonus?: number
  use_trend_penalty?: boolean
  ranking_smooth_alpha?: number
  market_smooth_window?: number
  market_smooth_alpha?: number
  top_n_retention?: number
  retention_days?: number
  correlation_window?: number
  use_phase_strategy?: boolean
  phase_crash_threshold?: number
  phase_recovery_threshold?: number
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
