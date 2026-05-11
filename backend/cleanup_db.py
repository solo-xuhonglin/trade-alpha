"""Script to clean up test database."""

import asyncio
from trade_alpha.dao.mongodb import init_db, get_database


async def cleanup():
    """Clean up test data from database."""
    await init_db()
    db = await get_database()

    print("Cleaning up test database...")

    old_collections = [
        "portfolios", "strategies", "predictions",
        "trainings", "signals", "backtests"
    ]

    for coll_name in old_collections:
        try:
            await db.drop_collection(coll_name)
            print(f"Dropped collection: {coll_name}")
        except Exception as e:
            print(f"Warning: Could not drop {coll_name}: {e}")

    print("\nDatabase cleanup complete!")


if __name__ == "__main__":
    asyncio.run(cleanup())
