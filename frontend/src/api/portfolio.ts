import api from './index'

export interface Portfolio {
  id: string
  name: string
  initial_capital: number
  cash: number
  position: number
  buy_fee_rate: number
  sell_fee_rate: number
  stamp_tax_rate: number
  min_fee: number
}

export const portfolioApi = {
  list: () => api.get<Portfolio[]>('/portfolios'),
  get: (id: string) => api.get<Portfolio>(`/portfolios/${id}`),
  create: (data: Partial<Portfolio>) => api.post<Portfolio>('/portfolios', data),
  update: (id: string, data: Partial<Portfolio>) => api.put(`/portfolios/${id}`, data),
  delete: (id: string) => api.delete(`/portfolios/${id}`),
}
