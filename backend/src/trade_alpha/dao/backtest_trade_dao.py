"""Backtest trade DAO module."""

from typing import Any, Optional
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
from trade_alpha.dao.mongodb import MongoDB


class BacktestTradeDAO:
    """DAO for backtest_trades collection."""

    def __init__(self, db: MongoDB | None = None):
        self.db = db or MongoDB()
        self.collection = "backtest_trades"

    def insert_many(self, docs: list[dict[str, Any]]) -> int:
        """Insert multiple trade documents.

        Args:
            docs: List of trade documents

        Returns:
            Number of documents inserted
        """
        if not docs:
            return 0
        coll = self.db._get_collection(self.collection)
        result = coll.insert_many(docs)
        return len(result.inserted_ids)

    def find_by_backtest_id(
        self,
        backtest_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """Find trades by backtest ID with pagination.

        Args:
            backtest_id: Backtest ID
            page: Page number (1-based)
            page_size: Items per page

        Returns:
            Tuple of (list of trades, total count)
        """
        coll = self.db._get_collection(self.collection)
        query = {"backtest_id": ObjectId(backtest_id)}
        total = coll.count_documents(query)
        skip = (page - 1) * page_size
        results = list(
            coll.find(query)
            .sort("trade_date", ASCENDING)
            .skip(skip)
            .limit(page_size)
        )
        return results, total

    def find_all(
        self,
        portfolio_id: str | None = None,
        strategy_id: str | None = None,
        training_id: str | None = None,
        ts_code: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """Find all trades with filtering and pagination.

        Args:
            portfolio_id: Filter by portfolio ID
            strategy_id: Filter by strategy ID
            training_id: Filter by training ID
            ts_code: Filter by stock code
            page: Page number (1-based)
            page_size: Items per page

        Returns:
            Tuple of (list of trades, total count)
        """
        coll = self.db._get_collection(self.collection)

        query_conditions = []
        if portfolio_id:
            try:
                query_conditions.append({"portfolio_id": ObjectId(portfolio_id)})
            except Exception:
                pass
        if strategy_id:
            try:
                query_conditions.append({"strategy_id": ObjectId(strategy_id)})
            except Exception:
                pass
        if training_id:
            try:
                query_conditions.append({"training_id": ObjectId(training_id)})
            except Exception:
                pass
        if ts_code:
            query_conditions.append({"ts_code": ts_code})

        query = {"$and": query_conditions} if query_conditions else {}
        total = coll.count_documents(query)
        skip = (page - 1) * page_size
        results = list(
            coll.find(query)
            .sort("trade_date", DESCENDING)
            .skip(skip)
            .limit(page_size)
        )
        return results, total

    def get_distinct_ts_codes(self) -> list[str]:
        """Get distinct stock codes.

        Returns:
            List of distinct ts_codes
        """
        coll = self.db._get_collection(self.collection)
        return coll.distinct("ts_code")

    def delete_by_backtest_id(self, backtest_id: str) -> int:
        """Delete all trades for a backtest.

        Args:
            backtest_id: Backtest ID

        Returns:
            Number of trades deleted
        """
        return self.db.delete_generic(
            {"backtest_id": ObjectId(backtest_id)},
            self.collection
        )
