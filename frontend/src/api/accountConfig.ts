import api from './index'

export interface AccountConfig {
  id: string
  name: string
  initial_capital: number
  cash: number
  position: number
  buy_fee_rate: number
  sell_fee_rate: number
  stamp_tax_rate: number
  min_fee: number
  created_at: string
  updated_at?: string
}

export const accountConfigApi = {
  list: () => api.get<AccountConfig[]>('/account-configs'),
  get: (id: string) => api.get<AccountConfig>(`/account-configs/${id}`),
  create: (data: Partial<AccountConfig>) => api.post<AccountConfig>('/account-configs', data),
  update: (id: string, data: Partial<AccountConfig>) => api.put(`/account-configs/${id}`, data),
  delete: (id: string) => api.delete(`/account-configs/${id}`),
}
