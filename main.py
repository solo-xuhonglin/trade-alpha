"""Main entry point for stock prediction and trading signal."""

from datetime import datetime, timedelta
from trade_alpha.data import fetch_and_store
from trade_alpha.indicators import calculate_and_store_ma, calculate_and_store_macd
from trade_alpha.predict import predict
from trade_alpha.strategy import generate_signal


def main():
    ts_code = "002594.SZ"

    today = datetime.now()
    start_date = (today - timedelta(days=365)).strftime("%Y%m%d")
    end_date = today.strftime("%Y%m%d")

    print(f"Fetching data for {ts_code} from {start_date} to {end_date}...")
    try:
        count = fetch_and_store(ts_code, start_date, end_date)
        print(f"  Fetched {count} records")
    except Exception as e:
        print(f"  Error fetching data: {e}")

    print("Calculating indicators...")
    calculate_and_store_ma(ts_code, periods=[5, 10, 20, 60])
    calculate_and_store_macd(ts_code)

    print("Predicting...")
    result = predict(ts_code, targets=["open", "close", "high", "low"])

    print()
    print("Prediction result:")
    for key, value in result.items():
        print(f"  {key}: {value:.2f}")

    print()
    print("Generating trading signal...")
    signal = generate_signal(ts_code, strategy="price")

    print()
    print("Trading signal:")
    print(f"  Action: {signal.get('action', 'N/A')}")
    print(f"  Current price: {signal.get('current_price', 0):.2f}")
    print(f"  Target price: {signal.get('target_price', 0):.2f}")
    print(f"  Reason: {signal.get('reason', 'N/A')}")


if __name__ == "__main__":
    main()
