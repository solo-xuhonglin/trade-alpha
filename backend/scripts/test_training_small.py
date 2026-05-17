"""Test training with small data."""
import asyncio
from trade_alpha.dao import init_db, StockList
from trade_alpha.predict import config_service, training_service
from trade_alpha.logging import setup_logging

async def main():
    setup_logging(log_level="INFO")
    await init_db()

    ts_codes = ["002594.SZ"]
    print(f"Training with: {ts_codes}")

    config = await config_service.get_config_by_name("test_model_config")
    if not config:
        print("Config not found")
        return

    print(f"Config: {config.name} ({config.id})")

    await training_service.delete_training_by_name("test_run")

    def progress_callback(progress, message):
        print(f"[{progress:.1f}%] {message}")

    training = await training_service.create_training(
        config_id=config.id,
        name="test_run",
        ts_codes=ts_codes,
        start_date="20200101",
        end_date="20200630",
        progress_callback=progress_callback,
    )

    print(f"\nTraining completed: {training.id}")
    print(f"Samples: {training.metrics.get('sample_count', 'N/A')}")

if __name__ == "__main__":
    asyncio.run(main())
