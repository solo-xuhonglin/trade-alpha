import api from './index'

export interface Strategy {
  id: string
  name: string
  type: string
  config: Record<string, any>
  created_at: string
}

export const strategyApi = {
  list: () => api.get<Strategy[]>('/strategies'),
  get: (id: string) => api.get<Strategy>(`/strategies/${id}`),
  create: (data: Partial<Strategy>) => api.post<Strategy>('/strategies', data),
  update: (id: string, data: Partial<Strategy>) => api.put(`/strategies/${id}`, data),
  delete: (id: string) => api.delete(`/strategies/${id}`),
}
