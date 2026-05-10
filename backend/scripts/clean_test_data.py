"""Clean up integration test default data.

Run this script when there are incompatible schema changes:
    cd backend
    $env:PYTHONPATH='src'
    python scripts/clean_test_data.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from trade_alpha.dao import MongoDB, StockDailyDAO
from trade_alpha.predict import config_service, training_service


def clean_all():
    """Clean all default test data."""
    dao = MongoDB()

    print("Cleaning test data...")

    stock_daily_dao = StockDailyDAO()

    print("  - stock_daily (002594.SZ)")
    stock_daily_dao.delete_by_ts_code("002594.SZ")
    stock_daily_dao.delete_by_ts_code("601398.SH")

    print("  - stock_list")
    dao._get_collection("stock_list").delete_many({})

    print("  - portfolios (test_portfolio)")
    dao._get_collection("portfolios").delete_many({"name": {"$regex": "^test_"}})

    print("  - strategies (test_strategy)")
    dao._get_collection("strategies").delete_many({"name": {"$regex": "^test_"}})

    print("  - signals")
    dao._get_collection("signals").delete_many({})

    print("  - model_configs (test_model_config)")
    configs = list(dao._get_collection("model_configs").find({"name": {"$regex": "^test_"}}))
    for c in configs:
        config_id = str(c["_id"])
        trainings = list(dao._get_collection("trainings").find({"config_id": c["_id"]}))
        for t in trainings:
            if t.get("model_path") and os.path.exists(t["model_path"]):
                os.remove(t["model_path"])
            dao._get_collection("trainings").delete_one({"_id": t["_id"]})
        dao._get_collection("model_configs").delete_one({"_id": c["_id"]})

    print("  - trainings (test_training)")
    trainings = list(dao._get_collection("trainings").find({"name": {"$regex": "^test_"}}))
    for t in trainings:
        if t.get("model_path") and os.path.exists(t["model_path"]):
            os.remove(t["model_path"])
        dao._get_collection("trainings").delete_one({"_id": t["_id"]})

    print("  - models directory")
    models_dir = os.path.join(os.path.dirname(__file__), '..', 'models')
    if os.path.exists(models_dir):
        import shutil
        for item in os.listdir(models_dir):
            item_path = os.path.join(models_dir, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)

    print("  - backtests (test_backtest)")
    backtests = list(dao._get_collection("backtests").find({"portfolio_name": {"$regex": "^test_"}}))
    for bt in backtests:
        dao._get_collection("backtest_trades").delete_many({"backtest_id": bt["_id"]})
        dao._get_collection("backtests").delete_one({"_id": bt["_id"]})

    print("  - backtest_trades")
    dao._get_collection("backtest_trades").delete_many({})

    dao.close()

    print("\nDone! All test data cleaned.")


if __name__ == "__main__":
    clean_all()
