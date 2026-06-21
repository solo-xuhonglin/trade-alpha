"""Debug data availability for improvement analysis."""
import asyncio
from beanie.odm.operators.find.comparison import In
from trade_alpha.dao.mongodb import init_db
from trade_alpha.dao import StockListHistory
from trade_alpha.dao.stock_daily import StockDaily


async def main():
    await init_db()
    date = "20240105"

    # 1. StockListHistory
    slh = await StockListHistory.find(StockListHistory.trade_date == date).sort(-StockListHistory.total_mv).limit(5).to_list(None)
    print(f"SLH {date}: {len(slh)} records")
    if slh:
        print(f"  top: {slh[0].ts_code} mv={slh[0].total_mv}")

    # 2. StockDaily indicator counts
    for field in ["trend_slope_20", "trend_arrangement_20", "close_position_20", "close_position_60", "bias_20", "bias_60", "atr_14"]:
        count = await StockDaily.find(StockDaily.trade_date == date, getattr(StockDaily, field) != None).count()
        print(f"  StockDaily.{field}: {count}")

    # 3. Stocks with both slope_20 and atr_14
    sd = await StockDaily.find(
        StockDaily.trade_date == date,
        StockDaily.trend_slope_20 != None,
        StockDaily.atr_14 != None,
    ).limit(300).to_list(None)
    print(f"StockDaily with both slope_20+atr_14: {len(sd)}")

    # 4. Forward return test
    codes = [r.ts_code for r in sd[:5]]
    mv_recs = await StockListHistory.find(
        StockListHistory.trade_date == date,
        In(StockListHistory.ts_code, codes),
        StockListHistory.total_mv != None,
    ).to_list(None)
    print(f"Have MV data for top 5: {len(mv_recs)}")

    # 5. Test forward_return approach
    future_date = "20240315"
    sd2 = await StockDaily.find(
        StockDaily.trade_date == future_date,
        StockDaily.ts_code == codes[0],
    ).to_list(None)
    print(f"Forward: {codes[0]} on {future_date}: {sd2[0].close if sd2 else 'NOT FOUND'}")

asyncio.run(main())
