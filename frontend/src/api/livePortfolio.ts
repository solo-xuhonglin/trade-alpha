import api from './index'

export interface LivePosition {
  id: string
  ts_code: string
  stock_name: string
  shares: number
  cost_price: number
  total_cost: number
  created_at: string
  updated_at: string
}

export interface LivePortfolio {
  id: string
  positions: LivePosition[]
  created_at: string
  updated_at: string
}

export interface StockSearchItem {
  ts_code: string
  name: string
  industry: string | null
  market: string | null
}

export interface PortfolioOption {
  id: string
  name: string
}

export const livePortfolioApi = {
  listOptions(): Promise<{ data: { items: PortfolioOption[] } }> {
    return api.get('/live-portfolio/options')
  },

  createPortfolio(name: string): Promise<{ data: LivePortfolio }> {
    return api.post('/live-portfolio/', { name })
  },

  deletePortfolio(id: string): Promise<void> {
    return api.delete(`/live-portfolio/${id}`)
  },

  getPortfolio(id?: string): Promise<{ data: LivePortfolio }> {
    const params: Record<string, string> = {}
    if (id) params.id = id
    return api.get('/live-portfolio/', { params })
  },

  addPosition(data: {
    ts_code: string
    stock_name: string
    shares: number
    price: number
  }, portfolioId?: string): Promise<{ data: LivePortfolio }> {
    const params: Record<string, string> = {}
    if (portfolioId) params.portfolio_id = portfolioId
    return api.post('/live-portfolio/positions', data, { params })
  },

  updatePosition(
    id: string,
    data: { shares?: number; cost_price?: number },
    portfolioId?: string
  ): Promise<{ data: LivePortfolio }> {
    const params: Record<string, string> = {}
    if (portfolioId) params.portfolio_id = portfolioId
    return api.put(`/live-portfolio/positions/${id}`, data, { params })
  },

  deletePosition(id: string, portfolioId?: string): Promise<{ data: LivePortfolio }> {
    const params: Record<string, string> = {}
    if (portfolioId) params.portfolio_id = portfolioId
    return api.delete(`/live-portfolio/positions/${id}`, { params })
  },

  searchStocks(q: string): Promise<{ data: { items: StockSearchItem[] } }> {
    return api.get('/live-portfolio/stocks/search', { params: { q } })
  },
}
