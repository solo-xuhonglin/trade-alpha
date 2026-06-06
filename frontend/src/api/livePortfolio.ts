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

export const livePortfolioApi = {
  getPortfolio(): Promise<{ data: LivePortfolio }> {
    return request.get('/live-portfolio/')
  },

  addPosition(data: {
    ts_code: string
    stock_name: string
    shares: number
    price: number
  }): Promise<{ data: LivePortfolio }> {
    return request.post('/live-portfolio/positions', data)
  },

  updatePosition(
    id: string,
    data: { shares?: number; cost_price?: number }
  ): Promise<{ data: LivePortfolio }> {
    return request.put(`/live-portfolio/positions/${id}`, data)
  },

  deletePosition(id: string): Promise<{ data: LivePortfolio }> {
    return request.delete(`/live-portfolio/positions/${id}`)
  },

  searchStocks(q: string): Promise<{ data: { items: StockSearchItem[] } }> {
    return request.get('/live-portfolio/stocks/search', { params: { q } })
  },
}