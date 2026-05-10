"""Debug script to check backtest trades."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from trade_alpha.dao import MongoDB

dao = MongoDB()
backtests = list(dao._get_collection('backtests').find())
print(f'Backtests: {len(backtests)}')
for bt in backtests:
    print(f"  - {bt.get('portfolio_name')}: {bt.get('ts_code')}")
    trades = list(dao._get_collection('backtest_trades').find({'backtest_id': bt['_id']}))
    print(f"    Trades: {len(trades)}")
    for t in trades[:3]:
        print(f"      {t.get('trade_date')}: {t.get('action')} {t.get('shares')} @ {t.get('price')}")
dao.close()
