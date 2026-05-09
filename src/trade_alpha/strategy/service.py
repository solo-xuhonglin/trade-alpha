"""Strategy service."""

from datetime import datetime
from trade_alpha.db.storage import Storage
from trade_alpha.strategy.base import StrategyContext
from trade_alpha.strategy.price import PriceStrategy


STRATEGIES = {
    "price": PriceStrategy,
}


def generate_signal(
    ts_code: str,
    strategy: str = "price"
) -> dict[str, any]:
    """Generate trading signal and store to database.

    Args:
        ts_code: Stock code
        strategy: Strategy name, default "price"

    Returns:
        Signal result dictionary
    """
    storage = Storage()
    records = storage.find_by_ts_code(ts_code)

    if not records:
        storage.close()
        return {}

    latest = records[-1]

    prediction = {}
    pred_records = list(storage._get_collection("predictions").find(
        {"ts_code": ts_code},
        {"_id": 0, "target_open": 1, "target_close": 1, "target_high": 1, "target_low": 1}
    ).sort("trade_date", -1).limit(1))
    if pred_records:
        pred = pred_records[0]
        prediction = {
            "open": pred.get("target_open"),
            "close": pred.get("target_close"),
            "high": pred.get("target_high"),
            "low": pred.get("target_low"),
        }

    indicator_cols = [col for col in latest.keys() if col.startswith(("ma_", "macd"))]
    indicators = {col: latest[col] for col in indicator_cols if latest.get(col) is not None}

    context = StrategyContext(
        ts_code=ts_code,
        trade_date=latest["trade_date"],
        current_price=float(latest["close"]),
        prediction=prediction,
        indicators=indicators,
    )

    strategy_cls = STRATEGIES.get(strategy)
    if strategy_cls is None:
        storage.close()
        return {}

    action = strategy_cls().decide(context)

    today = datetime.now().strftime("%Y%m%d")

    signal_record = {
        "ts_code": ts_code,
        "trade_date": today,
        "strategy": strategy,
        "action": action,
        "current_price": context.current_price,
        "target_price": prediction.get("close"),
        "reason": f"{strategy} strategy",
    }

    storage.insert_many([signal_record], collection="signals")
    storage.close()

    return {
        "action": action,
        "current_price": context.current_price,
        "target_price": prediction.get("close"),
        "reason": signal_record["reason"],
    }
