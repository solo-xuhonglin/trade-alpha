import api from './index'

export interface DataRecord {
  ts_code: string
  trade_date: string
  open: number
  high: number
  low: number
  close: number
  vol: number
  amount: number
  ma_5?: number
  ma_10?: number
  ma_20?: number
  ma_40?: number
  ma_60?: number
  macd?: number
  macd_signal?: number
  macd_hist?: number
  obv_chg_5?: number
  obv_chg_10?: number
  obv_chg_20?: number
}

export interface Stock {
  ts_code: string
  name: string
  industry?: string
  list_date?: string
  market?: string
  total_mv?: number
  pe?: number
  pb?: number
  updated_at?: string
  sync_status: string
  data_count?: number
  latest_date?: string
}

export interface StockListResponse {
  items: Stock[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface DataRecordListResponse {
  items: DataRecord[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export const dataApi = {
  listStocks: (page: number = 1, pageSize: number = 20, startRank?: number, endRank?: number) => {
    const params: any = { page, page_size: pageSize }
    if (startRank !== undefined && endRank !== undefined) {
      params.start_rank = startRank
      params.end_rank = endRank
    }
    return api.get<StockListResponse>('/data/stocks', { params })
  },

  updateStocks: () =>
    api.post('/data/stocks/update'),

  getData: (tsCode: string, startDate?: string, endDate?: string) =>
    api.get<DataRecord[]>(`/data/${tsCode}`, { params: { start_date: startDate, end_date: endDate } }),

  getDataPaginated: (tsCode: string, page: number = 1, pageSize: number = 500) =>
    api.get<DataRecordListResponse>(`/data/${tsCode}/paginated`, { params: { page, page_size: pageSize } }),

  fetchData: (tsCode: string, startDate: string, endDate: string) =>
    api.post('/data', { ts_code: tsCode, start_date: startDate, end_date: endDate }),

  deleteData: (tsCode: string) =>
    api.delete(`/data/${tsCode}`),

}
