import api from './index'

export interface TradeCalendarRecord {
  exchange: string
  cal_date: string
  is_open: number
  pretrade_date: string | null
  stock_count?: number
  indicator_rate?: number
}

export const tradeCalendarApi = {
  sync: () =>
    api.post<{ start_date: string; end_date: string; stored_count: number }>('/trade-calendar/sync'),

  triggerDailyUpdate: () =>
    api.post<{ message: string }>('/trade-calendar/daily-update'),

  list: (startDate?: string, endDate?: string) =>
    api.get<TradeCalendarRecord[]>('/trade-calendar', {
      params: { start_date: startDate, end_date: endDate },
    }),
}