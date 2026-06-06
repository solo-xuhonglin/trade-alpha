"""Run live suggestion and print results.

Usage:
    python scripts/run_live_suggestion.py --training <id> --strategy <id>

Example:
    python scripts/run_live_suggestion.py --training 65d8def... --strategy 65d8ghi...
"""
import asyncio
import argparse
import sys
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.dao.model_config import ModelConfig
from trade_alpha.dao.mongodb import document_models
from trade_alpha.execution.suggestion_pipeline import SuggestionPipeline
from trade_alpha.models.training.trainer import get_training_by_id
from trade_alpha.models.training.config import get_config_by_id
from trade_alpha.logging import get_logger

logger = get_logger("run_live_suggestion")


async def main():
    parser = argparse.ArgumentParser(description="Run live suggestion")
    parser.add_argument("--training", required=True, help="Training ID")
    parser.add_argument("--strategy", required=True, help="Strategy config ID")
    args = parser.parse_args()

    # Connect to MongoDB
    from trade_alpha.dao.mongodb import MONGODB_URL, DATABASE_NAME
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]
    await init_beanie(db, document_models=document_models)

    # Load configs
    training = await get_training_by_id(args.training)
    if not training:
        logger.error(f"Training not found: {args.training}")
        sys.exit(1)

    strategy = await StrategyConfig.get(args.strategy)
    if not strategy:
        logger.error(f"Strategy config not found: {args.strategy}")
        sys.exit(1)

    model_config = await get_config_by_id(training.config_id)
    if not model_config:
        logger.error("Training has no associated model config")
        sys.exit(1)

    # Build pipeline
    pipeline = SuggestionPipeline(
        training_id=training.id,
        model_config=model_config,
        strategy_config=strategy,
    )

    # Run
    run_id = await pipeline.run()
    logger.info(f"Live suggestion completed: run_id={run_id}")

    # Print summary
    from trade_alpha.dao.live_suggestion_run import LiveSuggestionRun
    from trade_alpha.dao.live_order_suggestion import LiveOrderSuggestion
    run_record = await LiveSuggestionRun.get(run_id)
    suggestions = await LiveOrderSuggestion.find(LiveOrderSuggestion.trade_date == run_record.target_date).to_list()
    print(f"\n=== Live Suggestion Result ===")
    print(f"Run ID: {run_id}")
    print(f"Target Date: {run_record.target_date}")
    print(f"Status: {run_record.status}")
    print(f"Orders: {len(suggestions)}")
    print(f"\nTop suggestions:")
    for s in sorted(suggestions, key=lambda x: x.composite_score, reverse=True)[:10]:
        print(f"  {s.ts_code} ({s.stock_name}): score={s.composite_score:.3f}, "
              f"rank={s.rank}, price={s.order_price:.2f}, shares={s.order_shares}")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())