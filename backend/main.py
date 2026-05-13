"""Main entry point for stock prediction and trading signal."""

from datetime import datetime, timedelta
from trade_alpha.data.service import fetch_and_store_stock_daily
from trade_alpha.indicators.service import calculate_all_indicators
from trade_alpha.predict import predict


def main():
    ts_code = "002594.SZ"

    today = datetime.now()
    start_date = (today - timedelta(days=365)).strftime("%Y%m%d")
    end_date = today.strftime("%Y%m%d")

    print(f"Fetching data for {ts_code} from {start_date} to {end_date}...")
    count = fetch_and_store_stock_daily(ts_code, start_date, end_date)
    print(f"  Fetched {count} records")

    print("Calculating all indicators...")
    calculate_all_indicators(ts_code)

    print("Predicting...")
    result = predict(ts_code, targets=["open", "close", "high", "low"])

    print()
    print("Prediction result:")
    for key, value in result.items():
        print(f"  {key}: {value:.2f}")

    # Signal generation moved to execution pipeline


if __name__ == "__main__":
    main()
