export const DAILY_BASIC_FIELDS = [
  'open', 'high', 'low', 'close', 'vol', 'amount',
  'candle_body_pct', 'candle_upper_pct', 'candle_lower_pct',
  'close_location_pct', 'gap_pct', 'gap_fill_pct',
]

export const INDICATOR_FIELDS = [
  'ma_5', 'ma_10', 'ma_20', 'ma_40', 'ma_60',
  'macd', 'macd_signal', 'macd_hist',
  'pct_chg',
  'bias_5', 'bias_10', 'bias_20', 'bias_60',
  'close_position_5', 'close_position_10', 'close_position_20', 'close_position_60',
  'vol_ratio_5', 'vol_ratio_10', 'vol_ratio_20', 'vol_ratio_60',
  'kdj_k', 'kdj_d', 'kdj_j',
  'boll_upper', 'boll_middle', 'boll_lower', 'boll_position',
  'rsi_6', 'rsi_12',
  'trend_arrangement_5', 'trend_arrangement_10', 'trend_arrangement_20',
  'trend_slope_5', 'trend_slope_10', 'trend_slope_20',
  'trend_volume_5', 'trend_volume_10', 'trend_volume_20',
  'trend_stability_5', 'trend_stability_10', 'trend_stability_20',
  'obv',
]

export const ALL_FEATURE_FIELDS = [...DAILY_BASIC_FIELDS, ...INDICATOR_FIELDS]

export const PRICE_INDEPENDENT_FIELDS = [
  'pct_chg',
  'bias_5', 'bias_10', 'bias_20', 'bias_60',
  'close_position_5', 'close_position_10', 'close_position_20', 'close_position_60',
  'vol_ratio_5', 'vol_ratio_10', 'vol_ratio_20', 'vol_ratio_60',
  'kdj_k', 'kdj_d', 'kdj_j',
  'boll_position',
  'rsi_6', 'rsi_12',
  'trend_arrangement_5', 'trend_arrangement_10', 'trend_arrangement_20',
  'trend_slope_5', 'trend_slope_10', 'trend_slope_20',
  'trend_volume_5', 'trend_volume_10', 'trend_volume_20',
  'trend_stability_5', 'trend_stability_10', 'trend_stability_20',
  'obv',
]

export const LSTM_RECOMMENDED_FIELDS = [
  'macd', 'macd_signal', 'macd_hist',
  'rsi_6', 'rsi_12',
  'bias_5', 'bias_10', 'bias_20',
  'boll_position',
  'kdj_k', 'kdj_d', 'kdj_j',
  'vol_ratio_5', 'vol_ratio_10',
  'trend_slope_5', 'trend_slope_10',
  'trend_volume_5', 'trend_volume_10',
]

export const LSTM_AFFECTED_BY_PRICE_FIELDS = [
  'ma_5', 'ma_10', 'ma_20', 'ma_40', 'ma_60',
  'macd', 'macd_signal', 'macd_hist',
  'boll_upper', 'boll_middle', 'boll_lower',
]
