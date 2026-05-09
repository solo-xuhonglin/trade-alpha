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
  ma_60?: number
  macd?: number
  macd_signal?: number
  macd_hist?: number
}

export const dataApi = {
  getData: (tsCode: string, startDate?: string, endDate?: string) =>
    api.get<DataRecord[]>(`/data/${tsCode}`, { params: { start_date: startDate, end_date: endDate } }),
  
  fetchData: (tsCode: string, startDate: string, endDate: string) =>
    api.post('/data', { ts_code: tsCode, start_date: startDate, end_date: endDate }),
  
  deleteData: (tsCode: string) =>
    api.delete(`/data/${tsCode}`),
}
