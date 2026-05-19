"""Clean up data analysis results collection using direct pymongo."""

from trade_alpha.config import load_config
from pymongo import MongoClient


def cleanup_analysis_data():
    """Delete all data analysis results and associated tasks directly."""
    config = load_config()
    client = MongoClient(config.mongodb_uri)
    db = client.get_database(config.mongodb_db)

    # Delete all analysis results
    count = db["data_analysis_results"].delete_many({})
    print(f"Deleted {count.deleted_count} analysis results")

    # Delete all data analysis tasks
    count = db["tasks"].delete_many({"type": "data_analysis"})
    print(f"Deleted {count.deleted_count} analysis tasks")

    print("\nCleanup complete!")
    client.close()


if __name__ == "__main__":
    cleanup_analysis_data()
