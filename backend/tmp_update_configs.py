"""Update strategy configs in DB with new fields."""
import asyncio
from trade_alpha.dao.mongodb import init_db
from trade_alpha.dao.strategy_config import StrategyConfig


async def update_config(name: str) -> None:
    config = await StrategyConfig.find_one({"name": name})
    if not config:
        print(f"{name}: not found")
        return

    updates = {
        "sell_rank_pct": 0.15,
        "rotation_bottom_pct": 0.60,
        "rotation_rank_min_pct": 0.30,
        "rotation_rank_max_pct": 0.70,
        "rotation_was_top_pct": 0.15,
        "top_n_retention_pct": 0.20,
        "use_momentum_penalty": True,
        "use_trend_penalty": True,
    }

    for key, value in updates.items():
        setattr(config, key, value)

    await config.save()
    print(f"{name}: updated OK (id={config.id})")


async def main():
    await init_db()
    for name in ["default_strategy_big_long", "default_strategy_live_long"]:
        await update_config(name)


asyncio.run(main())
