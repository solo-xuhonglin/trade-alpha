"""Main entry point for stock prediction."""

from datetime import datetime, timedelta
from trade_alpha.data import fetch_and_store
from trade_alpha.indicators import calculate_and_store_ma, calculate_and_store_macd
from trade_alpha.predict import predict


def main():
    ts_code = "002594.SZ"

    today = datetime.now()
    start_date = (today - timedelta(days=365)).strftime("%Y%m%d")
    end_date = today.strftime("%Y%m%d")

    print(f"Fetching data for {ts_code} from {start_date} to {end_date}...")
    fetch_and_store(ts_code, start_date, end_date)

    print("Calculating indicators...")
    calculate_and_store_ma(ts_code, periods=[5, 10, 20, 60])
    calculate_and_store_macd(ts_code)

    print("Predicting...")
    result = predict(ts_code, targets=["open", "close", "high", "low"])

    print()
    print("Prediction result:")
    for key, value in result.items():
        print(f"  {key}: {value:.2f}")


if __name__ == "__main__":
    main()
