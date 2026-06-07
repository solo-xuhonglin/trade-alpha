import request from './index'

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
    return request.get('/live-portfolio/options')
  },

  createPortfolio(name: string): Promise<{ data: PortfolioOption }> {
    return request.post('/live-portfolio/', { name })
  },

  getPortfolio(id?: string): Promise<{ data: LivePortfolio }> {
    const params = id ? { portfolio_id: id } : {}
    return request.get('/live-portfolio/', { params })
  },

  addPosition(data: {
    ts_code: string
    stock_name: string
    shares: number
    price: number
  }, portfolioId?: string): Promise<{ data: LivePortfolio }> {
    const params = portfolioId ? { portfolio_id: portfolioId } : {}
    return request.post('/live-portfolio/positions', data, { params })
  },

  updatePosition(
    id: string,
    data: { shares?: number; cost_price?: number },
    portfolioId?: string
  ): Promise<{ data: LivePortfolio }> {
    const params = portfolioId ? { portfolio_id: portfolioId } : {}
    return request.put(`/live-portfolio/positions/${id}`, data, { params })
  },

  deletePosition(id: string, portfolioId?: string): Promise<{ data: LivePortfolio }> {
    const params = portfolioId ? { portfolio_id: portfolioId } : {}
    return request.delete(`/live-portfolio/positions/${id}`, { params })
  },

  searchStocks(q: string): Promise<{ data: { items: StockSearchItem[] } }> {
    return request.get('/live-portfolio/stocks/search', { params: { q } })
  },
}