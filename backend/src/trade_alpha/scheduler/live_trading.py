"""Live trading scheduler module."""

from datetime import datetime, timezone
from typing import List

from trade_alpha.dao import (
    init_db,
    AccountConfig,
    StrategyConfig,
    ModelConfig,
    StockList,
    OrderSuggestion,
)
from trade_alpha.execution.pipeline import ExecutionPipeline
from trade_alpha.execution.schemas import OrderSuggestion as ExecutionOrderSuggestion
from trade_alpha.logging import get_logger, setup_logging

logger = get_logger("scheduler.live_trading")


async def get_default_account_config() -> AccountConfig:
    """Get the default account configuration."""
    configs = await AccountConfig.find_all().to_list()
    if not configs:
        raise ValueError("No account configuration found")
    return configs[0]


async def get_default_strategy_config() -> StrategyConfig:
    """Get the default strategy configuration."""
    configs = await StrategyConfig.find_all().to_list()
    if not configs:
        raise ValueError("No strategy configuration found")
    return configs[0]


async def get_default_model_config() -> ModelConfig:
    """Get the default model configuration."""
    configs = await ModelConfig.find_all().to_list()
    if not configs:
        raise ValueError("No model configuration found")
    return configs[0]


async def get_stock_list() -> List[str]:
    """Get list of stock codes from database."""
    stocks = await StockList.find_all().to_list()
    return [stock.ts_code for stock in stocks]


async def run_live_trading():
    """
    Run live trading execution.
    
    This function:
    1. Gets default configurations (account, strategy, model)
    2. Gets stock list from database
    3. Creates and runs ExecutionPipeline in live mode
    4. Saves order suggestions to database
    """
    logger.info("run_live_trading", "Starting live trading execution")
    
    try:
        # Initialize database
        await init_db()
        
        # Get configurations
        logger.info("run_live_trading", "Loading configurations")
        account_config = await get_default_account_config()
        strategy_config = await get_default_strategy_config()
        model_config = await get_default_model_config()
        
        logger.info("run_live_trading", 
            f"Using account config: {account_config.name}, "
            f"strategy config: {strategy_config.name}, "
            f"model config: {model_config.name}"
        )
        
        # Get stock list
        logger.info("run_live_trading", "Loading stock list")
        ts_codes = await get_stock_list()
        logger.info("run_live_trading", f"Loaded {len(ts_codes)} stocks")
        
        if not ts_codes:
            logger.warning("run_live_trading", "No stocks to process")
            return
        
        # Create execution pipeline
        logger.info("run_live_trading", "Creating execution pipeline")
        pipeline = ExecutionPipeline(
            account_config=account_config,
            strategy_config=strategy_config,
            model_config=model_config,
        )
        
        # Get today's date
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        logger.info("run_live_trading", f"Running live trading for date: {today}")
        
        # Run pipeline
        suggestions = await pipeline.run(
            mode="live",
            ts_codes=ts_codes,
            date=today,
        )
        
        # Save order suggestions to database
        logger.info("run_live_trading", f"Saving {len(suggestions)} order suggestions")
        saved_count = 0
        
        for suggestion in suggestions:
            if isinstance(suggestion, ExecutionOrderSuggestion):
                order_doc = OrderSuggestion(
                    ts_code=suggestion.ts_code,
                    stock_name=suggestion.stock_name,
                    date=today,
                    action=suggestion.action,
                    suggested_price=suggestion.suggested_price,
                    suggested_shares=suggestion.suggested_shares,
                    signal_strength=suggestion.signal_strength,
                    position_reason=suggestion.position_reason,
                    risk_notes=suggestion.risk_notes,
                    prediction_data=suggestion.prediction_data,
                    account_config_id=account_config.id,
                    strategy_id=strategy_config.id,
                    training_id=model_config.id,  # Using model config id as training id
                    status=suggestion.status,
                    created_at=datetime.now(timezone.utc),
                )
                await order_doc.insert()
                saved_count += 1
        
        logger.info("run_live_trading", f"Successfully saved {saved_count} order suggestions")
        logger.info("run_live_trading", "Live trading execution completed successfully")
        
    except Exception as e:
        logger.error("run_live_trading", f"Live trading execution failed: {str(e)}")
        raise


if __name__ == "__main__":
    import asyncio
    
    setup_logging()
    
    try:
        asyncio.run(run_live_trading())
    except Exception as e:
        logger.error("__main__", f"Error running live trading: {str(e)}")
        exit(1)